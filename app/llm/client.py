"""Thin wrapper around the Anthropic SDK forcing tool_use JSON output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic, APIError

from app.config import Settings
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.llm.schema import TOOL_NAME, anthropic_tool_definition
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LLMExtractionError(RuntimeError):
    """Raised when Anthropic fails or returns an unparseable response."""


@dataclass
class LLMExtraction:
    """Result of an LLM round-trip."""

    payload: dict[str, Any]
    stop_reason: str | None
    usage: dict[str, Any] | None


class AnthropicExtractor:
    """Wrapper that sends the raw document text + tool schema to Claude."""

    def __init__(self, settings: Settings, client: Anthropic | None = None) -> None:
        self._settings = settings
        if not settings.anthropic_api_key and client is None:
            # Allow instantiation without a key; ``extract`` will raise at call time.
            self._client = None
        else:
            self._client = client or Anthropic(
                api_key=settings.anthropic_api_key,
                timeout=settings.llm_timeout_seconds,
            )

    def extract(self, document_text: str, *, hint_type: str | None = None) -> LLMExtraction:
        """Send ``document_text`` to the LLM and return the parsed tool input."""
        if self._client is None:
            raise LLMExtractionError(
                "ANTHROPIC_API_KEY is not configured; cannot run LLM extraction."
            )
        if not document_text.strip():
            raise LLMExtractionError("Cannot extract: document text is empty")

        try:
            response = self._client.messages.create(
                model=self._settings.llm_model,
                max_tokens=self._settings.llm_max_tokens,
                temperature=self._settings.llm_temperature,
                system=SYSTEM_PROMPT,
                tools=[anthropic_tool_definition()],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[
                    {
                        "role": "user",
                        "content": build_user_prompt(document_text, hint_type=hint_type),
                    }
                ],
            )
        except APIError as exc:  # pragma: no cover - network path
            logger.error("anthropic_api_error", error=str(exc))
            raise LLMExtractionError(f"Anthropic API error: {exc}") from exc

        payload = _extract_tool_payload(response)
        usage = getattr(response, "usage", None)
        usage_dict = (
            {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
            if usage is not None
            else None
        )
        return LLMExtraction(
            payload=payload,
            stop_reason=getattr(response, "stop_reason", None),
            usage=usage_dict,
        )


def _extract_tool_payload(response: Any) -> dict[str, Any]:
    """Walk the response content blocks and return the ``tool_use`` input."""
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == TOOL_NAME:
            return dict(block.input or {})
    raise LLMExtractionError(
        "LLM response did not include the expected tool_use block"
    )
