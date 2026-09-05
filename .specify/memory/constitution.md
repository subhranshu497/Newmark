<!--
Sync Impact Report
- Version change: [TEMPLATE] → 1.0.0 (initial ratification)
- Modified principles: n/a (first authored version; template placeholders replaced)
- Added sections:
  - Core Principles I–VI (Additive/Non-Blocking AI Layer; Human-Verified Data Is Authoritative;
    Determinism for Money and Legal Records; Graceful Degradation, Never Outage; Manual Entry Is
    Permanently Available; Operational Readiness and Measurable Trust)
  - Scope Constraints (Section 2)
  - Development Workflow (Section 3)
  - Governance
- Removed sections: none
- Templates requiring updates:
  - .specify/templates/plan-template.md — no changes required (Constitution Check section reads this file at runtime)
  - .specify/templates/spec-template.md — no changes required
  - .specify/templates/tasks-template.md — no changes required
  - .specify/templates/checklist-template.md — no changes required
- Follow-up TODOs:
  - TODO(CONFIDENCE_THRESHOLDS): Per-field confidence thresholds referenced in Principle II are not
    yet calibrated (README.md §7 — "Confidence threshold calibration" requires a labeled evaluation
    set that does not yet exist). Track resolution in the lease-abstraction feature spec.
  - TODO(SCAN_QUALITY_FLOOR): OCR quality floor referenced in Principle IV is not yet established
    empirically (README.md §7 — "Scan quality floor").
-->

# Newmark AI Layer for Commercial Leasing Constitution

## Core Principles

### I. Additive, Non-Blocking AI Layer
No core transaction — deal state transition, commission calculation, document upload, or search
request — MAY call an AI/ML inference synchronously and block on its response. AI outputs
(extraction results, semantic match rankings) are produced asynchronously and merged into records
that already exist. The AI layer reads from the existing event stream and writes suggestions back;
it is never in the write path of a core transaction.

**Rationale**: The useful comparison is a water filter fitted under a kitchen sink rather than
spliced into the building's main line. If the filter clogs, water still reaches the tap. If the AI
layer fails, the leasing platform must continue operating exactly as it does today (README §5.3).

### II. Human-Verified Data Is Authoritative
Once a field is confirmed by a person, it is the record. Reprocessing, model upgrades, and pipeline
reruns MUST NOT overwrite a verified value under any circumstance. Every extracted field carries
provenance — model version, confidence score, verifying user, timestamp — stored alongside the
value. Fields above the calibrated confidence threshold populate automatically; fields below it
route to a human review queue (threshold values: TODO(CONFIDENCE_THRESHOLDS)).

**Rationale**: The analyst's role changes from transcription to verification, and that verification
step is a permanent design feature, not a temporary safeguard during rollout (README §5.1, §6.2).

### III. Determinism for Money and Legal Records
Commission calculations and deal audit records MUST be reconstructable years after close, frequently
in a dispute or litigation context. Model outputs are not reproducible across versions and MUST NOT
be treated as the record. The pipeline proposes; a person confirms; the confirmed value enters the
legal record with its provenance attached. This is a deliberate, permanent constraint on the design,
not a limitation to be engineered away in a later phase.

**Rationale**: A commission split or lease term that cannot be reproduced on demand is not
auditable, and brokers act as fiduciaries whose disputes are litigated years after close (README
§6.3).

### IV. Graceful Degradation, Never Outage
The platform MUST degrade to today's manual process; it MUST NOT degrade to a system outage. This
applies at minimum to the following failure modes:

- Extraction service unavailable → documents queue for later processing; the deal record accepts
  manual entry.
- Extraction degraded or slow → a circuit breaker opens after an explicit threshold; the queue
  drains on recovery; half-open probes test recovery before full traffic resumes.
- Confidence uniformly low → all fields route to review; accuracy is unaffected.
- Semantic ranking unavailable → fall back to structured filters and keyword ranking.
- Embedding index stale or corrupt → serve the last known good, versioned index; rebuild in the
  background.
- Model provider outage → fail over to a secondary provider; if both fail, fall back to full manual
  mode.

Supporting these fallbacks, documents awaiting extraction MUST persist in a durable queue with retry
and dead-letter handling — an outage delays processing, it never drops work. The OCR quality floor
below which documents are excluded from automated processing is empirically established, not assumed
(TODO(SCAN_QUALITY_FLOOR)).

**Rationale**: Nothing downstream (commission, comparables, portfolio reporting) may become
unavailable because an AI dependency failed (README §6, §6.1, §6.2).

### V. Manual Entry Is Permanently Available
Every field the extraction pipeline can populate MUST remain editable by hand, permanently. This is
the standing behavior of the form at all times, not a fallback mode that gets switched on during an
incident.

**Rationale**: Brokers must never be blocked from closing a deal by an AI-layer failure, and treating
manual entry as a first-class permanent path (rather than an emergency-only path) is what keeps it
reliable when it is actually needed (README §6.2).

### VI. Operational Readiness and Measurable Trust
Extraction accuracy MUST be monitored per field type against a labeled holdout set, with alerting on
drift. Human override rate MUST be tracked as a leading indicator of model degradation. Every model
version MUST be recorded per extraction, enabling audit and targeted reprocessing. Manual-mode
operation MUST be exercised on a schedule so the fallback path is known to work before it is needed.

**Rationale**: Trust in an automated extraction is only as good as the ability to detect when it is
degrading, and an untested fallback path is not a real fallback path (README §6.4).

## Scope Constraints

The AI layer covers exactly two capabilities: (1) lease abstraction — OCR → extraction → per-field
confidence → human review queue → structured lease terms, and (2) semantic requirement matching —
hard structured filters followed by meaning-based ranking against listing descriptions. Both
capabilities share one underlying dataset and consume from the existing event stream (README §5).
Any feature outside these two capabilities (inventory, deal lifecycle, document storage, commission
engine as core services) is out of scope for this constitution and is governed separately if and
when specified.

## Development Workflow

Every AI-layer feature MUST proceed through the Spec Kit pipeline before implementation is
considered complete: `/speckit-specify` (business-facing spec) → `/speckit-clarify` (resolve
open ambiguities, e.g. confidence calibration and scan quality floor) → `/speckit-plan` (technical
design, including the provenance data model required by Principle II) → `/speckit-tasks` →
`/speckit-implement`. Before implementation is treated as complete, either `/speckit-analyze` (pre-
implementation) or `/speckit-converge` (post-implementation) MUST be run to check the artifacts or
codebase against this constitution; any finding that violates a MUST principle above is CRITICAL and
blocks sign-off until resolved.

## Governance

This constitution supersedes ad hoc engineering decisions for the AI layer described in Scope
Constraints above. Amendments require: an updated version of this document, a Sync Impact Report
describing what changed and why, and a semantic version bump (MAJOR for backward-incompatible
principle removal/redefinition, MINOR for new principles or materially expanded guidance, PATCH for
clarifications). Compliance is verified per feature via `/speckit-analyze` or `/speckit-converge`
rather than manual review alone.

**Version**: 1.0.0 | **Ratified**: 2026-09-05 | **Last Amended**: 2026-09-05
