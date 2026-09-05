# API Contracts: Lease Abstraction

REST, resource-oriented, versioned — consistent with the platform convention in
`commercial-brokerage-platform-design.md` §4. All endpoints require the caller's `teamId`
(from the platform's existing AuthN/AuthZ layer) and enforce the information-barrier filter
described below (FR-018).

## `GET /v1/lease-documents/{documentId}/extracted-fields`

Returns all `ExtractedField` rows for a document, each with its value, confidence, provenance,
and verification status. Used by User Story 1's confirmation flow.

- **403** if `caller.teamId ∉ document.allowedTeams`.

## `POST /v1/lease-documents/{documentId}/extracted-fields/{fieldId}/verify`

```json
{ "value": "optional — omit to confirm the extracted value as-is; include to override it" }
```

- If `value` is omitted: `verificationStatus → VERIFIED`, `extractedValue` unchanged (US1 scenario 2).
- If `value` is present: `verificationStatus → OVERRIDDEN`, `extractedValue` set to the provided
  value (US1 scenario 3).
- **409** if the field's `verificationStatus` is already `VERIFIED` or `OVERRIDDEN` — verified
  fields are terminal (FR-008); this endpoint never mutates an already-verified field.
- **403** if `caller.teamId ∉ document.allowedTeams`.

## `GET /v1/review-queue?teamId={teamId}&status=PENDING`

Returns `ReviewQueueItem` rows scoped to the caller's team(s) only (FR-018). The `teamId` query
parameter MUST be a subset of the caller's own team memberships — a caller cannot request another
team's queue by changing the parameter.

## `POST /v1/review-queue/{itemId}/resolve`

```json
{ "value": "the correct field value, in the shape appropriate to fieldType" }
```

- Sets the linked `ExtractedField.verificationStatus → OVERRIDDEN` (or creates one, if the item
  originated from an `EXCLUDED_LOW_QUALITY` document with no prior extraction) and
  `ReviewQueueItem.status → RESOLVED`.
- **403** if `caller.teamId ∉ item.allowedTeams`.
- **409** if the item is already `RESOLVED`.

## `GET /v1/metrics/extraction-accuracy?fieldType=&modelVersion=&period=`

Returns `AccuracyMetricSnapshot` rows for the given filters (User Story 3 / FR-015). No
information-barrier filtering — this is aggregate operational data, not deal-scoped.

## `GET /v1/metrics/override-rate?fieldType=&period=`

Returns `OverrideRateMetric` rows for the given filters (User Story 3 / FR-016).

## `POST /v1/baseline-measurements`

```json
{ "sampleLeaseIds": ["uuid"], "measuredMedianMinutes": 178.0, "method": "string" }
```

Records the one-time (or periodically repeated) manual-abstraction baseline study required by
FR-019, so SC-001 can be evaluated against a real measurement rather than an assumed figure.

## Cross-cutting

- **Idempotency**: `POST` endpoints that mutate state (`verify`, `resolve`) accept an
  `Idempotency-Key` header, consistent with the platform-wide convention in
  `commercial-brokerage-platform-design.md` §4.8, so retried requests from an unreliable client
  connection do not double-process a verification.
- **No synchronous cross-service calls**: none of these endpoints call the Deal, Commission, or
  Search services synchronously (Constitution I). `dealId`/`teamId`/`allowedTeams` are sourced from
  the `document.uploaded` event at ingest time, not fetched live per-request.
