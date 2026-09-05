# Event Contracts: Lease Abstraction

Transport: the platform's existing Kafka bus (`commercial-brokerage-platform-design.md` §6).

## Consumed: `document.uploaded`

Emitted by the (out-of-scope) Document service. This service's consumer group subscribes to it.

```json
{
  "documentId": "uuid",
  "dealId": "uuid",
  "teamId": "uuid",
  "allowedTeams": ["uuid"],
  "s3Key": "string",
  "sha256": "string",
  "contentType": "application/pdf",
  "documentType": "LEASE",
  "uploadedAt": "iso8601"
}
```

- Only messages with `documentType: "LEASE"` are processed by this service; others are ignored.
- Consumer group: `lease-abstraction-intake`. Failed messages retry per the consumer's backoff
  policy; after exhausting retries they are published to `lease.extraction.dead-letter` (FR-010).

## Produced: `lease.extraction.completed`

Emitted once a `LeaseDocument`'s `ExtractionRun` reaches a terminal state (`COMPLETE` or `FAILED`).

```json
{
  "documentId": "uuid",
  "extractionRunId": "uuid",
  "runType": "LIVE",
  "status": "COMPLETE",
  "extractedFieldIds": ["uuid"],
  "reviewQueueItemIds": ["uuid"],
  "completedAt": "iso8601"
}
```

- Downstream consumers (Deal service, comparables, analytics — all out of scope here) use this event
  to know that auto-populated values are available; they read the actual values via the REST API in
  `api.md`, not from the event payload itself (keeps the event small and avoids duplicating the
  authoritative store).

## Produced: `lease.extraction.dead-letter`

Emitted when a `document.uploaded` message exhausts retry attempts (FR-010).

```json
{
  "documentId": "uuid",
  "originalEvent": { "...": "the original document.uploaded payload" },
  "failureReason": "string",
  "attemptCount": "int",
  "lastAttemptAt": "iso8601"
}
```

- Consumed by an operational alerting process (out of scope for this feature) so a human can triage
  documents that never made it into the pipeline.

## Consumed: `document.backfill.requested` (added during implementation, T044/FR-017)

Same payload shape as `document.uploaded`, but published by the (out-of-scope) historical-archive
migration process rather than the live Document service, and consumed by a dedicated consumer
group so bulk backfill volume cannot contend with or delay live processing.

- Consumer group: `lease-abstraction-backfill` (distinct from `lease-abstraction-intake`).
- Rate-limited: the backfill consumer processes at most
  `LEASE_ABSTRACTION_BACKFILL_RATE_LIMIT_PER_MINUTE` documents per minute (config, default 30),
  throttling itself rather than relying on the live path's capacity.
- Produces the same `lease.extraction.completed` event as the live path, with `runType: "BACKFILL"`.
