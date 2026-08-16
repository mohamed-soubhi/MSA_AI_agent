"""Central configuration for the agent — every "how long / how many /
what's allowed" knob, in one place, each overridable by an environment
variable of the same name. This mirrors the pattern log_config.py
already established for logging; this file covers everything else
(chat/network, the tool loop, filesystem limits, shell allow/block
lists, confirm() behavior, auto mode).

Nothing in shared.py, fs_tools.py, shell_tools.py, confirm.py, or
auto_runner.py hardcodes these values anymore — change a number here
(or export the matching env var before running) and it takes effect
everywhere that setting is used, without touching any of those files.
log_config.py stays separate on purpose: it's a distinct concern
(logging) that already had its own file before this one existed.
"""

import os


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean from an env var ('1'/'true'/'yes'/'on' -> True)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Read a plain int from an env var, or fall back to default."""
    raw = os.getenv(name)
    return int(raw) if raw is not None else default


def _env_int_or_none(name: str, default):
    """Read an int from an env var, or the literal string 'none' -> None."""
    raw = os.getenv(name)
    if raw is None:
        return default
    if raw.strip().lower() == "none":
        return None
    return int(raw)


def _env_set(name: str, default: set) -> set:
    """Read a comma-separated set from an env var, e.g. 'python,node,ls'."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return {item.strip() for item in raw.split(",") if item.strip()}


def _env_list(name: str, default: list) -> list:
    """Read a comma-separated list from an env var, order preserved."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------
# Ollama / chat (shared.py — OllamaAgent)
# --------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("WORKSHOP_MODEL", "glm-5.2:cloud")
CHAT_TIMEOUT_SECONDS = _env_int("CHAT_TIMEOUT_SECONDS", 60)
CHAT_MAX_RETRIES = _env_int("CHAT_MAX_RETRIES", 2)
CHAT_RETRY_BACKOFF_SECONDS = _env_int("CHAT_RETRY_BACKOFF_SECONDS", 2)

# --------------------------------------------------------------------------
# Agent tool loop (shared.py — run_agent)
# --------------------------------------------------------------------------
MAX_ITERATIONS = _env_int("MAX_ITERATIONS", 40)               # safety: never loop forever (rounds)
MAX_WALL_SECONDS = _env_int("MAX_WALL_SECONDS", 600)           # safety: hard ceiling on total run time
TOOL_TIMEOUT_SECONDS = _env_int("TOOL_TIMEOUT_SECONDS", 30)    # safety: no single tool call blocks forever
MAX_REPEAT_CALLS = _env_int("MAX_REPEAT_CALLS", 3)             # same (tool, args) this many times -> stuck
MAX_OBSERVATION_CHARS = _env_int("MAX_OBSERVATION_CHARS", 4000)  # cap what a tool result adds to context

# --------------------------------------------------------------------------
# Filesystem tools (fs_tools.py)
# --------------------------------------------------------------------------
MAX_WRITE_BYTES = _env_int("MAX_WRITE_BYTES", 2_000_000)       # 2 MB per write_file() call
REQUIRE_CONFIRMATION = _env_bool("REQUIRE_CONFIRMATION", True)  # gate write_file/create_directory

# --------------------------------------------------------------------------
# Shell tools (shell_tools.py)
# --------------------------------------------------------------------------
SHELL_ALLOWED = _env_set(
    "SHELL_ALLOWED",
    {"python", "python3", "ls", "cat", "echo", "pip", "pytest", "node", "npm", "mkdir", "cd"},
)
SHELL_BLOCKED = _env_list(
    "SHELL_BLOCKED",
    ["rm ", "rm-", "sudo", "mkfs", "dd ", ":(){", "> /dev", "curl ", "wget ", "chmod ", "mv /"],
)
SHELL_TIMEOUT_SECONDS = _env_int("SHELL_TIMEOUT_SECONDS", 120)
SHELL_MAX_OUTPUT_LINES = _env_int("SHELL_MAX_OUTPUT_LINES", 50)

# --------------------------------------------------------------------------
# confirm() (confirm.py)
# --------------------------------------------------------------------------
CONFIRM_TIMEOUT_SECONDS = _env_int_or_none("CONFIRM_TIMEOUT_SECONDS", 120)
CONFIRM_MAX_ACTION_LEN = _env_int("CONFIRM_MAX_ACTION_LEN", 400)

# --------------------------------------------------------------------------
# Auto mode (auto_runner.py)
# --------------------------------------------------------------------------
MAX_AUTO_TOOL_CALLS = _env_int("MAX_AUTO_TOOL_CALLS", 30)
