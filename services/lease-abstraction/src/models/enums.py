"""Shared enums for the lease-abstraction data model (data-model.md)."""

from __future__ import annotations

import enum


class OcrStatus(enum.StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    EXCLUDED_LOW_QUALITY = "EXCLUDED_LOW_QUALITY"


class RunType(enum.StrEnum):
    LIVE = "LIVE"
    BACKFILL = "BACKFILL"
    REPROCESS = "REPROCESS"


class RunStatus(enum.StrEnum):
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class FieldType(enum.StrEnum):
    BASE_RENT = "BASE_RENT"
    ESCALATION_SCHEDULE = "ESCALATION_SCHEDULE"
    FREE_RENT_PERIOD = "FREE_RENT_PERIOD"
    TI_ALLOWANCE = "TI_ALLOWANCE"
    TERM = "TERM"


class VerificationStatus(enum.StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    OVERRIDDEN = "OVERRIDDEN"


class ReviewQueueStatus(enum.StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
