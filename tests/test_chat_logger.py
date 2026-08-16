"""Tests for chat_logger.py — structured JSONL session logging.

Covers _truncate()'s recursive shortening, ChatLogger's event methods
(each writes one JSON line with the right fields), size-based rotation,
NullChatLogger's no-op contract, and get_logger()'s enabled/disabled/
fallback branches.
"""

import json

import pytest

import chat_logger as cl_mod
import log_config as cfg
from chat_logger import ChatLogger, NullChatLogger, _extract_model_timing, _truncate, get_logger


def read_events(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(autouse=True)
def isolated_log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(cfg, "LOG_FILE_MODE", "single")
    monkeypatch.setattr(cfg, "SINGLE_LOG_FILENAME", "chat.jsonl")
    monkeypatch.setattr(cfg, "MAX_FIELD_CHARS", 4000)
    monkeypatch.setattr(cfg, "MAX_LOG_FILE_BYTES", 10_000_000)
    monkeypatch.setattr(cfg, "LOG_MODEL_TIMING", True)
    monkeypatch.setattr(cfg, "ECHO_TO_TERMINAL", False)
    monkeypatch.setattr(cfg, "LOG_ENABLED", True)
    return tmp_path


# --------------------------------------------------------------------------
# _truncate
# --------------------------------------------------------------------------

class TestTruncate:
    @pytest.mark.tid("CHATLOG-001")
    def test_short_string_untouched(self):
        assert _truncate("hello") == "hello"

    @pytest.mark.tid("CHATLOG-002")
    def test_long_string_truncated_with_marker(self, monkeypatch):
        monkeypatch.setattr(cfg, "MAX_FIELD_CHARS", 5)
        result = _truncate("abcdefghij")
        assert result.startswith("abcde")
        assert "truncated 5 more chars" in result

    @pytest.mark.tid("CHATLOG-003")
    def test_none_limit_disables_truncation(self, monkeypatch):
        monkeypatch.setattr(cfg, "MAX_FIELD_CHARS", None)
        assert _truncate("x" * 10000) == "x" * 10000

    @pytest.mark.tid("CHATLOG-004")
    def test_non_string_values_untouched(self):
        assert _truncate(42) == 42
        assert _truncate(None) is None
        assert _truncate(True) is True

    @pytest.mark.tid("CHATLOG-005")
    def test_recurses_into_dict_values(self, monkeypatch):
        monkeypatch.setattr(cfg, "MAX_FIELD_CHARS", 3)
        result = _truncate({"content": "abcdef"})
        assert result["content"].startswith("abc")

    @pytest.mark.tid("CHATLOG-006")
    def test_recurses_into_list_items(self, monkeypatch):
        monkeypatch.setattr(cfg, "MAX_FIELD_CHARS", 3)
        result = _truncate(["abcdef", "ghijkl"])
        assert all(item.startswith(item[:3]) for item in result)
        assert "truncated" in result[0]


# --------------------------------------------------------------------------
# _extract_model_timing
# --------------------------------------------------------------------------

class TestExtractModelTiming:
    @pytest.mark.tid("CHATLOG-007")
    def test_pulls_present_fields(self):
        class FakeResponse:
            total_duration = 100
            eval_count = 5

        result = _extract_model_timing(FakeResponse())
        assert result == {"total_duration": 100, "eval_count": 5}

    @pytest.mark.tid("CHATLOG-008")
    def test_missing_fields_omitted_not_null(self):
        class Empty:
            pass

        assert _extract_model_timing(Empty()) == {}

    @pytest.mark.tid("CHATLOG-009")
    def test_disabled_returns_empty_dict(self, monkeypatch):
        monkeypatch.setattr(cfg, "LOG_MODEL_TIMING", False)

        class FakeResponse:
            total_duration = 100

        assert _extract_model_timing(FakeResponse()) == {}


# --------------------------------------------------------------------------
# ChatLogger
# --------------------------------------------------------------------------

class TestChatLoggerInit:
    @pytest.mark.tid("CHATLOG-010")
    def test_creates_log_dir_and_writes_session_start(self, isolated_log_dir):
        logger = ChatLogger("test_agent", "llama3")
        assert logger.path.exists()
        events = read_events(logger.path)
        assert events[0]["event"] == "session_start"
        assert events[0]["agent"] == "test_agent"
        assert events[0]["model"] == "llama3"

    @pytest.mark.tid("CHATLOG-011")
    def test_per_run_mode_uses_timestamped_filename(self, isolated_log_dir, monkeypatch):
        monkeypatch.setattr(cfg, "LOG_FILE_MODE", "per_run")
        logger = ChatLogger("myagent", "llama3")
        assert logger.path.name.startswith("myagent_")
        assert logger.path.suffix == ".jsonl"

    @pytest.mark.tid("CHATLOG-012")
    def test_single_mode_reuses_same_file_across_instances(self, isolated_log_dir):
        first = ChatLogger("agent1", "m1")
        second = ChatLogger("agent2", "m2")
        assert first.path == second.path
        events = read_events(second.path)
        assert len(events) == 2  # two session_start records, same file


class TestChatLoggerEvents:
    @pytest.fixture
    def logger(self, isolated_log_dir):
        return ChatLogger("agent", "model-x")

    @pytest.mark.tid("CHATLOG-013")
    def test_user_message_increments_turn(self, logger):
        assert logger.turn_index == 0
        logger.user_message("hi")
        assert logger.turn_index == 1
        events = read_events(logger.path)
        assert events[-1]["event"] == "user_message"
        assert events[-1]["content"] == "hi"
        assert events[-1]["turn"] == 1

    @pytest.mark.tid("CHATLOG-014")
    def test_model_call_start_logs_tool_names(self, logger):
        def toolA():
            pass

        def toolB():
            pass

        logger.model_call_start(3, [toolA, toolB])
        events = read_events(logger.path)
        assert events[-1]["tools"] == ["toolA", "toolB"]
        assert events[-1]["message_count"] == 3

    @pytest.mark.tid("CHATLOG-015")
    def test_model_response_computes_elapsed_ms(self, logger):
        logger.model_call_start(1, [])
        logger.model_response("answer", [])
        events = read_events(logger.path)
        assert events[-1]["content"] == "answer"
        assert events[-1]["elapsed_ms"] >= 0

    @pytest.mark.tid("CHATLOG-016")
    def test_model_response_without_prior_start_has_no_elapsed(self, logger):
        logger.model_response("answer", [])
        events = read_events(logger.path)
        assert events[-1]["elapsed_ms"] is None

    @pytest.mark.tid("CHATLOG-017")
    def test_model_response_includes_timing_from_response_object(self, logger):
        class FakeResponse:
            eval_count = 10

        logger.model_response("x", [], response=FakeResponse())
        events = read_events(logger.path)
        assert events[-1]["eval_count"] == 10

    @pytest.mark.tid("CHATLOG-018")
    def test_tool_call_returns_start_time_token(self, logger):
        token = logger.tool_call("read_file", {"path": "a.txt"})
        assert isinstance(token, float)
        events = read_events(logger.path)
        assert events[-1]["event"] == "tool_call"
        assert events[-1]["tool"] == "read_file"

    @pytest.mark.tid("CHATLOG-019")
    def test_tool_result_logs_elapsed_and_error_flag(self, logger):
        start = logger.tool_call("read_file", {})
        logger.tool_result("read_file", "contents", start, error=False)
        events = read_events(logger.path)
        assert events[-1]["event"] == "tool_result"
        assert events[-1]["error"] is False
        assert events[-1]["elapsed_ms"] >= 0

    @pytest.mark.tid("CHATLOG-020")
    def test_loop_limit_hit_logs_max_iterations(self, logger):
        logger.loop_limit_hit(40)
        events = read_events(logger.path)
        assert events[-1]["event"] == "loop_limit_hit"
        assert events[-1]["max_iterations"] == 40

    @pytest.mark.tid("CHATLOG-021")
    def test_error_logs_message_and_context(self, logger):
        logger.error("boom", detail="stack trace here")
        events = read_events(logger.path)
        assert events[-1]["message"] == "boom"
        assert events[-1]["detail"] == "stack trace here"

    @pytest.mark.tid("CHATLOG-022")
    def test_session_end_default_reason(self, logger):
        logger.session_end()
        events = read_events(logger.path)
        assert events[-1]["reason"] == "user_exit"

    @pytest.mark.tid("CHATLOG-023")
    def test_session_end_custom_reason(self, logger):
        logger.session_end(reason="crashed")
        events = read_events(logger.path)
        assert events[-1]["reason"] == "crashed"

    @pytest.mark.tid("CHATLOG-024")
    def test_unserializable_field_logs_stub_not_crash(self, logger):
        class Poison:
            def __str__(self):
                raise TypeError("cannot stringify")

        logger.error("weird", payload=Poison())
        events = read_events(logger.path)
        assert "log_error" in events[-1] or events[-1]["event"] == "error"

    @pytest.mark.tid("CHATLOG-025")
    def test_write_failure_does_not_raise(self, logger, monkeypatch):
        def boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(type(logger.path), "open", boom)
        logger.error("should not crash")  # must not raise

    @pytest.mark.tid("CHATLOG-026")
    def test_echo_to_terminal_prints(self, logger, monkeypatch, capsys):
        monkeypatch.setattr(cfg, "ECHO_TO_TERMINAL", True)
        logger.error("visible")
        captured = capsys.readouterr()
        assert "[log] error" in captured.out


class TestChatLoggerRotation:
    @pytest.mark.tid("CHATLOG-027")
    def test_rotates_when_exceeding_max_bytes(self, isolated_log_dir, monkeypatch):
        monkeypatch.setattr(cfg, "MAX_LOG_FILE_BYTES", 1)  # rotate almost immediately
        logger = ChatLogger("agent", "model")
        original_path = logger.path
        logger.user_message("this line pushes the file over the tiny limit")
        rotated_files = list(isolated_log_dir.glob("logs/*.jsonl"))
        # Original filename should exist again (new file after rotation)
        # plus at least one rotated backup.
        assert original_path.exists()
        assert len(rotated_files) >= 2

    @pytest.mark.tid("CHATLOG-028")
    def test_rotation_disabled_when_limit_is_none(self, isolated_log_dir, monkeypatch):
        monkeypatch.setattr(cfg, "MAX_LOG_FILE_BYTES", None)
        logger = ChatLogger("agent", "model")
        for i in range(50):
            logger.user_message(f"message {i}")
        assert len(list(isolated_log_dir.glob("logs/*.jsonl"))) == 1


# --------------------------------------------------------------------------
# NullChatLogger
# --------------------------------------------------------------------------

class TestNullChatLogger:
    @pytest.mark.tid("CHATLOG-029")
    def test_all_methods_are_no_ops_and_never_raise(self):
        logger = NullChatLogger()
        logger.user_message("x")
        logger.model_call_start(1, [])
        logger.model_response("x", [])
        assert logger.tool_call("x", {}) == 0.0
        logger.tool_result("x", "y", 0.0)
        logger.loop_limit_hit(1)
        logger.error("x")
        logger.session_end()


# --------------------------------------------------------------------------
# get_logger
# --------------------------------------------------------------------------

class TestGetLogger:
    @pytest.mark.tid("CHATLOG-030")
    def test_returns_null_logger_when_disabled(self, monkeypatch):
        monkeypatch.setattr(cfg, "LOG_ENABLED", False)
        logger = get_logger("agent", "model")
        assert isinstance(logger, NullChatLogger)

    @pytest.mark.tid("CHATLOG-031")
    def test_returns_real_logger_when_enabled(self, isolated_log_dir):
        logger = get_logger("agent", "model")
        assert isinstance(logger, ChatLogger)

    @pytest.mark.tid("CHATLOG-032")
    def test_falls_back_to_null_logger_on_init_failure(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("read-only filesystem")

        monkeypatch.setattr(cl_mod, "ChatLogger", boom)
        logger = get_logger("agent", "model")
        assert isinstance(logger, NullChatLogger)
