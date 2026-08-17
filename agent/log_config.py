"""Logging configuration for the agents in this folder.

Edit this file to change what gets logged and where -- nothing else in
chat_logger.py or file_agent.py needs to change. All settings are plain
module-level constants, each overridable by an environment variable of
the same name (this was previously just a comment claim -- now actually
implemented below).
"""

import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean from an env var ('1'/'true'/'yes' -> True), else default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int_or_none(name: str, default):
    """Read an int from an env var, or the literal string 'none' -> None."""
    raw = os.getenv(name)
    if raw is None:
        return default
    if raw.strip().lower() == "none":
        return None
    return int(raw)


# Master switch. Set False to disable logging entirely with zero overhead
# (a no-op logger is used instead, so no file I/O happens at all).
LOG_ENABLED = _env_bool("LOG_ENABLED", True)

# This file lives in agent/, one level under the project root -- fixed
# there so LOG_DIR no longer depends on the process's working directory
# at launch (same reasoning as agent_config.WORKSPACE_DIR/MEMORY_FILE).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Folder logs are written into. Fixed at <project_root>/logs by default.
LOG_DIR = Path(os.getenv("LOG_DIR", str(_PROJECT_ROOT / "logs")))

# "per_run"  -> one new file per session, named chat_YYYYmmdd_HHMMSS.jsonl
# "single"   -> everything appends to one file, chat.jsonl (subject to
#               rotation once MAX_LOG_FILE_BYTES is exceeded -- see below)
LOG_FILE_MODE = os.getenv("LOG_FILE_MODE", "per_run")
SINGLE_LOG_FILENAME = os.getenv("SINGLE_LOG_FILENAME", "chat.jsonl")

# Format: one JSON object per line (JSONL). Easiest to tail, grep, and
# stream while a chat is still running -- a single giant JSON array can't
# be read until the file is closed, JSONL can be read line by line live.
LOG_FORMAT = "jsonl"

# Truncate any single logged text field (file content, model output, tool
# arguments) beyond this many characters, to keep log files from growing
# out of control on large file writes. None disables truncation -- useful
# for a deep-dive debug session, but be aware it removes the size safety
# net entirely.
MAX_FIELD_CHARS = _env_int_or_none("MAX_FIELD_CHARS", 4000)

# Roll the current log file over to a numbered backup once it exceeds
# this many bytes, so a long-running "single" mode session (or an
# unexpectedly chatty per_run session) can't grow without bound and
# eventually fill the disk. None disables rotation.
MAX_LOG_FILE_BYTES = _env_int_or_none("MAX_LOG_FILE_BYTES", 10_000_000)  # 10 MB

# Include Ollama's own performance counters when present on the response
# (eval_count, prompt_eval_count, total_duration, load_duration, etc).
# These are extremely useful for debugging latency / slow responses.
LOG_MODEL_TIMING = _env_bool("LOG_MODEL_TIMING", True)

# Print a one-line summary to the terminal every time an event is logged
# (in addition to writing it to the file). Handy while developing; turn
# off for a quieter terminal once things are working.
ECHO_TO_TERMINAL = _env_bool("ECHO_TO_TERMINAL", False)

# SEC-03: mask common secret patterns (API keys, tokens, private keys)
# in every logged field before it's written to disk. Tool arguments and
# model output previously went to JSONL logs unmodified -- if the agent
# read a .env file or printed a token as part of its reasoning, that
# secret landed in plaintext in the log file. Off switch exists for a
# deep-dive debug session where you need the raw, unmasked text.
MASK_SECRETS = _env_bool("MASK_SECRETS", True)
