"""Surya-backed OCR (optional, higher quality on noisy inputs).

Surya is a transformer-based OCR that benefits from GPU. We lazy-import
so the baseline Docker image stays small: this module only loads the
heavy dependencies when ``OCR_ENGINE=surya`` at runtime.
"""

from __future__ import annotations

from pdf2image import convert_from_bytes

from app.config import Settings
from app.extractors.base import ExtractedText
from app.extractors.ocr.base import BaseOCR


class SuryaOCR(BaseOCR):
    """Surya wrapper. Models are downloaded on first use and cached."""

    name = "surya"

    def __init__(self, settings: Settings) -> None:
        self._language = [settings.ocr_language or "por"]
        self._dpi = settings.ocr_dpi or 220
        self._poppler_path = settings.poppler_path
        # Lazy model load — keeps ``import`` cheap.
        from surya.model.detection.model import load_model as load_det_model  # type: ignore
        from surya.model.detection.model import load_processor as load_det_processor  # type: ignore
        from surya.model.recognition.model import load_model as load_rec_model  # type: ignore
        from surya.model.recognition.processor import load_processor as load_rec_processor  # type: ignore

        self._det_model = load_det_model()
        self._det_processor = load_det_processor()
        self._rec_model = load_rec_model()
        self._rec_processor = load_rec_processor()

    def _run(self, images: list) -> list[str]:
        from surya.ocr import run_ocr  # type: ignore

        predictions = run_ocr(
            images,
            [self._language] * len(images),
            self._det_model,
            self._det_processor,
            self._rec_model,
            self._rec_processor,
        )
        out: list[str] = []
        for page in predictions:
            lines = getattr(page, "text_lines", [])
            out.append("\n".join(line.text for line in lines))
        return out

    def recognize_image(self, data: bytes) -> ExtractedText:
        image = self._open_image(data)
        text = self._run([image])[0]
        return ExtractedText(text=text.strip(), source="image_ocr", page_count=1)

    def recognize_pdf(self, data: bytes) -> ExtractedText:
        images = convert_from_bytes(
            data,
            dpi=self._dpi,
            poppler_path=self._poppler_path,
        )
        pages = self._run(list(images))
        return ExtractedText(
            text="\f".join(p.strip() for p in pages).strip(),
            source="ocr",
            page_count=len(pages),
        )
