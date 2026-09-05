"""Transient-failure handling for the two extraction providers, built on
src/fallback/retry.py. src/extraction/claude_adapter.py and
src/extraction/failover.py call `call_anthropic_with_retry` /
`call_openai_with_retry` instead of the SDK client methods directly, so a
5xx from either provider gets a few bounded retries before the request is
given up on — and, when it is given up on, the caller gets a message that's
safe to show an end user rather than a raw SDK exception string.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import anthropic
import openai

from src.fallback.retry import is_transient_status, retry_with_jitter

T = TypeVar("T")


class ProviderCallFailedError(RuntimeError):
    """Raised once a provider call has exhausted retries, or failed with a
    non-transient error not worth retrying at all.

    `user_message` is safe to surface directly to an end user — it never
    includes raw provider error text, which may reference internal
    identifiers or be confusing outside an engineering context. `retried`
    tells the caller whether this was a transient failure (retries were
    attempted and exhausted) or a non-transient one (failed fast, e.g. a bad
    model name or invalid API key — retrying would not have helped).
    """

    def __init__(self, user_message: str, *, retried: bool, cause: Exception) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.retried = retried
        self.__cause__ = cause


def _is_transient_anthropic_error(exc: Exception) -> bool:
    if isinstance(exc, anthropic.APIConnectionError):
        return True  # network blip — never got a response to read a status from
    if isinstance(exc, anthropic.APIStatusError):
        return is_transient_status(exc.status_code)
    return False


def _is_transient_openai_error(exc: Exception) -> bool:
    if isinstance(exc, openai.APIConnectionError):
        return True
    if isinstance(exc, openai.APIStatusError):
        return is_transient_status(exc.status_code)
    return False


def call_anthropic_with_retry(fn: Callable[[], T]) -> T:
    return _call_with_retry(fn, _is_transient_anthropic_error, provider_label="Claude")


def call_openai_with_retry(fn: Callable[[], T]) -> T:
    return _call_with_retry(fn, _is_transient_openai_error, provider_label="OpenAI")


def _call_with_retry(
    fn: Callable[[], T], is_transient: Callable[[Exception], bool], *, provider_label: str
) -> T:
    try:
        return retry_with_jitter(fn, is_transient=is_transient)
    except Exception as exc:  # noqa: BLE001 - translated to a user-facing message below
        if is_transient(exc):
            message = (
                f"The {provider_label} extraction service is temporarily unavailable "
                "after multiple attempts. Please try again shortly."
            )
            raise ProviderCallFailedError(message, retried=True, cause=exc) from exc
        message = (
            f"The {provider_label} extraction request failed and won't succeed on retry. "
            "Please check the service configuration (model name, API key) and try again."
        )
        raise ProviderCallFailedError(message, retried=False, cause=exc) from exc
