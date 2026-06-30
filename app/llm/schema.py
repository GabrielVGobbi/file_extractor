"""Build the JSON schema used as an Anthropic tool definition."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.schemas.document import DocumentExtractionData

TOOL_NAME = "emit_document_data"
TOOL_DESCRIPTION = (
    "Retorna os dados estruturados do documento brasileiro (fiscal, utilidade, "
    "locação, boleto ou fatura genérica) extraídos do texto. "
    "Use sempre esta ferramenta como única forma de responder."
)

# Legacy alias kept for tests that patch tool name.
LEGACY_TOOL_NAME = "emit_fiscal_document"


def _strip_titles(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip_titles(v) for k, v in node.items() if k != "title"}
    if isinstance(node, list):
        return [_strip_titles(v) for v in node]
    return node


@lru_cache(maxsize=1)
def document_extraction_tool_schema() -> dict[str, Any]:
    schema = DocumentExtractionData.model_json_schema(mode="serialization")
    return _strip_titles(schema)


@lru_cache(maxsize=1)
def anthropic_tool_definition() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "input_schema": document_extraction_tool_schema(),
    }


# Backward-compatible aliases
fiscal_document_tool_schema = document_extraction_tool_schema
