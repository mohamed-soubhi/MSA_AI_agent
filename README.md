# MSA_AI_agent — sandboxed AI coding agent

A sandboxed CLI coding agent built on Ollama tool-calling, plus a
FastAPI backend that exposes the same agent over a web chat UI, a
config editor, and a persistent-memory viewer.

**Start here:**

- **[doc/USER_MANUAL.md](doc/USER_MANUAL.md)** — practical guide: how to run the
  agent, the backend, and the config editor.
- **[doc/README.md](doc/README.md)** — documentation index: every module,
  its purpose, and a link to its own doc page.
- **[doc/BE.md](doc/BE.md)** — backend service layout (FastAPI routes, chat
  page, config editor, approval bridge).
- **[code_flow_diagrams/index.html](code_flow_diagrams/index.html)** —
  interactive architecture visualizer: system topology, 9 flow diagrams,
  module call graph, security deep-dive.

## Quick start

Dependencies are managed by [uv](https://docs.astral.sh/uv/) — one
root `pyproject.toml` + `uv.lock`, one isolated `.venv`, works
identically on any machine/OS. See
[doc/USER_MANUAL.md §10](doc/USER_MANUAL.md#10-working-with-uv-dependency-management)
for the full command reference (adding deps, offline, CI, etc.).

```bash
# One-time setup (installs uv itself, then syncs the project's .venv)
curl -LsSf https://astral.sh/uv/install.sh | sh   # Linux/macOS/WSL
uv sync --group dev

# Backend (FastAPI) + web UI — chat, config editor, memory viewer
./run_be.sh          # Linux/WSL
run_be.bat           # Windows
# then open the "Open the UI at" links it prints (Chat / Config)

# CLI agent
./run_cli_agent.sh   # Linux/WSL
run_cli_agent.bat    # Windows
```

## Project layout

```
Project/
├── pyproject.toml       — uv project: one dependency set for agent/ + BE/
├── uv.lock              — pinned, reproducible dependency versions (commit this)
├── agent/               — agent source (CLI_agent.py entry point + tools)
├── BE/                  — FastAPI backend: chat/config/memory APIs + static UI
├── workspace/           — agent's sandbox (BASE_DIR) — all agent file I/O lives here
├── tests/                — pytest suite for agent/
├── doc/                 — full documentation (module docs, user manual, reports)
├── code_flow_diagrams/  — standalone architecture/flow visualizer (open index.html)
├── jsonl-viewer/        — standalone viewer for session log JSONL files
├── markdown-reader/     — standalone Markdown file viewer
├── logs/                — JSONL session logs
├── memory.json          — persistent agent memory (viewable at /config)
├── run_be.sh/.bat        — launch the backend + web UI (via `uv run`)
└── run_cli_agent.sh/.bat — launch the CLI agent (via `uv run`)
```

## Reports

- [doc/test_report.md](doc/test_report.md) — test pass/fail report (446 tests in agent suite, 524 tests across full project, 100% pass rate).
- [doc/code_review_report.md](doc/code_review_report.md) /
  [.html](doc/code_review_report.html) — code review & defect assessment.
