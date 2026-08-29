#!/usr/bin/env bash
# Launches the BE FastAPI service with Uvicorn via `uv run`, using the
# root pyproject.toml/uv.lock -- no manual venv activation needed, uv
# creates/reuses .venv itself. Run from anywhere -- cds to this
# script's own directory (the project root) first.
set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# A venv built on one OS can't be reused on another (WSL vs. Windows --
# different binaries, symlink layout). If this same repo path is also
# used from Windows (e.g. /mnt/c/... == C:\...), each OS needs its own
# venv directory so they never collide/corrupt each other.
export UV_PROJECT_ENVIRONMENT="$ROOT_DIR/.venv-linux"

HOST="${BE_HOST:-127.0.0.1}"
PORT="${BE_PORT:-8000}"

# Lock directory is shared with run_be.bat (same repo path, reachable from
# both WSL and Windows) so simultaneous launches can't race onto the same
# port -- a plain "is the port open" check has a TOCTOU gap between two
# processes starting at nearly the same instant.
LOCK_ROOT="$ROOT_DIR/.port-locks"
mkdir -p "$LOCK_ROOT"

is_port_open() {
  (exec 3<>"/dev/tcp/$HOST/$1") 2>/dev/null && { exec 3>&-; return 0; } || return 1
}

# A lock older than this with nothing listening is from a crashed/killed
# run, not a launch still starting up (uvicorn takes a couple seconds to
# bind) -- safe to steal.
STALE_SECONDS=30

while :; do
  if is_port_open "$PORT"; then
    PORT=$((PORT + 1))
    continue
  fi
  if mkdir "$LOCK_ROOT/$PORT" 2>/dev/null; then
    break
  fi
  # Lock dir exists. Only steal it if it's old AND nothing is listening --
  # otherwise another launch may just be mid-startup.
  LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_ROOT/$PORT" 2>/dev/null || echo "$(date +%s)") ))
  if [ "$LOCK_AGE" -gt "$STALE_SECONDS" ] && ! is_port_open "$PORT"; then
    rmdir "$LOCK_ROOT/$PORT" 2>/dev/null
    if mkdir "$LOCK_ROOT/$PORT" 2>/dev/null; then
      break
    fi
  fi
  PORT=$((PORT + 1))
done
trap 'rmdir "$LOCK_ROOT/$PORT" 2>/dev/null' EXIT INT TERM

echo ""
echo "Open the UI at:"
echo "  Chat:   http://$HOST:$PORT/chat"
echo "  Config: http://$HOST:$PORT/config"
echo ""

# Watch only BE/app -- the live server code. Deliberately NOT all of
# BE/: the automated "AGY Tester and Reviewer" writes test/doc files
# into BE/tests/ on its own schedule, and a reload landing on an
# in-flight /api/chat/stream turn aborts it with a noisy
# KeyboardInterrupt/CancelledError unwind. (--reload-exclude is avoided
# for parity with run_be.bat, where `uv run` glob-expands the pattern
# against the repo root on Windows before uvicorn sees it.)
uv run --directory "$ROOT_DIR" uvicorn app.main:app --app-dir BE \
  --reload --reload-dir "$ROOT_DIR/BE/app" \
  --host "$HOST" --port "$PORT"
