"""Celery tasks that execute the extractor pipeline asynchronously."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.services.extractor_service import ExtractionServiceError, ExtractorService
from app.utils.logging import configure_logging, get_logger
from app.workers.celery_app import celery_app

_settings = get_settings()
configure_logging(_settings.log_level)
logger = get_logger(__name__)


@celery_app.task(name="fiscal.run_extraction", bind=True)
def run_extraction(
    self,
    *,
    file_bytes: bytes,
    filename: str | None,
    document_type: str = "auto",
    direction: str = "auto",
    organization_id: str | None = None,
    branch_id: str | None = None,
    strategy: str = "auto",
) -> dict[str, Any]:
    """Run ``ExtractorService.extract`` and return a JSON-ready dict.

    Errors are serialised as ``ErrorResponse`` payloads so the polling
    endpoint can surface them back to the caller.
    """
    service = ExtractorService(settings=_settings)
    try:
        result = service.extract(
            file_bytes=file_bytes,
            filename=filename,
            document_type=document_type,
            direction=direction,
            organization_id=organization_id,
            branch_id=branch_id,
            strategy=strategy,  # type: ignore[arg-type]
        )
    except ExtractionServiceError as exc:
        logger.warning("task_extraction_failed", error=exc.error.error_code)
        return exc.error.model_dump()
    return result.model_dump(mode="json")
