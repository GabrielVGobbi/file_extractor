"""OCR abstraction shared by Tesseract and Surya backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO

from PIL import Image

from app.extractors.base import ExtractedText


class BaseOCR(ABC):
    """Minimal contract for an OCR backend."""

    name: str = "base"

    @abstractmethod
    def recognize_image(self, data: bytes) -> ExtractedText:
        """Recognise text in a raster image (bytes of PNG/JPG/WebP)."""

    @abstractmethod
    def recognize_pdf(self, data: bytes) -> ExtractedText:
        """Recognise text in a (likely scanned) PDF."""

    @staticmethod
    def _open_image(data: bytes) -> Image.Image:
        return Image.open(BytesIO(data)).convert("RGB")
