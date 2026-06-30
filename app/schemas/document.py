"""Universal document extraction schema for ERP controladoria.

Covers fiscal documents (NF-e, NFS-e, NFC-e, CT-e, NF3e), utility bills
(water, electricity, telecom), rental invoices, boletos and generic
invoices. Flat fields mirror the ERP ``fiscal_documents`` table; nested
structures carry line items, parties, taxes, withholdings and payment data.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentCategory = Literal[
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
    "other",
]

PartyRole = Literal[
    "issuer",
    "recipient",
    "provider",
    "customer",
    "payer",
    "beneficiary",
    "intermediary",
]

Direction = Literal["inbound", "outbound"]
OperationType = Literal["entrada", "saida"]
Origin = Literal["pdf_upload", "xml_upload", "manual", "image_upload", "docx_upload"]
DocumentStatus = Literal["authorized", "cancelled", "denied", "pending", "paid", "open"]

WithholdingType = Literal[
    "iss",
    "irrf",
    "inss",
    "pis",
    "cofins",
    "csll",
    "ipi",
    "icms",
    "icms_st",
    "other",
]


class Address(BaseModel):
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


class Party(BaseModel):
    """Issuer, recipient, payer, beneficiary or other involved party."""

    model_config = ConfigDict(extra="ignore")

    role: PartyRole
    document_type: Literal["cnpj", "cpf"] | None = None
    document: str | None = None
    name: str | None = None
    fancy_name: str | None = None
    ie: str | None = None
    im: str | None = None
    email: str | None = None
    phone: str | None = None
    address: Address | None = None


class LineItem(BaseModel):
    """Product, service or billing line."""

    model_config = ConfigDict(extra="ignore")

    line_number: int | None = None
    code: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: int | None = None
    total_price: int | None = None
    discount: int | None = None
    ncm: str | None = None
    cfop: str | None = None
    cst: str | None = None
    service_code: str | None = None
    tax_rate: float | None = None
    icms_base: int | None = None
    icms_value: int | None = None
    ipi_value: int | None = None


class Withholding(BaseModel):
    """Tax retention (ISS retido, IRRF, INSS, etc.)."""

    model_config = ConfigDict(extra="ignore")

    type: WithholdingType
    base: int | None = None
    rate: float | None = None
    amount: int | None = None
    retained_by: Literal["issuer", "recipient"] | None = None
    description: str | None = None


class TaxEntry(BaseModel):
    """Individual tax line (ICMS, PIS, COFINS, ISS, etc.)."""

    model_config = ConfigDict(extra="ignore")

    type: str
    base: int | None = None
    rate: float | None = None
    amount: int | None = None


class PaymentInfo(BaseModel):
    """Boleto, PIX or other payment instrument."""

    model_config = ConfigDict(extra="ignore")

    has_boleto: bool | None = None
    has_pix: bool | None = None
    barcode: str | None = None
    digitable_line: str | None = None
    pix_code: str | None = None
    due_date: date | None = None
    bank: str | None = None
    bank_code: str | None = None
    agency: str | None = None
    account: str | None = None
    beneficiary_code: str | None = None
    our_number: str | None = None
    document_number: str | None = None
    total_amount: int | None = None
    installment_number: int | None = None
    installments_total: int | None = None
    auto_debit_code: str | None = None


class ConsumptionInfo(BaseModel):
    """Utility consumption (kWh, m³, GB, etc.)."""

    model_config = ConfigDict(extra="ignore")

    unit: str | None = None
    current_reading: float | None = None
    previous_reading: float | None = None
    consumption: float | None = None
    meter_id: str | None = None
    supply_code: str | None = None
    customer_code: str | None = None
    tariff_group: str | None = None


class BillingPeriod(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reference_month: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    issue_date: date | None = None
    presentation_date: date | None = None
    next_reading_date: date | None = None


class FiscalInfo(BaseModel):
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
    rps_number: str | None = None
    rps_series: str | None = None
    national_identifier: str | None = None
    service_municipality: str | None = None
    approximate_taxes: int | None = None
    approximate_taxes_rate: float | None = None


class ExtractionMetadata(BaseModel):
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
    detected_category: str | None = None
    detected_subtype: str | None = None


class DocumentExtractionData(BaseModel):
    """Full extraction payload for ERP controladoria and DB insert."""

    model_config = ConfigDict(extra="ignore")

    # Classification
    document_category: DocumentCategory = "other"
    document_subtype: str | None = None

    # ERP fiscal_documents flat fields (backward compatible)
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
    due_at: date | None = None

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
    icms_value: int | None = None
    icms_st_value: int | None = None
    ipi_value: int | None = None

    installments_count: int | None = None
    contract_number: str | None = None
    customer_code: str | None = None
    purchase_order: str | None = None

    additional_info: str | None = None

    # Rich nested structures
    parties: list[Party] = Field(default_factory=list)
    line_items: list[LineItem] = Field(default_factory=list)
    withholdings: list[Withholding] = Field(default_factory=list)
    taxes: list[TaxEntry] = Field(default_factory=list)
    payment: PaymentInfo | None = None
    consumption: ConsumptionInfo | None = None
    billing: BillingPeriod | None = None

    fiscal_info: FiscalInfo | None = None
    metadata: ExtractionMetadata | None = None


# Backward-compatible alias used by legacy imports and ERP mapping docs.
FiscalDocumentData = DocumentExtractionData
