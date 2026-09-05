"""LLM extraction adapter — Anthropic Claude, primary provider (T014, research.md).

Reads OCR'd lease text and returns the five in-scope fields (FR-002) each
with its own confidence score (FR-003), independent of Textract's
OCR-level confidence. Wrapped by the extraction circuit breaker (T008).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import anthropic

from src.config import get_settings
from src.models.enums import FieldType
from src.queue.circuit_breaker import BreakerOpenError, call_with_breaker, extraction_breaker

EXTRACTION_SYSTEM_PROMPT = """You are extracting structured lease terms from OCR'd commercial \
lease text. Extract exactly these five fields when present in the text: BASE_RENT, \
ESCALATION_SCHEDULE, FREE_RENT_PERIOD, TI_ALLOWANCE, TERM. For each field, return its value, a \
confidence score between 0 and 1 reflecting your certainty in the extraction, and the \
approximate source location (a short quote or page reference) you drew it from. Respond only \
with a JSON array of objects: [{"field_type": ..., "value": ..., "confidence": ..., \
"source_location": ...}, ...]. Omit a field entirely if it is not present in the text."""


class ExtractionProviderError(RuntimeError):
    """Raised when the extraction call itself fails (network, rate limit, bad response)."""


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fence(text: str) -> str:
    """Some models wrap JSON output in a ```json ... ``` fence despite the
    prompt asking for a bare array — strip it before parsing rather than
    tightening the prompt further, since this varies by model and isn't
    reliably preventable from the prompt alone."""
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


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
            )
            # Don't assume content[0] is the text block — some models (e.g.
            # extended-thinking-capable ones) prepend a ThinkingBlock first.
            text_blocks = [block.text for block in response.content if block.type == "text"]
            if not text_blocks:
                raise ExtractionProviderError("Claude response contained no text block")
            parsed = json.loads(_strip_code_fence("".join(text_blocks)))
        except Exception as exc:  # noqa: BLE001
            raise ExtractionProviderError(f"Claude extraction call failed: {exc}") from exc

        results = []
        for item in parsed:
            value = item["value"] if isinstance(item["value"], dict) else {"raw": item["value"]}
            results.append(
                ExtractedFieldResult(
                    field_type=FieldType(item["field_type"]),
                    value=value,
                    confidence=float(item["confidence"]),
                    source_location=item.get("source_location"),
                    model_version=self._model,
                )
            )
        return results
