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

import logging
import os
from pathlib import Path

logger = logging.getLogger("agent.config")

# SANDBOX FIX: this file lives in agent/, one level under the project
# root. PROJECT_ROOT is computed from THIS file's own location, not
# from the process's current working directory -- so the sandbox
# boundary below no longer depends on which directory you happened to
# launch the agent from (previously fs_tools.BASE_DIR = Path.cwd(),
# which meant running from the project root let the agent read/write
# its OWN source files, exactly the bug this fixes).
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean from an env var ('1'/'true'/'yes'/'on' -> True)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Read a plain int from an env var, or fall back to default.

    ROB-05: a non-numeric value logs a warning and falls back to
    `default` instead of raising -- a typo'd env var degrades the one
    affected setting to its documented default rather than crashing
    agent startup before a single tool call has run. (Deliberately
    scoped to this helper only -- _env_int_or_none's "raise on garbage"
    behavior for its literal-'none' handling is untouched.)
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("env_int_invalid name=%s raw=%r default=%s", name, raw, default)
        return default


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
# WORKSPACE_DIR is the sandbox root -- fs_tools.BASE_DIR and
# shell_tools.run_command's cwd both point here, and NOTHING outside it
# is ever reachable through resolve_path(). Fixed at <project_root>/
# workspace/ by default: a dedicated folder for whatever the agent
# builds, sitting NEXT TO agent/ (this code) rather than mixed into it.
# Override via WORKSPACE_DIR env var for a different sandbox location
# entirely.
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", str(PROJECT_ROOT / "workspace")))

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

# --------------------------------------------------------------------------
# Memory (memory.py)
# --------------------------------------------------------------------------
MEMORY_ENABLED = _env_bool("MEMORY_ENABLED", True)
# Fixed at <project_root>/memory.json by default -- deliberately OUTSIDE
# WORKSPACE_DIR, so the agent's own persistent memory can never be
# read/written through its own sandboxed fs_tools (write_file etc. can
# only ever reach inside WORKSPACE_DIR). Also no longer cwd-relative --
# same reasoning as WORKSPACE_DIR above.
MEMORY_FILE = os.getenv("MEMORY_FILE", str(PROJECT_ROOT / "memory.json"))
MEMORY_MAX_ENTRIES = _env_int("MEMORY_MAX_ENTRIES", 500)        # oldest entries drop past this
MEMORY_MAX_TEXT_CHARS = _env_int("MEMORY_MAX_TEXT_CHARS", 1000)  # per-entry text cap
MEMORY_MAX_RECALL_RESULTS = _env_int("MEMORY_MAX_RECALL_RESULTS", 10)  # cap on recall_memory() output
# ROB-04: save_session_summary() sends this many of the MOST RECENT
# messages to the model, not the full unbounded conversation history --
# a long multi-turn session could otherwise overflow the model's
# context window on the one call that happens automatically, with no
# human in the loop to notice or intervene.
MEMORY_SUMMARY_MAX_MESSAGES = _env_int("MEMORY_SUMMARY_MAX_MESSAGES", 40)

# --------------------------------------------------------------------------
# System prompt (CLI_agent.py)
# --------------------------------------------------------------------------
# PROMPT-LEVEL GUIDANCE — quality, not safety (pattern vs guarantee). The
# prompt ASKS for good behavior; the sandbox/allowlist/blocklist/confirm/
# timeout layers in fs_tools.py and shell_tools.py GUARANTEE the boundary.
# The non-interactive rule matters most: an interactive command ("npm
# create", a pip confirm) doesn't error here — it just hangs until the
# timeout kills it. And "--yes/--force" flags are only safe to suggest
# because the human still approves every command's exact text before it
# runs. Overridable wholesale via the SYSTEM_PROMPT env var if you need a
# different persona/ruleset without touching code.
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", """
You are an AI software engineering assistant.

You have access to tools for listing, reading, and writing files,
creating directories, running terminal commands, and asking the human
for clarification or a choice when something is ambiguous.

Rules:
- Always prefer non-interactive terminal commands.
- Never run commands that wait for user input.
- If a command has a non-interactive flag (such as --yes, --template, --force), use it.
- Before running a command, think about whether it could block.
- If a command fails, inspect the error and fix the problem.
- If a request is ambiguous, use ask_human or ask_human_choice instead of guessing.
- Keep changes as small as possible.
- Do not call run_command unless it is necessary.
- Do not invent tool results.
- At the start of a task, consider calling recall_memory to check for
  relevant facts from past sessions.
- Call remember_fact when you learn something durable worth keeping for
  future sessions (a user preference, a decision made, a fact about the
  project) -- not for throwaway details.
""")
