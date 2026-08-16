"""Tests for shared.py — OllamaAgent wrapper and the run_agent tool loop.

Network calls are mocked throughout (no real Ollama server needed).
Covers: section() formatting, _call_signature()/_parse_arguments()/
_sanitize_for_model() helpers, _run_tool_with_timeout(), OllamaAgent.chat()
retry/timeout/failure behavior, chat_stream(), and run_agent()'s full
control flow (final answer, tool success/error/timeout/unknown, malformed
args, stuck-loop detection, wall-clock timeout, max iterations).
"""

import time
from types import SimpleNamespace

import pytest

import shared
from chat_logger import NullChatLogger
from shared import (
    OllamaAgent,
    _call_signature,
    _parse_arguments,
    _run_tool_with_timeout,
    _sanitize_for_model,
    _validate_arguments,
    run_agent,
    section,
)


# --------------------------------------------------------------------------
# section
# --------------------------------------------------------------------------

class TestSection:
    @pytest.mark.tid("SHARED-001")
    def test_underlines_title_with_equals_matching_length(self):
        result = section("Hello")
        assert result == "\nHello\n====="

    @pytest.mark.tid("SHARED-002")
    def test_empty_title(self):
        assert section("") == "\n\n"


# --------------------------------------------------------------------------
# _call_signature
# --------------------------------------------------------------------------

class TestCallSignature:
    @pytest.mark.tid("SHARED-003")
    def test_same_name_and_args_produce_same_signature(self):
        a = _call_signature("read_file", {"path": "x.txt"})
        b = _call_signature("read_file", {"path": "x.txt"})
        assert a == b

    @pytest.mark.tid("SHARED-004")
    def test_key_order_does_not_affect_signature(self):
        a = _call_signature("write_file", {"path": "x", "content": "y"})
        b = _call_signature("write_file", {"content": "y", "path": "x"})
        assert a == b

    @pytest.mark.tid("SHARED-005")
    def test_different_args_produce_different_signature(self):
        a = _call_signature("read_file", {"path": "x.txt"})
        b = _call_signature("read_file", {"path": "y.txt"})
        assert a != b

    @pytest.mark.tid("SHARED-006")
    def test_different_tool_name_produces_different_signature(self):
        a = _call_signature("read_file", {"path": "x"})
        b = _call_signature("write_file", {"path": "x"})
        assert a != b

    @pytest.mark.tid("SHARED-007")
    def test_unserializable_arguments_fall_back_to_str(self):
        class Weird:
            pass

        # Must not raise even though Weird() isn't JSON-serializable.
        sig = _call_signature("tool", {"obj": Weird()})
        assert isinstance(sig, str) and len(sig) == 16


# --------------------------------------------------------------------------
# _parse_arguments
# --------------------------------------------------------------------------

class TestParseArguments:
    @pytest.mark.tid("SHARED-008")
    def test_dict_passes_through(self):
        assert _parse_arguments({"a": 1}) == {"a": 1}

    @pytest.mark.tid("SHARED-009")
    def test_valid_json_string_parsed(self):
        assert _parse_arguments('{"a": 1}') == {"a": 1}

    @pytest.mark.tid("SHARED-010")
    def test_malformed_json_raises_value_error(self):
        with pytest.raises(ValueError, match="malformed tool arguments"):
            _parse_arguments("{not valid json")

    @pytest.mark.tid("SHARED-011")
    def test_json_array_string_raises_value_error(self):
        with pytest.raises(ValueError, match="must decode to a JSON object"):
            _parse_arguments("[1, 2, 3]")

    @pytest.mark.tid("SHARED-012")
    def test_unsupported_type_raises_value_error(self):
        with pytest.raises(ValueError, match="unsupported arguments type"):
            _parse_arguments(12345)

    @pytest.mark.tid("SHARED-013")
    def test_empty_dict_is_valid(self):
        assert _parse_arguments({}) == {}


# --------------------------------------------------------------------------
# _sanitize_for_model
# --------------------------------------------------------------------------

class TestSanitizeForModel:
    @pytest.mark.tid("SHARED-014")
    def test_short_text_untouched(self):
        assert _sanitize_for_model("short") == "short"

    @pytest.mark.tid("SHARED-015")
    def test_long_text_truncated_with_marker(self, monkeypatch):
        monkeypatch.setattr(shared, "MAX_OBSERVATION_CHARS", 10)
        result = _sanitize_for_model("a" * 100)
        assert result.startswith("a" * 10)
        assert "truncated, 100 chars total" in result

    @pytest.mark.tid("SHARED-016")
    def test_boundary_length_untouched(self, monkeypatch):
        monkeypatch.setattr(shared, "MAX_OBSERVATION_CHARS", 10)
        assert _sanitize_for_model("a" * 10) == "a" * 10


# --------------------------------------------------------------------------
# _run_tool_with_timeout
# --------------------------------------------------------------------------

class TestRunToolWithTimeout:
    @pytest.mark.tid("SHARED-017")
    def test_returns_function_result(self):
        def add(a, b):
            return a + b

        assert _run_tool_with_timeout(add, {"a": 1, "b": 2}, timeout_seconds=5) == 3

    @pytest.mark.tid("SHARED-018")
    def test_raises_timeout_error_when_function_hangs(self):
        def slow():
            time.sleep(1)
            return "done"

        with pytest.raises(TimeoutError, match="exceeded"):
            _run_tool_with_timeout(slow, {}, timeout_seconds=0.05)

    @pytest.mark.tid("SHARED-019")
    def test_propagates_function_exceptions(self):
        def raises():
            raise KeyError("missing")

        with pytest.raises(KeyError):
            _run_tool_with_timeout(raises, {}, timeout_seconds=5)


# --------------------------------------------------------------------------
# OllamaAgent.chat
# --------------------------------------------------------------------------

class FakeClient:
    """Stand-in for ollama.Client with scriptable chat() behavior."""

    def __init__(self, responses):
        # responses: list of return values OR Exception instances to raise,
        # consumed in order on successive calls.
        self._responses = list(responses)
        self.calls = 0

    def chat(self, model, messages, tools=None, stream=False):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if stream:
            return iter(item)
        return item


class TestValidateArguments:
    @pytest.mark.tid("SHARED-043")
    def test_matching_arguments_pass_silently(self):
        def tool(path: str, content: str):
            pass

        _validate_arguments(tool, {"path": "a.txt", "content": "x"})  # must not raise

    @pytest.mark.tid("SHARED-044")
    def test_missing_required_parameter_raises(self):
        def tool(path: str, content: str):
            pass

        with pytest.raises(ValueError, match="invalid arguments for 'tool'"):
            _validate_arguments(tool, {"path": "a.txt"})

    @pytest.mark.tid("SHARED-045")
    def test_unknown_extra_parameter_raises(self):
        def tool(path: str):
            pass

        with pytest.raises(ValueError, match="invalid arguments for 'tool'"):
            _validate_arguments(tool, {"path": "a.txt", "bogus": "x"})

    @pytest.mark.tid("SHARED-046")
    def test_typoed_parameter_name_raises(self):
        def tool(path: str):
            pass

        with pytest.raises(ValueError, match="invalid arguments for 'tool'"):
            _validate_arguments(tool, {"patth": "a.txt"})

    @pytest.mark.tid("SHARED-047")
    def test_error_message_lists_expected_and_given_params(self):
        def tool(path: str, content: str):
            pass

        with pytest.raises(ValueError) as exc_info:
            _validate_arguments(tool, {"path": "a.txt", "bogus": "x"})
        message = str(exc_info.value)
        assert "['path', 'content']" in message
        assert "['path', 'bogus']" in message

    @pytest.mark.tid("SHARED-048")
    def test_no_argument_function_accepts_empty_dict(self):
        def tool():
            pass

        _validate_arguments(tool, {})  # must not raise


class TestOllamaAgentChat:
    @pytest.mark.tid("SHARED-020")
    def test_returns_response_on_first_success(self, monkeypatch):
        agent = OllamaAgent(model="test-model")
        response = SimpleNamespace(message=SimpleNamespace(content="hi", tool_calls=None))
        agent.client = FakeClient([response])
        result = agent.chat([{"role": "user", "content": "hello"}])
        assert result is response

    @pytest.mark.tid("SHARED-021")
    def test_retries_transient_failure_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(shared, "CHAT_RETRY_BACKOFF_SECONDS", 0)
        agent = OllamaAgent(model="test-model")
        response = SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None))
        agent.client = FakeClient([ConnectionError("network blip"), response])
        result = agent.chat([{"role": "user", "content": "hi"}])
        assert result is response
        assert agent.client.calls == 2

    @pytest.mark.tid("SHARED-022")
    def test_raises_friendly_runtime_error_after_all_retries_fail(self, monkeypatch):
        monkeypatch.setattr(shared, "CHAT_RETRY_BACKOFF_SECONDS", 0)
        monkeypatch.setattr(shared, "CHAT_MAX_RETRIES", 1)
        agent = OllamaAgent(model="test-model")
        agent.client = FakeClient([ConnectionError("down"), ConnectionError("still down")])
        with pytest.raises(RuntimeError, match="Could not reach Ollama model 'test-model'"):
            agent.chat([{"role": "user", "content": "hi"}])
        assert agent.client.calls == 2

    @pytest.mark.tid("SHARED-023")
    def test_default_model_used_when_none_specified(self):
        agent = OllamaAgent()
        assert agent.model == shared.DEFAULT_MODEL


class TestOllamaAgentChatStream:
    @pytest.mark.tid("SHARED-024")
    def test_yields_chunks(self):
        agent = OllamaAgent(model="test-model")
        chunks = [SimpleNamespace(message=SimpleNamespace(content="a")),
                   SimpleNamespace(message=SimpleNamespace(content="b"))]
        agent.client = FakeClient([chunks])
        result = list(agent.chat_stream([{"role": "user", "content": "hi"}]))
        assert result == ["a", "b"]

    @pytest.mark.tid("SHARED-025")
    def test_raises_friendly_runtime_error_on_failure(self):
        agent = OllamaAgent(model="test-model")

        class BoomClient:
            def chat(self, **kwargs):
                raise ConnectionError("gone")

        agent.client = BoomClient()
        with pytest.raises(RuntimeError, match="Could not reach Ollama model 'test-model'"):
            list(agent.chat_stream([{"role": "user", "content": "hi"}]))


# --------------------------------------------------------------------------
# run_agent
# --------------------------------------------------------------------------

def make_response(content=None, tool_calls=None):
    tc_objs = []
    for call in (tool_calls or []):
        tc_objs.append(SimpleNamespace(
            function=SimpleNamespace(name=call["name"], arguments=call["arguments"])
        ))
    return SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tc_objs or None))


class FakeAgent:
    """Stand-in for OllamaAgent with a scripted sequence of chat() responses."""

    def __init__(self, responses):
        self._responses = list(responses)

    def chat(self, messages, tools=None):
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TestRunAgent:
    @pytest.mark.tid("SHARED-026")
    def test_returns_final_answer_when_no_tool_calls(self):
        agent = FakeAgent([make_response(content="the answer")])
        result = run_agent(agent, [], tools=[], tool_map={}, verbose=False)
        assert result == "the answer"

    @pytest.mark.tid("SHARED-027")
    def test_final_answer_none_content_returns_empty_string(self):
        agent = FakeAgent([make_response(content=None)])
        result = run_agent(agent, [], tools=[], tool_map={}, verbose=False)
        assert result == ""

    @pytest.mark.tid("SHARED-028")
    def test_executes_tool_and_returns_final_answer_next_round(self):
        calls = [
            make_response(tool_calls=[{"name": "echo", "arguments": {"text": "hi"}}]),
            make_response(content="done"),
        ]
        agent = FakeAgent(calls)

        def echo(text):
            return f"echoed: {text}"

        result = run_agent(agent, [], tools=[echo], tool_map={"echo": echo}, verbose=False)
        assert result == "done"

    @pytest.mark.tid("SHARED-029")
    def test_unknown_tool_reported_as_error_observation(self):
        calls = [
            make_response(tool_calls=[{"name": "ghost", "arguments": {}}]),
            make_response(content="done"),
        ]
        agent = FakeAgent(calls)
        messages = []
        run_agent(agent, messages, tools=[], tool_map={}, verbose=False)
        tool_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]
        assert "unknown tool" in tool_msgs[0]["content"]

    @pytest.mark.tid("SHARED-030")
    def test_tool_exception_reported_not_raised(self):
        def boom():
            raise KeyError("missing")

        calls = [
            make_response(tool_calls=[{"name": "boom", "arguments": {}}]),
            make_response(content="done"),
        ]
        agent = FakeAgent(calls)
        messages = []
        run_agent(agent, messages, tools=[boom], tool_map={"boom": boom}, verbose=False)
        tool_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]
        assert "KeyError" in tool_msgs[0]["content"]

    @pytest.mark.tid("SHARED-031")
    def test_tool_timeout_via_patched_constant(self, monkeypatch):
        monkeypatch.setattr(shared, "TOOL_TIMEOUT_SECONDS", 0.05)

        def slow():
            time.sleep(1)

        calls = [
            make_response(tool_calls=[{"name": "slow", "arguments": {}}]),
            make_response(content="done"),
        ]
        agent = FakeAgent(calls)
        messages = []
        run_agent(agent, messages, tools=[slow], tool_map={"slow": slow}, verbose=False)
        tool_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]
        assert "exceeded" in tool_msgs[0]["content"]

    @pytest.mark.tid("SHARED-032")
    def test_malformed_arguments_reported_as_error(self):
        calls = [
            make_response(tool_calls=[{"name": "echo", "arguments": "{not json"}]),
            make_response(content="done"),
        ]
        agent = FakeAgent(calls)
        messages = []
        run_agent(agent, messages, tools=[], tool_map={}, verbose=False)
        tool_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]
        assert "Error" in tool_msgs[0]["content"]

    @pytest.mark.tid("SHARED-033")
    def test_stuck_loop_detection_stops_after_repeated_identical_calls(self, monkeypatch):
        monkeypatch.setattr(shared, "MAX_REPEAT_CALLS", 3)

        def echo(text):
            return text

        repeated_call = make_response(tool_calls=[{"name": "echo", "arguments": {"text": "x"}}])
        agent = FakeAgent([repeated_call] * 5)
        result = run_agent(agent, [], tools=[echo], tool_map={"echo": echo}, verbose=False)
        assert "stuck" in result

    @pytest.mark.tid("SHARED-034")
    def test_chat_failure_returns_stopped_message_not_raise(self):
        agent = FakeAgent([RuntimeError("network down")])
        result = run_agent(agent, [], tools=[], tool_map={}, verbose=False)
        assert "error communicating with the model" in result

    @pytest.mark.tid("SHARED-035")
    def test_max_iterations_reached_returns_stopped_message_when_no_final_answer(self):
        # First round has no tool_calls, so run_agent treats it as a final
        # answer immediately -- confirm that "final answer" short-circuits
        # before max_iterations logic even applies.
        agent = FakeAgent([make_response(content=None)])
        result = run_agent(
            agent, [], tools=[], tool_map={}, verbose=False, max_iterations=2,
        )
        assert result == ""

    @pytest.mark.tid("SHARED-036")
    def test_max_iterations_reached_when_always_calling_tools(self):
        def echo(text):
            return text

        # Vary arguments each round so stuck-loop detection doesn't fire
        # first, isolating max_iterations behavior.
        responses = [
            make_response(tool_calls=[{"name": "echo", "arguments": {"text": str(i)}}])
            for i in range(5)
        ]
        agent = FakeAgent(responses)
        result = run_agent(
            agent, [], tools=[echo], tool_map={"echo": echo}, verbose=False,
            max_iterations=3, chat_logger=NullChatLogger(),
        )
        assert "too many tool rounds" in result

    @pytest.mark.tid("SHARED-037")
    def test_wall_timeout_stops_run(self):
        agent = FakeAgent([make_response(content="never reached")])
        result = run_agent(
            agent, [], tools=[], tool_map={}, verbose=False, max_wall_seconds=-1,
        )
        assert "exceeded maximum run time" in result

    @pytest.mark.tid("SHARED-038")
    def test_defaults_to_null_chat_logger_when_none_passed(self):
        agent = FakeAgent([make_response(content="ok")])
        # Should not raise even though chat_logger is omitted.
        result = run_agent(agent, [], tools=[], tool_map={})
        assert result == "ok"

    @pytest.mark.tid("SHARED-039")
    def test_uses_provided_chat_logger(self):
        events = []

        class SpyLogger(NullChatLogger):
            def model_call_start(self, *a, **k):
                events.append("model_call_start")

            def model_response(self, *a, **k):
                events.append("model_response")

        agent = FakeAgent([make_response(content="ok")])
        run_agent(agent, [], tools=[], tool_map={}, verbose=False, chat_logger=SpyLogger())
        assert events == ["model_call_start", "model_response"]

    @pytest.mark.tid("SHARED-040")
    def test_max_tool_calls_stops_run_at_the_cap(self):
        def echo(text):
            return text

        # Model keeps calling the tool forever; only max_tool_calls (not
        # max_iterations) should be what stops it here.
        responses = [
            make_response(tool_calls=[{"name": "echo", "arguments": {"text": str(i)}}])
            for i in range(10)
        ]
        agent = FakeAgent(responses)
        result = run_agent(
            agent, [], tools=[echo], tool_map={"echo": echo}, verbose=False,
            max_iterations=100, max_tool_calls=3,
        )
        assert "reached the 3-tool-call limit" in result

    @pytest.mark.tid("SHARED-041")
    def test_max_tool_calls_capped_call_never_reaches_the_tool(self):
        calls = []

        def echo(text):
            calls.append(text)
            return text

        responses = [
            make_response(tool_calls=[{"name": "echo", "arguments": {"text": str(i)}}])
            for i in range(5)
        ]
        agent = FakeAgent(responses)
        run_agent(
            agent, [], tools=[echo], tool_map={"echo": echo}, verbose=False,
            max_iterations=100, max_tool_calls=2,
        )
        # The call that would push the count past the cap must never run.
        assert len(calls) == 2

    @pytest.mark.tid("SHARED-042")
    def test_max_tool_calls_none_leaves_run_uncapped(self):
        def echo(text):
            return text

        calls = [
            make_response(tool_calls=[{"name": "echo", "arguments": {"text": "x"}}]),
            make_response(content="done"),
        ]
        agent = FakeAgent(calls)
        result = run_agent(
            agent, [], tools=[echo], tool_map={"echo": echo}, verbose=False,
            max_tool_calls=None,
        )
        assert result == "done"

    @pytest.mark.tid("SHARED-049")
    def test_mismatched_arguments_reported_without_calling_the_tool(self):
        called = []

        def echo(text):
            called.append(text)
            return text

        calls = [
            make_response(tool_calls=[{"name": "echo", "arguments": {"wrong_key": "x"}}]),
            make_response(content="done"),
        ]
        agent = FakeAgent(calls)
        messages = []
        run_agent(agent, messages, tools=[echo], tool_map={"echo": echo}, verbose=False)
        tool_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]
        assert "invalid arguments for 'echo'" in tool_msgs[0]["content"]
        assert called == []
