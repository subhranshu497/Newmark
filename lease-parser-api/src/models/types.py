"""Cross-dialect column types.

Production runs against PostgreSQL (plan.md Storage); the test suite runs
against an in-memory SQLite database so it can execute without live
infrastructure. These TypeDecorators store the Postgres-native
representation in production and a portable equivalent under SQLite, while
always presenting the same Python type (uuid.UUID / list[uuid.UUID]) to
application code.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CHAR, JSON, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class GUID(TypeDecorator):
    """Platform-independent UUID: native UUID on Postgres, CHAR(32) elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return str(value)
        return uuid.UUID(str(value)).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(value)


class UUIDArray(TypeDecorator):
    """Platform-independent array of UUIDs: native ARRAY on Postgres, JSON elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(PG_UUID(as_uuid=True)))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return [uuid.UUID(str(v)) for v in value]
        return [str(v) for v in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return [v if isinstance(v, uuid.UUID) else uuid.UUID(v) for v in value]
