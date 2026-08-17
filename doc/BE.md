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
│   │   ├── health.py      — GET /health
│   │   ├── config.py      — GET/POST /api/config (interactive config editor's API)
│   │   └── models.py      — GET /api/models (local + cloud Ollama models, with specs)
│   ├── core/
│   │   ├── config.py         — Settings (pydantic-settings), BE_-prefixed env vars
│   │   └── config_schema.py  — field list + .env read/write + default-value resolver
│   └── static/
│       └── config.html    — the editor page itself (served at GET /config)
├── tests/
│   ├── conftest.py         — adds BE/ to sys.path (same pattern as tests/conftest.py)
│   ├── test_health.py
│   ├── test_config.py
│   └── test_models.py
├── nginx/
│   └── nginx.conf          — reverse proxy: Nginx :80 → Uvicorn 127.0.0.1:8000
├── requirements.txt
├── pytest.ini
└── .env.example
```

## Config editor (`GET /config`)

An interactive page for editing every agent + BE setting, backed by
`GET/POST /api/config`. Open `http://<host>:8000/config` (or through
Nginx, `http://<host>/config`) while the BE service is running.

- **Reads live**: the page always shows the *currently effective*
  value of every setting — `agent/.env` overrides, real env vars, or
  the built-in default, whichever actually won. Field metadata (label,
  grouping, type, description) comes from one schema,
  `app/core/config_schema.py`'s `FIELDS` list — the single source of
  truth both the form and the save logic use, so they can't drift
  apart.
- **Writes to two files**: agent settings (`agent_config.py`/
  `log_config.py`) go to `agent/.env`; `BE_`-prefixed settings go to
  `BE/.env`. Existing lines (comments, unrelated keys) are preserved —
  only the submitted keys are added or updated in place.
- **Not live** — saving does **not** restart or hot-reload anything.
  Both the agent and this BE process read their `.env` file exactly
  once, at startup (`agent_config.py`/`log_config.py` call
  `load_dotenv()` on import; BE's `Settings` reads `env_file` the same
  way). A saved change takes effect the **next time each process is
  restarted** — this is deliberate, not a bug: exactly what was asked
  for ("saved in .env that can be loaded when restart").
- Values are double-quoted and escaped on write, so `SYSTEM_PROMPT`'s
  embedded newlines round-trip correctly through `python-dotenv` on
  the next load.
- **Recommended defaults, shown per field**: a small "Recommended
  default: ..." hint (with a one-click "Use default" button) appears
  under every field, alongside its current value. For agent-side
  fields, this is **not** a hand-maintained duplicate list — see
  `config_schema.agent_defaults()` below.
- **"Load models" dropdown** on the Model field, backed by two
  endpoints fetched in parallel:
  - `GET /api/models` — asks the local Ollama server for every model
    it already knows about (`ollama.Client().list()`), split into
    **Local** (pulled, fully on this machine — real specs: size,
    parameter count, quantization, family) and **Cloud (in use)**
    (already registered, name ends in `:cloud`, no local specs to
    show).
  - `GET /api/models/catalog` — browses Ollama's full **public** cloud
    catalog directly from `ollama.com/api/tags` (verified live: 19
    models, unauthenticated), independent of what's already
    pulled/registered — shown as **"Cloud catalog (browse all)"**.
    Sends `OLLAMA_API_KEY` (a plain, unprefixed env var — Ollama's own
    convention, not `BE_`-namespaced) as a Bearer token if set; not
    required today, but a `401` from that endpoint surfaces a clear
    "set OLLAMA_API_KEY" message rather than a raw error.
  Click any entry in any group to fill the Model field with its tag.
  Either endpoint being unreachable shows its own error line instead
  of breaking the whole dropdown.

### `config_schema.agent_defaults()` — drift-safe default values

Rather than a second, hand-maintained list of default values (which
could silently fall out of sync whenever `agent_config.py`/
`log_config.py` change), the "Recommended default" shown for every
agent-side field is computed by actually **re-importing those two
files fresh, in an isolated subprocess**, with `load_dotenv()`
neutralized and every agent-target env var stripped from that
subprocess's environment first. Whatever the resulting Python
attributes are — straight from the real source, not a copy — is the
default shown in the UI. Cached for the life of the BE process
(`functools.lru_cache`; restart to pick up an actual code change to a
default). BE-side (`BE_*`) defaults don't need this — pydantic-settings
already keeps a field's declared default separate from its
env-file-overridden value, so those are read directly off
`Settings.model_fields`.

See [agent_config.md](agent_config.md) for the full settings reference.

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

- No agent wiring — `/health`, `/config`, and `/api/models` are the
  only routes. The chat API (however it ends up shaped — REST,
  WebSocket, SSE) needs its own design pass once the UI's requirements
  are clearer.
- No auth.
- No Dockerfile / containerization.
- No CI config for this service specifically.
- No production Nginx hardening (TLS, rate limiting, security headers) —
  `nginx.conf` here is a local-dev reverse-proxy template, not a
  production config.
