"""Tests for GET /api/chat/history, POST /api/chat/stream,
POST /api/chat/respond, POST /api/chat/reset -- the full tool-calling
chat (run_agent(), same 9 tools as CLI_agent.py, approval gate answered
over HTTP instead of a terminal). agent_bridge.get_agent() is
monkeypatched with a scriptable fake OllamaAgent throughout; no real
Ollama server needed. fs_tools.BASE_DIR is isolated to tmp_path so a
real write_file()/create_directory() call in a test can't touch the
real workspace/.

Approval/human-request round trips are unit-tested directly against
ConversationTurn in test_approval_bridge.py -- TestClient's synchronous
request/response model buffers the whole SSE body before returning, so
it can't cleanly answer an approval mid-stream from the same process.
The full HTTP round trip (approve, deny, ask_human, ask_human_choice,
real sandboxed file write) was live-verified against a real Uvicorn
process + real Ollama model during development; what's tested here over
HTTP is everything that doesn't require answering mid-stream: final
answers, read-only tool calls, history, reset, the 409 concurrency
guard, logging, and token accounting.

Also covers logging: every message/tool call is written through the
agent's own chat_logger.py -- LOG_DIR is pointed at an isolated
tmp_path so no test ever writes into the real logs/. Same isolation for
memory.MEMORY_PATH, since token usage now also accumulates into
memory.json.
"""

import json
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import fs_tools
from app.api import chat as chat_api
from app.core import agent_bridge  # noqa: F401 -- import first, adds agent/ to sys.path
from app.main import create_app

import log_config  # noqa: E402 -- must come after agent_bridge's sys.path insert
import memory  # noqa: E402


class FakeMessage:
    """Stand-in for ollama's Message -- supports subscript access
    (m["role"]) the same way the real one does, since chat.py's
    get_history() and run_agent() (shared.py) both read messages that
    way."""

    def __init__(self, role="assistant", content=None, tool_calls=None):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls

    def __getitem__(self, key):
        return getattr(self, key)


class FakeToolCall:
    def __init__(self, name, arguments):
        self.function = SimpleNamespace(name=name, arguments=arguments)


class FakeResponse:
    def __init__(self, message, prompt_eval_count=0, eval_count=0):
        self.message = message
        self.prompt_eval_count = prompt_eval_count
        self.eval_count = eval_count


def final_round(content, prompt_eval_count=1, eval_count=1):
    """A round with no tool calls -- run_agent() treats this as the
    finished answer."""
    return FakeResponse(FakeMessage(content=content), prompt_eval_count, eval_count)


def tool_call_round(tool_name, arguments, prompt_eval_count=1, eval_count=1):
    """A round proposing exactly one tool call."""
    call = FakeToolCall(tool_name, arguments)
    return FakeResponse(FakeMessage(content=None, tool_calls=[call]), prompt_eval_count, eval_count)


class FakeAgent:
    """Scriptable stand-in for OllamaAgent -- each .chat() call pops
    the next round from `rounds`, mirroring the real interface
    run_agent() depends on: .chat(messages, tools), .model,
    .total_tokens (incremented the same way OllamaAgent.chat() does)."""

    def __init__(self, rounds):
        self._rounds = list(rounds)
        self.model = "test-model"
        self.total_tokens = 0
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        response = self._rounds.pop(0)
        self.total_tokens += (response.prompt_eval_count or 0) + (response.eval_count or 0)
        return response


@pytest.fixture(autouse=True)
def reset_chat_state(monkeypatch, tmp_path):
    """Every test gets a fresh conversation, no active turn, an
    isolated log directory + memory file + sandbox dir, and a clean
    chat_logger singleton -- all of chat.py's module-level state that
    would otherwise bleed across tests."""
    chat_api._messages = [{"role": "system", "content": agent_bridge.CHAT_SYSTEM_PROMPT}]
    chat_api._chat_logger = None
    chat_api._current_turn = None
    monkeypatch.setattr(log_config, "LOG_DIR", tmp_path)
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)
    fake_agent = FakeAgent([final_round("Hello!")])
    monkeypatch.setattr(agent_bridge, "_agent", fake_agent)
    yield fake_agent


def client():
    return TestClient(create_app())


def parse_sse_events(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            events.append(json.loads(block[5:].strip()))
    return events


def stream(c, message: str) -> list[dict]:
    """POST /stream and wait for the full SSE body. Only valid for
    scripts with no tool call that needs approval/human input."""
    response = c.post("/api/chat/stream", json={"message": message})
    assert response.status_code == 200
    return parse_sse_events(response.text)


# --------------------------------------------------------------------------
# Basic conversation, no tools
# --------------------------------------------------------------------------

def test_history_starts_empty():
    response = client().get("/api/chat/history")
    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_stream_final_answer_and_history(reset_chat_state):
    reset_chat_state._rounds = [final_round("Hi there!")]
    events = stream(client(), "hello")
    assert events[-2] == {"type": "final", "content": "Hi there!"}
    assert events[-1] == {"type": "stream_end"}

    history = client().get("/api/chat/history").json()["messages"]
    assert history[0] == {"role": "user", "content": "hello"}
    assert history[1] == {"role": "assistant", "content": "Hi there!"}


def test_stream_passes_full_message_history_to_agent(reset_chat_state):
    reset_chat_state._rounds = [final_round("first reply"), final_round("second reply")]
    c = client()
    stream(c, "first")
    stream(c, "second")
    history = c.get("/api/chat/history").json()["messages"]
    roles = [m["role"] for m in history]
    assert roles == ["user", "assistant", "user", "assistant"]


# --------------------------------------------------------------------------
# Tool calls that don't need approval (read-only)
# --------------------------------------------------------------------------

def test_stream_runs_read_only_tool_without_approval(reset_chat_state, tmp_path):
    (tmp_path / "note.txt").write_text("hi")
    reset_chat_state._rounds = [
        tool_call_round("list_directory", {"path": "."}),
        final_round("Found note.txt"),
    ]
    events = stream(client(), "list files")
    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "approval_request" not in types
    assert events[-2] == {"type": "final", "content": "Found note.txt"}


# --------------------------------------------------------------------------
# Concurrency guard -- one turn at a time
# --------------------------------------------------------------------------

def test_second_stream_while_one_active_gets_409(reset_chat_state):
    # A tool call that WILL pause on an approval the test never
    # answers -- lets us assert 409 while it's still in flight, then
    # answer it directly (bypassing HTTP) to let the background thread
    # finish cleanly before the test ends.
    reset_chat_state._rounds = [
        tool_call_round("write_file", {"path": "out.txt", "content": "hi"}),
        final_round("done"),
    ]
    c = client()
    t = threading.Thread(target=lambda: c.post("/api/chat/stream", json={"message": "first"}))
    t.start()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        turn = chat_api._current_turn
        if turn is not None and turn._pending_request_id is not None:
            break
        time.sleep(0.02)
    assert chat_api._current_turn is not None, "turn never started"

    second = c.post("/api/chat/stream", json={"message": "second"})
    assert second.status_code == 409

    turn = chat_api._current_turn
    if turn is not None:
        turn.submit_answer(turn._pending_request_id, True)
    t.join(timeout=5)


# --------------------------------------------------------------------------
# Reset
# --------------------------------------------------------------------------

def test_reset_clears_history(reset_chat_state):
    reset_chat_state._rounds = [final_round("hi")]
    c = client()
    stream(c, "hello")
    assert c.get("/api/chat/history").json()["messages"] != []

    reset_response = c.post("/api/chat/reset")
    assert reset_response.status_code == 200
    assert c.get("/api/chat/history").json()["messages"] == []


def test_respond_with_no_active_turn_reports_no_active_turn():
    response = client().post("/api/chat/respond", json={"request_id": "whatever", "approved": True})
    assert response.json()["status"] == "no_active_turn"


def test_chat_page_is_served():
    response = client().get("/chat")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Agent Chat" in response.text


# --------------------------------------------------------------------------
# Logging -- every step logged through the agent's own chat_logger.py
# --------------------------------------------------------------------------

def _read_log_events(tmp_path):
    log_files = list(tmp_path.glob("*.jsonl"))
    assert len(log_files) == 1, f"expected exactly one log file, found {log_files}"
    return [json.loads(line) for line in log_files[0].read_text().splitlines() if line.strip()]


def test_stream_logs_user_message_tool_call_and_response(reset_chat_state, tmp_path):
    reset_chat_state._rounds = [
        tool_call_round("list_directory", {"path": "."}),
        final_round("done"),
    ]
    stream(client(), "list files")
    events = _read_log_events(tmp_path)
    event_types = [e["event"] for e in events]
    assert "session_start" in event_types
    assert "user_message" in event_types
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "model_response" in event_types


def test_reset_closes_log_with_session_end(reset_chat_state, tmp_path):
    reset_chat_state._rounds = [final_round("hi")]
    c = client()
    stream(c, "hi")
    c.post("/api/chat/reset")
    events = _read_log_events(tmp_path)
    session_end = next(e for e in events if e["event"] == "session_end")
    assert session_end["reason"] == "new_chat"


def test_no_message_sent_means_no_log_file_created(tmp_path):
    client().get("/api/chat/history")
    client().get("/chat")
    assert list(tmp_path.glob("*.jsonl")) == []


# --------------------------------------------------------------------------
# Token usage -- saved into the same memory.json the CLI agent uses
# --------------------------------------------------------------------------

def test_stream_saves_token_delta_to_memory(reset_chat_state):
    reset_chat_state._rounds = [final_round("hi", prompt_eval_count=30, eval_count=12)]
    stream(client(), "hello")
    assert memory.load_token_usage() == 42


def test_second_message_adds_to_running_total(reset_chat_state):
    reset_chat_state._rounds = [
        final_round("first", prompt_eval_count=10, eval_count=5),
        final_round("second", prompt_eval_count=8, eval_count=7),
    ]
    c = client()
    stream(c, "first")
    stream(c, "second")
    assert memory.load_token_usage() == 30
