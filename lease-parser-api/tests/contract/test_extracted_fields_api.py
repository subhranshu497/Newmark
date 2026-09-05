"""Contract tests for extracted-fields endpoints (T010, contracts/api.md).

Covers: GET list, POST verify (confirm-as-is and override), the 409
terminal-state guard (FR-008), and the 403 information-barrier guard
(FR-018).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enums import FieldType, OcrStatus, RunType
from src.models.extracted_field import ExtractedField
from src.models.lease_document import LeaseDocument


async def _make_document(session: AsyncSession, allowed_teams: list[uuid.UUID]) -> LeaseDocument:
    document = LeaseDocument(
        id=uuid.uuid4(),
        deal_id=uuid.uuid4(),
        team_id=allowed_teams[0],
        allowed_teams=allowed_teams,
        s3_key="bucket/key.pdf",
        sha256="abc123",
        ocr_status=OcrStatus.COMPLETE,
        run_type=RunType.LIVE,
        uploaded_at=datetime.now(UTC),
    )
    session.add(document)
    await session.commit()
    return document


async def _make_field(
    session: AsyncSession, document_id: uuid.UUID, confidence=0.95
) -> ExtractedField:
    field = ExtractedField(
        id=uuid.uuid4(),
        lease_document_id=document_id,
        field_type=FieldType.BASE_RENT,
        extracted_value={"amount": 42.5, "unit": "USD_PER_SQFT_PER_YEAR"},
        confidence_score=confidence,
        model_version="test-model-v1",
    )
    session.add(field)
    await session.commit()
    return field


@pytest.mark.asyncio
async def test_list_extracted_fields_returns_them(app_client, session):
    principal = app_client.default_principal
    document = await _make_document(session, [principal.team_id])
    await _make_field(session, document.id)

    resp = await app_client.get(f"/v1/lease-documents/{document.id}/extracted-fields")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["field_type"] == "BASE_RENT"
    assert body[0]["verification_status"] == "UNVERIFIED"


@pytest.mark.asyncio
async def test_list_extracted_fields_403_outside_information_barrier(app_client, session):
    document = await _make_document(session, [uuid.uuid4()])  # a different team

    resp = await app_client.get(f"/v1/lease-documents/{document.id}/extracted-fields")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_verify_confirms_value_as_is(app_client, session):
    principal = app_client.default_principal
    document = await _make_document(session, [principal.team_id])
    field = await _make_field(session, document.id)

    resp = await app_client.post(
        f"/v1/lease-documents/{document.id}/extracted-fields/{field.id}/verify", json={}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["verification_status"] == "VERIFIED"
    assert body["extracted_value"] == {"amount": 42.5, "unit": "USD_PER_SQFT_PER_YEAR"}


@pytest.mark.asyncio
async def test_verify_with_value_overrides(app_client, session):
    principal = app_client.default_principal
    document = await _make_document(session, [principal.team_id])
    field = await _make_field(session, document.id)

    resp = await app_client.post(
        f"/v1/lease-documents/{document.id}/extracted-fields/{field.id}/verify",
        json={"value": {"amount": 50.0, "unit": "USD_PER_SQFT_PER_YEAR"}},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["verification_status"] == "OVERRIDDEN"
    assert body["extracted_value"]["amount"] == 50.0


@pytest.mark.asyncio
async def test_reverify_already_verified_field_returns_409(app_client, session):
    principal = app_client.default_principal
    document = await _make_document(session, [principal.team_id])
    field = await _make_field(session, document.id)

    first = await app_client.post(
        f"/v1/lease-documents/{document.id}/extracted-fields/{field.id}/verify", json={}
    )
    assert first.status_code == 200

    second = await app_client.post(
        f"/v1/lease-documents/{document.id}/extracted-fields/{field.id}/verify",
        json={"value": {"amount": 999}},
    )

    assert second.status_code == 409
