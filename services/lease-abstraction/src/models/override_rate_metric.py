"""OverrideRateMetric model (T034, data-model.md, FR-016, User Story 3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db import SCHEMA_NAME, Base
from src.models.enums import FieldType
from src.models.types import GUID


class OverrideRateMetric(Base):
    __tablename__ = "override_rate_metrics"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    field_type: Mapped[FieldType] = mapped_column(
        Enum(FieldType, name="field_type", schema=SCHEMA_NAME), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    override_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_verified_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
