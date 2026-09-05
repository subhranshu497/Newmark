"""Unit tests for information-barrier enforcement (T047 audit fix, FR-018)."""

from __future__ import annotations

import uuid

import pytest

from src.policy.team_scope import (
    InformationBarrierError,
    Principal,
    enforce_team_scope,
    enforce_team_scope_with_admin_audit,
)


def test_enforce_team_scope_allows_matching_team():
    team_id = uuid.uuid4()
    principal = Principal(user_id=uuid.uuid4(), team_id=team_id)
    enforce_team_scope(principal, [team_id])  # does not raise


def test_enforce_team_scope_blocks_non_admin_outside_team():
    principal = Principal(user_id=uuid.uuid4(), team_id=uuid.uuid4())
    with pytest.raises(InformationBarrierError):
        enforce_team_scope(principal, [uuid.uuid4()])


def test_enforce_team_scope_never_bypasses_for_admin():
    """Strict variant: even an admin is blocked (used by write endpoints)."""
    principal = Principal(user_id=uuid.uuid4(), team_id=uuid.uuid4(), is_admin=True)
    with pytest.raises(InformationBarrierError):
        enforce_team_scope(principal, [uuid.uuid4()])


def test_admin_audit_variant_allows_admin_and_logs(caplog):
    principal = Principal(user_id=uuid.uuid4(), team_id=uuid.uuid4(), is_admin=True)
    resource_id = uuid.uuid4()

    with caplog.at_level("WARNING", logger="lease_abstraction.audit"):
        enforce_team_scope_with_admin_audit(principal, [uuid.uuid4()], "review_queue", resource_id)

    assert any("admin_information_barrier_override" in record.message for record in caplog.records)
    assert any(str(resource_id) in record.message for record in caplog.records)


def test_admin_audit_variant_still_blocks_non_admin():
    principal = Principal(user_id=uuid.uuid4(), team_id=uuid.uuid4(), is_admin=False)
    with pytest.raises(InformationBarrierError):
        enforce_team_scope_with_admin_audit(principal, [uuid.uuid4()], "review_queue", uuid.uuid4())
