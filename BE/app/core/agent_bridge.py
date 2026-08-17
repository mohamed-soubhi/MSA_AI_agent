"""Bridges the BE chat API to the agent's own OllamaAgent -- reused
here so the web chat talks to the EXACT same hardened chat wrapper
(timeout/retry/friendly-errors, see shared.py) the CLI agent uses, not
a second reimplementation that could drift out of sync.

Deliberately NO tool-calling wired in yet: shared.run_agent() (the
tool-calling loop) drives fs_tools/shell_tools through confirm(), which
blocks on a real terminal input() -- that has no meaning inside an
HTTP request/response cycle. This bridge only uses OllamaAgent.chat_stream(),
which never touches tools or confirm() at all, so the chat page works
today without needing to solve "how does a human approve a tool call
over HTTP" first. That's a real, separate design question for later.
"""

import sys
import threading
from pathlib import Path

BE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = BE_DIR.parent / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from shared import OllamaAgent  # noqa: E402

CHAT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant, integrated into this project's web "
    "chat interface. Tool-calling (file access, running commands) is not "
    "available in this interface yet -- answer from your own knowledge "
    "and the conversation so far, and say so plainly if a request would "
    "require a capability you don't have here."
)

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
