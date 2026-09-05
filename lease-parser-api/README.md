# Lease Abstraction Service

The lease-abstraction capability of the Newmark AI Layer for Commercial Leasing (see the root
`README.md` for the business problem, and `specs/001-lease-abstraction/` for the spec, plan, and
tasks this service was built from).

Converts signed lease PDFs into structured, verified lease terms (base rent, escalation schedule,
free-rent period, TI allowance, term) via a two-stage OCR (AWS Textract) → LLM extraction
(Anthropic Claude, with OpenAI as failover) pipeline, with per-field confidence scoring, a
team-scoped human review queue for low-confidence fields, and accuracy/drift monitoring.

## Architecture at a glance

- **Additive, non-blocking** (Constitution I): consumes `document.uploaded` off the platform's
  existing Kafka bus and produces `lease.extraction.completed`. No endpoint here is ever called
  synchronously by the Deal, Commission, or Search services.
- **Human-verified data is authoritative** (Constitution II / FR-008): once a field is `VERIFIED`
  or `OVERRIDDEN`, it is terminal — no reprocessing run or model upgrade can change it.
- **Graceful degradation** (Constitution IV): circuit breakers around OCR and extraction, provider
  failover (Claude → OpenAI) before falling back to manual mode, durable Kafka retry + dead-letter
  handling, and an isolated rate-limited path for bulk historical backfill.

See `specs/001-lease-abstraction/plan.md`, `data-model.md`, `research.md`, and `contracts/` for the
full design rationale.

## Local setup

```bash
cd lease-parser-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # or: pip install <deps from pyproject.toml> directly
```

Configure via environment variables (see `src/config.py` for the full list), e.g.:

```bash
export LEASE_ABSTRACTION_DATABASE_URL="postgresql+asyncpg://localhost/lease_abstraction"
export LEASE_ABSTRACTION_KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export LEASE_ABSTRACTION_ANTHROPIC_API_KEY="..."
export LEASE_ABSTRACTION_OPENAI_API_KEY="..."
```

Run database migrations:

```bash
alembic upgrade head
```

Run the API:

```bash
uvicorn src.api.main:app --reload
```

## Running tests

The test suite runs against an in-memory SQLite database (no live Postgres/Kafka/AWS/Anthropic/
OpenAI required) via the cross-dialect types in `src/models/types.py` and fakes for the OCR/LLM
adapters — see `tests/conftest.py`.

```bash
pip install -e ".[dev]"
pytest
```

For the manual end-to-end scenarios this automated suite is derived from, see
`specs/001-lease-abstraction/quickstart.md`.

## Known gaps requiring non-engineering follow-up

- **`docs/UI_INTEGRATION.md`** (FR-006/SC-004): the review queue is API-only; surfacing it inside
  the existing broker deal-management tool requires that team's involvement.
- **`docs/BASELINE_STUDY.md`** (FR-019/SC-001): the 3-hour manual baseline this feature's ~10-minute
  target is measured against has not yet been captured; requires a brokerage-operations timing study.
- Confidence thresholds (FR-004) and the OCR scan-quality floor (FR-013) currently ship with
  conservative placeholder values (`src/config.py`), pending the labeled evaluation set called out
  in the root README.md §7.
