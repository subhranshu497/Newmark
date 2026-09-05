"""ExtractedField model (T012, data-model.md).

One structured lease term derived from a LeaseDocument. Once
`verification_status` leaves UNVERIFIED it is terminal — Constitution II /
FR-008 requires human-verified data to be authoritative and never
overwritten by reprocessing, model upgrades, or pipeline reruns. That
invariant is enforced here at the model layer (`apply_verification`) and
again at the API layer (contracts/api.md's 409 rule).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db import SCHEMA_NAME, Base, qualified
from src.models.enums import FieldType, VerificationStatus
from src.models.types import GUID


class FieldAlreadyVerifiedError(ValueError):
    """Raised when attempting to mutate a field whose verification is terminal."""


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    lease_document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey(qualified("lease_documents.id")), nullable=False
    )

    field_type: Mapped[FieldType] = mapped_column(
        Enum(FieldType, name="field_type", schema=SCHEMA_NAME), nullable=False
    )
    extracted_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    source_location: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", schema=SCHEMA_NAME),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @property
    def is_terminal(self) -> bool:
        return self.verification_status != VerificationStatus.UNVERIFIED

    def apply_verification(
        self, verified_by: uuid.UUID, override_value: dict[str, Any] | None = None
    ) -> None:
        """Confirm (or override-then-confirm) this field. Terminal once applied (FR-008).

        Raises FieldAlreadyVerifiedError if the field has already been
        verified — callers (the API layer) translate this into a 409.
        """
        if self.is_terminal:
            raise FieldAlreadyVerifiedError(
                f"ExtractedField {self.id} is already {self.verification_status.value}"
            )
        if override_value is not None:
            self.extracted_value = override_value
            self.verification_status = VerificationStatus.OVERRIDDEN
        else:
            self.verification_status = VerificationStatus.VERIFIED
        self.verified_by = verified_by
        self.verified_at = datetime.now(UTC)
