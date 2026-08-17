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
- **`_timeout_handler(signum, frame)`** — SIGALRM handler; raises
  `ConfirmTimeout`.
- **`ConfirmTimeout`** — internal exception used to unwind `input()` on
  timeout.

### Control flow

1. If `sys.stdin.isatty()` is `False` → log + return `False` immediately
   (headless/CI/piped context — nobody can approve anything).
2. Arm a `SIGALRM` for `timeout_seconds` (if set and supported).
3. Print the sanitized prompt and call `input()`.
4. On `ConfirmTimeout`, `EOFError`, `KeyboardInterrupt`, or any other
   exception → log + return `False`.
5. `finally`: always disarm the alarm and restore the previous SIGALRM
   handler, so no pending alarm leaks into unrelated code.
6. Parse the answer: `answer.strip().lower() in {"", "y", "yes"}` →
   approved.

### Notes

- SIGALRM is POSIX-only; on platforms without it (e.g. native Windows),
  the timeout is silently skipped and `input()` blocks indefinitely.
- **Thread Safety & Signal Handlers (ROB-01)**: `signal.signal(signal.SIGALRM)`
  is only supported on the interpreter's main thread. When tools run
  in secondary threads (e.g. via `shared._run_tool_with_timeout`), calling
  `signal.signal()` raises a `ValueError`, which `confirm()` catches to
  safely deny the action (fail-closed).
  *Roadmap*: Replace `signal.alarm` with non-blocking terminal I/O (`select.select`).
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
- Timeout path (skipped on non-POSIX platforms lacking `SIGALRM`).
- Alarm is disarmed after both success and timeout.
- `timeout_seconds=None` disables the alarm entirely.
- Auto mode: `agent_mode.AUTO_MODE=True` with `force_ask=False` (the
  default) auto-approves without ever calling `input()`; `force_ask=True`
  still prompts even with `AUTO_MODE=True`; `AUTO_MODE=False` (the
  normal default) prompts regardless of `force_ask`.
