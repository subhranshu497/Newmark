# Commercial Brokerage Platform — System Design

| | |
|---|---|
| **Document** | Listing-to-Close Platform — Architecture & Design |
| **Status** | Draft |
| **Version** | 0.1 |
| **Date** | September 2026 |
| **Domain** | Commercial Real Estate Services |

---

## 1. Problem Statement

### 1.1 Overview

This document specifies a **Listing-to-Close** platform for a commercial real estate brokerage.

The system maintains an inventory of commercial properties and the leasable spaces within them, publishes available spaces as listings, captures occupier requirements (for example: a tenant needs 40,000 sq ft of Class A office space in Phoenix by Q3), matches those requirements against available inventory, and tracks the resulting transaction through tour → LOI → negotiation → execution.

On close, the deal is materialized as an immutable **comparable** that feeds market intelligence back into future pricing and matching. Broker commissions are calculated and split at the point of close.

### 1.2 Scope

**In scope**

- Property and space inventory management
- Listing publication and search
- Occupier requirement capture and matching
- Deal lifecycle management
- Document storage and access control
- Comparables and market analytics
- Commission calculation and splits

**Out of scope**

- Facilities and work-order management
- Loan origination and servicing
- Payment rails and escrow
- E-signature internals (integration only, via DocuSign)
- Investment management / fund administration

### 1.3 User Classes

The platform serves two populations with opposing access patterns, and this split drives most of the architectural decisions that follow.

| Class | Volume | Profile |
|---|---|---|
| **Brokers** (internal) | ~10,000 | Write-heavy, transactional, confidentiality-sensitive |
| **Clients & public** | ~200,000 DAU | Read-heavy search and browse |

---

## 2. Functional Requirements

**FR-1 — Inventory management.** CRUD operations across the Property → Building → Floor → Space hierarchy, with time-bounded availability windows attached to each space.

**FR-2 — Listing publication and search.** Publish available spaces to the market. Support search by geography (radius and polygon), structured attributes (size range, asset class, rent, build-out condition), and free text, returning results in sub-second time.

**FR-3 — Requirement capture and matching.** Record an occupier's demand profile, return a ranked set of candidate spaces, and support persisted requirements that generate alerts when new matching inventory is published.

**FR-4 — Deal lifecycle.** Model a deal as a state machine spanning tour → proposal → LOI → negotiation → executed → closed, with participants (landlord, tenant, both broker teams), an activity timeline, and attached documents.

**FR-5 — Comparables and market analytics.** On close, derive an immutable comparable record. Serve aggregated market statistics — average $/PSF, net absorption, vacancy — sliced by submarket and asset class.

**FR-6 — Commission calculation and splits.** Compute the gross fee from executed lease or sale terms, apply the applicable split schedule across brokers and teams, and emit an auditable payout record.

---

## 3. Non-Functional Requirements

### 3.1 Scale Assumptions

| Dimension | Estimate |
|---|---|
| Properties / spaces | 10M / 40M |
| Active listings | ~2M |
| Peak search QPS | ~2,000 |
| Deal writes (incl. activity logging) | ~500 TPS |
| Read-to-write ratio | ~100:1 |
| Documents | 50M objects, ~100 TB |

### 3.2 Requirements

**Latency.** Search p99 under 300 ms. Listing detail p99 under 150 ms. Matching may run asynchronously with a 5-second target.

**Availability.** 99.95% on the read and search path. The deal-write path can tolerate a marginally lower target — brokers retry, the public does not.

**Consistency.** Deal state, commission, and comparables are **strongly consistent**; they constitute the money and legal record. The search index is **eventually consistent** — a listing surfacing three seconds late is acceptable, an incorrect commission split is not.

**Confidentiality and information barriers.** Deal data must be walled between broker teams representing opposing sides of the same transaction. Authorization is therefore row-level, not merely role-level. This is a domain-specific constraint with direct architectural consequences and is treated in detail in §7.2.

**Auditability.** Every deal state transition and every document access is recorded in an append-only, immutable log. Brokers act as fiduciaries and disputes are frequently litigated years after close.

**Data residency.** International operations may require EU tenant data to remain in-region, which argues for regional deployment of the OLTP tier rather than a single global cluster.

**Idempotency.** All external integrations — DocuSign callbacks, third-party data feeds such as CoStar — must be replay-safe.

---

## 4. API Surface

REST, resource-oriented, versioned. Cursor-based pagination throughout.

### 4.1 Inventory

```
POST   /v1/properties
GET    /v1/properties/{propertyId}
POST   /v1/properties/{propertyId}/spaces
PATCH  /v1/spaces/{spaceId}
POST   /v1/spaces/{spaceId}/availability     # {startDate, endDate, askingRentPsf, type}
```

### 4.2 Listings and Search

```
POST   /v1/listings                          # publish an available space
DELETE /v1/listings/{listingId}
GET    /v1/listings/search
       ?bbox= | ?lat=&lng=&radiusKm=
       &assetClass=OFFICE&minSqft=&maxSqft=
       &maxRentPsf=&availableBy=
       &q=<free text>&sort=relevance&cursor=&limit=
GET    /v1/listings/{listingId}
```

### 4.3 Requirements and Matching

```
POST   /v1/requirements                          # occupier demand profile
GET    /v1/requirements/{reqId}/matches?cursor=  # ranked candidates
POST   /v1/requirements/{reqId}/subscriptions    # alert on new inventory
```

### 4.4 Deals

```
POST   /v1/deals                             # {requirementId?, listingId, side}
GET    /v1/deals/{dealId}
POST   /v1/deals/{dealId}/transitions        # {toState, reason} — Idempotency-Key required
POST   /v1/deals/{dealId}/participants
POST   /v1/deals/{dealId}/activities         # tour, call, note
GET    /v1/deals/{dealId}/audit
```

### 4.5 Documents

```
POST   /v1/documents:presign                 # returns S3 pre-signed PUT
POST   /v1/documents                         # commit metadata after upload
GET    /v1/documents/{docId}/download        # pre-signed GET, access logged
```

### 4.6 Comparables and Analytics

```
GET    /v1/comps/search?submarketId=&assetClass=&closedAfter=
GET    /v1/market-stats?submarketId=&assetClass=&period=2026Q2
```

### 4.7 Commission

```
POST   /v1/deals/{dealId}/commission:calculate   # preview, no side effects
POST   /v1/deals/{dealId}/commission             # commit, idempotent
```

### 4.8 Cross-Cutting Conventions

Two conventions apply across the surface.

The **`:calculate` versus `POST` separation** provides a side-effect-free preview path. Commission splits are negotiated between broker teams before commitment, so the ability to model an outcome without writing to the ledger is a functional necessity rather than a convenience.

An **`Idempotency-Key` header is mandatory on every state-changing call**. The key is persisted alongside a hash of the response; a replay returns the original result rather than producing a duplicate effect.

---

## 5. Core Entities

```
Property        id, address, geo(point), submarketId, assetClass, yearBuilt,
                totalSqft, ownerPartyId
Space           id, propertyId, floor, suite, rentableSqft, condition
Availability    id, spaceId, [startDate, endDate), askingRentPsf, leaseType,
                status(AVAILABLE|UNDER_LOI|LEASED)
Listing         id, availabilityId, publishedAt, marketingCopy, media[], visibility

Party           id, type(COMPANY|PERSON), name          # tenants, landlords, investors
Broker          id, partyId, teamId, licenseNo, market
Requirement     id, occupierPartyId, geoTargets[], sqftRange, assetClass,
                budgetPsf, targetOccupancy, status

Deal            id, type(LEASE|SALE), state, listingId, requirementId,
                landlordTeamId, tenantTeamId, econTerms{}, version
DealParticipant dealId, partyId, role(TENANT|LANDLORD|BROKER), side
DealEvent       id, dealId, fromState, toState, actorId, at, payload   # append-only
Document        id, dealId?, propertyId?, type(LOI|LEASE|OM), s3Key, sha256

Comp            id, dealId, propertyId, closedAt, sqft, effectiveRentPsf,
                termMonths, concessions                 # immutable snapshot
Commission      id, dealId, grossFee, splits[{brokerId, pct, amount}], status
```

### 5.1 Modeling Note: Space versus Availability

`Availability` is modeled as a distinct entity from `Space`. A space is a physical fact; an availability is a time-bounded commercial offer made against that space. The same suite may be listed, withdrawn, re-listed at a different asking rent, and leased — repeatedly, over decades.

Collapsing the two into a single record destroys the ability to reconstruct historical pricing, which is the raw material for the comparables and market-analytics capability in FR-5. The separation is load-bearing.

---

## 6. High-Level Architecture

```
        Public Web / Broker SPA / Mobile
                     │
              CDN (media, static)
                     │
              API Gateway  ── AuthN (OIDC) ── AuthZ (row-level policy)
                     │
        ┌────────────┴────────────────────────────────────┐
        │            │           │          │             │
   Inventory     Search      Deal       Document      Commission
    Service      Service    Service      Service        Service
        │            │           │          │             │
   Postgres     OpenSearch  Postgres      S3          Postgres
   +PostGIS      cluster    (deals,      +KMS         (ledger)
   (sharded                 partitioned
    by market)              by year)
        │            ▲           │                        │
        │            │           │                        │
        └──── Debezium CDC ──────┴────────────────────────┘
                     │
              ┌──────┴──────┐
              │   Kafka     │   topics: property.changed, listing.published,
              └──────┬──────┘           deal.state.changed, deal.closed
                     │
     ┌───────────────┼──────────────┬──────────────┐
     │               │              │              │
  Indexer      Matching Engine   Comp Builder   Notification
  (→ OpenSearch)  (→ matches)    (→ comps)      (email/push)
                     │
              Redis (hot listings, session, rate limit)
                     │
        Analytics: Kafka → Snowflake → dbt → market_stats (served via cache)
```

### 6.1 Key Architectural Decisions

**CQRS on the listing path.** Writes are directed to Postgres; reads are served from OpenSearch. The two sides differ in both shape (normalized versus denormalized) and scale profile (100:1 read-to-write). Synchronization uses a **transactional outbox → Debezium → Kafka → indexer** chain, which guarantees that an index update cannot be lost when the originating database commit succeeds.

**The Deal service is an isolated bounded context.** It operates under strong consistency, uses optimistic locking on a `version` column, and maintains an append-only `DealEvent` table. It is never made eventually consistent, regardless of read-scaling pressure elsewhere in the system.

**The AI layer is additive.** Two capabilities sit alongside the core rather than within it: a lease-abstraction pipeline (OCR → LLM extraction → structured `econTerms` with per-field confidence scores and a human review queue), and vector embeddings supporting semantic requirement matching. Both consume from the existing event stream and neither is on the critical path for any core transaction.

---

## 7. Low-Level Design

### 7.1 Search and Matching

The search index stores one denormalized document per active listing. All joins are resolved at write time; none at read time.

```json
{
  "listingId": "...", "propertyId": "...",
  "location": {"lat": 33.45, "lon": -112.07},
  "submarketId": "PHX-CENTRAL", "assetClass": "OFFICE",
  "rentableSqft": 42000, "askingRentPsf": 34.50,
  "availableFrom": "2026-10-01",
  "amenities": ["parking", "fiber"],
  "text": "address + marketing copy",
  "visibility": ["PUBLIC"], "boostScore": 1.4
}
```

**Geospatial handling.** `location` is indexed as a `geo_point`. Map viewport queries use `geo_bounding_box`; proximity queries use `geo_distance`.

**Filter versus scoring context.** Square footage, rent, and date predicates are placed in `filter` context, where results are cached as bitsets and incur no scoring cost. Only free-text terms enter `must` context.

**Ranking.** A `function_score` query composes BM25 text relevance with a Gaussian geo-decay function, a freshness decay, and a listing-tier boost.

**Index freshness.** `refresh_interval` is set to 5 seconds. Indexer consumers are idempotent, keyed on `listingId`, and carry a version field used to discard out-of-order events.

**Reindexing.** Schema changes ship via alias-based blue/green cutover (`listings_v3` promoted behind the `listings` alias), producing zero downtime.

**Matching** executes the same query construction, sourced from a `Requirement` rather than user input, running as a Kafka consumer on `listing.published`. Results are persisted so that brokers observe a stable ranked set rather than one that shifts between page loads.

### 7.2 Deal State Machine and Information Barriers

```
DRAFT → TOURING → PROPOSAL → LOI_OUT → LOI_SIGNED
      → LEASE_NEGOTIATION → EXECUTED → CLOSED
                    ↓ (from any state)
                  LOST
```

Transitions are validated server-side against an explicit allow-map. The client is never trusted to submit a valid `toState`.

Each transition executes within a single database transaction:

```sql
BEGIN;
  UPDATE deals SET state=?, version=version+1
   WHERE id=? AND version=?;              -- optimistic lock; 0 rows → 409
  INSERT INTO deal_events (...);          -- append-only audit
  INSERT INTO outbox (topic, payload);    -- transactional outbox
COMMIT;
```

**Information barriers.** Where the firm represents the landlord on one side of a transaction and a separate internal team represents the tenant, those teams must not have visibility into each other's positions. This is a regulatory and fiduciary obligation, not a UX preference, and it constrains the design in four places:

1. Authorization is evaluated at the service layer as a row-level policy, never in the UI.
2. Every deal-scoped read passes a policy check of the form `principal.teamId ∈ deal.sides[side].allowedTeams`.
3. A `barrier` flag on the deal restricts even organization-wide administrative reads; all such access is written to the audit log.
4. Cache keys must incorporate the principal's team identifier. Omitting this leaks data across the barrier via Redis, bypassing the service-layer check entirely.

### 7.3 Commission Engine

Fee calculation is implemented as a pure function — no I/O, fully unit-testable, and versioned.

```
grossFee = f(dealType, econTerms, feeSchedule)

  LEASE: Σ over term months of (rentPsf × sqft × ratePct),
         NPV-discounted, net of free-rent concessions
  SALE:  salePrice × ratePct (tiered / banded)
```

**Schedule versioning.** `feeScheduleVersion` is pinned to the deal at creation time. Rate cards change; a deal signed under a Q1 schedule must continue to calculate under Q1 rules through close. Resolving the current schedule at close time is incorrect and produces silent retroactive repricing.

**Numeric handling.** Splits are validated to sum to exactly 100% prior to commit and stored as integer basis points. Monetary amounts are stored in minor units as `BIGINT`. Floating-point representation is not used anywhere in the fee path.

**Ledger semantics.** The commission store is append-only. Corrections are recorded as reversing entries; existing rows are never updated.

**Close as a saga.** Deal close is coordinated as a saga rather than a distributed transaction:

```
deal.closed → [Comp Builder] → [Commission] → [Notification] → [Analytics]
```

Each step is idempotent and independently retryable. A failure in comparable creation leaves the deal closed; the comparable is subsequently rebuilt from the event log. The two are deliberately decoupled.

---

## 8. Known Bottlenecks and Future Work

**Search index lag during bulk ingest.** Large third-party data imports can saturate the indexing pipeline and degrade freshness for organic listing publication. Mitigation is a separate bulk ingestion path with throttled indexing and a distinct consumer group, isolating batch load from the interactive path.

**Hot partitions in dense markets.** Market-based sharding produces uneven load; Manhattan and similar submarkets generate disproportionate write and query volume. Candidate approaches include sub-sharding high-volume markets by asset class, or moving to consistent hashing with explicit hot-key splitting.

**Cold start in thin submarkets.** Matching quality degrades in submarkets with sparse comparable history, where there is insufficient signal to calibrate ranking. Options include falling back to attribute-similarity scoring, borrowing priors from demographically comparable submarkets, or surfacing lower-confidence results with explicit uncertainty indicators.

**Lease abstraction accuracy.** The extraction pipeline described in §6.1 requires a measured confidence threshold below which human review is mandatory. Establishing that threshold requires a labeled evaluation set that does not yet exist.

**Regional data residency.** The current design assumes a single OLTP region. Supporting EU residency requires regional Postgres deployment with a resolved strategy for cross-region search, comparables, and analytics aggregation — none of which is specified in this document.
