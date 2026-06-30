"""Response envelopes returned by the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document import DocumentExtractionData

# Backward-compatible alias
FiscalDocumentData = DocumentExtractionData

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
    model_config = ConfigDict(extra="ignore")

    status: ExtractionStatus = "success"
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_method: ExtractionMethod
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data: DocumentExtractionData


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["error"] = "error"
    error_code: str
    message: str
    partial_data: dict[str, Any] | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["accepted"] = "accepted"
    job_id: str
    poll_url: str


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str
    status: JobStatus
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    result: ExtractionResponse | None = None
    error: ErrorResponse | None = None
