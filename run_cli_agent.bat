@echo off
REM Launches the CLI agent. Safe to double-click or run from any
REM directory -- cds to this script's own folder first (the project
REM root), so agent\CLI_agent.py always resolves regardless of where
REM the .bat was invoked from.
cd /d "%~dp0"
python agent\CLI_agent.py
pause
