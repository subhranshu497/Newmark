"""Holdout-set accuracy computation (T036, FR-015, User Story 3).

Compares extracted values against a labeled holdout set and persists an
AccuracyMetricSnapshot per field type / model version. The holdout set
itself (README §7's "labeled evaluation set that does not yet exist") is
supplied by the caller — building that dataset is an operational
prerequisite tracked in spec.md's Assumptions, not something this job
creates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.accuracy_metric import AccuracyMetricSnapshot
from src.models.enums import FieldType
from src.models.extracted_field import ExtractedField
from src.monitoring.drift_alerts import DRIFT_MARGIN


@dataclass(frozen=True)
class HoldoutSample:
    lease_document_id: uuid.UUID
    field_type: FieldType
    expected_value: dict[str, Any]


async def compute_accuracy(
    session: AsyncSession,
    holdout_samples: list[HoldoutSample],
    model_version: str,
    baseline_accuracy_by_field: dict[FieldType, float],
) -> list[AccuracyMetricSnapshot]:
    """Compute and persist one AccuracyMetricSnapshot per field type present in the holdout set."""
    by_field: dict[FieldType, list[HoldoutSample]] = {}
    for sample in holdout_samples:
        by_field.setdefault(sample.field_type, []).append(sample)

    snapshots: list[AccuracyMetricSnapshot] = []
    for field_type, samples in by_field.items():
        correct = 0
        for sample in samples:
            result = await session.execute(
                select(ExtractedField).where(
                    ExtractedField.lease_document_id == sample.lease_document_id,
                    ExtractedField.field_type == field_type,
                )
            )
            field = result.scalars().first()
            if field is not None and field.extracted_value == sample.expected_value:
                correct += 1

        measured_accuracy = correct / len(samples) if samples else 0.0
        baseline = baseline_accuracy_by_field.get(field_type, measured_accuracy)

        snapshot = AccuracyMetricSnapshot(
            id=uuid.uuid4(),
            field_type=field_type,
            model_version=model_version,
            measured_accuracy=measured_accuracy,
            baseline_accuracy=baseline,
            sample_size=len(samples),
            drift_flag=(baseline - measured_accuracy) > DRIFT_MARGIN,
            measured_at=datetime.now(UTC),
        )
        session.add(snapshot)
        snapshots.append(snapshot)

    return snapshots
