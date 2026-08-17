"""Direct unit tests for ConversationTurn (app/core/approval_bridge.py)
-- the confirm()/ask_human() <-> HTTP handoff that lets run_agent()'s
tool loop pause for a human answer without a real terminal.

Tested directly against ConversationTurn rather than through
TestClient's HTTP layer: TestClient's synchronous .post() buffers the
whole SSE body before returning, so a same-process test can't cleanly
answer an approval mid-stream over real HTTP. The full HTTP round trip
was live-verified against a real Uvicorn process + real Ollama model
during development (approve, deny, ask_human, ask_human_choice, a real
sandboxed file write). What matters at the unit level -- and is
deterministic here -- is that _handle_confirm/_handle_human correctly
pause, resume on submit_answer(), time out cleanly, and reject stale
request ids.
"""

import threading

from app.core import agent_bridge  # noqa: F401 -- adds agent/ to sys.path
from app.core.approval_bridge import ConversationTurn


class _NullChatLogger:
    def user_message(self, *a, **k): pass
    def model_call_start(self, *a, **k): pass
    def model_response(self, *a, **k): pass
    def tool_call(self, *a, **k): return 0.0
    def tool_result(self, *a, **k): pass
    def loop_limit_hit(self, *a, **k): pass
    def error(self, *a, **k): pass
    def session_end(self, *a, **k): pass


def make_turn():
    return ConversationTurn(agent=None, messages=[], chat_logger=_NullChatLogger(), tools=[], tool_map={})


def test_confirm_approved_returns_true():
    turn = make_turn()
    result_holder = {}

    def call_confirm():
        result_holder["value"] = turn._handle_confirm("do the thing", timeout_seconds=5)

    t = threading.Thread(target=call_confirm)
    t.start()

    event = turn.events.get(timeout=2)
    assert event["type"] == "approval_request"
    assert event["action"] == "do the thing"

    ok = turn.submit_answer(event["request_id"], True)
    assert ok is True
    t.join(timeout=2)
    assert result_holder["value"] is True


def test_confirm_denied_returns_false():
    turn = make_turn()
    result_holder = {}

    def call_confirm():
        result_holder["value"] = turn._handle_confirm("do the thing", timeout_seconds=5)

    t = threading.Thread(target=call_confirm)
    t.start()
    event = turn.events.get(timeout=2)
    turn.submit_answer(event["request_id"], False)
    t.join(timeout=2)
    assert result_holder["value"] is False


def test_confirm_timeout_returns_false_and_emits_event():
    turn = make_turn()
    result_holder = {}

    def call_confirm():
        result_holder["value"] = turn._handle_confirm("do the thing", timeout_seconds=0.1)

    t = threading.Thread(target=call_confirm)
    t.start()
    request_event = turn.events.get(timeout=2)
    timeout_event = turn.events.get(timeout=2)
    t.join(timeout=2)

    assert timeout_event == {"type": "approval_timeout", "request_id": request_event["request_id"]}
    assert result_holder["value"] is False


def test_stale_request_id_is_rejected():
    turn = make_turn()

    def call_confirm():
        turn._handle_confirm("do the thing", timeout_seconds=2)

    t = threading.Thread(target=call_confirm)
    t.start()
    turn.events.get(timeout=2)  # the real approval_request

    ok = turn.submit_answer("not-the-real-id", True)
    assert ok is False

    t.join(timeout=3)  # the real one still times out on its own


def test_ask_human_returns_the_answer():
    turn = make_turn()
    result_holder = {}

    def call_ask():
        result_holder["value"] = turn._handle_human("ask", "What's the name?", None)

    t = threading.Thread(target=call_ask)
    t.start()
    event = turn.events.get(timeout=2)
    assert event["type"] == "human_request"
    assert event["kind"] == "ask"
    assert event["options"] is None

    turn.submit_answer(event["request_id"], "notes.txt")
    t.join(timeout=2)
    assert result_holder["value"] == "notes.txt"


def test_ask_human_choice_carries_options():
    turn = make_turn()
    result_holder = {}

    def call_choice():
        result_holder["value"] = turn._handle_human("choice", "Pick one", ["a", "b"])

    t = threading.Thread(target=call_choice)
    t.start()
    event = turn.events.get(timeout=2)
    assert event["options"] == ["a", "b"]

    turn.submit_answer(event["request_id"], "2")
    t.join(timeout=2)
    assert result_holder["value"] == "2"


def test_submit_answer_before_any_pending_request_is_rejected():
    turn = make_turn()
    assert turn.submit_answer("anything", True) is False
