# Phase 0 Research: Lease Abstraction

## Decision: OCR provider — AWS Textract

**Rationale**: Textract returns a per-block and per-page confidence score natively, which gives
FR-013's "OCR engine's own output-confidence signal" placeholder floor a real, ready-made value to
threshold on without building custom scan-quality heuristics for v1. It also handles the tables and
key-value layouts common in lease riders and exhibits better than generic OCR.

**Alternatives considered**:
- *Azure Form Recognizer* — comparable confidence-scoring support; rejected only for v1 to avoid
  standing up a second cloud provider relationship when the rest of the platform (per the design
  doc) already assumes AWS (S3, KMS).
- *Google Document AI* — same rejection rationale as Azure.
- *Open-source OCR (Tesseract)* — rejected: no native per-field confidence signal comparable to
  managed services, which would leave FR-013 with nothing concrete to threshold on.

## Decision: Extraction (LLM) provider — Anthropic Claude

**Rationale**: The extraction step (finding base rent, escalation schedule, free-rent period, TI
allowance, and term inside OCR'd text) is a structured-output-from-long-document task, which Claude
handles well via tool-use/structured JSON output, and keeps the whole pipeline within a single model
family for the initial implementation. Per Constitution IV, a secondary provider is still required
for failover — this decision covers the *primary* provider only.

**Alternatives considered**:
- *OpenAI GPT-family* — reasonable alternative; designated as the secondary/failover provider (see
  below) rather than primary, so the two are never the same vendor and a real provider-level outage
  can be tested (Constitution VI: "manual-mode operation is exercised on a schedule").
- *Fine-tuned open-weight extraction model* — rejected for v1: requires the labeled evaluation set
  that doesn't exist yet (README §7); revisit once FR-004/FR-013 have real calibration data.

## Decision: Secondary provider for failover — OpenAI GPT-family

**Rationale**: Satisfies FR-012 ("fail over to a secondary provider before falling back to full
manual mode") with a genuinely independent vendor, so a primary-provider outage is not correlated
with the failover path.

**Alternatives considered**: A second Anthropic model/region was rejected as insufficiently
independent for failover purposes — a single-vendor outage could take out both paths.

## Decision: Event transport — reuse the platform's existing Kafka bus

**Rationale**: `commercial-brokerage-platform-design.md` §6 already establishes Kafka as the
platform-wide event bus (`property.changed`, `listing.published`, `deal.state.changed`,
`deal.closed`). This service consumes a `document.uploaded` event (emitted by the existing Document
service) and produces `lease.extraction.completed`, rather than introducing a second messaging
technology. This is also what makes Constitution I concrete: the service is wired in via the event
bus, not a synchronous call.

**Alternatives considered**: A dedicated job queue (e.g., Redis/Celery) was considered for simplicity
but rejected — it would duplicate durability/retry machinery the platform's Kafka consumer groups
already provide, and would add a second technology to operate for no added capability.

## Decision: Durable queue + dead-letter handling — Kafka consumer group with a dead-letter topic

**Rationale**: Satisfies FR-010 directly: failed or unavailable-downstream messages are retried by
the consumer group's offset-commit semantics; messages that exhaust retries move to
`lease.extraction.dead-letter` for manual triage rather than being dropped.

**Alternatives considered**: In-database job table with polling — rejected as redundant given Kafka
is already the platform's durability mechanism.

## Decision: Circuit breaker — `pybreaker` around both the OCR and LLM extraction calls

**Rationale**: Satisfies FR-011: independent breakers for OCR and for extraction so a degraded LLM
provider doesn't necessarily stop OCR from queuing progress, and vice versa. Explicit failure-rate
and latency thresholds are configuration, not code, so they can be tuned operationally.

**Alternatives considered**: Hand-rolled threshold counters — rejected in favor of a maintained
library with half-open-probe semantics already built in (matches Constitution IV's "half-open probes
test recovery before full traffic resumes").

## Decision: Information-barrier enforcement — reuse the Deal service's row-level policy check

**Rationale**: Per the Clarifications session, FR-018 requires the review queue to inherit the same
barrier as the Deal service (design doc §7.2: `principal.teamId ∈ deal.sides[side].allowedTeams`).
This service receives `teamId`/`allowedTeams` as part of the `document.uploaded` event payload and
re-evaluates the same policy shape locally at read time, rather than calling back into the Deal
service synchronously (which would violate Constitution I).

**Alternatives considered**: Synchronous authorization call to the Deal service per review-queue
read — rejected as a violation of Constitution I (no core-service dependency on the AI layer's
critical path, and symmetrically, no AI-layer dependency on a synchronous core-service call either).
