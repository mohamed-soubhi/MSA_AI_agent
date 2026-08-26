#!/usr/bin/env bash
# Launches the CLI agent. Safe to run from any directory --
# cds to this script's own folder first (the project root),
# so agent/CLI_agent.py always resolves regardless of where invoked.
set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# See run_be.sh -- a venv built on one OS can't be reused on another.
export UV_PROJECT_ENVIRONMENT="$ROOT_DIR/.venv-linux"

uv run agent/CLI_agent.py
