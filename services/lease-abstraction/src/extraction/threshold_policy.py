"""Confidence-threshold policy (T016, FR-004).

Decides auto-populate vs. review-queue per extracted field. Thresholds are
read from config (src/config.py) per field type, defaulting to a
conservative placeholder (DEFAULT_CONFIDENCE_THRESHOLD) until a labeled
evaluation set exists to calibrate real values (Clarifications session).
Nothing here hardcodes a final threshold number — recalibration is a
config change, not a code change.
"""

from __future__ import annotations

from src.config import Settings, get_settings
from src.extraction.claude_adapter import ExtractedFieldResult


def should_auto_populate(result: ExtractedFieldResult, settings: Settings | None = None) -> bool:
    """True if this field's confidence meets its (per-field-type) threshold."""
    settings = settings or get_settings()
    threshold = settings.confidence_threshold_for(result.field_type)
    return result.confidence >= threshold
