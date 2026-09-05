"""OCR adapter — AWS Textract (T013, research.md).

Chosen because Textract returns a per-block/per-page confidence score
natively, giving FR-013's scan-quality floor a real signal to threshold on
without building custom heuristics for v1. Wrapped by the OCR circuit
breaker (T008) so a degraded/unavailable OCR provider opens the breaker
rather than accumulating timeouts (FR-011).
"""

from __future__ import annotations

from dataclasses import dataclass

import boto3

from src.config import get_settings
from src.queue.circuit_breaker import BreakerOpenError, call_with_breaker, ocr_breaker

TEXTRACT_MODEL_VERSION = "aws-textract-v1"


class OcrUnavailableError(RuntimeError):
    """Raised when OCR cannot be performed — breaker open or provider failure.

    Callers MUST treat this as "queue for later / accept manual entry"
    (FR-010), never as a reason to block the upload itself.
    """


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float  # 0.0-1.0, Textract's own block-confidence average
    model_version: str = TEXTRACT_MODEL_VERSION


class TextractAdapter:
    def __init__(self, client=None) -> None:
        settings = get_settings()
        self._client = client or boto3.client("textract", region_name=settings.aws_region)

    def extract_text(self, s3_bucket: str, s3_key: str) -> OcrResult:
        try:
            return call_with_breaker(ocr_breaker, lambda: self._call_textract(s3_bucket, s3_key))
        except BreakerOpenError as exc:
            raise OcrUnavailableError("OCR circuit breaker is open") from exc
        except Exception as exc:  # noqa: BLE001 - any provider failure maps to OcrUnavailableError
            raise OcrUnavailableError(f"Textract call failed: {exc}") from exc

    def _call_textract(self, s3_bucket: str, s3_key: str) -> OcrResult:
        response = self._client.analyze_document(
            Document={"S3Object": {"Bucket": s3_bucket, "Name": s3_key}},
            FeatureTypes=["TABLES", "FORMS"],
        )
        blocks = response.get("Blocks", [])
        text_blocks = [b for b in blocks if b.get("BlockType") in ("LINE", "WORD")]
        text = "\n".join(b.get("Text", "") for b in text_blocks if b.get("BlockType") == "LINE")
        confidences = [b["Confidence"] / 100.0 for b in text_blocks if "Confidence" in b]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(text=text, confidence=avg_confidence)


def below_quality_floor(ocr_result: OcrResult) -> bool:
    """FR-013: documents below the configured scan-quality floor are excluded
    from automated extraction entirely and routed to manual entry."""
    return ocr_result.confidence < get_settings().scan_quality_floor
