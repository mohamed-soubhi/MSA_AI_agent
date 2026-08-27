# chat_logger.py

Structured JSONL logging for agent chat sessions. Every event (session
start, user message, model response, each tool call/result, errors,
session end) is one JSON object per line — `tail -f`-able live, or
loadable via `pandas.read_json(path, lines=True)`.

Behavior is controlled entirely by `log_config.py`; this module only
implements it.

## Line schema

Every written line has this shape:

```json
{
  "ts": "2026-08-10T12:34:56.789",
  "session_id": "a1b2c3d4e5f6",
  "agent": "filesystem_agent",
  "model": "deepseek-v4-flash:cloud",
  "turn": 0,
  "event": "user_message",
  "...event-specific fields": "..."
}
```

`session_id` is a random 12-hex-char id generated once per `ChatLogger`
instance. `turn` increments on each `user_message()` call.

## `_truncate(value)`

Recursively shortens any string field beyond `cfg.MAX_FIELD_CHARS`,
applied to dict values and list items too (so a nested `write_file`
`content` argument still gets truncated). `None` limit disables
truncation entirely. Non-string/short values pass through untouched.

## `_mask_secrets(value)`

SEC-03: Recursively masks recognizable secret patterns (API keys,
GitHub personal access tokens, Bearer authorization tokens, and
`.env`-style password/secret assignments) before fields are written to
disk. Controlled by `cfg.MASK_SECRETS` (defaults to `True`). Non-string
values and clean text pass through untouched.

## `_extract_model_timing(response) -> dict`

Pulls Ollama's own performance counters off a chat response, if
present: `total_duration`, `load_duration`, `prompt_eval_count`,
`prompt_eval_duration`, `eval_count`, `eval_duration` (all nanoseconds
except the counts). Missing fields are omitted, not logged as
null/zero. Returns `{}` if `cfg.LOG_MODEL_TIMING` is `False`.

## `class ChatLogger`

Writes one JSON line per event to a per-session or shared log file.

### `__init__(self, agent_name: str, model: str)`

Creates `cfg.LOG_DIR` if needed, picks the log file path per
`cfg.LOG_FILE_MODE` (`"single"` → `cfg.SINGLE_LOG_FILENAME`; `"per_run"`
→ `{agent_name}_{YYYYmmdd_HHMMSS}.jsonl`), generates a `session_id`, and
writes the first `session_start` event. Raises `OSError` if `LOG_DIR`
can't be created (caught by `get_logger()`, not here).

### Public methods

| Method | Event | Notes |
|---|---|---|
| `user_message(text)` | `user_message` | Increments `turn_index` first. |
| `model_call_start(message_count, tools)` | `model_call_start` | Starts an internal latency timer; logs tool names only (`[t.__name__ for t in tools]`). |
| `model_response(content, tool_calls, response=None)` | `model_response` | Computes `elapsed_ms` from the timer started above (`None` if no prior start). Merges in `_extract_model_timing(response)`. |
| `tool_call(name, arguments)` | `tool_call` | Returns a `time.perf_counter()` token to pass to `tool_result()`. |
| `tool_result(name, result, start_time, error=False)` | `tool_result` | Computes elapsed ms from `start_time`. |
| `loop_limit_hit(max_iterations)` | `loop_limit_hit` | Logged when the ReAct loop hits `MAX_ITERATIONS` without a final answer. |
| `error(message, **context)` | `error` | For non-tool errors, e.g. the model call itself failing. |
| `session_end(reason="user_exit")` | `session_end` | Call before process exit. |

### `_write(event, **fields)` (internal)

Builds the record, JSON-serializes it (`default=str`; on a genuinely
unserializable field, logs a `log_error` stub instead of losing the
event or crashing), and appends it under a `threading.Lock` (protects
concurrent tool calls in the future). **Never raises** — a disk-full or
permissions error degrades to a stderr warning, since logging is a side
channel, not part of the agent's critical path. Rotation is checked
(and possibly performed) before every write, while the lock is held.

### `_rotate_if_needed(self)` (internal)

If `cfg.MAX_LOG_FILE_BYTES` is set and the current file has grown past
it, renames the file to `{stem}.{timestamp}{suffix}` before the next
write. A rename failure (e.g. permissions) warns to stderr and
continues logging to the same file rather than stopping logging.

## `class NullChatLogger`

No-op logger used when `cfg.LOG_ENABLED` is `False`. Mirrors
`ChatLogger`'s public method signatures (all accept `*a, **k` and do
nothing; `tool_call()` returns `0.0`), so call sites never need an
`if logging_enabled:` branch.

## `get_logger(agent_name: str, model: str)`

The only entry point call sites should use.

- `cfg.LOG_ENABLED is False` → returns `NullChatLogger()`.
- Otherwise tries `ChatLogger(agent_name, model)`; on `OSError` (e.g.
  read-only filesystem), warns to stderr and falls back to
  `NullChatLogger()` rather than crashing agent startup over a logging
  problem.

## Test coverage (`tests/test_chat_logger.py`)

44 tests (`CHATLOG-001` .. `CHATLOG-032`), covering:

- `_truncate`: short/long/`None`-limit strings, non-string passthrough,
  recursion into dicts and lists.
- `_extract_model_timing`: present fields, missing fields omitted,
  disabled-via-config returns `{}`.
- `ChatLogger.__init__`: dir creation + `session_start` line,
  `per_run` filename format, `single` mode file reuse across instances.
- Every event method: `user_message` turn increment, `model_call_start`
  tool-name extraction, `model_response` elapsed-ms with and without a
  prior `model_call_start`, timing fields merged from a fake response,
  `tool_call`/`tool_result` pairing and elapsed time, `loop_limit_hit`,
  `error` with extra context, `session_end` default and custom reason.
- Hardening: unserializable field degrades to a log stub instead of
  raising; a simulated write failure (`OSError`) does not raise;
  `ECHO_TO_TERMINAL` prints to stdout.
- Rotation: file rolls over past `MAX_LOG_FILE_BYTES`; disabled when the
  limit is `None`.
- `NullChatLogger`: every method callable with arbitrary args, never
  raises.
- `get_logger`: disabled → `NullChatLogger`; enabled → `ChatLogger`;
  init failure → falls back to `NullChatLogger`.
