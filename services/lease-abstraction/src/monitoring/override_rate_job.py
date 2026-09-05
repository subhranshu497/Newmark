"""Override-rate aggregation (T037, FR-016, User Story 3).

Aggregates ExtractedField verification outcomes over a period into an
OverrideRateMetric per field type — the leading indicator of model
degradation called out in Constitution VI.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enums import FieldType, VerificationStatus
from src.models.extracted_field import ExtractedField
from src.models.override_rate_metric import OverrideRateMetric


async def compute_override_rate(
    session: AsyncSession, field_type: FieldType, period_start: datetime, period_end: datetime
) -> OverrideRateMetric:
    result = await session.execute(
        select(ExtractedField).where(
            ExtractedField.field_type == field_type,
            ExtractedField.verification_status.in_(
                [VerificationStatus.VERIFIED, VerificationStatus.OVERRIDDEN]
            ),
            ExtractedField.verified_at >= period_start,
            ExtractedField.verified_at < period_end,
        )
    )
    fields = result.scalars().all()

    total = len(fields)
    overridden = sum(1 for f in fields if f.verification_status == VerificationStatus.OVERRIDDEN)
    rate = overridden / total if total else 0.0

    metric = OverrideRateMetric(
        id=uuid.uuid4(),
        field_type=field_type,
        period_start=period_start,
        period_end=period_end,
        override_count=overridden,
        total_verified_count=total,
        rate=rate,
    )
    session.add(metric)
    return metric
