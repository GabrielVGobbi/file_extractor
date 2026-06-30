from pathlib import Path

import pytest

from app.extractors.xml_nfe import parse_xml

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def nfse_bytes() -> bytes:
    return (FIXTURES / "nfse_sample.xml").read_bytes()


@pytest.fixture()
def nfe_bytes() -> bytes:
    return (FIXTURES / "nfe_sample.xml").read_bytes()


def test_nfse_parse_core_fields(nfse_bytes):
    data = parse_xml(nfse_bytes)
    assert data["document_category"] == "nfse"
    assert data["fiscal_document_number"] == "183"
    assert data["model"] == "99"
    assert data["series"] == "U"
    assert data["issuer_cnpj"] == "31070254000100"
    assert data["issuer_name"] == "BRASIL HIDRAULICOS PECAS E SERVICOS LTDA"
    assert data["recipient_name"] == "LAND SOLUCOES LTDA"
    assert data["total_services"] == 95000
    assert data["total_fiscal_document"] == 95000
    assert data["fiscal_document_net_value"] == 95000
    assert data["iss_value"] == 0
    assert data["issuer_address"]["city"] == "2211001"
    assert data["fiscal_info"]["service_code"] == "14.01"


def test_nfse_origin_and_direction(nfse_bytes):
    data = parse_xml(nfse_bytes)
    assert data["origin"] == "xml_upload"
    assert data["direction"] == "outbound"
    assert data["type"] == "saida"


def test_nfe_parse_core_fields(nfe_bytes):
    data = parse_xml(nfe_bytes)
    assert data["document_category"] == "nfe"
    assert data["fiscal_document_number"] == "123"
    assert data["model"] == "55"
    assert data["series"] == "1"
    assert data["issuer_cnpj"] == "14200166000187"
    assert data["recipient_document"] == "28390966000606"
    assert data["total_fiscal_document"] == 100000  # R$ 1000,00
    assert data["pis_value"] == 1650
    assert data["cofins_value"] == 7600
    assert data["direction"] == "outbound"
    assert data["type"] == "saida"


def test_unsupported_xml_raises():
    with pytest.raises(ValueError):
        parse_xml(b"<?xml version='1.0'?><foo><bar/></foo>")
