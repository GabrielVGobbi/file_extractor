"""Pytest fixtures shared across the suite."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("ENABLE_CELERY", "false")
os.environ.setdefault("APP_ENV", "development")
# Tests run with cache disabled so runs don't pollute each other.
os.environ.setdefault("ENABLE_CACHE", "false")

from app.config import get_settings  # noqa: E402  (env must be set first)
from app.llm.client import AnthropicExtractor, LLMExtraction  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.extractor_service import ExtractorService  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture()
def mock_llm(monkeypatch) -> Iterator[MagicMock]:
    """Patch :class:`AnthropicExtractor.extract` so no network call happens."""
    mock = MagicMock()

    def _extract(self, document_text: str, *, hint_type: str | None = None):  # noqa: ARG001
        return mock(document_text, hint_type=hint_type)

    monkeypatch.setattr(AnthropicExtractor, "extract", _extract)
    yield mock


@pytest.fixture()
def app_client(mock_llm, settings) -> Iterator[TestClient]:
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def extractor_service(settings) -> ExtractorService:
    return ExtractorService(settings=settings)


def llm_success(payload: dict) -> LLMExtraction:
    return LLMExtraction(payload=payload, stop_reason="tool_use", usage=None)
