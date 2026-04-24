"""Pydantic schemas that mirror the ERP ``fiscal_documents`` table.

These types drive both the JSON tool schema sent to the LLM and the
final validation of its output.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentType = Literal["nfe", "nfse", "nfce", "cte"]
Direction = Literal["inbound", "outbound"]
OperationType = Literal["entrada", "saida"]
Origin = Literal["pdf_upload", "xml_upload", "manual", "image_upload", "docx_upload"]
DocumentStatus = Literal["authorized", "cancelled", "denied", "pending"]


class Address(BaseModel):
    """Structured address fragment used for issuer and recipient."""

    model_config = ConfigDict(extra="ignore")

    street: str | None = None
    number: str | None = None
    complement: str | None = None
    block: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = Field(default="BRASIL")
    zip: str | None = None


class FiscalInfo(BaseModel):
    """Tax / regime metadata. Free-form to support NFe, NFS-e and CT-e."""

    model_config = ConfigDict(extra="allow")

    issqn_exigibility: str | None = None
    issqn_municipality: str | None = None
    issqn_responsible: str | None = None
    issqn_retention: str | None = None
    simples_nacional: bool | None = None
    special_tax_regime: str | None = None
    cnae: str | None = None
    service_code: str | None = None
    verification_code: str | None = None


class ExtractionMetadata(BaseModel):
    """Extraction provenance attached to the persisted row."""

    model_config = ConfigDict(extra="allow")

    extraction_method: Literal[
        "llm",
        "xml_parser",
        "ocr+llm",
        "heuristic",
        "ocr+heuristic",
        "cache",
    ] = "llm"
    confidence: float = 0.0
    extracted_at: datetime | None = None


class FiscalDocumentData(BaseModel):
    """Mirrors the columns of ``fiscal_documents`` for direct DB insert.

    Monetary values are stored as **integer cents** to avoid floating point
    drift.
    """

    model_config = ConfigDict(extra="ignore")

    access_key: str | None = None
    fiscal_document_number: str | None = None
    series: str | None = None
    model: str | None = None
    nature_operation: str | None = None
    type: OperationType | None = None
    direction: Direction | None = None
    origin: Origin | None = None
    status: DocumentStatus | None = None

    issued_at: datetime | None = None
    competence_at: date | None = None

    issuer_cnpj: str | None = None
    issuer_name: str | None = None
    issuer_fancy_name: str | None = None
    issuer_ie: str | None = None
    issuer_crt: str | None = None
    issuer_address: Address | None = None

    recipient_document: str | None = None
    recipient_name: str | None = None
    recipient_ie: str | None = None
    recipient_address: Address | None = None

    total_services: int | None = None
    subtotal: int | None = None
    total_fiscal_document: int | None = None
    fiscal_document_net_value: int | None = None
    total_discount: int | None = None
    total_products: int | None = None
    total_freight: int | None = None

    iss_value: int | None = None
    pis_value: int | None = None
    cofins_value: int | None = None
    inss_value: int | None = None
    irrf_value: int | None = None
    csll_value: int | None = None

    installments_count: int | None = None

    additional_info: str | None = None

    fiscal_info: FiscalInfo | None = None
    metadata: ExtractionMetadata | None = None
