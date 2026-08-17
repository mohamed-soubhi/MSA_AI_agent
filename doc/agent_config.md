# agent_config.py

Central configuration for the agent — every "how long / how many /
what's allowed" knob, in one place, each overridable by an environment
variable of the same name. Mirrors the pattern `log_config.py` already
established for logging; this file covers everything else (chat/
network, the tool loop, filesystem limits, shell allow/block lists,
`confirm()` behavior, auto mode).

Nothing in `shared.py`, `fs_tools.py`, `shell_tools.py`, `confirm.py`,
or `auto_runner.py` hardcodes these values anymore — change a number
here (or export the matching env var before running) and it takes
effect everywhere that setting is used, without touching any of those
files. `log_config.py` stays separate on purpose: it's a distinct
concern (logging) that already had its own file before this one
existed.

## `PROJECT_ROOT` (module constant, not env-overridable)

`PROJECT_ROOT = Path(__file__).resolve().parent.parent` — this file
lives in `agent/`, one level under the project root, so `PROJECT_ROOT`
is computed from **this file's own on-disk location**, never from the
process's working directory. Everything below that's supposed to be
launch-directory-independent (`WORKSPACE_DIR`, `MEMORY_FILE`'s default,
`log_config.LOG_DIR`'s default) is anchored to this, not to `Path.cwd()`
or a relative string. See [fs_tools.md](fs_tools.md) for the bug this
fixes (the agent's sandbox used to be `Path.cwd()`, which — launched
from the project root, as it normally was — let it read/edit its own
source).

## Parsing helpers

| Helper | Behavior |
|---|---|
| `_env_bool(name, default)` | `"1"`/`"true"`/`"yes"`/`"on"` (case-insensitive, trimmed) → `True`; anything else present → `False`; missing → `default`. |
| `_env_int(name, default)` | `int(raw)` if set, else `default`. A non-numeric value logs a warning and falls back to `default` rather than raising (ROB-05). |
| `_env_int_or_none(name, default)` | Literal `"none"` (case-insensitive) → `None`; missing → `default`; otherwise `int(raw)`. |
| `_env_set(name, default)` | Comma-separated env value → a `set` of trimmed, non-empty items; missing → `default`. |
| `_env_list(name, default)` | Same as `_env_set` but returns a `list` (order preserved); missing → `default`. |

## Settings by module

### Ollama / chat (`shared.py` — `OllamaAgent`)

| Constant | Env var | Default |
|---|---|---|
| `DEFAULT_MODEL` | `WORKSHOP_MODEL` | `"glm-5.2:cloud"` |
| `CHAT_TIMEOUT_SECONDS` | `CHAT_TIMEOUT_SECONDS` | `60` |
| `CHAT_MAX_RETRIES` | `CHAT_MAX_RETRIES` | `2` |
| `CHAT_RETRY_BACKOFF_SECONDS` | `CHAT_RETRY_BACKOFF_SECONDS` | `2` |

### Agent tool loop (`shared.py` — `run_agent`)

| Constant | Env var | Default |
|---|---|---|
| `MAX_ITERATIONS` | `MAX_ITERATIONS` | `40` |
| `MAX_WALL_SECONDS` | `MAX_WALL_SECONDS` | `600` |
| `TOOL_TIMEOUT_SECONDS` | `TOOL_TIMEOUT_SECONDS` | `30` |
| `MAX_REPEAT_CALLS` | `MAX_REPEAT_CALLS` | `3` |
| `MAX_OBSERVATION_CHARS` | `MAX_OBSERVATION_CHARS` | `4000` |

### Filesystem tools (`fs_tools.py`)

| Constant | Env var | Default |
|---|---|---|
| `WORKSPACE_DIR` | `WORKSPACE_DIR` | `PROJECT_ROOT / "workspace"` |
| `MAX_WRITE_BYTES` | `MAX_WRITE_BYTES` | `2_000_000` (2 MB) |
| `REQUIRE_CONFIRMATION` | `REQUIRE_CONFIRMATION` | `True` |

`WORKSPACE_DIR` is `fs_tools.BASE_DIR` — the sandbox root every path
resolves against. Fixed at `<project_root>/workspace/` by default, a
folder sitting next to `agent/` (the source code), not inside it — see
[fs_tools.md](fs_tools.md#sandbox-escape-fix-agent-could-readedit-its-own-source).

### Shell tools (`shell_tools.py`)

| Constant | Env var | Default |
|---|---|---|
| `SHELL_ALLOWED` | `SHELL_ALLOWED` (comma-separated) | 11 program names |
| `SHELL_BLOCKED` | `SHELL_BLOCKED` (comma-separated) | 10 dangerous substrings |
| `SHELL_TIMEOUT_SECONDS` | `SHELL_TIMEOUT_SECONDS` | `120` |
| `SHELL_MAX_OUTPUT_LINES` | `SHELL_MAX_OUTPUT_LINES` | `50` |

`shell_tools.py` imports these under its own shorter local names
(`ALLOWED`, `BLOCKED`, `TIMEOUT_SECONDS`, `MAX_OUTPUT_LINES`) — see
[shell_tools.md](shell_tools.md).

### `confirm()` (`confirm.py`)

| Constant | Env var | Default |
|---|---|---|
| `CONFIRM_TIMEOUT_SECONDS` | `CONFIRM_TIMEOUT_SECONDS` | `120` (or `None` via literal `"none"`) |
| `CONFIRM_MAX_ACTION_LEN` | `CONFIRM_MAX_ACTION_LEN` | `400` |

### Auto mode (`auto_runner.py`)

| Constant | Env var | Default |
|---|---|---|
| `MAX_AUTO_TOOL_CALLS` | `MAX_AUTO_TOOL_CALLS` | `30` |

### Memory (`memory.py`)

| Constant | Env var | Default |
|---|---|---|
| `MEMORY_ENABLED` | `MEMORY_ENABLED` | `True` |
| `MEMORY_FILE` | `MEMORY_FILE` | `PROJECT_ROOT / "memory.json"` |
| `MEMORY_MAX_ENTRIES` | `MEMORY_MAX_ENTRIES` | `500` |
| `MEMORY_MAX_TEXT_CHARS` | `MEMORY_MAX_TEXT_CHARS` | `1000` |
| `MEMORY_MAX_RECALL_RESULTS` | `MEMORY_MAX_RECALL_RESULTS` | `10` |
| `MEMORY_SUMMARY_MAX_MESSAGES` | `MEMORY_SUMMARY_MAX_MESSAGES` | `40` |

See [memory.md](memory.md) for what each setting controls.

### System prompt (`CLI_agent.py`)

| Constant | Env var | Default |
|---|---|---|
| `SYSTEM_PROMPT` | `SYSTEM_PROMPT` | multi-line prompt text (see below) |

Unlike every other setting above, this one holds free-form text, not a
number/bool/list. `CLI_agent.py` no longer defines its own
`SYSTEM_PROMPT` — it imports this constant and seeds it as the first
message in `messages` on every run, unchanged from before. Set the
`SYSTEM_PROMPT` env var to replace the whole prompt (a different
persona or ruleset) without touching code; there's no partial-override
mechanism — it's all-or-nothing, same as `SHELL_ALLOWED`/`SHELL_BLOCKED`
replacing their whole list rather than merging with the default.

## Test coverage (`tests/test_agent_config.py`)

- Each `_env_*` helper: default value when the env var is unset, every
  parseable form. `_env_int`: a bad value logs a warning and falls back
  to `default` (ROB-05). `_env_int_or_none`: a bad value still raises
  `ValueError` — out of scope for ROB-05, untouched.
- `_env_set`/`_env_list`: comma-splitting, whitespace trimming, empty
  items dropped, set-vs-list return type, order preserved for the list
  variant.
- Spot checks that the module-level constants resolve to their
  documented defaults when no env vars are set (confirms nothing
  silently drifted from this doc), including the `MEMORY_*` settings
  and `SYSTEM_PROMPT`.
- `SYSTEM_PROMPT` env var override: reloads the module with
  `SYSTEM_PROMPT` set and confirms the constant reflects the override,
  then reloads again after cleanup to restore the real default for
  later tests in the same process.
