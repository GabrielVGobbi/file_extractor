"""Tests for the NFS-e ABRASF regex parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.extractors.heuristic import try_heuristic_extract
from app.extractors.heuristic.common import to_cents
from app.extractors.heuristic.nfse_abrasf import is_nfse, parse

FIXTURE = Path(__file__).parent / "fixtures" / "nfse_teresina_ocr.txt"
NFSE_TEXT = FIXTURE.read_text(encoding="utf-8")


def test_is_nfse_detects_teresina_layout():
    assert is_nfse(NFSE_TEXT) is True


def test_is_nfse_rejects_random_text():
    assert is_nfse("Lorem ipsum dolor sit amet") is False


def test_parse_extracts_core_fields():
    payload = parse(NFSE_TEXT)

    assert payload is not None
    assert payload["fiscal_document_number"] == "183"
    assert payload["series"] == "U"
    assert payload["issuer_cnpj"] == "31.070.254/0001-00"
    assert payload["recipient_document"] == "28.390.966/0006-06"
    assert payload["issuer_name"].startswith("BRASIL HIDRAULICOS")
    assert payload["recipient_name"].startswith("LAND SOLUCOES")
    assert payload["total_fiscal_document"] == 95000  # R$ 950,00
    assert payload["issued_at"].startswith("2026-04-14T17:42:47")
    assert payload["competence_at"] == "2026-04-01"


def test_parse_extracts_number_from_danfse_label():
    text = """
    DANFSe v1.0
    Documento Auxiliar da NFS-e
    Chave de Acesso da NFS-e
    31186011247808930000130000000000015526067021669695
    Número da NFS-e
    155
    Data e Hora da emissão da NFS-e
    15/06/2026 15:00:44
    EMITENTE DA NFS-e
    Prestador do Serviço
    CNPJ / CPF / NIF
    47.808.930/0001-30
    TOMADOR DO SERVIÇO
    CNPJ / CPF / NIF
    28.390.966/0001-00
    SERVIÇO PRESTADO
    Código de Tributação Nacional
    14.01.01 - Lubrificação, limpeza
    Valor do Serviço
    R$ 2.137,00
    ISSQN
    """

    payload = parse(text)

    assert payload is not None
    assert payload["fiscal_document_number"] == "155"
    assert payload["access_key"] == "31186011247808930000130000000000015526067021669695"
    assert payload["fiscal_info"]["national_identifier"] == "31186011247808930000130000000000015526067021669695"


def test_parse_extracts_fiscal_info():
    payload = parse(NFSE_TEXT)
    assert payload is not None
    info = payload["fiscal_info"]
    assert info.get("verification_code") == "goD3XLFsi"
    assert info.get("simples_nacional") is True
    assert info.get("issqn_retention") == "NÃO RETIDO"
    assert "14.01" in info.get("service_code", "")


def test_parse_extracts_nature_operation():
    payload = parse(NFSE_TEXT)
    assert payload is not None
    assert "LUBRIFICACAO" in payload["nature_operation"].upper()


def test_try_heuristic_extract_returns_best():
    result = try_heuristic_extract(NFSE_TEXT)
    assert result is not None
    assert result.parser == "nfse_abrasf"
    assert result.confidence >= 0.70
    assert result.payload["fiscal_document_number"] == "183"


def test_try_heuristic_extract_returns_none_when_unrecognisable():
    result = try_heuristic_extract("hello world this is not a fiscal document")
    assert result is None


def test_try_heuristic_extract_respects_hint_type():
    # Hint explicitly says NF-e, so the NFS-e parser must bow out.
    result = try_heuristic_extract(NFSE_TEXT, hint_type="nfe")
    assert result is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("950,00", 95000),
        ("1.234,56", 123456),
        ("R$ 1.000,00", 100000),
        ("0,00", 0),
        ("1234.56", 123456),
        ("abc", None),
    ],
)
def test_to_cents(raw, expected):
    assert to_cents(raw) == expected
