from app.validators.confidence import (
    build_warnings,
    missing_required_fields,
    score,
)


def test_score_empty_dict():
    assert score({}) == 0.0


def test_score_full_coverage_near_one():
    data = {
        "document_category": "nfe",
        "issuer_cnpj": "11.222.333/0001-81",
        "recipient_document": "529.982.247-25",
        "fiscal_document_number": "1",
        "total_fiscal_document": 1000,
        "issued_at": "2026-01-01T00:00:00",
        "issuer_name": "X",
        "nature_operation": "Y",
        "access_key": "z",
        "series": "1",
        "model": "55",
        "issuer_address": {"street": "s"},
        "recipient_name": "r",
        "recipient_address": {"street": "s"},
        "subtotal": 1,
        "total_services": 1,
        "line_items": [{"description": "item"}],
        "payment": {"has_boleto": True, "due_date": "2026-01-15"},
        "parties": [{"role": "issuer", "name": "X"}],
    }
    assert score(data) >= 0.85
    assert score(data) <= 1.0


def test_score_core_fields_only():
    data = {
        "document_category": "nfe",
        "issuer_cnpj": "11.222.333/0001-81",
        "fiscal_document_number": "1",
        "total_fiscal_document": 1000,
        "issued_at": "2026-01-01T00:00:00",
        "issuer_name": "X",
    }
    assert score(data) == 0.51


def test_missing_required_fields():
    missing = missing_required_fields(
        {"document_category": "nfe", "issuer_name": "X"}
    )
    assert "issuer_cnpj" in missing
    assert "fiscal_document_number" in missing


def test_missing_required_utility_accepts_issuer_name():
    missing = missing_required_fields(
        {
            "document_category": "utility_water",
            "issuer_name": "Sabesp",
            "total_fiscal_document": 17879,
            "due_at": "2026-05-25",
        }
    )
    assert missing == []


def test_build_warnings_flags_bad_checksum():
    warnings = build_warnings({"issuer_cnpj": "11.222.333/0001-00"})
    assert "invalid_issuer_cnpj_checksum" in warnings
