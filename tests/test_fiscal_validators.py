from app.validators.fiscal import (
    is_valid_cnpj,
    is_valid_cpf,
    is_valid_document,
    is_valid_nfe_access_key,
    only_digits,
)


def test_only_digits():
    assert only_digits("31.070.254/0001-00") == "31070254000100"
    assert only_digits(None) == ""


def test_valid_cnpj():
    # Receita-generated valid CNPJ
    assert is_valid_cnpj("11.222.333/0001-81") is True
    assert is_valid_cnpj("11.222.333/0001-82") is False
    assert is_valid_cnpj("11111111111111") is False


def test_valid_cpf():
    assert is_valid_cpf("529.982.247-25") is True
    assert is_valid_cpf("111.111.111-11") is False


def test_is_valid_document_accepts_both():
    assert is_valid_document("11.222.333/0001-81") is True
    assert is_valid_document("529.982.247-25") is True
    assert is_valid_document("123") is False


def test_invalid_access_key_length():
    assert is_valid_nfe_access_key("12345") is False
