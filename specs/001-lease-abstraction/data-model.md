# Phase 1 Data Model: Lease Abstraction

All entities live in a dedicated `lease_abstraction` schema, separate from the core Deal service's
schema (Constitution I). Cross-service identifiers (`dealId`, `teamId`, `allowedTeams`) are stored as
opaque values sourced from event payloads — no cross-database foreign keys.

## LeaseDocument

Represents one uploaded lease PDF and its OCR outcome.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `dealId` | UUID | From `document.uploaded` event; opaque reference to the Deal service |
| `teamId` | UUID | Owning team, from event payload |
| `allowedTeams` | UUID[] | Information-barrier scope, from event payload (FR-018) |
| `s3Key` | string | Source document location |
| `sha256` | string | Integrity/dedup check |
| `ocrStatus` | enum | `PENDING` \| `PROCESSING` \| `COMPLETE` \| `FAILED` \| `EXCLUDED_LOW_QUALITY` |
| `ocrConfidence` | float, nullable | Engine-native confidence signal (FR-013 placeholder floor) |
| `uploadedAt` | timestamp | |
| `runType` | enum | `LIVE` \| `BACKFILL` \| `REPROCESS` (FR-017 isolation) |

**Validation rule**: a document with `ocrConfidence` below the configured floor MUST transition to
`EXCLUDED_LOW_QUALITY`, never to `COMPLETE` (FR-013).

## ExtractedField

One structured lease term derived from a `LeaseDocument`.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `leaseDocumentId` | UUID (FK → LeaseDocument) | |
| `fieldType` | enum | `BASE_RENT` \| `ESCALATION_SCHEDULE` \| `FREE_RENT_PERIOD` \| `TI_ALLOWANCE` \| `TERM` (FR-002) |
| `extractedValue` | jsonb | Shape varies by `fieldType` (e.g. escalation schedule is structured, not scalar) |
| `confidenceScore` | float | Per FR-003 |
| `modelVersion` | string | Extraction model identifier, per FR-007 |
| `sourceLocation` | jsonb | Page/offset/bounding-box reference into the source document |
| `verificationStatus` | enum | `UNVERIFIED` \| `VERIFIED` \| `OVERRIDDEN` |
| `verifiedBy` | UUID, nullable | Set on transition to `VERIFIED`/`OVERRIDDEN` |
| `verifiedAt` | timestamp, nullable | |
| `createdAt` | timestamp | |

**State transitions** (FR-008 — terminal once verified):

```
UNVERIFIED → VERIFIED     (human confirms auto-populated or reviewed value unchanged)
UNVERIFIED → OVERRIDDEN   (human edits the value, then confirms)
VERIFIED, OVERRIDDEN are terminal: no further writes to `extractedValue` are permitted.
A reprocessing run MAY create a new ExtractionRun's fields but MUST NOT mutate a verified field.
```

**Validation rule**: any write attempting to change `extractedValue`, `confidenceScore`, or
`modelVersion` on a row where `verificationStatus != UNVERIFIED` MUST be rejected at the application
layer (Constitution II / FR-008).

## ReviewQueueItem

A pending unit of work for a low-confidence (or excluded) field.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `extractedFieldId` | UUID (FK → ExtractedField), nullable | Null when the item originates from an `EXCLUDED_LOW_QUALITY` document rather than a specific field |
| `leaseDocumentId` | UUID (FK → LeaseDocument) | |
| `teamId` | UUID | Copied from `LeaseDocument.teamId` |
| `allowedTeams` | UUID[] | Copied from `LeaseDocument.allowedTeams` (FR-018) |
| `status` | enum | `PENDING` \| `IN_PROGRESS` \| `RESOLVED` |
| `assignedTo` | UUID, nullable | |
| `createdAt` | timestamp | |
| `resolvedAt` | timestamp, nullable | |

**Authorization rule**: any read of `ReviewQueueItem` MUST filter to
`caller.teamId ∈ allowedTeams`, evaluated identically to the Deal service's row-level policy
(FR-018, design doc §7.2). This applies even to organization-wide/admin views.

## ExtractionRun

Tracks one pass of the pipeline over a document (supports FR-017 isolation and reprocessing without
overwriting verified data).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `leaseDocumentId` | UUID (FK) | |
| `runType` | enum | `LIVE` \| `BACKFILL` \| `REPROCESS` |
| `ocrModelVersion` | string | |
| `extractionModelVersion` | string | |
| `startedAt` / `completedAt` | timestamp | |
| `status` | enum | `RUNNING` \| `COMPLETE` \| `FAILED` |

## AccuracyMetricSnapshot

Supports User Story 3 / FR-015.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `fieldType` | enum | Same enum as `ExtractedField.fieldType` |
| `modelVersion` | string | |
| `measuredAccuracy` | float | Against the labeled holdout set |
| `baselineAccuracy` | float | Historical comparison point |
| `sampleSize` | int | |
| `driftFlag` | boolean | True when `measuredAccuracy` drops below `baselineAccuracy` by the configured margin |
| `measuredAt` | timestamp | |

## OverrideRateMetric

Supports User Story 3 / FR-016.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `fieldType` | enum | |
| `period` | daterange | Aggregation window |
| `overrideCount` | int | Fields transitioned to `OVERRIDDEN` in the period |
| `totalVerifiedCount` | int | Fields transitioned to `VERIFIED` or `OVERRIDDEN` in the period |
| `rate` | float | `overrideCount / totalVerifiedCount` |

## BaselineMeasurement

Supports FR-019 (prerequisite: measure the current manual-abstraction baseline before claiming
SC-001).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `sampleLeaseIds` | UUID[] | Leases sampled for the manual-timing measurement |
| `measuredMedianMinutes` | float | Result of the baseline measurement |
| `method` | string | Free-text description of how the sample/measurement was conducted |
| `measuredAt` | timestamp | |

**Note**: this entity records the *outcome* of the one-time baseline study; it is not itself
re-measured continuously. SC-001 is evaluated against whichever `BaselineMeasurement` is most recent
at rollout time.
