"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. All values overridable via environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    log_level: str = "INFO"
    cors_origins: str = "*"

    auth_enabled: bool = True
    jwt_secret: str = "change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 90.0

    max_file_size_mb: int = 20
    accepted_mimetypes: str = (
        "application/pdf,image/jpeg,image/png,image/webp,"
        "text/xml,application/xml,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    ocr_engine: Literal["tesseract", "surya"] = "tesseract"
    ocr_language: str = "por"
    ocr_dpi: int = 220
    tesseract_cmd: str | None = None
    tessdata_prefix: str | None = None
    poppler_path: str | None = None

    confidence_threshold: float = 0.70

    # --- Cost-control pipeline --------------------------------------------
    # When true, the service tries deterministic regex parsers before the
    # LLM. Only falls back to Anthropic when confidence stays below
    # ``heuristic_min_confidence``.
    enable_heuristic: bool = True
    heuristic_min_confidence: float = 0.70

    # Content-addressable cache (sha256 of the upload). Cheap redundant
    # extractions cost 0. Disable for privacy-sensitive deployments.
    enable_cache: bool = True
    cache_dir: str = ".cache/extractions"

    # When true, the LLM fallback is disabled at the service level and the
    # endpoint fails instead of spending tokens. Useful for "cheap tier"
    # deployments where you accept 70-90% coverage.
    disable_llm_fallback: bool = False

    enable_celery: bool = False
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    @field_validator("cors_origins")
    @classmethod
    def _strip_cors(cls, v: str) -> str:
        return v.strip()

    @field_validator("poppler_path", mode="after")
    @classmethod
    def _resolve_poppler_path(cls, v: str | None) -> str | None:
        """Normalise the Poppler path and auto-discover a nested ``bin`` folder.

        Accepts any of the common layouts produced when extracting the
        Windows release zip:

        - ``C:\\poppler\\Library\\bin``                    (already correct)
        - ``C:\\poppler\\Release-25.x.x-0``                 (auto-discovers ``*/Library/bin``)
        - ``C:\\poppler\\poppler-25.x.x``                   (auto-discovers ``Library/bin``)
        """
        if not v:
            return v
        path = Path(v).expanduser()
        if (path / "pdfinfo.exe").exists() or (path / "pdfinfo").exists():
            return str(path)
        # Walk a few levels looking for bin/pdfinfo[.exe]
        for candidate in path.rglob("pdfinfo.exe"):
            return str(candidate.parent)
        for candidate in path.rglob("pdfinfo"):
            return str(candidate.parent)
        return str(path)  # let pdf2image raise if the user insists

    @property
    def poppler_ok(self) -> bool:
        if not self.poppler_path:
            return False
        p = Path(self.poppler_path)
        return (p / "pdfinfo.exe").exists() or (p / "pdfinfo").exists()

    @property
    def tesseract_ok(self) -> bool:
        if self.tesseract_cmd:
            return Path(self.tesseract_cmd).exists()
        # On Linux/Mac the binary is expected to be on PATH.
        return os.name != "nt"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def accepted_mimetypes_set(self) -> set[str]:
        return {m.strip() for m in self.accepted_mimetypes.split(",") if m.strip()}

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton accessor. Use as a FastAPI dependency."""
    return Settings()
