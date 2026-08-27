"""Tests for the shared tool registry (agent/tools_registry.py) as
re-exported by BE's app/core/tool_bridge.py -- specifically that the
web tools are added to / withheld from the model's tool list purely by
the WEB_TOOLS_ENABLED config flag, checked live per call.
"""

import agent_config
from app.core.tool_bridge import get_active_tools

BASE_NAMES = {
    "list_directory", "read_file", "write_file", "create_directory",
    "run_command", "ask_human", "ask_human_choice",
    "remember_fact", "recall_memory",
}


def test_web_tools_absent_when_disabled(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_TOOLS_ENABLED", False)

    tools, tool_map = get_active_tools()
    names = {fn.__name__ for fn in tools}

    assert names == BASE_NAMES
    assert set(tool_map) == BASE_NAMES
    assert "web_search" not in tool_map


def test_web_tools_present_when_enabled(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_TOOLS_ENABLED", True)

    tools, tool_map = get_active_tools()
    names = {fn.__name__ for fn in tools}

    assert names == BASE_NAMES | {"web_search", "web_fetch"}
    assert tool_map["web_search"].__name__ == "web_search"
    assert tool_map["web_fetch"].__name__ == "web_fetch"


def test_tool_map_keys_match_function_names(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_TOOLS_ENABLED", True)
    _, tool_map = get_active_tools()
    for name, fn in tool_map.items():
        assert name == fn.__name__
