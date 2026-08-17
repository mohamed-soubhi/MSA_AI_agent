@echo off
REM Launches the BE FastAPI service with Uvicorn. Safe to double-click
REM or run from any directory -- cds to this script's own folder first.
cd /d "%~dp0BE"
if "%BE_HOST%"=="" set BE_HOST=0.0.0.0
if "%BE_PORT%"=="" set BE_PORT=8000
python -m uvicorn app.main:app --host %BE_HOST% --port %BE_PORT% --reload
pause
