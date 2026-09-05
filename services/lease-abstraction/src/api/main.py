"""FastAPI application entry point, wiring routers and cross-cutting middleware."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.extracted_fields import router as extracted_fields_router
from src.api.metrics import router as metrics_router
from src.api.middleware.idempotency import IdempotencyMiddleware
from src.api.review_queue import router as review_queue_router
from src.config import get_settings

app = FastAPI(title="lease-abstraction", version="0.1.0")
app.add_middleware(IdempotencyMiddleware)

app.include_router(extracted_fields_router)
app.include_router(review_queue_router)
app.include_router(metrics_router)

if get_settings().enable_demo_ui:
    from fastapi.middleware.cors import CORSMiddleware

    from src.api.demo_seed import router as demo_router

    # lease-parser-ui (Newmark/lease-parser-ui) is a standalone frontend on its
    # own origin, not served by this app — needs CORS to call these endpoints.
    # Only added under the same demo flag, so a real deployment never opens this up.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(demo_router)
