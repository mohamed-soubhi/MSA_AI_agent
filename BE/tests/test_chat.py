"""Tests for GET /api/chat/history, POST /api/chat/stream, POST
/api/chat/reset -- the plain conversational chat (no tool-calling yet,
see agent_bridge.py). agent_bridge.get_agent() is monkeypatched
throughout with a fake OllamaAgent; no real Ollama server needed.

Also covers logging: every message is written through the agent's own
chat_logger.py (see chat.py's module docstring) -- LOG_DIR is pointed
at an isolated tmp_path so no test ever writes into the real logs/.
Same isolation for memory.MEMORY_PATH, since token usage now also
accumulates into memory.json.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.core import agent_bridge  # noqa: F401 -- import first, adds agent/ to sys.path
from app.main import create_app

import log_config  # noqa: E402 -- must come after agent_bridge's sys.path insert
import memory  # noqa: E402


class FakeStreamingAgent:
    """Stand-in for OllamaAgent -- chat_stream() yields scripted chunks.

    total_tokens increments by (prompt_eval_count + eval_count) from
    stream_stats once the stream completes, mirroring
    shared.OllamaAgent.chat_stream()'s real behavior -- lets tests
    verify the resulting memory.json delta.
    """

    def __init__(self, chunks=None, raise_after=None, stream_stats=None):
        self._chunks = chunks if chunks is not None else ["Hello", ", ", "world!"]
        self._raise_after = raise_after
        self.received_messages = None
        self.model = "test-model"
        self.last_stream_stats = stream_stats
        self.total_tokens = 0

    def chat_stream(self, messages):
        self.received_messages = messages
        for i, chunk in enumerate(self._chunks):
            if self._raise_after is not None and i == self._raise_after:
                raise RuntimeError("model exploded")
            yield chunk
        if self.last_stream_stats:
            self.total_tokens += (
                (self.last_stream_stats.get("prompt_eval_count") or 0)
                + (self.last_stream_stats.get("eval_count") or 0)
            )


@pytest.fixture(autouse=True)
def reset_chat_state(monkeypatch, tmp_path):
    """Every test gets a fresh conversation, a fresh fake agent, an
    isolated log directory + memory file, and a clean chat_logger
    singleton -- all of chat.py's module-level state that would
    otherwise bleed across tests."""
    chat_api._messages = [{"role": "system", "content": agent_bridge.CHAT_SYSTEM_PROMPT}]
    chat_api._chat_logger = None
    monkeypatch.setattr(log_config, "LOG_DIR", tmp_path)
    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "memory.json")
    fake_agent = FakeStreamingAgent()
    monkeypatch.setattr(agent_bridge, "_agent", fake_agent)
    yield fake_agent


def client():
    return TestClient(create_app())


def parse_sse_events(text: str) -> list[dict]:
    import json

    events = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            events.append(json.loads(block[5:].strip()))
    return events


def test_history_starts_empty():
    response = client().get("/api/chat/history")
    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_stream_returns_sse_deltas_and_done(reset_chat_state):
    response = client().post("/api/chat/stream", json={"message": "hi"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse_events(response.text)
    deltas = [e["delta"] for e in events if "delta" in e]
    assert deltas == ["Hello", ", ", "world!"]
    assert events[-1] == {"done": True}


def test_stream_appends_user_and_assistant_to_history():
    client().post("/api/chat/stream", json={"message": "hi there"})
    history = client().get("/api/chat/history").json()["messages"]
    assert history[0] == {"role": "user", "content": "hi there"}
    assert history[1] == {"role": "assistant", "content": "Hello, world!"}


def test_stream_passes_full_message_history_to_agent(reset_chat_state):
    client().post("/api/chat/stream", json={"message": "first"})
    client().post("/api/chat/stream", json={"message": "second"})
    sent = reset_chat_state.received_messages
    roles = [m["role"] for m in sent]
    assert roles == ["system", "user", "assistant", "user"]
    assert sent[-1]["content"] == "second"


def test_stream_error_mid_generation_yields_error_event(monkeypatch):
    broken_agent = FakeStreamingAgent(chunks=["partial ", "more"], raise_after=1)
    monkeypatch.setattr(agent_bridge, "_agent", broken_agent)

    response = client().post("/api/chat/stream", json={"message": "hi"})
    events = parse_sse_events(response.text)
    assert any("error" in e for e in events)
    assert events[-1] == {"done": True}


def test_reset_clears_history():
    client().post("/api/chat/stream", json={"message": "hi"})
    assert client().get("/api/chat/history").json()["messages"] != []

    reset_response = client().post("/api/chat/reset")
    assert reset_response.status_code == 200
    assert client().get("/api/chat/history").json()["messages"] == []


def test_chat_page_is_served():
    response = client().get("/chat")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Agent Chat" in response.text


# --------------------------------------------------------------------------
# Logging -- every message logged through the agent's own chat_logger.py
# --------------------------------------------------------------------------

def _read_log_events(tmp_path):
    log_files = list(tmp_path.glob("*.jsonl"))
    assert len(log_files) == 1, f"expected exactly one log file, found {log_files}"
    return [json.loads(line) for line in log_files[0].read_text().splitlines() if line.strip()]


def test_stream_logs_user_message_and_model_response(tmp_path):
    client().post("/api/chat/stream", json={"message": "hi there"})
    events = _read_log_events(tmp_path)
    event_types = [e["event"] for e in events]
    assert "session_start" in event_types
    assert "user_message" in event_types
    assert "model_response" in event_types

    user_event = next(e for e in events if e["event"] == "user_message")
    assert user_event["content"] == "hi there"

    response_event = next(e for e in events if e["event"] == "model_response")
    assert response_event["content"] == "Hello, world!"


def test_stream_logs_token_and_timing_stats_from_final_chunk(monkeypatch, tmp_path):
    stats = {
        "prompt_eval_count": 42, "eval_count": 7, "total_duration": 1000,
        "load_duration": 100, "prompt_eval_duration": 50, "eval_duration": 20,
    }
    fake_agent = FakeStreamingAgent(stream_stats=stats)
    monkeypatch.setattr(agent_bridge, "_agent", fake_agent)

    client().post("/api/chat/stream", json={"message": "hi"})
    events = _read_log_events(tmp_path)
    response_event = next(e for e in events if e["event"] == "model_response")

    assert response_event["prompt_eval_count"] == 42
    assert response_event["eval_count"] == 7
    assert response_event["total_duration"] == 1000


def test_stream_error_is_logged(monkeypatch, tmp_path):
    broken_agent = FakeStreamingAgent(chunks=["partial ", "more"], raise_after=1)
    monkeypatch.setattr(agent_bridge, "_agent", broken_agent)

    client().post("/api/chat/stream", json={"message": "hi"})
    events = _read_log_events(tmp_path)
    assert any(e["event"] == "error" for e in events)


def test_reset_closes_log_with_session_end(tmp_path):
    client().post("/api/chat/stream", json={"message": "hi"})
    client().post("/api/chat/reset")
    events = _read_log_events(tmp_path)
    session_end = next(e for e in events if e["event"] == "session_end")
    assert session_end["reason"] == "new_chat"


def test_new_conversation_after_reset_starts_a_fresh_chat_logger(tmp_path):
    # chat_logger.py's per_run filenames are second-resolution
    # (chat_page_YYYYmmdd_HHMMSS.jsonl) -- two conversations started
    # within the same wall-clock second legitimately land in the same
    # file (a pre-existing chat_logger.py granularity limit, not
    # something this test is about). What matters here is that
    # POST /reset actually creates a NEW ChatLogger object (a fresh
    # session_start/session_end pair), not that it's always a
    # distinct file on disk.
    client().post("/api/chat/stream", json={"message": "first conversation"})
    first_logger = chat_api._chat_logger
    client().post("/api/chat/reset")
    client().post("/api/chat/stream", json={"message": "second conversation"})
    second_logger = chat_api._chat_logger

    assert first_logger is not second_logger
    events = [
        json.loads(line)
        for f in tmp_path.glob("*.jsonl")
        for line in f.read_text().splitlines() if line.strip()
    ]
    assert len([e for e in events if e["event"] == "session_start"]) == 2


def test_no_message_sent_means_no_log_file_created(tmp_path):
    # GET /history and GET /chat alone shouldn't open a log file.
    client().get("/api/chat/history")
    client().get("/chat")
    assert list(tmp_path.glob("*.jsonl")) == []


# --------------------------------------------------------------------------
# Token usage -- saved into the same memory.json the CLI agent uses
# --------------------------------------------------------------------------

def test_stream_saves_token_delta_to_memory(monkeypatch):
    fake_agent = FakeStreamingAgent(stream_stats={"prompt_eval_count": 30, "eval_count": 12})
    monkeypatch.setattr(agent_bridge, "_agent", fake_agent)

    client().post("/api/chat/stream", json={"message": "hi"})

    assert memory.load_token_usage() == 42


def test_second_message_adds_to_running_total(monkeypatch):
    fake_agent = FakeStreamingAgent(stream_stats={"prompt_eval_count": 10, "eval_count": 5})
    monkeypatch.setattr(agent_bridge, "_agent", fake_agent)

    client().post("/api/chat/stream", json={"message": "first"})
    client().post("/api/chat/stream", json={"message": "second"})

    # Same fake agent instance -> total_tokens accumulates across both
    # calls; memory.json should reflect the SUM of both deltas (30),
    # not just the second call's raw total_tokens value.
    assert memory.load_token_usage() == 30


def test_no_stream_stats_means_no_memory_write(monkeypatch):
    # A backend that never sends a done=True chunk -- last_stream_stats
    # stays None, total_tokens never moves, nothing should be saved.
    fake_agent = FakeStreamingAgent(stream_stats=None)
    monkeypatch.setattr(agent_bridge, "_agent", fake_agent)

    client().post("/api/chat/stream", json={"message": "hi"})

    assert memory.load_token_usage() == 0


def test_error_mid_stream_still_saves_whatever_tokens_were_used(monkeypatch):
    # Partial output before a failure may still have consumed tokens
    # (the failure is mid-generation, not mid-request) -- but this fake
    # only sets total_tokens on a clean finish, so a failure here means
    # delta stays 0. Real chat_stream() would only have counted
    # anything if a done=True chunk actually arrived, which a raised
    # exception mid-stream means it didn't -- so 0 is the correct,
    # honest answer, not a bug.
    broken_agent = FakeStreamingAgent(chunks=["partial ", "more"], raise_after=1)
    monkeypatch.setattr(agent_bridge, "_agent", broken_agent)

    client().post("/api/chat/stream", json={"message": "hi"})

    assert memory.load_token_usage() == 0
