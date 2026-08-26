# assignment2 — sandboxed AI coding agent

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

```bash
# Backend (FastAPI) + web UI — chat, config editor
./run_be.sh          # Linux/WSL
run_be.bat           # Windows
# then open the "Open the UI at" links it prints (Chat / Config)

# CLI agent
python3 agent/CLI_agent.py
run_cli_agent.bat    # Windows
```

## Project layout

```
Project/
├── agent/               — agent source (CLI_agent.py entry point + tools)
├── BE/                  — FastAPI backend: chat/config APIs + static UI
├── workspace/           — agent's sandbox (BASE_DIR) — all agent file I/O lives here
├── tests/                — pytest suite for agent/
├── doc/                 — full documentation (module docs, user manual, reports)
├── code_flow_diagrams/  — standalone architecture/flow visualizer (open index.html)
├── jsonl-viewer/        — standalone viewer for session log JSONL files
├── markdown-reader/     — standalone Markdown file viewer
├── logs/                — JSONL session logs
├── memory.json          — persistent agent memory
├── run_be.sh/.bat        — launch the backend + web UI
└── run_cli_agent.bat     — launch the CLI agent (Windows)
```

## Reports

- [doc/test_report.md](doc/test_report.md) — test pass/fail report (413 tests, 100% pass rate).
- [doc/code_review_report.md](doc/code_review_report.md) /
  [.html](doc/code_review_report.html) — code review & defect assessment.
