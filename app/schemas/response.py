"""Response envelopes returned by the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.fiscal import FiscalDocumentData

ExtractionStatus = Literal["success", "partial", "error"]
ExtractionMethod = Literal[
    "llm",
    "xml_parser",
    "ocr+llm",
    "heuristic",
    "ocr+heuristic",
    "cache",
]
JobStatus = Literal["queued", "processing", "succeeded", "failed"]


class ExtractionResponse(BaseModel):
    """Successful extraction envelope (also used for ``partial`` results)."""

    model_config = ConfigDict(extra="ignore")

    status: ExtractionStatus = "success"
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_method: ExtractionMethod
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data: FiscalDocumentData


class ErrorResponse(BaseModel):
    """Shape returned on validation / extraction failures."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["error"] = "error"
    error_code: str
    message: str
    partial_data: dict[str, Any] | None = None


class JobResponse(BaseModel):
    """Envelope returned when ``async=true`` is used."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["accepted"] = "accepted"
    job_id: str
    poll_url: str


class JobStatusResponse(BaseModel):
    """Status + eventual result of an async extraction job."""

    model_config = ConfigDict(extra="ignore")

    job_id: str
    status: JobStatus
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    result: ExtractionResponse | None = None
    error: ErrorResponse | None = None
