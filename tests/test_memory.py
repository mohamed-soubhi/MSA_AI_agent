"""Tests for memory.py -- persistent, JSON-backed agent memory.

remember_fact/recall_memory are model-invoked tools (same shape as
human_tools.py); save_session_summary() is host-invoked only, called
by 09_full_agent.py at session end. Every test points memory.MEMORY_PATH
at an isolated tmp file so nothing touches the real memory.json.
"""

import json

import pytest

import memory as mem_mod
from memory import recall_memory, remember_fact, save_session_summary


@pytest.fixture(autouse=True)
def isolated_memory_file(tmp_path, monkeypatch):
    """Point MEMORY_PATH at an isolated tmp file for every test in this file."""
    monkeypatch.setattr(mem_mod, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(mem_mod, "MEMORY_ENABLED", True)


def _read_entries(path):
    return json.loads(path.read_text(encoding="utf-8"))["entries"]


# --------------------------------------------------------------------------
# remember_fact
# --------------------------------------------------------------------------

class TestRememberFact:
    @pytest.mark.tid("MEMORY-001")
    def test_saves_fact_to_disk(self):
        remember_fact("User prefers pytest over unittest.")
        entries = _read_entries(mem_mod.MEMORY_PATH)
        assert len(entries) == 1
        assert entries[0]["text"] == "User prefers pytest over unittest."
        assert entries[0]["type"] == "fact"

    @pytest.mark.tid("MEMORY-002")
    def test_returns_confirmation_with_id_and_text(self):
        result = remember_fact("Project uses Ollama cloud models.")
        assert "Remembered" in result
        assert "Project uses Ollama cloud models." in result

    @pytest.mark.tid("MEMORY-003")
    def test_empty_text_returns_error_without_writing(self):
        result = remember_fact("")
        assert result.startswith("Error")
        assert not mem_mod.MEMORY_PATH.exists()

    @pytest.mark.tid("MEMORY-004")
    def test_whitespace_only_text_returns_error(self):
        result = remember_fact("   ")
        assert result.startswith("Error")

    @pytest.mark.tid("MEMORY-005")
    def test_tags_are_lowercased_and_deduped(self):
        remember_fact("fact text", tags=["Testing", "testing", " Prefs "])
        entries = _read_entries(mem_mod.MEMORY_PATH)
        assert entries[0]["tags"] == ["prefs", "testing"]

    @pytest.mark.tid("MEMORY-006")
    def test_text_truncated_to_max_chars(self, monkeypatch):
        monkeypatch.setattr(mem_mod, "MEMORY_MAX_TEXT_CHARS", 10)
        remember_fact("this text is way too long to keep in full")
        entries = _read_entries(mem_mod.MEMORY_PATH)
        assert len(entries[0]["text"]) == 10

    @pytest.mark.tid("MEMORY-007")
    def test_disabled_memory_does_not_write(self, monkeypatch):
        monkeypatch.setattr(mem_mod, "MEMORY_ENABLED", False)
        result = remember_fact("anything")
        assert "disabled" in result.lower()
        assert not mem_mod.MEMORY_PATH.exists()

    @pytest.mark.tid("MEMORY-008")
    def test_second_call_appends_not_overwrites(self):
        remember_fact("first fact")
        remember_fact("second fact")
        entries = _read_entries(mem_mod.MEMORY_PATH)
        assert len(entries) == 2

    @pytest.mark.tid("MEMORY-009")
    def test_entries_trimmed_to_max_entries(self, monkeypatch):
        monkeypatch.setattr(mem_mod, "MEMORY_MAX_ENTRIES", 3)
        for i in range(5):
            remember_fact(f"fact {i}")
        entries = _read_entries(mem_mod.MEMORY_PATH)
        assert len(entries) == 3
        assert [e["text"] for e in entries] == ["fact 2", "fact 3", "fact 4"]


# --------------------------------------------------------------------------
# recall_memory
# --------------------------------------------------------------------------

class TestRecallMemory:
    @pytest.mark.tid("MEMORY-010")
    def test_no_memories_saved_yet(self):
        result = recall_memory()
        assert "no memories" in result.lower()

    @pytest.mark.tid("MEMORY-011")
    def test_empty_query_returns_all_recent_entries(self):
        remember_fact("fact one")
        remember_fact("fact two")
        result = recall_memory()
        assert "fact one" in result
        assert "fact two" in result

    @pytest.mark.tid("MEMORY-012")
    def test_substring_query_filters_matches(self):
        remember_fact("User prefers dark mode.")
        remember_fact("Project deploys to AWS.")
        result = recall_memory(query="dark mode")
        assert "dark mode" in result
        assert "AWS" not in result

    @pytest.mark.tid("MEMORY-013")
    def test_query_is_case_insensitive(self):
        remember_fact("User prefers Dark Mode.")
        result = recall_memory(query="dark mode")
        assert "Dark Mode" in result

    @pytest.mark.tid("MEMORY-014")
    def test_no_match_returns_explicit_message(self):
        remember_fact("fact about testing")
        result = recall_memory(query="nonexistent topic")
        assert "no memories matched" in result.lower()

    @pytest.mark.tid("MEMORY-015")
    def test_tag_filter_matches_any_tag(self):
        remember_fact("fact A", tags=["testing"])
        remember_fact("fact B", tags=["deployment"])
        result = recall_memory(tags=["testing"])
        assert "fact A" in result
        assert "fact B" not in result

    @pytest.mark.tid("MEMORY-016")
    def test_query_and_tag_filter_combine_with_and(self):
        remember_fact("prefers pytest", tags=["testing"])
        remember_fact("prefers pytest", tags=["deployment"])
        result = recall_memory(query="pytest", tags=["testing"])
        assert result.count("prefers pytest") == 1

    @pytest.mark.tid("MEMORY-017")
    def test_results_capped_at_max_recall_results(self, monkeypatch):
        monkeypatch.setattr(mem_mod, "MEMORY_MAX_RECALL_RESULTS", 2)
        for i in range(5):
            remember_fact(f"fact {i}")
        result = recall_memory()
        assert result.count("fact ") == 2
        assert "fact 3" in result and "fact 4" in result

    @pytest.mark.tid("MEMORY-018")
    def test_disabled_memory_returns_disabled_message(self, monkeypatch):
        monkeypatch.setattr(mem_mod, "MEMORY_ENABLED", False)
        result = recall_memory()
        assert "disabled" in result.lower()

    @pytest.mark.tid("MEMORY-019")
    def test_corrupt_memory_file_treated_as_empty(self):
        mem_mod.MEMORY_PATH.write_text("not valid json", encoding="utf-8")
        result = recall_memory()
        assert "no memories" in result.lower()

    @pytest.mark.tid("MEMORY-026")
    def test_corrupt_memory_file_backed_up_before_wipe(self):
        # ROB-02: don't let the next remember_fact() silently destroy
        # the only copy of a corrupted-but-maybe-salvageable file.
        mem_mod.MEMORY_PATH.write_text("not valid json {{{", encoding="utf-8")
        recall_memory()
        backup_path = mem_mod.MEMORY_PATH.with_suffix(mem_mod.MEMORY_PATH.suffix + ".corrupt.bak")
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == "not valid json {{{"

    @pytest.mark.tid("MEMORY-027")
    def test_missing_file_produces_no_backup(self):
        recall_memory()
        backup_path = mem_mod.MEMORY_PATH.with_suffix(mem_mod.MEMORY_PATH.suffix + ".corrupt.bak")
        assert not backup_path.exists()


class TestAtomicWrite:
    @pytest.mark.tid("MEMORY-028")
    def test_save_uses_os_replace_not_direct_write(self, monkeypatch):
        # ROB-02: _save() must go through a temp file + os.replace(),
        # not a direct write_text() that can be interrupted mid-write.
        calls = []
        real_replace = mem_mod.os.replace

        def spy_replace(src, dst):
            calls.append((str(src), str(dst)))
            return real_replace(src, dst)

        monkeypatch.setattr(mem_mod.os, "replace", spy_replace)
        remember_fact("fact one")
        assert len(calls) == 1
        src, dst = calls[0]
        assert dst == str(mem_mod.MEMORY_PATH)
        assert src != dst  # temp file, not the real path directly

    @pytest.mark.tid("MEMORY-029")
    def test_no_leftover_temp_file_after_save(self):
        remember_fact("fact one")
        leftovers = list(mem_mod.MEMORY_PATH.parent.glob(f"{mem_mod.MEMORY_PATH.name}.tmp*"))
        assert leftovers == []

    @pytest.mark.tid("MEMORY-030")
    def test_final_file_is_valid_json_after_multiple_saves(self):
        for i in range(3):
            remember_fact(f"fact {i}")
        # A successful atomic replace always leaves valid, complete JSON.
        entries = _read_entries(mem_mod.MEMORY_PATH)
        assert len(entries) == 3


# --------------------------------------------------------------------------
# save_session_summary
# --------------------------------------------------------------------------

class FakeAgent:
    def __init__(self, content="Built a todo app; user prefers dark mode."):
        self.chat_calls = []
        self._content = content

    def chat(self, messages, tools=None):
        self.chat_calls.append((messages, tools))
        response = type("R", (), {})()
        response.message = type("M", (), {"content": self._content})()
        return response


class TestSaveSessionSummary:
    @pytest.mark.tid("MEMORY-020")
    def test_saves_summary_entry_when_enough_turns(self):
        agent = FakeAgent()
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "build a todo app"},
            {"role": "assistant", "content": "done"},
        ]
        save_session_summary(agent, messages)
        entries = _read_entries(mem_mod.MEMORY_PATH)
        assert len(entries) == 1
        assert entries[0]["type"] == "summary"
        assert "todo app" in entries[0]["text"]

    @pytest.mark.tid("MEMORY-021")
    def test_skips_when_fewer_than_two_real_turns(self):
        agent = FakeAgent()
        messages = [{"role": "system", "content": "sys"}]
        save_session_summary(agent, messages)
        assert agent.chat_calls == []
        assert not mem_mod.MEMORY_PATH.exists()

    @pytest.mark.tid("MEMORY-022")
    def test_summarizer_call_offers_no_tools(self):
        agent = FakeAgent()
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        save_session_summary(agent, messages)
        _, tools = agent.chat_calls[0]
        assert tools is None

    @pytest.mark.tid("MEMORY-023")
    def test_chat_failure_is_swallowed_not_raised(self):
        class BrokenAgent:
            def chat(self, messages, tools=None):
                raise RuntimeError("network down")

        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        save_session_summary(BrokenAgent(), messages)  # must not raise
        assert not mem_mod.MEMORY_PATH.exists()

    @pytest.mark.tid("MEMORY-024")
    def test_empty_summary_content_writes_nothing(self):
        agent = FakeAgent(content="")
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        save_session_summary(agent, messages)
        assert not mem_mod.MEMORY_PATH.exists()

    @pytest.mark.tid("MEMORY-031")
    def test_summarizer_call_windowed_to_recent_messages(self, monkeypatch):
        # ROB-04: a long conversation must not send its entire history
        # to the model in the automatic shutdown-time summary call.
        monkeypatch.setattr(mem_mod, "MEMORY_SUMMARY_MAX_MESSAGES", 4)
        agent = FakeAgent()
        messages = [{"role": "system", "content": "sys"}] + [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
            for i in range(10)
        ]
        save_session_summary(agent, messages)
        sent_messages, _ = agent.chat_calls[0]
        # 4 windowed messages + 1 appended summarization request = 5.
        assert len(sent_messages) == 5
        assert sent_messages[0]["content"] == "turn 6"
        assert sent_messages[-2]["content"] == "turn 9"

    @pytest.mark.tid("MEMORY-032")
    def test_short_conversation_under_window_sent_in_full(self):
        agent = FakeAgent()
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        save_session_summary(agent, messages)
        sent_messages, _ = agent.chat_calls[0]
        assert len(sent_messages) == 4  # all 3 original + 1 appended request

    @pytest.mark.tid("MEMORY-025")
    def test_disabled_memory_skips_entirely(self, monkeypatch):
        monkeypatch.setattr(mem_mod, "MEMORY_ENABLED", False)
        agent = FakeAgent()
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        save_session_summary(agent, messages)
        assert agent.chat_calls == []
