"""Heuristic document classification — advisory only.

Used by ``scripts/analyze_examples.py`` and logged as metadata for
comparison. **Not** fed to the LLM and **not** used to override
``document_category`` — classification is the LLM's job on the PDF path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.document import DocumentCategory

# Ordered from most specific to least specific.
_RULES: list[tuple[DocumentCategory, str, re.Pattern[str]]] = [
    (
        "nf3e",
        "enel",
        re.compile(
            r"NF3e|Eletropaulo|ENEL|conta de energia|"
            r"NOTA FISCAL N[º°°o]\s*\d+.*S[ée]rie\s*0?01",
            re.I,
        ),
    ),
    (
        "rental_invoice",
        "nota_debito",
        re.compile(
            r"NOTA DE D[EÉ]BITO|NOTA DE DEBITO",
            re.I,
        ),
    ),
    (
        "rental_invoice",
        "rental",
        re.compile(
            r"LOCA[ÇC][ÃA]O DE EQUIPAMENTOS|FATURA/DUPLICATA|"
            r"loca[çc][ãa]o de equip|Loca[çc][ãa]o de Bens",
            re.I,
        ),
    ),
    (
        "nfse",
        "nfse_sp",
        re.compile(
            r"NOTA FISCAL ELETR[ÔO]NICA DE SERVI[ÇC]OS|"
            r"(?<![A-Z])NFS-?e(?![A-Z])",
            re.I,
        ),
    ),
    (
        "nfe",
        "danfe",
        re.compile(
            r"DANFE|DOCUMENTO AUXILIAR DA NOTA FISCAL|CHAVE DE ACESSO|"
            r"NOTA FISCAL ELETR[ÔO]NICA(?! DE SERVI)",
            re.I,
        ),
    ),
    (
        "utility_water",
        "sabesp",
        re.compile(
            r"Sabesp|Fatura de Servi[çc]os de [ÁA]gua|Cia de Saneamento",
            re.I,
        ),
    ),
    (
        "utility_telecom",
        "vivo",
        re.compile(
            r"Telefonica Brasil|vivo\.com\.br|VIVO EMPRESAS|SMART EMPRESAS",
            re.I,
        ),
    ),
    (
        "utility_telecom",
        "telecom",
        re.compile(
            r"Claro|TIM S\.A\.|Oi S\.A\.|NET Servi[çc]os|telecomunica",
            re.I,
        ),
    ),
    (
        "utility_electricity",
        "electricity",
        re.compile(
            r"conta de energia|kWh|CONSUMO.*kWh|CEMIG|CPFL|Light|Copel|"
            r"Energisa|Neoenergia",
            re.I,
        ),
    ),
    (
        "utility_gas",
        "gas",
        re.compile(r"Comg[áa]s|Gas Natural|G[áa]s\b", re.I),
    ),
    (
        "boleto",
        "boleto",
        re.compile(
            r"Recibo do Pagador|Autentica[çc][ãa]o Mec[âa]nica|"
            r"34191\.|Linha Digit[áa]vel|FEBRABAN",
            re.I,
        ),
    ),
    (
        "nfce",
        "nfce",
        re.compile(r"NFC-?e|NOTA FISCAL DE CONSUMIDOR", re.I),
    ),
    (
        "cte",
        "cte",
        re.compile(r"CT-?e|CONHECIMENTO DE TRANSPORTE", re.I),
    ),
]


@dataclass(frozen=True)
class ClassificationResult:
    category: DocumentCategory
    subtype: str | None
    confidence: float


def suggest_category(text: str, *, hint_type: str | None = None) -> ClassificationResult:
    """Best-effort regex guess for logging/debug — not authoritative."""
    text = (text or "").strip()
    if not text:
        return ClassificationResult("other", None, 0.0)

    if hint_type and hint_type not in ("auto", "other"):
        mapped = _map_hint(hint_type)
        if mapped:
            return ClassificationResult(mapped, hint_type, 0.85)

    for category, subtype, pattern in _RULES:
        if pattern.search(text):
            return ClassificationResult(category, subtype, 0.90)

    if re.search(r"CNPJ|CPF|NOTA FISCAL|FATURA|BOLETO|VENCIMENTO", text, re.I):
        return ClassificationResult("invoice", None, 0.40)

    return ClassificationResult("other", None, 0.0)


# Backward-compatible alias used by analyze script and tests.
classify_document = suggest_category


def _map_hint(hint: str) -> DocumentCategory | None:
    mapping: dict[str, DocumentCategory] = {
        "nfe": "nfe",
        "nfse": "nfse",
        "nfce": "nfce",
        "cte": "cte",
        "nf3e": "nf3e",
        "utility_water": "utility_water",
        "utility_electricity": "utility_electricity",
        "utility_gas": "utility_gas",
        "utility_telecom": "utility_telecom",
        "rental_invoice": "rental_invoice",
        "boleto": "boleto",
        "invoice": "invoice",
        "receipt": "receipt",
    }
    return mapping.get(hint.lower())
