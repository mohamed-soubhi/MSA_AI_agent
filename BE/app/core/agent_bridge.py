"""Bridges the BE chat API to the agent's own OllamaAgent -- reused
here so the web chat talks to the EXACT same hardened chat wrapper
(timeout/retry/friendly-errors, see shared.py) the CLI agent uses, not
a second reimplementation that could drift out of sync.

Tool-calling IS wired in (see tool_bridge.py + approval_bridge.py) --
run_agent() drives the same 9 tools CLI_agent.py does, with
confirm()/ask_human()/ask_human_choice() rerouted from a blocking
terminal input() to an HTTP approve/deny round-trip
(POST /api/chat/respond) instead. CHAT_SYSTEM_PROMPT is therefore the
SAME SYSTEM_PROMPT the CLI agent seeds every session with, not a
separate "no tools here" placeholder -- the chat page has the same
capabilities now, just approved over HTTP instead of a terminal.
"""

import sys
import threading
from pathlib import Path

BE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = BE_DIR.parent / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from shared import OllamaAgent  # noqa: E402
from agent_config import SYSTEM_PROMPT as CHAT_SYSTEM_PROMPT  # noqa: E402

_agent_lock = threading.Lock()
_agent: OllamaAgent | None = None


def get_agent() -> OllamaAgent:
    """One OllamaAgent instance, shared across every chat request in
    this process -- same reasoning as CLI_agent.py creating exactly one
    per session (keeps OllamaAgent.chat_stream()'s retry/timeout state
    and the underlying ollama.Client connection reused, not
    reconnected every message)."""
    global _agent
    with _agent_lock:
        if _agent is None:
            _agent = OllamaAgent()
        return _agent
