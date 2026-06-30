"""Category-aware confidence scoring and required-field validation."""

from __future__ import annotations

from typing import Any

from app.schemas.document import DocumentCategory
from app.validators.fiscal import is_valid_document

FIELD_WEIGHTS: dict[str, float] = {
    "document_category": 0.05,
    "issuer_cnpj": 0.10,
    "recipient_document": 0.08,
    "fiscal_document_number": 0.08,
    "total_fiscal_document": 0.12,
    "issued_at": 0.08,
    "due_at": 0.05,
    "issuer_name": 0.08,
    "nature_operation": 0.03,
    "access_key": 0.03,
    "series": 0.02,
    "model": 0.02,
    "issuer_address": 0.02,
    "recipient_name": 0.05,
    "recipient_address": 0.02,
    "subtotal": 0.02,
    "total_services": 0.02,
    "line_items": 0.05,
    "payment": 0.05,
    "parties": 0.03,
}

REQUIRED_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "nfe": (
        "issuer_cnpj",
        "fiscal_document_number",
        "total_fiscal_document",
        "issued_at",
    ),
    "nfse": (
        "issuer_cnpj",
        "recipient_document",
        "fiscal_document_number",
        "total_fiscal_document",
        "issued_at",
    ),
    "nfce": (
        "issuer_cnpj",
        "fiscal_document_number",
        "total_fiscal_document",
        "issued_at",
    ),
    "cte": (
        "issuer_cnpj",
        "fiscal_document_number",
        "total_fiscal_document",
        "issued_at",
    ),
    "nf3e": (
        "issuer_name",
        "total_fiscal_document",
    ),
    "utility_water": (
        "issuer_name",
        "total_fiscal_document",
    ),
    "utility_electricity": (
        "issuer_name",
        "total_fiscal_document",
    ),
    "utility_gas": (
        "issuer_name",
        "total_fiscal_document",
    ),
    "utility_telecom": (
        "issuer_name",
        "total_fiscal_document",
    ),
    "rental_invoice": (
        "issuer_cnpj",
        "fiscal_document_number",
        "total_fiscal_document",
        "issued_at",
    ),
    "boleto": (
        "total_fiscal_document",
    ),
    "invoice": (
        "issuer_name",
        "total_fiscal_document",
    ),
    "receipt": (
        "issuer_name",
        "total_fiscal_document",
    ),
    "other": (
        "total_fiscal_document",
    ),
}

# Legacy flat required set — used when category is unknown.
REQUIRED_FIELDS: tuple[str, ...] = REQUIRED_BY_CATEGORY["nfe"]


def score(extracted: dict[str, Any]) -> float:
    total = 0.0
    for field, weight in FIELD_WEIGHTS.items():
        if _has_value(extracted.get(field)):
            total += weight
    return round(min(total, 1.0), 2)


def missing_required_fields(extracted: dict[str, Any]) -> list[str]:
    category = extracted.get("document_category") or "other"
    required = REQUIRED_BY_CATEGORY.get(category, REQUIRED_BY_CATEGORY["other"])

    missing: list[str] = []
    for field in required:
        if not _has_value(extracted.get(field)):
            if field == "issuer_name" and _has_value(extracted.get("issuer_cnpj")):
                continue
            if (
                field == "issuer_cnpj"
                and _has_value(extracted.get("issuer_name"))
                and category.startswith("utility_")
            ):
                continue
            if field == "issued_at" and _has_payment_due(extracted):
                continue
            missing.append(field)

    # Utility/telecom: require due date via payment or due_at
    if category.startswith("utility_") or category == "boleto":
        if not _has_payment_due(extracted) and not _has_value(extracted.get("due_at")):
            if "due_at" not in missing:
                missing.append("due_at")

    return missing


def build_warnings(extracted: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    issuer = extracted.get("issuer_cnpj")
    if issuer and not is_valid_document(issuer):
        warnings.append("invalid_issuer_cnpj_checksum")
    recipient = extracted.get("recipient_document")
    if recipient and not is_valid_document(recipient):
        warnings.append("invalid_recipient_document_checksum")

    category = extracted.get("document_category")
    if category == "other":
        warnings.append("unclassified_document_category")

    payment = extracted.get("payment")
    if isinstance(payment, dict):
        if payment.get("has_boleto") and not payment.get("digitable_line") and not payment.get("barcode"):
            warnings.append("boleto_flagged_but_no_barcode")
    return warnings


def _has_payment_due(extracted: dict[str, Any]) -> bool:
    if _has_value(extracted.get("due_at")):
        return True
    payment = extracted.get("payment")
    if isinstance(payment, dict) and _has_value(payment.get("due_date")):
        return True
    return False


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True
