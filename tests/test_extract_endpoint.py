"""End-to-end tests for POST /api/v1/extract."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import llm_success

FIXTURES = Path(__file__).parent / "fixtures"


def test_health():
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_extract_xml_skips_llm(app_client, mock_llm):
    xml = (FIXTURES / "nfse_sample.xml").read_bytes()
    resp = app_client.post(
        "/api/v1/extract",
        files={"file": ("nfse.xml", xml, "application/xml")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["extraction_method"] == "xml_parser"
    assert body["confidence"] == 1.0
    assert body["data"]["fiscal_document_number"] == "183"
    mock_llm.assert_not_called()


def _build_pdf_with_text(text: str) -> bytes:
    """Build an in-memory PDF, paginating automatically to avoid truncation."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in text.splitlines():
        if y > 760:
            page = doc.new_page()
            y = 72
        page.insert_text((72, y), line)
        y += 14
    data = doc.write()
    doc.close()
    return data


def test_extract_pdf_force_llm_header(app_client, mock_llm):
    # Text-based PDF with a NFS-e layout; with force_llm the heuristic is
    # bypassed and the LLM is guaranteed to be invoked.
    text = (
        "NOTA FISCAL ELETRONICA DE SERVICOS Nº 183\n"
        "PRESTADOR: BRASIL HIDRAULICOS PECAS E SERVICOS LTDA\n"
        "CNPJ: 31.070.254/0001-00\n"
        "DATA DE EMISSAO: 14/04/2026\n"
        "VALOR TOTAL DOS SERVICOS: R$ 950,00\n"
        "TOMADOR: LAND SOLUCOES LTDA CNPJ 28.390.966/0006-06\n"
    )
    data = _build_pdf_with_text(text)

    mock_llm.return_value = llm_success(
        {
            "fiscal_document_number": "183",
            "issuer_cnpj": "11.222.333/0001-81",
            "issuer_name": "ACME LTDA",
            "issued_at": "2026-04-14T17:42:47",
            "total_fiscal_document": 95000,
            "type": "saida",
            "direction": "outbound",
        }
    )

    resp = app_client.post(
        "/api/v1/extract",
        files={"file": ("nota.pdf", data, "application/pdf")},
        headers={"X-Extraction-Strategy": "force_llm"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["extraction_method"] == "llm"
    assert body["data"]["fiscal_document_number"] == "183"
    assert body["data"]["total_fiscal_document"] == 95000
    mock_llm.assert_called_once()


def test_extract_pdf_heuristic_skips_llm(app_client, mock_llm):
    """A NFS-e-shaped PDF must be handled by the regex heuristic, saving a
    round-trip to Anthropic entirely."""
    text = (FIXTURES / "nfse_teresina_ocr.txt").read_text(encoding="utf-8")
    data = _build_pdf_with_text(text)

    resp = app_client.post(
        "/api/v1/extract",
        files={"file": ("nota.pdf", data, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["extraction_method"] == "heuristic"
    assert body["data"]["fiscal_document_number"] == "183"
    assert body["data"]["issuer_cnpj"] == "31.070.254/0001-00"
    assert body["data"]["total_fiscal_document"] == 95000
    mock_llm.assert_not_called()


def test_extract_no_llm_strategy_rejects_when_heuristic_fails(app_client, mock_llm):
    """With ``no_llm`` the service must fail fast instead of spending tokens."""
    text = (
        "DOCUMENTO GENERICO SEM CAMPOS RECONHECIVEIS.\n"
        "Texto suficiente para passar do threshold de scanned-PDF.\n"
        "Lorem ipsum dolor sit amet consectetur adipiscing elit.\n"
    )
    data = _build_pdf_with_text(text)

    resp = app_client.post(
        "/api/v1/extract",
        files={"file": ("bad.pdf", data, "application/pdf")},
        headers={"X-Extraction-Strategy": "no_llm"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "HEURISTIC_INSUFFICIENT"
    mock_llm.assert_not_called()


def test_extract_markdown_output_format(app_client, mock_llm):
    text = (FIXTURES / "nfse_teresina_ocr.txt").read_text(encoding="utf-8")
    data = _build_pdf_with_text(text)

    resp = app_client.post(
        "/api/v1/extract",
        files={"file": ("nota.pdf", data, "application/pdf")},
        headers={"X-Output-Format": "markdown"},
    )
    assert resp.status_code == 200, resp.text
    assert "text/markdown" in resp.headers["content-type"]
    assert "NFSe" in resp.text or "NFS" in resp.text
    assert "183" in resp.text
    mock_llm.assert_not_called()


def test_extract_invalid_output_format_rejected(app_client):
    resp = app_client.post(
        "/api/v1/extract",
        files={"file": ("x.xml", b"<a/>", "application/xml")},
        headers={"X-Output-Format": "yaml"},
    )
    assert resp.status_code == 400


def test_extract_missing_required_returns_422(app_client, mock_llm):
    text = (
        "DOCUMENTO GENERICO COM TEXTO SUFICIENTE PARA NAO ENTRAR NO OCR\n"
        "Lorem ipsum dolor sit amet consectetur adipiscing elit.\n"
        "Descricao vazia sem campos fiscais reconheciveis.\n"
    )
    data = _build_pdf_with_text(text)

    mock_llm.return_value = llm_success({"series": "1"})

    resp = app_client.post(
        "/api/v1/extract",
        files={"file": ("bad.pdf", data, "application/pdf")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_code"] == "EXTRACTION_FAILED"


def test_extract_unsupported_mime_returns_422(app_client):
    resp = app_client.post(
        "/api/v1/extract",
        files={"file": ("blob.bin", b"??????", "application/octet-stream")},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "UNSUPPORTED_FILE_TYPE"


def test_async_mode_disabled_returns_503(app_client):
    resp = app_client.post(
        "/api/v1/extract",
        files={"file": ("nfse.xml", b"<?xml version='1.0'?><a/>", "application/xml")},
        data={"async": "true"},
    )
    assert resp.status_code == 503
