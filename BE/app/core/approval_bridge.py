"""Runs one run_agent() tool-calling turn in a background thread, and
relays every step (model thoughts, tool calls/results, confirm()
approval gates, ask_human/ask_human_choice questions) as a stream of
plain-dict events an SSE endpoint can forward to the browser.

Why a background thread at all: run_agent() (shared.py) is fully
synchronous -- it blocks on agent.chat() and, for anything with a side
effect, on confirm() (a real terminal input() in the CLI). There is no
terminal here. confirm.py/human_tools.py's set_confirm_backend()/
set_human_backend() (added alongside this file) let ConversationTurn
substitute a callback that instead:
  1. pushes an "approval_request"/"human_request" event onto self.events
     (the SSE endpoint's generator is reading this queue and forwards
     it to the browser immediately),
  2. blocks on self._pending_answer.get(timeout=...) -- the SAME
     background thread, not the HTTP request thread, so the SSE
     connection stays open and responsive the whole time,
  3. resumes once POST /api/chat/respond (a DIFFERENT request, a
     DIFFERENT thread) calls submit_answer() with the human's decision.

Single global conversation, matching chat.py's existing simplicity
choice (see its own module docstring) -- exactly one ConversationTurn
can be active at a time; chat.py enforces that with its own lock before
constructing one.
"""

import queue
import sys
import threading
import uuid
from pathlib import Path

BE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = BE_DIR.parent / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import confirm as confirm_module  # noqa: E402
import human_tools as human_tools_module  # noqa: E402
from agent_config import CONFIRM_TIMEOUT_SECONDS  # noqa: E402
from shared import run_agent  # noqa: E402


class _EventForwardingLogger:
    """Wraps a real ChatLogger (see chat_logger.py) so every call still
    writes the normal JSONL record, but ALSO pushes an SSE-shaped event
    onto `events` -- the only way the browser sees the model's
    intermediate thoughts and tool activity, since run_agent() itself
    is called with verbose=False here (nothing should be printed to the
    BE process's own stdout on behalf of a web request)."""

    def __init__(self, real_logger, events: "queue.Queue"):
        self._real = real_logger
        self._events = events

    def user_message(self, text):
        self._real.user_message(text)

    def model_call_start(self, message_count, tools):
        self._real.model_call_start(message_count, tools)

    def model_response(self, content, tool_calls, response=None):
        self._real.model_response(content, tool_calls, response=response)
        if content:
            self._events.put({"type": "thought", "content": content})

    def tool_call(self, name, arguments):
        start = self._real.tool_call(name, arguments)
        self._events.put({"type": "tool_call", "name": name, "arguments": arguments})
        return start

    def tool_result(self, name, result, start_time, error=False):
        self._real.tool_result(name, result, start_time, error=error)
        self._events.put({"type": "tool_result", "name": name, "result": str(result), "error": error})

    def loop_limit_hit(self, max_iterations):
        self._real.loop_limit_hit(max_iterations)

    def error(self, message, **context):
        self._real.error(message, **context)

    def session_end(self, reason="user_exit"):
        self._real.session_end(reason=reason)


class ConversationTurn:
    """One run_agent() call, running on a background thread, with its
    confirm()/ask_human() calls rerouted to wait for an HTTP answer
    instead of a terminal."""

    def __init__(self, agent, messages, chat_logger, tools, tool_map):
        self.agent = agent
        self.messages = messages
        self.tools = tools
        self.tool_map = tool_map
        self.events: queue.Queue = queue.Queue()
        self.cancelled = False
        self.final_answer: str | None = None

        self._logger = _EventForwardingLogger(chat_logger, self.events)
        self._pending_answer: queue.Queue = queue.Queue(maxsize=1)
        self._pending_lock = threading.Lock()
        self._pending_request_id: str | None = None
        self._thread: threading.Thread | None = None

    # -- backends, called FROM the background thread (see _run) --------

    def _handle_confirm(self, action: str, timeout_seconds) -> bool:
        request_id = uuid.uuid4().hex[:8]
        with self._pending_lock:
            self._pending_request_id = request_id
        self.events.put({"type": "approval_request", "request_id": request_id, "action": action})

        timeout = timeout_seconds if timeout_seconds is not None else CONFIRM_TIMEOUT_SECONDS
        try:
            value = self._pending_answer.get(timeout=timeout)
        except queue.Empty:
            self.events.put({"type": "approval_timeout", "request_id": request_id})
            return False
        finally:
            with self._pending_lock:
                self._pending_request_id = None
        return bool(value)

    def _handle_human(self, kind: str, question: str, options) -> str:
        request_id = uuid.uuid4().hex[:8]
        with self._pending_lock:
            self._pending_request_id = request_id
        self.events.put({
            "type": "human_request", "request_id": request_id,
            "kind": kind, "question": question, "options": options,
        })
        try:
            value = self._pending_answer.get(timeout=CONFIRM_TIMEOUT_SECONDS)
        except queue.Empty:
            self.events.put({"type": "human_timeout", "request_id": request_id})
            return ""
        finally:
            with self._pending_lock:
                self._pending_request_id = None
        return str(value)

    # -- called from a DIFFERENT thread (the POST /respond handler) ----

    def submit_answer(self, request_id: str, value) -> bool:
        """Unblocks whichever _handle_confirm/_handle_human call is
        currently waiting, if request_id matches. Returns False (a
        no-op) for a stale/unknown request_id -- e.g. a duplicate
        click, or an answer arriving after this turn already timed out
        and moved on -- rather than raising."""
        with self._pending_lock:
            if self._pending_request_id != request_id:
                return False
        try:
            self._pending_answer.put_nowait(value)
        except queue.Full:
            return False
        return True

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        confirm_module.set_confirm_backend(self._handle_confirm)
        human_tools_module.set_human_backend(self._handle_human)
        try:
            answer = run_agent(
                self.agent, self.messages, self.tools, self.tool_map,
                verbose=False, chat_logger=self._logger,
            )
            self.final_answer = answer
            self.events.put({"type": "final", "content": answer})
        except Exception as exc:
            self.events.put({"type": "error", "detail": str(exc)})
        finally:
            confirm_module.clear_confirm_backend()
            human_tools_module.clear_human_backend()
            self.events.put({"type": "stream_end"})
