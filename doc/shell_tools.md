# shell_tools.py

Gives the agent a terminal, safely: allowlist + blocklist + human
confirm + timeout — **a layer, not a fortress**. Four independent
defenses stacked; none alone is a guarantee, but together the surviving
space is small, and every command still needs a human's explicit "y"
before it touches anything.

## The four layers

1. **Allowlist** (`ALLOWED`) — only these programs may be launched at
   all: `python`, `python3`, `ls`, `cat`, `echo`, `pip`, `pytest`,
   `node`, `npm`, `mkdir`, `cd`.
2. **Blocklist** (`BLOCKED`) — a command containing an obviously
   dangerous substring **always forces a real human prompt**, even in
   auto mode. Checked against the **full command string** (not just the
   first token): `"rm "`, `"rm-"`, `"sudo"`, `"mkfs"`, `"dd "`,
   `":(){"` (fork bomb), `"> /dev"`, `"curl "`, `"wget "`, `"chmod "`,
   `"mv /"`. This is **not** a silent reject — a human can still say
   yes to the exact text via `confirm(..., force_ask=True)` — but a
   pre-approved auto-mode plan can never run one of these unattended
   (see [agent_mode.md](agent_mode.md), [confirm.md](confirm.md)).
   Checking the full string catches a chained/injected command riding
   behind an allowlisted program, e.g. `python3 -c '...'; rm -rf .` is
   caught by `"rm "` even though `python3` alone is allowlisted.
3. **`confirm()`** — every *other* (non-blocklisted, non-compound)
   command still goes through the normal `confirm()` gate: auto-approves
   in auto mode (the plan already covered it) or asks in step mode. Same
   hard gate used everywhere else in this project (see
   [confirm.md](confirm.md)). A command containing a shell chaining or
   substitution operator (`&&`, `||`, `;`, `|`, `&`, `$(`, backtick) is
   treated the same as a blocklist hit — it always `force_ask`s a real
   human, never silently auto-approves (SEC-01, see below).
4. **Timeout** (`TIMEOUT_SECONDS = 120`) — a command that hangs (waiting
   on stdin, an infinite loop) is killed, **together with its entire
   process group** (SEC-02, see below), rather than blocking the agent
   loop forever or leaving an orphaned child process running.

**Honest limitation, stated rather than hidden**: layers 1–2 can be
talked around by an *allowed* interpreter (`python3`, `node`) running
arbitrary code internally — `python3 -c "..."` is still `"python3"`,
and a blocklist built from string patterns can't reason about what a
script does. This is why layer 3 is not optional: the human reviewing
the exact command text before it runs is the real backstop, not the
lists.

## Module constants

| Name | Value | Purpose |
|---|---|---|
| `ALLOWED` | 11 program names | Layer 1. Extend deliberately. Imported from [agent_config.py](agent_config.md)'s `SHELL_ALLOWED`, env `SHELL_ALLOWED` (comma-separated). |
| `BLOCKED` | 10 substrings | Layer 2, matched against the full command. Imported from `agent_config.SHELL_BLOCKED`, env `SHELL_BLOCKED` (comma-separated). |
| `TIMEOUT_SECONDS` | `120` | Layer 4 hard ceiling per command. Imported from `agent_config.SHELL_TIMEOUT_SECONDS`, env `SHELL_TIMEOUT_SECONDS`. |
| `MAX_OUTPUT_LINES` | `50` | Cap applied **independently** to stdout and to stderr, keeping only the **last** N lines of each — see `_format_result()` below. Imported from `agent_config.SHELL_MAX_OUTPUT_LINES`, env `SHELL_MAX_OUTPUT_LINES`. |

All four are aliased to shorter local names on import
(`from agent_config import SHELL_ALLOWED as ALLOWED, ...`), so this
module's own code and tests still reference the short names shown
above.

## `run_command(command: str) -> str`

Runs a non-interactive shell command inside `fs_tools.BASE_DIR` (the
same sandbox root used everywhere else). Never raises — every outcome
is rendered by `_format_result()` into a labeled multi-line string the
model can read.

Docstring on the tool tells the model explicitly: check `exit_code`,
not just whether `stderr` is non-empty — a nonzero exit with empty
stderr means something different than a zero exit with noisy stderr.

### Control flow

1. Strip whitespace; empty → `"Blocked: empty command."`
2. Extract the program name via `shlex.split()` (not a naive
   `.split()`, so quoted arguments with spaces don't confuse which
   token is the program) and strip any path prefix
   (`/usr/bin/python3` → `python3`). Unparseable input (unbalanced
   quotes) → `"Blocked: could not parse command (...)."`, not a crash.
3. **Layer 1**: program not in `ALLOWED` → `"Blocked: '{program}' is
   not in the allowlist {sorted(ALLOWED)}."`
4. **Layer 2**: any `BLOCKED` substring present in the full command →
   `confirm(f"DANGEROUS pattern detected, approve anyway?\nrun:
   {command}", force_ask=True)`. If denied →
   `"Blocked: command contains a forbidden pattern and was not
   approved."` If approved, execution proceeds as normal.
5. **SEC-01 compound-operator check** (only reached when layer 2 didn't
   trigger): `_is_compound(command)` — `True` if the command contains
   `&&`, `||`, `;`, `|`, `&`, `$(`, or a backtick. If so →
   `confirm(f"Compound/chained command detected, approve anyway?\nrun:
   {command}", force_ask=True)`; denied → `"Blocked: compound/chained
   command was not approved."` This closes the gap where layer 1 only
   ever checked the *first* token — a chained command like `echo hi &&
   /bin/bash -c '...'` used to pass layer 1 (`echo` is allowlisted),
   skip layer 2 if no `BLOCKED` substring matched, and reach the plain
   `confirm()` below — which auto-approves in auto mode. Now it always
   force-asks, same as a blocklist hit.
6. **Layer 3** (only reached when neither layer 2 nor the compound
   check triggered): `confirm(f"run: {command}")`; denied →
   `"Command cancelled by user."`
7. **Layer 4 + execution**: `subprocess.Popen(command, shell=True,
   cwd=BASE_DIR, stdout=PIPE, stderr=PIPE, text=True,
   start_new_session=True)`, then `proc.communicate(timeout=
   TIMEOUT_SECONDS)`. `start_new_session=True` puts the shell in its own
   process group (SEC-02).
   - On completion: `_format_result(proc.returncode, stdout, stderr)`.
   - `subprocess.TimeoutExpired`: `os.killpg(os.getpgid(proc.pid),
     signal.SIGKILL)` kills the **whole process group** — the shell
     *and* anything it spawned — not just the immediate `/bin/sh`
     (SEC-02 fix; previously a timed-out `npm run dev`-style command
     left its child running, orphaned, in the background). A
     `ProcessLookupError`/`PermissionError`/`OSError` from `killpg`
     (process already exited on its own) is caught and logged, not
     raised. `proc.communicate()` (no timeout) is called again after
     the kill to drain whatever partial output exists —
     `_format_result(None, partial_stdout, partial_stderr, note=f"Timed
     out after {TIMEOUT_SECONDS}s and was killed.")`.
   - Any other exception: `_format_result(None, "", "", note=f"Could
     not run command: {error}")`.

Every blocked/timed-out/errored attempt is logged via
`logging.getLogger("agent.shell_tools")`.

## `_format_result(exit_code, stdout, stderr, note="") -> str`

Renders a command's outcome as **distinct, clearly-labeled fields**
instead of merging stdout/stderr into one blob — the model (and a human
reading the JSONL log) needs the exit code and the two streams kept
separate. Each stream is capped **independently** at `MAX_OUTPUT_LINES`
lines so a giant stdout can't crowd out a short but important stderr
message, or vice versa.

Output shape (each line always present except `note`, which only
appears when set):

```
exit_code: 0
note: Timed out after 120s and was killed.   ← only present on timeout/error
stdout:
<stdout text, or "(empty)", capped independently>
stderr:
<stderr text, or "(empty)", capped independently>
```

- `exit_code` prints literally, or `"(none — process killed)"` when
  `None` (timeout/exception path — a killed process has no real exit
  code).
- Each stream is `.strip()`'d; empty → `"(empty)"`.
- **Line-based cap, not char-based**: everything a tool returns lands
  in the message history, and the message history *is* the context
  window — a verbose build/test command dumping full output would bloat
  context every round. Past `MAX_OUTPUT_LINES` lines, only the **last**
  N lines are kept (errors and final results usually show up at the
  end, not the beginning), prefixed with
  `f"[... {omitted} lines omitted ...]\n\n"`.

## Test coverage (`tests/test_shell_tools.py`)

`subprocess.Popen` and `confirm()` are fully mocked (via a `FakePopen`
test double driven by `.communicate()`) — no real commands or OS
process groups are ever touched.

- Empty/whitespace-only command, unparseable (unbalanced quotes) input.
- Allowlist: rejected program, path-prefix stripping
  (`/usr/bin/python3`), every allowlisted program individually passes
  layer 1.
- Blocklist: all 10 dangerous patterns individually route through
  `confirm(..., force_ask=True)` with the "DANGEROUS pattern detected"
  text — approved lets the command through to execution, denied returns
  the "not approved" message; confirmed the layer-3 `confirm()` call is
  **not** made when layer 2 already handled the confirmation.
- **Compound operator force-ask (SEC-01)**: each operator (`&&`, `||`,
  `;`, `|`, `&`, `$(`, backtick) individually routes through
  `confirm(..., force_ask=True)` with the "Compound/chained command
  detected" text; approved lets the command execute; a simple command
  with no operator does **not** force-ask (plain `confirm(action)`,
  no kwargs); `_is_compound()` unit-tested directly for every operator.
- Confirmation gate (non-blocklisted, non-compound commands):
  cancellation on denial, and the exact `"run: {command}"` text passed
  through to `confirm()`.
- Execution: `exit_code`/`stdout`/`stderr` fields present and correct,
  `cwd=BASE_DIR` sandboxing, independent per-stream line-based
  truncation past `MAX_OUTPUT_LINES` (keeping the *last* N lines, not
  the first), `"(empty)"` placeholder for a blank stream, a generic
  exception rendered through the same `_format_result()` path with
  `exit_code: (none — process killed)`.
- **Timeout + process-group kill (SEC-02)**: `TimeoutExpired` on the
  first `communicate()` call preserves partial output plus the timeout
  `note`; `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` is called
  with the exact `proc.pid`; a `ProcessLookupError` from `killpg` (the
  process already exited on its own) does not crash the call and still
  returns the timeout result.

## Security Threat Model & Audit Notes

Findings from the [Code Review & Defect Assessment Report](code_review_report.md) touching this module — both now fixed (see that report's Remediation Status table for the full list):

1. **Compound Command / Shell Operator Chaining (SEC-01) — fixed**:
   Because `shell_tools.py` executes commands with `shell=True` after parsing only the *first* token via `shlex.split(command)[0]`, a compound command using operators like `&&`, `||`, `;`, `|`, or backticks could execute a non-allowlisted binary if chained behind an allowed first token (e.g. `echo ok && /bin/bash -c ...`) — and in auto mode, the plain `confirm()` at layer 3 would auto-approve it silently.
   *Fix*: `_is_compound()` detects any of these operators and force-asks a real human confirm, exactly like a `BLOCKED` pattern — auto mode can no longer silently approve a compound command, regardless of what's hidden after the operator.

2. **Process Group Orphan Management on Timeout (SEC-02) — fixed**:
   When `subprocess.run` timed out, Python killed only `/bin/sh`. Background or detached child processes it spawned continued running, orphaned.
   *Fix*: switched to `subprocess.Popen(..., start_new_session=True)`; on timeout, `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` kills the shell's entire process group.

