"""Integration test for accuracy-drift alerting (T032, FR-015, SC-005)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.models.enums import FieldType
from src.models.extracted_field import ExtractedField
from src.models.lease_document import LeaseDocument
from src.monitoring.accuracy_job import HoldoutSample, compute_accuracy
from src.monitoring.drift_alerts import check_for_drift


async def _make_document_with_field(session, correct_value: dict, actual_value: dict):
    document = LeaseDocument(
        id=uuid.uuid4(),
        deal_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        allowed_teams=[],
        s3_key="bucket/key.pdf",
        sha256="x",
        uploaded_at=datetime.now(UTC),
    )
    session.add(document)
    await session.flush()

    field = ExtractedField(
        id=uuid.uuid4(),
        lease_document_id=document.id,
        field_type=FieldType.BASE_RENT,
        extracted_value=actual_value,
        confidence_score=0.9,
        model_version="v1",
    )
    session.add(field)
    await session.commit()
    return document, correct_value


@pytest.mark.asyncio
async def test_drift_detected_when_accuracy_drops_below_baseline(session):
    # 3 samples: 1 correct, 2 wrong -> 33% accuracy, well below a 95% baseline.
    samples = []
    for i in range(3):
        actual = {"amount": 42.5} if i == 0 else {"amount": 999.0}  # only first is "correct"
        document, expected = await _make_document_with_field(
            session, correct_value={"amount": 42.5}, actual_value=actual
        )
        samples.append(
            HoldoutSample(
                lease_document_id=document.id,
                field_type=FieldType.BASE_RENT,
                expected_value=expected,
            )
        )

    snapshots = await compute_accuracy(
        session,
        holdout_samples=samples,
        model_version="v1",
        baseline_accuracy_by_field={FieldType.BASE_RENT: 0.95},
    )
    await session.commit()

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.measured_accuracy == pytest.approx(1 / 3)
    assert snapshot.drift_flag is True

    alerts = check_for_drift(snapshots)
    assert len(alerts) == 1
    assert "BASE_RENT" in str(alerts[0])


@pytest.mark.asyncio
async def test_no_drift_when_accuracy_matches_baseline(session):
    document, expected = await _make_document_with_field(
        session, correct_value={"amount": 42.5}, actual_value={"amount": 42.5}
    )
    samples = [
        HoldoutSample(
            lease_document_id=document.id, field_type=FieldType.BASE_RENT, expected_value=expected
        )
    ]

    snapshots = await compute_accuracy(
        session,
        holdout_samples=samples,
        model_version="v1",
        baseline_accuracy_by_field={FieldType.BASE_RENT: 0.95},
    )

    assert snapshots[0].drift_flag is False
    assert check_for_drift(snapshots) == []
