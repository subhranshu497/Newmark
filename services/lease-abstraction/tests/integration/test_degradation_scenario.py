"""Integration test for quickstart.md Scenario 4 (T045): degradation.

OCR outage -> circuit breaker opens -> document stays queued, not lost,
and no core-service call is blocked -> OCR recovers -> processing resumes.
Uses the real TextractAdapter + circuit breaker (T008/T013), with a fake
boto3 client so no live AWS call is made.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from src.consumers.document_uploaded_consumer import DocumentUploadedConsumer
from src.extraction.claude_adapter import ExtractedFieldResult
from src.models.enums import FieldType, OcrStatus, RunStatus
from src.models.lease_document import ExtractionRun, LeaseDocument
from src.ocr.textract_adapter import OcrUnavailableError, TextractAdapter
from src.queue.circuit_breaker import ocr_breaker


class _FakeExtractionAdapter:
    """Avoids real Anthropic/OpenAI calls — this test is only exercising OCR degradation."""

    def extract_fields(self, ocr_text: str) -> list[ExtractedFieldResult]:
        return [
            ExtractedFieldResult(
                field_type=FieldType.BASE_RENT,
                value={"amount": 10.0},
                confidence=0.97,
                source_location=None,
                model_version="fake-v1",
            )
        ]


class _NullProducer:
    def publish(self, topic, payload, key=None):
        pass


class _FlakyTextractClient:
    """Fails every call until `recovered` is set, mimicking a provider outage."""

    def __init__(self) -> None:
        self.recovered = False
        self.call_count = 0

    def analyze_document(self, **kwargs):
        self.call_count += 1
        if not self.recovered:
            raise RuntimeError("simulated Textract outage")
        return {
            "Blocks": [
                {"BlockType": "LINE", "Text": "BASE RENT: $10/sqft", "Confidence": 99.0},
            ]
        }


@pytest.fixture(autouse=True)
def _reset_shared_ocr_breaker():
    """The OCR circuit breaker (T008) is a process-wide singleton; reset both
    its state and its configured fail_max around this test so mutating it
    here can't leak into other tests."""
    original_fail_max = ocr_breaker.fail_max
    yield
    ocr_breaker.close()
    ocr_breaker.fail_max = original_fail_max


@pytest.mark.asyncio
async def test_scenario_4_ocr_outage_then_recovery(session):
    client = _FlakyTextractClient()
    adapter = TextractAdapter(client=client)
    ocr_breaker.fail_max = 2  # open quickly for the test rather than waiting on the real default

    consumer = DocumentUploadedConsumer(
        ocr_adapter=adapter, extraction_adapter=_FakeExtractionAdapter(), producer=_NullProducer()
    )

    event = {
        "documentId": str(uuid.uuid4()),
        "dealId": str(uuid.uuid4()),
        "teamId": str(uuid.uuid4()),
        "allowedTeams": [],
        "s3Key": "lease-bucket/leases/during-outage.pdf",
        "sha256": "outage-test",
        "contentType": "application/pdf",
        "documentType": "LEASE",
    }
    event["allowedTeams"] = [event["teamId"]]

    # During the outage: OcrUnavailableError propagates (so the Kafka-level
    # RetryingConsumer can retry/dead-letter it) rather than being swallowed,
    # and the document is left in a non-lost, re-processable state.
    with pytest.raises(OcrUnavailableError):
        await consumer.handle(session, event)
    await session.commit()

    documents = (await session.execute(select(LeaseDocument))).scalars().all()
    assert len(documents) == 1
    assert documents[0].ocr_status == OcrStatus.PROCESSING  # never silently marked COMPLETE

    runs = (await session.execute(select(ExtractionRun))).scalars().all()
    assert runs[0].status == RunStatus.FAILED

    # Recovery: OCR comes back; a fresh attempt against the SAME document
    # (simulating the retry the Kafka consumer would perform) succeeds.
    client.recovered = True
    ocr_breaker.close()  # simulate the breaker's reset-timeout elapsing
    await consumer.reprocess(session, documents[0].id)
    await session.commit()

    await session.refresh(documents[0])
    assert documents[0].ocr_status == OcrStatus.COMPLETE
