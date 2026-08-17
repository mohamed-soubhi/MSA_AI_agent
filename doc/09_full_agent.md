# 09_full_agent.py

The single CLI entry point: reads/writes/lists/creates files, runs
terminal commands, and can ask the human for clarification — all inside
one sandbox, one `confirm()` gate, and one JSONL log.

This **merges** the two earlier, now-removed entry points
(`07_filesystem_tools.py` and `08_terminal_tools.py`) into one agent.
Nothing is reimplemented twice: `write_file`, `run_command`,
`ask_human`, `ask_human_choice`, `remember_fact`, and `recall_memory`
are each imported from their one real implementation (`fs_tools.py`,
`shell_tools.py`, `human_tools.py`, `memory.py`) — this file only wires
them together and owns the conversation loop. See [memory.md](memory.md)
for what `remember_fact`/`recall_memory`/`save_session_summary` do.

Like its predecessors, the filename starts with a digit and must be
loaded via `importlib.util` rather than a normal `import`.

## `auto_mode: bool` (module-level, default `False`)

Controls which of two run paths `main()` takes each turn:

- `False` (**step mode**): asks before every tool call, as always.
- `True` (**auto mode**): writes `plan.md`, prints the plan in full,
  asks **one** question, then runs to the end — still stopping for
  anything outside the sandbox or a destructive shell command (see
  [auto_runner.md](auto_runner.md), [shell_tools.md](shell_tools.md)).

This is a plain local variable in `09_full_agent.py`, **distinct from**
`agent_mode.AUTO_MODE` (lowercase vs. uppercase, different module) —
`auto_mode` here only decides which function `main()` calls each turn;
`agent_mode.AUTO_MODE` is the flag `confirm()` actually reads, and is
flipped on/off by `auto_runner.run_with_auto_mode()` for the duration
of one plan's execution. The startup banner prints the current mode via
`f"Mode: {'auto (plan once, run to the end)' if auto_mode else 'step (asks before every tool call)'}"`.

## `SYSTEM_PROMPT`

**Lives in `agent_config.py` now**, not here — imported as
`from agent_config import SYSTEM_PROMPT`. See
[agent_config.md](agent_config.md#system-prompt-09_full_agentpy) for
the full text and its `SYSTEM_PROMPT` env-var override.

Prompt-level guidance — **quality, not safety** (a pattern the model is
asked to follow, not a guarantee). The sandbox/allowlist/blocklist/
confirm/timeout layers in `fs_tools.py` and `shell_tools.py` are what
actually *guarantee* the boundary; this prompt just asks the model to
behave well within it.

The non-interactive rule matters most in practice: an interactive
command (`npm create`, a pip confirmation prompt) doesn't error here —
it just hangs until `shell_tools.TIMEOUT_SECONDS` kills it. Suggesting
`--yes`/`--force` flags is only safe *because* the human still approves
every command's exact text before it runs. The prompt also tells the
model to prefer `ask_human`/`ask_human_choice` over guessing when a
request is ambiguous, and to use `recall_memory`/`remember_fact` for
cross-session context.

Seeded as the first message in `messages` on every run.

## `_report_token_usage(agent) -> None`

Saves this session's token usage and prints both numbers. Called
**exactly once**, from a `finally` block wrapped around the whole
session in `main()`, so it always runs regardless of how the session
ends — normal exit, `KeyboardInterrupt`, or an unhandled crash.

Unlike `save_session_summary` (which makes an extra `agent.chat()` call
and is deliberately skipped on the crash path — see
[memory.md](memory.md#wiring-into-09_full_agentpy)), this makes **no**
model call: it just reads `agent.total_tokens` and calls
`memory.save_token_usage()`, so there's no extra-failure risk to avoid
by skipping it anywhere.

`agent.total_tokens` is coerced to a plain `int` defensively
(`session_tokens = agent.total_tokens if isinstance(agent.total_tokens,
int) else 0`) — a test double without that attribute set, or a
non-numeric value, degrades to `0` rather than crashing the shutdown
path over a display feature.

## `main() -> None`

1. Creates an `OllamaAgent()` and offers **nine** tools: `list_directory`,
   `read_file`, `write_file`, `create_directory` (from `fs_tools.py`),
   `run_command` (from `shell_tools.py`), `ask_human`, `ask_human_choice`
   (from `human_tools.py`), `remember_fact`, `recall_memory` (from
   `memory.py`).
2. Opens one JSONL session log via `get_logger("full_agent", agent.model)`.
3. Prints the startup banner, including
   `f"Tokens used all-time so far (loaded from memory): {load_token_usage()}"`
   — the running total saved by every previous session (see
   [memory.md](memory.md)).
4. `messages` starts pre-seeded with `SYSTEM_PROMPT`, which now also
   tells the model to consider `recall_memory` at the start of a task
   and to call `remember_fact` for durable, cross-session facts.
5. Loops reading `input("\nYou > ")`:
   - `"exit"` / `"quit"` / `"q"` (case-insensitive) → calls
     `save_session_summary(agent, messages)`, then logs
     `session_end(reason="user_exit")` and breaks.
   - Otherwise, logs the user message, then branches on `auto_mode`:
     - **`True`**: calls `run_with_auto_mode(agent, user_input, tools,
       tool_map, chat_logger=chat_logger)`. Note `messages` is **not**
       extended here — `run_with_auto_mode()` manages its own message
       list for the plan + execution turns (see
       [auto_runner.md](auto_runner.md)).
     - **`False`**: appends the user message to `messages` and calls
       `run_agent(agent, messages, tools, tool_map, chat_logger=chat_logger)`,
       same as before.
   - Either way, prints the returned answer.
6. `KeyboardInterrupt` → prints `"\nInterrupted."`, calls
   `save_session_summary(agent, messages)`, logs
   `session_end(reason="keyboard_interrupt")`, returns normally.
7. Any other `Exception` → logs `error("main_loop_crashed",
   detail=str(exc))`, then `session_end(reason="crashed")`, then
   **re-raises**. `save_session_summary` is deliberately **not** called
   here — see [memory.md](memory.md#wiring-into-09_full_agentpy).
8. `finally`: calls `_report_token_usage(agent)` — **always**, on every
   path above, including the crash path in step 7 (before the
   re-raised exception actually propagates out of `main()`).

## Test coverage (`tests/test_full_agent_main.py`)

Module loaded via `importlib.util.spec_from_file_location`
(digit-prefixed filename). `OllamaAgent`, `get_logger`, `run_agent`,
and `input()` are all mocked — no live Ollama server or real terminal
needed.

- `"exit"` and all case-insensitive synonyms end the session cleanly
  without calling `run_agent`.
- A real user message is logged and passed through to `run_agent`; the
  returned answer is printed.
- The system prompt is confirmed to be the first message passed to
  `run_agent`.
- `KeyboardInterrupt` during `input()` is caught, not propagated.
- An unexpected exception from `run_agent` is logged, followed by
  `session_end(reason="crashed")`, then re-raised.
- Tool wiring sanity check: all nine real functions are present, and
  `run_agent` is offered exactly those nine tools (no more, no less —
  confirms nothing from the retired 07/08 entry points is missing and
  nothing extra leaked in).
- Mode dispatch: `auto_mode=False` (the default) calls `run_agent`, not
  `run_with_auto_mode`; `auto_mode=True` calls `run_with_auto_mode`
  instead, without extending `messages` with the raw user turn first.
- `save_session_summary` wiring: called on the `"exit"` and
  `KeyboardInterrupt` paths, **not** called on the crash path (see
  `FULLAGENT-012`–`014`).
- Token usage wiring (`FULLAGENT-015`–`020`): startup banner prints
  `load_token_usage()`'s return value; `save_token_usage()` is called
  with `agent.total_tokens` exactly once on **all three** exit paths
  (exit, `KeyboardInterrupt`, **and** crash — unlike
  `save_session_summary`); both the session total and the returned
  all-time total are printed; a non-`int` `total_tokens` (e.g. an
  unconfigured `MagicMock`) is coerced to `0` rather than crashing.
