"""Isolated bulk-backfill processing path (T044, FR-017).

Consumes `document.backfill.requested` on a separate consumer group from
the live `document.uploaded` path, and self-throttles to a configured
rate so historical-archive backfill volume (README §7: "tens of thousands
of executed leases") cannot contend with or delay live document
processing.

Added per `/speckit-analyze` finding A1 — previously only a `runType`
enum value existed with no task implementing the actual isolation.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from src.config import get_settings
from src.consumers.base import RetryingConsumer
from src.consumers.document_uploaded_consumer import DocumentUploadedConsumer
from src.models.db import session_scope
from src.models.enums import RunType


class RateLimiter:
    """Simple token-bucket-per-minute limiter."""

    def __init__(self, max_per_minute: int) -> None:
        self._max_per_minute = max_per_minute
        self._window_start = time.monotonic()
        self._count_in_window = 0

    async def acquire(self) -> None:
        now = time.monotonic()
        elapsed = now - self._window_start
        if elapsed >= 60:
            self._window_start = now
            self._count_in_window = 0

        if self._count_in_window >= self._max_per_minute:
            wait_seconds = 60 - elapsed
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            self._window_start = time.monotonic()
            self._count_in_window = 0

        self._count_in_window += 1


class BackfillProcessor:
    """Runs the same extraction pipeline as the live path, on an isolated,
    rate-limited consumer group (contracts/events.md: document.backfill.requested)."""

    def __init__(
        self,
        consumer: RetryingConsumer | None = None,
        pipeline: DocumentUploadedConsumer | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        settings = get_settings()
        self._consumer = consumer or RetryingConsumer(
            topics=["document.backfill.requested"],
            group_id=settings.kafka_backfill_consumer_group,
            dead_letter_topic=settings.topic_dead_letter,
        )
        self._pipeline = pipeline or DocumentUploadedConsumer()
        self._rate_limiter = rate_limiter or RateLimiter(settings.backfill_rate_limit_per_minute)

    async def _handle_one(self, event: dict[str, Any]) -> None:
        await self._rate_limiter.acquire()
        async with session_scope() as session:
            await self._pipeline.handle(session, event, run_type=RunType.BACKFILL)

    async def run_forever(self) -> None:
        while True:
            await self._consumer.run_once(self._handle_one)

    def close(self) -> None:
        self._consumer.close()
