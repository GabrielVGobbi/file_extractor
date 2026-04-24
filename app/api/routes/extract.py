"""POST /api/v1/extract — cost-aware fiscal document extraction.

Request-level knobs (all optional, all via HTTP headers):

* ``X-Output-Format``: ``json_fiscal`` (default) → structured JSON;
  ``markdown`` → raw OCR text rendered as markdown.
* ``X-Extraction-Strategy``: ``auto`` (default) → cache → heuristic → LLM;
  ``no_llm`` → deterministic only (fails if not enough signal);
  ``force_llm`` → skip cache + heuristic;
  ``cache_only`` → 422 on cache miss.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.deps import get_extractor_service
from app.auth import TokenPayload, verify_jwt
from app.config import Settings, get_settings
from app.schemas.request import DirectionHint, DocumentTypeHint
from app.schemas.response import ExtractionResponse, JobResponse
from app.services.extractor_service import (
    ExtractionServiceError,
    ExtractorService,
)
from app.services.markdown_formatter import to_markdown

router = APIRouter(prefix="/api/v1", tags=["extract"])

OutputFormat = Literal["json_fiscal", "markdown"]
_VALID_FORMATS: set[str] = {"json_fiscal", "markdown"}
_VALID_STRATEGIES: set[str] = {"auto", "no_llm", "force_llm", "cache_only"}


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    responses={
        200: {"description": "Structured JSON or raw markdown, depending on X-Output-Format"},
        202: {"model": JobResponse, "description": "Accepted for async processing"},
        422: {"description": "Validation / extraction failure"},
    },
)
async def extract_document(
    request: Request,
    _: Annotated[TokenPayload, Depends(verify_jwt)],
    service: Annotated[ExtractorService, Depends(get_extractor_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(description="PDF, image, XML or DOCX")],
    document_type: Annotated[DocumentTypeHint, Form()] = "auto",
    direction: Annotated[DirectionHint, Form()] = "auto",
    organization_id: Annotated[UUID | None, Form()] = None,
    branch_id: Annotated[UUID | None, Form()] = None,
    async_mode: Annotated[bool, Form(alias="async")] = False,
    output_format: Annotated[str, Header(alias="X-Output-Format")] = "json_fiscal",
    extraction_strategy: Annotated[
        str, Header(alias="X-Extraction-Strategy")
    ] = "auto",
):
    """Extract fiscal data from the uploaded file.

    Synchronous by default. Pass ``async=true`` to dispatch via Celery.
    """
    output_format = output_format.lower().strip()
    extraction_strategy = extraction_strategy.lower().strip()
    if output_format not in _VALID_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid X-Output-Format. Use one of: {sorted(_VALID_FORMATS)}",
        )
    if extraction_strategy not in _VALID_STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid X-Extraction-Strategy. Use one of: {sorted(_VALID_STRATEGIES)}",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file payload"
        )

    # Markdown output skips the structured pipeline entirely: useful when
    # the caller only wants the OCR'd text (zero LLM cost, zero regex,
    # zero cache — always fresh).
    if output_format == "markdown":
        try:
            text, source = service.extract_text(file_bytes=raw, filename=file.filename)
        except ExtractionServiceError as exc:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=exc.error.model_dump(),
            )
        body = to_markdown(text, title=file.filename)
        return PlainTextResponse(
            content=body,
            media_type="text/markdown; charset=utf-8",
            headers={"X-Text-Source": source},
        )

    if async_mode:
        if not settings.enable_celery:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Async mode is disabled (set ENABLE_CELERY=true).",
            )
        from app.workers.tasks import run_extraction

        task = run_extraction.delay(
            file_bytes=raw,
            filename=file.filename,
            document_type=document_type,
            direction=direction,
            organization_id=str(organization_id) if organization_id else None,
            branch_id=str(branch_id) if branch_id else None,
            strategy=extraction_strategy,
        )
        poll_url = str(request.url_for("get_job_status", job_id=task.id))
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=JobResponse(job_id=task.id, poll_url=poll_url).model_dump(),
        )

    try:
        result = service.extract(
            file_bytes=raw,
            filename=file.filename,
            document_type=document_type,
            direction=direction,
            organization_id=str(organization_id) if organization_id else None,
            branch_id=str(branch_id) if branch_id else None,
            strategy=extraction_strategy,  # type: ignore[arg-type]
        )
    except ExtractionServiceError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=exc.error.model_dump(),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result.model_dump(mode="json"),
        headers={"X-Extraction-Method": result.extraction_method},
    )
