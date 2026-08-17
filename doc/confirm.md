# confirm.py

Hardened human-in-the-loop confirmation gate. Design principle: **fail
CLOSED (deny) on every ambiguous or abnormal condition** — no tty,
timeout, malformed input, unexpected exception. A gate that can be
tricked into "fail open" is worse than no gate at all.

Threat model: `action` is a human-readable description of something an
LLM agent wants to do. The string itself may be attacker/model-influenced
(prompt injection), so it's treated as untrusted before ever being
printed or logged.

## `confirm(action: str, *, timeout_seconds: Optional[int] = 120, force_ask: bool = False) -> bool`

Asks the human before any side-effecting action (write, run, delete).
This is **the single checkpoint in the whole project where auto/step
mode is decided** — individual tools never need their own mode-checking
logic (see [agent_mode.md](agent_mode.md)).

- **If `agent_mode.AUTO_MODE` is `True` and `force_ask` is `False`** →
  auto-approves immediately without prompting, and returns `True`. The
  human already approved the plan once, up front (see
  [auto_runner.md](auto_runner.md)).
- Otherwise, prompts as normal: **returns `True`** only if the human
  explicitly typed `y`/`yes`, or pressed Enter on an empty line (bare
  Enter defaults to yes — shown explicitly in the prompt).
- **Returns `False`** for every other outcome: no tty attached, timeout
  expired, EOF on stdin, Ctrl-C, any unexpected exception, or any answer
  that isn't y/yes/empty.
- **Never raises.** Every failure mode is caught and converted to a
  denial.
- Every outcome (including auto-approval) is logged via
  `logging.getLogger("agent.confirm")` with a per-call correlation id
  (`request_id`), for audit purposes.

### Parameters

| Name | Type | Description |
|---|---|---|
| `action` | `str` | Human-readable description of the proposed action. Sanitized before display/logging. |
| `timeout_seconds` | `int \| None` | Deny and move on if unanswered in time. `None` disables the timeout (SIGALRM-based; POSIX only). Default `agent_config.CONFIRM_TIMEOUT_SECONDS` (`120`), env `CONFIRM_TIMEOUT_SECONDS` (literal `"none"` disables it). |
| `force_ask` | `bool` | If `True`, always prompt even when `agent_mode.AUTO_MODE` is on. Callers use this for anything that must never be silently approved by a pre-approved plan — e.g. `shell_tools.run_command`'s blocklist hits, and `auto_runner.py`'s own "approve the plan" question. Default `False`. |

### Internal helpers

- **`_sanitize(action) -> str`** — strips ANSI escape sequences and raw
  control characters (`_ANSI_ESCAPE` regex), coerces non-strings via
  `str()`, and caps length at `_MAX_ACTION_LEN` (from
  `agent_config.CONFIRM_MAX_ACTION_LEN`, default 400 chars, env
  `CONFIRM_MAX_ACTION_LEN`), appending
  `" …[truncated]"` when cut. Prevents a crafted `action` from rewriting
  the terminal, hiding text, or scrolling the real question off screen.
- **`_read_input_with_timeout(prompt, timeout_seconds)`** — runs
  `input(prompt)` on a background **daemon thread**, communicated back
  via a `queue.Queue`; the caller waits with `queue.get(timeout=
  timeout_seconds)`. Raises `ConfirmTimeout` if the queue wait itself
  times out; re-raises whatever `input()` raised (e.g. `EOFError`)
  otherwise. **Not signal-based** — see ROB-01 below.
- **`ConfirmTimeout`** — internal exception used to signal the timeout.
- **`_stdin_lock`** — a process-global `threading.Lock`, held for the
  duration of one `confirm()` call's input-wait. Prevents two concurrent
  `confirm()` calls from ever starting two `input()` readers on the same
  stdin at once — see the stdin race bug fixed below.

### Control flow

1. If `sys.stdin.isatty()` is `False` → log + return `False` immediately
   (headless/CI/piped context — nobody can approve anything).
2. `_stdin_lock.acquire(blocking=False)` — if another `confirm()` call
   already holds it (see below), log `reason=stdin_busy` and return
   `False` immediately, **without** printing a prompt or touching
   `input()`.
3. Print the sanitized prompt and call
   `_read_input_with_timeout(prompt, timeout_seconds)`.
4. On `ConfirmTimeout` → log + return `False`, but **deliberately do
   NOT release `_stdin_lock`** (see the bug note below — the reader
   thread is presumed still alive).
5. On `EOFError`, `KeyboardInterrupt`, or any other exception → release
   the lock, log + return `False` (in all these cases `input()` itself
   raised, so the reader thread has already ended).
6. On success → release the lock, parse the answer:
   `answer.strip().lower() in {"", "y", "yes"}` → approved.

### Notes

- **Thread Safety & Signal Handlers (ROB-01) — fixed**: the original
  implementation used `signal.signal(signal.SIGALRM)` / `signal.alarm()`
  for the timeout, which only works on the interpreter's **main**
  thread — calling it from a worker thread (e.g. a tool running inside
  `shared._run_tool_with_timeout`'s `ThreadPoolExecutor`) raised
  `ValueError`, silently denying the action instead of actually timing
  out. The fix replaces that with `_read_input_with_timeout()`
  (background daemon thread + `queue.get(timeout=...)`), which works
  correctly from **any** calling thread and needs no POSIX-only signal
  at all — the timeout now works identically on Windows.
- **Orphaned-reader stdin race — fixed (found via log analysis,
  2026-08-17)**: `shared._run_tool_with_timeout` wraps every tool call
  in its own `TOOL_TIMEOUT_SECONDS` (default 30s), independent of
  `confirm()`'s own `CONFIRM_TIMEOUT_SECONDS` (default 120s). If a human
  was still deciding on a `confirm()` prompt when the *tool-level*
  timeout fired first, the tool call was "abandoned" — but the
  `confirm()` prompt's background `input()` reader thread did **not**
  die with it; it kept listening on stdin for up to another 120s. If
  the model's very next move also needed `confirm()` (a different,
  unrelated prompt), a **second** reader thread started on the **same**
  stdin — whichever thread happened to receive the next keystroke was
  effectively random. Observed symptom: the human answers a prompt, the
  session goes silent with no further `tool_result` or `session_end` in
  the JSONL log, because the answer was consumed by the orphaned first
  reader instead of the live second one.
  *Fix*: `_stdin_lock` — only one `confirm()` call may ever be waiting
  on `input()` at a time. If an earlier (possibly orphaned) call still
  holds it, a new `confirm()` denies immediately with a clear
  `reason=stdin_busy` log line instead of racing for input. This can
  occasionally deny a `confirm()` that a human would have approved (if
  an orphaned prompt is still alive from an earlier abandoned tool
  call), but that's the project's existing fail-**closed** philosophy
  applied consistently — an ambiguous situation denies, it never
  silently guesses which prompt the human meant to answer.
- If the timeout fires, the background reader thread is left running,
  blocked on `input()` forever with nothing left listening for its
  result. Same accepted tradeoff as
  `shared._run_tool_with_timeout`'s "abandoned" worker thread — it's a
  daemon thread, so it can't block process exit.
- Every call site (`fs_tools.write_file`, `fs_tools.create_directory`,
  `shell_tools.run_command`, `human_tools.approve_action`,
  `auto_runner.run_with_auto_mode`) passes a fresh, specific action
  string per call.
- Note the auto-mode check happens **before** the no-tty check — an
  auto-approved call never touches `sys.stdin` at all.

## Test coverage (`tests/test_confirm.py`)

- `_sanitize`: plain strings, ANSI stripping, control-char stripping,
  truncation + marker, non-string coercion, empty string.
- No-tty short-circuit.
- All yes/no answer variants (case, whitespace, bare Enter).
- EOFError, KeyboardInterrupt, and generic exception during `input()`.
- Sanitization applied to the actual prompt shown to the user.
- Timeout path: `ConfirmTimeout` raised synchronously, and a genuine
  "input() outlives the timeout window" case exercising the real
  `queue.get(timeout=...)` wait.
- `timeout_seconds=None` disables the timeout entirely (blocks on
  `input()`, same as before).
- **ROB-01 regression test**: `confirm()` called from inside a
  background `threading.Thread` still resolves correctly with a
  timeout set — the exact scenario `signal.alarm()` used to crash on.
- **Stdin-race regression tests** (`TestStdinLockRace`): reproduces the
  actual reported bug — a `confirm()` call that times out (leaving its
  reader thread, and `_stdin_lock`, alive) is immediately followed by a
  second, unrelated `confirm()` call, which must deny without ever
  invoking `input()` (verified via a call-recording stub); the denial
  is logged with `reason=stdin_busy`; the lock is correctly released
  (and the *next* call proceeds normally) after a normal answer and
  after `EOFError`; the lock is never touched at all by the no-tty or
  auto-mode short-circuits (`confirm_mod._stdin_lock.locked()` checked
  directly).
  An autouse `reset_stdin_lock` fixture force-releases `_stdin_lock`
  before and after every test in this file — it's a real process-global
  lock, and the real-timeout test above deliberately leaves it held on
  purpose (mirroring the actual bug), which would otherwise leak into
  every later test.
- Auto mode: `agent_mode.AUTO_MODE=True` with `force_ask=False` (the
  default) auto-approves without ever calling `input()`; `force_ask=True`
  still prompts even with `AUTO_MODE=True`; `AUTO_MODE=False` (the
  normal default) prompts regardless of `force_ask`.
