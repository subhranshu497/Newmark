"""Dead-letter consumer/alert hook (T043, FR-010).

Consumes `lease.extraction.dead-letter` (produced by RetryingConsumer once
a `document.uploaded` message exhausts its retries) and routes it to an
operational alert so a human can triage the document that never made it
through the pipeline — satisfying "an outage delays processing, it never
drops work" without requiring a person to notice a missing document on
their own.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

AlertSink = Callable[[dict[str, Any]], None]


def default_alert_sink(payload: dict[str, Any]) -> None:
    """Default sink: structured log line.

    Production deployments should replace this with a call into the
    platform's existing alerting channel (out of scope for this service to
    own) via the `alert_sink` constructor argument below.
    """
    logger.error(
        "Lease document dead-lettered: documentId=%s reason=%s attempts=%s",
        payload.get("documentId"),
        payload.get("failureReason"),
        payload.get("attemptCount"),
    )


class DeadLetterConsumer:
    def __init__(self, alert_sink: AlertSink | None = None) -> None:
        self._alert_sink = alert_sink or default_alert_sink

    async def handle(self, event: dict[str, Any]) -> None:
        self._alert_sink(event)
