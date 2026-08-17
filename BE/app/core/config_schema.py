"""Schema for the interactive config editor (GET/POST /api/config,
served at /config).

One field list drives both what the editor form shows AND how values
get written back to disk -- so the form can never drift out of sync
with what agent_config.py/log_config.py/BE's own Settings actually
read. Each field's CURRENT value is read live from the real config
modules at request time (via sys.path-injecting agent/ the same way
tests/conftest.py does), not hardcoded here -- so the editor always
shows what's actually in effect right now, defaults or overrides alike.

Two separate target files, matching how the code itself is split:
  - "agent"  -> agent/.env      (agent_config.py + log_config.py settings)
  - "be"     -> BE/.env         (this service's own BE_-prefixed settings)

IMPORTANT: saving here does NOT hot-reload the running agent or BE
process -- both only read their .env file once, at import/startup time
(see agent_config.py's/log_config.py's load_dotenv() calls, and
Settings' env_file). A saved change takes effect on the NEXT restart,
exactly as asked for ("saved in .env that can be loaded when
restart") -- this is a deliberate simplicity choice, not an oversight.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

BE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BE_DIR.parent
AGENT_DIR = PROJECT_ROOT / "agent"
AGENT_ENV_FILE = AGENT_DIR / ".env"
BE_ENV_FILE = BE_DIR / ".env"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


@dataclass(frozen=True)
class Field:
    key: str            # env var name, e.g. "CHAT_TIMEOUT_SECONDS"
    section: str        # form grouping, e.g. "Chat / Ollama"
    label: str          # human-readable label
    type: str           # "str" | "int" | "int_or_none" | "bool" | "list" | "text"
    target: str         # "agent" | "be"
    description: str = ""


FIELDS: list[Field] = [
    # -- Chat / Ollama (agent_config.py) --------------------------------
    Field("WORKSHOP_MODEL", "Chat / Ollama", "Model", "str", "agent",
          "Ollama model tag used for every chat() call."),
    Field("CHAT_TIMEOUT_SECONDS", "Chat / Ollama", "Chat timeout (s)", "int", "agent",
          "A single chat() call must return within this many seconds."),
    Field("CHAT_MAX_RETRIES", "Chat / Ollama", "Chat max retries", "int", "agent",
          "Transient network errors get this many retries."),
    Field("CHAT_RETRY_BACKOFF_SECONDS", "Chat / Ollama", "Retry backoff (s)", "int", "agent",
          "Linear backoff multiplier between retries."),

    # -- Tool loop (shared.py run_agent) --------------------------------
    Field("MAX_ITERATIONS", "Tool loop", "Max iterations", "int", "agent",
          "Hard cap on ReAct rounds per run."),
    Field("MAX_WALL_SECONDS", "Tool loop", "Max wall time (s)", "int", "agent",
          "Hard ceiling on total run time."),
    Field("TOOL_TIMEOUT_SECONDS", "Tool loop", "Tool timeout (s)", "int", "agent",
          "No single tool call may block longer than this."),
    Field("MAX_REPEAT_CALLS", "Tool loop", "Max repeat calls", "int", "agent",
          "Same (tool, args) this many times in a row -> treated as a stuck loop."),
    Field("MAX_OBSERVATION_CHARS", "Tool loop", "Max observation chars", "int", "agent",
          "Cap on what a tool result adds back into the message history."),

    # -- Filesystem / sandbox (fs_tools.py) -----------------------------
    Field("WORKSPACE_DIR", "Filesystem / sandbox", "Workspace dir", "str", "agent",
          "Sandbox root -- fs_tools.BASE_DIR. Everything the agent reads/writes stays inside this."),
    Field("MAX_WRITE_BYTES", "Filesystem / sandbox", "Max write bytes", "int", "agent",
          "Hard cap on a single write_file() call."),
    Field("REQUIRE_CONFIRMATION", "Filesystem / sandbox", "Require confirmation", "bool", "agent",
          "Gate write_file/create_directory behind confirm()."),

    # -- Shell tools (shell_tools.py) ------------------------------------
    Field("SHELL_ALLOWED", "Shell tools", "Allowed programs", "list", "agent",
          "Comma-separated allowlist -- only these programs may be launched at all."),
    Field("SHELL_BLOCKED", "Shell tools", "Blocked patterns", "list", "agent",
          "Comma-separated dangerous substrings -- force-asks even in auto mode."),
    Field("SHELL_TIMEOUT_SECONDS", "Shell tools", "Shell timeout (s)", "int", "agent",
          "A command that hangs is killed after this many seconds."),
    Field("SHELL_MAX_OUTPUT_LINES", "Shell tools", "Max output lines", "int", "agent",
          "stdout/stderr each capped to the last N lines."),

    # -- confirm() --------------------------------------------------------
    Field("CONFIRM_TIMEOUT_SECONDS", "Confirmation gate", "Confirm timeout (s)", "int_or_none", "agent",
          "Deny and move on if unanswered in time. Empty/'none' disables the timeout."),
    Field("CONFIRM_MAX_ACTION_LEN", "Confirmation gate", "Max action text length", "int", "agent",
          "Prompt text longer than this is truncated before display/logging."),

    # -- Auto mode ----------------------------------------------------------
    Field("MAX_AUTO_TOOL_CALLS", "Auto mode", "Max auto tool calls", "int", "agent",
          "Hard cap on total tool calls during one approved auto-mode plan."),

    # -- Memory (memory.py) ------------------------------------------------
    Field("MEMORY_ENABLED", "Memory", "Memory enabled", "bool", "agent",
          "Master switch -- False makes remember_fact/recall_memory no-ops."),
    Field("MEMORY_FILE", "Memory", "Memory file path", "str", "agent",
          "Path to memory.json. Fixed outside WORKSPACE_DIR on purpose."),
    Field("MEMORY_MAX_ENTRIES", "Memory", "Max entries", "int", "agent",
          "Oldest entries are dropped once the file exceeds this many."),
    Field("MEMORY_MAX_TEXT_CHARS", "Memory", "Max text chars per entry", "int", "agent",
          "Per-entry text is truncated to this length before saving."),
    Field("MEMORY_MAX_RECALL_RESULTS", "Memory", "Max recall results", "int", "agent",
          "recall_memory() returns at most this many matches."),
    Field("MEMORY_SUMMARY_MAX_MESSAGES", "Memory", "Summary window (messages)", "int", "agent",
          "save_session_summary() only sends the last N messages to the model."),

    # -- System prompt ------------------------------------------------------
    Field("SYSTEM_PROMPT", "System prompt", "System prompt", "text", "agent",
          "Full prompt seeded as the first message on every run. Empty saves the built-in default."),

    # -- Logging (log_config.py) ---------------------------------------
    Field("LOG_ENABLED", "Logging", "Logging enabled", "bool", "agent",
          "Master switch -- False disables all JSONL logging."),
    Field("LOG_DIR", "Logging", "Log directory", "str", "agent",
          "Folder session logs are written into."),
    Field("LOG_FILE_MODE", "Logging", "Log file mode", "str", "agent",
          "'per_run' (one file per session) or 'single' (one growing file)."),
    Field("SINGLE_LOG_FILENAME", "Logging", "Single-mode filename", "str", "agent",
          "Filename used when LOG_FILE_MODE=single."),
    Field("MAX_FIELD_CHARS", "Logging", "Max field chars", "int_or_none", "agent",
          "Truncate any single logged text field beyond this length. Empty disables truncation."),
    Field("MAX_LOG_FILE_BYTES", "Logging", "Max log file bytes", "int_or_none", "agent",
          "Roll the log file over past this size. Empty disables rotation."),
    Field("LOG_MODEL_TIMING", "Logging", "Log model timing", "bool", "agent",
          "Include Ollama's own performance counters when present."),
    Field("ECHO_TO_TERMINAL", "Logging", "Echo to terminal", "bool", "agent",
          "Print a one-line summary to the terminal for every logged event."),
    Field("MASK_SECRETS", "Logging", "Mask secrets", "bool", "agent",
          "Redact recognizable secret patterns before writing logs to disk."),

    # -- BE server (BE/app/core/config.py) ------------------------------
    Field("BE_HOST", "Backend server", "Host", "str", "be",
          "Interface Uvicorn binds to."),
    Field("BE_PORT", "Backend server", "Port", "int", "be",
          "Port Uvicorn binds to. Must match nginx.conf's upstream if changed."),
    Field("BE_CORS_ORIGINS", "Backend server", "CORS origins", "list", "be",
          "Comma-separated origins allowed to call this API. Empty = no cross-origin access."),
    Field("BE_LOG_LEVEL", "Backend server", "Log level", "str", "be",
          "Reserved for when structured BE logging is added."),
]

_FIELDS_BY_KEY = {f.key: f for f in FIELDS}


def _current_agent_values() -> dict[str, str]:
    """Read the live, currently-in-effect values from agent_config.py /
    log_config.py -- reflects .env + real env vars + built-in defaults,
    whichever actually won, so the editor never shows a stale picture."""
    import agent_config as ac
    import log_config as lc

    def render(value) -> str:
        if isinstance(value, (set, frozenset)):
            return ",".join(sorted(value))
        if isinstance(value, list):
            return ",".join(value)
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return {
        "WORKSHOP_MODEL": render(ac.DEFAULT_MODEL),
        "CHAT_TIMEOUT_SECONDS": render(ac.CHAT_TIMEOUT_SECONDS),
        "CHAT_MAX_RETRIES": render(ac.CHAT_MAX_RETRIES),
        "CHAT_RETRY_BACKOFF_SECONDS": render(ac.CHAT_RETRY_BACKOFF_SECONDS),
        "MAX_ITERATIONS": render(ac.MAX_ITERATIONS),
        "MAX_WALL_SECONDS": render(ac.MAX_WALL_SECONDS),
        "TOOL_TIMEOUT_SECONDS": render(ac.TOOL_TIMEOUT_SECONDS),
        "MAX_REPEAT_CALLS": render(ac.MAX_REPEAT_CALLS),
        "MAX_OBSERVATION_CHARS": render(ac.MAX_OBSERVATION_CHARS),
        "WORKSPACE_DIR": render(str(ac.WORKSPACE_DIR)),
        "MAX_WRITE_BYTES": render(ac.MAX_WRITE_BYTES),
        "REQUIRE_CONFIRMATION": render(ac.REQUIRE_CONFIRMATION),
        "SHELL_ALLOWED": render(ac.SHELL_ALLOWED),
        "SHELL_BLOCKED": render(ac.SHELL_BLOCKED),
        "SHELL_TIMEOUT_SECONDS": render(ac.SHELL_TIMEOUT_SECONDS),
        "SHELL_MAX_OUTPUT_LINES": render(ac.SHELL_MAX_OUTPUT_LINES),
        "CONFIRM_TIMEOUT_SECONDS": render(ac.CONFIRM_TIMEOUT_SECONDS),
        "CONFIRM_MAX_ACTION_LEN": render(ac.CONFIRM_MAX_ACTION_LEN),
        "MAX_AUTO_TOOL_CALLS": render(ac.MAX_AUTO_TOOL_CALLS),
        "MEMORY_ENABLED": render(ac.MEMORY_ENABLED),
        "MEMORY_FILE": render(str(ac.MEMORY_FILE)),
        "MEMORY_MAX_ENTRIES": render(ac.MEMORY_MAX_ENTRIES),
        "MEMORY_MAX_TEXT_CHARS": render(ac.MEMORY_MAX_TEXT_CHARS),
        "MEMORY_MAX_RECALL_RESULTS": render(ac.MEMORY_MAX_RECALL_RESULTS),
        "MEMORY_SUMMARY_MAX_MESSAGES": render(ac.MEMORY_SUMMARY_MAX_MESSAGES),
        "SYSTEM_PROMPT": render(ac.SYSTEM_PROMPT),
        "LOG_ENABLED": render(lc.LOG_ENABLED),
        "LOG_DIR": render(str(lc.LOG_DIR)),
        "LOG_FILE_MODE": render(lc.LOG_FILE_MODE),
        "SINGLE_LOG_FILENAME": render(lc.SINGLE_LOG_FILENAME),
        "MAX_FIELD_CHARS": render(lc.MAX_FIELD_CHARS),
        "MAX_LOG_FILE_BYTES": render(lc.MAX_LOG_FILE_BYTES),
        "LOG_MODEL_TIMING": render(lc.LOG_MODEL_TIMING),
        "ECHO_TO_TERMINAL": render(lc.ECHO_TO_TERMINAL),
        "MASK_SECRETS": render(lc.MASK_SECRETS),
    }


def _current_be_values() -> dict[str, str]:
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "BE_HOST": settings.host,
        "BE_PORT": str(settings.port),
        "BE_CORS_ORIGINS": settings.cors_origins,
        "BE_LOG_LEVEL": settings.log_level,
    }


def current_values() -> dict[str, str]:
    """All fields' current effective values, keyed by env var name."""
    values = {}
    values.update(_current_agent_values())
    values.update(_current_be_values())
    return values


def get_form_schema() -> list[dict]:
    """Field metadata + current value, ready to serialize as JSON for
    the /config page's form."""
    values = current_values()
    return [
        {
            "key": f.key,
            "section": f.section,
            "label": f.label,
            "type": f.type,
            "description": f.description,
            "value": values.get(f.key, ""),
        }
        for f in FIELDS
    ]


def _quote_env_value(value: str) -> str:
    """Double-quote a .env value, escaping backslashes/quotes/newlines
    so python-dotenv round-trips it exactly (including SYSTEM_PROMPT's
    embedded newlines) on the next load_dotenv() call."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _write_env_file(path: Path, updates: dict[str, str]) -> None:
    """Merge `updates` into the KEY=value lines of `path`, preserving
    every other existing line (comments, blank lines, unrelated keys)
    untouched. New keys not already present are appended at the end.
    """
    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()

    remaining = dict(updates)
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                new_lines.append(f"{key}={_quote_env_value(remaining.pop(key))}")
                continue
        new_lines.append(line)

    if remaining:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        for key, value in remaining.items():
            new_lines.append(f"{key}={_quote_env_value(value)}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def save_values(values: dict[str, str]) -> dict[str, list[str]]:
    """Split `values` (env var name -> new string value) by target file
    and write each. Unknown keys are silently ignored (defense against
    a stale/malicious client payload). Returns which keys were written
    to each file, for the API response.
    """
    agent_updates: dict[str, str] = {}
    be_updates: dict[str, str] = {}

    for key, value in values.items():
        field_def = _FIELDS_BY_KEY.get(key)
        if field_def is None:
            continue
        target = agent_updates if field_def.target == "agent" else be_updates
        target[key] = value

    if agent_updates:
        _write_env_file(AGENT_ENV_FILE, agent_updates)
    if be_updates:
        _write_env_file(BE_ENV_FILE, be_updates)

    return {
        "agent": sorted(agent_updates.keys()),
        "be": sorted(be_updates.keys()),
    }
