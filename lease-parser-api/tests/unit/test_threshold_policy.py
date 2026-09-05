"""Unit tests for the confidence-threshold policy (T048, FR-004)."""

from __future__ import annotations

from src.config import Settings
from src.extraction.claude_adapter import ExtractedFieldResult
from src.extraction.threshold_policy import should_auto_populate
from src.models.enums import FieldType


def _result(confidence: float, field_type: FieldType = FieldType.BASE_RENT) -> ExtractedFieldResult:
    return ExtractedFieldResult(
        field_type=field_type,
        value={"amount": 1.0},
        confidence=confidence,
        source_location=None,
        model_version="test",
    )


def test_above_default_threshold_auto_populates():
    settings = Settings(confidence_thresholds={})
    assert should_auto_populate(_result(0.99), settings) is True


def test_below_default_threshold_does_not_auto_populate():
    settings = Settings(confidence_thresholds={})
    assert should_auto_populate(_result(0.10), settings) is False


def test_per_field_type_threshold_overrides_default():
    # TERM is given a lenient threshold; BASE_RENT keeps the conservative default.
    settings = Settings(confidence_thresholds={"TERM": 0.5})

    assert should_auto_populate(_result(0.6, FieldType.TERM), settings) is True
    assert should_auto_populate(_result(0.6, FieldType.BASE_RENT), settings) is False


def test_recalibration_is_a_config_change_not_a_code_change():
    """FR-004: thresholds must be re-calibratable without a code deploy."""
    lenient = Settings(confidence_thresholds={"BASE_RENT": 0.1})
    strict = Settings(confidence_thresholds={"BASE_RENT": 0.99})

    result = _result(0.5, FieldType.BASE_RENT)
    assert should_auto_populate(result, lenient) is True
    assert should_auto_populate(result, strict) is False
