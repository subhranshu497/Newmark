"""Environment/config management (T009).

Holds OCR/LLM provider credentials and the re-calibratable, per-field-type
confidence and scan-quality thresholds required by FR-004 and FR-013. These
thresholds are read from environment/config at process start, not hardcoded,
so they can be recalibrated without a code deploy once a labeled evaluation
set exists (per the Clarifications session in spec.md).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.models.enums import FieldType

# Conservative placeholder: biased toward routing to review over risking a
# wrong auto-populated value, per the Clarifications session (FR-004).
DEFAULT_CONFIDENCE_THRESHOLD = 0.92

# Placeholder OCR scan-quality floor, taken from the OCR engine's own
# confidence signal until an empirical floor is established (FR-013).
DEFAULT_SCAN_QUALITY_FLOOR = 0.60


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEASE_ABSTRACTION_", env_file=".env")

    database_url: str = "postgresql+asyncpg://localhost/lease_abstraction"

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "lease-abstraction-intake"
    kafka_backfill_consumer_group: str = "lease-abstraction-backfill"
    topic_document_uploaded: str = "document.uploaded"
    topic_extraction_completed: str = "lease.extraction.completed"
    topic_dead_letter: str = "lease.extraction.dead-letter"

    aws_region: str = "us-east-1"

    anthropic_api_key: str = ""
    #anthropic_model: str = "claude-sonnet-5"
    #anthropic_model: str = "claude-3-5-haiku-20241022"
    anthropic_model: str = "claude-opus-4-5"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    circuit_breaker_fail_max: int = 5
    circuit_breaker_reset_timeout_seconds: int = 60

    # Per-field-type confidence thresholds (FR-004). Falls back to
    # DEFAULT_CONFIDENCE_THRESHOLD for any field type not explicitly listed.
    confidence_thresholds: dict[str, float] = Field(default_factory=dict)

    scan_quality_floor: float = DEFAULT_SCAN_QUALITY_FLOOR

    backfill_rate_limit_per_minute: int = 30

    # Mounts the seed endpoint (src/api/demo_seed.py) and opens CORS for the
    # standalone lease-parser-ui frontend. Off by default so a real deployment
    # never exposes a data-seeding endpoint or relaxes CORS.
    enable_demo_ui: bool = False

    def confidence_threshold_for(self, field_type: FieldType) -> float:
        return self.confidence_thresholds.get(field_type.value, DEFAULT_CONFIDENCE_THRESHOLD)


@lru_cache
def get_settings() -> Settings:
    return Settings()
