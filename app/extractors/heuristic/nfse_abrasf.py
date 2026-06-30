"""Regex-based parser for NFS-e ABRASF layouts (generic Brazilian municipalities).

The ABRASF model (adopted by Teresina, SP, RJ, BH, Curitiba, Porto Alegre
and many others) produces PDFs with a remarkably stable set of section
headers. We key off those headers to slice the text and then apply
narrow regex patterns inside each slice.

When a section cannot be located we fall back to first-match-in-document
heuristics. Every field is optional; the caller judges overall quality
via the confidence score.
"""

from __future__ import annotations

import re
from typing import Any

from app.extractors.heuristic import common  # noqa: I001

ISSUER_HEADERS = [
    "EMITENTE PRESTADOR DO SERVICO",
    "EMITENTE PRESTADOR",
    "PRESTADOR DO SERVICO",
    "PRESTADOR DE SERVICO",
    "DADOS DO PRESTADOR",
]

RECIPIENT_HEADERS = [
    "TOMADOR DO SERVICO",
    "TOMADOR DE SERVICO",
    "DADOS DO TOMADOR",
    "DESTINATARIO",
]

SERVICE_HEADERS = [
    "SERVICO PRESTADO",
    "DADOS DO SERVICO",
    "DISCRIMINACAO DOS SERVICOS",
    "DESCRICAO DO SERVICO PRESTADO",
]

CALC_HEADERS = [
    "CALCULO DO ISSQN",
    "VALOR TOTAL",
    "VALORES DA NFS-E",
    "VALOR DA NOTA",
]

END_HEADERS = [
    "EMITENTE PRESTADOR DO SERVICO",
    "EMITENTE PRESTADOR",
    "PRESTADOR DO SERVICO",
    "TOMADOR DO SERVICO",
    "TOMADOR DE SERVICO",
    "SERVICO PRESTADO",
    "DADOS DO SERVICO",
    "DESCRICAO DO SERVICO PRESTADO",
    "CALCULO DO ISSQN",
    "VALOR TOTAL",
    "RETENCOES",
    "INFORMACOES COMPLEMENTARES",
    "TRIBUTACAO MUNICIPAL",
]

NFSE_SIGNALS = [
    "NFS-E",
    "NFSE",
    "NOTA FISCAL DE SERVICOS",
    "NOTA FISCAL DE SERVICO",
    "PREFEITURA MUNICIPAL",
    "ISSQN",
    "TOMADOR",
    "PRESTADOR",
]


def is_nfse(text: str) -> bool:
    """Cheap layout detector — true if at least two NFS-e signals are present."""
    upper = common.normalize_for_match(text)
    hits = sum(1 for s in NFSE_SIGNALS if s in upper)
    return hits >= 2


def parse(text: str, *, hint_type: str | None = None) -> dict[str, Any] | None:
    """Return a ``FiscalDocumentData``-compatible dict, or ``None`` if the text
    does not look like an ABRASF NFS-e.
    """
    if not text:
        return None

    if hint_type and hint_type not in {"auto", "nfse"}:
        return None
    if not is_nfse(text):
        return None

    text = common.normalize_whitespace(text)
    upper = common.normalize_for_match(text)

    data: dict[str, Any] = {
        "document_category": "nfse",
        "document_subtype": "abrasf",
        "model": "99",
        "type": "saida",
        "direction": "outbound",
        "origin": "pdf_upload",
        "fiscal_info": {},
    }

    number, series = _extract_number_series(text, upper)
    if number:
        data["fiscal_document_number"] = number
    if series:
        data["series"] = series

    access_key = _extract_access_key(text, upper)
    if access_key:
        data["access_key"] = access_key
        data["fiscal_info"]["national_identifier"] = access_key

    issued_at = common.parse_datetime(text)
    if issued_at:
        data["issued_at"] = issued_at.isoformat()
    competence = common.parse_competence(text)
    if competence:
        data["competence_at"] = competence.isoformat()

    verification = _extract_verification_code(text, upper)
    if verification:
        data["fiscal_info"]["verification_code"] = verification

    issuer_block = common.section_between(text, ISSUER_HEADERS, [h for h in END_HEADERS if h not in ISSUER_HEADERS])
    if issuer_block:
        issuer = _parse_party(issuer_block)
        data["issuer_cnpj"] = issuer.get("document")
        data["issuer_name"] = issuer.get("name")
        if issuer.get("address"):
            data["issuer_address"] = issuer["address"]

    recipient_block = common.section_between(text, RECIPIENT_HEADERS, [h for h in END_HEADERS if h not in RECIPIENT_HEADERS])
    if recipient_block:
        recipient = _parse_party(recipient_block)
        data["recipient_document"] = recipient.get("document")
        data["recipient_name"] = recipient.get("name")
        if recipient.get("address"):
            data["recipient_address"] = recipient["address"]

    service_block = common.section_between(text, SERVICE_HEADERS, [h for h in END_HEADERS if h not in SERVICE_HEADERS])
    if service_block:
        nature = _extract_service_description(service_block)
        if nature:
            data["nature_operation"] = nature
        cnae_match = common.CNAE_RE.search(service_block)
        if cnae_match:
            data["fiscal_info"]["cnae"] = cnae_match.group(1)
        code_match = common.SERVICE_CODE_RE.search(service_block)
        if code_match:
            data["fiscal_info"]["service_code"] = code_match.group(1)

    calc_block = common.section_between(text, CALC_HEADERS, ["INFORMACOES COMPLEMENTARES"]) or text
    values = _extract_values(calc_block)
    data.update({k: v for k, v in values.items() if v is not None})

    _extract_tax_hints(text, data)
    _extract_retentions(text, data)

    if not data.get("issuer_cnpj"):
        cnpj = common.first_cnpj(text)
        if cnpj:
            data["issuer_cnpj"] = cnpj

    return data


def _extract_number_series(text: str, upper: str) -> tuple[str | None, str | None]:
    """Look for ``Número / Série`` near the top of the document.

    We have to be careful to skip date fragments like ``14/04/2026``, which
    superficially look like ``number/series``. Strategy:

    1. Prefer ``<digits>/<single-letter>`` (NFS-e convention: série U/A/E).
    2. Fallback to ``<digits>/<1-3 alnum>`` but exclude dates by checking
       that the candidate isn't followed by ``/\\d{4}`` (year continuation).
    """
    idx = upper.find("NUMERO / SERIE")
    if idx == -1:
        idx = upper.find("NUMERO/SERIE")
    window = text[idx : idx + 200] if idx != -1 else text[:600]

    for label in ("NUMERO DA NFS-E", "NUMERO DA NFSE"):
        idx = upper.find(label)
        if idx != -1:
            window_after_label = text[idx + len(label) : idx + len(label) + 120]
            m = re.search(r"\b(\d{1,15})\b", window_after_label)
            if m:
                return m.group(1), None

    # Pass 1: strict (letter-series). This matches ``183/U`` and ignores
    # ``14/04`` because ``04`` is digits-only.
    strict = re.search(r"\b(\d{1,9})\s*/\s*([A-Z])\b", window)
    if strict:
        return strict.group(1), strict.group(2)

    # Pass 2: loose, but filter out date-like matches.
    for match in re.finditer(r"\b(\d{1,9})\s*/\s*([A-Z0-9]{1,3})\b", window):
        after = window[match.end() : match.end() + 5]
        if re.match(r"/\d{2,4}", after):
            continue
        return match.group(1), match.group(2)

    m2 = re.search(r"\bN[º°O]\s*[:\s]\s*(\d{1,9})\b", text)
    if m2:
        return m2.group(1), None
    return None, None


def _extract_access_key(text: str, upper: str) -> str | None:
    for label in ("CHAVE DE ACESSO DA NFS-E", "CHAVE DE ACESSO DA NFSE"):
        idx = upper.find(label)
        if idx == -1:
            continue
        window_after_label = text[idx + len(label) : idx + len(label) + 200]
        m = re.search(r"\b(\d[\d\s.]{42,90}\d)\b", window_after_label)
        if not m:
            continue
        digits = common.digits_only(m.group(1))
        if 44 <= len(digits) <= 60:
            return digits
    return None


def _extract_verification_code(text: str, upper: str) -> str | None:
    idx = upper.find("CODIGO DE VERIFICACAO")
    if idx == -1:
        return None
    window = text[idx : idx + 200]
    lines = [ln.strip() for ln in window.splitlines() if ln.strip()]
    for line in lines[1:]:
        candidate = re.sub(r"[^A-Za-z0-9]", "", line)
        if 6 <= len(candidate) <= 20:
            return candidate
    return None


def _parse_party(block: str) -> dict[str, Any]:
    """Extract ``{document, name, address}`` from a prestador/tomador block."""
    out: dict[str, Any] = {}
    doc = common.first_cpf_or_cnpj(block)
    if doc:
        out["document"] = doc

    upper = common.normalize_for_match(block)
    # Find the right-most header; on multi-line OCR output, either variant
    # may come through.
    name_idx = -1
    for header in ("NOME / NOME EMPRESARIAL", "NOME/NOME EMPRESARIAL", "NOME EMPRESARIAL", "RAZAO SOCIAL"):
        pos = upper.find(header)
        if pos != -1:
            name_idx = pos
            break

    if name_idx != -1:
        name = _extract_name_after_label(block[name_idx:])
        if name:
            out["name"] = name

    address = _parse_address(block)
    if address:
        out["address"] = address
    return out


_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")


def _extract_name_after_label(trailer: str) -> str | None:
    """Read the first meaningful line after ``Nome / Nome Empresarial``.

    The PDF lays out ``Nome`` and ``E-mail`` side-by-side, so after OCR
    both end up on the same line:

        LAND SOLUCOES LTDA email@naoinformado.com

    We strip the e-mail token and then trim orphan ``email`` / ``e-mail``
    label remnants, if any.
    """
    lines = trailer.splitlines()
    for raw in lines[1:5]:
        line = raw.strip()
        if len(line) < 4:
            continue
        cleaned = _EMAIL_RE.sub("", line).strip()
        cleaned = re.sub(r"\b(?:e[-\s]?mail|email|telefone|cep|cpf|cnpj)\b[:\s]*", "", cleaned, flags=re.IGNORECASE).strip(" .:;-")
        if _is_pure_label_line(cleaned):
            continue
        if len(cleaned) < 3:
            continue
        return cleaned.split("  ")[0].strip()
    return None


_LABEL_TOKENS = {
    "NOME", "EMPRESARIAL", "CPF", "CNPJ", "NIF", "INSCRICAO", "MUNICIPAL",
    "TELEFONE", "E-MAIL", "EMAIL", "ENDERECO", "MUNICIPIO", "CEP",
    "RAZAO", "SOCIAL", "LOGRADOURO", "E", "DO", "DA", "DE",
}


def _is_pure_label_line(line: str) -> bool:
    """True when a line is only field labels (no data content)."""
    if not line:
        return True
    if re.search(r"[\d@$]", line):
        return False
    upper = common.normalize_for_match(line)
    tokens = [t for t in re.split(r"[\s/,;]+", upper) if t]
    if not tokens:
        return True
    return all(t in _LABEL_TOKENS for t in tokens)


def _parse_address(block: str) -> dict[str, Any] | None:
    upper = common.normalize_for_match(block)
    idx = upper.find("ENDERECO")
    if idx == -1:
        return None
    lines = [ln.strip() for ln in block[idx:].splitlines() if ln.strip()]
    # First meaningful line after the ENDERECO header is the full address
    target = None
    for line in lines[1:]:
        if _looks_like_header(line):
            continue
        target = line
        break
    if not target:
        return None

    address: dict[str, Any] = {"street": target, "country": "BRASIL"}
    cep_match = common.CEP_RE.search(target)
    if cep_match:
        address["zip"] = cep_match.group(1)
        target_wo_cep = target[: cep_match.start()].strip(" ,;-")
    else:
        target_wo_cep = target
    # Last UF token is typically the state; the word before it tends to be the city.
    tokens = re.split(r"[\s,;]+", target_wo_cep)
    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i] in common.STATES:
            address["state"] = tokens[i]
            if i > 0:
                city = tokens[i - 1]
                if len(city) >= 2:
                    address["city"] = city.title()
            break
    return address


def _looks_like_header(line: str) -> bool:
    upper = common.normalize_for_match(line)
    return any(h in upper for h in (
        "CPF", "CNPJ", "INSCRICAO", "TELEFONE", "E-MAIL", "EMAIL",
        "NOME / NOME", "NOME EMPRESARIAL", "RAZAO SOCIAL",
        "MUNICIPIO", "CEP", "ENDERECO",
    ))


_NATURE_INLINE_RE = re.compile(
    r"(\d{2}[.,]\d{2}\s*[-–—]\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{10,})"
)


def _extract_service_description(block: str) -> str | None:
    """Pull the best natural-language description line in the SERVICE block.

    ABRASF pages follow ``<service-code> - <description>`` almost without
    exception (e.g. ``14.01 - LUBRIFICACAO, LIMPEZA, ...``). We match that
    shape directly; if nothing fits, we fall back to the first long line
    that isn't a header or a CNAE entry.
    """
    m = _NATURE_INLINE_RE.search(block)
    if m:
        return m.group(1).strip()[:500]

    upper = common.normalize_for_match(block)
    for header in ("DESCRICAO DO SERVICO", "SERVICO PRESTADO"):
        idx = upper.find(header)
        if idx == -1:
            continue
        for raw in block[idx:].splitlines()[1:]:
            line = raw.strip()
            if len(line) < 10 or _looks_like_header(line):
                continue
            if common.CNAE_RE.search(line):
                continue
            if common.normalize_for_match(line) in {"CNAE / CBO", "CNAE/CBO", "SERVICO"}:
                continue
            return line[:500]
    return None


def _extract_values(block: str) -> dict[str, Any]:
    """Extract monetary values from the CÁLCULO DO ISSQN section.

    We anchor on the table row ``Valor total da NFSe | Deduções | Desconto
    incondicionado | Base de cálculo | Alíquota | Valor do ISSQN``. The
    last numeric value before the Alíquota is reliably the ISS.
    """
    out: dict[str, Any] = {}
    moneys = [common.to_cents(m.group(1)) for m in common.MONEY_RE.finditer(block)]
    moneys = [m for m in moneys if m is not None]

    if not moneys:
        return out

    total = max(moneys)
    out["total_fiscal_document"] = total
    out["fiscal_document_net_value"] = total
    out["total_services"] = total
    out["subtotal"] = total
    return out


def _extract_tax_hints(text: str, data: dict[str, Any]) -> None:
    upper = common.normalize_for_match(text)
    fiscal_info: dict[str, Any] = data.setdefault("fiscal_info", {})
    if "SIMPLES NACIONAL" in upper:
        fiscal_info["simples_nacional"] = True
        fiscal_info["special_tax_regime"] = "Simples Nacional"
    if "NAO RETIDO" in upper:
        fiscal_info["issqn_retention"] = "NÃO RETIDO"
    elif "RETIDO" in upper:
        fiscal_info["issqn_retention"] = "RETIDO"
    if "EXIGIVEL" in upper:
        fiscal_info["issqn_exigibility"] = "Exigível"
    if "PRESTADOR DO SERVICO" in upper and "RESPONSAVEL PELO RECOLHIMENTO" in upper:
        fiscal_info["issqn_responsible"] = "PRESTADOR DO SERVIÇO"


def _extract_retentions(text: str, data: dict[str, Any]) -> None:
    upper = common.normalize_for_match(text)
    idx = upper.find("RETENCOES")
    if idx == -1:
        return
    block = text[idx : idx + 400]
    values = [common.to_cents(m.group(1)) for m in common.MONEY_RE.finditer(block)]
    values = [v for v in values if v is not None]
    labels = ["iss_value", "irrf_value", "pis_value", "cofins_value", "inss_value", "csll_value"]
    for label, value in zip(labels, values, strict=False):
        if value and value > 0:
            data[label] = value
