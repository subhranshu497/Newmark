"""Contract tests for metrics + baseline-measurement endpoints (T031, contracts/api.md)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.models.accuracy_metric import AccuracyMetricSnapshot
from src.models.enums import FieldType
from src.models.override_rate_metric import OverrideRateMetric


@pytest.mark.asyncio
async def test_get_extraction_accuracy_filters_by_field_type(app_client, session):
    session.add(
        AccuracyMetricSnapshot(
            id=uuid.uuid4(),
            field_type=FieldType.BASE_RENT,
            model_version="v1",
            measured_accuracy=0.9,
            baseline_accuracy=0.95,
            sample_size=50,
            drift_flag=True,
            measured_at=datetime.now(UTC),
        )
    )
    session.add(
        AccuracyMetricSnapshot(
            id=uuid.uuid4(),
            field_type=FieldType.TERM,
            model_version="v1",
            measured_accuracy=0.98,
            baseline_accuracy=0.97,
            sample_size=50,
            drift_flag=False,
            measured_at=datetime.now(UTC),
        )
    )
    await session.commit()

    resp = await app_client.get(
        "/v1/metrics/extraction-accuracy", params={"fieldType": FieldType.BASE_RENT.value}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["drift_flag"] is True


@pytest.mark.asyncio
async def test_get_override_rate(app_client, session):
    session.add(
        OverrideRateMetric(
            id=uuid.uuid4(),
            field_type=FieldType.ESCALATION_SCHEDULE,
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
            override_count=3,
            total_verified_count=10,
            rate=0.3,
        )
    )
    await session.commit()

    resp = await app_client.get("/v1/metrics/override-rate")

    assert resp.status_code == 200
    assert resp.json()[0]["rate"] == 0.3


@pytest.mark.asyncio
async def test_record_baseline_measurement(app_client):
    resp = await app_client.post(
        "/v1/baseline-measurements",
        json={
            "sample_lease_ids": [str(uuid.uuid4()) for _ in range(5)],
            "measured_median_minutes": 182.5,
            "method": "manual stopwatch timing on 5 recent leases",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["measured_median_minutes"] == 182.5
