"""Monetary helpers — convert human-written BRL strings into integer cents."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_CURRENCY_CLEAN = re.compile(r"[^\d,.\-]")


def to_cents(value: str | int | float | None) -> int | None:
    """Convert an arbitrary monetary representation into integer cents.

    Examples
    --------
    >>> to_cents("R$ 950,00")
    95000
    >>> to_cents("1.234,56")
    123456
    >>> to_cents("1234.56")
    123456
    >>> to_cents(95000)
    95000
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value * 100))

    cleaned = _CURRENCY_CLEAN.sub("", value).strip()
    if not cleaned:
        return None

    has_comma = "," in cleaned
    has_dot = "." in cleaned
    if has_comma and has_dot:
        # e.g. "1.234,56" — dot is thousands, comma is decimal
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif has_comma:
        cleaned = cleaned.replace(",", ".")

    try:
        return int((Decimal(cleaned) * 100).quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        return None


def normalize_money_fields(data: dict, fields: tuple[str, ...]) -> dict:
    """Mutate-and-return helper that ensures the listed keys are integer cents."""
    for field in fields:
        if field in data and data[field] is not None and not isinstance(data[field], int):
            data[field] = to_cents(data[field])
    return data


MONEY_FIELDS: tuple[str, ...] = (
    "total_services",
    "subtotal",
    "total_fiscal_document",
    "fiscal_document_net_value",
    "total_discount",
    "total_products",
    "total_freight",
    "iss_value",
    "pis_value",
    "cofins_value",
    "inss_value",
    "irrf_value",
    "csll_value",
)
