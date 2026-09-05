# Running & Testing This Service Locally

This documents how to actually start `lease-abstraction` and drive it, at two levels: a quick
local demo that needs nothing but Python (used to validate the service in development), and the
full production-like stack. See `specs/001-lease-abstraction/quickstart.md` for the four
acceptance scenarios this exercises.

## Required tools

| Tool | Why |
|---|---|
| **Python 3.12+** | Runtime (`pyproject.toml` — `requires-python = ">=3.12"`) |
| **pip / venv** | Dependency install |
| **git** | Repo already cloned |
| **curl** | Drive the API once it's running |
| **sqlite3** CLI (optional) | Inspect the local demo DB |
| **uuidgen** (optional) | Generate test UUIDs for headers/seed data |

**Only needed for the full real pipeline** (not required for the quick local demo):

| Tool | Why |
|---|---|
| PostgreSQL | Production datastore (`LEASE_ABSTRACTION_DATABASE_URL`) |
| Kafka broker | Event bus — `document.uploaded` in, `lease.extraction.completed`/`dead-letter` out |
| AWS credentials | Real Textract OCR calls |
| Anthropic API key | Real Claude extraction (primary provider) |
| OpenAI API key | Real failover provider (FR-012) |
| Alembic | Applying migrations against real Postgres (`alembic upgrade head`) |

## Quick local demo (SQLite, no Kafka/Postgres/AWS)

This is the fastest way to confirm the service runs and its API behaves correctly. It bypasses
OCR/Kafka entirely by seeding data directly into the database.

1. `cd services/lease-abstraction`

2. Create the virtual environment:
   ```bash
   python3 -m venv .venv
   ```

3. Install dependencies:
   ```bash
   .venv/bin/pip install -e ".[dev]"
   ```
   (or install the dependency list from `pyproject.toml` directly, without the editable install,
   if the package doesn't need to be importable outside `pytest`'s `pythonpath`)

4. Create `.env` in this directory (gitignored — never commit it) with at minimum:
   ```
   LEASE_ABSTRACTION_ANTHROPIC_API_KEY=<your key>
   ```
   Add `LEASE_ABSTRACTION_OPENAI_API_KEY=<your key>` too if you want to test the failover path.

5. Bootstrap the database schema:
   ```bash
   LEASE_ABSTRACTION_DATABASE_URL="sqlite+aiosqlite:///./local_demo.db" \
     .venv/bin/python -c "import asyncio; from src.models.db import create_all; asyncio.run(create_all())"
   ```

6. Run the automated test suite to confirm the codebase is healthy:
   ```bash
   .venv/bin/python -m pytest tests/ -q
   .venv/bin/ruff check src/ tests/
   ```
   Expect: 31 passed, lint clean.

7. Start the API server in the background:
   ```bash
   LEASE_ABSTRACTION_DATABASE_URL="sqlite+aiosqlite:///./local_demo.db" \
     nohup .venv/bin/uvicorn src.api.main:app --port 8000 --host 127.0.0.1 &> /tmp/server.log &
   ```

8. Verify it's up:
   ```bash
   curl -sf http://127.0.0.1:8000/openapi.json
   ```

9. Seed a realistic record. There's no Kafka broker in this mode, so nothing will call
   `document.uploaded` for you — insert a `LeaseDocument` + `ExtractedField` directly.

   Write the seed script to a temp file with a quoted heredoc (`'PYEOF'`) rather than an inline
   `python -c "..."` one-liner — a long multi-line string with nested quotes is easy for a shell
   to misparse when copy-pasted (e.g. `unexpected EOF while looking for matching quote`); a
   heredoc avoids shell quote-parsing entirely:
   Note the body below is indented with a single tab per line and uses `<<-` (not `<<`), so the
   leading tab is stripped from every line — including the `PYEOF` terminator — regardless of
   how much markdown-list indentation your copy tool adds on top:
   ```bash
   cat > ./seed_demo.py <<-'PYEOF'
	import asyncio
	import uuid
	from datetime import datetime, timezone

	from src.models.db import session_scope
	from src.models.lease_document import LeaseDocument
	from src.models.extracted_field import ExtractedField
	from src.models.enums import OcrStatus, RunType, FieldType, VerificationStatus

	TEAM_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
	DOC_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
	FIELD_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


	async def seed():
	    async with session_scope() as session:
	        session.add(LeaseDocument(
	            id=DOC_ID, deal_id=uuid.uuid4(), team_id=TEAM_ID, allowed_teams=[TEAM_ID],
	            s3_key="lease-bucket/leases/demo.pdf", sha256="demo-sha",
	            ocr_status=OcrStatus.COMPLETE, run_type=RunType.LIVE,
	            uploaded_at=datetime.now(timezone.utc),
	        ))
	        session.add(ExtractedField(
	            id=FIELD_ID, lease_document_id=DOC_ID, field_type=FieldType.BASE_RENT,
	            extracted_value={"amount": 38.50, "unit": "USD_PER_SQFT_PER_YEAR"},
	            confidence_score=0.97, model_version="demo-seed",
	            verification_status=VerificationStatus.UNVERIFIED,
	        ))


	asyncio.run(seed())
	print(DOC_ID, FIELD_ID, TEAM_ID)
	PYEOF

   LEASE_ABSTRACTION_DATABASE_URL="sqlite+aiosqlite:///./local_demo.db" \
     .venv/bin/python ./seed_demo.py
   ```
   (Run from `services/lease-abstraction`, same as the rest of this guide — `python -c` implicitly
   puts the current directory on `sys.path` so `import src...` resolves; running a script from
   `/tmp` would not, since `src` isn't installed as an importable package name.)

10. Drive it with `curl` (headers `X-User-Id` / `X-Team-Id` stand in for the platform's real
    AuthN/AuthZ gateway — see `src/api/deps.py`):

    ```bash
    DOC=22222222-2222-2222-2222-222222222222
    FIELD=33333333-3333-3333-3333-333333333333
    TEAM=11111111-1111-1111-1111-111111111111

    # View the auto-populated field (still UNVERIFIED)
    curl -s -H "X-User-Id: $(uuidgen)" -H "X-Team-Id: $TEAM" \
      "http://127.0.0.1:8000/v1/lease-documents/$DOC/extracted-fields"

    # Confirm it as-is (User Story 1)
    curl -s -X POST -H "X-User-Id: $(uuidgen)" -H "X-Team-Id: $TEAM" -H "Content-Type: application/json" \
      -d '{}' "http://127.0.0.1:8000/v1/lease-documents/$DOC/extracted-fields/$FIELD/verify"

    # Re-verify -> expect 409 (terminal-state guard, FR-008)
    curl -s -o /dev/stderr -w "\nHTTP %{http_code}\n" -X POST \
      -H "X-User-Id: $(uuidgen)" -H "X-Team-Id: $TEAM" -H "Content-Type: application/json" \
      -d '{"value": {"amount": 1.0}}' \
      "http://127.0.0.1:8000/v1/lease-documents/$DOC/extracted-fields/$FIELD/verify"

    # Different team -> expect 403 (information barrier, FR-018)
    curl -s -o /dev/stderr -w "\nHTTP %{http_code}\n" \
      -H "X-User-Id: $(uuidgen)" -H "X-Team-Id: $(uuidgen)" \
      "http://127.0.0.1:8000/v1/lease-documents/$DOC/extracted-fields"

    # Review queue and metrics endpoints
    curl -s "http://127.0.0.1:8000/v1/review-queue?teamId=$TEAM" \
      -H "X-User-Id: $(uuidgen)" -H "X-Team-Id: $TEAM"
    curl -s -X POST -H "Content-Type: application/json" \
      -d '{"sample_lease_ids": ["'$(uuidgen)'"], "measured_median_minutes": 172.5, "method": "demo timing"}' \
      "http://127.0.0.1:8000/v1/baseline-measurements"
    ```

11. Test the real Claude extraction adapter directly (bypasses the API/Kafka entirely, calls
    Anthropic for real using the key from `.env`):
    ```bash
    .venv/bin/python -c "
    from src.extraction.claude_adapter import ClaudeExtractionAdapter
    adapter = ClaudeExtractionAdapter()
    results = adapter.extract_fields('''<OCR'd lease text here>''')
    for r in results:
        print(r.field_type.value, r.confidence, r.value)
    "
    ```

12. Stop the server and clean up:
    ```bash
    pkill -f "uvicorn src.api.main:app"
    rm -f local_demo.db seed_demo.py
    ```

## Full production-like stack

1. Steps 1–4 above, but point `LEASE_ABSTRACTION_DATABASE_URL` at a real Postgres instance and
   `LEASE_ABSTRACTION_KAFKA_BOOTSTRAP_SERVERS` at a real broker.
2. Apply migrations properly instead of `create_all()`:
   ```bash
   alembic upgrade head
   ```
3. Start the API: `uvicorn src.api.main:app`
4. Start the live consumer (currently **no `__main__`/CLI entrypoint exists for this** — see Known
   Gaps below; would need a small runner script looping `RetryingConsumer.run_once()` against
   `DocumentUploadedConsumer.handle()`, the same pattern already used by
   `BackfillProcessor.run_forever()`).
5. Start the backfill consumer if processing historical leases:
   ```python
   import asyncio
   from src.consumers.backfill_consumer import BackfillProcessor
   asyncio.run(BackfillProcessor().run_forever())
   ```
6. Publish a real `document.uploaded` event (contracts/events.md schema) to trigger
   OCR → Claude/OpenAI extraction → auto-populate or review queue.

## Known gaps

- **No standalone entrypoint for the live consumer.** Only `BackfillProcessor` has a `run_forever()`
  loop; the live `document.uploaded` path (`DocumentUploadedConsumer` + `RetryingConsumer`) has no
  equivalent runner script yet — needed before this can run as a real background worker.
- **`docs/UI_INTEGRATION.md`** (FR-006/SC-004): review queue is API-only; no frontend exists.
- **`docs/BASELINE_STUDY.md`** (FR-019/SC-001): manual-abstraction baseline hasn't been measured.
