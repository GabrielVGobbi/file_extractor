"""GET /api/v1/jobs/{id} — query async extraction job status."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import TokenPayload, verify_jwt
from app.config import Settings, get_settings
from app.schemas.response import ErrorResponse, ExtractionResponse, JobStatusResponse

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobStatusResponse, name="get_job_status")
async def get_job_status(
    job_id: str,
    _: Annotated[TokenPayload, Depends(verify_jwt)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JobStatusResponse:
    """Return the status + result of a Celery extraction job."""
    if not settings.enable_celery:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async mode is disabled (set ENABLE_CELERY=true).",
        )

    from celery.result import AsyncResult

    from app.workers.celery_app import celery_app

    result = AsyncResult(job_id, app=celery_app)

    mapping = {
        "PENDING": "queued",
        "STARTED": "processing",
        "RETRY": "processing",
        "SUCCESS": "succeeded",
        "FAILURE": "failed",
    }
    state_str: str = mapping.get(result.state, "queued")  # type: ignore[assignment]

    response = JobStatusResponse(job_id=job_id, status=state_str)  # type: ignore[arg-type]

    if result.successful():
        payload = result.result
        if isinstance(payload, dict) and payload.get("status") == "error":
            response.error = ErrorResponse.model_validate(payload)
            response.status = "failed"
        elif isinstance(payload, dict):
            response.result = ExtractionResponse.model_validate(payload)
    elif result.failed():
        response.error = ErrorResponse(
            error_code="TASK_FAILED",
            message=str(result.result) if result.result else "Task failed",
        )

    return response
