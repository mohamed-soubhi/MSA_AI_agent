"""Tests for auto_runner.py — plan once, approve once, run to the end.

OllamaAgent.chat, confirm(), fs_tools.resolve_path (via auto_runner's
own import), and shared.run_agent are all mocked -- no live model,
real filesystem writes, or terminal prompts.
"""

from types import SimpleNamespace

import pytest

import agent_mode
import auto_runner as ar_mod
from auto_runner import MAX_AUTO_TOOL_CALLS, _generate_plan, run_with_auto_mode


@pytest.fixture(autouse=True)
def reset_auto_mode():
    agent_mode.AUTO_MODE = False
    yield
    agent_mode.AUTO_MODE = False


class FakeAgent:
    def __init__(self, plan_content="1. Do the thing.", chat_side_effect=None):
        self.plan_content = plan_content
        self.chat_calls = []
        self.chat_side_effect = chat_side_effect

    def chat(self, messages, tools=None):
        self.chat_calls.append({"messages": messages, "tools": tools})
        if self.chat_side_effect:
            raise self.chat_side_effect
        return SimpleNamespace(message=SimpleNamespace(content=self.plan_content))


class TestGeneratePlan:
    @pytest.mark.tid("AUTORUN-001")
    def test_passes_tools_none_during_planning(self):
        agent = FakeAgent(plan_content="1. Create file.")
        _generate_plan(agent, "build a todo app")
        assert agent.chat_calls[0]["tools"] is None

    @pytest.mark.tid("AUTORUN-002")
    def test_returns_model_plan_text(self):
        agent = FakeAgent(plan_content="1. Step one.\n2. Step two.")
        result = _generate_plan(agent, "do something")
        assert result == "1. Step one.\n2. Step two."

    @pytest.mark.tid("AUTORUN-003")
    def test_empty_plan_falls_back_to_placeholder(self):
        agent = FakeAgent(plan_content=None)
        result = _generate_plan(agent, "do something")
        assert result == "(model returned an empty plan)"

    @pytest.mark.tid("AUTORUN-004")
    def test_includes_user_request_in_planning_prompt(self):
        agent = FakeAgent(plan_content="plan")
        _generate_plan(agent, "build a REST API")
        prompt = agent.chat_calls[0]["messages"][0]["content"]
        assert "build a REST API" in prompt


class TestRunWithAutoMode:
    @pytest.mark.tid("AUTORUN-005")
    def test_writes_plan_to_sandboxed_path(self, monkeypatch, tmp_path):
        import fs_tools
        monkeypatch.setattr(fs_tools, "resolve_path", lambda path: tmp_path / path)
        monkeypatch.setattr(ar_mod, "confirm", lambda action, **kwargs: False)

        agent = FakeAgent(plan_content="1. Write hello.py.")
        run_with_auto_mode(agent, "make a script", tools=[], tool_map={})

        plan_file = tmp_path / "plan.md"
        assert plan_file.read_text() == "1. Write hello.py."

    @pytest.mark.tid("AUTORUN-006")
    def test_plan_write_failure_does_not_block_review(self, monkeypatch, tmp_path, capsys):
        import fs_tools

        def raise_on_resolve(path):
            class BoomPath:
                def write_text(self, *a, **k):
                    raise OSError("disk full")

                def __str__(self):
                    return str(tmp_path / path)

            return BoomPath()

        monkeypatch.setattr(fs_tools, "resolve_path", raise_on_resolve)
        monkeypatch.setattr(ar_mod, "confirm", lambda action, **kwargs: False)

        agent = FakeAgent(plan_content="1. Do it.")
        result = run_with_auto_mode(agent, "do something", tools=[], tool_map={})

        assert result == "Plan not approved — nothing was run."
        captured = capsys.readouterr()
        assert "could not write plan.md" in captured.out

    @pytest.mark.tid("AUTORUN-007")
    def test_rejected_plan_returns_message_and_leaves_step_mode(self, monkeypatch, tmp_path):
        import fs_tools
        monkeypatch.setattr(fs_tools, "resolve_path", lambda path: tmp_path / path)
        monkeypatch.setattr(ar_mod, "confirm", lambda action, **kwargs: False)

        agent = FakeAgent(plan_content="1. Do it.")
        result = run_with_auto_mode(agent, "do something", tools=[], tool_map={})

        assert result == "Plan not approved — nothing was run."
        assert agent_mode.AUTO_MODE is False

    @pytest.mark.tid("AUTORUN-008")
    def test_approval_prompt_uses_force_ask(self, monkeypatch, tmp_path):
        import fs_tools
        monkeypatch.setattr(fs_tools, "resolve_path", lambda path: tmp_path / path)
        seen = {}

        def fake_confirm(action, **kwargs):
            seen["action"] = action
            seen["kwargs"] = kwargs
            return False

        monkeypatch.setattr(ar_mod, "confirm", fake_confirm)

        agent = FakeAgent(plan_content="1. Do it.")
        run_with_auto_mode(agent, "do something", tools=[], tool_map={})

        assert seen["kwargs"] == {"force_ask": True}

    @pytest.mark.tid("AUTORUN-009")
    def test_approved_plan_sets_auto_mode_and_calls_run_agent(self, monkeypatch, tmp_path):
        import fs_tools
        monkeypatch.setattr(fs_tools, "resolve_path", lambda path: tmp_path / path)
        monkeypatch.setattr(ar_mod, "confirm", lambda action, **kwargs: True)

        seen_auto_mode_during_call = {}

        def fake_run_agent(agent, messages, tools, tool_map, chat_logger=None, max_tool_calls=None):
            seen_auto_mode_during_call["value"] = agent_mode.AUTO_MODE
            seen_auto_mode_during_call["max_tool_calls"] = max_tool_calls
            seen_auto_mode_during_call["messages"] = messages
            return "Executed successfully."

        monkeypatch.setattr(ar_mod, "run_agent", fake_run_agent)

        agent = FakeAgent(plan_content="1. Do it.")
        result = run_with_auto_mode(agent, "do something", tools=["t"], tool_map={"t": lambda: None})

        assert result == "Executed successfully."
        assert seen_auto_mode_during_call["value"] is True
        assert seen_auto_mode_during_call["max_tool_calls"] == MAX_AUTO_TOOL_CALLS
        assert len(seen_auto_mode_during_call["messages"]) == 3

    @pytest.mark.tid("AUTORUN-010")
    def test_auto_mode_reset_to_false_after_successful_run(self, monkeypatch, tmp_path):
        import fs_tools
        monkeypatch.setattr(fs_tools, "resolve_path", lambda path: tmp_path / path)
        monkeypatch.setattr(ar_mod, "confirm", lambda action, **kwargs: True)
        monkeypatch.setattr(ar_mod, "run_agent", lambda *a, **k: "done")

        agent = FakeAgent(plan_content="1. Do it.")
        run_with_auto_mode(agent, "do something", tools=[], tool_map={})

        assert agent_mode.AUTO_MODE is False

    @pytest.mark.tid("AUTORUN-011")
    def test_auto_mode_reset_to_false_even_if_run_agent_raises(self, monkeypatch, tmp_path):
        import fs_tools
        monkeypatch.setattr(fs_tools, "resolve_path", lambda path: tmp_path / path)
        monkeypatch.setattr(ar_mod, "confirm", lambda action, **kwargs: True)

        def raising_run_agent(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(ar_mod, "run_agent", raising_run_agent)

        agent = FakeAgent(plan_content="1. Do it.")
        with pytest.raises(RuntimeError, match="boom"):
            run_with_auto_mode(agent, "do something", tools=[], tool_map={})

        assert agent_mode.AUTO_MODE is False

    @pytest.mark.tid("AUTORUN-012")
    def test_plan_text_included_in_execution_messages(self, monkeypatch, tmp_path):
        import fs_tools
        monkeypatch.setattr(fs_tools, "resolve_path", lambda path: tmp_path / path)
        monkeypatch.setattr(ar_mod, "confirm", lambda action, **kwargs: True)

        captured_messages = {}

        def fake_run_agent(agent, messages, tools, tool_map, chat_logger=None, max_tool_calls=None):
            captured_messages["messages"] = messages
            return "done"

        monkeypatch.setattr(ar_mod, "run_agent", fake_run_agent)

        agent = FakeAgent(plan_content="1. Write hello.py.\n2. Run it.")
        run_with_auto_mode(agent, "build a script", tools=[], tool_map={})

        messages = captured_messages["messages"]
        assert messages[0] == {"role": "user", "content": "build a script"}
        assert "1. Write hello.py." in messages[1]["content"]
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
