"""Shared FastAPI dependencies: DB session and caller identity.

Principal resolution here is a placeholder that reads headers already set
by the platform's existing AuthN/AuthZ gateway (design doc §6 — API
Gateway -- AuthN (OIDC) -- AuthZ). This service trusts those headers rather
than re-implementing authentication, consistent with Constitution I (no
new synchronous dependency on a core service).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import get_session_factory
from src.policy.team_scope import Principal


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_principal(
    x_user_id: str = Header(...),
    x_team_id: str = Header(...),
    x_is_admin: bool = Header(default=False),
) -> Principal:
    try:
        return Principal(
            user_id=uuid.UUID(x_user_id), team_id=uuid.UUID(x_team_id), is_admin=x_is_admin
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid caller identity headers") from exc
