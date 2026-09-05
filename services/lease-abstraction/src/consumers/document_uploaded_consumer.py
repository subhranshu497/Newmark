"""`document.uploaded` consumer: OCR -> extraction (with failover) -> auto-populate or queue.

- `handle()` (T017, T020): the live path — a brand-new LeaseDocument from a
  `document.uploaded` event.
- `reprocess()` (T029): reruns the pipeline against an *existing*
  LeaseDocument (e.g. after a model upgrade). Guards already-verified
  fields from being touched (FR-008) — this is the reprocessing edge case
  from quickstart.md Scenario 2 step 5.
- Below-threshold and below-quality-floor documents create ReviewQueueItem
  rows (T025, T026, FR-005/FR-013), scoped to the same team/allowed-teams
  as the parent LeaseDocument (FR-018).

Non-blocking by construction (Constitution I / FR-014): this module is only
ever invoked by the Kafka consumer loop, never called synchronously by the
Deal, Commission, or Search services.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.consumers.base import JsonProducer
from src.extraction.failover import ExtractionUnavailableError, FailoverExtractionAdapter
from src.extraction.threshold_policy import should_auto_populate
from src.models.enums import OcrStatus, ReviewQueueStatus, RunStatus, RunType, VerificationStatus
from src.models.extracted_field import ExtractedField
from src.models.lease_document import ExtractionRun, LeaseDocument
from src.models.review_queue_item import ReviewQueueItem
from src.ocr.textract_adapter import OcrUnavailableError, TextractAdapter, below_quality_floor


class DocumentUploadedConsumer:
    def __init__(
        self,
        ocr_adapter: TextractAdapter | None = None,
        extraction_adapter: FailoverExtractionAdapter | None = None,
        producer: JsonProducer | None = None,
        extraction_completed_topic: str = "lease.extraction.completed",
    ) -> None:
        self._ocr = ocr_adapter or TextractAdapter()
        self._extraction = extraction_adapter or FailoverExtractionAdapter()
        self._producer = producer or JsonProducer()
        self._extraction_completed_topic = extraction_completed_topic

    async def handle(
        self, session: AsyncSession, event: dict[str, Any], run_type: RunType = RunType.LIVE
    ) -> LeaseDocument | None:
        """Process a new document. `run_type` is LIVE for `document.uploaded` and
        BACKFILL for `document.backfill.requested` (T044, isolated backfill path).

        Returns the created LeaseDocument (callers that only consume Kafka
        events, like backfill_consumer.py, ignore this; src/api/demo_seed.py
        uses it to report the document id back to the caller synchronously).
        """
        if event.get("documentType") != "LEASE":
            return None  # only lease documents are processed by this service

        document = LeaseDocument(
            id=uuid.uuid4(),
            deal_id=uuid.UUID(event["dealId"]),
            team_id=uuid.UUID(event["teamId"]),
            allowed_teams=[uuid.UUID(t) for t in event["allowedTeams"]],
            s3_key=event["s3Key"],
            sha256=event["sha256"],
            ocr_status=OcrStatus.PROCESSING,
            run_type=run_type,
            uploaded_at=datetime.now(UTC),
        )
        session.add(document)
        await session.flush()

        run = ExtractionRun(
            id=uuid.uuid4(),
            lease_document_id=document.id,
            run_type=run_type,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()

        await self._run_pipeline(session, document, run, existing_fields_by_type={})
        return document

    async def reprocess(self, session: AsyncSession, lease_document_id: uuid.UUID) -> None:
        """Rerun the pipeline against an existing document (e.g. model upgrade).

        FR-008 guard: any field already VERIFIED/OVERRIDDEN on this document
        is left untouched — no new value, no new ReviewQueueItem for it.
        """
        document = await session.get(LeaseDocument, lease_document_id)
        if document is None:
            raise ValueError(f"LeaseDocument {lease_document_id} not found")

        existing = (
            await session.execute(
                select(ExtractedField).where(ExtractedField.lease_document_id == lease_document_id)
            )
        ).scalars().all()
        existing_terminal_by_type = {
            f.field_type: f
            for f in existing
            if f.verification_status != VerificationStatus.UNVERIFIED
        }

        run = ExtractionRun(
            id=uuid.uuid4(),
            lease_document_id=document.id,
            run_type=RunType.REPROCESS,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()

        await self._run_pipeline(
            session, document, run, existing_fields_by_type=existing_terminal_by_type
        )

    async def _run_pipeline(
        self,
        session: AsyncSession,
        document: LeaseDocument,
        run: ExtractionRun,
        existing_fields_by_type: dict,
    ) -> None:
        try:
            s3_bucket, s3_key = _split_s3_key(document.s3_key)
            ocr_result = self._ocr.extract_text(s3_bucket, s3_key)
        except OcrUnavailableError:
            # FR-010: leave the document queued; the Kafka-level
            # RetryingConsumer will retry this message, and the deal record
            # continues to accept manual entry in the meantime.
            run.status = RunStatus.FAILED
            run.completed_at = datetime.now(UTC)
            raise

        run.ocr_model_version = ocr_result.model_version
        document.ocr_confidence = ocr_result.confidence

        if below_quality_floor(ocr_result):
            document.ocr_status = OcrStatus.EXCLUDED_LOW_QUALITY
            run.status = RunStatus.COMPLETE
            run.completed_at = datetime.now(UTC)

            queue_item = ReviewQueueItem(
                id=uuid.uuid4(),
                extracted_field_id=None,
                lease_document_id=document.id,
                team_id=document.team_id,
                allowed_teams=document.allowed_teams,
                status=ReviewQueueStatus.PENDING,
                created_at=datetime.now(UTC),
            )
            session.add(queue_item)
            await self._emit_completion(document, run, [], [queue_item.id])
            return

        document.ocr_status = OcrStatus.COMPLETE

        try:
            extracted = self._extraction.extract_fields(ocr_result.text)
        except ExtractionUnavailableError:
            # FR-012: both providers failed. Fall back to full manual mode —
            # the document remains COMPLETE at the OCR stage so an analyst
            # can still read the source text; no fields are auto-populated.
            run.status = RunStatus.FAILED
            run.completed_at = datetime.now(UTC)
            raise

        field_ids: list[uuid.UUID] = []
        queue_item_ids: list[uuid.UUID] = []

        for result in extracted:
            existing_terminal = existing_fields_by_type.get(result.field_type)
            if existing_terminal is not None:
                # FR-008 guard: never touch an already-verified field on reprocess.
                field_ids.append(existing_terminal.id)
                continue

            field = ExtractedField(
                id=uuid.uuid4(),
                lease_document_id=document.id,
                field_type=result.field_type,
                extracted_value=result.value,
                confidence_score=result.confidence,
                model_version=result.model_version,
                source_location=result.source_location,
            )
            session.add(field)
            await session.flush()
            field_ids.append(field.id)

            if not should_auto_populate(result):
                queue_item = ReviewQueueItem(
                    id=uuid.uuid4(),
                    extracted_field_id=field.id,
                    lease_document_id=document.id,
                    team_id=document.team_id,
                    allowed_teams=document.allowed_teams,
                    status=ReviewQueueStatus.PENDING,
                    created_at=datetime.now(UTC),
                )
                session.add(queue_item)
                queue_item_ids.append(queue_item.id)

        run.extraction_model_version = extracted[0].model_version if extracted else None
        run.status = RunStatus.COMPLETE
        run.completed_at = datetime.now(UTC)

        await self._emit_completion(document, run, field_ids, queue_item_ids)

    async def _emit_completion(
        self,
        document: LeaseDocument,
        run: ExtractionRun,
        extracted_field_ids: list[uuid.UUID],
        review_queue_item_ids: list[uuid.UUID],
    ) -> None:
        self._producer.publish(
            self._extraction_completed_topic,
            {
                "documentId": str(document.id),
                "extractionRunId": str(run.id),
                "runType": run.run_type.value,
                "status": run.status.value,
                "extractedFieldIds": [str(fid) for fid in extracted_field_ids],
                "reviewQueueItemIds": [str(qid) for qid in review_queue_item_ids],
                "completedAt": run.completed_at.isoformat() if run.completed_at else None,
            },
            key=str(document.id),
        )


def _split_s3_key(full_key: str) -> tuple[str, str]:
    """S3 keys in events are stored as 'bucket/key...'; split for the Textract call."""
    bucket, _, key = full_key.partition("/")
    return bucket, key
