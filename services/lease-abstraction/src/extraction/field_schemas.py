"""Per-field-type output schema for the five in-scope lease terms (FR-002).

Both extraction providers (src/extraction/claude_adapter.py,
src/extraction/failover.py's OpenAiExtractionAdapter) and the demo seed
endpoint (src/api/demo_seed.py) validate/build `ExtractedField.extracted_value`
through these models, so the API's `extracted_value` shape for a given
field_type is the same no matter which provider produced it — the UI
(lease-parser-ui) renders off of this shape rather than an unstructured blob.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.models.enums import FieldType


class BaseRentValue(BaseModel):
    amount: float
    unit: Literal[
        "USD_PER_SQFT_PER_YEAR", "USD_PER_SQFT_PER_MONTH", "USD_PER_MONTH", "USD_PER_YEAR"
    ]


class EscalationScheduleValue(BaseModel):
    percent: float
    frequency: Literal["ANNUAL", "BIENNIAL", "OTHER"]


class FreeRentPeriodValue(BaseModel):
    months: float


class TiAllowanceValue(BaseModel):
    amount: float
    unit: Literal["USD_PER_SQFT", "USD_TOTAL"]


class TermValue(BaseModel):
    years: float
    commencement_date: str | None = None
    expiration_date: str | None = None


# Shared between claude_adapter.py and failover.py's OpenAiExtractionAdapter —
# the semantics are identical across providers, only the surrounding framing
# ("use this tool" vs. "respond with JSON matching this schema") differs.
FIELD_EXTRACTION_INSTRUCTIONS = (
    "Extract exactly the fields present in the text from this set: BASE_RENT, "
    "ESCALATION_SCHEDULE, FREE_RENT_PERIOD, TI_ALLOWANCE, TERM. Omit a field entirely if it "
    "isn't present in the text. For each field you do report, set `confidence` (0-1, your "
    "certainty in the extraction) and `source_location` (a short quote or page reference you "
    "drew it from), and fill in only the one nested value object that matches that field's own "
    "field_type — leave the other four nested value objects null/absent."
)

FIELD_VALUE_SCHEMAS: dict[FieldType, type[BaseModel]] = {
    FieldType.BASE_RENT: BaseRentValue,
    FieldType.ESCALATION_SCHEDULE: EscalationScheduleValue,
    FieldType.FREE_RENT_PERIOD: FreeRentPeriodValue,
    FieldType.TI_ALLOWANCE: TiAllowanceValue,
    FieldType.TERM: TermValue,
}


def validate_field_value(field_type: FieldType, raw_value: dict) -> dict:
    """Validate/coerce a provider's raw value against field_type's schema,
    returning the canonical dict form to store in ExtractedField.extracted_value.
    Raises pydantic.ValidationError if the provider's output doesn't fit —
    callers should treat that field as unusable rather than persist it as-is,
    since an unvalidated shape is exactly what this schema exists to prevent.
    """
    schema = FIELD_VALUE_SCHEMAS[field_type]
    return schema.model_validate(raw_value).model_dump()


def anthropic_tool_schema() -> dict:
    """Build the Anthropic tool `input_schema` for structured extraction: one
    array of field objects, each carrying only the nested value object that
    matches its own field_type (the model leaves the other four null/absent).
    """
    value_properties = {
        field_type.value: schema.model_json_schema()
        for field_type, schema in FIELD_VALUE_SCHEMAS.items()
    }
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_type": {
                            "type": "string",
                            "enum": [ft.value for ft in FIELD_VALUE_SCHEMAS],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Model's confidence in this extraction, 0-1.",
                        },
                        "source_location": {
                            "type": "string",
                            "description": "Short quote or page reference this was drawn from.",
                        },
                        **value_properties,
                    },
                    "required": ["field_type", "confidence"],
                },
            }
        },
        "required": ["fields"],
    }


def openai_json_schema() -> dict:
    """Same shape as anthropic_tool_schema(), wrapped for OpenAI's Structured
    Outputs (response_format={"type": "json_schema", ...}), which requires
    the root to be an object (not a bare array) and `additionalProperties:
    false` plus every property listed in `required` on every object.
    """
    # OpenAI strict mode requires additionalProperties: false on every object
    # schema, including nested ones — pydantic's model_json_schema() doesn't
    # set that itself, so it's added here rather than on the models (which
    # also feed anthropic_tool_schema(), where this key is irrelevant noise).
    value_properties = {
        field_type.value: {**schema.model_json_schema(), "additionalProperties": False}
        for field_type, schema in FIELD_VALUE_SCHEMAS.items()
    }
    item_properties = {
        "field_type": {"type": "string", "enum": [ft.value for ft in FIELD_VALUE_SCHEMAS]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "source_location": {"type": ["string", "null"]},
        **{
            name: {"anyOf": [schema, {"type": "null"}]}
            for name, schema in value_properties.items()
        },
    }
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": item_properties,
                    "required": list(item_properties),
                    "additionalProperties": False,
                },
            }
        },
        "required": ["fields"],
        "additionalProperties": False,
    }
