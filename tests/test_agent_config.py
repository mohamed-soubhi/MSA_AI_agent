"""Tests for agent_config.py — env-var-overridable settings for every
agent module (chat/network, tool loop, filesystem, shell, confirm,
auto mode). Mirrors log_config.py's own test style.
"""

import pytest

import agent_config as cfg
from agent_config import _env_bool, _env_int, _env_int_or_none, _env_list, _env_set


class TestEnvBool:
    @pytest.mark.tid("AGENTCFG-001")
    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "YES", "on", "  true  "])
    def test_truthy_values(self, monkeypatch, raw):
        monkeypatch.setenv("SOME_FLAG", raw)
        assert _env_bool("SOME_FLAG", False) is True

    @pytest.mark.tid("AGENTCFG-002")
    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", "", "banana"])
    def test_falsy_or_unrecognized_values(self, monkeypatch, raw):
        monkeypatch.setenv("SOME_FLAG", raw)
        assert _env_bool("SOME_FLAG", True) is False

    @pytest.mark.tid("AGENTCFG-003")
    def test_missing_env_var_uses_default(self, monkeypatch):
        monkeypatch.delenv("SOME_FLAG", raising=False)
        assert _env_bool("SOME_FLAG", True) is True
        assert _env_bool("SOME_FLAG", False) is False


class TestEnvInt:
    @pytest.mark.tid("AGENTCFG-004")
    def test_missing_env_var_uses_default(self, monkeypatch):
        monkeypatch.delenv("SOME_INT", raising=False)
        assert _env_int("SOME_INT", 42) == 42

    @pytest.mark.tid("AGENTCFG-005")
    def test_numeric_string_parsed(self, monkeypatch):
        monkeypatch.setenv("SOME_INT", "99")
        assert _env_int("SOME_INT", 42) == 99

    @pytest.mark.tid("AGENTCFG-006")
    def test_non_numeric_string_falls_back_to_default(self, monkeypatch):
        # ROB-05: a malformed env var degrades to the default instead of
        # crashing agent startup.
        monkeypatch.setenv("SOME_INT", "not-a-number")
        assert _env_int("SOME_INT", 42) == 42

    @pytest.mark.tid("AGENTCFG-027")
    def test_non_numeric_string_logs_a_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("SOME_INT", "not-a-number")
        with caplog.at_level("WARNING", logger="agent.config"):
            _env_int("SOME_INT", 42)
        assert any("env_int_invalid" in record.message for record in caplog.records)


class TestEnvIntOrNone:
    @pytest.mark.tid("AGENTCFG-007")
    def test_missing_env_var_uses_default(self, monkeypatch):
        monkeypatch.delenv("SOME_INT", raising=False)
        assert _env_int_or_none("SOME_INT", 42) == 42
        assert _env_int_or_none("SOME_INT", None) is None

    @pytest.mark.tid("AGENTCFG-008")
    @pytest.mark.parametrize("raw", ["none", "None", "NONE", "  none  "])
    def test_literal_none_string(self, monkeypatch, raw):
        monkeypatch.setenv("SOME_INT", raw)
        assert _env_int_or_none("SOME_INT", 42) is None

    @pytest.mark.tid("AGENTCFG-009")
    def test_numeric_string_parsed(self, monkeypatch):
        monkeypatch.setenv("SOME_INT", "12345")
        assert _env_int_or_none("SOME_INT", 42) == 12345

    @pytest.mark.tid("AGENTCFG-010")
    def test_non_numeric_string_raises(self, monkeypatch):
        monkeypatch.setenv("SOME_INT", "nope")
        with pytest.raises(ValueError):
            _env_int_or_none("SOME_INT", 42)


class TestEnvSet:
    @pytest.mark.tid("AGENTCFG-011")
    def test_missing_env_var_uses_default(self, monkeypatch):
        monkeypatch.delenv("SOME_SET", raising=False)
        default = {"a", "b"}
        assert _env_set("SOME_SET", default) == default

    @pytest.mark.tid("AGENTCFG-012")
    def test_comma_separated_parsed_into_set(self, monkeypatch):
        monkeypatch.setenv("SOME_SET", "python,node,ls")
        assert _env_set("SOME_SET", set()) == {"python", "node", "ls"}

    @pytest.mark.tid("AGENTCFG-013")
    def test_whitespace_trimmed_and_empty_items_dropped(self, monkeypatch):
        monkeypatch.setenv("SOME_SET", " python , , node ,")
        assert _env_set("SOME_SET", set()) == {"python", "node"}

    @pytest.mark.tid("AGENTCFG-014")
    def test_returns_a_set_type(self, monkeypatch):
        monkeypatch.setenv("SOME_SET", "a,b")
        assert isinstance(_env_set("SOME_SET", set()), set)


class TestEnvList:
    @pytest.mark.tid("AGENTCFG-015")
    def test_missing_env_var_uses_default(self, monkeypatch):
        monkeypatch.delenv("SOME_LIST", raising=False)
        default = ["a", "b"]
        assert _env_list("SOME_LIST", default) == default

    @pytest.mark.tid("AGENTCFG-016")
    def test_order_is_preserved(self, monkeypatch):
        monkeypatch.setenv("SOME_LIST", "z,a,m")
        assert _env_list("SOME_LIST", []) == ["z", "a", "m"]

    @pytest.mark.tid("AGENTCFG-017")
    def test_whitespace_trimmed_and_empty_items_dropped(self, monkeypatch):
        monkeypatch.setenv("SOME_LIST", " rm , , sudo ,")
        assert _env_list("SOME_LIST", []) == ["rm", "sudo"]

    @pytest.mark.tid("AGENTCFG-018")
    def test_returns_a_list_type(self, monkeypatch):
        monkeypatch.setenv("SOME_LIST", "a,b")
        assert isinstance(_env_list("SOME_LIST", []), list)


class TestDefaultConstants:
    """Spot checks that module constants resolve to their documented
    defaults when no env vars override them (catches drift from
    doc/agent_config.md and accidental hardcoded overrides)."""

    @pytest.mark.tid("AGENTCFG-019")
    def test_chat_and_loop_defaults(self):
        assert cfg.CHAT_TIMEOUT_SECONDS == 60
        assert cfg.CHAT_MAX_RETRIES == 2
        assert cfg.CHAT_RETRY_BACKOFF_SECONDS == 2
        assert cfg.MAX_ITERATIONS == 40
        assert cfg.MAX_WALL_SECONDS == 600
        assert cfg.TOOL_TIMEOUT_SECONDS == 30
        assert cfg.MAX_REPEAT_CALLS == 3
        assert cfg.MAX_OBSERVATION_CHARS == 4000

    @pytest.mark.tid("AGENTCFG-020")
    def test_fs_tools_defaults(self):
        assert cfg.MAX_WRITE_BYTES == 2_000_000
        assert cfg.REQUIRE_CONFIRMATION is True

    @pytest.mark.tid("AGENTCFG-021")
    def test_shell_tools_defaults(self):
        assert "python3" in cfg.SHELL_ALLOWED
        assert "rm " in cfg.SHELL_BLOCKED
        assert cfg.SHELL_TIMEOUT_SECONDS == 120
        assert cfg.SHELL_MAX_OUTPUT_LINES == 50

    @pytest.mark.tid("AGENTCFG-022")
    def test_confirm_defaults(self):
        assert cfg.CONFIRM_TIMEOUT_SECONDS == 120
        assert cfg.CONFIRM_MAX_ACTION_LEN == 400

    @pytest.mark.tid("AGENTCFG-023")
    def test_auto_mode_default(self):
        assert cfg.MAX_AUTO_TOOL_CALLS == 30

    @pytest.mark.tid("AGENTCFG-024")
    def test_memory_defaults(self):
        assert cfg.MEMORY_ENABLED is True
        assert cfg.MEMORY_FILE == str(cfg.PROJECT_ROOT / "memory.json")
        assert cfg.MEMORY_MAX_ENTRIES == 500
        assert cfg.MEMORY_MAX_TEXT_CHARS == 1000
        assert cfg.MEMORY_MAX_RECALL_RESULTS == 10
        assert cfg.MEMORY_SUMMARY_MAX_MESSAGES == 40

    @pytest.mark.tid("AGENTCFG-025")
    def test_system_prompt_default_mentions_core_tools(self):
        assert "ask_human" in cfg.SYSTEM_PROMPT
        assert "recall_memory" in cfg.SYSTEM_PROMPT
        assert "remember_fact" in cfg.SYSTEM_PROMPT

    @pytest.mark.tid("AGENTCFG-028")
    def test_project_root_is_parent_of_agent_dir(self):
        # This file (agent_config.py) lives in agent/; PROJECT_ROOT must
        # be the directory ONE level up, not the process's cwd.
        import pathlib
        assert cfg.PROJECT_ROOT == pathlib.Path(cfg.__file__).resolve().parent.parent

    @pytest.mark.tid("AGENTCFG-029")
    def test_workspace_dir_default_is_sibling_of_agent_dir(self):
        assert cfg.WORKSPACE_DIR == cfg.PROJECT_ROOT / "workspace"

    @pytest.mark.tid("AGENTCFG-030")
    def test_workspace_dir_is_not_inside_agent_source_dir(self):
        # The whole point of the sandbox fix: the workspace must never
        # be (or live inside) the directory holding the agent's own
        # source code.
        agent_source_dir = cfg.PROJECT_ROOT / "agent"
        assert not cfg.WORKSPACE_DIR.is_relative_to(agent_source_dir)

    @pytest.mark.tid("AGENTCFG-031")
    def test_memory_file_is_outside_workspace_dir(self):
        # memory.json must not be reachable through the agent's own
        # sandboxed fs_tools (which only ever resolves inside
        # WORKSPACE_DIR) -- otherwise the agent could read/edit its own
        # persistent memory through write_file/read_file.
        import pathlib
        memory_path = pathlib.Path(cfg.MEMORY_FILE)
        assert not memory_path.is_relative_to(cfg.WORKSPACE_DIR)


class TestSystemPromptOverride:
    @pytest.mark.tid("AGENTCFG-026")
    def test_env_var_overrides_default_prompt(self, monkeypatch):
        monkeypatch.setenv("SYSTEM_PROMPT", "You are a custom assistant.")
        import importlib
        reloaded = importlib.reload(cfg)
        try:
            assert reloaded.SYSTEM_PROMPT == "You are a custom assistant."
        finally:
            monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
            importlib.reload(cfg)
