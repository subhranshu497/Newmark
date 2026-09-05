"""Health check endpoint for uptime/status monitoring."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: str


@router.get("/health", response_model=HealthOut)
async def get_health() -> HealthOut:
    return HealthOut(status="up")
