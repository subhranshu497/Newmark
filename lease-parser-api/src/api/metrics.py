"""Metrics + baseline-measurement endpoints (T039, T040, T041, contracts/api.md).

No information-barrier filtering — this is aggregate operational data, not
deal-scoped (contracts/api.md's explicit note).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.accuracy_metric import AccuracyMetricSnapshot
from src.models.baseline_measurement import BaselineMeasurement
from src.models.enums import FieldType
from src.models.override_rate_metric import OverrideRateMetric

router = APIRouter(prefix="/v1", tags=["metrics"])


class AccuracyMetricOut(BaseModel):
    field_type: str
    model_version: str
    measured_accuracy: float
    baseline_accuracy: float
    sample_size: int
    drift_flag: bool
    model_config = {"from_attributes": True}


class OverrideRateMetricOut(BaseModel):
    field_type: str
    rate: float
    override_count: int
    total_verified_count: int
    model_config = {"from_attributes": True}


class BaselineMeasurementIn(BaseModel):
    sample_lease_ids: list[uuid.UUID]
    measured_median_minutes: float
    method: str


class BaselineMeasurementOut(BaselineMeasurementIn):
    id: uuid.UUID
    measured_at: datetime
    model_config = {"from_attributes": True}


@router.get("/metrics/extraction-accuracy", response_model=list[AccuracyMetricOut])
async def get_extraction_accuracy(
    fieldType: FieldType | None = Query(default=None),
    modelVersion: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[AccuracyMetricSnapshot]:
    stmt = select(AccuracyMetricSnapshot)
    if fieldType is not None:
        stmt = stmt.where(AccuracyMetricSnapshot.field_type == fieldType)
    if modelVersion is not None:
        stmt = stmt.where(AccuracyMetricSnapshot.model_version == modelVersion)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/metrics/override-rate", response_model=list[OverrideRateMetricOut])
async def get_override_rate(
    fieldType: FieldType | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[OverrideRateMetric]:
    stmt = select(OverrideRateMetric)
    if fieldType is not None:
        stmt = stmt.where(OverrideRateMetric.field_type == fieldType)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/baseline-measurements", response_model=BaselineMeasurementOut)
async def record_baseline_measurement(
    body: BaselineMeasurementIn, session: AsyncSession = Depends(get_session)
) -> BaselineMeasurement:
    measurement = BaselineMeasurement(
        id=uuid.uuid4(),
        sample_lease_ids=body.sample_lease_ids,
        measured_median_minutes=body.measured_median_minutes,
        method=body.method,
        measured_at=datetime.now(UTC),
    )
    session.add(measurement)
    await session.commit()
    return measurement
