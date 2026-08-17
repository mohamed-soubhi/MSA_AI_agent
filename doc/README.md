# assignment2 — documentation index

A sandboxed agent built on Ollama tool-calling. `09_full_agent.py` is
the single entry point — it merges what used to be two separate agents
(filesystem-only, and a "vibe-coding" write+run agent) into one that
can list/read/write/create files, run terminal commands, and ask the
human for clarification. It also supports **auto mode**: approve one
generated plan up front instead of confirming every step, with a few
things (paths outside the sandbox, destructive shell patterns, a
tool-call cap) that still always interrupt regardless of the plan.
Everything stays inside `BASE_DIR` (the working directory the process
was started from), and every session is logged to JSONL.

## Modules

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
| `09_full_agent.py` | The CLI entry point: files + terminal + human-in-the-loop + auto/step mode, all in one agent | [09_full_agent.md](09_full_agent.md) |

> `07_filesystem_tools.py` and `08_terminal_tools.py` (and their docs)
> have been retired — `09_full_agent.py` merges both into one agent
> that reuses their exact same tool implementations.

## Architecture (call graph)

```
09_full_agent.py (main)
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

## Running the tests

```bash
cd assignment2
python3 -m pytest tests/ -v
python3 -m pytest tests/ --cov=. --cov-report=term-missing   # with coverage
```

No live Ollama server or terminal tty is required — all network calls
and `input()`/`confirm()` prompts are mocked in the test suite.

## Test IDs

Every test carries a `@pytest.mark.tid("PREFIX-NNN")` marker, sequential
per file (e.g. `FSTOOLS-014`, `CONFIRM-007`), registered in `pytest.ini`.
Prefixes: `CONFIRM`, `FSTOOLS`, `LOGCFG`, `CHATLOG`, `SHARED`, `HUMAN`,
`SHELL`, `FULLAGENT`, `AUTORUN`, `AGENTCFG`, `MEMORY`. Filter by id or module the
normal pytest way:

```bash
python3 -m pytest tests/ -m "tid" -k "FSTOOLS-014"
python3 -m pytest tests/test_fs_tools.py -v
```

## Report generator & Audit Reports

```bash
python3 tests/generate_report.py
```

- **Test Pass/Fail Report**: [`test_report.md`](test_report.md) — 392 tests, 100% pass rate.
- **Code Review & Defect Assessment Report (HTML)**: [`code_review_report.html`](code_review_report.html) — interactive audit dashboard.
- **Code Review & Defect Assessment Report (Markdown)**: [`code_review_report.md`](code_review_report.md) — comprehensive static analysis and defect assessment.

