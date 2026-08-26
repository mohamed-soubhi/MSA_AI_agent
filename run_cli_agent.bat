@echo off
REM Launches the CLI agent. Safe to double-click or run from any
REM directory -- cds to this script's own folder first (the project
REM root), so agent\CLI_agent.py always resolves regardless of where
REM the .bat was invoked from.
cd /d "%~dp0"

REM See run_be.bat -- a venv built on one OS can't be reused on another.
set UV_PROJECT_ENVIRONMENT=%~dp0.venv-windows

uv run agent\CLI_agent.py
pause
