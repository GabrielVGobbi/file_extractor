"""Confidence scoring per the spec (section 8)."""

from __future__ import annotations

from typing import Any

from app.validators.fiscal import is_valid_document

FIELD_WEIGHTS: dict[str, float] = {
    "issuer_cnpj": 0.15,
    "recipient_document": 0.15,
    "fiscal_document_number": 0.10,
    "total_fiscal_document": 0.15,
    "issued_at": 0.10,
    "issuer_name": 0.10,
    "nature_operation": 0.05,
    # Remaining fields worth 0.02 each up to the cap:
    "access_key": 0.02,
    "series": 0.02,
    "model": 0.02,
    "issuer_address": 0.02,
    "recipient_name": 0.02,
    "recipient_address": 0.02,
    "subtotal": 0.02,
    "total_services": 0.02,
}

REQUIRED_FIELDS: tuple[str, ...] = (
    "issuer_cnpj",
    "fiscal_document_number",
    "total_fiscal_document",
    "issuer_name",
    "issued_at",
)


def score(extracted: dict[str, Any]) -> float:
    """Weighted sum of present (non-null) fields, capped at 1.0."""
    total = 0.0
    for field, weight in FIELD_WEIGHTS.items():
        if _has_value(extracted.get(field)):
            total += weight
    return round(min(total, 1.0), 2)


def missing_required_fields(extracted: dict[str, Any]) -> list[str]:
    """List the spec-mandated required fields that came out empty."""
    return [f for f in REQUIRED_FIELDS if not _has_value(extracted.get(f))]


def build_warnings(extracted: dict[str, Any]) -> list[str]:
    """Best-effort semantic warnings (invalid CNPJ, etc.)."""
    warnings: list[str] = []
    issuer = extracted.get("issuer_cnpj")
    if issuer and not is_valid_document(issuer):
        warnings.append("invalid_issuer_cnpj_checksum")
    recipient = extracted.get("recipient_document")
    if recipient and not is_valid_document(recipient):
        warnings.append("invalid_recipient_document_checksum")
    return warnings


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True
