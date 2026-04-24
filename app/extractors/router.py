"""Dispatcher that picks the right extractor for the detected file type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import Settings
from app.extractors import docx as docx_extractor
from app.extractors import pdf as pdf_extractor
from app.extractors import xml_nfe
from app.extractors.base import ExtractedText
from app.extractors.ocr.factory import get_ocr
from app.utils.file_type import DetectedFile

Stage = Literal["structured", "text_for_llm"]


@dataclass
class RoutedResult:
    """Output of the router.

    ``structured_data`` is set when we hit the deterministic XML path; in
    that case the caller skips the LLM entirely. Otherwise ``extracted``
    contains raw text to feed the LLM.
    """

    stage: Stage
    extracted: ExtractedText | None = None
    structured_data: dict | None = None


def route(
    data: bytes,
    detected: DetectedFile,
    settings: Settings,
) -> RoutedResult:
    """Run the appropriate extractor based on ``detected.category``."""
    if detected.category == "xml":
        structured = xml_nfe.parse_xml(data)
        return RoutedResult(stage="structured", structured_data=structured)

    if detected.category == "pdf":
        pdf_result = pdf_extractor.extract_pdf_text(data)
        if pdf_result.is_scanned or pdf_result.extracted.is_empty:
            ocr = get_ocr(settings)
            return RoutedResult(stage="text_for_llm", extracted=ocr.recognize_pdf(data))
        return RoutedResult(stage="text_for_llm", extracted=pdf_result.extracted)

    if detected.category == "image":
        ocr = get_ocr(settings)
        return RoutedResult(stage="text_for_llm", extracted=ocr.recognize_image(data))

    if detected.category == "docx":
        return RoutedResult(stage="text_for_llm", extracted=docx_extractor.extract_docx_text(data))

    raise ValueError(f"Unsupported file category: {detected.category} ({detected.mimetype})")
