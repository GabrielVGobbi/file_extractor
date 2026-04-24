"""Factory that resolves the configured OCR backend at runtime."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.extractors.ocr.base import BaseOCR


@lru_cache(maxsize=2)
def _build(engine: str) -> BaseOCR:
    settings = get_settings()
    if engine == "surya":
        from app.extractors.ocr.surya import SuryaOCR

        return SuryaOCR(settings)
    from app.extractors.ocr.tesseract import TesseractOCR

    return TesseractOCR(settings)


def get_ocr(settings: Settings | None = None) -> BaseOCR:
    """Return the OCR backend selected by ``settings.ocr_engine``."""
    settings = settings or get_settings()
    return _build(settings.ocr_engine)
