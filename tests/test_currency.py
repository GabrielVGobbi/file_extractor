from app.validators.currency import MONEY_FIELDS, normalize_money_fields, to_cents


def test_to_cents_brl_with_symbol():
    assert to_cents("R$ 950,00") == 95000


def test_to_cents_thousands_separator():
    assert to_cents("1.234,56") == 123456


def test_to_cents_us_notation():
    assert to_cents("1234.56") == 123456


def test_to_cents_integer_passthrough():
    assert to_cents(95000) == 95000


def test_to_cents_none_and_empty():
    assert to_cents(None) is None
    assert to_cents("") is None
    assert to_cents("  ") is None


def test_to_cents_invalid():
    assert to_cents("abc") is None


def test_normalize_money_fields_mutates_only_known_keys():
    data = {
        "total_fiscal_document": "R$ 1.234,56",
        "issuer_name": "ACME LTDA",
        "iss_value": 0,
    }
    out = normalize_money_fields(data, MONEY_FIELDS)
    assert out["total_fiscal_document"] == 123456
    assert out["issuer_name"] == "ACME LTDA"
    assert out["iss_value"] == 0
