# shared.py

Hardened plumbing shared by the workshop agents: `OllamaAgent` (chat
wrapper with timeout/retry/friendly-errors) and `run_agent()` (the
ReAct-style tool-calling loop). One default model defined once, so
there's no drift between files.

## Configuration constants

All imported from [agent_config.py](agent_config.md) (each overridable
via an env var of the same name) — `shared.py` no longer hardcodes any
of these itself.

| Constant | Default | Meaning |
|---|---|---|
| `DEFAULT_MODEL` | `os.getenv("WORKSHOP_MODEL", "glm-5.2:cloud")` | Model used when `OllamaAgent()` is constructed with no argument. |
| `CHAT_TIMEOUT_SECONDS` | `60` | A single `chat()` call must return within this. |
| `CHAT_MAX_RETRIES` | `2` | Transient network errors get this many retries (3 attempts total). |
| `CHAT_RETRY_BACKOFF_SECONDS` | `2` | Linear backoff multiplier between retries (`backoff * attempt`). |
| `MAX_ITERATIONS` | `40` | Hard cap on ReAct rounds in `run_agent()`. |
| `MAX_WALL_SECONDS` | `600` | Hard ceiling on total `run_agent()` run time. |
| `TOOL_TIMEOUT_SECONDS` | `30` | No single tool call may block longer than this. |
| `MAX_REPEAT_CALLS` | `3` | Same `(tool, args)` this many times in a row → treated as a stuck loop, abort. |
| `MAX_OBSERVATION_CHARS` | `4000` | Cap on what a tool result adds back into the message history. |

## `section(title) -> str`

Returns a terminal heading: the title on one line, an `"="` underline of
matching length on the next, both preceded by a blank line.

## `class OllamaAgent`

Small, hardened wrapper around `ollama.Client`.

### `__init__(self, model=DEFAULT_MODEL)`

Binds one model to this instance, creates the underlying
`ollama.Client()`, and initializes `self.total_tokens = 0` — a running
count across every successful `chat()` call made through this instance
(see `total_tokens` below).

### `chat(self, messages, tools=None)`

Sends the full message history (the model has no memory between calls)
and returns one response.

- Runs the real client call in a `ThreadPoolExecutor` with
  `future.result(timeout=CHAT_TIMEOUT_SECONDS)`, so a stalled network
  call can't hang the whole agent.
- Retries up to `CHAT_MAX_RETRIES` times on **any** exception (including
  the timeout), sleeping `CHAT_RETRY_BACKOFF_SECONDS * attempt` between
  tries.
- On final failure, raises one friendly `RuntimeError` (`"Could not
  reach Ollama model '{model}' after N attempts: {last_error}"`) instead
  of a raw connection traceback, chained via `from last_error`.
- Every attempt/failure is logged via `logging.getLogger("agent.core")`.
- On success, adds `_extract_token_count(response)` to
  `self.total_tokens` before returning — never incremented on a failed
  attempt (only the final successful `future.result()` call counts).

### `total_tokens` (instance attribute)

Cumulative `prompt_eval_count + eval_count` across every successful
`chat()` call made through this `OllamaAgent` instance. Since
`09_full_agent.py` creates exactly one instance per run, this is
effectively "tokens used this session" — read once by the host CLI at
shutdown (see `09_full_agent.md` and `memory.md`'s
`save_token_usage()`). Not reset between calls; not touched by
`chat_stream()` (streaming responses aren't used by `09_full_agent.py`,
and per-chunk token accounting would need different handling).

### `_extract_token_count(response) -> int`

Module-level helper: `getattr(response, "prompt_eval_count", 0) or 0`
plus the same for `eval_count`. Same two fields
`chat_logger._extract_model_timing()` already reads for logging.
Missing/`None` on either → counted as `0`, not a crash — not every
Ollama backend reports both.

### `chat_stream(self, messages)`

Sends the message history and **yields** response content piece by
piece (`stream=True`). Intentionally **not** retried — once content has
partially streamed to the caller, retrying would duplicate output
already shown. Still gets the same friendly-`RuntimeError` treatment on
failure as `chat()`.

## Tool-calling loop internals

### `_call_signature(name, arguments) -> str`

Stable 16-char SHA-256 hex digest of `f"{name}:{json.dumps(arguments, sort_keys=True)}"`
(falls back to `str(arguments)` if not JSON-serializable). `sort_keys=True`
means argument key order never affects the signature. Used for
stuck-loop detection.

### `_parse_arguments(raw_arguments) -> dict`

Normalizes a tool call's arguments to a `dict`, regardless of whether
the client handed back a `dict` or a JSON string.

- `dict` → returned as-is.
- `str` → `json.loads()`'d; raises `ValueError` if not valid JSON or if
  it doesn't decode to an object (e.g. a JSON array).
- Anything else → raises `ValueError("unsupported arguments type: ...")`.

Never crashes the loop — the caller converts the `ValueError` into tool
data the model can see and correct.

### `_sanitize_for_model(text) -> str`

Truncates tool output beyond `MAX_OBSERVATION_CHARS` before it re-enters
the message history, appending `"…[truncated, {N} chars total]"`.

### `_run_tool_with_timeout(func, arguments, timeout_seconds)`

Runs one tool call in a `ThreadPoolExecutor` with a hard wall-clock
timeout. Raises `TimeoutError("tool exceeded {N}s timeout and was
abandoned")` if exceeded; propagates any other exception the tool
raises.

### `_validate_arguments(func, arguments: dict) -> None`

Checks that `arguments` actually bind to `func`'s real parameters
**before** calling it, via `inspect.signature(func).bind(**arguments)`.
Without this, a malformed tool call (typo'd parameter name, missing
required argument, an extra one the model invented) would reach
`func(**arguments)` directly and blow up with a raw `TypeError` from
Python's own argument binding — not actionable for the model, and a
generic-looking crash for a human reading the log.

On a binding failure, raises `ValueError(f"invalid arguments for
'{func.__name__}': {e}. Expected parameters: {expected}. Got:
{given}.")` — same "errors are data, not crashes" principle as the rest
of the loop: this becomes ordinary tool-result data the model can read
and correct on its next attempt, not a raised exception.

## `run_agent(agent, messages, tools, tool_map, verbose=True, max_iterations=MAX_ITERATIONS, max_wall_seconds=MAX_WALL_SECONDS, chat_logger=None, max_tool_calls=None) -> str`

Runs the tool-calling loop until the model gives a final answer (a
response with no `tool_calls`). Returns the final answer text, or one of
several `"(stopped: ...)"` strings on abnormal termination.

Every round is logged via Python's `logging` module with a per-run id
(`run_id`). If `chat_logger` is passed, every stage additionally gets a
structured JSONL record via `chat_logger.py`. `chat_logger=None` defaults
to a silent `NullChatLogger()`.

`max_tool_calls` is a separate, optional cap on the **total number of
tool calls across the whole run** (not rounds — a single round can
contain several calls). Built for auto mode (see
[auto_runner.md](auto_runner.md)): "stop after 30 tool calls if the
task isn't finished" is a call-count budget, not a round-count one, and
`max_iterations` alone can't express that. `None` (the default) means
no extra cap beyond `max_iterations`.

### Per-round flow

1. **Wall-clock check**: if elapsed time exceeds `max_wall_seconds` →
   return `"(stopped: exceeded maximum run time)"`.
2. **Model call**: `agent.chat(messages, tools=tools)`. If this raises
   (past `OllamaAgent.chat`'s own retries) → return `"(stopped: error
   communicating with the model)"`.
3. Append the assistant's raw message object to `messages`.
4. If `verbose` and there's text content, print it as `[thought]`.
5. **No tool calls** → this is the final answer; return
   `response.message.content or ""`.
6. **For each requested tool call**:
   - Increment the running `total_tool_calls` counter; if
     `max_tool_calls` is set and now exceeded → return `"(stopped:
     reached the {max_tool_calls}-tool-call limit — not a failure, just
     a sign the plan wandered; check plan.md and the log to see
     where)"`. Checked **before** parsing arguments or invoking the
     tool, so the call that would exceed the cap never runs.
   - Look up `func = tool_map.get(tool_name)` (looked up once, up
     front, before parsing/validation — used both by the validation
     step below and the unknown-tool check further down).
   - Parse arguments via `_parse_arguments()`; a `ValueError` here (or
     from the validation step below) is appended to `messages` as a
     `{"role": "tool", "content": "Error: ..."}` entry and the loop
     continues to the next call (not a hard stop).
   - If `func` was found, validate the parsed arguments against its
     real signature via `_validate_arguments(func, arguments)` — a
     mismatch raises `ValueError`, caught the same way as a
     `_parse_arguments()` failure above.
   - Compute the call signature and check for stuck loops:
     triggers if the exact same signature repeats `MAX_REPEAT_CALLS`
     times, or if an alternating 2-step (A,B,A,B,...) or 3-step
     (A,B,C,A,B,C,...) cycle repeats `MAX_REPEAT_CALLS` times → return
     `"(stopped: '{tool}' is part of a repeating tool-call pattern — agent appears stuck)"`.
   - `func is None` → unknown-tool error observation, doesn't call
     anything.
   - Otherwise run via `_run_tool_with_timeout(func, arguments,
     TOOL_TIMEOUT_SECONDS)`, catching `TimeoutError` and any other
     `Exception` (full traceback goes only to the log, never into the
     model's context — just `"{ExceptionType}: {message}"`).
   - Sanitize the result via `_sanitize_for_model()` and append it as a
     `{"role": "tool", "name": tool_name, "content": result}` message.
7. If `max_iterations` rounds complete without a final answer → return
   `"(stopped: too many tool rounds)"`.

### Guarantees

- Tool errors, timeouts, malformed arguments, and repeated/stuck calls
  are always fed back to the model as data — the loop itself never
  raises because of tool behavior.
- `agent.chat()` failures are the one place the loop terminates instead
  of continuing (since without a model response there's nothing to act
  on).

## Test coverage (`tests/test_shared.py`)

All network calls are mocked (`FakeClient`, `FakeAgent`) — no live
Ollama server needed.

- `section`: normal title, empty title.
- `_call_signature`: identical inputs match, key order doesn't matter,
  different args/tool names differ, unserializable args fall back to
  `str()` without raising.
- `_parse_arguments`: dict passthrough, valid/invalid JSON strings,
  JSON array (non-object) rejection, unsupported type rejection, empty
  dict.
- `_sanitize_for_model`: short text untouched, long text truncated with
  marker, exact-boundary length untouched.
- `_run_tool_with_timeout`: normal return, timeout on a hanging
  function, exception propagation.
- `_validate_arguments`: matching arguments pass silently; a missing
  required parameter, an unknown/extra parameter, and a typo'd
  parameter name all raise `ValueError` naming the function, expected
  parameters, and what was actually given.
- `OllamaAgent.chat`: first-try success, retry-then-succeed, all
  retries exhausted → friendly `RuntimeError`, default model resolution.
- `OllamaAgent.total_tokens`: starts at `0`; accumulates
  `prompt_eval_count + eval_count` on success; accumulates across
  multiple `chat()` calls (not overwritten); missing fields count as
  `0` rather than crashing; **not** incremented when a call ultimately
  fails after retries.
- `OllamaAgent.chat_stream`: chunk yielding, friendly `RuntimeError` on
  failure.
- `run_agent`: final answer (with and without `None` content), a
  successful tool call followed by a final answer, unknown tool,
  tool exception, tool timeout (via patched `TOOL_TIMEOUT_SECONDS`),
  malformed arguments, a tool call with arguments that don't bind to
  the tool's real signature (fed back as a `ValueError` tool-result,
  never reaching the function), stuck-loop detection, `agent.chat()`
  failure,
  `max_iterations` exhaustion (both the trivial single-round case and a
  multi-round case with varying tool arguments), wall-clock timeout,
  default `NullChatLogger` when none is passed, a custom logger
  actually receiving `model_call_start`/`model_response` calls, and
  `max_tool_calls`: stopping exactly at the cap, the capped call itself
  never reaching the tool, and `None` (default) leaving the loop
  uncapped.
