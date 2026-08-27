"""Hot-reload agent_config.py / log_config.py after the config editor
saves agent/.env, without restarting the process.

Why this needs its own module instead of "just re-run load_dotenv()":
almost every consumer did `from agent_config import X` at its own
import time -- e.g. shell_tools.py's `from agent_config import
SHELL_ALLOWED as ALLOWED`. That copies the *value* into shell_tools'
own namespace once; reassigning agent_config.SHELL_ALLOWED later never
touches that copy, because `from X import Y` doesn't keep a live link
back to X. `importlib.reload(agent_config)` alone would recompute
agent_config's own attributes fine, but every already-imported
consumer module would still be holding its stale copy.

The fix: reload agent_config/log_config in place, then explicitly push
each recomputed value into every module that copied it by name, via
setattr() on the module object looked up through sys.modules (not a
fresh import -- this only touches modules that happen to already be
loaded in this process, so it works the same whether called from the
CLI agent or the BE service, and never triggers import-order issues
with agent_config.py itself, which nearly everything else imports).

Modules that instead did `import agent_config` (whole-module
reference, e.g. config_schema.py's `import agent_config as ac`) or
read values through another module's live attribute (chat_logger.py's
`cfg.LOG_DIR`, where `cfg` is `log_config` itself) need no propagation
at all -- `importlib.reload()` repopulates the SAME module object in
place, so `ac.SOME_SETTING` / `cfg.SOME_SETTING` reflect the new value
automatically the next time they're read.
"""

import importlib
import sys
from pathlib import Path

from dotenv import load_dotenv

_AGENT_DIR = Path(__file__).resolve().parent

# Every module that copied an agent_config name into its own namespace
# via `from agent_config import X` (same name on both sides).
_PROPAGATE = {
    "auto_runner": ["MAX_AUTO_TOOL_CALLS", "SYSTEM_PROMPT"],
    "CLI_agent": ["SYSTEM_PROMPT"],
    "confirm": ["CONFIRM_TIMEOUT_SECONDS", "CONFIRM_MAX_ACTION_LEN"],
    "fs_tools": ["MAX_WRITE_BYTES", "REQUIRE_CONFIRMATION", "WORKSPACE_DIR"],
    "memory": [
        "MEMORY_ENABLED", "MEMORY_FILE", "MEMORY_MAX_ENTRIES",
        "MEMORY_MAX_TEXT_CHARS", "MEMORY_MAX_RECALL_RESULTS",
        "MEMORY_SUMMARY_MAX_MESSAGES",
    ],
    "shared": [
        "DEFAULT_MODEL", "CHAT_TIMEOUT_SECONDS", "CHAT_MAX_RETRIES",
        "CHAT_RETRY_BACKOFF_SECONDS", "CHAT_STREAM_IDLE_TIMEOUT_SECONDS",
        "MAX_ITERATIONS", "MAX_WALL_SECONDS", "TOOL_TIMEOUT_SECONDS",
        "MAX_REPEAT_CALLS", "MAX_OBSERVATION_CHARS", "CONFIRM_TIMEOUT_SECONDS",
    ],
}

# Same idea, but the consumer renamed the value on import
# (`from agent_config import SHELL_ALLOWED as ALLOWED`).
_PROPAGATE_ALIASED = {
    "shell_tools": {
        "ALLOWED": "SHELL_ALLOWED",
        "BLOCKED": "SHELL_BLOCKED",
        "TIMEOUT_SECONDS": "SHELL_TIMEOUT_SECONDS",
        "MAX_OUTPUT_LINES": "SHELL_MAX_OUTPUT_LINES",
    },
}

# BE-side modules that also copied an agent_config name by value.
_PROPAGATE_BE = {
    "app.api.memory": ["MEMORY_FILE"],
    "app.core.approval_bridge": ["CONFIRM_TIMEOUT_SECONDS"],
}
_PROPAGATE_BE_ALIASED = {
    "app.core.agent_bridge": {"CHAT_SYSTEM_PROMPT": "SYSTEM_PROMPT"},
    # chat.py copied agent_bridge.CHAT_SYSTEM_PROMPT again at ITS OWN
    # import time (`from app.core.agent_bridge import CHAT_SYSTEM_PROMPT`)
    # -- a second by-value copy, one level removed from agent_config.
    # Without this, Save updates agent_bridge's copy correctly but
    # reset_chat()/_messages' seed (both read chat.py's own stale name)
    # keep using whatever prompt was in effect when chat.py first loaded.
    "app.api.chat": {"CHAT_SYSTEM_PROMPT": "SYSTEM_PROMPT"},
}


def reload_all() -> None:
    """Re-read agent/.env and push every setting live into every
    already-imported module that reads it -- called once by BE's
    POST /api/config right after it writes agent/.env, so Save takes
    effect immediately instead of requiring a restart."""
    # override=True: Save just rewrote the file, so its contents are
    # authoritative from this point on -- including over a value this
    # same process already loaded into os.environ on startup or a
    # previous reload (agent_config.py's own load_dotenv() call stays
    # override=False, since THAT one only governs first-startup
    # precedence against a genuinely pre-exported shell env var).
    load_dotenv(_AGENT_DIR / ".env", override=True)

    import agent_config
    import log_config

    importlib.reload(agent_config)
    importlib.reload(log_config)

    for mod_name, names in _PROPAGATE.items():
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        for name in names:
            setattr(mod, name, getattr(agent_config, name))

    for mod_name, alias_map in _PROPAGATE_ALIASED.items():
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        for local_name, source_name in alias_map.items():
            setattr(mod, local_name, getattr(agent_config, source_name))

    for mod_name, names in _PROPAGATE_BE.items():
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        for name in names:
            setattr(mod, name, getattr(agent_config, name))

    for mod_name, alias_map in _PROPAGATE_BE_ALIASED.items():
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        for local_name, source_name in alias_map.items():
            setattr(mod, local_name, getattr(agent_config, source_name))

    # Derived values: recomputed from a source above, not read from
    # agent_config directly, so they need their own refresh.
    fs_tools = sys.modules.get("fs_tools")
    if fs_tools is not None:
        fs_tools.BASE_DIR = agent_config.WORKSPACE_DIR.resolve()

    shell_tools = sys.modules.get("shell_tools")
    if shell_tools is not None and fs_tools is not None:
        shell_tools.BASE_DIR = fs_tools.BASE_DIR

    tool_bridge = sys.modules.get("app.core.tool_bridge")
    if tool_bridge is not None and fs_tools is not None:
        tool_bridge.BASE_DIR = fs_tools.BASE_DIR

    memory = sys.modules.get("memory")
    if memory is not None:
        memory.MEMORY_PATH = Path(agent_config.MEMORY_FILE)

    # OllamaAgent's model is an instance attribute set once at
    # construction (self.model = model), not a module-level name --
    # reassigning shared.DEFAULT_MODEL doesn't reach an already-built
    # instance. Drop the BE's cached singleton so the next chat request
    # builds a fresh one with the new model; nothing conversation-
    # related lives on it (messages are stored separately in chat.py).
    agent_bridge = sys.modules.get("app.core.agent_bridge")
    if agent_bridge is not None and getattr(agent_bridge, "_agent", None) is not None:
        agent_bridge._agent = None
