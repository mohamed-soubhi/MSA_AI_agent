"""Tests for agent/config_reload.py hot-reload logic."""

import os
from pathlib import Path
import pytest
import sys
import dotenv
from dotenv.main import load_dotenv as real_load_dotenv
import agent_config
import config_reload
import fs_tools
import shell_tools
import confirm
import memory
import shared


@pytest.fixture(autouse=True)
def isolate_config_and_dotenv(monkeypatch):
    """Restore real load_dotenv for tests, and restore pristine state after."""
    monkeypatch.setattr(dotenv, "load_dotenv", real_load_dotenv)
    monkeypatch.setattr(config_reload, "load_dotenv", real_load_dotenv)

    # Snapshot current environment and module values
    env_snapshot = dict(os.environ)
    orig_allowed = set(shell_tools.ALLOWED)
    orig_blocked = list(shell_tools.BLOCKED)
    orig_shell_timeout = shell_tools.TIMEOUT_SECONDS
    orig_shell_lines = shell_tools.MAX_OUTPUT_LINES
    orig_shell_base = shell_tools.BASE_DIR
    orig_fs_base = fs_tools.BASE_DIR
    orig_fs_max_bytes = fs_tools.MAX_WRITE_BYTES
    orig_confirm_timeout = confirm.CONFIRM_TIMEOUT_SECONDS
    orig_mem_path = memory.MEMORY_PATH
    orig_mem_entries = memory.MEMORY_MAX_ENTRIES
    orig_tool_timeout = shared.TOOL_TIMEOUT_SECONDS
    orig_obs_chars = shared.MAX_OBSERVATION_CHARS

    yield

    # Restore environment and module values
    os.environ.clear()
    os.environ.update(env_snapshot)
    shell_tools.ALLOWED = orig_allowed
    shell_tools.BLOCKED = orig_blocked
    shell_tools.TIMEOUT_SECONDS = orig_shell_timeout
    shell_tools.MAX_OUTPUT_LINES = orig_shell_lines
    shell_tools.BASE_DIR = orig_shell_base
    fs_tools.BASE_DIR = orig_fs_base
    fs_tools.MAX_WRITE_BYTES = orig_fs_max_bytes
    confirm.CONFIRM_TIMEOUT_SECONDS = orig_confirm_timeout
    memory.MEMORY_PATH = orig_mem_path
    memory.MEMORY_MAX_ENTRIES = orig_mem_entries
    shared.TOOL_TIMEOUT_SECONDS = orig_tool_timeout
    shared.MAX_OBSERVATION_CHARS = orig_obs_chars


@pytest.mark.tid("CFGRELOAD-001")
def test_reload_all_reloads_agent_config(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TOOL_TIMEOUT_SECONDS=77\nMAX_WRITE_BYTES=12345\n", encoding="utf-8")
    monkeypatch.setattr(config_reload, "_AGENT_DIR", tmp_path)

    config_reload.reload_all()

    assert agent_config.TOOL_TIMEOUT_SECONDS == 77
    assert agent_config.MAX_WRITE_BYTES == 12345
    assert fs_tools.MAX_WRITE_BYTES == 12345
    assert shared.TOOL_TIMEOUT_SECONDS == 77


@pytest.mark.tid("CFGRELOAD-002")
def test_reload_propagates_unaliased_variables(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CONFIRM_TIMEOUT_SECONDS=45\n"
        "MEMORY_MAX_ENTRIES=88\n"
        "MAX_OBSERVATION_CHARS=999\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_reload, "_AGENT_DIR", tmp_path)

    config_reload.reload_all()

    assert confirm.CONFIRM_TIMEOUT_SECONDS == 45
    assert memory.MEMORY_MAX_ENTRIES == 88
    assert shared.MAX_OBSERVATION_CHARS == 999


@pytest.mark.tid("CFGRELOAD-003")
def test_reload_propagates_aliased_variables(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SHELL_ALLOWED=python3,git,custom_tool\n"
        "SHELL_TIMEOUT_SECONDS=99\n"
        "SHELL_MAX_OUTPUT_LINES=55\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_reload, "_AGENT_DIR", tmp_path)

    config_reload.reload_all()

    assert "custom_tool" in shell_tools.ALLOWED
    assert shell_tools.TIMEOUT_SECONDS == 99
    assert shell_tools.MAX_OUTPUT_LINES == 55


@pytest.mark.tid("CFGRELOAD-004")
def test_reload_recomputes_derived_base_dir(tmp_path, monkeypatch):
    custom_ws = tmp_path / "custom_workspace"
    custom_ws.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(f"WORKSPACE_DIR={custom_ws}\n", encoding="utf-8")
    monkeypatch.setattr(config_reload, "_AGENT_DIR", tmp_path)

    config_reload.reload_all()

    assert fs_tools.BASE_DIR == custom_ws.resolve()
    assert shell_tools.BASE_DIR == custom_ws.resolve()


@pytest.mark.tid("CFGRELOAD-005")
def test_reload_recomputes_derived_memory_path(tmp_path, monkeypatch):
    custom_mem = tmp_path / "custom_memory.json"
    env_file = tmp_path / ".env"
    env_file.write_text(f"MEMORY_FILE={custom_mem}\n", encoding="utf-8")
    monkeypatch.setattr(config_reload, "_AGENT_DIR", tmp_path)

    config_reload.reload_all()

    assert memory.MEMORY_PATH == Path(str(custom_mem))


@pytest.mark.tid("CFGRELOAD-006")
def test_reload_clears_cached_agent_bridge_singleton(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DEFAULT_MODEL=test-model\n", encoding="utf-8")
    monkeypatch.setattr(config_reload, "_AGENT_DIR", tmp_path)

    if "app.core.agent_bridge" not in sys.modules:
        import types
        dummy_bridge = types.ModuleType("app.core.agent_bridge")
        dummy_bridge._agent = object()
        monkeypatch.setitem(sys.modules, "app.core.agent_bridge", dummy_bridge)
    else:
        sys.modules["app.core.agent_bridge"]._agent = object()

    config_reload.reload_all()

    assert sys.modules["app.core.agent_bridge"]._agent is None


@pytest.mark.tid("CFGRELOAD-007")
def test_reload_skips_unimported_modules_safely(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TOOL_TIMEOUT_SECONDS=10\n", encoding="utf-8")
    monkeypatch.setattr(config_reload, "_AGENT_DIR", tmp_path)

    old_mod = sys.modules.pop("auto_runner", None)
    try:
        config_reload.reload_all()
        assert "auto_runner" not in sys.modules
    finally:
        if old_mod is not None:
            sys.modules["auto_runner"] = old_mod


@pytest.mark.tid("CFGRELOAD-008")
def test_reload_propagates_be_modules(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MEMORY_FILE=/tmp/be_test_memory.json\n"
        "CONFIRM_TIMEOUT_SECONDS=88\n"
        "SYSTEM_PROMPT=Custom BE prompt\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_reload, "_AGENT_DIR", tmp_path)

    import types
    dummy_mem = types.ModuleType("app.api.memory")
    dummy_mem.MEMORY_FILE = ""
    monkeypatch.setitem(sys.modules, "app.api.memory", dummy_mem)

    dummy_approval = types.ModuleType("app.core.approval_bridge")
    dummy_approval.CONFIRM_TIMEOUT_SECONDS = 0
    monkeypatch.setitem(sys.modules, "app.core.approval_bridge", dummy_approval)

    dummy_agent_bridge = types.ModuleType("app.core.agent_bridge")
    dummy_agent_bridge.CHAT_SYSTEM_PROMPT = ""
    monkeypatch.setitem(sys.modules, "app.core.agent_bridge", dummy_agent_bridge)

    dummy_chat = types.ModuleType("app.api.chat")
    dummy_chat.CHAT_SYSTEM_PROMPT = ""
    monkeypatch.setitem(sys.modules, "app.api.chat", dummy_chat)

    config_reload.reload_all()

    assert dummy_mem.MEMORY_FILE == "/tmp/be_test_memory.json"
    assert dummy_approval.CONFIRM_TIMEOUT_SECONDS == 88
    assert dummy_agent_bridge.CHAT_SYSTEM_PROMPT == "Custom BE prompt"
    assert dummy_chat.CHAT_SYSTEM_PROMPT == "Custom BE prompt"


@pytest.mark.tid("CFGRELOAD-009")
def test_reload_propagates_chat_api_system_prompt_live(tmp_path, monkeypatch):
    """Test propagation into live app.api.chat module when imported."""
    env_file = tmp_path / ".env"
    env_file.write_text("SYSTEM_PROMPT=Fresh live system prompt\n", encoding="utf-8")
    monkeypatch.setattr(config_reload, "_AGENT_DIR", tmp_path)

    import types
    dummy_chat = types.ModuleType("app.api.chat")
    dummy_chat.CHAT_SYSTEM_PROMPT = "Old prompt"
    monkeypatch.setitem(sys.modules, "app.api.chat", dummy_chat)

    config_reload.reload_all()

    assert dummy_chat.CHAT_SYSTEM_PROMPT == "Fresh live system prompt"
