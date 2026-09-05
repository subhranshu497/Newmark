"""BaselineMeasurement model (T035, data-model.md, FR-019).

Records the outcome of the one-time (or periodically repeated) manual-
abstraction baseline study. SC-001 is evaluated against whichever row is
most recent at rollout time — this entity is not itself continuously
re-measured.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db import SCHEMA_NAME, Base
from src.models.types import GUID, UUIDArray


class BaselineMeasurement(Base):
    __tablename__ = "baseline_measurements"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    sample_lease_ids: Mapped[list[uuid.UUID]] = mapped_column(UUIDArray(), nullable=False)
    measured_median_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)

    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
