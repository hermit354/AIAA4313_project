#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
PYTHON="$ROOT/.venv/Scripts/python.exe"
[ -x "$PYTHON" ] || PYTHON=python
"$PYTHON" -m alembic -c "$ROOT/web_demo/alembic.ini" upgrade head
"$PYTHON" -m uvicorn web_demo.backend:app --app-dir "$ROOT" --reload --port 8000 &
API_PID=$!
cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$ROOT/web_demo/frontend"
exec npm run dev
