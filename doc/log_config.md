# log_config.py

Logging configuration for the agents in this folder. All settings are
plain module-level constants, each overridable by an environment
variable of the same name, so `chat_logger.py` and call sites never need
to change — edit this file (or set env vars) instead.

## Helpers

### `_env_bool(name: str, default: bool) -> bool`

Reads a boolean from an env var. `"1"`, `"true"`, `"yes"`, `"on"`
(case-insensitive, whitespace-trimmed) → `True`. Anything else present
→ `False`. Missing var → `default`.

### `_env_int_or_none(name: str, default)`

Reads an int from an env var. The literal string `"none"`
(case-insensitive) → `None`. Missing var → `default`. Otherwise
`int(raw)` (raises `ValueError` on non-numeric input).

## Settings

| Constant | Env var | Default | Meaning |
|---|---|---|---|
| `LOG_ENABLED` | `LOG_ENABLED` | `True` | Master switch. `False` → `get_logger()` returns a no-op `NullChatLogger`, zero file I/O. |
| `LOG_DIR` | `LOG_DIR` | `Path("logs")` | Folder logs are written into. |
| `LOG_FILE_MODE` | `LOG_FILE_MODE` | `"per_run"` | `"per_run"` → one new file per session (`{agent}_{timestamp}.jsonl`). `"single"` → everything appends to one file (subject to rotation). |
| `SINGLE_LOG_FILENAME` | `SINGLE_LOG_FILENAME` | `"chat.jsonl"` | Filename used in `"single"` mode. |
| `LOG_FORMAT` | — | `"jsonl"` | Fixed; one JSON object per line (streamable, tailable). |
| `MAX_FIELD_CHARS` | `MAX_FIELD_CHARS` | `4000` | Truncate any single logged text field beyond this length. `None` disables truncation. |
| `MAX_LOG_FILE_BYTES` | `MAX_LOG_FILE_BYTES` | `10_000_000` (10 MB) | Roll the log file over to a numbered backup once it exceeds this size. `None` disables rotation. |
| `LOG_MODEL_TIMING` | `LOG_MODEL_TIMING` | `True` | Include Ollama's own performance counters (`eval_count`, `total_duration`, etc.) when present on a response. |
| `ECHO_TO_TERMINAL` | `ECHO_TO_TERMINAL` | `False` | Also print a one-line summary of every logged event to the terminal. |
| `MASK_SECRETS` | `MASK_SECRETS` | `True` | SEC-03: mask recognizable secret patterns (API keys, bearer tokens, private keys) before disk serialization. |

## Test coverage (`tests/test_log_config.py`)

- `_env_bool`: every truthy string variant (case-insensitive), every
  falsy/unrecognized string, missing-var default (both `True` and
  `False`), whitespace trimming.
- `_env_int_or_none`: missing-var default (including `None` default),
  literal `"none"` in various cases/whitespace, valid numeric string,
  non-numeric string raising `ValueError`.
