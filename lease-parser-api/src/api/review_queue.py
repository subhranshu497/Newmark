"""Review-queue endpoints (T027, T028, contracts/api.md).

GET is scoped to the caller's own team — a caller cannot see another
team's queue by widening the `teamId` query parameter (FR-018). POST
resolves an item, creating or overriding the linked ExtractedField.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_principal, get_session
from src.models.enums import FieldType, ReviewQueueStatus, VerificationStatus
from src.models.extracted_field import ExtractedField, FieldAlreadyVerifiedError
from src.models.review_queue_item import ReviewQueueItem
from src.policy.team_scope import (
    InformationBarrierError,
    Principal,
    enforce_team_scope,
    enforce_team_scope_with_admin_audit,
)

router = APIRouter(prefix="/v1/review-queue", tags=["review-queue"])


class ReviewQueueItemOut(BaseModel):
    id: uuid.UUID
    lease_document_id: uuid.UUID
    extracted_field_id: uuid.UUID | None
    status: str
    model_config = {"from_attributes": True}


class ResolveRequest(BaseModel):
    value: dict
    field_type: FieldType | None = None  # required only when extracted_field_id is None


@router.get("", response_model=list[ReviewQueueItemOut])
async def list_review_queue(
    teamId: uuid.UUID = Query(...),
    status: ReviewQueueStatus | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> list[ReviewQueueItem]:
    if teamId != principal.team_id:
        # Read endpoint: an admin MAY request another team's queue, but the
        # crossing is written to the audit log below (T047 audit finding —
        # this previously bypassed silently with no log entry, inconsistent
        # with design doc §7.2 point 3 and with extracted_fields' pattern).
        try:
            enforce_team_scope_with_admin_audit(principal, [teamId], "review_queue", teamId)
        except InformationBarrierError as exc:
            raise HTTPException(
                status_code=403, detail="cannot request another team's review queue"
            ) from exc

    stmt = select(ReviewQueueItem).where(ReviewQueueItem.team_id == teamId)
    if status is not None:
        stmt = stmt.where(ReviewQueueItem.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/{item_id}/resolve", response_model=ReviewQueueItemOut)
async def resolve_review_queue_item(
    item_id: uuid.UUID,
    body: ResolveRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_principal),
) -> ReviewQueueItem:
    item = await session.get(ReviewQueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="review queue item not found")

    try:
        enforce_team_scope(principal, item.allowed_teams)
    except InformationBarrierError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if item.status == ReviewQueueStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="review queue item already resolved")

    if item.extracted_field_id is not None:
        field = await session.get(ExtractedField, item.extracted_field_id)
        try:
            field.apply_verification(verified_by=principal.user_id, override_value=body.value)
        except FieldAlreadyVerifiedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        if body.field_type is None:
            raise HTTPException(
                status_code=422,
                detail="field_type is required when resolving an item with no existing field",
            )
        field = ExtractedField(
            id=uuid.uuid4(),
            lease_document_id=item.lease_document_id,
            field_type=body.field_type,
            extracted_value=body.value,
            confidence_score=1.0,  # human-entered, not a model prediction
            model_version="human-entry",
            verification_status=VerificationStatus.OVERRIDDEN,
            verified_by=principal.user_id,
            verified_at=datetime.now(UTC),
        )
        session.add(field)
        await session.flush()
        item.extracted_field_id = field.id

    item.status = ReviewQueueStatus.RESOLVED
    item.resolved_at = datetime.now(UTC)

    await session.commit()
    return item
