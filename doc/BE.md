# BE/ — backend service (FastAPI + Uvicorn + Nginx)

Bare scaffold, no agent wiring yet — proves the stack runs end to end
(`/health` only) so the actual chat API can be designed and added on
top of a known-working base. A separate top-level folder, sitting next
to `agent/`, `workspace/`, `tests/`, `doc/` — a permanent part of the
project, not sandboxed content `agent/` builds.

## Layout

```
BE/
├── app/
│   ├── main.py           — FastAPI app factory (create_app()) + module-level `app`
│   ├── api/
│   │   └── health.py      — GET /health
│   └── core/
│       └── config.py      — Settings (pydantic-settings), BE_-prefixed env vars
├── tests/
│   ├── conftest.py         — adds BE/ to sys.path (same pattern as tests/conftest.py)
│   └── test_health.py
├── nginx/
│   └── nginx.conf          — reverse proxy: Nginx :80 → Uvicorn 127.0.0.1:8000
├── requirements.txt
├── pytest.ini
└── .env.example
```

## Running it

```bash
cd BE
python3 -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Then either:
- `../run_be.sh` (or `run_be.bat` on Windows) from the project root, or
- `uvicorn app.main:app --reload` from inside `BE/` directly.

Both read `BE_HOST`/`BE_PORT` (default `0.0.0.0:8000`). Copy
`.env.example` to `.env` and adjust as needed — `BE_CORS_ORIGINS` in
particular, once a real frontend origin exists (empty by default = no
cross-origin access at all).

**Nginx**: `nginx -c $(pwd)/BE/nginx/nginx.conf` (or install the config
under `/etc/nginx/sites-available/` on a real box). Requires Uvicorn
already running on the upstream port. Already wired for WebSocket
upgrade (`Connection: upgrade`), even though nothing uses it yet — so
adding a streaming/WebSocket chat endpoint later won't need an Nginx
config change.

## Tests

```bash
cd BE
pytest tests/ -v
```

`app.main.create_app()` is a factory (not a shared module-level
singleton) specifically so tests can build a fresh app instance per
test — same reasoning as `tests/test_CLI_agent_main.py`'s per-test
module reload on the agent side.

## Config (`app/core/config.py`)

| Setting | Env var | Default | Purpose |
|---|---|---|---|
| `app_name` | `BE_APP_NAME` | `"agent-backend"` | Returned by `/health`, shown in FastAPI's auto-docs. |
| `app_version` | `BE_APP_VERSION` | `"0.1.0"` | Returned by `/health`. |
| `host` | `BE_HOST` | `"0.0.0.0"` | Read by `run_be.sh`/`run_be.bat`. |
| `port` | `BE_PORT` | `8000` | Read by `run_be.sh`/`run_be.bat`; must match `nginx.conf`'s `upstream` if changed. |
| `cors_origins` | `BE_CORS_ORIGINS` | `""` (none) | Comma-separated allowed origins. Empty = no cross-origin access. |
| `log_level` | `BE_LOG_LEVEL` | `"info"` | Not yet wired to anything — reserved for when structured logging is added. |

All `BE_`-prefixed, deliberately distinct from the agent's own env vars
(`WORKSPACE_DIR`, `MEMORY_FILE`, `SYSTEM_PROMPT`, ...) so the two
processes never collide if they ever share an environment.

## Not done yet (deliberately out of scope for this scaffold)

- No agent wiring — `/health` is the only route. The chat API (however
  it ends up shaped — REST, WebSocket, SSE) needs its own design pass
  once the UI's requirements are clearer.
- No auth.
- No Dockerfile / containerization.
- No CI config for this service specifically.
- No production Nginx hardening (TLS, rate limiting, security headers) —
  `nginx.conf` here is a local-dev reverse-proxy template, not a
  production config.
