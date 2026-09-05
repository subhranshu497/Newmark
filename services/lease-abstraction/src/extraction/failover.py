"""Secondary-provider failover for extraction (T015, FR-012, research.md).

Moved into the MVP phase per /speckit-analyze finding A2: Constitution
Principle IV lists "model provider outage -> fail over to secondary
provider" as a required degradation behavior, so the MVP must attempt it
rather than deferring straight to manual mode.

OpenAI is used as the secondary provider specifically because it is a
genuinely independent vendor from the primary (Anthropic) — a single
vendor's outage cannot take out both paths (research.md).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import openai

from src.config import get_settings
from src.extraction.claude_adapter import (
    EXTRACTION_SYSTEM_PROMPT,
    ClaudeExtractionAdapter,
    ExtractedFieldResult,
    ExtractionProviderError,
)
from src.models.enums import FieldType

logger = logging.getLogger(__name__)


class ExtractionUnavailableError(RuntimeError):
    """Raised only when BOTH the primary and secondary providers have failed.

    Callers (the document_uploaded_consumer) catch this and fall back to
    full manual mode (FR-012's final degradation tier) rather than
    auto-populating or queuing a review item with no value.
    """


class OpenAiExtractionAdapter:
    """Secondary provider — same ExtractedFieldResult contract as Claude's adapter."""

    def __init__(self, client: openai.OpenAI | None = None) -> None:
        settings = get_settings()
        self._client = client or openai.OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def extract_fields(self, ocr_text: str) -> list[ExtractedFieldResult]:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": ocr_text},
                ],
                response_format={"type": "json_object"},
            )
            parsed: list[dict[str, Any]] = json.loads(response.choices[0].message.content)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionProviderError(f"OpenAI extraction call failed: {exc}") from exc

        return [
            ExtractedFieldResult(
                field_type=FieldType(item["field_type"]),
                value=item["value"] if isinstance(item["value"], dict) else {"raw": item["value"]},
                confidence=float(item["confidence"]),
                source_location=item.get("source_location"),
                model_version=self._model,
            )
            for item in parsed
        ]


class FailoverExtractionAdapter:
    """Tries the primary provider, falls over to the secondary, else raises.

    This is the adapter the document_uploaded_consumer should depend on
    directly, rather than either provider adapter individually.
    """

    def __init__(
        self,
        primary: ClaudeExtractionAdapter | None = None,
        secondary: OpenAiExtractionAdapter | None = None,
    ) -> None:
        self._primary = primary or ClaudeExtractionAdapter()
        self._secondary = secondary or OpenAiExtractionAdapter()

    def extract_fields(self, ocr_text: str) -> list[ExtractedFieldResult]:
        try:
            return self._primary.extract_fields(ocr_text)
        except ExtractionProviderError:
            logger.warning("Primary extraction provider failed; failing over to secondary")
        try:
            return self._secondary.extract_fields(ocr_text)
        except ExtractionProviderError as exc:
            raise ExtractionUnavailableError(
                "both primary and secondary extraction providers failed"
            ) from exc
