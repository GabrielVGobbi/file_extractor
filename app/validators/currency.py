"""Monetary helpers — convert human-written BRL strings into integer cents."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_CURRENCY_CLEAN = re.compile(r"[^\d,.\-]")

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
    "icms_value",
    "icms_st_value",
    "ipi_value",
)

NESTED_MONEY_PATHS: tuple[tuple[str, str], ...] = (
    ("line_items", "unit_price"),
    ("line_items", "total_price"),
    ("line_items", "discount"),
    ("line_items", "icms_base"),
    ("line_items", "icms_value"),
    ("line_items", "ipi_value"),
    ("withholdings", "base"),
    ("withholdings", "amount"),
    ("taxes", "base"),
    ("taxes", "amount"),
    ("payment", "total_amount"),
    ("fiscal_info", "approximate_taxes"),
    ("consumption", "unit_price"),  # ignored if missing
)


def to_cents(value: str | int | float | None) -> int | None:
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
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif has_comma:
        cleaned = cleaned.replace(",", ".")

    try:
        return int((Decimal(cleaned) * 100).quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        return None


def normalize_money_fields(data: dict, fields: tuple[str, ...] | None = None) -> dict:
    """Ensure top-level and nested monetary keys are integer cents."""
    fields = fields or MONEY_FIELDS
    for field in fields:
        if field in data and data[field] is not None and not isinstance(data[field], int):
            data[field] = to_cents(data[field])

    for container_key, money_key in NESTED_MONEY_PATHS:
        container = data.get(container_key)
        if container_key == "payment" and isinstance(container, dict):
            if money_key in container and container[money_key] is not None:
                if not isinstance(container[money_key], int):
                    container[money_key] = to_cents(container[money_key])
            continue
        if container_key == "fiscal_info" and isinstance(container, dict):
            if money_key in container and container[money_key] is not None:
                if not isinstance(container[money_key], int):
                    container[money_key] = to_cents(container[money_key])
            continue
        if not isinstance(container, list):
            continue
        for item in container:
            if isinstance(item, dict) and money_key in item and item[money_key] is not None:
                if not isinstance(item[money_key], int):
                    item[money_key] = to_cents(item[money_key])

    return data
