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

import json
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
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
    Field("CHAT_STREAM_IDLE_TIMEOUT_SECONDS", "Chat / Ollama", "Stream idle timeout (s)", "int", "agent",
          "chat_stream() fails if no chunk arrives within this many seconds (a stall, not a total-duration cap)."),

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
          "Sandbox root -- fs_tools.BASE_DIR. Everything the agent reads/writes stays inside this. "
          "Leave unset to auto-resolve per-OS -- an absolute path saved from one OS (e.g. WSL's "
          "/mnt/c/...) won't resolve on another (e.g. native Windows' C:\\...) sharing this same file."),
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
          "Path to memory.json. Fixed outside WORKSPACE_DIR on purpose. "
          "Leave unset to auto-resolve per-OS -- see Workspace dir's note above."),
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
          "Folder session logs are written into. "
          "Leave unset to auto-resolve per-OS -- see Workspace dir's note above."),
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
    Field("BE_AUTO_APPROVE_SECONDS", "Chat page", "Auto-approve timeout (s)", "int", "be",
          "Seconds the chat page's Auto-approve checkbox waits with no click before approving a pending confirm() request."),
]

_FIELDS_BY_KEY = {f.key: f for f in FIELDS}


def _render(value) -> str:
    """Render any agent_config.py/log_config.py value type as the plain
    string an .env file (and this form) uses."""
    if isinstance(value, (set, frozenset)):
        return ",".join(sorted(value))
    if isinstance(value, list):
        return ",".join(value)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _snapshot(ac, lc) -> dict[str, str]:
    """Pull every agent-target field's value out of already-imported
    agent_config/log_config modules. ONE mapping, reused for two very
    different purposes:
      - _current_agent_values() below feeds it the REAL, already-loaded
        modules -- .env + env vars + built-ins, whichever won.
      - agent_defaults() feeds it modules imported in a clean subprocess
        with .env loading neutralized and relevant env vars stripped --
        the TRUE built-in defaults, straight from the source, with zero
        hand-maintained duplicate list to fall out of sync when
        agent_config.py/log_config.py change (see agent_defaults()).
    """
    return {
        "WORKSHOP_MODEL": _render(ac.DEFAULT_MODEL),
        "CHAT_TIMEOUT_SECONDS": _render(ac.CHAT_TIMEOUT_SECONDS),
        "CHAT_MAX_RETRIES": _render(ac.CHAT_MAX_RETRIES),
        "CHAT_RETRY_BACKOFF_SECONDS": _render(ac.CHAT_RETRY_BACKOFF_SECONDS),
        "CHAT_STREAM_IDLE_TIMEOUT_SECONDS": _render(ac.CHAT_STREAM_IDLE_TIMEOUT_SECONDS),
        "MAX_ITERATIONS": _render(ac.MAX_ITERATIONS),
        "MAX_WALL_SECONDS": _render(ac.MAX_WALL_SECONDS),
        "TOOL_TIMEOUT_SECONDS": _render(ac.TOOL_TIMEOUT_SECONDS),
        "MAX_REPEAT_CALLS": _render(ac.MAX_REPEAT_CALLS),
        "MAX_OBSERVATION_CHARS": _render(ac.MAX_OBSERVATION_CHARS),
        "WORKSPACE_DIR": _render(str(ac.WORKSPACE_DIR)),
        "MAX_WRITE_BYTES": _render(ac.MAX_WRITE_BYTES),
        "REQUIRE_CONFIRMATION": _render(ac.REQUIRE_CONFIRMATION),
        "SHELL_ALLOWED": _render(ac.SHELL_ALLOWED),
        "SHELL_BLOCKED": _render(ac.SHELL_BLOCKED),
        "SHELL_TIMEOUT_SECONDS": _render(ac.SHELL_TIMEOUT_SECONDS),
        "SHELL_MAX_OUTPUT_LINES": _render(ac.SHELL_MAX_OUTPUT_LINES),
        "CONFIRM_TIMEOUT_SECONDS": _render(ac.CONFIRM_TIMEOUT_SECONDS),
        "CONFIRM_MAX_ACTION_LEN": _render(ac.CONFIRM_MAX_ACTION_LEN),
        "MAX_AUTO_TOOL_CALLS": _render(ac.MAX_AUTO_TOOL_CALLS),
        "MEMORY_ENABLED": _render(ac.MEMORY_ENABLED),
        "MEMORY_FILE": _render(str(ac.MEMORY_FILE)),
        "MEMORY_MAX_ENTRIES": _render(ac.MEMORY_MAX_ENTRIES),
        "MEMORY_MAX_TEXT_CHARS": _render(ac.MEMORY_MAX_TEXT_CHARS),
        "MEMORY_MAX_RECALL_RESULTS": _render(ac.MEMORY_MAX_RECALL_RESULTS),
        "MEMORY_SUMMARY_MAX_MESSAGES": _render(ac.MEMORY_SUMMARY_MAX_MESSAGES),
        "SYSTEM_PROMPT": _render(ac.SYSTEM_PROMPT),
        "LOG_ENABLED": _render(lc.LOG_ENABLED),
        "LOG_DIR": _render(str(lc.LOG_DIR)),
        "LOG_FILE_MODE": _render(lc.LOG_FILE_MODE),
        "SINGLE_LOG_FILENAME": _render(lc.SINGLE_LOG_FILENAME),
        "MAX_FIELD_CHARS": _render(lc.MAX_FIELD_CHARS),
        "MAX_LOG_FILE_BYTES": _render(lc.MAX_LOG_FILE_BYTES),
        "LOG_MODEL_TIMING": _render(lc.LOG_MODEL_TIMING),
        "ECHO_TO_TERMINAL": _render(lc.ECHO_TO_TERMINAL),
        "MASK_SECRETS": _render(lc.MASK_SECRETS),
    }


def _current_agent_values() -> dict[str, str]:
    """Read the live, currently-in-effect values from agent_config.py /
    log_config.py -- reflects .env + real env vars + built-in defaults,
    whichever actually won, so the editor never shows a stale picture."""
    import agent_config as ac
    import log_config as lc

    return _snapshot(ac, lc)


_DEFAULTS_SNAPSHOT_SCRIPT = """
import json, sys
sys.path.insert(0, {agent_dir!r})
sys.path.insert(0, {be_dir!r})
import dotenv
dotenv.load_dotenv = lambda *a, **k: False  # neutralize -- want pure code defaults, not agent/.env
import agent_config as ac
import log_config as lc
from app.core.config_schema import _snapshot
print(json.dumps(_snapshot(ac, lc)))
"""


@lru_cache
def agent_defaults() -> dict[str, str]:
    """The TRUE built-in defaults for every agent-target field, computed
    by importing agent_config.py/log_config.py fresh in an isolated
    subprocess -- .env loading neutralized, and every relevant env var
    stripped from that subprocess's environment first, so neither an
    exported env var nor agent/.env can leak into the result.

    Deliberately NOT a hand-maintained duplicate list: whatever
    agent_config.py/log_config.py's literal defaults are, THIS is what
    shows up next to each field in the editor -- automatically, even if
    those files change later. Cached for this BE process's lifetime
    (defaults don't change while it's running); restart the BE service
    to pick up a code change to the defaults themselves.
    """
    import os as _os

    agent_keys = {f.key for f in FIELDS if f.target == "agent"}
    clean_env = {k: v for k, v in _os.environ.items() if k not in agent_keys}

    script = _DEFAULTS_SNAPSHOT_SCRIPT.format(agent_dir=str(AGENT_DIR), be_dir=str(BE_DIR))
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=15, env=clean_env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:])
        return json.loads(result.stdout)
    except Exception:
        # Defaults are a "nice to have" hint in the UI -- never let a
        # failure to compute them break the editor itself.
        return {}


def _current_be_values() -> dict[str, str]:
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "BE_HOST": settings.host,
        "BE_PORT": str(settings.port),
        "BE_CORS_ORIGINS": settings.cors_origins,
        "BE_LOG_LEVEL": settings.log_level,
        "BE_AUTO_APPROVE_SECONDS": str(settings.auto_approve_seconds),
    }


def be_defaults() -> dict[str, str]:
    """The BE_* fields' built-in defaults. No subprocess needed here --
    unlike the agent side, pydantic-settings already keeps a field's
    declared default separate from whatever env_file/env var overrode
    it, so this just reads Settings' own field metadata directly."""
    from app.core.config import Settings

    fields = Settings.model_fields
    return {
        "BE_HOST": str(fields["host"].default),
        "BE_PORT": str(fields["port"].default),
        "BE_CORS_ORIGINS": str(fields["cors_origins"].default),
        "BE_LOG_LEVEL": str(fields["log_level"].default),
        "BE_AUTO_APPROVE_SECONDS": str(fields["auto_approve_seconds"].default),
    }


def current_values() -> dict[str, str]:
    """All fields' current effective values, keyed by env var name."""
    values = {}
    values.update(_current_agent_values())
    values.update(_current_be_values())
    return values


def default_values() -> dict[str, str]:
    """All fields' built-in default values, keyed by env var name --
    what the field would be if no .env/env var override existed."""
    values = {}
    values.update(agent_defaults())
    values.update(be_defaults())
    return values


def get_form_schema() -> list[dict]:
    """Field metadata + current value + built-in default, ready to
    serialize as JSON for the /config page's form. `default` is shown
    beside each field as a recommendation -- what you'd get by leaving
    it unset."""
    values = current_values()
    defaults = default_values()
    return [
        {
            "key": f.key,
            "section": f.section,
            "label": f.label,
            "type": f.type,
            "description": f.description,
            "value": values.get(f.key, ""),
            "default": defaults.get(f.key, ""),
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
