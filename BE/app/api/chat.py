"""GET /api/chat/history, POST /api/chat/stream, POST /api/chat/respond,
POST /api/chat/reset -- a full tool-calling chat over the agent's own
run_agent() loop, exactly the same 9 tools CLI_agent.py wires up (see
app/core/tool_bridge.py), with the same confirm() approval gate --
except confirm()/ask_human()/ask_human_choice() are answered over HTTP
(POST /api/chat/respond) instead of a blocking terminal input(). See
app/core/approval_bridge.py for how that handoff actually works.

Single in-memory conversation, shared by every request to this BE
process -- matches a single local user, same simplicity choice as the
CLI agent's one-conversation-per-run design. Restarting the BE process
clears it; POST /reset clears it on purpose without a restart. Only
ONE tool-calling turn may be in flight at a time (_turn_lock) -- a
second POST /stream while one is still running gets a 409, same as a
human can only be asked one confirm() prompt at once.

Every message/reply is logged through the agent's OWN chat_logger.py --
same JSONL format, same logs/ directory, same fields (including
prompt_eval_count/eval_count/durations, each tool_call/tool_result)
the CLI agent's sessions produce. One "session" here = one
conversation: the log file opens on the first message after startup or
a reset, and POST /reset closes it out with session_end(reason="new_chat")
before starting a fresh one.

Token usage also accumulates into the SAME memory.json the CLI agent
uses (memory.save_token_usage()) -- one running "tokens used all-time"
total, shared regardless of whether the tokens came from the CLI or
this chat page.
"""

import asyncio
import json
import queue
import threading

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.core.agent_bridge import CHAT_SYSTEM_PROMPT, get_agent
from app.core.approval_bridge import ConversationTurn
from app.core.tool_bridge import get_active_tools
from chat_logger import get_logger
from memory import save_token_usage

router = APIRouter(prefix="/api/chat", tags=["chat"])

_history_lock = threading.Lock()
_messages: list = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

_logger_lock = threading.Lock()
_chat_logger = None

_turn_lock = threading.Lock()
_current_turn: ConversationTurn | None = None


def _get_chat_logger(model: str):
    """Lazily open one ChatLogger per conversation -- not per process,
    so a long-running BE service still gets one JSONL file per
    conversation, same granularity as one CLI session."""
    global _chat_logger
    with _logger_lock:
        if _chat_logger is None:
            _chat_logger = get_logger("chat_page", model)
        return _chat_logger


def _close_chat_logger(reason: str) -> None:
    global _chat_logger
    with _logger_lock:
        if _chat_logger is not None:
            _chat_logger.session_end(reason=reason)
            _chat_logger = None


class ChatRequest(BaseModel):
    message: str


class RespondRequest(BaseModel):
    request_id: str
    approved: bool | None = None  # answers an "approval_request" event
    answer: str | None = None     # answers a "human_request" event


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    messages: list[HistoryMessage]


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/history", response_model=HistoryResponse)
def get_history() -> HistoryResponse:
    """User/assistant turns only, system prompt excluded and tool
    messages excluded -- the live tool activity is what the SSE stream
    itself carries (thought/tool_call/tool_result events), this is just
    the durable transcript."""
    with _history_lock:
        visible = [
            HistoryMessage(role=m["role"], content=m["content"])
            for m in _messages
            if m["role"] in ("user", "assistant") and m["content"]
        ]
        return HistoryResponse(messages=visible)


@router.post("/reset")
def reset_chat() -> dict:
    """Start a new conversation -- clears history back to just the
    system prompt, cancels any in-flight turn (its background thread
    finishes on its own, but its result is discarded -- see
    ConversationTurn.cancelled), and closes out the current JSONL log
    file (if any message was actually sent)."""
    global _messages, _current_turn
    with _turn_lock:
        if _current_turn is not None:
            _current_turn.cancelled = True
            _current_turn = None
    with _history_lock:
        _messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    _close_chat_logger(reason="new_chat")
    return {"status": "ok"}


@router.post("/respond")
def respond_to_turn(request: RespondRequest) -> dict:
    """Answers a pending approval_request (request.approved) or
    human_request (request.answer) from the currently active turn --
    see ConversationTurn.submit_answer(). A stale/unknown request_id
    (e.g. a duplicate click, or an answer arriving after the turn
    already timed out) is reported back, not raised."""
    turn = _current_turn
    if turn is None:
        return {"status": "no_active_turn"}
    value = request.approved if request.approved is not None else (request.answer or "")
    ok = turn.submit_answer(request.request_id, value)
    return {"status": "ok" if ok else "stale_request"}


@router.post("/stream")
def stream_chat(chat_request: ChatRequest, http_request: Request):
    """Append the user's message, run the full tool-calling loop
    (run_agent(), same as CLI_agent.py's step mode), and stream every
    step back as Server-Sent Events: `data: <json>\\n\\n` per event,
    `{"type": "thought", "content": ...}` for model text,
    `{"type": "tool_call", ...}` / `{"type": "tool_result", ...}` for
    each tool invocation, `{"type": "approval_request", "request_id":
    ..., "action": ...}` when confirm() needs a human (answer via
    POST /respond), `{"type": "human_request", ...}` for
    ask_human/ask_human_choice, `{"type": "final", "content": ...}` for
    the finished answer, `{"type": "error", ...}` on failure, and
    always ending with `{"type": "stream_end"}`.

    Not using EventSource client-side (GET-only, and this needs to POST
    the message body) -- consumed via fetch() + a manual ReadableStream
    reader instead, see static/chat.html.
    """
    global _current_turn

    with _turn_lock:
        if _current_turn is not None:
            return JSONResponse(
                status_code=409,
                content={"error": "a message is already being processed"},
            )

        with _history_lock:
            _messages.append({"role": "user", "content": chat_request.message})
            snapshot = list(_messages)

        agent = get_agent()
        logger = _get_chat_logger(agent.model)
        logger.user_message(chat_request.message)

        # Per turn, not import-time: get_active_tools() reflects the
        # current WEB_TOOLS_ENABLED, so toggling web tools in the config
        # editor takes effect on the next message with no BE restart.
        tools, tool_map = get_active_tools()
        turn = ConversationTurn(agent, snapshot, logger, tools, tool_map)
        _current_turn = turn

    tokens_before = agent.total_tokens
    turn.start()

    async def event_generator():
        global _messages, _current_turn
        try:
            while True:
                # BUG this fixes (found via log analysis, 2026-08-27):
                # a plain blocking turn.events.get() ties this generator
                # to ONE http connection forever -- if the browser
                # navigates away or drops the connection mid-turn (e.g.
                # to the config page) while the background
                # ConversationTurn is itself stuck waiting on a
                # confirm()/ask_human() answer nobody will ever send,
                # nothing here ever learns the client is gone. _current_turn
                # never clears, and every future POST /stream 409s
                # forever -- recoverable only by a full BE restart.
                # Polling with a short timeout instead of blocking
                # forever lets us check http_request.is_disconnected()
                # between events and bail out (clearing _current_turn)
                # the moment the client leaves, instead of waiting on an
                # answer that can never arrive.
                try:
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, turn.events.get, True, 1.0
                    )
                except queue.Empty:
                    if await http_request.is_disconnected():
                        turn.cancelled = True
                        break
                    continue
                yield _sse(event)
                if event["type"] == "stream_end":
                    break
        except asyncio.CancelledError:
            # The ASGI task was cancelled out from under us -- client
            # navigated away, or uvicorn --reload is bouncing the worker
            # mid-stream. The finally below still clears _current_turn;
            # returning here (instead of re-raising) keeps it from
            # surfacing as a noisy "Exception in ASGI application"
            # traceback on every reload-during-a-turn.
            turn.cancelled = True
        finally:
            with _turn_lock:
                if _current_turn is turn:
                    _current_turn = None
            if not turn.cancelled:
                with _history_lock:
                    _messages = turn.messages
                delta = agent.total_tokens - tokens_before
                if delta > 0:
                    save_token_usage(delta)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
