"""Tests for 09_full_agent.py — the single CLI entry point.

Merges what were previously two separate entry points
(07_filesystem_tools.py, 08_terminal_tools.py, both now removed) into
one agent offering seven tools. Filename starts with a digit, so it's
loaded via importlib. OllamaAgent, get_logger, run_agent, and input()
are all mocked -- no live Ollama server needed.
"""

import importlib.util
import os
import sys
from unittest.mock import MagicMock

import pytest

MODULE_PATH = os.path.join(os.path.dirname(__file__), "..", "09_full_agent.py")


def load_module():
    spec = importlib.util.spec_from_file_location("full_agent_main", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["full_agent_main"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def full_main():
    return load_module()


@pytest.fixture
def mocked_agent(full_main, monkeypatch):
    fake_agent = MagicMock()
    fake_agent.model = "test-model"
    monkeypatch.setattr(full_main, "OllamaAgent", lambda: fake_agent)
    return fake_agent


@pytest.fixture
def mocked_logger(full_main, monkeypatch):
    fake_logger = MagicMock()
    monkeypatch.setattr(full_main, "get_logger", lambda *a, **k: fake_logger)
    return fake_logger


class TestMain:
    @pytest.mark.tid("FULLAGENT-001")
    def test_exit_command_ends_session_cleanly(
        self, full_main, mocked_agent, mocked_logger, monkeypatch
    ):
        monkeypatch.setattr("builtins.input", lambda prompt: "exit")
        monkeypatch.setattr(full_main, "run_agent", MagicMock())

        full_main.main()

        mocked_logger.session_end.assert_called_once_with(reason="user_exit")
        full_main.run_agent.assert_not_called()

    @pytest.mark.parametrize("cmd", ["exit", "quit", "q", "EXIT", "Quit"])
    @pytest.mark.tid("FULLAGENT-002")
    def test_exit_synonyms_case_insensitive(
        self, full_main, mocked_agent, mocked_logger, monkeypatch, cmd
    ):
        monkeypatch.setattr("builtins.input", lambda prompt: cmd)
        monkeypatch.setattr(full_main, "run_agent", MagicMock())

        full_main.main()

        mocked_logger.session_end.assert_called_once_with(reason="user_exit")

    @pytest.mark.tid("FULLAGENT-003")
    def test_user_message_is_logged_and_agent_is_run(
        self, full_main, mocked_agent, mocked_logger, monkeypatch, capsys
    ):
        inputs = iter(["build a todo app", "exit"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
        fake_run_agent = MagicMock(return_value="Done.")
        monkeypatch.setattr(full_main, "run_agent", fake_run_agent)

        full_main.main()

        mocked_logger.user_message.assert_called_once_with("build a todo app")
        fake_run_agent.assert_called_once()
        captured = capsys.readouterr()
        assert "Done." in captured.out

    @pytest.mark.tid("FULLAGENT-004")
    def test_system_prompt_seeded_as_first_message(
        self, full_main, mocked_agent, mocked_logger, monkeypatch
    ):
        inputs = iter(["hello", "exit"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
        fake_run_agent = MagicMock(return_value="ok")
        monkeypatch.setattr(full_main, "run_agent", fake_run_agent)

        full_main.main()

        messages_arg = fake_run_agent.call_args[0][1]
        assert messages_arg[0] == {"role": "system", "content": full_main.SYSTEM_PROMPT}

    @pytest.mark.tid("FULLAGENT-005")
    def test_keyboard_interrupt_during_input_ends_session(
        self, full_main, mocked_agent, mocked_logger, monkeypatch
    ):
        def raise_kbi(prompt):
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", raise_kbi)

        full_main.main()

        mocked_logger.session_end.assert_called_once_with(reason="keyboard_interrupt")

    @pytest.mark.tid("FULLAGENT-006")
    def test_unexpected_exception_is_logged_and_reraised(
        self, full_main, mocked_agent, mocked_logger, monkeypatch
    ):
        inputs = iter(["do something"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
        monkeypatch.setattr(
            full_main, "run_agent", MagicMock(side_effect=RuntimeError("model exploded"))
        )

        with pytest.raises(RuntimeError, match="model exploded"):
            full_main.main()

        mocked_logger.error.assert_called_once()
        mocked_logger.session_end.assert_called_once_with(reason="crashed")

    @pytest.mark.tid("FULLAGENT-007")
    def test_tool_map_wires_all_seven_real_functions(self, full_main):
        assert full_main.list_directory.__name__ == "list_directory"
        assert full_main.read_file.__name__ == "read_file"
        assert full_main.write_file.__name__ == "write_file"
        assert full_main.create_directory.__name__ == "create_directory"
        assert full_main.run_command.__name__ == "run_command"
        assert full_main.ask_human.__name__ == "ask_human"
        assert full_main.ask_human_choice.__name__ == "ask_human_choice"

    @pytest.mark.tid("FULLAGENT-008")
    def test_run_agent_is_offered_exactly_seven_tools(
        self, full_main, mocked_agent, mocked_logger, monkeypatch
    ):
        inputs = iter(["hello", "exit"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
        fake_run_agent = MagicMock(return_value="ok")
        monkeypatch.setattr(full_main, "run_agent", fake_run_agent)

        full_main.main()

        tools_arg = fake_run_agent.call_args[0][2]
        tool_names = {t.__name__ for t in tools_arg}
        assert tool_names == {
            "list_directory", "read_file", "write_file", "create_directory",
            "run_command", "ask_human", "ask_human_choice",
        }

    @pytest.mark.tid("FULLAGENT-009")
    def test_step_mode_default_calls_run_agent_not_auto(
        self, full_main, mocked_agent, mocked_logger, monkeypatch
    ):
        assert full_main.auto_mode is False
        inputs = iter(["hello", "exit"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
        fake_run_agent = MagicMock(return_value="ok")
        fake_auto = MagicMock()
        monkeypatch.setattr(full_main, "run_agent", fake_run_agent)
        monkeypatch.setattr(full_main, "run_with_auto_mode", fake_auto)

        full_main.main()

        fake_run_agent.assert_called_once()
        fake_auto.assert_not_called()

    @pytest.mark.tid("FULLAGENT-010")
    def test_auto_mode_true_calls_run_with_auto_mode_not_run_agent(
        self, full_main, mocked_agent, mocked_logger, monkeypatch
    ):
        monkeypatch.setattr(full_main, "auto_mode", True)
        inputs = iter(["build a todo app", "exit"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
        fake_run_agent = MagicMock()
        fake_auto = MagicMock(return_value="Plan approved and executed.")
        monkeypatch.setattr(full_main, "run_agent", fake_run_agent)
        monkeypatch.setattr(full_main, "run_with_auto_mode", fake_auto)

        full_main.main()

        fake_auto.assert_called_once()
        fake_run_agent.assert_not_called()
        # user_input, tools, tool_map, chat_logger=... -- not the mutated
        # `messages` list, since run_with_auto_mode manages its own.
        args, kwargs = fake_auto.call_args
        assert args[1] == "build a todo app"
        assert kwargs["chat_logger"] is mocked_logger

    @pytest.mark.tid("FULLAGENT-011")
    def test_auto_mode_answer_is_printed(
        self, full_main, mocked_agent, mocked_logger, monkeypatch, capsys
    ):
        monkeypatch.setattr(full_main, "auto_mode", True)
        inputs = iter(["hello", "exit"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
        monkeypatch.setattr(
            full_main, "run_with_auto_mode", MagicMock(return_value="Plan not approved.")
        )

        full_main.main()

        captured = capsys.readouterr()
        assert "Plan not approved." in captured.out
