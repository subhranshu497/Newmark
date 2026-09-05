"""Integration tests for quickstart.md Scenarios 2 and 3 (T023).

Scenario 2: a low-confidence field routes to the review queue; resolving
it overrides the field; a subsequent reprocess run leaves the resolved
field and does not recreate a queue item for it (FR-008 guard, T029).

Scenario 3: a caller outside the document's allowed teams cannot see or
resolve the resulting review-queue item (FR-018).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from src.consumers.document_uploaded_consumer import DocumentUploadedConsumer
from src.extraction.claude_adapter import ExtractedFieldResult
from src.models.enums import FieldType, ReviewQueueStatus, VerificationStatus
from src.models.review_queue_item import ReviewQueueItem
from src.ocr.textract_adapter import OcrResult


class _FakeOcrAdapter:
    def extract_text(self, s3_bucket: str, s3_key: str) -> OcrResult:
        return OcrResult(text="ESCALATION: unclear formula...", confidence=0.95)


class _FakeLowConfidenceExtraction:
    def extract_fields(self, ocr_text: str) -> list[ExtractedFieldResult]:
        return [
            ExtractedFieldResult(
                field_type=FieldType.ESCALATION_SCHEDULE,
                value={"raw": "3% annual, ambiguous"},
                confidence=0.40,  # below the conservative default threshold
                source_location={"page": 3},
                model_version="fake-claude-v1",
            )
        ]


class _NullProducer:
    def publish(self, topic, payload, key=None):
        pass


def _upload_event(team_id: uuid.UUID) -> dict:
    return {
        "documentId": str(uuid.uuid4()),
        "dealId": str(uuid.uuid4()),
        "teamId": str(team_id),
        "allowedTeams": [str(team_id)],
        "s3Key": "lease-bucket/leases/ambiguous-scan.pdf",
        "sha256": "cafebabe",
        "contentType": "application/pdf",
        "documentType": "LEASE",
    }


@pytest.mark.asyncio
async def test_scenario_2_review_queue_and_reprocess_guard(session, app_client):
    team_id = app_client.default_principal.team_id
    consumer = DocumentUploadedConsumer(
        ocr_adapter=_FakeOcrAdapter(),
        extraction_adapter=_FakeLowConfidenceExtraction(),
        producer=_NullProducer(),
    )
    event = _upload_event(team_id)
    await consumer.handle(session, event)
    await session.commit()

    items = (await session.execute(select(ReviewQueueItem))).scalars().all()
    assert len(items) == 1
    item = items[0]
    assert item.status == ReviewQueueStatus.PENDING

    resp = await app_client.get("/v1/review-queue", params={"teamId": str(team_id)})
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resolve_resp = await app_client.post(
        f"/v1/review-queue/{item.id}/resolve",
        json={"value": {"raw": "3% annual, confirmed by analyst"}},
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "RESOLVED"

    # Reprocess: the resolved field must be left untouched (FR-008) and no
    # second queue item created for the same field type.
    await consumer.reprocess(session, item.lease_document_id)
    await session.commit()

    items_after = (await session.execute(select(ReviewQueueItem))).scalars().all()
    assert len(items_after) == 1  # no new item created

    from src.models.extracted_field import ExtractedField

    fields = (
        (
            await session.execute(
                select(ExtractedField).where(
                    ExtractedField.lease_document_id == item.lease_document_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(fields) == 1
    assert fields[0].verification_status == VerificationStatus.OVERRIDDEN
    assert fields[0].extracted_value == {"raw": "3% annual, confirmed by analyst"}


@pytest.mark.asyncio
async def test_scenario_3_information_barrier_on_review_queue(session, app_client):
    other_team = uuid.uuid4()  # not the caller's team
    consumer = DocumentUploadedConsumer(
        ocr_adapter=_FakeOcrAdapter(),
        extraction_adapter=_FakeLowConfidenceExtraction(),
        producer=_NullProducer(),
    )
    await consumer.handle(session, _upload_event(other_team))
    await session.commit()

    # The default caller (a different team) must not see this team's queue.
    resp = await app_client.get("/v1/review-queue", params={"teamId": str(other_team)})
    assert resp.status_code == 403

    items = (await session.execute(select(ReviewQueueItem))).scalars().all()
    item = items[0]
    resolve_resp = await app_client.post(
        f"/v1/review-queue/{item.id}/resolve", json={"value": {"raw": "should be blocked"}}
    )
    assert resolve_resp.status_code == 403
