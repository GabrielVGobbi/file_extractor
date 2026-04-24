from app.validators.confidence import (
    build_warnings,
    missing_required_fields,
    score,
)


def test_score_empty_dict():
    assert score({}) == 0.0


def test_score_full_coverage_near_one():
    data = {
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
    }
    # Sum of all weighted fields lands at 0.96 — the cap at 1.0 protects against
    # accidental overflow if the weights table is ever extended.
    assert score(data) >= 0.9
    assert score(data) <= 1.0


def test_score_core_fields_only():
    data = {
        "issuer_cnpj": "11.222.333/0001-81",
        "fiscal_document_number": "1",
        "total_fiscal_document": 1000,
        "issued_at": "2026-01-01T00:00:00",
        "issuer_name": "X",
    }
    # 0.15 + 0.10 + 0.15 + 0.10 + 0.10 = 0.60
    assert score(data) == 0.60


def test_missing_required_fields():
    missing = missing_required_fields({"issuer_name": "X"})
    assert "issuer_cnpj" in missing
    assert "issuer_name" not in missing


def test_build_warnings_flags_bad_checksum():
    warnings = build_warnings({"issuer_cnpj": "11.222.333/0001-00"})
    assert "invalid_issuer_cnpj_checksum" in warnings
