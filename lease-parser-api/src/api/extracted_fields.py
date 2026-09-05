"""Extracted-fields endpoints (T018, T019, contracts/api.md).

GET .../extracted-fields (T018) and POST .../verify (T019). Both enforce
the information barrier (FR-018) and the verify endpoint enforces the
terminal-state guard (FR-008) with a 409 on an already-verified field.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_principal, get_session
from src.models.extracted_field import ExtractedField, FieldAlreadyVerifiedError
from src.models.lease_document import LeaseDocument
from src.policy.team_scope import (
    InformationBarrierError,
    Principal,
    enforce_team_scope,
    enforce_team_scope_with_admin_audit,
)

router = APIRouter(prefix="/v1/lease-documents", tags=["extracted-fields"])


class ExtractedFieldOut(BaseModel):
    id: uuid.UUID
    field_type: str
    extracted_value: dict
    confidence_score: float
    model_version: str
    verification_status: str
    verified_by: uuid.UUID | None
    model_config = {"from_attributes": True}


class VerifyRequest(BaseModel):
    value: dict | None = None


async def _get_document_or_404(session: AsyncSession, document_id: uuid.UUID) -> LeaseDocument:
    document = await session.get(LeaseDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="lease document not found")
    return document


@router.get("/{document_id}/extracted-fields", response_model=list[ExtractedFieldOut])
async def list_extracted_fields(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> list[ExtractedField]:
    document = await _get_document_or_404(session, document_id)
    try:
        # Read endpoint: an admin MAY cross the barrier, but every crossing
        # is written to the audit log (T047 / design doc §7.2 point 3).
        enforce_team_scope_with_admin_audit(
            principal, document.allowed_teams, "lease_document", document_id
        )
    except InformationBarrierError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    result = await session.execute(
        select(ExtractedField).where(ExtractedField.lease_document_id == document_id)
    )
    return list(result.scalars().all())


@router.post("/{document_id}/extracted-fields/{field_id}/verify", response_model=ExtractedFieldOut)
async def verify_extracted_field(
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    body: VerifyRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> ExtractedField:
    document = await _get_document_or_404(session, document_id)
    try:
        # Write endpoint: no admin bypass. §7.2's admin allowance is
        # scoped to reads; an admin verifying a field on another team's
        # deal is not something the design doc authorizes (T047 audit).
        enforce_team_scope(principal, document.allowed_teams)
    except InformationBarrierError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    field = await session.get(ExtractedField, field_id)
    if field is None or field.lease_document_id != document_id:
        raise HTTPException(status_code=404, detail="extracted field not found")

    try:
        field.apply_verification(verified_by=principal.user_id, override_value=body.value)
    except FieldAlreadyVerifiedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await session.commit()
    return field
