# Implementation Plan: Lease Abstraction

**Branch**: `001-lease-abstraction` | **Date**: 2026-09-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-lease-abstraction/spec.md`

## Summary

Build a standalone lease-abstraction service that consumes uploaded lease documents from the
existing platform's event stream, runs a two-stage OCR → LLM-extraction pipeline to produce
per-field structured lease terms with confidence scores, auto-populates the deal record for
high-confidence fields, and routes low-confidence fields to a team-scoped human review queue.
Verified values are permanently authoritative. The service is additive: it never sits on the
synchronous path of any core deal, commission, or search operation (Constitution I), and it
degrades to fully-manual entry rather than causing an outage (Constitution IV).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI (service API), a Kafka client (e.g. `confluent-kafka`) for
consuming `document.uploaded` and producing `lease.extraction.completed`, an OCR provider SDK
(AWS Textract, chosen for native per-page/per-block confidence scores — see research.md), an
Anthropic Claude client for the LLM extraction step, SQLAlchemy + `asyncpg` for PostgreSQL access,
Pydantic for schema/contract validation, `pybreaker` for circuit-breaker logic.

**Storage**: PostgreSQL — a dedicated `lease_abstraction` schema/database, decoupled from the core
Deal service's schema (Constitution I: additive, not embedded in the core transactional path).
Cross-service references (`dealId`, `teamId`) are stored as opaque IDs, validated against event
payloads at write time — no cross-service foreign-key constraints, since this is a separate bounded
context.

**Testing**: pytest (unit, contract, integration), with a labeled holdout fixture set for extraction
accuracy tests (Constitution VI / User Story 3).

**Target Platform**: Linux containers, deployed as an independent microservice alongside the other
bounded contexts described in `commercial-brokerage-platform-design.md` §6.

**Project Type**: Single web-service (backend only — no dedicated frontend; the review queue is
surfaced through the existing broker SPA via this service's API, per FR-006).

**Performance Goals**: No synchronous latency SLA (FR-014 forbids synchronous coupling). Queue-drain
time and per-document processing time are operational SLOs tracked via monitoring (User Story 3),
not hard real-time targets in this plan.

**Constraints**: Non-blocking on the core write path (FR-014); durable queue with retry/dead-letter
(FR-010); circuit breaker with explicit thresholds (FR-011); provider failover before manual fallback
(FR-012); verified fields immutable once confirmed (FR-008); row-level information-barrier
enforcement on all review-queue reads (FR-018); OCR/extraction thresholds re-calibratable without a
code deploy (FR-004, FR-013).

**Scale/Scope**: Live path scoped to ongoing new lease uploads (a small fraction of the platform's
~500 TPS deal-write volume, which is dominated by activity logging, not document uploads). Backfill
scope is tens of thousands of historical leases, processed on an isolated path (FR-017) and excluded
from this plan's live-path capacity assumptions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Additive, Non-Blocking AI Layer | Service is a separate microservice; consumes `document.uploaded` via Kafka, produces `lease.extraction.completed`; no endpoint here is called synchronously by the Deal, Commission, or Search services. | PASS |
| II. Human-Verified Data Is Authoritative | `ExtractedField.verificationStatus` transitions to `VERIFIED`/`OVERRIDDEN` are terminal; application layer rejects any write attempting to change a verified field's value (enforced in data-model.md + contracts). | PASS |
| III. Determinism for Money and Legal Records | This service does not calculate commission; it only produces provenance-tagged Structured Lease Terms for the (out-of-scope) Deal/Commission services to consume. Provenance (`modelVersion`, `confidenceScore`, `verifiedBy`, `verifiedAt`) is stored on every field. | PASS |
| IV. Graceful Degradation, Never Outage | Kafka consumer group with dead-letter topic (durable queue); `pybreaker` circuit breaker around both OCR and LLM calls; secondary-provider failover documented in research.md; manual entry is a capability of the (out-of-scope) Deal service's form, not owned here — this plan's contracts must not require this service to be available for manual entry to work. | PASS |
| V. Manual Entry Is Permanently Available | Owned by the Deal service (out of scope here); this plan's integration contract explicitly does not gate deal-record field editability on this service's availability. | PASS (external dependency noted) |
| VI. Operational Readiness and Measurable Trust | `AccuracyMetricSnapshot` and `OverrideRateMetric` entities + `/v1/metrics/*` endpoints implement User Story 3 directly. | PASS |

No violations. Complexity Tracking table is not applicable.

## Project Structure

### Documentation (this feature)

```text
specs/001-lease-abstraction/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── api.md
│   └── events.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
services/lease-abstraction/
├── src/
│   ├── api/              # FastAPI routers: review-queue, extracted-fields, metrics
│   ├── ocr/               # OCR provider adapter (Textract) + confidence normalization
│   ├── extraction/        # LLM extraction adapter (Claude) + per-field confidence scoring
│   ├── models/            # SQLAlchemy models: LeaseDocument, ExtractedField, ReviewQueueItem,
│   │                       # ExtractionRun, AccuracyMetricSnapshot, OverrideRateMetric,
│   │                       # BaselineMeasurement
│   ├── consumers/         # Kafka consumers/producers (document.uploaded → lease.extraction.completed)
│   ├── queue/              # Durable job orchestration, retry/dead-letter, circuit breaker
│   ├── policy/             # Team-scoped / information-barrier authorization checks
│   └── monitoring/         # Accuracy drift + override-rate computation (User Story 3)
└── tests/
    ├── contract/            # Validates api.md / events.md against implementation
    ├── integration/         # End-to-end: upload event → extraction → review queue → verify
    └── unit/
```

**Structure Decision**: Single project (Option 1), scoped to one independently deployable service.
This matches Constitution Scope Constraints (AI layer = exactly two capabilities, lease abstraction
being one) and Constitution I (must remain separable from core services, not a module inside them).

## Complexity Tracking

*No Constitution Check violations — table not applicable.*
