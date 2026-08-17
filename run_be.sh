#!/usr/bin/env bash
# Launches the BE FastAPI service with Uvicorn. Run from anywhere --
# cds to this script's own directory (the project root) first.
set -e
cd "$(dirname "$0")/BE"
python3 -m uvicorn app.main:app --host "${BE_HOST:-0.0.0.0}" --port "${BE_PORT:-8000}" --reload
