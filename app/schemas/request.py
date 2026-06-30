"""Request schemas for the extraction endpoint."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DocumentTypeHint = Literal[
    "nfe",
    "nfse",
    "nfce",
    "cte",
    "nf3e",
    "utility_water",
    "utility_electricity",
    "utility_gas",
    "utility_telecom",
    "rental_invoice",
    "boleto",
    "invoice",
    "receipt",
    "auto",
]
DirectionHint = Literal["inbound", "outbound", "auto"]


class ExtractionOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_type: DocumentTypeHint = "auto"
    direction: DirectionHint = "auto"
    organization_id: UUID | None = None
    branch_id: UUID | None = None
    async_mode: bool = False
