from app.utils.file_type import detect_file


def test_detect_pdf_by_magic():
    result = detect_file(b"%PDF-1.7\n...", "anything.pdf")
    assert result.category == "pdf"


def test_detect_png_by_magic():
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    result = detect_file(data, "doc.png")
    assert result.category == "image"


def test_detect_xml_by_content():
    data = b"<?xml version='1.0'?><foo/>"
    result = detect_file(data, "doc.xml")
    assert result.category == "xml"


def test_detect_docx_uses_extension_hint():
    data = b"PK\x03\x04" + b"\x00" * 20
    result = detect_file(data, "file.docx")
    assert result.category == "docx"


def test_detect_unknown():
    result = detect_file(b"???", "file.bin")
    assert result.category == "unknown"
