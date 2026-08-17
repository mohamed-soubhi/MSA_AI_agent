"""GET /api/chat/history, POST /api/chat/stream, POST /api/chat/reset --
a plain conversational chat over the agent's own OllamaAgent (see
app/core/agent_bridge.py for why tool-calling isn't wired in here yet).

Single in-memory conversation, shared by every request to this BE
process -- matches a single local user, same simplicity choice as the
CLI agent's one-conversation-per-run design. Restarting the BE process
clears it; POST /reset clears it on purpose without a restart.

Every message/reply is logged through the agent's OWN chat_logger.py --
same JSONL format, same logs/ directory, same fields (including
prompt_eval_count/eval_count/durations) the CLI agent's sessions
produce, so `logs/*.jsonl` has one consistent shape regardless of
whether a session came from the CLI or this chat page. One "session"
here = one conversation: the log file opens on the first message after
startup or a reset, and POST /reset closes it out with
session_end(reason="new_chat") before starting a fresh one.
"""

import json
import threading
from types import SimpleNamespace

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.agent_bridge import CHAT_SYSTEM_PROMPT, get_agent
from chat_logger import get_logger

router = APIRouter(prefix="/api/chat", tags=["chat"])

_history_lock = threading.Lock()
_messages: list[dict] = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

_logger_lock = threading.Lock()
_chat_logger = None


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


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    messages: list[HistoryMessage]


@router.get("/history", response_model=HistoryResponse)
def get_history() -> HistoryResponse:
    """Every message so far, system prompt excluded (that's an
    implementation detail, not something the chat UI should render)."""
    with _history_lock:
        visible = [m for m in _messages if m["role"] != "system"]
        return HistoryResponse(messages=[HistoryMessage(**m) for m in visible])


@router.post("/reset")
def reset_chat() -> dict:
    """Start a new conversation -- clears history back to just the
    system prompt, and closes out the current JSONL log file (if any
    message was actually sent) so the next conversation starts a fresh
    one instead of appending to the old one."""
    global _messages
    with _history_lock:
        _messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    _close_chat_logger(reason="new_chat")
    return {"status": "ok"}


@router.post("/stream")
def stream_chat(request: ChatRequest) -> StreamingResponse:
    """Append the user's message, stream the model's reply back as
    Server-Sent Events, and append the completed reply to history once
    streaming finishes.

    Each event is `data: <json>\\n\\n` -- `{"delta": "..."}` for each
    piece of text as it arrives, `{"error": "..."}` if the model call
    fails partway through, and a final `{"done": true}` always sent
    last so the client knows the stream is over. Not using a plain
    EventSource on the client side (EventSource can only GET, and this
    needs to POST the message body), so this is consumed via fetch() +
    a manual ReadableStream reader instead -- see static/chat.html.
    """
    with _history_lock:
        _messages.append({"role": "user", "content": request.message})
        snapshot = list(_messages)

    agent = get_agent()
    logger = _get_chat_logger(agent.model)
    logger.user_message(request.message)
    logger.model_call_start(len(snapshot), tools=[])

    def event_generator():
        full_text_parts: list[str] = []
        try:
            for chunk in agent.chat_stream(snapshot):
                if chunk:
                    full_text_parts.append(chunk)
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
        except Exception as exc:
            logger.error("chat_stream_failed", detail=str(exc))
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            answer = "".join(full_text_parts)
            if answer:
                with _history_lock:
                    _messages.append({"role": "assistant", "content": answer})
                # last_stream_stats came from the stream's own final
                # (done=True) chunk -- wrapped as a plain object so
                # ChatLogger.model_response()'s existing
                # _extract_model_timing() (which reads response.<field>
                # via getattr, same as it does for chat()'s response)
                # picks up prompt_eval_count/eval_count/durations here
                # too, with no changes needed to chat_logger.py itself.
                stats = agent.last_stream_stats or {}
                logger.model_response(answer, [], response=SimpleNamespace(**stats))
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
