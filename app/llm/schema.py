"""Build the JSON schema used as an Anthropic tool definition.

We derive the schema from ``FiscalDocumentData`` so it stays in sync with
the Pydantic model without hand-maintained drift.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.schemas.fiscal import FiscalDocumentData

TOOL_NAME = "emit_fiscal_document"
TOOL_DESCRIPTION = (
    "Retorna os dados estruturados do documento fiscal brasileiro extraídos do texto. "
    "Use sempre esta ferramenta como única forma de responder."
)


def _strip_titles(node: Any) -> Any:
    """Remove ``title`` keys for cleaner tool schemas (Anthropic ignores them)."""
    if isinstance(node, dict):
        return {k: _strip_titles(v) for k, v in node.items() if k != "title"}
    if isinstance(node, list):
        return [_strip_titles(v) for v in node]
    return node


@lru_cache(maxsize=1)
def fiscal_document_tool_schema() -> dict[str, Any]:
    """JSON schema for the ``FiscalDocumentData`` model."""
    schema = FiscalDocumentData.model_json_schema(mode="serialization")
    return _strip_titles(schema)


@lru_cache(maxsize=1)
def anthropic_tool_definition() -> dict[str, Any]:
    """Anthropic ``tools=[...]`` entry with ``input_schema`` ready to use."""
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "input_schema": fiscal_document_tool_schema(),
    }
