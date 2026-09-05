"""Generic retry-with-jitter helper for transient (5xx-class) failures.

Separate from src/queue/circuit_breaker.py: the breaker tracks a *sustained*
failure rate across many calls over time and trips to stop hammering a
provider that's clearly down. This handles one call's transient blip —
a handful of bounded retries — before the breaker's failure count is even
touched. src/fallback/providers.py builds on this for the two extraction
providers; nothing here is Anthropic/OpenAI-specific.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY_SECONDS = 0.5
DEFAULT_MAX_DELAY_SECONDS = 4.0


def is_transient_status(status_code: int | None) -> bool:
    """5xx is the provider's own fault and often resolves on retry (overload,
    gateway timeout, temporary unavailability); 4xx (bad request, unknown
    model, bad auth) will not succeed on retry — retrying it just wastes
    time and burns API calls for a guaranteed-identical failure.
    """
    return status_code is not None and 500 <= status_code < 600


def retry_with_jitter(
    fn: Callable[[], T],
    *,
    is_transient: Callable[[Exception], bool],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `fn()`, retrying up to `max_attempts` total attempts when
    `is_transient` says the raised exception is worth retrying. Delay
    between attempts is exponential backoff with *full* jitter — a random
    delay between 0 and the backoff cap — so concurrent callers don't all
    retry in lockstep against a provider that's already struggling.

    Re-raises the last exception unchanged once attempts are exhausted, or
    immediately if `is_transient` says it's not worth retrying at all.
    Callers decide how to present that to an end user (src/fallback/providers.py
    translates it into a safe, user-facing message).
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - reclassified via is_transient below
            last_exc = exc
            if not is_transient(exc) or attempt == max_attempts:
                raise
            delay = random.uniform(0, min(max_delay, base_delay * (2 ** (attempt - 1))))
            logger.warning(
                "transient failure on attempt %d/%d, retrying in %.2fs: %s",
                attempt,
                max_attempts,
                delay,
                exc,
            )
            sleep(delay)
    raise last_exc  # pragma: no cover - loop above always returns or raises
