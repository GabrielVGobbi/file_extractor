"""Regex-based parser for NFS-e emitida pela Prefeitura de São Paulo (SEFIN).

Layout peculiarity: field labels (CPF/CNPJ, Nome/Razão Social, Endereço…)
appear on their own lines **before** the actual values, unlike standard
ABRASF layouts where each label is immediately followed by its value.

Example issuer block::

    PRESTADOR DE SERVIÇOS
    CPF/CNPJ: Inscrição Municipal:        ← labels only
    Nome/Razão Social:                    ← label only
    Endereço:                             ← label only
    17.668.689/0001-20 4.755.140-2        ← CNPJ + IE values
    CONCIERGE BLINDADO SERVICOS …         ← company name
    R LOURENCO MARQUES 297 … CEP: 04547  ← address
    Município: São Paulo  UF: SP          ← city / state
"""

from __future__ import annotations

import re
from typing import Any

from app.extractors.heuristic import common

# ─────────────────────────── Detection ────────────────────────────────────────

_SP_SIGNALS = [
    "PREFEITURA DO MUNICIPIO DE SAO PAULO",
    "SECRETARIA MUNICIPAL DA FAZENDA",
    "NOTA FISCAL ELETRONICA DE SERVICOS",
    "NFS-E",
    "PRESTADOR DE SERVICO",
    "TOMADOR DE SERVICO",
]

# Page-2 IBS/CBS identifier (44–50 decimal digits)
_ACCESS_KEY_RE = re.compile(r"\bIdentificador[:\s]+(\d{44,50})\b")

# NFS-e number printed under "Número da Nota"  (6-9 digits)
_NOTA_NUM_RE = re.compile(r"(?:N[uú]mero da Nota|NUMERO DA NOTA)[^\n]*\n([^\n]*\n)*?[ \t]*(\d{6,9})[ \t]*\n", re.IGNORECASE)

# Series from the RPS substitution line "RPS Nº 286431 Série 1, …"
_SERIES_RE = re.compile(r"\bS[eé]rie\s+(\w+)", re.IGNORECASE)

# Verification code: e.g. "YUHC-4XUY"  (4 alnum + dash + 4 alnum)
_VERIF_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{4})\b")

# ISS value in the calc table
_ISS_RE = re.compile(
    r"Valor\s+do\s+ISS\s*\(R\$\)[^\n]*\n[^\n]*?([\d.,]+)", re.IGNORECASE
)

# Total service value  "VALOR TOTAL DO SERVIÇO = R$ 2.599,00"
_TOTAL_RE = re.compile(
    r"VALOR\s+TOTAL\s+DO\s+SERVI[CÇ]O\s*=\s*R\$\s*([\d.,]+)", re.IGNORECASE
)

# Código do Serviço block: "02800 - Licenciamento …"
_SERVICE_CODE_RE = re.compile(
    r"C[oó]digo\s+do\s+Servi[cç]o\s*\n\s*(\d{4,6})\b", re.IGNORECASE
)

# Retention table labels mapped to field names (order-sensitive)
_RETENTION_MAP = [
    (re.compile(r"INSS\s*\(R\$\)", re.IGNORECASE), "inss_value"),
    (re.compile(r"IRRF\s*\(R\$\)", re.IGNORECASE), "irrf_value"),
    (re.compile(r"CSLL\s*\(R\$\)", re.IGNORECASE), "csll_value"),
    (re.compile(r"COFINS\s*\(R\$\)", re.IGNORECASE), "cofins_value"),
    (re.compile(r"PIS[/\s]PASEP\s*\(R\$\)", re.IGNORECASE), "pis_value"),
]

# Labels that appear alone on a line in SP NFS-e blocks (pure metadata rows).
_SP_LABEL_FRAGMENTS = [
    "CPF/CNPJ", "INSCRICAO MUNICIPAL", "INSC. MUNICIPAL",
    "NOME/RAZAO SOCIAL", "NOME / RAZAO SOCIAL",
    "RAZAO SOCIAL", "ENDERECO", "MUNICIPIO", "E-MAIL",
    "INTERMEDIARIO DE SERVICO", "NIF",
]


def is_saopaulo_nfse(text: str) -> bool:
    """Return True when at least 3 SP-specific signals are present."""
    upper = common.normalize_for_match(text)
    hits = sum(1 for s in _SP_SIGNALS if s in upper)
    return hits >= 3


# ─────────────────────────── Public entry point ───────────────────────────────

def parse(text: str, *, hint_type: str | None = None) -> dict[str, Any] | None:
    """Parse a São Paulo SEFIN NFS-e text blob.

    Returns a ``FiscalDocumentData``-compatible dict or ``None`` if the text
    does not look like this specific layout.
    """
    if not text:
        return None
    if hint_type and hint_type not in {"auto", "nfse"}:
        return None
    if not is_saopaulo_nfse(text):
        return None

    text = common.normalize_whitespace(text)
    upper = common.normalize_for_match(text)

    data: dict[str, Any] = {
        "model": "99",
        "type": "saida",
        "direction": "outbound",
        "origin": "pdf_upload",
        "fiscal_info": {},
    }

    # ── NFS-e number ──────────────────────────────────────────────────────────
    number = _extract_nota_number(text, upper)
    if number:
        data["fiscal_document_number"] = number

    # ── Series (from RPS substitution line) ───────────────────────────────────
    series = _extract_series(text)
    if series:
        data["series"] = series

    # ── Issued datetime ───────────────────────────────────────────────────────
    issued_at = common.parse_datetime(text)
    if issued_at:
        data["issued_at"] = issued_at.isoformat()
    competence = common.parse_competence(text)
    if competence:
        data["competence_at"] = competence.isoformat()

    # ── Verification code ─────────────────────────────────────────────────────
    verif = _extract_verification_code(text, upper)
    if verif:
        data["fiscal_info"]["verification_code"] = verif

    # ── Access key (IBS identifier, page 2) ───────────────────────────────────
    access_key = _extract_access_key(text)
    if access_key:
        data["access_key"] = access_key

    # ── Issuer (PRESTADOR DE SERVIÇOS) ────────────────────────────────────────
    issuer_block = _section(upper, text, "PRESTADOR DE SERVICO",
                            ["TOMADOR DE SERVICO", "INTERMEDIARIO"])
    if issuer_block:
        issuer = _parse_sp_party(issuer_block)
        if issuer.get("document"):
            data["issuer_cnpj"] = issuer["document"]
        if issuer.get("ie"):
            data["issuer_ie"] = issuer["ie"]
        if issuer.get("name"):
            data["issuer_name"] = issuer["name"]
        if issuer.get("address"):
            data["issuer_address"] = issuer["address"]

    # ── Recipient (TOMADOR DE SERVIÇOS) ───────────────────────────────────────
    recipient_block = _section(upper, text, "TOMADOR DE SERVICO",
                               ["INTERMEDIARIO DE SERVICO",
                                "DISCRIMINACAO DE SERVICO",
                                "DISCRIMINACAO DOS SERVICOS"])
    if recipient_block:
        recipient = _parse_sp_party(recipient_block)
        if recipient.get("document"):
            data["recipient_document"] = recipient["document"]
        if recipient.get("name"):
            data["recipient_name"] = recipient["name"]
        if recipient.get("address"):
            data["recipient_address"] = recipient["address"]

    # ── Service code & description ────────────────────────────────────────────
    svc_code = _extract_service_code(text)
    if svc_code:
        data["fiscal_info"]["service_code"] = svc_code

    svc_desc = _extract_service_description(text, upper)
    if svc_desc:
        data["nature_operation"] = svc_desc

    # ── Monetary totals ───────────────────────────────────────────────────────
    total = _extract_total(text)
    if total:
        data["total_services"] = total
        data["subtotal"] = total
        data["total_fiscal_document"] = total
        data["fiscal_document_net_value"] = total

    iss = _extract_iss_value(text)
    if iss:
        data["iss_value"] = iss

    _extract_retentions(text, data)

    return data


# ─────────────────────────── Section slicer ───────────────────────────────────

def _section(upper: str, text: str, start: str, ends: list[str]) -> str | None:
    """Return the slice of *text* between *start* header and the first *ends* hit."""
    start_idx = upper.find(start)
    if start_idx == -1:
        return None
    end_idx = len(text)
    for end in ends:
        idx = upper.find(end, start_idx + 1)
        if idx != -1 and idx < end_idx:
            end_idx = idx
    return text[start_idx:end_idx]


# ─────────────────────────── Number / series ──────────────────────────────────

def _extract_nota_number(text: str, upper: str) -> str | None:
    """Extract the NFS-e number (e.g. '00295383') from 'Número da Nota' header.

    The SP layout places the actual number on a line by itself, a few lines
    after the 'Número da Nota' label (which may be on its own line too).
    We look for the first 6-9 digit standalone token in the window.
    """
    idx = upper.find("NUMERO DA NOTA")
    window = text[idx: idx + 300] if idx != -1 else text[:400]
    for line in window.splitlines():
        stripped = line.strip()
        if re.match(r"^\d{6,9}$", stripped):
            return stripped
    # Fallback: "Número da Nota\n...\n<digits>" scattered layout
    m = re.search(r"N[uú]mero\s+da\s+Nota[^\n]*\n(?:[^\n]*\n){0,3}\s*(\d{6,9})\s*\n",
                  text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _extract_series(text: str) -> str | None:
    m = _SERIES_RE.search(text)
    return m.group(1) if m else None


# ─────────────────────────── Verification code ────────────────────────────────

def _extract_verification_code(text: str, upper: str) -> str | None:
    idx = upper.find("CODIGO DE VERIFICACAO")
    window = text[idx: idx + 200] if idx != -1 else text[:600]
    m = _VERIF_RE.search(window)
    return m.group(1) if m else None


# ─────────────────────────── Access key ───────────────────────────────────────

def _extract_access_key(text: str) -> str | None:
    m = _ACCESS_KEY_RE.search(text)
    if m:
        return m.group(1)
    # Also accept a bare 44-digit string (without the "Identificador:" label)
    m2 = re.search(r"\b(\d{44})\b", text)
    return m2.group(1) if m2 else None


# ─────────────────────────── Party parser ─────────────────────────────────────

# Lines that carry only field labels (no actual data).  The SP NFS-e places
# every label on its own line: "CPF/CNPJ:", "Nome/Razão Social:", …
_PURE_LABEL_RE = re.compile(
    r"^(?:CPF/CNPJ|CNPJ|CPF|INSCRI[CÇ][AÃ]O\s+MUNICIPAL|"
    r"NOME/RAZ[AÃ]O\s+SOCIAL|NOME\s*/\s*RAZ[AÃ]O\s+SOCIAL|RAZ[AÃ]O\s+SOCIAL|"
    r"ENDERE[CÇ]O|MUNIC[IÍ]PIO|UF|E-MAIL|EMAIL|NIF)\s*:?\s*$",
    re.IGNORECASE,
)

# Inscrição Municipal pattern (e.g. "4.755.140-2")
_IE_RE = re.compile(r"^(\d[\d.\-\/]+)$")

# Placeholder lines
_PLACEHOLDER_RE = re.compile(r"^[-–—]+$")

# Bare 2-letter state code on its own line
_BARE_STATE_RE = re.compile(r"^([A-Z]{2})$")


def _parse_sp_party(block: str) -> dict[str, Any]:
    """Extract document, IE, name and address from a SP NFS-e party block.

    The SP SEFIN layout puts ALL labels on individual lines first, then the
    corresponding values follow below in the same order.  We classify each
    non-label line by its content (CNPJ regex, CEP regex, state code, etc.)
    rather than relying on the label immediately preceding the value.
    """
    out: dict[str, Any] = {}
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]

    # Accumulate city/state fragments: list of ("city"|"state", value)
    city_fragments: list[tuple[str, str]] = []

    for line in lines[1:]:  # skip section header
        upper = common.normalize_for_match(line)

        # ── Skip pure label lines ─────────────────────────────────────────
        if _PURE_LABEL_RE.match(upper):
            continue
        if _PLACEHOLDER_RE.match(line):
            continue

        # ── CNPJ ─────────────────────────────────────────────────────────
        cnpj_m = common.CNPJ_RE.match(line.strip())
        if cnpj_m and len(common.digits_only(cnpj_m.group(1))) == 14:
            if not out.get("document"):
                digits = common.digits_only(cnpj_m.group(1))
                out["document"] = (
                    f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}"
                    f"/{digits[8:12]}-{digits[12:]}"
                )
            continue

        # ── Address (contains CEP) ────────────────────────────────────────
        if common.CEP_RE.search(line) and not out.get("address"):
            out["address"] = _build_address(line)
            continue

        # ── City line with "Município:" label (upper used to handle encoding) ─
        if re.match(r"^MUNICIPIO\s*:\s*.+", upper):
            # Extract city from normalized form — avoids broken encoding
            city_m = re.match(r"MUNICIPIO\s*:\s*(.+)", upper)
            if city_m:
                city_fragments.append(("city", city_m.group(1).strip().title()))
            continue

        # ── UF line with explicit "UF: XX" label ─────────────────────────
        if re.match(r"^UF\s*:\s*[A-Z]{2}", upper):
            uf_m = re.match(r"UF\s*:\s*([A-Z]{2})", upper)
            if uf_m and uf_m.group(1) in common.STATES:
                city_fragments.append(("state", uf_m.group(1)))
            continue

        # ── Bare 2-letter state code on its own line ─────────────────────
        if _BARE_STATE_RE.match(upper.strip()) and upper.strip() in common.STATES:
            city_fragments.append(("state", upper.strip()))
            continue

        # ── Email — skip ──────────────────────────────────────────────────
        if re.search(r"@", line):
            continue

        # ── Inscrição Municipal — lone IE on its own line ─────────────────
        ie_m = _IE_RE.match(line.strip())
        if ie_m and not out.get("ie"):
            ie_raw = ie_m.group(1)
            digs = common.digits_only(ie_raw)
            if 4 <= len(digs) <= 12 and len(digs) != 14:
                out["ie"] = ie_raw
                continue

        # ── Bare city name (after address is already found) ───────────────
        # e.g. "Santana de Parnaíba" with no label prefix
        if out.get("address") and not re.search(r"\d", line) and len(line) > 3:
            city_fragments.append(("city", common.normalize_for_match(line).strip().title()))
            continue

        # ── Company name — everything else ───────────────────────────────
        if not out.get("name") and len(line) > 5:
            out["name"] = line.split("  ")[0].strip()

    # Merge city/state fragments into address
    if city_fragments:
        addr = out.setdefault("address", {"country": "BRASIL"})
        for kind, value in city_fragments:
            if kind == "city" and not addr.get("city"):
                addr["city"] = value
            elif kind == "state" and not addr.get("state"):
                addr["state"] = value

    return out


def _build_address(line: str) -> dict[str, Any]:
    """Parse a single address line into a structured dict."""
    addr: dict[str, Any] = {"country": "BRASIL"}

    cep_m = common.CEP_RE.search(line)
    if cep_m:
        addr["zip"] = cep_m.group(1).replace(" ", "-")
        street_part = line[: cep_m.start()].strip(" ,-")
    else:
        street_part = line

    # Remove "CEP:" prefix if present
    street_part = re.sub(r"\bCEP\s*:?\s*", "", street_part, flags=re.IGNORECASE).strip(" ,-")

    # Split on " - " to get neighborhood
    segments = [s.strip() for s in re.split(r"\s+-\s+", street_part)]
    if segments:
        # First segment: "R LOURENCO MARQUES 297, ANEXO 303 E 315"
        # or "Rua ALBERTO FREDIANI 90, FUNDOS"
        first = segments[0]
        # Try to extract number from "STREET_NAME NNN" or "STREET_NAME NNN, COMPLEMENT"
        num_m = re.search(r"\b(\d+)\b(.*)$", first)
        if num_m:
            addr["street"] = first[: num_m.start()].strip(" ,")
            addr["number"] = num_m.group(1)
            complement = num_m.group(2).strip(" ,")
            if complement:
                addr["complement"] = complement
        else:
            addr["street"] = first

    if len(segments) == 2:
        addr["neighborhood"] = segments[1]
    elif len(segments) >= 3:
        addr["neighborhood"] = segments[-1]
        if not addr.get("complement"):
            addr["complement"] = " - ".join(segments[1:-1])

    return addr


# ─────────────────────────── Service code / description ───────────────────────

def _extract_service_code(text: str) -> str | None:
    """Extract the 'Código do Serviço' (e.g. '02800') from its section."""
    m = _SERVICE_CODE_RE.search(text)
    if m:
        return m.group(1)
    # Inline format: "02800 - Licenciamento …" anywhere near a 'Código' label
    upper = common.normalize_for_match(text)
    idx = upper.find("CODIGO DO SERVICO")
    if idx == -1:
        return None
    window = text[idx: idx + 300]
    code_m = re.search(r"\b(\d{4,6})\s*[-–]", window)
    return code_m.group(1) if code_m else None


def _extract_service_description(text: str, upper: str) -> str | None:
    """Pull the service description from the 'Código do Serviço' line."""
    idx = upper.find("CODIGO DO SERVICO")
    if idx == -1:
        return None
    window = text[idx: idx + 400]
    # "02800 - Licenciamento ou cessão …"
    m = re.search(r"\d{4,6}\s*[-–]\s*(.+)", window)
    if m:
        return m.group(1).strip()[:500]
    return None


# ─────────────────────────── Monetary values ──────────────────────────────────

def _extract_total(text: str) -> int | None:
    m = _TOTAL_RE.search(text)
    if not m:
        return None
    return common.to_cents(m.group(1))


def _extract_iss_value(text: str) -> int | None:
    """Extract Valor do ISS from the ISS calc section.

    In the SP NFS-e each column header and value occupy their own line::

        Valor Total das Deduções (R$)   ← header 0
        Base de Cálculo (R$)            ← header 1
        Alíquota (%)                    ← header 2
        Valor do ISS (R$)               ← header 3
        Crédito Programa da NFP (R$)    ← header 4
        0,00                            ← value 0  (deductions)
        2.599,00                        ← value 1  (base)
        2,90%                           ← value 2  (aliquota — skip)
        75,37                           ← value 3  (ISS)  ← we want this
        0,00                            ← value 4  (credit)

    Strategy: find the ISS header, count its position among sibling headers,
    then grab the same-indexed value from the following value lines.
    """
    upper = common.normalize_for_match(text)

    # Locate the block that starts with the first ISS-section header
    iss_section_headers = [
        "VALOR TOTAL DAS DEDUCOES",
        "BASE DE CALCULO",
        "ALIQUOTA",
        "VALOR DO ISS",
        "CREDITO PROGRAMA",
    ]
    # Find the start of the ISS header block
    block_start = -1
    for hdr in iss_section_headers:
        idx = upper.find(hdr)
        if idx != -1 and (block_start == -1 or idx < block_start):
            block_start = idx

    if block_start == -1:
        return None

    window = text[block_start: block_start + 600]
    upper_win = common.normalize_for_match(window)
    lines = [ln.strip() for ln in window.splitlines() if ln.strip()]

    # Split into header lines vs value lines
    header_lines: list[str] = []
    value_lines: list[str] = []
    in_values = False
    for line in lines:
        ul = common.normalize_for_match(line)
        is_header = any(h in ul for h in iss_section_headers)
        if is_header and not in_values:
            header_lines.append(line)
        else:
            # Once we hit a non-header line, we're in the values section
            in_values = True
            value_lines.append(line)

    # Find position of "Valor do ISS" in header_lines
    iss_pos = -1
    for i, hl in enumerate(header_lines):
        if "VALOR DO ISS" in common.normalize_for_match(hl):
            iss_pos = i
            break

    if iss_pos == -1:
        return None

    # Map value lines to actual cent values (skip percentage lines like "2,90%")
    cent_values: list[int] = []
    for vl in value_lines:
        if re.search(r"\d+[.,]\d+%", vl):
            cent_values.append(-1)  # placeholder for aliquota
            continue
        m = common.MONEY_RE.search(vl)
        if m:
            v = common.to_cents(m.group(1))
            cent_values.append(v if v is not None else 0)
        else:
            break  # stop at first non-monetary line

    if iss_pos < len(cent_values):
        v = cent_values[iss_pos]
        return v if v and v > 0 else None
    return None


def _extract_retentions(text: str, data: dict[str, Any]) -> None:
    """Extract INSS/IRRF/CSLL/COFINS/PIS from the retentions section.

    In the SP NFS-e the headers are each on their own line, followed by the
    value lines in the same order.
    """
    upper = common.normalize_for_match(text)
    idx = upper.find("INSS (R$)")
    if idx == -1:
        return

    retention_headers = ["INSS (R$)", "IRRF (R$)", "CSLL (R$)", "COFINS (R$)", "PIS/PASEP (R$)", "IPI (R$)"]
    field_names = ["inss_value", "irrf_value", "csll_value", "cofins_value", "pis_value"]

    window = text[idx: idx + 400]
    lines = [ln.strip() for ln in window.splitlines() if ln.strip()]

    header_lines: list[str] = []
    value_lines: list[str] = []
    in_values = False
    for line in lines:
        ul = common.normalize_for_match(line)
        is_header = any(h in ul for h in retention_headers)
        if is_header and not in_values:
            header_lines.append(line)
        else:
            in_values = True
            m = common.MONEY_RE.search(line)
            if m:
                value_lines.append(line)
            else:
                break

    for field, vl in zip(field_names, value_lines, strict=False):
        m = common.MONEY_RE.search(vl)
        if m:
            v = common.to_cents(m.group(1))
            if v and v > 0:
                data[field] = v
