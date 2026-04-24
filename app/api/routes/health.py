"""Health-check endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def liveness() -> dict[str, str]:
    """Always returns 200 while the process is alive."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    """Summarises configuration so you can detect deploy-time misconfigs."""
    return {
        "status": "ok",
        "llm_configured": bool(settings.anthropic_api_key),
        "ocr_engine": settings.ocr_engine,
        "celery_enabled": settings.enable_celery,
        "auth_enabled": settings.auth_enabled,
        "env": settings.app_env,
        "poppler_path": settings.poppler_path,
        "poppler_ok": settings.poppler_ok,
        "tesseract_cmd": settings.tesseract_cmd,
        "tesseract_ok": settings.tesseract_ok,
    }
