"""Unit test for the backfill rate limiter (T044, FR-017).

Not one of the two files explicitly named in T048, but added alongside
since it's new code from the same remediation (finding A1) and is cheap
to verify without a live Kafka broker.
"""

from __future__ import annotations

import pytest

from src.consumers.backfill_consumer import RateLimiter


@pytest.mark.asyncio
async def test_does_not_throttle_within_limit(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(
        "src.consumers.backfill_consumer.asyncio.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    limiter = RateLimiter(max_per_minute=5)
    for _ in range(5):
        await limiter.acquire()

    assert sleep_calls == []


@pytest.mark.asyncio
async def test_throttles_once_limit_exceeded_within_window(monkeypatch):
    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.consumers.backfill_consumer.asyncio.sleep", _fake_sleep)

    limiter = RateLimiter(max_per_minute=2)
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()  # 3rd call within the same window should throttle

    assert len(sleep_calls) == 1
    assert sleep_calls[0] > 0
