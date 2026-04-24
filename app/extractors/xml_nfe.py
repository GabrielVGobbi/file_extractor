"""Deterministic parser for NF-e and NFS-e (ABRASF) XML documents.

This path never goes through the LLM — confidence is always ``1.0`` and
the cost is zero. Supported schemas:

- NF-e (``http://www.portalfiscal.inf.br/nfe``), both wrapped as ``nfeProc``
  and raw ``NFe``.
- NFS-e ABRASF (common prefectures — tag namespace with ``CompNfse`` or
  ``ConsultarNfseResposta`` wrappers).

The output is a dict whose keys match ``FiscalDocumentData`` so the
service layer can feed it straight into the Pydantic model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from lxml import etree

_NFE_NS = "http://www.portalfiscal.inf.br/nfe"


def _localname(elem: etree._Element) -> str:
    tag = elem.tag
    if isinstance(tag, str) and "}" in tag:
        return tag.split("}", 1)[1]
    return tag  # type: ignore[return-value]


def _find(root: etree._Element, path: str) -> etree._Element | None:
    """Namespace-agnostic descendant lookup by local-name path.

    ``path`` is a ``/``-separated list of local tag names (e.g. ``emit/enderEmit``).
    """
    current: list[etree._Element] = [root]
    for part in path.split("/"):
        nxt: list[etree._Element] = []
        for node in current:
            nxt.extend(el for el in node.iter() if _localname(el) == part)
        if not nxt:
            return None
        current = [nxt[0]]
    return current[0]


def _text(root: etree._Element, path: str) -> str | None:
    node = _find(root, path)
    if node is None:
        return None
    text = (node.text or "").strip()
    return text or None


def _money_to_cents(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value.replace(",", ".")) * 100))
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:25] if len(value) > 25 else value, fmt).isoformat()
        except ValueError:
            continue
    return value


def detect_schema(root: etree._Element) -> str:
    """Return ``'nfe'`` | ``'nfse'`` | ``'unknown'`` based on the XML root."""
    name = _localname(root)
    if name in {"nfeProc", "NFe"}:
        return "nfe"
    if name in {"CompNfse", "Nfse", "ConsultarNfseResposta", "ConsultarNfseRpsResposta"}:
        return "nfse"
    # Fallback: scan descendants
    for el in root.iter():
        ln = _localname(el)
        if ln in {"infNFe"}:
            return "nfe"
        if ln in {"InfNfse", "InfDeclaracaoPrestacaoServico"}:
            return "nfse"
    return "unknown"


def parse_xml(data: bytes) -> dict[str, Any]:
    """Parse a NF-e or NFS-e XML payload into a ``fiscal_documents`` dict."""
    root = etree.fromstring(data)
    schema = detect_schema(root)
    if schema == "nfe":
        return _parse_nfe(root)
    if schema == "nfse":
        return _parse_nfse(root)
    raise ValueError("Unsupported XML schema: expected NF-e or NFS-e ABRASF")


# ---------------------------------------------------------------------------
# NF-e (modelo 55 / 65)
# ---------------------------------------------------------------------------

def _address_from_end(node: etree._Element | None) -> dict[str, Any] | None:
    if node is None:
        return None
    return {
        "street": _text(node, "xLgr"),
        "number": _text(node, "nro"),
        "complement": _text(node, "xCpl"),
        "neighborhood": _text(node, "xBairro"),
        "city": _text(node, "xMun"),
        "state": _text(node, "UF"),
        "country": _text(node, "xPais") or "BRASIL",
        "zip": _text(node, "CEP"),
    }


def _parse_nfe(root: etree._Element) -> dict[str, Any]:
    inf = _find(root, "infNFe")
    if inf is None:
        raise ValueError("NF-e XML missing <infNFe> element")

    ide = _find(inf, "ide")
    emit = _find(inf, "emit")
    dest = _find(inf, "dest")
    total = _find(inf, "total/ICMSTot")

    access_key = inf.attrib.get("Id", "").replace("NFe", "") if inf is not None else None
    model = _text(ide, "mod") if ide is not None else None
    tp_nf = _text(ide, "tpNF") if ide is not None else None  # "0" entrada, "1" saida

    issuer_address = _address_from_end(_find(emit, "enderEmit")) if emit is not None else None
    recipient_address = _address_from_end(_find(dest, "enderDest")) if dest is not None else None

    return {
        "access_key": access_key,
        "fiscal_document_number": _text(ide, "nNF") if ide is not None else None,
        "series": _text(ide, "serie") if ide is not None else None,
        "model": model,
        "nature_operation": _text(ide, "natOp") if ide is not None else None,
        "type": "saida" if tp_nf == "1" else "entrada",
        "direction": "outbound" if tp_nf == "1" else "inbound",
        "origin": "xml_upload",
        "status": "authorized",
        "issued_at": _parse_datetime(
            _text(ide, "dhEmi") or _text(ide, "dEmi") if ide is not None else None
        ),
        "issuer_cnpj": _text(emit, "CNPJ") or _text(emit, "CPF") if emit is not None else None,
        "issuer_name": _text(emit, "xNome") if emit is not None else None,
        "issuer_fancy_name": _text(emit, "xFant") if emit is not None else None,
        "issuer_ie": _text(emit, "IE") if emit is not None else None,
        "issuer_crt": _text(emit, "CRT") if emit is not None else None,
        "issuer_address": issuer_address,
        "recipient_document": (
            _text(dest, "CNPJ") or _text(dest, "CPF") if dest is not None else None
        ),
        "recipient_name": _text(dest, "xNome") if dest is not None else None,
        "recipient_ie": _text(dest, "IE") if dest is not None else None,
        "recipient_address": recipient_address,
        "total_products": _money_to_cents(_text(total, "vProd") if total is not None else None),
        "total_freight": _money_to_cents(_text(total, "vFrete") if total is not None else None),
        "total_discount": _money_to_cents(_text(total, "vDesc") if total is not None else None),
        "subtotal": _money_to_cents(_text(total, "vProd") if total is not None else None),
        "total_fiscal_document": _money_to_cents(
            _text(total, "vNF") if total is not None else None
        ),
        "fiscal_document_net_value": _money_to_cents(
            _text(total, "vNF") if total is not None else None
        ),
        "pis_value": _money_to_cents(_text(total, "vPIS") if total is not None else None),
        "cofins_value": _money_to_cents(_text(total, "vCOFINS") if total is not None else None),
        "iss_value": _money_to_cents(_text(total, "vISSQN") if total is not None else None),
    }


# ---------------------------------------------------------------------------
# NFS-e ABRASF
# ---------------------------------------------------------------------------

def _nfse_address(node: etree._Element | None) -> dict[str, Any] | None:
    if node is None:
        return None
    return {
        "street": _text(node, "Endereco"),
        "number": _text(node, "Numero"),
        "complement": _text(node, "Complemento"),
        "neighborhood": _text(node, "Bairro"),
        "city": _text(node, "xMun") or _text(node, "CodigoMunicipio"),
        "state": _text(node, "Uf"),
        "country": _text(node, "xPais") or "BRASIL",
        "zip": _text(node, "Cep"),
    }


def _parse_nfse(root: etree._Element) -> dict[str, Any]:
    info = _find(root, "InfNfse")
    if info is None:
        info = _find(root, "Nfse")
    if info is None:
        raise ValueError("NFS-e XML missing <InfNfse>")

    prestador = _find(info, "PrestadorServico")
    if prestador is None:
        prestador = _find(info, "IdentificacaoPrestador")
    tomador = _find(info, "TomadorServico")
    servico = _find(info, "Servico")
    valores = _find(servico, "Valores") if servico is not None else None

    valor_servicos = _text(valores, "ValorServicos") if valores is not None else None
    valor_liquido = _text(valores, "ValorLiquidoNfse") if valores is not None else None
    valor_iss = _text(valores, "ValorIss") if valores is not None else None
    valor_pis = _text(valores, "ValorPis") if valores is not None else None
    valor_cofins = _text(valores, "ValorCofins") if valores is not None else None
    valor_inss = _text(valores, "ValorInss") if valores is not None else None
    valor_ir = _text(valores, "ValorIr") if valores is not None else None
    valor_csll = _text(valores, "ValorCsll") if valores is not None else None

    endereco_prestador = None
    nome_prestador = None
    cnpj_prestador = None
    ie_prestador = None
    if prestador is not None:
        endereco_prestador = _nfse_address(_find(prestador, "Endereco"))
        nome_prestador = _text(prestador, "RazaoSocial")
        cnpj_prestador = _text(prestador, "Cnpj") or _text(prestador, "Cpf")
        ie_prestador = _text(prestador, "InscricaoEstadual") or _text(
            prestador, "InscricaoMunicipal"
        )

    endereco_tomador = None
    nome_tomador = None
    doc_tomador = None
    ie_tomador = None
    if tomador is not None:
        endereco_tomador = _nfse_address(_find(tomador, "Endereco"))
        nome_tomador = _text(tomador, "RazaoSocial")
        doc_tomador = _text(tomador, "Cnpj") or _text(tomador, "Cpf")
        ie_tomador = _text(tomador, "InscricaoEstadual") or _text(
            tomador, "InscricaoMunicipal"
        )

    fiscal_info = {
        "cnae": _text(servico, "CodigoCnae") if servico is not None else None,
        "service_code": _text(servico, "ItemListaServico") if servico is not None else None,
        "issqn_municipality": _text(servico, "CodigoMunicipio") if servico is not None else None,
        "verification_code": _text(info, "CodigoVerificacao"),
    }

    return {
        "access_key": _text(info, "CodigoVerificacao"),
        "fiscal_document_number": _text(info, "Numero"),
        "series": "U",
        "model": "99",
        "nature_operation": _text(servico, "Discriminacao") if servico is not None else None,
        "type": "saida",
        "direction": "outbound",
        "origin": "xml_upload",
        "status": "authorized",
        "issued_at": _parse_datetime(_text(info, "DataEmissao")),
        "competence_at": _parse_datetime(_text(info, "Competencia")),
        "issuer_cnpj": cnpj_prestador,
        "issuer_name": nome_prestador,
        "issuer_ie": ie_prestador,
        "issuer_address": endereco_prestador,
        "recipient_document": doc_tomador,
        "recipient_name": nome_tomador,
        "recipient_ie": ie_tomador,
        "recipient_address": endereco_tomador,
        "total_services": _money_to_cents(valor_servicos),
        "subtotal": _money_to_cents(valor_servicos),
        "total_fiscal_document": _money_to_cents(valor_servicos),
        "fiscal_document_net_value": _money_to_cents(valor_liquido or valor_servicos),
        "iss_value": _money_to_cents(valor_iss),
        "pis_value": _money_to_cents(valor_pis),
        "cofins_value": _money_to_cents(valor_cofins),
        "inss_value": _money_to_cents(valor_inss),
        "irrf_value": _money_to_cents(valor_ir),
        "csll_value": _money_to_cents(valor_csll),
        "additional_info": _text(servico, "Discriminacao") if servico is not None else None,
        "fiscal_info": {k: v for k, v in fiscal_info.items() if v is not None},
    }
