"""PDF text extraction using PyMuPDF.

When a PDF has no embedded text (i.e. it is scanned) we return an empty
``ExtractedText`` plus a flag so the caller can dispatch to OCR instead.
"""

from __future__ import annotations

from dataclasses import dataclass

import fitz  # type: ignore[import-not-found]

from app.extractors.base import ExtractedText

_SCAN_TEXT_THRESHOLD = 50  # characters considered "real text" per page


@dataclass
class PdfExtractionResult:
    """Result wrapper: either we got text or the PDF is scanned."""

    extracted: ExtractedText
    is_scanned: bool


def is_scanned_pdf(data: bytes) -> bool:
    """Return True when the PDF has virtually no embedded text (image-only)."""
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text().strip()
            if len(text) > _SCAN_TEXT_THRESHOLD:
                return False
    return True


def extract_pdf_text(data: bytes) -> PdfExtractionResult:
    """Extract text from a PDF buffer.

    Pages are concatenated with a form-feed separator so the LLM can reason
    about page boundaries if it needs to.
    """
    parts: list[str] = []
    total_chars = 0
    page_count = 0
    warnings: list[str] = []

    with fitz.open(stream=data, filetype="pdf") as doc:
        page_count = doc.page_count
        for page in doc:
            text = page.get_text("text") or ""
            parts.append(text)
            total_chars += len(text.strip())

    combined = "\f".join(parts).strip()
    scanned = total_chars < _SCAN_TEXT_THRESHOLD * max(page_count, 1)

    if scanned and not combined:
        warnings.append("pdf_has_no_embedded_text")

    return PdfExtractionResult(
        extracted=ExtractedText(
            text=combined,
            source="pdf_text",
            page_count=page_count,
            warnings=warnings,
        ),
        is_scanned=scanned,
    )
