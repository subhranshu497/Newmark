#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -d ".venv" ] && ! .venv/bin/python3 -c "" 2>/dev/null; then
  # Stale venv (e.g. this directory was moved/renamed since it was created,
  # which breaks the absolute shebang paths in .venv/bin/*).
  rm -rf .venv
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

pip install -e ".[dev]" -q

if [ ! -f "local_demo.db" ]; then
  python -c "import asyncio; from src.models.db import create_all; asyncio.run(create_all())"
fi

exec uvicorn src.api.main:app --reload
