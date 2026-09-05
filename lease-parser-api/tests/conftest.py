"""Shared pytest fixtures.

Sets the DB URL to an in-memory SQLite database *before* any `src.*` module
is imported, since `src.models.db` resolves `SCHEMA_NAME` at import time
from settings. This lets the same models run against SQLite for tests and
PostgreSQL in production (src/models/types.py) without a live Postgres
instance in this environment.
"""

from __future__ import annotations

import os

os.environ.setdefault("LEASE_ABSTRACTION_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LEASE_ABSTRACTION_ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("LEASE_ABSTRACTION_OPENAI_API_KEY", "test-key")

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.models.db import Base
from src.policy.team_scope import Principal


@pytest_asyncio.fixture
async def engine():
    # StaticPool keeps a single underlying connection alive so the
    # in-memory database persists across the multiple sessions each test
    # (and each simulated HTTP request) opens against it.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture
async def app_client(engine) -> AsyncIterator[AsyncClient]:
    from src.api.deps import get_principal, get_session
    from src.api.main import app

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_session_override() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    default_principal = Principal(user_id=uuid.uuid4(), team_id=uuid.uuid4())

    app.dependency_overrides[get_session] = _get_session_override
    app.dependency_overrides[get_principal] = lambda: default_principal

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.default_principal = default_principal  # type: ignore[attr-defined]
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def make_principal():
    def _make(team_id: uuid.UUID | None = None, is_admin: bool = False) -> Principal:
        return Principal(user_id=uuid.uuid4(), team_id=team_id or uuid.uuid4(), is_admin=is_admin)

    return _make
