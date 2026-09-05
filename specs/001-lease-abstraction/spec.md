# Feature Specification: Lease Abstraction

**Feature Branch**: `001-lease-abstraction`

**Created**: 2026-09-05

**Status**: Draft

**Input**: User description: "Convert signed commercial lease PDFs into structured, verified lease terms (base rent, escalation schedule, free-rent period, tenant-improvement allowance, term) via OCR + extraction with per-field confidence scoring, routing low-confidence fields to a human review queue, while keeping human-verified data authoritative and never blocking the core leasing platform. (README.md §2.1, §3.1, §5.1, §6, §7)"

## Clarifications

### Session 2026-09-05

- Q: FR-004 needs a confidence threshold to decide auto-populate vs. review-queue, but the labeled evaluation set to calibrate one doesn't exist yet. How should v1 behave until a real threshold is calibrated? → A: Ship with an intentionally conservative placeholder threshold (high confidence required to auto-populate); route everything else to review; recalibrate against the labeled set once it exists.
- Q: FR-013 needs an OCR scan-quality floor, but it hasn't been established empirically yet. How should v1 behave until then? → A: Use an off-the-shelf OCR-engine confidence signal as a placeholder floor; anything below it routes straight to manual entry; refine the floor once real scan-quality data is analyzed.
- Q: Should the review queue (User Story 2) enforce the same team-based information barriers as the Deal service (design doc §7.2)? → A: Yes — review queue items are scoped to the deal's assigned team the same way deal reads are, via the same row-level policy check.
- Q: Should measuring the current ~3-hour manual baseline be a prerequisite before this feature is considered complete (README §7)? → A: Yes — measure the baseline (sample of recent leases) before or alongside rollout so SC-001 can be validated rather than assumed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify Auto-Populated High-Confidence Fields (Priority: P1)

A lease analyst uploads a signed lease PDF. The system automatically populates the deal record's
lease terms for every field the extraction pipeline is confident about. The analyst's job changes
from reading all 100 pages and transcribing numbers into a spreadsheet, to reviewing and confirming
a short list of pre-populated values against the source document.

**Why this priority**: This is the single largest, fastest-to-deliver win described in the business
problem: it collapses a ~3-hour manual abstraction into ~10 minutes of verification, unblocking
commission calculation, comparable creation, and portfolio reporting for every deal downstream
(README §3.1). It is valuable on its own even before the review-queue workflow (User Story 2) exists,
because manual entry remains the fallback for anything not auto-populated.

**Independent Test**: Upload a lease PDF with clearly stated terms; confirm the deal record is
pre-populated with the five core fields (base rent, escalation schedule, free-rent period, TI
allowance, term) and that an analyst can confirm each field in under 10 minutes without opening a
separate application.

**Acceptance Scenarios**:

1. **Given** a signed lease PDF with clearly legible terms, **When** it is uploaded, **Then** the
   deal record is auto-populated with values for fields whose extraction confidence is above the
   calibrated threshold, each tagged with its confidence score and model version.
2. **Given** an auto-populated field, **When** an analyst confirms it without changes, **Then** the
   field is marked human-verified with the confirming user and timestamp, and becomes the
   authoritative value for that field going forward.
3. **Given** an auto-populated field, **When** an analyst edits the value before confirming, **Then**
   the corrected value (not the model's original output) is stored as the human-verified record.

---

### User Story 2 - Work the Low-Confidence Review Queue (Priority: P2)

A lease analyst opens a review queue, inside the tool they already use, listing every field across
all uploaded leases whose extraction confidence fell below the calibrated threshold. For each queued
field, the analyst sees the source document location, the model's proposed value (if any), and the
confidence score, and enters or confirms the correct value.

**Why this priority**: This is what makes automatic population (User Story 1) trustworthy — without
it, low-confidence extractions would either be silently wrong or would block the deal record entirely.
It depends on User Story 1's confidence-scoring pipeline existing first, so it is P2.

**Independent Test**: Upload a lease PDF with a poorly scanned or ambiguous clause for one field
(e.g., an unusual escalation formula); confirm that field appears in the review queue with its
confidence score and source location, and that entering a value there populates the deal record
identically to an auto-populated field.

**Acceptance Scenarios**:

1. **Given** a field with confidence below the calibrated threshold, **When** extraction completes,
   **Then** the field appears in the review queue instead of being auto-populated, and the deal
   record accepts manual entry for it in the meantime.
2. **Given** a document where every field falls below threshold, **When** extraction completes,
   **Then** all fields for that document route to the review queue and none are silently dropped.
3. **Given** a field already confirmed by a human, **When** the extraction pipeline is rerun (e.g.,
   after a model upgrade), **Then** the previously verified value is left unchanged and does not
   reappear in the review queue.
4. **Given** a lease document whose deal is restricted by a team-based information barrier, **When**
   an analyst who is not on that deal's assigned team opens the review queue, **Then** that
   document's queue items are not visible to them, matching the deal's row-level access policy.

---

### User Story 3 - Monitor Extraction Accuracy and Degradation (Priority: P3)

An operations or engineering stakeholder views per-field extraction accuracy against a labeled
holdout set, the analyst override rate over time, and which model version produced each extraction,
in order to detect quality drift before it affects a large volume of leases.

**Why this priority**: This does not block day-to-day abstraction (User Stories 1–2 work without it),
but is required before the automation can be trusted at scale, and is explicitly called out as a
standing operational requirement rather than a one-time launch check (README §6.4).

**Independent Test**: With extraction running against a labeled holdout set, confirm a
per-field-type accuracy report is viewable, the override rate trend is viewable, and every extracted
record shows which model version produced it.

**Acceptance Scenarios**:

1. **Given** a labeled holdout set, **When** extraction accuracy for any field type drops below its
   historical baseline, **Then** an alert is raised before the drop affects live review-queue volume.
2. **Given** a period of rising analyst override rate on a specific field type, **When** the trend is
   viewed, **Then** it is visible as a leading indicator distinct from raw accuracy.

---

### Edge Cases

- What happens when a lease PDF is a low-quality scan below the (to-be-established) OCR quality
  floor? The document MUST be excluded from automated extraction and routed entirely to manual entry
  rather than producing low-confidence guesses.
- How does the system behave when the extraction service is unavailable? Documents queue durably for
  later processing; the deal record continues to accept manual entry in the meantime (README §6.1).
- How does the system behave when the extraction service is degraded or slow? A circuit breaker opens
  after an explicit threshold and routes new documents directly to manual review rather than allowing
  timeouts to accumulate; the queue drains once the service recovers.
- How does the system behave when the model provider itself has an outage? It fails over to a
  secondary provider; if both are unavailable, the system falls back to full manual entry with no
  loss of uploaded documents.
- What happens if a reprocessing run (e.g., a model upgrade) produces a different value for a field a
  human already verified? The verified value is retained unchanged; the new model output is discarded
  or logged for evaluation purposes only, never written over the verified value.
- What happens to leases in the historical archive (tens of thousands of already-executed leases)?
  Bulk backfill runs on an isolated processing path so it cannot contend with or delay extraction of
  newly uploaded, live leases.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a signed lease PDF upload and run OCR to produce machine-readable
  text before extraction.
- **FR-002**: The system MUST extract, at minimum, these five lease terms from the document: base
  rent, escalation schedule, free-rent period, tenant-improvement (TI) allowance, and lease term.
- **FR-003**: The system MUST attach a per-field confidence score to every extracted value.
- **FR-004**: The system MUST auto-populate the deal record for any field whose confidence score is
  at or above a threshold. Until a labeled evaluation set exists to calibrate real per-field-type
  thresholds, the system MUST use a conservative placeholder threshold (deliberately biased toward
  routing to review over risking a wrong auto-populated value) and MUST be re-calibratable per field
  type once the evaluation set exists, without requiring a code change.
- **FR-005**: The system MUST route any field whose confidence score is below the calibrated
  threshold to a human review queue instead of auto-populating it.
- **FR-006**: The review queue MUST be reachable from within the tool analysts already use for deal
  management, without requiring a separate application.
- **FR-007**: The system MUST record, for every extracted field, its model version, confidence score,
  verifying user (once verified), and verification timestamp.
- **FR-008**: Once a field is confirmed by a human, the system MUST treat that value as authoritative
  and MUST NOT overwrite it via reprocessing, model upgrades, or pipeline reruns.
- **FR-009**: Every field the extraction pipeline can populate MUST remain manually editable at all
  times, independent of extraction or review-queue availability.
- **FR-010**: If the extraction service is unavailable, the system MUST queue uploaded documents
  durably for later processing without blocking manual entry on the deal record.
- **FR-011**: If the extraction service is degraded or slow (exceeding an explicit latency/error-rate
  threshold), the system MUST open a circuit breaker and route new documents to manual review rather
  than allow requests to time out.
- **FR-012**: If the model provider is unavailable, the system MUST fail over to a secondary provider
  before falling back to full manual mode.
- **FR-013**: The system MUST exclude documents scanned below a quality floor from automated
  extraction entirely, routing them to manual entry instead. Until an empirically established floor
  exists (README §7), the system MUST use the OCR engine's own output-confidence signal as a
  placeholder floor, and MUST be able to have that floor refined once real scan-quality data is
  analyzed, without requiring a code change.
- **FR-014**: The system MUST NOT allow any deal-state transition, commission calculation, or search
  request to block on a synchronous call to the extraction pipeline.
- **FR-015**: The system MUST track per-field-type extraction accuracy against a labeled holdout set
  and alert when accuracy drifts from baseline.
- **FR-016**: The system MUST track analyst override rate (auto-populated or suggested values later
  corrected by a human) as an ongoing operational metric.
- **FR-017**: Bulk backfill processing of historical leases MUST run on a path isolated from live,
  newly uploaded document processing.
- **FR-018**: The review queue MUST enforce the same team-based, row-level information-barrier
  policy as the deal record it belongs to — an analyst not on a deal's assigned team MUST NOT see
  that deal's review queue items, regardless of any organization-wide or admin-level view.
- **FR-019**: Before this feature is considered complete, the current fully-manual abstraction time
  (baseline for SC-001) MUST be measured against a representative sample of recent leases, so the
  improvement can be validated rather than assumed.

### Key Entities

- **Lease Document**: The uploaded source PDF for a single lease. Attributes include the file
  reference, OCR output, scan-quality assessment, and upload timestamp.
- **Extracted Field**: One structured lease term derived from a Lease Document (e.g., base rent).
  Attributes: field type, extracted value, confidence score, model version, source location in the
  document, verification status, verifying user, verification timestamp.
- **Structured Lease Terms**: The confirmed set of Extracted Fields for a Lease Document, consumed by
  the existing deal record, the comparables database, and the market analytics layer.
- **Review Queue Item**: A reference to an Extracted Field whose confidence fell below threshold,
  pending human entry or confirmation. Scoped to the same assigned team / information-barrier policy
  as the Lease Document's associated deal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Median analyst time to fully verify a lease's structured terms drops from a measured
  baseline (approximately 3 hours fully manual, to be confirmed per FR-019) to approximately 10
  minutes of review.
- **SC-002**: 100% of documents continue to be accepted (queued or manually entered) during a
  simulated extraction-service outage — zero uploads are rejected or lost.
- **SC-003**: Zero previously human-verified field values are altered by any reprocessing or model
  upgrade event, across all monitored extractions.
- **SC-004**: A person can locate and complete every item in the review queue without leaving the
  deal-management tool.
- **SC-005**: Per-field-type extraction accuracy against the labeled holdout set is visible and
  alerts within one monitoring cycle of dropping below its established baseline.

## Assumptions

- The five fields named in the business problem (base rent, escalation schedule, free-rent period,
  TI allowance, term) constitute the v1 scope of extraction; additional lease terms may be added in a
  later iteration.
- A labeled evaluation set for calibrating confidence thresholds and the OCR quality floor does not
  yet exist. Until it does, both FR-004 and FR-013 use conservative, engine-provided placeholder
  signals (per Clarifications) rather than firm capital targets; both MUST be re-calibratable
  without a code change once real data exists.
- The review queue's information-barrier scoping (FR-018) reuses the Deal service's existing
  row-level policy mechanism (design doc §7.2) rather than introducing a separate authorization
  model for AI-layer surfaces.
- The existing deal record, comparables database, and market analytics layer already exist as
  downstream consumers and are out of scope to build here — this feature only produces and verifies
  Structured Lease Terms and hands them off.
- Historical backfill of tens of thousands of already-executed leases is a distinct, lower-priority
  effort from live document processing and may be sequenced after the live path ships.
- OCR and extraction may be provided by third-party or model-provider services; the specific
  vendor(s) are an implementation decision for `/speckit-plan`, not this spec.
