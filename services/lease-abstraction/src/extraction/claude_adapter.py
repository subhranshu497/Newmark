"""LLM extraction adapter — Anthropic Claude, primary provider (T014, research.md).

Reads OCR'd lease text and returns the five in-scope fields (FR-002) each
with its own confidence score (FR-003), independent of Textract's
OCR-level confidence. Wrapped by the extraction circuit breaker (T008).

Uses Claude's tool-use (function calling) rather than asking for bare JSON
in the response text: the model's tool `input` is already a parsed dict
matching `anthropic_tool_schema()` (src/extraction/field_schemas.py), so
there's no free-text JSON to parse — no markdown code-fence stripping, no
guessing which content block is the answer. Each field's value is then
validated against its own field_type's pydantic schema (`validate_field_value`)
so `ExtractedFieldResult.value` has the same shape regardless of what the
model actually returned, matching the OpenAI failover path's output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import anthropic
from pydantic import ValidationError

from src.config import get_settings
from src.extraction.field_schemas import (
    FIELD_EXTRACTION_INSTRUCTIONS,
    anthropic_tool_schema,
    validate_field_value,
)
from src.models.enums import FieldType
from src.queue.circuit_breaker import BreakerOpenError, call_with_breaker, extraction_breaker

logger = logging.getLogger(__name__)

TOOL_NAME = "record_lease_fields"

EXTRACTION_SYSTEM_PROMPT = (
    "You are extracting structured lease terms from OCR'd commercial lease text. "
    f"Use the {TOOL_NAME} tool to report them. " + FIELD_EXTRACTION_INSTRUCTIONS
)


class ExtractionProviderError(RuntimeError):
    """Raised when the extraction call itself fails (network, rate limit, bad response)."""


@dataclass(frozen=True)
class ExtractedFieldResult:
    field_type: FieldType
    value: dict[str, Any]
    confidence: float
    source_location: dict[str, Any] | None
    model_version: str


class ClaudeExtractionAdapter:
    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        settings = get_settings()
        self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    def extract_fields(self, ocr_text: str) -> list[ExtractedFieldResult]:
        try:
            return call_with_breaker(extraction_breaker, lambda: self._call_claude(ocr_text))
        except BreakerOpenError as exc:
            raise ExtractionProviderError("extraction circuit breaker is open") from exc

    def _call_claude(self, ocr_text: str) -> list[ExtractedFieldResult]:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=EXTRACTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": ocr_text}],
                tools=[
                    {
                        "name": TOOL_NAME,
                        "description": "Record the lease fields found in the text.",
                        "input_schema": anthropic_tool_schema(),
                    }
                ],
                tool_choice={"type": "tool", "name": TOOL_NAME},
            )
            # Don't assume content[0] is the answer — some models (e.g.
            # extended-thinking-capable ones) prepend a ThinkingBlock first.
            tool_uses = [
                b for b in response.content if b.type == "tool_use" and b.name == TOOL_NAME
            ]
            if not tool_uses:
                raise ExtractionProviderError("Claude response contained no tool_use block")
            items = tool_uses[0].input.get("fields", [])
        except Exception as exc:  # noqa: BLE001
            raise ExtractionProviderError(f"Claude extraction call failed: {exc}") from exc

        results = []
        for item in items:
            field_type = FieldType(item["field_type"])
            raw_value = item.get(field_type.value)
            if raw_value is None:
                continue  # tool schema allows the model to omit an inconsistent field
            try:
                value = validate_field_value(field_type, raw_value)
            except ValidationError:
                logger.warning(
                    "Claude returned a %s value that failed schema validation; dropping it",
                    field_type.value,
                )
                continue
            results.append(
                ExtractedFieldResult(
                    field_type=field_type,
                    value=value,
                    confidence=float(item["confidence"]),
                    source_location=item.get("source_location"),
                    model_version=self._model,
                )
            )
        return results
