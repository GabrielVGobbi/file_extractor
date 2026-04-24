"""Shared FastAPI dependencies used by multiple routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.extractor_service import ExtractorService


def get_extractor_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExtractorService:
    """Build a fresh ``ExtractorService`` per request.

    The LLM client inside is only instantiated on first use, so XML-only
    requests never contact Anthropic.
    """
    return ExtractorService(settings=settings)
