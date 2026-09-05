"""AccuracyMetricSnapshot model (T033, data-model.md, FR-015, User Story 3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db import SCHEMA_NAME, Base
from src.models.enums import FieldType
from src.models.types import GUID


class AccuracyMetricSnapshot(Base):
    __tablename__ = "accuracy_metric_snapshots"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    field_type: Mapped[FieldType] = mapped_column(
        Enum(FieldType, name="field_type", schema=SCHEMA_NAME), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String, nullable=False)

    measured_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    drift_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
