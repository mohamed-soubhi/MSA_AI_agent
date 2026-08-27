# MSA_AI_agent — documentation index

**New here? Start with the [User Manual](USER_MANUAL.md)** — practical,
task-oriented instructions for running the agent, the backend, and the
config editor. This file is the module-by-module reference index.

A sandboxed agent built on Ollama tool-calling. `CLI_agent.py` is
the single entry point — it merges what used to be two separate agents
(filesystem-only, and a "vibe-coding" write+run agent) into one that
can list/read/write/create files, run terminal commands, and ask the
human for clarification. It also supports **auto mode**: approve one
generated plan up front instead of confirming every step, with a few
things (paths outside the sandbox, destructive shell patterns, a
tool-call cap) that still always interrupt regardless of the plan.
Everything stays inside `BASE_DIR` (a fixed `workspace/` folder at the
project root — **not** the working directory the process was started
from, see "Project layout" below), and every session is logged to
JSONL.

## Project layout

```
Project/
├── agent/          — all agent source code (this file's "Modules" table)
├── workspace/       — the agent's sandbox; BASE_DIR. Everything it
│                      builds/reads/writes lives here, and ONLY here.
├── BE/             — backend service: FastAPI + Uvicorn + Nginx (see BE.md)
├── tests/          — pytest suite (imports agent/ via conftest.py)
├── doc/            — this documentation
├── logs/           — JSONL session logs (fixed at project root)
└── memory.json     — persistent agent memory (fixed at project root)
```

## Backend service (`BE/`)

A FastAPI + Uvicorn + Nginx scaffold — currently just a `/health`
endpoint proving the stack runs end to end, no agent wiring yet. Run it
with `run_be.sh` / `run_be.bat` at the project root. See
[BE.md](BE.md) for the full layout, config, and how to run it.

**Sandbox-escape fix**: `agent/` and `workspace/` used to be the same
directory (the project root) — the agent's own source code sat right
next to whatever it was sandboxed to work on, and its sandbox root
(`BASE_DIR = Path.cwd().resolve()`) was wherever the process happened
to be launched from, which was normally that same root. That meant the
agent's own filesystem tools could read and overwrite its own source
files. Moving the source into `agent/` and fixing `BASE_DIR` to a
dedicated `workspace/` folder (resolved from `agent_config.py`'s own
file location, not the process cwd) closes that gap structurally —
there's no path the model can construct that reaches back into `agent/`.
See [fs_tools.md](fs_tools.md#sandbox-escape-fix-agent-could-readedit-its-own-source)
for the full writeup. `logs/` and `memory.json` are likewise fixed at
the project root now (not cwd-relative) and sit **outside**
`workspace/`, so the agent can't read or edit its own operational data
through its own sandboxed tools either.

## Modules

All files below live in `agent/` (e.g. `agent/agent_config.py`).

| File | Purpose | Docs |
|---|---|---|
| `agent_config.py` | Central, env-var-overridable settings for every module below (chat, tool loop, filesystem, shell, confirm, auto mode) | [agent_config.md](agent_config.md) |
| `shared.py` | `OllamaAgent` (hardened chat wrapper) + `run_agent()` (the ReAct tool-calling loop, with an optional `max_tool_calls` cap) | [shared.md](shared.md) |
| `fs_tools.py` | Sandboxed filesystem tools: `list_directory`, `read_file`, `write_file`, `create_directory` | [fs_tools.md](fs_tools.md) |
| `shell_tools.py` | Sandboxed shell execution: `run_command`, gated by allowlist + blocklist(→force-ask) + `confirm()` + timeout | [shell_tools.md](shell_tools.md) |
| `confirm.py` | Fail-closed human-in-the-loop confirmation gate; also the one place auto/step mode is decided | [confirm.md](confirm.md) |
| `agent_mode.py` | The single `AUTO_MODE` toggle `confirm()` reads | [agent_mode.md](agent_mode.md) |
| `auto_runner.py` | Auto-mode orchestration: generate a plan, approve once, run to completion | [auto_runner.md](auto_runner.md) |
| `human_tools.py` | Conversational human-in-the-loop tools: `ask_human`, `ask_human_choice`, `approve_action` (model-optional, not a security boundary) | [human_tools.md](human_tools.md) |
| `memory.py` | Persistent JSON memory across sessions: `remember_fact`/`recall_memory` (model tools) + `save_session_summary`/`load_token_usage`/`save_token_usage` (host-called at session start/end) | [memory.md](memory.md) |
| `chat_logger.py` | Structured JSONL session logging (`ChatLogger`, `NullChatLogger`, `get_logger`) | [chat_logger.md](chat_logger.md) |
| `log_config.py` | Env-var-overridable logging configuration | [log_config.md](log_config.md) |
| `config_reload.py` | Hot-reloads configuration into all loaded modules on Save without restarting | [config_reload.md](config_reload.md) |
| `CLI_agent.py` | The CLI entry point: files + terminal + human-in-the-loop + auto/step mode, all in one agent | [CLI_agent.md](CLI_agent.md) |

> `07_filesystem_tools.py` and `08_terminal_tools.py` (and their docs)
> have been retired — `CLI_agent.py` merges both into one agent
> that reuses their exact same tool implementations.

## Architecture (call graph)

```
CLI_agent.py (main)
 ├── shared.OllamaAgent           — talks to Ollama
 ├── auto_mode == False:
 │     shared.run_agent()         — the tool-calling loop (step mode)
 │       ├── fs_tools.{list_directory, read_file, write_file, create_directory}
 │       │     ├── fs_tools.resolve_path()  — sandbox enforcement (single choke point)
 │       │     └── confirm.confirm()        — human approval gate (write/create only)
 │       ├── shell_tools.run_command
 │       │     ├── allowlist (layer 1)
 │       │     ├── blocklist (layer 2) → confirm.confirm(force_ask=True)
 │       │     ├── confirm.confirm() (layer 3)
 │       │     └── subprocess timeout (layer 4)
 │       ├── human_tools.{ask_human, ask_human_choice}
 │       │     — conversational, model-optional; NOT a security boundary
 │       └── memory.{remember_fact, recall_memory}
 │             — persistent JSON memory (memory.json), model-invoked
 ├── auto_mode == True:
 │     auto_runner.run_with_auto_mode()   — plan once, approve once, run to the end
 │       ├── writes plan.md, asks ONE confirm(force_ask=True)
 │       ├── sets agent_mode.AUTO_MODE = True for the run, resets in finally
 │       └── shared.run_agent(..., max_tool_calls=30)
 │             — same tool tree as step mode; confirm() auto-approves
 │               everywhere EXCEPT force_ask=True call sites above
 ├── memory.save_session_summary()  — called on exit/KeyboardInterrupt paths
 │       only (not on crash); one extra agent.chat() call, tools=None,
 │       condenses the session into a "summary" entry in memory.json
 ├── memory.load_token_usage()      — printed once at startup (all-time total)
 ├── memory.save_token_usage()      — called in a `finally` block on EVERY
 │       exit path, including crash (no model call, no extra-failure risk);
 │       adds agent.total_tokens to the running total in memory.json
 └── chat_logger.get_logger()     — JSONL audit log for the whole session
       └── log_config              — settings (env-var overridable)

fs_tools.resolve_path() and shell_tools.run_command() route through the
SAME BASE_DIR and the SAME confirm() gate — one sandbox, one approval
experience, shared by every tool in the project, in BOTH modes.
```

## Running the agent

```bash
python3 agent/CLI_agent.py
```

Run from the project root, or from anywhere — `agent_config.WORKSPACE_DIR`
no longer depends on the process's working directory (see "Project
layout" above), so launch location doesn't affect where the sandbox is.

## Running the tests

```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/ --cov=agent --cov-report=term-missing   # with coverage
```

Run from the project root. `tests/conftest.py` adds `agent/` to
`sys.path`, so `import fs_tools`, `import shared`, etc. resolve
normally inside every test file without needing `agent.` as a package
prefix.

No live Ollama server or terminal tty is required — all network calls
and `input()`/`confirm()` prompts are mocked in the test suite.

## Test IDs

Every test carries a `@pytest.mark.tid("PREFIX-NNN")` marker, sequential
per file (e.g. `FSTOOLS-014`, `CONFIRM-007`, `CFGRELOAD-001`), registered in `pytest.ini`.
Prefixes: `CONFIRM`, `FSTOOLS`, `LOGCFG`, `CHATLOG`, `SHARED`, `HUMAN`,
`SHELL`, `FULLAGENT`, `AUTORUN`, `AGENTCFG`, `MEMORY`, `CFGRELOAD`. Filter by id or module the
normal pytest way:

```bash
python3 -m pytest tests/ -m "tid" -k "FSTOOLS-014"
python3 -m pytest tests/test_fs_tools.py -v
```

## Report generator & Audit Reports

```bash
python3 tests/generate_report.py
```

- **Test Pass/Fail Report**: [`test_report.md`](test_report.md) — 435 tests, 100% pass rate (500 tests across full suite).
- **Code Review & Defect Assessment Report (HTML)**: [`code_review_report.html`](code_review_report.html) — interactive audit dashboard.
- **Code Review & Defect Assessment Report (Markdown)**: [`code_review_report.md`](code_review_report.md) — comprehensive static analysis and defect assessment.


