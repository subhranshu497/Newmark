"""Unit tests for the circuit breaker wrapper (T048, FR-011)."""

from __future__ import annotations

import pytest

from src.queue.circuit_breaker import BreakerOpenError, call_with_breaker, make_breaker


def test_successful_call_passes_through():
    breaker = make_breaker("test-success")
    assert call_with_breaker(breaker, lambda: 42) == 42


def test_breaker_opens_after_repeated_failures_and_rejects_further_calls():
    breaker = make_breaker("test-failure")
    breaker.fail_max = 2

    def _boom():
        raise RuntimeError("provider unavailable")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            call_with_breaker(breaker, _boom)

    # Breaker is now open: further calls are rejected without even invoking `fn`,
    # and the raw pybreaker exception is translated into BreakerOpenError so
    # callers (OCR/extraction adapters) can catch one exception type (FR-011).
    with pytest.raises(BreakerOpenError):
        call_with_breaker(breaker, lambda: 1)
