"""Unit tests for the retry-with-jitter helper (src/fallback/retry.py) and
the provider-specific wrappers (src/fallback/providers.py) — transient
(5xx-class) failures should retry up to 3 attempts total, non-transient
(4xx) failures should fail fast, and either way the caller-facing message
must be readable, not a raw SDK exception dump.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import anthropic
import httpx
import openai
import pytest

from src.fallback.providers import (
    ProviderCallFailedError,
    call_anthropic_with_retry,
    call_openai_with_retry,
)
from src.fallback.retry import is_transient_status, retry_with_jitter


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    # call_{anthropic,openai}_with_retry don't expose a `sleep` override (no
    # production need for one), so patch the module-level time.sleep they
    # call through instead — keeps these tests from taking real seconds.
    monkeypatch.setattr("src.fallback.retry.time.sleep", lambda _: None)


def test_is_transient_status():
    assert is_transient_status(500) is True
    assert is_transient_status(503) is True
    assert is_transient_status(599) is True
    assert is_transient_status(400) is False
    assert is_transient_status(404) is False
    assert is_transient_status(429) is False  # rate-limit: not in the 5xx band
    assert is_transient_status(None) is False


def test_retry_with_jitter_succeeds_without_retry_when_first_call_works():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    result = retry_with_jitter(fn, is_transient=lambda exc: True, sleep=lambda _: None)
    assert result == "ok"
    assert len(calls) == 1


def test_retry_with_jitter_retries_transient_failures_up_to_max_attempts():
    attempts = []

    def fn():
        attempts.append(1)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        retry_with_jitter(
            fn, is_transient=lambda exc: True, max_attempts=3, sleep=lambda _: None
        )

    assert len(attempts) == 3  # exhausted all 3 attempts, then re-raised


def test_retry_with_jitter_succeeds_on_a_later_attempt():
    attempts = []

    def fn():
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("transient blip")
        return "recovered"

    result = retry_with_jitter(
        fn, is_transient=lambda exc: True, max_attempts=3, sleep=lambda _: None
    )
    assert result == "recovered"
    assert len(attempts) == 3


def test_retry_with_jitter_does_not_retry_non_transient_failures():
    attempts = []

    def fn():
        attempts.append(1)
        raise ValueError("permanent, not worth retrying")

    with pytest.raises(ValueError):
        retry_with_jitter(
            fn, is_transient=lambda exc: False, max_attempts=3, sleep=lambda _: None
        )

    assert len(attempts) == 1  # failed fast, no retries


def test_retry_with_jitter_sleeps_are_bounded_and_nonnegative():
    sleeps = []

    def fn():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        retry_with_jitter(
            fn,
            is_transient=lambda exc: True,
            max_attempts=3,
            base_delay=1.0,
            max_delay=4.0,
            sleep=sleeps.append,
        )

    assert len(sleeps) == 2  # slept between attempts 1->2 and 2->3, not after the last
    assert all(0 <= s <= 4.0 for s in sleeps)


def _anthropic_status_error(status_code: int) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request, json={"error": {"type": "x"}})
    return anthropic.APIStatusError("boom", response=response, body={"error": {"type": "x"}})


def _openai_status_error(status_code: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code, request=request, json={"error": {}})
    return openai.APIStatusError("boom", response=response, body={"error": {}})


def test_call_anthropic_with_retry_retries_5xx_then_raises_user_safe_message():
    call_count = 0

    def fn():
        nonlocal call_count
        call_count += 1
        raise _anthropic_status_error(503)

    with pytest.raises(ProviderCallFailedError) as exc_info:
        call_anthropic_with_retry(fn)

    assert call_count == 3  # retried transient failures to the max
    err = exc_info.value
    assert err.retried is True
    assert "temporarily unavailable" in err.user_message
    # Never leak the raw SDK exception text (would include response internals).
    assert "APIStatusError" not in err.user_message


def test_call_anthropic_with_retry_fails_fast_on_404_bad_model():
    call_count = 0

    def fn():
        nonlocal call_count
        call_count += 1
        raise _anthropic_status_error(404)

    with pytest.raises(ProviderCallFailedError) as exc_info:
        call_anthropic_with_retry(fn)

    assert call_count == 1  # no retries for a non-transient client error
    err = exc_info.value
    assert err.retried is False
    assert "configuration" in err.user_message


def test_call_anthropic_with_retry_treats_connection_error_as_transient():
    call_count = 0

    def fn():
        nonlocal call_count
        call_count += 1
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.APIConnectionError(request=request)

    with pytest.raises(ProviderCallFailedError) as exc_info:
        call_anthropic_with_retry(fn)

    assert call_count == 3
    assert exc_info.value.retried is True


def test_call_openai_with_retry_retries_5xx_then_raises_user_safe_message():
    call_count = 0

    def fn():
        nonlocal call_count
        call_count += 1
        raise _openai_status_error(500)

    with pytest.raises(ProviderCallFailedError) as exc_info:
        call_openai_with_retry(fn)

    assert call_count == 3
    assert exc_info.value.retried is True
    assert "OpenAI" in exc_info.value.user_message


def test_call_with_retry_succeeds_after_transient_failures_returns_real_result():
    mock_response = MagicMock()
    attempts = []

    def fn():
        attempts.append(1)
        if len(attempts) < 2:
            raise _anthropic_status_error(502)
        return mock_response

    result = call_anthropic_with_retry(fn)
    assert result is mock_response
    assert len(attempts) == 2
