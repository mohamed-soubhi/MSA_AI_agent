# memory.py

Persistent, JSON-backed memory: what the agent learns survives past one
session. Two different write paths feed the same file, and one read
path serves both:

- `remember_fact(text, tags=None)` — **model-invoked tool**, same
  pattern as `human_tools.py`. The model decides something is worth
  keeping (a user preference, a decision made, a fact about the
  project) and calls this to save it.
- `recall_memory(query="", tags=None)` — **model-invoked tool**. The
  model calls this to search past facts/summaries, e.g. at the start of
  a task or whenever something from an earlier session could help.
- `save_session_summary(agent, messages)` — **host-invoked only**, from
  `CLI_agent.py`, right before a session ends. Not offered to the
  model as a tool: a mid-conversation call would summarize an
  unfinished conversation. Runs one extra `agent.chat()` call with
  `tools=None` so the summarizer itself can't call `write_file` /
  `run_command`, then saves the result as a `"summary"` entry.
- `load_token_usage()` / `save_token_usage(session_tokens)` —
  **host-invoked only**, also from `CLI_agent.py`. Track a running
  cumulative token count (`OllamaAgent.total_tokens` — prompt +
  completion tokens, summed across every `chat()` call made through one
  agent instance) across every session ever run. `load_token_usage()`
  is printed once at startup ("tokens used all-time so far");
  `save_token_usage()` adds the session's count to the saved total and
  is called once, in a `finally` block, on **every** exit path —
  including a crash, since unlike `save_session_summary` it makes no
  model call and so carries no extra-failure risk.

## Storage

One JSON file, `MEMORY_FILE` in `agent_config.py` (default
`<project_root>/memory.json` — fixed, not relative to the working
directory, same convention as `LOG_DIR` in `log_config.py`).
Deliberately fixed OUTSIDE `WORKSPACE_DIR` (the agent's sandbox — see
[fs_tools.md](fs_tools.md)), so the agent can never read or overwrite
its own persistent memory through its own sandboxed `write_file`/
`read_file` tools. Format:

```json
{
  "entries": [
    {
      "id": "a1b2c3d4",
      "type": "fact",
      "text": "User prefers pytest over unittest for this project.",
      "tags": ["preferences", "testing"],
      "timestamp": "2026-08-17T10:30:00"
    },
    {
      "id": "e5f6a7b8",
      "type": "summary",
      "text": "Built a todo app; user asked for dark mode by default.",
      "tags": [],
      "timestamp": "2026-08-17T11:05:00"
    }
  ],
  "token_usage_total": 48213
}
```

`type` is either `"fact"` (from `remember_fact`) or `"summary"` (from
`save_session_summary`) — `recall_memory` returns both, since a past
summary is often exactly what answers "what did we do last time?".
`token_usage_total` is a sibling top-level integer, not an entry —
`_load()`/`_save()` (entries-only) and `load_token_usage()`/
`save_token_usage()` (the integer) share the file through
`_load_data()`/`_save_data()` (full JSON object), so writing one never
clobbers the other regardless of write order.

Memory is **deliberately not** routed through `fs_tools.resolve_path()`
/ `BASE_DIR`: it persists across different sandboxes on purpose, so the
agent can remember things about the user across different working
directories, not just within one sandboxed project.

## Config (`agent_config.py`)

| Setting | Default | Purpose |
|---|---|---|
| `MEMORY_ENABLED` | `True` | Master switch — `False` makes both tools no-ops and `save_session_summary` skip entirely, with zero file I/O. |
| `MEMORY_FILE` | `PROJECT_ROOT / "memory.json"` | Fixed path to the JSON file — not relative to the working directory, and outside `WORKSPACE_DIR`. |
| `MEMORY_MAX_ENTRIES` | `500` | Oldest entries are dropped once the file exceeds this many. |
| `MEMORY_MAX_TEXT_CHARS` | `1000` | Per-entry text is truncated to this length before saving. |
| `MEMORY_MAX_RECALL_RESULTS` | `10` | `recall_memory()` returns at most this many matches (most recent first). |

All five follow the project-wide pattern: plain module constant,
overridable by an environment variable of the same name.

## Retrieval

`recall_memory` is a plain, case-insensitive **substring match** on
`text`, with an optional tag filter (`tags=[...]` matches an entry if
it has **any** of the given tags). No embeddings, no vector search —
this is intentionally the simplest thing that works at the scale one
person's agent memory reaches; a query and a tag filter combine with
AND (both must match if both are given).

## Failure handling

Every disk operation (`_load`, `_save`) degrades to a logged warning
instead of raising — a missing/corrupt `memory.json` is treated as "no
memories yet" on read, and a full disk or permissions error on write is
swallowed the same way `chat_logger.py` swallows logging failures.
`save_session_summary`'s `agent.chat()` call is wrapped the same way:
losing a summary must never crash the shutdown path in
`CLI_agent.py`.

## Wiring into `CLI_agent.py`

- `remember_fact` and `recall_memory` are added to the same `tools` /
  `tool_map` lists as every other tool (nine total now).
- `save_session_summary(agent, messages)` is called at the `"exit"` /
  `"quit"` / `"q"` path and the `KeyboardInterrupt` path, right before
  `chat_logger.session_end(...)`. It is **not** called on the crash
  path (`session_end(reason="crashed")`) — deliberately, so a second
  failure (another `agent.chat()` call) can't happen while already
  unwinding from the first one.
- In **auto mode**, `messages` (the list passed to `save_session_summary`)
  is the step-mode message list only — `run_with_auto_mode()` manages
  its own separate message list for the plan + execution turns (see
  [auto_runner.md](auto_runner.md)), so a session spent entirely in
  auto mode won't produce a summary from this call site. This is a
  known, accepted gap rather than something `save_session_summary`
  itself needs to handle.

## Test coverage (`tests/test_memory.py`)

43 tests (`MEMORY-001` .. `MEMORY-043`), covering:
- `remember_fact`: writes, appends (not overwrites), tag
  normalization, text truncation, entry-count trimming, empty/whitespace
  input rejected, disabled-memory no-op.
- `recall_memory`: empty-store message, substring match (case
  insensitive), tag filter (any-of), query+tag AND combination, no-match
  message, result cap, disabled-memory message, corrupt-file
  resilience, corrupt-file backup preservation.
- Atomic writes: `_save()` goes through `os.replace()` (not a direct
  write), no leftover `.tmp*` file after a save, valid JSON after
  repeated saves.
- `save_session_summary`: writes a `"summary"` entry, skips under-two-turn
  conversations, offers no tools to the summarizer call, swallows a
  `chat()` failure without raising, skips on empty model output,
  disabled-memory no-op, windows to `MEMORY_SUMMARY_MAX_MESSAGES` on a
  long conversation, sends a short conversation in full.
- `load_token_usage`/`save_token_usage`: zero when never saved, save
  returns and persists the new total, second save adds to the running
  total (not overwrites), zero/negative `session_tokens` is a no-op,
  disabled-memory no-op on both load and save, coexists with `entries`
  writes without clobbering either, corrupt file treated as zero.

`tests/test_CLI_agent_main.py` additionally covers the wiring: both
memory tools present in `tool_map` (`FULLAGENT-007`/`008`, now nine
tools), `save_session_summary` called on the exit and `KeyboardInterrupt`
paths but **not** the crash path (`FULLAGENT-012`–`014`), and
`load_token_usage`/`save_token_usage` — startup print, session total
passed to `save_token_usage`, called on **all three** exit paths
including the crash path, and a non-int `total_tokens` (e.g. an
unconfigured test double) coerced to `0` rather than crashing
(`FULLAGENT-015`–`020`).

## Architectural & Persistence Notes

Findings from the [Code Review & Defect Assessment Report](code_review_report.md) touching this module — both now fixed (see that report's Remediation Status table for the full list):

1. **Non-Atomic File Persistence (ROB-02) — fixed**:
   `_save()` now writes to a temp file (`memory.json.tmp<pid>`) and atomically swaps it into place with `os.replace()`, so an interrupted write can never leave `memory.json` half-written. A corrupt file found on load is preserved as `memory.json.corrupt.bak` before `_load()` falls back to an empty list, so nothing is silently lost.
2. **Multi-Turn Context Sizing (ROB-04) — fixed (summarizer only)**:
   `save_session_summary` now sends only the last `MEMORY_SUMMARY_MAX_MESSAGES` (default 40, see `agent_config.py`) messages to `agent.chat()`, not the full session history. The live `messages` list `run_agent()` itself uses was deliberately left unbounded — trimming it would cost the model visibility into earlier turns it may still need mid-conversation.

