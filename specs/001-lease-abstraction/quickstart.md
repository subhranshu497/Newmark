# Quickstart: Lease Abstraction

Validates that the feature works end-to-end, per the acceptance scenarios in spec.md.

## Prerequisites

- Local Kafka broker (or `localstack`/`redpanda` equivalent) with topics: `document.uploaded`,
  `lease.extraction.completed`, `lease.extraction.dead-letter`.
- Local PostgreSQL with the `lease_abstraction` schema applied (see data-model.md).
- Sandbox/test credentials for the OCR provider (AWS Textract) and both LLM providers
  (Anthropic primary, OpenAI secondary — research.md).
- Two sample lease PDFs: one with clearly legible terms, one with a poor scan or ambiguous clause.

## Scenario 1 — Auto-populate and confirm (User Story 1)

1. Publish a `document.uploaded` event referencing the clearly-legible sample PDF, with a
   `dealId`/`teamId`/`allowedTeams` of your choosing.
2. Wait for `lease.extraction.completed` on the output topic.
3. `GET /v1/lease-documents/{documentId}/extracted-fields` — expect 5 fields (base rent, escalation
   schedule, free-rent period, TI allowance, term), each with `confidenceScore` and `modelVersion`
   populated, and `verificationStatus: UNVERIFIED`.
4. `POST /v1/lease-documents/{documentId}/extracted-fields/{fieldId}/verify` with no body — expect
   `verificationStatus: VERIFIED`, `verifiedBy`/`verifiedAt` populated.
5. Re-run step 4 on the same field — expect **409** (verified fields are terminal, FR-008).

## Scenario 2 — Review queue for a low-confidence field (User Story 2)

1. Publish a `document.uploaded` event referencing the poor-scan/ambiguous sample PDF.
2. Wait for `lease.extraction.completed`.
3. `GET /v1/review-queue?teamId={teamId}&status=PENDING` — expect at least one item referencing the
   ambiguous field, with its confidence score and source location.
4. `POST /v1/review-queue/{itemId}/resolve` with a corrected value — expect the linked
   `ExtractedField.verificationStatus → OVERRIDDEN` and the queue item `status → RESOLVED`.
5. Trigger a `REPROCESS` `ExtractionRun` on the same document — expect the resolved field's value to
   remain unchanged (FR-008) and no new review-queue item created for it.

## Scenario 3 — Information barrier (Clarifications session)

1. Repeat Scenario 2 steps 1–2 using a `teamId`/`allowedTeams` pair that excludes a second team, `B`.
2. `GET /v1/review-queue?teamId=B&status=PENDING` as a caller on team `B` — expect the item from step
   1 to be absent, and a **403** if team `B` is requested explicitly by a non-member caller.

## Scenario 4 — Degradation (Constitution IV)

1. Disable network access to the OCR provider (or point at an invalid endpoint).
2. Publish a `document.uploaded` event.
3. Expect: after the configured failure threshold, the circuit breaker opens; the document remains
   queued (not dropped); `LeaseDocument.ocrStatus` reflects the pending/failed state; no request to
   any core service (deal, commission, search) is blocked or errors as a result.
4. Re-enable OCR access — expect the queue to drain and the document to complete processing without
   manual intervention.

## Running the automated test suite

```bash
pytest services/lease-abstraction/tests/contract      # validates api.md and events.md
pytest services/lease-abstraction/tests/integration    # runs scenarios 1–4 above
pytest services/lease-abstraction/tests/unit
```
