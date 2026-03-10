#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="python3"
if [ -x ".venv/bin/python" ]; then
    # Use the project-local interpreter directly because copied entrypoint
    # wrappers can keep stale shebangs from the source machine.
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
fi

set -a
[ -f ".env" ] && source .env
[ -f ".env.local" ] && source .env.local
set +a

export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:$PYTHONPATH}"
: "${CHAINLIT_AUTH_SECRET:=dev-local-secret-change-me-32chars-min}"
: "${CHAINLIT_HOST:=0.0.0.0}"
: "${CHAINLIT_PORT:=8000}"
: "${DATABASE_URL:=postgresql://cdpadmin:cdpadmin123@localhost:5432/cdp?sslmode=disable}"

exec "$PYTHON_BIN" -m uvicorn src.app:chainlit_server_app --host "$CHAINLIT_HOST" --port "$CHAINLIT_PORT"
