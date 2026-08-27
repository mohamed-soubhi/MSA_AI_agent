# BE/ — backend service (FastAPI + Uvicorn + Nginx)

Health check, an interactive config editor, and a full tool-calling
chat page over the agent's own `OllamaAgent`/`run_agent()` — the same
9 tools and confirm() gate `CLI_agent.py` uses, approved over HTTP
instead of a terminal. A separate top-level folder, sitting next to
`agent/`, `workspace/`, `tests/`, `doc/` — a permanent part of the
project, not sandboxed content `agent/` builds.

## Layout

```
BE/
├── app/
│   ├── main.py           — FastAPI app factory (create_app()) + module-level `app`
│   ├── api/
│   │   ├── health.py      — GET /health
│   │   ├── config.py      — GET/POST /api/config (interactive config editor's API)
│   │   ├── models.py      — GET /api/models(/catalog) (local + cloud Ollama models, with specs)
│   │   ├── chat.py        — GET/POST /api/chat/* (tool-calling chat, incl. GET /history, see "Chat page" below)
│   │   ├── memory.py      — GET /api/memory (read-only view of memory.json for config UI)
│   │   └── workspace.py   — GET /api/workspace/file (sandboxed file preview for chat's Preview tab)
│   ├── core/
│   │   ├── config.py           — Settings (pydantic-settings), BE_-prefixed env vars
│   │   ├── config_schema.py    — field list + .env read/write + default-value resolver
│   │   ├── agent_bridge.py     — reuses agent/shared.py's OllamaAgent for chat.py
│   │   ├── tool_bridge.py      — the same 9 tools CLI_agent.py wires up
│   │   └── approval_bridge.py  — ConversationTurn: runs run_agent() on a background
│   │                              thread, routes confirm()/ask_human() over SSE + HTTP
│   └── static/
│       ├── config.html    — the editor page itself (served at GET /config, with unlock gate & memory view)
│       └── chat.html      — the chat page itself (served at GET /chat)
├── tests/
│   ├── conftest.py           — adds BE/ and agent/ to sys.path
│   ├── test_health.py
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_chat.py
│   ├── test_memory_api.py    — read-only memory API tests
│   ├── test_workspace.py     — GET /api/workspace/file (Preview tab backend)
│   └── test_approval_bridge.py  — direct unit tests of ConversationTurn's approval/human handoff
├── nginx/
│   └── nginx.conf          — reverse proxy: Nginx :80 → Uvicorn 127.0.0.1:8000
├── requirements.txt
├── pytest.ini
└── .env.example
```

## Chat page (`GET /chat`)

A two-pane page: chat on the left, a live **Activity** panel on the
right showing tool calls, tool results, and any pending
approval/question. Runs the full tool-calling loop (`shared.run_agent()`)
over Server-Sent Events, streaming every step back as it happens.

- **Same 9 tools as `CLI_agent.py`, exactly.** `app/core/tool_bridge.py`
  imports `list_directory`/`read_file`/`write_file`/`create_directory`
  (`fs_tools.py`), `run_command` (`shell_tools.py`),
  `ask_human`/`ask_human_choice` (`human_tools.py`), and
  `remember_fact`/`recall_memory` (`memory.py`) — the same functions
  `CLI_agent.py`'s `main()` wires up, never reimplemented. Same
  sandbox (`fs_tools.BASE_DIR` / `WORKSPACE_DIR`), same shell allow/
  block lists, same everything — only the approval channel differs.
- **Approval over HTTP, not a terminal.** `confirm()` (`confirm.py`)
  and `ask_human()`/`ask_human_choice()` (`human_tools.py`) each gained
  a pluggable backend (`set_confirm_backend()`/`set_human_backend()`,
  a lock-protected module global — not `contextvars`, since
  `shared._run_tool_with_timeout` runs every tool call in its own
  `ThreadPoolExecutor` worker thread, which wouldn't inherit a
  contextvar set on the calling thread). `app/core/approval_bridge.py`'s
  `ConversationTurn` runs one `run_agent()` call on a background
  thread, installs itself as that backend for the duration, and turns
  every confirm()/ask_human() call into: push an `approval_request`/
  `human_request` SSE event → block on an internal queue → resume once
  `POST /api/chat/respond` answers it. The CLI's terminal behavior is
  completely unchanged (default backend is `None`) — only this BE
  process ever installs one.
- **One shared `OllamaAgent` instance**, reused across every request in
  this BE process (`agent_bridge.get_agent()`) — the exact same
  hardened chat wrapper (timeout/retry/friendly-errors) the CLI agent
  uses, not a second reimplementation. `CHAT_SYSTEM_PROMPT` is the same
  `SYSTEM_PROMPT` the CLI seeds every session with.
- **One in-memory conversation, one turn at a time.** `app/api/chat.py`'s
  module-level `_messages` list matches a single local user, same
  simplicity choice as the CLI agent's one-conversation-per-run design.
  Only one `ConversationTurn` may run at once — a second
  `POST /api/chat/stream` while one is still in flight gets a `409`.
  Cleared by `POST /api/chat/reset` ("New chat" button, which also
  cancels any in-flight turn) or a BE restart — nothing persists to
  disk beyond the JSONL log and `memory.json`'s token counter.
- **Client disconnect mid-stream also clears the turn.** `event_generator()`
  polls `turn.events.get(timeout=1.0)` instead of blocking forever, checking
  `Request.is_disconnected()` between polls. If the browser navigates away or
  drops the connection while the background `ConversationTurn` is itself
  stuck waiting on a `confirm()`/`ask_human()` answer nobody will ever send,
  the turn is marked cancelled and `_current_turn` cleared immediately —
  same as the reset-triggered cancellation path — instead of wedging every
  future `POST /api/chat/stream` behind a `409` until a full BE restart.
- **SSE protocol**: each event is `data: <json>\n\n` with a `type`
  field — `thought` (model text for the round), `tool_call`/
  `tool_result`, `approval_request`/`approval_timeout`, `human_request`
  (`kind`: `"ask"` or `"choice"`, with `options` for the latter) /
  `human_timeout`, `final` (the finished answer), `error`, always
  ending with `stream_end`. Answer a pending request with
  `POST /api/chat/respond` — `{"request_id": ..., "approved": true|false}`
  for `approval_request`, `{"request_id": ..., "answer": "..."}` for
  `human_request` (a free-text answer for `"ask"`, the chosen option's
  1-based index as a string for `"choice"`). The client can't use a
  plain `EventSource` (GET-only, and this needs to POST the message
  body) — `chat.html` reads the streaming response body manually via
  `fetch()` + `ReadableStream`.
- **`GET /api/chat/history`** returns the durable transcript — user/
  assistant turns only (system prompt and tool messages excluded,
  since live tool activity is what the SSE stream itself carries as
  `thought`/`tool_call`/`tool_result` events). Used by `chat.html` to
  repaint the conversation on page reload.
- **Assistant answers get basic markdown rendering** (`renderMarkdown()`
  in `chat.html` -- bold, inline code, fenced code blocks, links,
  lists), hand-written since this is one static file with no build
  step/CDN. Escapes everything first, so only the specific patterns it
  recognizes produce real markup -- the model's own text can't inject
  raw HTML.
- **Preview tab, next to Activity**, for data-analysis output (an HTML
  report/Plotly chart the agent wrote). A **View** button appears on
  any `.html`/`.htm` mention: a `[label](path.html)` markdown link or a
  bare path in the answer text, and on the Activity panel's own
  `tool_call`/`tool_result` items (`addViewButtons()` scans the full
  arguments/output text, not just `write_file`'s `path` argument) --
  since the report is just as often produced by `run_command` (a
  Python one-liner calling `fig.write_html(...)`) as by the agent's own
  `write_file`, and the model usually just mentions the path as plain
  text rather than proper markdown link syntax. The iframe navigates
  (`src=`) directly to `GET /api/workspace/file-raw?path=...`
  (`app/api/workspace.py`, reusing `fs_tools.read_file()`'s own sandbox
  enforcement -- no new way to reach outside `workspace/`), which
  serves the file's raw content as `Content-Type: text/html` --
  switched from an earlier `srcdoc` + JSON-fetch approach whose
  `about:srcdoc` base URL broke relative-asset resolution some Plotly
  exports depend on. **Deliberately still `sandbox="allow-scripts"`
  with NO `allow-same-origin`**: this content is model-written
  (`write_file`/`run_command` output) -- content an adversarial prompt
  injection could influence -- and `allow-same-origin` would grant it
  this app's real origin (ambient-credentialed access to
  `window.parent` and every other `/api/*` endpoint, no CORS
  boundary). The frame keeps its opaque/null origin regardless of
  `srcdoc` vs. a real `src=` navigation; only the base-URL fix, never
  same-origin privilege, was the actual goal of this switch.
  `GET /api/workspace/file` (JSON-wrapped, no navigation) still exists
  unchanged for any other consumer that wants the raw text.
  Switching tabs doesn't tear down the other one -- Activity keeps
  logging live tool calls underneath while Preview is showing. The most
  recently seen path also gets mirrored onto a persistent **View**
  button next to the Activity/Preview tabs themselves
  (`registerReportPath()`, called from every place an inline View
  button is created) -- a fixed shortcut to the last report without
  scrolling back through the transcript to find its own button.
- **Logged through the agent's own `chat_logger.py`** — same JSONL
  format, same `logs/` directory as the CLI agent, including every
  `tool_call`/`tool_result` and `prompt_eval_count`/`eval_count`/
  durations per round (`app/core/approval_bridge.py`'s
  `_EventForwardingLogger` wraps the real `ChatLogger` so every call
  both writes the normal JSONL record AND pushes the matching SSE
  event). One JSONL "session" = one conversation: opens on the first
  message, closes with `session_end` on `POST /reset` or BE shutdown.

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
- **Save only submits fields you actually changed** (`config.html`'s
  `initialValues` diff, client-side) — never every field's current
  displayed value. This matters most for `WORKSPACE_DIR`/
  `MEMORY_FILE`/`LOG_DIR`: with no override, each shows whatever THIS
  OS resolved as its default (e.g. `/mnt/c/...` under WSL, `C:\...` on
  native Windows, for the exact same physical file when the repo is
  shared between the two — `/mnt/c` **is** `C:\` under WSL). Submitting
  every field unconditionally would bake that OS-specific resolved
  value into `agent/.env` as a permanent override the next time ANY
  field was saved, breaking the other OS the next time it read the
  same file even though that field was never touched.
- **"Clear override (auto-resolve per OS)"**, next to "Use default" on
  `WORKSPACE_DIR`/`MEMORY_FILE`/`LOG_DIR` — submits an empty value for
  that field, which `_write_env_file()` treats as "remove this key's
  line entirely" rather than writing `KEY=""`. `KEY=""` would still
  count as "set" to `os.getenv()` (breaking the per-OS auto-resolve
  these three fields depend on when unset), so cleaning up an override
  already baked into `agent/.env` from before the diff-only-Save fix
  above requires actually deleting the line, not blanking it — "Use
  default" alone can't do that, since it bakes in THIS OS's resolved
  value as a new override, still wrong for the other OS.
- **Live, except three settings**: `save_config()` calls
  `config_reload.reload_all()` (agent settings) and
  `get_settings.cache_clear()` (BE settings) right after writing the
  `.env` files, so the change applies to THIS running BE process
  immediately. `BE_HOST`/`BE_PORT`/`BE_CORS_ORIGINS` are the exception
  — bound to the process at startup (socket already listening, CORS
  middleware already installed into the ASGI app), so those three
  still need a real restart no matter what.
- **Why agent settings needed their own reload module**
  (`agent/config_reload.py`): nearly every consumer did
  `from agent_config import X`, copying the *value* into its own
  namespace at import time — reassigning `agent_config.X` later never
  reaches that copy. `reload_all()` reloads `agent_config`/`log_config`
  in place via `importlib.reload()`, then explicitly pushes each
  recomputed value into every already-imported module that copied it
  (`shared`, `shell_tools`, `fs_tools`, `confirm`, `memory`, and this
  BE's own `agent_bridge`/`approval_bridge`/`tool_bridge`/`api/memory`),
  looked up through `sys.modules` — never a fresh import, so it can't
  create circular-import ordering issues. `OllamaAgent.model` is an
  instance attribute set once at construction, not a module-level
  name, so a model change instead drops `agent_bridge`'s cached
  singleton — the next chat request builds a fresh one.
- **The standalone CLI agent is a separate OS process** — this
  reload only reaches modules already imported inside the BE process.
  A `CLI_agent.py` session in progress is unaffected; start a new one
  to pick up a saved change.
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

### Deliberate Unlock Gate (`app/static/config.html`)

To prevent accidental modification of live settings while allowing frictionless
read-only inspection, the config page is locked by default. A random 5-digit
confirmation code is generated on-screen; typing this code unlocks form fields
and the **Save** button.

### Read-Only Memory View (`GET /api/memory`)

The config page also displays a live, read-only **Memory** section at the bottom:
- Fetches from `GET /api/memory`, returning all `entries` in `memory.json` in reverse
  chronological order (newest first).
- Displays entry type badges (`fact`, `summary`), timestamps, associated tags, and text.
- Displays cumulative token counts (`token_usage_total`).
- Fails safely if `memory.json` is missing or corrupt (returning an empty list and 0 tokens
  without raising an error).

See [agent_config.md](agent_config.md) for the full settings reference.

## Running it

Dependencies are managed by [uv](https://docs.astral.sh/uv/) from the
project root's `pyproject.toml`/`uv.lock` — one lockfile for both
`agent/` and `BE/`, no separate `BE/.venv`. From the project root:

```bash
uv sync --group dev
```

Then either:
- `../run_be.sh` (or `run_be.bat` on Windows) from the project root
  (both wrap `uv run uvicorn ...`), or
- `uv run --directory BE uvicorn app.main:app --reload` directly.

Both read `BE_HOST`/`BE_PORT` (default `127.0.0.1:8000`, and
`run_be.sh`/`.bat` auto-increment the port if it's already taken). Copy
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

- No "auto mode" on the chat page (CLI_agent.py's `auto_mode = True`
  plan-once-run-to-the-end path, via `auto_runner.py`) — the chat page
  always runs step mode (confirm before every side effect), same as the
  CLI's default.
- No `save_session_summary()` for chat-page conversations — the CLI
  agent calls this on exit/Ctrl-C to leave a memory.json summary;
  `POST /api/chat/reset`/BE shutdown don't yet.
- No auth on the chat page itself, nor rate limiting.
- No auth.
- No Dockerfile / containerization.
- No CI config for this service specifically.
- No production Nginx hardening (TLS, rate limiting, security headers) —
  `nginx.conf` here is a local-dev reverse-proxy template, not a
  production config.
