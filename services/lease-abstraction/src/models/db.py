"""Database engine/session setup and Alembic migration entry point (T004).

Schema is `lease_abstraction` — a dedicated schema, separate from the core
Deal service's schema (Constitution I: additive, not embedded in the core
transactional path). Cross-service references (dealId, teamId, allowedTeams)
are stored as opaque values sourced from event payloads, never as
cross-database foreign keys (plan.md Storage).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings

# Postgres-schema-qualified tables in production; SQLite (used by the test
# suite) has no equivalent concept, so tests run schema-less against an
# in-memory database instead.
SCHEMA_NAME = "lease_abstraction" if "postgresql" in get_settings().database_url else None


class Base(DeclarativeBase):
    """Declarative base for all lease-abstraction models, scoped to its own schema."""

    metadata_schema = SCHEMA_NAME


def qualified(table_name: str) -> str:
    """Return a schema-qualified table reference for ForeignKey(...) targets.

    Schema-qualifies under Postgres (`lease_abstraction.lease_documents.id`);
    returns the bare reference under SQLite, which has no schema concept.
    """
    return f"{SCHEMA_NAME}.{table_name}" if SCHEMA_NAME else table_name


def make_engine(database_url: str | None = None):
    settings = get_settings()
    return create_async_engine(database_url or settings.database_url, pool_pre_ping=True)


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a transactional scope for a series of operations."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    """Create all tables. Used by local/dev bootstrap and by the test suite;
    production schema changes go through Alembic migrations instead."""
    async with get_engine().begin() as conn:
        if SCHEMA_NAME:
            from sqlalchemy import text

            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
        await conn.run_sync(Base.metadata.create_all)
