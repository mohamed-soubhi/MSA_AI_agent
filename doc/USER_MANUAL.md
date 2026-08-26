# User Manual

Practical, task-oriented guide to running and using this project.
For implementation detail on any specific module, see its own doc file
(linked from [README.md](README.md)'s module table) — this manual
covers *how to use the thing*, not how it's built.

## 1. What this project is

A sandboxed CLI coding agent (`agent/CLI_agent.py`) built on Ollama
tool-calling: it can list/read/write files, run terminal commands, and
ask you clarifying questions — all confined to a dedicated `workspace/`
folder it can never escape. A FastAPI backend (`BE/`) is scaffolded
alongside it (currently just a health check + a config editor; the
chat API itself isn't wired up yet).

## 2. First-time setup

This project is packaged as one [uv](https://docs.astral.sh/uv/)
project, rooted at `pyproject.toml` + `uv.lock` — one lockfile for both
the agent and the backend, isolated in its own `.venv` that never
touches your system Python. Install uv once, then everything else is
`uv run`:

```bash
# 1. Install uv itself (one-time, machine-wide — not project-specific)
curl -LsSf https://astral.sh/uv/install.sh | sh   # Linux/macOS/WSL
# Windows (PowerShell): irm https://astral.sh/uv/install.ps1 | iex

# 2. From the project root: create .venv and install everything
#    (agent + BE dependencies, from the one root pyproject.toml)
uv sync --group dev
```

That's it — no `pip install`, no manually activating a venv.
`run_be.sh`/`.bat` and `run_cli_agent.sh`/`.bat` all invoke `uv run`
internally, which resolves `.venv` automatically (creating it on first
use if `uv sync` wasn't run explicitly). See
[§10 "Working with uv"](#10-working-with-uv-dependency-management)
below for adding dependencies, offline use, CI, and other cases.

You also need [Ollama](https://ollama.com) installed and running
locally, with a model pulled that matches `WORKSHOP_MODEL` (default
`glm-5.2:cloud` — a cloud model, needs internet; swap to a local model
via the config editor or `agent/.env` if you'd rather run offline).

## 3. Running the agent

```bash
uv run agent/CLI_agent.py
```

Or run `./run_cli_agent.sh` (Linux/WSL) / double-click `run_cli_agent.bat`
(Windows) at the project root — both `cd` to the right place and run
through `uv run`, so they work from anywhere without you activating
anything first.

You'll see a startup banner (sandbox path, mode, tokens used so far),
then a `You >` prompt. Type a request; the agent will list/read/write
files inside `workspace/`, run terminal commands, and ask before any
side-effecting action (unless you're in auto mode). Type `exit`,
`quit`, or `q` to end the session.

**Where things go**: everything the agent builds lands in `workspace/`
— nothing else on disk is reachable by its tools, including its own
source code in `agent/`. See [README.md](README.md#project-layout) for
the full "why" behind this split.

### Step mode vs. auto mode

- **Step mode** (the default): the agent asks `y/n` before every
  file write, directory creation, or terminal command.
- **Auto mode**: set `auto_mode = True` at the top of
  `agent/CLI_agent.py`. The agent writes a full plan
  (`workspace/plan.md`), you approve it **once**, and it runs to
  completion — except a few things that *always* still interrupt
  regardless of the plan: paths outside the sandbox, destructive shell
  patterns (`rm`, `sudo`, `curl`, ...), compound/chained shell commands,
  and a hard cap of 30 tool calls. See [auto_runner.md](auto_runner.md).

### Memory across sessions

The agent remembers things across restarts, stored in `memory.json` at
the project root (not inside `workspace/` — the agent can't read or
edit its own memory through its own sandboxed tools):
- Facts it decides are worth keeping (`remember_fact`), and a short
  auto-generated summary of each session.
- Cumulative token usage — printed at both startup ("tokens used
  all-time") and shutdown ("tokens used this session").

See [memory.md](memory.md).

## 4. Running the backend (BE)

```bash
./run_be.sh          # or run_be.bat on Windows
```

Starts Uvicorn on `http://localhost:8000` (override with `BE_HOST`/
`BE_PORT` env vars or the config editor). Three things exist today:

- `GET /health` — liveness check.
- `GET /chat` — a plain conversational chat page (below).
- `GET /config` — the interactive config editor (below).

Optionally, put Nginx in front of it as a reverse proxy:
`nginx -c $(pwd)/BE/nginx/nginx.conf` (requires Uvicorn already
running). See [BE.md](BE.md).

## 5. Chatting with the model

Open **`http://localhost:8000/chat`**. Type a message, hit Enter (or
click Send) — the reply streams in token-by-token. Uses whatever model
`WORKSHOP_MODEL` is currently set to (config editor, "Chat / Ollama"
section).

**No file/shell tools here** — this is plain conversation with the
model, not the full agent loop. The CLI (`python3 agent/CLI_agent.py`)
is still where tool-calling (reading/writing files, running commands)
happens; the chat page doesn't have that wired in yet.

The right-hand panel is a placeholder for now — reserved for content
tied to the conversation, not built yet. **New chat** clears history;
history otherwise survives a page refresh (held in the BE process's
memory) but resets if the BE service restarts.

## 6. Editing configuration (the config editor)

With the BE service running, open **`http://localhost:8000/config`**
in a browser (or `http://localhost/config` if you're going through
Nginx).

You'll see every setting across the whole project — chat/Ollama
timeouts, the tool loop, filesystem/sandbox limits, shell allow/block
lists, the confirmation gate, memory, the full system prompt, logging,
and the BE server itself — grouped into sections, pre-filled with
whatever's currently in effect. Each field also shows a **recommended
default** underneath, with a one-click "Use default" button.

- **Deliberate Unlock Gate**: Editing is locked by default to prevent
  stray clicks. A random 5-digit verification code appears in the top
  banner; typing the code enables editing and activates the **Save** button.
- **Read-Only Memory Inspector**: Below the config form, a live **Memory**
  section displays existing entries in `memory.json` (facts and session summaries)
  and cumulative all-time token usage.

Next to the Model field, a **"Load models"** button queries your local
Ollama installation and lists every model it knows about — split into
**Local** (already pulled, with real specs: size, parameter count,
quantization) and **Cloud** (resolved via ollama.com). Click one to
fill the field. Edit what you want, click **Save**.

**Important**: saving does **not** apply changes to an already-running
agent or BE process. Both only read their settings once, at startup.
After saving:
1. Stop the agent (if running) and restart it (`python3
   agent/CLI_agent.py` again) — it'll pick up everything you changed.
2. If you changed a `BE_*` setting, restart the BE service too.

Under the hood, this writes to two files — `agent/.env` for agent
settings, `BE/.env` for BE settings — using the exact same env-var
names documented in [agent_config.md](agent_config.md) and
[BE.md](BE.md). You can also hand-edit either file directly (copy
`agent/.env.example` / `BE/.env.example` as a starting point) if you'd
rather skip the UI.

## 7. Running the tests

```bash
uv run --group dev pytest tests/ -v                    # agent test suite
uv run --group dev --directory BE pytest tests/ -v      # BE test suite
```

`--directory BE` runs pytest with `BE/` as its working directory
(so it picks up `BE/pytest.ini`) while still using the one root
`.venv` — no separate BE virtualenv needed. See
[README.md](README.md#running-the-tests) for coverage/report-
generation commands.

## 8. Common tasks

| I want to... | Do this |
|---|---|
| Use a different Ollama model | Config editor → "Chat / Ollama" → Model, or set `WORKSHOP_MODEL` in `agent/.env` |
| Let the agent run more commands without asking | Add programs to `SHELL_ALLOWED` (config editor → "Shell tools") |
| Change what the agent's persona/rules are | Config editor → "System prompt" (full textarea) |
| Turn off memory entirely | Config editor → "Memory" → Memory enabled = off |
| Make the agent less chatty in logs | Config editor → "Logging" → Echo to terminal = off |
| Recover from a stuck/looping agent | It self-detects (`MAX_REPEAT_CALLS`, cycle detection) and stops on its own — see [shared.md](shared.md) |
| See what happened in a past session | `logs/*.jsonl` (one file per session by default) — see [chat_logger.md](chat_logger.md) |

## 10. Working with uv (dependency management)

Everything below runs from the project root, where `pyproject.toml` +
`uv.lock` live. `uv.lock` is committed — it pins every dependency
(direct and transitive) to an exact version, so `uv sync` reproduces
the *identical* environment on any machine, any OS, isolated from
whatever else is installed system-wide.

| Case | Command |
|---|---|
| Fresh clone, first run | `uv sync --group dev` |
| Run the agent | `uv run agent/CLI_agent.py` (or `./run_cli_agent.sh` / `run_cli_agent.bat`) |
| Run the backend | `./run_be.sh` / `run_be.bat` (wraps `uv run uvicorn ...` internally) |
| Run any one-off script/command in the project's env | `uv run <command>`, e.g. `uv run python -c "import fastapi"` |
| Run tests | `uv run --group dev pytest tests/ -v` (add `--directory BE` for the BE suite) |
| Add a new dependency | `uv add <package>` — updates `pyproject.toml` + `uv.lock` together |
| Add a dev-only dependency (tests, linters) | `uv add --group dev <package>` |
| Remove a dependency | `uv remove <package>` |
| Someone else changed `pyproject.toml`/`uv.lock` | `uv sync --group dev` — brings your `.venv` back in line |
| Regenerate the lockfile after manual `pyproject.toml` edits | `uv lock` |
| Check the lockfile isn't stale (CI-style check) | `uv lock --check` |
| Pin/verify the Python version | `requires-python = ">=3.12"` in `pyproject.toml`; uv downloads a matching interpreter itself if none is found (no separate `pyenv` needed) |
| Nuke and rebuild the environment from scratch | `rm -rf .venv && uv sync --group dev` |
| Offline, `uv.lock` already committed | Works as long as uv's package cache (`~/.cache/uv`) already has everything — `uv sync --offline` |
| CI pipeline | `uv sync --group dev --frozen` — fails instead of silently updating the lockfile if `pyproject.toml` and `uv.lock` disagree |

`.venv/` and `.port-locks/` are both git-ignored — they're
machine-local, reproducible, and safe to delete any time. `uv.lock` is
the only thing that needs to be committed for reproducibility.

## 11. Troubleshooting

- **"Blocked: 'X' is not in the allowlist"** — the agent tried to run a
  program not in `SHELL_ALLOWED`. Add it via the config editor if it's
  actually safe to allow, or just answer the confirm prompt as usual
  if it's a one-off.
- **Agent seems to hang after a confirm prompt** — check
  `TOOL_TIMEOUT_SECONDS` (default 30s) vs `CONFIRM_TIMEOUT_SECONDS`
  (default 120s); a slow answer to a confirm prompt can get the whole
  tool call abandoned before you finish typing. Both are editable in
  the config editor.
- **Config editor shows old values after saving** — that's expected;
  it shows what's *currently loaded in the running process*, not the
  file. Restart the relevant service and reload the page.
- **`uv run` seems to reinstall/re-resolve every time** — that's uv
  checking `pyproject.toml`/`uv.lock` are still in sync before running;
  it's fast (milliseconds) once `.venv` exists and nothing changed. If
  it's actually slow, check `uv.lock` isn't being regenerated on every
  call (`uv lock --check` should report clean).
- **`MEMORY_FILE`/other path settings look wrong after switching
  between Windows and WSL** — `agent/.env` and `BE/.env` store
  *absolute* paths (by design, see [agent_config.md](agent_config.md)).
  A path written while running under Windows (`C:\...`) won't resolve
  under WSL/Linux and vice versa. Fix by clearing the field in the
  config editor (falls back to the built-in default, which resolves
  relative to the project root on whichever OS is currently running)
  or hand-editing the `.env` file for the OS you're on.
