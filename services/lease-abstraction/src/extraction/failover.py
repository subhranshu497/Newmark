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

import openai
from pydantic import ValidationError

from src.config import get_settings
from src.extraction.claude_adapter import (
    ClaudeExtractionAdapter,
    ExtractedFieldResult,
    ExtractionProviderError,
)
from src.extraction.field_schemas import (
    FIELD_EXTRACTION_INSTRUCTIONS,
    openai_json_schema,
    validate_field_value,
)
from src.models.enums import FieldType

logger = logging.getLogger(__name__)

OPENAI_SYSTEM_PROMPT = (
    "You are extracting structured lease terms from OCR'd commercial lease text. "
    "Respond with JSON matching the provided schema. " + FIELD_EXTRACTION_INSTRUCTIONS
)


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
                    {"role": "system", "content": OPENAI_SYSTEM_PROMPT},
                    {"role": "user", "content": ocr_text},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "record_lease_fields",
                        "schema": openai_json_schema(),
                        "strict": True,
                    },
                },
            )
            items = json.loads(response.choices[0].message.content).get("fields", [])
        except Exception as exc:  # noqa: BLE001
            raise ExtractionProviderError(f"OpenAI extraction call failed: {exc}") from exc

        results = []
        for item in items:
            field_type = FieldType(item["field_type"])
            raw_value = item.get(field_type.value)
            if raw_value is None:
                continue  # schema allows the model to null out an inconsistent field
            try:
                value = validate_field_value(field_type, raw_value)
            except ValidationError:
                logger.warning(
                    "OpenAI returned a %s value that failed schema validation; dropping it",
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
