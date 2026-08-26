@echo off
REM Launches the BE FastAPI service with Uvicorn via `uv run`, using the
REM root pyproject.toml/uv.lock -- no manual venv activation needed, uv
REM creates/reuses .venv itself. Safe to double-click or run from any
REM directory -- cds to this script's own folder first.
set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
cd /d "%ROOT_DIR%"
if "%BE_HOST%"=="" set BE_HOST=127.0.0.1
if "%BE_PORT%"=="" set BE_PORT=8000

REM Lock directory is shared with run_be.sh (same repo path, reachable from
REM both Windows and WSL) so simultaneous launches can't race onto the same
REM port -- a plain "is the port open" check has a gap between two
REM processes starting at nearly the same instant.
set LOCK_ROOT=%ROOT_DIR%\.port-locks
if not exist "%LOCK_ROOT%" mkdir "%LOCK_ROOT%"

:check_port
powershell -NoProfile -Command "if ((Test-NetConnection -ComputerName '%BE_HOST%' -Port %BE_PORT% -WarningAction SilentlyContinue).TcpTestSucceeded) { exit 0 } else { exit 1 }"
if %ERRORLEVEL%==0 (
    echo Port %BE_PORT% is in use, trying next port...
    set /a BE_PORT=%BE_PORT%+1
    goto check_port
)

set LOCK_DIR=%LOCK_ROOT%\%BE_PORT%
mkdir "%LOCK_DIR%" 2>nul
if errorlevel 1 (
    REM Lock exists. Only steal it if it's old (crashed/killed run) --
    REM otherwise another launch may just be mid-startup.
    powershell -NoProfile -Command "if (((Get-Date) - (Get-Item '%LOCK_DIR%').LastWriteTime).TotalSeconds -le 30) { exit 1 } else { exit 0 }"
    if errorlevel 1 (
        echo Port %BE_PORT% is reserved by another launch, trying next port...
        set /a BE_PORT=%BE_PORT%+1
        goto check_port
    )
    rmdir "%LOCK_DIR%" 2>nul
    mkdir "%LOCK_DIR%" 2>nul
    if errorlevel 1 (
        set /a BE_PORT=%BE_PORT%+1
        goto check_port
    )
)

echo.
echo Open the UI at:
echo   Chat:   http://%BE_HOST%:%BE_PORT%/chat
echo   Config: http://%BE_HOST%:%BE_PORT%/config
echo.

uv run --directory "%ROOT_DIR%" uvicorn app.main:app --app-dir BE ^
  --reload --reload-dir "%ROOT_DIR%\BE" --host %BE_HOST% --port %BE_PORT%
rmdir "%LOCK_DIR%" 2>nul
pause
