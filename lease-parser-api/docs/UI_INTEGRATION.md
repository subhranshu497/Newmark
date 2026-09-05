# UI Integration Tracking: Review Queue (T030)

**Status**: Pending — not started. Requires engagement with the team that owns the broker
deal-management SPA (out of scope for this service; tracked here so it isn't silently dropped).

## Requirement

FR-006 (spec.md): "The review queue MUST be reachable from within the tool analysts already use
for deal management, without requiring a separate application." SC-004 depends on this directly:
"A person can locate and complete every item in the review queue without leaving the
deal-management tool."

## Why this is tracked separately

This service (`lease-parser-api`) is backend-only per plan.md's Project Structure — it
exposes the review queue as a REST API (contracts/api.md) but does not own any UI. `/speckit-analyze`
flagged (finding A3) that without an explicit tracking task, this requirement could fall through the
cracks between this service's team and whichever team owns the broker SPA.

## What the consuming team needs

- `GET /v1/review-queue?teamId={teamId}&status=PENDING` — list pending items for the caller's team
- `POST /v1/review-queue/{itemId}/resolve` — submit a corrected value for an item
- `GET /v1/lease-documents/{documentId}/extracted-fields` — view auto-populated fields for a document
- `POST /v1/lease-documents/{documentId}/extracted-fields/{fieldId}/verify` — confirm or override a field

All endpoints require `X-User-Id` / `X-Team-Id` headers (or the platform's equivalent identity
propagation) and enforce the same team-based information barrier as the Deal service (FR-018).

## Next step

Open a ticket with the broker-SPA team referencing this document and `contracts/api.md`, requesting
a review-queue view be added to the existing deal-management tool. This service's API is ready to
be integrated against as of Phase 4 completion.
