"""Shared types for the extractor pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TextSource = Literal["pdf_text", "ocr", "docx_text", "image_ocr"]


@dataclass
class ExtractedText:
    """Raw-text payload produced by the non-LLM extractors.

    Everything in this dataclass is fed into the LLM stage (or ignored when
    we already have a structured parser such as the XML one).
    """

    text: str
    source: TextSource
    page_count: int = 1
    warnings: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.text or not self.text.strip()
