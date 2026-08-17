# BE/ — backend service (FastAPI + Uvicorn + Nginx)

Health check, an interactive config editor, and a plain conversational
chat page over the agent's own `OllamaAgent`. A separate top-level
folder, sitting next to `agent/`, `workspace/`, `tests/`, `doc/` — a
permanent part of the project, not sandboxed content `agent/` builds.

## Layout

```
BE/
├── app/
│   ├── main.py           — FastAPI app factory (create_app()) + module-level `app`
│   ├── api/
│   │   ├── health.py      — GET /health
│   │   ├── config.py      — GET/POST /api/config (interactive config editor's API)
│   │   ├── models.py      — GET /api/models(/catalog) (local + cloud Ollama models, with specs)
│   │   └── chat.py        — GET/POST /api/chat/* (streaming chat, see "Chat page" below)
│   ├── core/
│   │   ├── config.py         — Settings (pydantic-settings), BE_-prefixed env vars
│   │   ├── config_schema.py  — field list + .env read/write + default-value resolver
│   │   └── agent_bridge.py   — reuses agent/shared.py's OllamaAgent for chat.py
│   └── static/
│       ├── config.html    — the editor page itself (served at GET /config)
│       └── chat.html      — the chat page itself (served at GET /chat)
├── tests/
│   ├── conftest.py         — adds BE/ to sys.path (same pattern as tests/conftest.py)
│   ├── test_health.py
│   ├── test_config.py
│   ├── test_models.py
│   └── test_chat.py
├── nginx/
│   └── nginx.conf          — reverse proxy: Nginx :80 → Uvicorn 127.0.0.1:8000
├── requirements.txt
├── pytest.ini
└── .env.example
```

## Chat page (`GET /chat`)

A two-pane page: chat on the left, an empty placeholder panel on the
right reserved for content tied to the conversation (not built yet).
Streams the model's reply token-by-token via Server-Sent Events.

- **No tool-calling yet, on purpose.** `shared.run_agent()` (the
  tool-calling loop) drives `fs_tools`/`shell_tools` through
  `confirm()`, which blocks on a real terminal `input()` — that has no
  meaning inside an HTTP request/response cycle. `app/core/agent_bridge.py`
  only uses `OllamaAgent.chat_stream()`, which never touches tools or
  `confirm()` at all. How a human approves a tool call over HTTP is a
  real, separate design question for later.
- **One shared `OllamaAgent` instance**, reused across every request in
  this BE process (`agent_bridge.get_agent()`) — the exact same
  hardened chat wrapper (timeout/retry/friendly-errors) the CLI agent
  uses, not a second reimplementation.
- **One in-memory conversation**, held in `app/api/chat.py`'s
  module-level `_messages` list. Matches a single local user, same
  simplicity choice as the CLI agent's one-conversation-per-run design.
  Cleared by `POST /api/chat/reset` ("New chat" button) or a BE
  restart — nothing persists to disk.
- **SSE protocol**: each event is `data: <json>\n\n` —
  `{"delta": "..."}` per chunk, `{"error": "..."}` if the model call
  fails partway through, always ending with `{"done": true}`. The
  client can't use a plain `EventSource` (GET-only, and this needs to
  POST the message body) — `chat.html` reads the streaming response
  body manually via `fetch()` + `ReadableStream`.
- **Logged through the agent's own `chat_logger.py`** — same JSONL
  format, same `logs/` directory as the CLI agent, including
  `prompt_eval_count`/`eval_count`/durations (captured from the
  stream's final chunk via `OllamaAgent.last_stream_stats`, since
  `chat_stream()` itself only yields plain text — see `shared.py`). One
  JSONL "session" = one conversation: opens on the first message,
  closes with `session_end` on `POST /reset` or BE shutdown.

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

- No tool-calling in the chat page — plain conversation only. Wiring
  `fs_tools`/`shell_tools`/`memory` in means designing how a human
  approves a tool call over HTTP (`confirm()` blocks on a real terminal
  today) — a real, separate piece of work.
- No auth on the chat page itself, nor rate limiting.
- No auth.
- No Dockerfile / containerization.
- No CI config for this service specifically.
- No production Nginx hardening (TLS, rate limiting, security headers) —
  `nginx.conf` here is a local-dev reverse-proxy template, not a
  production config.
