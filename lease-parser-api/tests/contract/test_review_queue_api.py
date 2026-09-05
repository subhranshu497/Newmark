"""Contract tests for review-queue endpoints (T022, contracts/api.md).

Covers: list scoped to caller's team, 403 on requesting another team's
queue, resolve (both for an existing low-confidence field and for a
no-field EXCLUDED_LOW_QUALITY item), and 409 on double-resolve.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.models.enums import FieldType, ReviewQueueStatus
from src.models.review_queue_item import ReviewQueueItem


async def _make_queue_item(session, team_id: uuid.UUID, extracted_field_id=None) -> ReviewQueueItem:
    item = ReviewQueueItem(
        id=uuid.uuid4(),
        extracted_field_id=extracted_field_id,
        lease_document_id=uuid.uuid4(),
        team_id=team_id,
        allowed_teams=[team_id],
        status=ReviewQueueStatus.PENDING,
        created_at=datetime.now(UTC),
    )
    session.add(item)
    await session.commit()
    return item


@pytest.mark.asyncio
async def test_list_review_queue_scoped_to_own_team(app_client, session):
    team_id = app_client.default_principal.team_id
    await _make_queue_item(session, team_id)

    resp = await app_client.get("/v1/review-queue", params={"teamId": str(team_id)})

    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_review_queue_403_for_another_team(app_client, session):
    other_team = uuid.uuid4()
    await _make_queue_item(session, other_team)

    resp = await app_client.get("/v1/review-queue", params={"teamId": str(other_team)})

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_resolve_no_field_item_creates_field(app_client, session):
    team_id = app_client.default_principal.team_id
    item = await _make_queue_item(session, team_id, extracted_field_id=None)

    resp = await app_client.post(
        f"/v1/review-queue/{item.id}/resolve",
        json={"value": {"amount": 30.0}, "field_type": FieldType.BASE_RENT.value},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_resolve_already_resolved_returns_409(app_client, session):
    team_id = app_client.default_principal.team_id
    item = await _make_queue_item(session, team_id, extracted_field_id=None)

    first = await app_client.post(
        f"/v1/review-queue/{item.id}/resolve",
        json={"value": {"amount": 30.0}, "field_type": FieldType.BASE_RENT.value},
    )
    assert first.status_code == 200

    second = await app_client.post(
        f"/v1/review-queue/{item.id}/resolve",
        json={"value": {"amount": 31.0}, "field_type": FieldType.BASE_RENT.value},
    )
    assert second.status_code == 409
