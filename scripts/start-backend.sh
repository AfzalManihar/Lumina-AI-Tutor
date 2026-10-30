#!/usr/bin/env bash
# Creates backend/.venv if needed, installs dependencies, and starts the API on http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")/../backend"
PY="${PYTHON:-python3}"
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet -r requirements.txt
[ -f .env ] || echo "NOTE: backend/.env not found - copy ../.env.example to backend/.env and fill in values."
exec uvicorn app.main:app_factory --factory --reload --host 127.0.0.1 --port "${PORT:-8000}"
