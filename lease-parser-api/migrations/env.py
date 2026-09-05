"""Alembic migration environment for the lease_abstraction schema (T004)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config import get_settings
from src.models.db import SCHEMA_NAME, Base, make_engine

# Import all model modules so their tables register on Base.metadata.
from src.models import (  # noqa: F401
    accuracy_metric,
    baseline_measurement,
    extracted_field,
    lease_document,  # also defines ExtractionRun
    override_rate_metric,
    review_queue_item,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_settings().database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        version_table_schema=SCHEMA_NAME,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=SCHEMA_NAME,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = make_engine()
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
