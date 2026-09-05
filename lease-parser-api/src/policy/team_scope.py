"""Information-barrier / row-level policy check (T007, FR-018).

Reuses the Deal service's row-level policy shape
(`principal.teamId ∈ deal.sides[side].allowedTeams`, design doc §7.2)
rather than calling back into the Deal service synchronously, which would
violate Constitution I. `allowedTeams` arrives on this service's own rows
(LeaseDocument, ReviewQueueItem) via the `document.uploaded` event payload.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

logger = logging.getLogger("lease_abstraction.audit")


class InformationBarrierError(PermissionError):
    """Raised when a caller's team is not in a resource's allowed-teams set."""


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, as resolved by the platform's existing AuthN layer."""

    user_id: uuid.UUID
    team_id: uuid.UUID
    is_admin: bool = False


def enforce_team_scope(principal: Principal, allowed_teams: list[uuid.UUID]) -> None:
    """Raise InformationBarrierError unless the principal's team is permitted.

    Strict — no admin bypass. Use `enforce_team_scope_with_admin_audit` for
    endpoints where an organization-wide admin view is a legitimate use
    case (design doc §7.2 permits admin reads, but only with an audit
    trail; this function has no way to record one, so it never bypasses).
    """
    if principal.team_id not in allowed_teams:
        raise InformationBarrierError(
            f"team {principal.team_id} is not in the allowed set for this resource"
        )


def enforce_team_scope_with_admin_audit(
    principal: Principal, allowed_teams: list[uuid.UUID], resource_type: str, resource_id: uuid.UUID
) -> None:
    """Same barrier as `enforce_team_scope`, but an admin principal may cross
    it — with every crossing written to the audit log (FR-018, design doc
    §7.2: "A barrier flag ... restricts even organization-wide
    administrative reads; all such access is written to the audit log").

    T047 audit finding: every endpoint that lets an admin view another
    team's resource MUST call this (not the plain `enforce_team_scope`,
    and not an ad-hoc `or principal.is_admin` check) so the bypass is
    always logged, never silent.
    """
    if principal.team_id in allowed_teams:
        return
    if principal.is_admin:
        logger.warning(
            "admin_information_barrier_override user_id=%s resource_type=%s resource_id=%s",
            principal.user_id,
            resource_type,
            resource_id,
        )
        return
    raise InformationBarrierError(
        f"team {principal.team_id} is not in the allowed set for this resource"
    )
