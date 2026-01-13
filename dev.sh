#!/usr/bin/env bash
# PerceptionAI unified dev runner (absolute paths + auto venv)
# Usage: bash scripts/dev.sh

set -euo pipefail

# ---- Resolve absolute repo root no matter where it's run from ----
if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
  ROOT_DIR="$(git rev-parse --show-toplevel)"
else
  SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
  ROOT_DIR="$(dirname "$SCRIPT_DIR")"
fi

FRONTEND_PORT="${FRONTEND_PORT:-5175}"
SERVER_DIR="$ROOT_DIR/server"
WEB_DIR="$ROOT_DIR/web"

echo "🔎 Paths:"
echo "  ROOT_DIR   = $ROOT_DIR"
echo "  SERVER_DIR = $SERVER_DIR"
echo "  WEB_DIR    = $WEB_DIR"
echo

# ---- Sanity checks ----
[ -d "$SERVER_DIR" ] || { echo "❌ Missing $SERVER_DIR"; exit 1; }
[ -d "$WEB_DIR" ]    || { echo "❌ Missing $WEB_DIR"; exit 1; }

# ---- Pick Python ----
PY_BIN="$(command -v python3 || true)"
[ -n "$PY_BIN" ] || { echo "❌ python3 not found (install via Homebrew: brew install python)"; exit 1; }

# ---- Ensure venv exists (absolute path) ----
if [ ! -d "$SERVER_DIR/.venv" ]; then
  echo "🐍 Creating virtual environment at $SERVER_DIR/.venv ..."
  "$PY_BIN" -m venv "$SERVER_DIR/.venv"
fi

# ---- Activate venv (absolute path) ----
if [ ! -f "$SERVER_DIR/.venv/bin/activate" ]; then
  echo "❌ venv activation script not found: $SERVER_DIR/.venv/bin/activate"
  exit 1
fi
# shellcheck disable=SC1091
source "$SERVER_DIR/.venv/bin/activate"

# ---- Backend deps ----
if [ ! -f "$SERVER_DIR/requirements.txt" ]; then
  echo "❌ Missing $SERVER_DIR/requirements.txt"
  exit 1
fi
if [ ! -f "$SERVER_DIR/.deps_installed" ]; then
  echo "📦 Installing backend deps..."
  pip install --upgrade pip
  pip install -r "$SERVER_DIR/requirements.txt"
  touch "$SERVER_DIR/.deps_installed"
else
  echo "✅ Backend deps already installed."
fi

echo "🚀 Starting backend (FastAPI) on :8001 ..."
cd "$SERVER_DIR"
"$SERVER_DIR/.venv/bin/python" -m uvicorn app.main:app --reload --port 8001 &
BACK_PID=$!

# ---- Frontend deps ----
cd "$WEB_DIR"
if [ ! -d "$WEB_DIR/node_modules" ]; then
  echo "📦 Installing frontend deps..."
  npm install
else
  echo "✅ Frontend deps already installed."
fi

echo "🎨 Starting frontend (Vite) on :$FRONTEND_PORT ..."
# force the port even if vite.config missing
npm run dev -- --port "$FRONTEND_PORT" &
WEB_PID=$!

echo
echo "✅ Frontend should be at: http://localhost:$FRONTEND_PORT"
echo "✅ Backend   should be at: http://localhost:8001/docs"
echo


# ---- Cleanup on Ctrl+C ----
trap 'echo; echo "🛑 Shutting down..."; kill $BACK_PID 2>/dev/null || true; kill $WEB_PID 2>/dev/null || true; exit 0' INT
wait
