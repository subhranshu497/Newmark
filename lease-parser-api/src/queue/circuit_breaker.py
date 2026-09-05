"""Circuit breaker wrapper around external OCR/LLM calls (T008, FR-011).

Independent breakers for OCR and for extraction so a degraded LLM provider
doesn't necessarily stop OCR from making progress, and vice versa
(research.md). Explicit failure-rate/latency thresholds are configuration
(src/config.py), not code, so they can be tuned operationally. Half-open
probes test recovery before full traffic resumes (Constitution IV) — this
is pybreaker's built-in behavior, not something this wrapper reimplements.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

import pybreaker

from src.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BreakerOpenError(RuntimeError):
    """Raised when a circuit breaker is open and a call is rejected outright."""


class _LoggingListener(pybreaker.CircuitBreakerListener):
    def __init__(self, name: str) -> None:
        self._name = name

    def state_change(self, cb, old_state, new_state) -> None:
        logger.warning(
            "circuit_breaker.%s state change: %s -> %s", self._name, old_state.name, new_state.name
        )


def make_breaker(name: str) -> pybreaker.CircuitBreaker:
    settings = get_settings()
    return pybreaker.CircuitBreaker(
        fail_max=settings.circuit_breaker_fail_max,
        reset_timeout=settings.circuit_breaker_reset_timeout_seconds,
        listeners=[_LoggingListener(name)],
        name=name,
    )


ocr_breaker = make_breaker("ocr")
extraction_breaker = make_breaker("extraction")


def call_with_breaker(breaker: pybreaker.CircuitBreaker, fn: Callable[[], T]) -> T:
    """Invoke `fn` through `breaker`, translating an open circuit into BreakerOpenError.

    Callers (e.g. the document_uploaded_consumer) catch BreakerOpenError to
    route the document to manual review/queueing (FR-010/FR-011) instead of
    letting a raw pybreaker exception propagate.
    """
    try:
        return breaker.call(fn)
    except pybreaker.CircuitBreakerError as exc:
        raise BreakerOpenError(str(exc)) from exc
