"""Integration test for quickstart.md Scenario 1 (T011).

Upload -> OCR -> extraction -> auto-populate -> analyst confirms ->
re-verify rejected. OCR and extraction providers are faked (no live
Textract/Claude/OpenAI in this environment); everything else — the
consumer's orchestration logic, the DB, and the API — is exercised for
real.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from src.consumers.document_uploaded_consumer import DocumentUploadedConsumer
from src.extraction.claude_adapter import ExtractedFieldResult
from src.models.enums import FieldType, OcrStatus, VerificationStatus
from src.models.extracted_field import ExtractedField
from src.models.lease_document import LeaseDocument
from src.ocr.textract_adapter import OcrResult


class _FakeOcrAdapter:
    def extract_text(self, s3_bucket: str, s3_key: str) -> OcrResult:
        return OcrResult(text="BASE RENT: $42.50/sqft/yr...", confidence=0.98)


class _FakeExtractionAdapter:
    def extract_fields(self, ocr_text: str) -> list[ExtractedFieldResult]:
        return [
            ExtractedFieldResult(
                field_type=FieldType.BASE_RENT,
                value={"amount": 42.5, "unit": "USD_PER_SQFT_PER_YEAR"},
                confidence=0.97,  # above the conservative default threshold
                source_location={"page": 1},
                model_version="fake-claude-v1",
            )
        ]


class _NullProducer:
    def publish(self, topic, payload, key=None):
        pass


@pytest.mark.asyncio
async def test_scenario_1_auto_populate_and_confirm(session, app_client):
    team_id = app_client.default_principal.team_id
    event = {
        "documentId": str(uuid.uuid4()),
        "dealId": str(uuid.uuid4()),
        "teamId": str(team_id),
        "allowedTeams": [str(team_id)],
        "s3Key": "lease-bucket/leases/clear-scan.pdf",
        "sha256": "deadbeef",
        "contentType": "application/pdf",
        "documentType": "LEASE",
    }

    consumer = DocumentUploadedConsumer(
        ocr_adapter=_FakeOcrAdapter(),
        extraction_adapter=_FakeExtractionAdapter(),
        producer=_NullProducer(),
    )
    await consumer.handle(session, event)
    await session.commit()

    documents = (await session.execute(select(LeaseDocument))).scalars().all()
    assert len(documents) == 1
    document = documents[0]
    assert document.ocr_status == OcrStatus.COMPLETE

    field_stmt = select(ExtractedField).where(ExtractedField.lease_document_id == document.id)
    fields = (await session.execute(field_stmt)).scalars().all()
    assert len(fields) == 1
    field = fields[0]
    assert field.field_type == FieldType.BASE_RENT
    # Populated, not yet confirmed.
    assert field.verification_status == VerificationStatus.UNVERIFIED

    # Analyst confirms the auto-populated value as-is via the API.
    resp = await app_client.post(
        f"/v1/lease-documents/{document.id}/extracted-fields/{field.id}/verify", json={}
    )
    assert resp.status_code == 200
    assert resp.json()["verification_status"] == "VERIFIED"

    # Re-verifying an already-verified field is rejected (FR-008).
    resp2 = await app_client.post(
        f"/v1/lease-documents/{document.id}/extracted-fields/{field.id}/verify",
        json={"value": {"amount": 1.0}},
    )
    assert resp2.status_code == 409
