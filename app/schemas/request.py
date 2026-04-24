"""Request schemas for the extraction endpoint."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DocumentTypeHint = Literal["nfe", "nfse", "nfce", "cte", "auto"]
DirectionHint = Literal["inbound", "outbound", "auto"]


class ExtractionOptions(BaseModel):
    """Form-data fields that accompany the uploaded file.

    Values are parsed individually by FastAPI as ``Form(...)`` params; this
    model exists as documentation and for use inside services.
    """

    model_config = ConfigDict(extra="ignore")

    document_type: DocumentTypeHint = "auto"
    direction: DirectionHint = "auto"
    organization_id: UUID | None = None
    branch_id: UUID | None = None
    async_mode: bool = False
