"""FastAPI application entry point, wiring routers and cross-cutting middleware."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.extracted_fields import router as extracted_fields_router
from src.api.metrics import router as metrics_router
from src.api.middleware.idempotency import IdempotencyMiddleware
from src.api.review_queue import router as review_queue_router

app = FastAPI(title="lease-abstraction", version="0.1.0")
app.add_middleware(IdempotencyMiddleware)

app.include_router(extracted_fields_router)
app.include_router(review_queue_router)
app.include_router(metrics_router)
