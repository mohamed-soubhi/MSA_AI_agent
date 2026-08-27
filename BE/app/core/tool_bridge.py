"""Exposes the exact same tools CLI_agent.py wires up -- both this
module and CLI_agent.py now get their list from agent/tools_registry.py
(get_active_tools()), so BE's tool set can never silently drift from
the CLI's.

Use get_active_tools() for the CONFIG-AWARE set: the base 9, plus
web_search / web_fetch when WEB_TOOLS_ENABLED. chat.py calls it per
turn so the config-editor toggle applies with no restart. The
module-level TOOLS / TOOL_MAP below are an import-time snapshot of the
BASE set only -- kept for callers/tests that just need the fixed nine.
"""

import sys
from pathlib import Path

BE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = BE_DIR.parent / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from fs_tools import BASE_DIR  # noqa: E402,F401  (re-exported; config_reload refreshes it)
from tools_registry import BASE_TOOLS, get_active_tools  # noqa: E402,F401

TOOLS = list(BASE_TOOLS)
TOOL_MAP = {fn.__name__: fn for fn in BASE_TOOLS}
