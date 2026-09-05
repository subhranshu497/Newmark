"""LeaseDocument and ExtractionRun models (T005, data-model.md).

LeaseDocument represents one uploaded lease PDF and its OCR outcome.
ExtractionRun tracks one pass of the pipeline over a document, supporting
FR-017's isolated backfill path and reprocessing without overwriting
verified data (Constitution II / FR-008).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db import SCHEMA_NAME, Base, qualified
from src.models.enums import OcrStatus, RunStatus, RunType
from src.models.types import GUID, UUIDArray


class LeaseDocument(Base):
    __tablename__ = "lease_documents"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    deal_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    team_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    allowed_teams: Mapped[list[uuid.UUID]] = mapped_column(
        UUIDArray(), nullable=False, default=list
    )

    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)

    ocr_status: Mapped[OcrStatus] = mapped_column(
        Enum(OcrStatus, name="ocr_status", schema=SCHEMA_NAME),
        nullable=False,
        default=OcrStatus.PENDING,
    )
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    run_type: Mapped[RunType] = mapped_column(
        Enum(RunType, name="run_type", schema=SCHEMA_NAME), nullable=False, default=RunType.LIVE
    )

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    extraction_runs: Mapped[list[ExtractionRun]] = relationship(back_populates="lease_document")


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    lease_document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey(qualified("lease_documents.id")), nullable=False
    )

    run_type: Mapped[RunType] = mapped_column(
        Enum(RunType, name="run_type", schema=SCHEMA_NAME), nullable=False
    )
    ocr_model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    extraction_model_version: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status", schema=SCHEMA_NAME),
        nullable=False,
        default=RunStatus.RUNNING,
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lease_document: Mapped[LeaseDocument] = relationship(back_populates="extraction_runs")
