"""ReviewQueueItem model (T024, data-model.md).

A pending unit of work for a low-confidence (or excluded-for-quality)
field. `allowed_teams` is copied from the parent LeaseDocument so
information-barrier enforcement (FR-018) doesn't require a join back to
LeaseDocument on every read.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db import SCHEMA_NAME, Base, qualified
from src.models.enums import ReviewQueueStatus
from src.models.types import GUID, UUIDArray


class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # Nullable: an item may originate from an EXCLUDED_LOW_QUALITY document
    # with no ExtractedField at all (FR-013), not only from a below-threshold field.
    extracted_field_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey(qualified("extracted_fields.id")), nullable=True
    )
    lease_document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey(qualified("lease_documents.id")), nullable=False
    )

    team_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    allowed_teams: Mapped[list[uuid.UUID]] = mapped_column(
        UUIDArray(), nullable=False, default=list
    )

    status: Mapped[ReviewQueueStatus] = mapped_column(
        Enum(ReviewQueueStatus, name="review_queue_status", schema=SCHEMA_NAME),
        nullable=False,
        default=ReviewQueueStatus.PENDING,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
