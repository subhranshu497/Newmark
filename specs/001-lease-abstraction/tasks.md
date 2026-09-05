# Tasks: Lease Abstraction

**Input**: Design documents from `/specs/001-lease-abstraction/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — plan.md commits to a `tests/{contract,integration,unit}` structure and quickstart.md runs pytest against it, so contract/integration coverage is treated as required, not optional.

**Organization**: Tasks are grouped by user story (P1 → P2 → P3) so each is independently implementable, testable, and shippable.

**Remediation note (2026-09-05)**: This file was updated after `/speckit-analyze` to resolve findings A1–A4 (see `Notes` at the bottom). Task IDs below are renumbered from the original generation — nothing had started implementation, so renumbering was safe.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, or US3 — maps to spec.md's user stories

## Path Conventions

Single project, per plan.md: `services/lease-abstraction/src/`, `services/lease-abstraction/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `services/lease-abstraction/` skeleton (`src/{api,ocr,extraction,models,consumers,queue,policy,monitoring}`, `tests/{contract,integration,unit}`) per plan.md Project Structure
- [X] T002 Initialize Python 3.12 project in `services/lease-abstraction/pyproject.toml` with dependencies: fastapi, sqlalchemy, asyncpg, pydantic, confluent-kafka, pybreaker, anthropic, openai, boto3 (research.md)
- [X] T003 [P] Configure linting/formatting (ruff, black) and pytest config in `services/lease-abstraction/pyproject.toml`

**Checkpoint**: Project scaffold in place.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Set up `lease_abstraction` PostgreSQL schema and Alembic migrations framework in `services/lease-abstraction/src/models/db.py` per data-model.md
- [X] T005 [P] Create `LeaseDocument` and `ExtractionRun` models in `services/lease-abstraction/src/models/lease_document.py` (data-model.md)
- [X] T006 [P] Implement Kafka consumer/producer scaffolding in `services/lease-abstraction/src/consumers/base.py` for `document.uploaded`, `lease.extraction.completed`, `lease.extraction.dead-letter` (contracts/events.md)
- [X] T007 [P] Implement information-barrier policy check (`caller.teamId ∈ allowedTeams`) in `services/lease-abstraction/src/policy/team_scope.py` (FR-018, data-model.md authorization rule)
- [X] T008 [P] Implement circuit breaker wrapper (pybreaker) for external OCR/LLM calls in `services/lease-abstraction/src/queue/circuit_breaker.py` (FR-011, research.md)
- [X] T009 Implement environment/config management for OCR/LLM credentials and re-calibratable, per-field-type confidence/quality thresholds (FR-004, FR-013) in `services/lease-abstraction/src/config.py`

**Checkpoint**: Foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 - Verify Auto-Populated High-Confidence Fields (Priority: P1) 🎯 MVP

**Goal**: Upload a lease PDF → OCR → extraction → auto-populate high-confidence fields → analyst confirms or edits.

**Independent Test**: quickstart.md Scenario 1.

### Tests for User Story 1

- [X] T010 [P] [US1] Contract test for extracted-fields endpoints (GET + verify) in `services/lease-abstraction/tests/contract/test_extracted_fields_api.py` (contracts/api.md)
- [X] T011 [P] [US1] Integration test for quickstart Scenario 1 (upload → auto-populate → confirm → re-verify rejected) in `services/lease-abstraction/tests/integration/test_auto_populate_flow.py`

### Implementation for User Story 1

- [X] T012 [P] [US1] Create `ExtractedField` model with `verificationStatus` state machine in `services/lease-abstraction/src/models/extracted_field.py` (data-model.md)
- [X] T013 [US1] Implement OCR adapter (AWS Textract) returning text + per-block confidence, wrapped by the circuit breaker (T008) in `services/lease-abstraction/src/ocr/textract_adapter.py`
- [X] T014 [US1] Implement LLM extraction adapter (Anthropic Claude, primary) producing the 5 fields with confidence scores, wrapped by the circuit breaker (T008) in `services/lease-abstraction/src/extraction/claude_adapter.py`
- [X] T015 [US1] Implement secondary-provider (OpenAI) failover wrapping the extraction adapter — attempted before falling back to manual mode (FR-012, research.md) in `services/lease-abstraction/src/extraction/failover.py` (depends on T014). **Moved into the MVP phase per `/speckit-analyze` finding A2** — Constitution Principle IV lists provider failover as a required degradation behavior; it previously shipped only in Polish, after the MVP.
- [X] T016 [US1] Implement placeholder confidence-threshold policy, keyed per field type, conservative default, re-calibratable without deploy (FR-004) in `services/lease-abstraction/src/extraction/threshold_policy.py`
- [X] T017 [US1] Implement the `document.uploaded` consumer orchestrating OCR → extraction (with failover) → threshold-based auto-populate in `services/lease-abstraction/src/consumers/document_uploaded_consumer.py` (depends on T005, T006, T012, T013, T014, T015, T016)
- [X] T018 [US1] Implement `GET /v1/lease-documents/{documentId}/extracted-fields` in `services/lease-abstraction/src/api/extracted_fields.py` (depends on T012)
- [X] T019 [US1] Implement `POST /v1/lease-documents/{documentId}/extracted-fields/{fieldId}/verify` with the terminal-state guard (409 on already-verified) in `services/lease-abstraction/src/api/extracted_fields.py` (FR-008; depends on T012)
- [X] T020 [US1] Emit `lease.extraction.completed` on `ExtractionRun` completion in `services/lease-abstraction/src/consumers/document_uploaded_consumer.py` (depends on T017)
- [X] T021 [US1] Add `Idempotency-Key` handling middleware for state-changing endpoints in `services/lease-abstraction/src/api/middleware/idempotency.py` (contracts/api.md cross-cutting)

**Checkpoint**: User Story 1 fully functional and independently testable — this is the shippable MVP, now including provider failover (FR-012).

---

## Phase 4: User Story 2 - Work the Low-Confidence Review Queue (Priority: P2)

**Goal**: Below-threshold fields and excluded low-quality scans route to a team-scoped review queue instead of being dropped or silently wrong.

**Independent Test**: quickstart.md Scenario 2 (and Scenario 3 for the information-barrier check).

### Tests for User Story 2

- [X] T022 [P] [US2] Contract test for review-queue endpoints in `services/lease-abstraction/tests/contract/test_review_queue_api.py` (contracts/api.md)
- [X] T023 [P] [US2] Integration test for quickstart Scenarios 2 and 3 (review + resolve + information-barrier enforcement) in `services/lease-abstraction/tests/integration/test_review_queue_flow.py`

### Implementation for User Story 2

- [X] T024 [P] [US2] Create `ReviewQueueItem` model in `services/lease-abstraction/src/models/review_queue_item.py` (data-model.md)
- [X] T025 [US2] Extend the OCR adapter to route documents below the quality floor to `EXCLUDED_LOW_QUALITY` with a queue item (no `ExtractedField`) in `services/lease-abstraction/src/ocr/textract_adapter.py` (FR-013; depends on T013, T024)
- [X] T026 [US2] Extend the `document_uploaded_consumer` to create a `ReviewQueueItem` for every below-threshold field (FR-005) in `services/lease-abstraction/src/consumers/document_uploaded_consumer.py` (depends on T017, T024)
- [X] T027 [US2] Implement `GET /v1/review-queue` with team-scope filtering (FR-018) in `services/lease-abstraction/src/api/review_queue.py` (depends on T007, T024)
- [X] T028 [US2] Implement `POST /v1/review-queue/{itemId}/resolve` in `services/lease-abstraction/src/api/review_queue.py` (depends on T024, T019's terminal-state guard pattern)
- [X] T029 [US2] Guard reprocessing runs from creating queue items or extraction values for already-verified fields (FR-008) in `services/lease-abstraction/src/consumers/document_uploaded_consumer.py` (depends on T026)
- [X] T030 [US2] Coordinate with the broker-SPA/deal-management-tool owners to surface `GET /v1/review-queue` and the verify/resolve actions inside that existing tool, per FR-006/SC-004 (no separate application). **New per `/speckit-analyze` finding A3** — this feature is backend-only (plan.md), so this task exists to explicitly track the cross-team UI integration rather than let it fall through silently between teams. Tracked in `services/lease-abstraction/docs/UI_INTEGRATION.md` (status: pending, needs broker-SPA team engagement — this cannot be completed by this codebase alone).

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Monitor Extraction Accuracy and Degradation (Priority: P3)

**Goal**: Per-field accuracy against a labeled holdout set, override-rate trend, and model-version provenance are all visible; drift raises an alert.

**Independent Test**: quickstart.md's implied monitoring checks (accuracy report, override-rate trend visible).

### Tests for User Story 3

- [X] T031 [P] [US3] Contract test for metrics + baseline-measurement endpoints in `services/lease-abstraction/tests/contract/test_metrics_api.py` (contracts/api.md)
- [X] T032 [P] [US3] Integration test for accuracy-drift alerting in `services/lease-abstraction/tests/integration/test_accuracy_monitoring.py`

### Implementation for User Story 3

- [X] T033 [P] [US3] Create `AccuracyMetricSnapshot` model in `services/lease-abstraction/src/models/accuracy_metric.py` (data-model.md)
- [X] T034 [P] [US3] Create `OverrideRateMetric` model in `services/lease-abstraction/src/models/override_rate_metric.py` (data-model.md)
- [X] T035 [P] [US3] Create `BaselineMeasurement` model in `services/lease-abstraction/src/models/baseline_measurement.py` (FR-019)
- [X] T036 [US3] Implement holdout-set accuracy computation job in `services/lease-abstraction/src/monitoring/accuracy_job.py` (FR-015; depends on T033)
- [X] T037 [US3] Implement override-rate aggregation job reading `VERIFIED`/`OVERRIDDEN` transitions in `services/lease-abstraction/src/monitoring/override_rate_job.py` (FR-016; depends on T034)
- [X] T038 [US3] Implement drift alerting comparing measured accuracy to baseline in `services/lease-abstraction/src/monitoring/drift_alerts.py` (depends on T036)
- [X] T039 [US3] Implement `GET /v1/metrics/extraction-accuracy` in `services/lease-abstraction/src/api/metrics.py` (depends on T033)
- [X] T040 [US3] Implement `GET /v1/metrics/override-rate` in `services/lease-abstraction/src/api/metrics.py` (depends on T034)
- [X] T041 [US3] Implement `POST /v1/baseline-measurements` in `services/lease-abstraction/src/api/metrics.py` (FR-019; depends on T035)
- [X] T042 [US3] Conduct the baseline timing study: sample recent leases, measure current fully-manual abstraction time, and record the result via T041's endpoint (FR-019). **New per `/speckit-analyze` finding A4** — T041 only builds the recording endpoint; this task tracks actually performing the measurement, without which SC-001 cannot be validated. Tracked in `services/lease-abstraction/docs/BASELINE_STUDY.md` (status: pending, needs brokerage operations engagement — this cannot be completed by this codebase alone).

**Checkpoint**: All user stories independently functional.

---

## Final Phase: Polish & Cross-Cutting Concerns

- [X] T043 [P] Implement dead-letter consumer/alert hook for `lease.extraction.dead-letter` (FR-010) in `services/lease-abstraction/src/consumers/dead_letter_consumer.py`
- [X] T044 Implement the isolated bulk-backfill processing path: a separate Kafka consumer group and throttled batch job for `runType: BACKFILL` documents, kept independent from the live `document.uploaded` consumer group (T006) so backfill volume cannot contend with or delay live processing (FR-017). **New per `/speckit-analyze` finding A1** — previously only a `runType` enum value existed in data-model.md with no task actually implementing the isolation. Implemented in `src/consumers/backfill_consumer.py` (separate `lease-abstraction-backfill` consumer group + `RateLimiter`), contract documented in `contracts/events.md` (`document.backfill.requested`).
- [X] T045 Run quickstart.md Scenario 4 (degradation: OCR outage → circuit breaker → queue drains on recovery) end-to-end and record results. Automated as `tests/integration/test_degradation_scenario.py` rather than a one-off manual run.
- [X] T046 [P] Write `services/lease-abstraction/README.md` covering local setup, matching quickstart.md
- [X] T047 Audit all endpoints against FR-018 / design doc §7.2 to confirm information-barrier enforcement has no gaps. **Finding**: `GET /v1/review-queue` silently bypassed the barrier for admins with no audit trail, inconsistent with §7.2 point 3 and with the other endpoints. Fixed by adding `enforce_team_scope_with_admin_audit` (`src/policy/team_scope.py`) — reads now allow an audited admin bypass, writes (verify/resolve) never bypass. Covered by `tests/unit/test_team_scope.py`.
- [X] T048 [P] Additional unit tests for `threshold_policy.py` and `circuit_breaker.py` in `services/lease-abstraction/tests/unit/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only. Now includes provider failover (T015), so the MVP itself satisfies Constitution Principle IV's failover requirement rather than deferring it.
- **User Story 2 (Phase 4)**: Depends on Foundational; extends US1's consumer and OCR adapter (T025, T026 touch files US1 created), so implement after US1 rather than in parallel with it despite no *new* blocking entity.
- **User Story 3 (Phase 5)**: Depends on Foundational; reads verification events produced by US1/US2 (T037) but has its own models/endpoints and can be built in parallel with US2 if staffed separately.
- **Polish (Final Phase)**: Depends on all three user stories. T044 (backfill isolation) additionally depends on T005/T006 (Foundational models/Kafka scaffolding) directly and can start as soon as Foundational is done if staffed separately from the user stories.

### Within Each User Story

- Tests before implementation (write and confirm failing first).
- Models before consumers/services before API endpoints.
- US1's consumer/adapter files are extended, not duplicated, by US2 — coordinate to avoid merge conflicts if parallelized.

### Parallel Opportunities

- T003 alone in Phase 1.
- T005, T006, T007, T008 in Phase 2 (different files).
- T010, T011 (tests) and T012 (model) in Phase 3 can start together; T013–T021 are sequential/dependent as noted.
- T022, T023, T024 in Phase 4 can start together once Phase 3 lands.
- T031–T035 in Phase 5 can all start together; T036–T042 depend on their respective models.
- T043, T044, T046, T048 in the Final Phase are independent of each other and could start as soon as their stated dependencies are met, without waiting for every other Final Phase task.

---

## Parallel Example: User Story 1

```bash
# Tests + first model, in parallel:
Task: "Contract test for extracted-fields endpoints in tests/contract/test_extracted_fields_api.py"
Task: "Integration test for auto-populate flow in tests/integration/test_auto_populate_flow.py"
Task: "Create ExtractedField model in src/models/extracted_field.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (User Story 1).
2. Stop and validate against quickstart.md Scenario 1.
3. This alone delivers the largest business win (SC-001's 3hr→10min target) and is deployable independently — User Story 2's review queue is not required for auto-populated fields to work, and Constitution IV's failover requirement is already satisfied within this phase (T015).

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. User Story 1 → validate → this is the MVP.
3. User Story 2 → validate (Scenarios 2–3) → closes the loop on low-confidence fields.
4. User Story 3 → validate → operational trust/monitoring layer, including the baseline study (T042) needed to validate SC-001.
5. Final Phase → backfill isolation, dead-letter handling, degradation validation, documentation, cross-team UI tracking (T030).

## Notes

- [P] tasks touch different files with no unmet dependencies.
- Commit after each task or logical group; stop at each checkpoint to validate the story independently.
- FR-004 and FR-013's actual threshold *values* remain placeholders (per Clarifications) — no task here hardcodes a final number; T009/T016/T025 build the re-calibration mechanism, not a fixed constant.
- **Remediation history**: `/speckit-analyze` (2026-09-05) found 4 coverage/sequencing gaps (A1–A4), all resolved by renumbering/adding tasks above: A1 → T044, A2 → T015 (moved into Phase 3), A3 → T030, A4 → T042. Two LOW findings (A5, A6 — per-field-type threshold granularity, and no automated check for the non-blocking architectural rule) were not code-level gaps and were folded into existing task descriptions (T009, T016) rather than new tasks.
