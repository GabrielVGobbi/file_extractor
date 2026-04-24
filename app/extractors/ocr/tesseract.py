"""Tesseract-backed OCR (default engine).

Runs locally on CPU. Requires the ``tesseract-ocr`` binary + language packs
and ``poppler`` (for ``pdf2image``) installed on the host.
"""

from __future__ import annotations

import os

import pytesseract
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError

from app.config import Settings
from app.extractors.base import ExtractedText
from app.extractors.ocr.base import BaseOCR


class OCRDependencyError(RuntimeError):
    """Raised when a required native binary (Poppler / Tesseract) is missing."""


class TesseractOCR(BaseOCR):
    """Thin wrapper around ``pytesseract`` + ``pdf2image``."""

    name = "tesseract"

    def __init__(self, settings: Settings) -> None:
        self._language = settings.ocr_language or "por"
        self._dpi = settings.ocr_dpi or 220
        self._poppler_path = settings.poppler_path
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        # Exporting ``TESSDATA_PREFIX`` is more reliable than passing
        # ``--tessdata-dir`` via pytesseract (the latter trips over path
        # quoting on Windows).
        if settings.tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = settings.tessdata_prefix

    def _ocr(self, image) -> str:
        return pytesseract.image_to_string(image, lang=self._language) or ""

    def recognize_image(self, data: bytes) -> ExtractedText:
        image = self._open_image(data)
        return ExtractedText(text=self._ocr(image).strip(), source="image_ocr", page_count=1)

    def recognize_pdf(self, data: bytes) -> ExtractedText:
        try:
            images = convert_from_bytes(
                data,
                dpi=self._dpi,
                poppler_path=self._poppler_path,
            )
        except (PDFInfoNotInstalledError, FileNotFoundError) as exc:
            raise OCRDependencyError(
                "Poppler binaries not found. Scanned PDFs need `pdfinfo` and "
                "`pdftoppm` on the system PATH or via POPPLER_PATH. "
                "Download from https://github.com/oschwartz10612/poppler-windows/releases "
                "and point POPPLER_PATH at the folder containing pdfinfo.exe."
            ) from exc
        pages = [self._ocr(image) for image in images]
        return ExtractedText(
            text="\f".join(p.strip() for p in pages).strip(),
            source="ocr",
            page_count=len(pages),
        )
