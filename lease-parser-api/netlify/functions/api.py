"""Netlify Function entry point: adapts the FastAPI app to Lambda-style invocation.

Netlify's Python functions runtime is AWS-Lambda-compatible, so Mangum
(built for wrapping ASGI apps for API Gateway/Lambda events) works here too.
"""

from __future__ import annotations

from mangum import Mangum

from src.api.main import app

handler = Mangum(app, lifespan="off")
