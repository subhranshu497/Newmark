# AI Layer for Commercial Leasing

## Turning Locked Documents into Searchable Market Intelligence

| | |
|---|---|
| **Document** | AI Capability Proposal — Commercial Leasing Platform |
| **Status** | Draft |
| **Version** | 0.1 |
| **Date** | September 2026 |
| **Audience** | Engineering leadership, product, brokerage operations |

---

## 1. Problem Statement

**The most valuable information the business owns is trapped in PDFs that computers cannot read.**

A commercial lease is a 100-page contract. Four or five numbers inside it define the entire economics of the deal — base rent, escalation schedule, free-rent period, tenant-improvement allowance, term. Everything else is legal structure around those numbers.

Today a person reads all 100 pages, locates those numbers, and types them into a spreadsheet. This takes roughly three hours per lease. Nothing downstream can proceed until it is done: commission cannot be calculated, the comparable cannot be created, portfolio reporting cannot be updated.

The firm has executed tens of thousands of these leases over decades. Every one is retained. **None of them are searchable.**

A question as basic as *"what free-rent concession did landlords offer on Franklin Street last year?"* has no answer available today — not because the data does not exist, but because it exists only as unread text inside thousands of scanned documents.

Two failures follow from this:

1. **A throughput bottleneck.** Manual abstraction is a queue in front of every downstream process.
2. **A dormant asset.** The historical lease archive is the firm's single most differentiated dataset, and it currently produces no value.

---

## 2. The Problem in Practical Terms

### 2.1 A worked example

A tenant approaches the firm with a requirement:

> *"We need 40,000 square feet on Franklin Street in Chicago."*

**What the current search returns.** Buildings offering 40,000 square feet on Franklin Street. Exactly what was typed.

**What it misses.** The 38,500 sq ft full floor two buildings north — which would have suited the tenant well. The requirement said 40,000, so the filter excluded it. The system executed the request literally and returned an incomplete answer.

**What it cannot handle at all.** The criteria that actually decide commercial leases are rarely numeric:

- *"Somewhere with character — not a glass box."*
- *"Walkable to Metra for a younger workforce."*
- *"Room to expand by another floor in three years without relocating."*
- *"Not in the same building as our competitor."*

A broker with fifteen years in the Loop knows precisely which Franklin Street buildings satisfy each of these. A search box has no representation for any of them.

### 2.2 What this costs

The gap between *what the tenant meant* and *what the system can express* is closed today entirely by individual broker memory. That approach has three weaknesses:

- It does not scale beyond what one person can hold in their head.
- It is inconsistent between brokers and between markets.
- It leaves the firm permanently when that broker retires or moves to a competitor.

---

## 3. Why Build This

### 3.1 Deals close faster

The three-hour manual abstraction is a traffic jam, not a task. Commission calculation, comparable creation, and client reporting all sit behind it. Reducing that step to roughly ten minutes of human verification removes the jam rather than optimizing around it.

This benefit is immediate, measurable, and requires no change in broker behavior.

### 3.2 The firm can answer questions it previously could not

Once decades of executed leases become structured and queryable, an entire class of question opens up:

- How have effective rents on Franklin Street moved over eight years, net of concessions?
- Which landlords in the Loop consistently concede more free rent, and under what conditions?
- What TI allowance should we expect for a 40,000 sq ft Class A requirement in this submarket?

Competitors holding the same buildings and comparable brokers cannot answer these, because their leases are also still PDFs. This is the durable advantage — not the model, the corpus.

### 3.3 Institutional knowledge stops leaving the building

When a twenty-year broker departs, their judgment about which buildings suit which tenants leaves with them. Capturing requirement patterns and match outcomes converts a portion of that individual expertise into an asset the firm retains.

**Ranking these honestly:** §3.1 is the easiest to justify and the fastest to deliver. §3.2 is where the real value sits and should drive the roadmap. §3.3 is genuine but slower to materialize and hardest to measure — it should not carry the business case on its own.

---

## 4. Core Business Problem

Stated plainly:

> **The firm's competitive advantage depends on knowing the market better than anyone else. That knowledge is currently stored in a format nothing can read.**

Every brokerage in Chicago represents broadly the same building stock and employs broadly comparable brokers. Buildings are not proprietary. Talent is mobile. Public market data is available to everyone who pays for it.

What is genuinely proprietary is the record of transactions the firm itself executed — the terms actually agreed, the concessions actually granted, the deals that fell through and why. That record exists, in full, and is unusable.

The problem is therefore not a shortage of data. It is that the data is in the wrong format, and converting it by hand costs more than the conversion has historically been worth.

---

## 5. Solution — 10,000 Foot View

Two capabilities, sharing one underlying dataset.

### 5.1 Lease abstraction: PDFs to structured data

```
  Signed lease PDF
        │
        ▼
  ┌─────────────┐   ┌──────────────┐   ┌───────────────────┐
  │    OCR      │──▶│  Extraction  │──▶│ Confidence check  │
  │ (scans →    │   │  (find the   │   │ per field         │
  │  text)      │   │   terms)     │   └─────────┬─────────┘
  └─────────────┘   └──────────────┘             │
                                    high ────────┴──────── low
                                     │                     │
                                     ▼                     ▼
                              Auto-populate         Human review
                              deal record            queue
                                     │                     │
                                     └──────────┬──────────┘
                                                ▼
                                    Structured lease terms
                                    (rent, escalations, free
                                     rent, TI, term, options)
```

The output feeds three consumers: the deal record, the comparables database, and the market analytics layer.

Every extracted field carries a confidence score. Fields above threshold populate automatically; fields below it route to review. The analyst's role changes from transcription to verification. This human checkpoint is a permanent design feature, not a temporary safeguard during rollout.

### 5.2 Semantic requirement matching

```
  "40,000 sq ft on Franklin Street, walkable to Metra,
   room to expand, some character to the building"
                    │
                    ▼
        ┌───────────────────────┐
        │  Hard filters         │   geography, asset class,
        │  (non-negotiable)     │   broad size band
        └───────────┬───────────┘
                    ▼
        ┌───────────────────────┐
        │  Semantic ranking     │   meaning-based similarity
        │  (approximate intent) │   against listing descriptions
        └───────────┬───────────┘
                    ▼
        Ranked candidates — including the
        38,500 sq ft floor a strict filter
        would have discarded
```

Structured filters still constrain the candidate set; a retail pad never surfaces against an office requirement. Within that set, ranking uses meaning rather than exact predicate match, so near-misses and soft criteria are represented instead of silently excluded.

### 5.3 Placement principle

Both capabilities are **additive**. They read from the existing event stream and write suggestions back. No core transaction calls them synchronously and waits for a response.

The useful comparison is a water filter fitted under a kitchen sink rather than spliced into the building's main line. If the filter clogs, water still reaches the tap. If the AI layer fails, the leasing platform continues operating exactly as it does today.

Placement drives adoption. Abstraction runs automatically when a document is uploaded, and the review queue lives inside the tool analysts already use. A capability that requires someone to remember to open a separate application will not be used, regardless of model quality.

---

## 6. Resiliency — Operating When the AI Layer Fails

The governing rule: **the platform must degrade to today's process, never to an outage.**

### 6.1 Degradation tiers

| Failure | System behavior | User experience |
|---|---|---|
| Extraction service unavailable | Documents queue for later processing; deal record accepts manual entry | Analyst abstracts by hand — the current process |
| Extraction degraded or slow | Circuit breaker opens after threshold; queue drains on recovery | Documents process late; nothing is lost |
| Confidence uniformly low | All fields route to review | Review volume rises; accuracy is unaffected |
| Semantic ranking unavailable | Fall back to structured filters and keyword ranking | Search still returns results, ranked less well |
| Embedding index stale or corrupt | Serve last known good index; rebuild in background | Slightly dated ranking; search remains available |
| Model provider outage | Fail over to secondary provider; if both fail, full manual mode | Degraded quality, continuous availability |

### 6.2 Design guarantees

**No synchronous dependency on the critical path.** No deal state transition, commission calculation, document upload, or search request blocks on an inference call. AI outputs arrive asynchronously and are merged into records that already exist.

**Manual entry is always available.** Every field the extraction pipeline can populate remains editable by hand, permanently. This is not a fallback mode that gets switched on during an incident; it is the standing behavior of the form.

**Durable queues.** Documents awaiting extraction persist in a queue with retry and dead-letter handling. An outage delays processing; it never drops work.

**Circuit breakers with explicit thresholds.** Sustained error rates or latency above threshold open the breaker and route directly to manual review rather than allowing timeouts to accumulate. Half-open probes test recovery before full traffic resumes.

**Cached and versioned indexes.** The semantic index is versioned and served from cache. A failed rebuild serves the previous version rather than returning nothing.

**Human-verified data is authoritative.** Once a field is confirmed by a person, it is the record. Reprocessing, model upgrades, and pipeline reruns never overwrite verified values. Provenance — model version, confidence score, verifying user, timestamp — is stored alongside every field.

### 6.3 Why determinism is preserved deliberately

Commission calculations and deal audit records must be reconstructable years after close, frequently in a dispute or litigation context. Model outputs are not reproducible across versions and cannot serve that function.

The pipeline therefore proposes; a person confirms; the confirmed value enters the legal record with its provenance attached. This is a deliberate constraint on the design, not a limitation to be engineered away in a later phase.

### 6.4 Operational readiness

- Extraction accuracy is monitored per field type against a labeled holdout set, with alerting on drift.
- Human override rate is tracked as a leading indicator of model degradation.
- Every model version is recorded per extraction, enabling audit and targeted reprocessing.
- Manual-mode operation is exercised on a schedule so the fallback path is known to work when it is needed.

---

## 7. Open Items

- **Confidence threshold calibration.** Requires a labeled evaluation set that does not yet exist. Building it should precede any accuracy commitment.
- **Historical backfill sequencing.** Processing decades of archived leases is a bulk workload and must run on an isolated path so it does not contend with live document processing.
- **Scan quality floor.** Older leases exist only as low-quality scans. The OCR quality threshold below which documents are excluded from automated processing needs to be established empirically.
- **Baseline metrics.** Current abstraction time, error rate, and downstream cycle time should be measured before rollout. Without a baseline the improvement in §3.1 cannot be substantiated.
