"""Local-demo-only seed endpoint backing lease-parser-ui (a separate frontend
project at Newmark/lease-parser-ui — see that folder's index.html).

Not part of the platform contract (contracts/api.md) — there's no Kafka broker in
the local demo mode, so nothing seeds a LeaseDocument the normal way. This gives
the standalone demo UI a way to do it instead of a throwaway python script. Only
mounted when LEASE_ABSTRACTION_ENABLE_DEMO_UI=1 (src/config.py), never in
production; that same flag also gates CORS in src/api/main.py, since the UI runs
on a different origin than this API.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from io import BytesIO

import anthropic
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.config import get_settings
from src.consumers.document_uploaded_consumer import DocumentUploadedConsumer
from src.extraction.claude_adapter import ClaudeExtractionAdapter, ExtractionProviderError
from src.extraction.failover import ExtractionUnavailableError, FailoverExtractionAdapter
from src.extraction.field_schemas import validate_field_value
from src.models.enums import FieldType, OcrStatus, ReviewQueueStatus, RunType, VerificationStatus
from src.models.extracted_field import ExtractedField
from src.models.lease_document import LeaseDocument
from src.models.review_queue_item import ReviewQueueItem
from src.ocr.textract_adapter import OcrResult

router = APIRouter(tags=["demo"])
logger = logging.getLogger(__name__)

# Below this many non-whitespace characters, treat the PDF as having no usable
# text layer (e.g. a scanned image with no OCR available in this demo) rather
# than feeding a near-empty string to the extraction model.
MIN_USABLE_TEXT_CHARS = 20

_SUMMARY_SYSTEM_PROMPT = (
    "In exactly one sentence, describe what kind of document this is and what it covers, "
    "in plain language a commercial real estate analyst would understand. Do not mention "
    "that it lacks lease terms or discuss what's missing — just describe what the document "
    "actually is."
)


class _PrecomputedOcrAdapter:
    """Stands in for TextractAdapter: `extract_text` normally hits AWS, but this
    demo path already has the text (pulled from the uploaded PDF directly), so
    it just returns it — same interface, no S3/Textract dependency.
    """

    def __init__(self, result: OcrResult) -> None:
        self._result = result

    def extract_text(self, s3_bucket: str, s3_key: str) -> OcrResult:
        return self._result


class _NullProducer:
    """Stands in for JsonProducer: there's no Kafka broker in the local demo,
    and the UI doesn't need the `lease.extraction.completed` event — it gets
    the result synchronously as this endpoint's HTTP response instead.
    """

    def publish(self, topic: str, payload: dict, key: str | None = None) -> None:
        pass


def _extract_pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except PdfReadError as exc:
        raise HTTPException(status_code=422, detail=f"not a readable PDF: {exc}") from exc


def _summarize_document(text: str) -> str | None:
    """One-line, plain-English description of what an uploaded document
    actually is — shown when it produced zero lease fields, so the response
    is "here's what this actually is" rather than a bare empty list. Best
    effort: a failure here shouldn't fail the whole upload, since the fields
    result (empty) is already valid and returned regardless.
    """
    settings = get_settings()
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=100,
            system=_SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text[:4000]}],
        )
        summary = "".join(b.text for b in response.content if b.type == "text").strip()
        return summary or None
    except Exception:  # noqa: BLE001 - best-effort; caller falls back to a generic message
        logger.warning("document summary call failed", exc_info=True)
        return None


class SeedRequest(BaseModel):
    team_id: uuid.UUID | None = None


class SeedResponse(BaseModel):
    team_id: uuid.UUID
    document_id: uuid.UUID
    base_rent_field_id: uuid.UUID
    review_queue_item_id: uuid.UUID


@router.post("/demo/seed", response_model=SeedResponse)
async def seed_demo_record(
    body: SeedRequest, session: AsyncSession = Depends(get_session)
) -> SeedResponse:
    """Create one LeaseDocument with two ExtractedFields: a high-confidence
    BASE_RENT (ready to verify directly) and a low-confidence FREE_RENT_PERIOD
    that's already routed to a pending ReviewQueueItem — so the UI has
    something to demonstrate in both the "verify a field" and "review queue"
    flows immediately after seeding.
    """
    team_id = body.team_id or uuid.uuid4()
    document_id = uuid.uuid4()
    now = datetime.now(UTC)

    session.add(
        LeaseDocument(
            id=document_id,
            deal_id=uuid.uuid4(),
            team_id=team_id,
            allowed_teams=[team_id],
            s3_key=f"lease-bucket/leases/{document_id}.pdf",
            sha256=uuid.uuid4().hex,
            ocr_status=OcrStatus.COMPLETE,
            run_type=RunType.LIVE,
            uploaded_at=now,
        )
    )

    base_rent_field = ExtractedField(
        id=uuid.uuid4(),
        lease_document_id=document_id,
        field_type=FieldType.BASE_RENT,
        extracted_value=validate_field_value(
            FieldType.BASE_RENT, {"amount": 38.50, "unit": "USD_PER_SQFT_PER_YEAR"}
        ),
        confidence_score=0.97,
        model_version="demo-seed",
        verification_status=VerificationStatus.UNVERIFIED,
    )
    session.add(base_rent_field)

    low_confidence_field = ExtractedField(
        id=uuid.uuid4(),
        lease_document_id=document_id,
        field_type=FieldType.FREE_RENT_PERIOD,
        extracted_value=validate_field_value(FieldType.FREE_RENT_PERIOD, {"months": 2}),
        confidence_score=0.55,
        model_version="demo-seed",
        verification_status=VerificationStatus.UNVERIFIED,
    )
    session.add(low_confidence_field)
    await session.flush()

    review_item = ReviewQueueItem(
        id=uuid.uuid4(),
        extracted_field_id=low_confidence_field.id,
        lease_document_id=document_id,
        team_id=team_id,
        allowed_teams=[team_id],
        status=ReviewQueueStatus.PENDING,
        created_at=now,
    )
    session.add(review_item)

    await session.commit()

    return SeedResponse(
        team_id=team_id,
        document_id=document_id,
        base_rent_field_id=base_rent_field.id,
        review_queue_item_id=review_item.id,
    )


class ParsedFieldOut(BaseModel):
    id: uuid.UUID
    field_type: str
    extracted_value: dict
    confidence_score: float
    auto_populated: bool


class ParseUploadResponse(BaseModel):
    team_id: uuid.UUID
    document_id: uuid.UUID
    ocr_status: str
    fields: list[ParsedFieldOut]
    review_queue_item_ids: list[uuid.UUID]
    is_valid_lease_document: bool
    document_summary: str | None = None


@router.post("/demo/parse-upload", response_model=ParseUploadResponse)
async def parse_uploaded_pdf(
    file: UploadFile = File(...),
    team_id: uuid.UUID | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> ParseUploadResponse:
    """Real end-to-end parsing of an uploaded PDF: pull its text locally (no
    Textract/AWS needed for this demo), then run it through the same
    DocumentUploadedConsumer pipeline a real `document.uploaded` Kafka event
    would — real Claude/OpenAI extraction (FR-012 failover included) and real
    confidence-threshold routing to auto-populate vs. the review queue
    (FR-004/FR-013). Only the OCR step and the completion-event publish are
    swapped for local/no-op equivalents; everything else is production logic.
    """
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=422, detail="uploaded file is empty")

    text = _extract_pdf_text(pdf_bytes)
    has_usable_text = len(text.strip()) >= MIN_USABLE_TEXT_CHARS
    ocr_result = OcrResult(
        text=text,
        confidence=0.95 if has_usable_text else 0.0,
        model_version="local-pdf-text-extract",
    )

    team = team_id or uuid.uuid4()
    event = {
        "documentType": "LEASE",
        "dealId": str(uuid.uuid4()),
        "teamId": str(team),
        "allowedTeams": [str(team)],
        "s3Key": f"local-upload/{file.filename or 'upload.pdf'}",
        "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
    }

    # FailoverExtractionAdapter builds an OpenAI client eagerly, which raises
    # if no key is configured — but test.md documents the OpenAI key as
    # optional (only needed to exercise FR-012's failover path). Use Claude
    # alone when there's nothing to fail over to.
    extraction_adapter = (
        FailoverExtractionAdapter() if get_settings().openai_api_key else ClaudeExtractionAdapter()
    )

    consumer = DocumentUploadedConsumer(
        ocr_adapter=_PrecomputedOcrAdapter(ocr_result),
        extraction_adapter=extraction_adapter,
        producer=_NullProducer(),
    )
    try:
        document = await consumer.handle(session, event)
    except (ExtractionUnavailableError, ExtractionProviderError) as exc:
        # str(exc) is already a user-safe message by this point — either the
        # retry-exhausted / non-retryable message from src/fallback/providers.py,
        # or FailoverExtractionAdapter's own generic "both providers failed".
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=500, detail="pipeline did not create a document")
    await session.commit()

    field_rows = (
        await session.execute(
            select(ExtractedField).where(ExtractedField.lease_document_id == document.id)
        )
    ).scalars().all()
    queue_rows = (
        await session.execute(
            select(ReviewQueueItem).where(ReviewQueueItem.lease_document_id == document.id)
        )
    ).scalars().all()
    queued_field_ids = {q.extracted_field_id for q in queue_rows}

    # Text extracted fine but none of the five lease fields were found — this is
    # a real, valid outcome (see FIELD_EXTRACTION_INSTRUCTIONS), but a document
    # this clearly isn't a lease at all is worth flagging explicitly rather than
    # just returning an empty list, so the UI can say so instead of looking broken.
    is_valid_lease_document = bool(field_rows)
    document_summary = None
    if not is_valid_lease_document and document.ocr_status == OcrStatus.COMPLETE:
        document_summary = _summarize_document(text)

    return ParseUploadResponse(
        team_id=team,
        document_id=document.id,
        ocr_status=document.ocr_status.value,
        fields=[
            ParsedFieldOut(
                id=f.id,
                field_type=f.field_type.value,
                extracted_value=f.extracted_value,
                confidence_score=f.confidence_score,
                auto_populated=f.id not in queued_field_ids,
            )
            for f in field_rows
        ],
        review_queue_item_ids=[q.id for q in queue_rows],
        is_valid_lease_document=is_valid_lease_document,
        document_summary=document_summary,
    )
