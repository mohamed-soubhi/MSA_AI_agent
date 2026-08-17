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
3. **`confirm()`** — every *other* (non-blocklisted) command still goes
   through the normal `confirm()` gate: auto-approves in auto mode (the
   plan already covered it) or asks in step mode. Same hard gate used
   everywhere else in this project (see [confirm.md](confirm.md)).
4. **Timeout** (`TIMEOUT_SECONDS = 120`) — a command that hangs (waiting
   on stdin, an infinite loop) is killed rather than blocking the agent
   loop forever.

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
5. **Layer 3** (only reached when layer 2 didn't trigger): `confirm(f"run:
   {command}")`; denied → `"Command cancelled by user."`
6. **Layer 4 + execution**: `subprocess.run(command, shell=True,
   cwd=BASE_DIR, capture_output=True, text=True,
   timeout=TIMEOUT_SECONDS)`.
   - On completion: `_format_result(result.returncode, result.stdout, result.stderr)`.
   - `subprocess.TimeoutExpired`: a killed process has no real exit
     code, but may still have partial output captured before the kill —
     `_format_result(None, partial_stdout, partial_stderr, note=f"Timed
     out after {TIMEOUT_SECONDS}s and was killed.")` rather than
     discarding whatever ran before the kill.
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

`subprocess.run` and `confirm()` are fully mocked — no real commands
ever run.

- Empty/whitespace-only command, unparseable (unbalanced quotes) input.
- Allowlist: rejected program, path-prefix stripping
  (`/usr/bin/python3`), every allowlisted program individually passes
  layer 1.
- Blocklist: all 10 dangerous patterns individually route through
  `confirm(..., force_ask=True)` with the "DANGEROUS pattern detected"
  text — approved lets the command through to execution, denied returns
  the "not approved" message; confirmed the layer-3 `confirm()` call is
  **not** made when layer 2 already handled the confirmation.
- Confirmation gate (non-blocklisted commands): cancellation on denial,
  and the exact `"run: {command}"` text passed through to `confirm()`.
- Execution: `exit_code`/`stdout`/`stderr` fields present and correct,
  `cwd=BASE_DIR` sandboxing, independent per-stream line-based
  truncation past `MAX_OUTPUT_LINES` (keeping the *last* N lines, not
  the first), `"(empty)"` placeholder for a blank stream,
  `TimeoutExpired` preserving partial output plus the timeout `note`,
  and a generic exception rendered through the same `_format_result()`
  path with `exit_code: (none — process killed)`.

## Security Threat Model & Audit Notes

From the [Code Review & Defect Assessment Report](code_review_report.md):

1. **Compound Command / Shell Operator Chaining (SEC-01)**:
   Because `shell_tools.py` executes commands with `shell=True` after parsing only `shlex.split(command)[0]`, compound commands using operators like `&&`, `||`, `;`, `|`, or backticks could execute non-allowlisted binaries if chained behind an allowed first token (e.g. `echo ok && /bin/bash -c ...`). In auto mode, Layer 3 auto-approves this.
   *Mitigation Roadmap*: Parse compound shell statements or restrict to `shell=False` execution with explicit argument arrays.

2. **Process Group Orphan Management on Timeout (SEC-02)**:
   When `subprocess.run` times out, Python kills only `/bin/sh`. Background or detached child processes continue running in the background.
   *Mitigation Roadmap*: Use `start_new_session=True` and `os.killpg` on timeout.

