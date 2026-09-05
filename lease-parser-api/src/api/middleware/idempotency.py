"""Idempotency-Key middleware (T021, contracts/api.md cross-cutting).

Consistent with the platform-wide convention (design doc §4.8): state-
changing endpoints accept an `Idempotency-Key` header; a replay with the
same key returns the original response rather than double-processing
(e.g. double-verifying a field or double-resolving a queue item).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_IDEMPOTENT_METHODS = {"POST"}


class InMemoryIdempotencyStore:
    """Minimal store: {key: (status_code, body, media_type)}.

    Production deployments should back this with a shared store (e.g. the
    lease_abstraction schema or Redis) so idempotency holds across
    process restarts and multiple replicas — swap via the `store` argument.
    """

    def __init__(self) -> None:
        self._entries: dict[str, tuple[int, bytes, str]] = {}

    def get(self, key: str) -> tuple[int, bytes, str] | None:
        return self._entries.get(key)

    def put(self, key: str, status_code: int, body: bytes, media_type: str) -> None:
        self._entries[key] = (status_code, body, media_type)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, store: InMemoryIdempotencyStore | None = None) -> None:
        super().__init__(app)
        self._store = store or InMemoryIdempotencyStore()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in _IDEMPOTENT_METHODS:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)

        cache_key = f"{request.url.path}:{key}"
        cached = self._store.get(cache_key)
        if cached is not None:
            status_code, body, media_type = cached
            return Response(content=body, status_code=status_code, media_type=media_type)

        response = await call_next(request)
        body = b"".join([chunk async for chunk in response.body_iterator])
        media_type = response.media_type or "application/json"
        self._store.put(cache_key, response.status_code, body, media_type)
        return Response(
            content=body, status_code=response.status_code, media_type=response.media_type
        )
