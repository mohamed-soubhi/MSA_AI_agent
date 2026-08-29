"""Tests for the shared tool registry (agent/tools_registry.py) as
re-exported by BE's app/core/tool_bridge.py -- specifically that the
optional tool groups (web tools, scraping tools) are added to / withheld
from the model's tool list purely by their config flags, checked live
per call.
"""

import pytest

import agent_config
from app.core.tool_bridge import get_active_tools

BASE_NAMES = {
    "list_directory", "read_file", "write_file", "create_directory",
    "run_command", "ask_human", "ask_human_choice",
    "remember_fact", "recall_memory",
}


@pytest.fixture(autouse=True)
def _both_flags_off(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_TOOLS_ENABLED", False)
    monkeypatch.setattr(agent_config, "SCRAPING_ENABLED", False)


def test_only_base_tools_when_all_flags_off():
    tools, tool_map = get_active_tools()
    names = {fn.__name__ for fn in tools}
    assert names == BASE_NAMES
    assert set(tool_map) == BASE_NAMES


def test_web_tools_present_when_enabled(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_TOOLS_ENABLED", True)

    tools, tool_map = get_active_tools()
    names = {fn.__name__ for fn in tools}

    assert names == BASE_NAMES | {"web_search", "web_fetch"}
    assert tool_map["web_search"].__name__ == "web_search"
    assert tool_map["web_fetch"].__name__ == "web_fetch"


def test_scrape_tools_present_when_enabled(monkeypatch):
    monkeypatch.setattr(agent_config, "SCRAPING_ENABLED", True)

    tools, tool_map = get_active_tools()
    names = {fn.__name__ for fn in tools}

    assert names == BASE_NAMES | {"scrape_page", "scrape_extract"}
    assert "web_search" not in tool_map  # independent of WEB_TOOLS_ENABLED


def test_both_optional_groups_enabled(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_TOOLS_ENABLED", True)
    monkeypatch.setattr(agent_config, "SCRAPING_ENABLED", True)

    tools, _ = get_active_tools()
    names = {fn.__name__ for fn in tools}

    assert names == BASE_NAMES | {"web_search", "web_fetch", "scrape_page", "scrape_extract"}
    assert len(tools) == 13


def test_tool_map_keys_match_function_names(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_TOOLS_ENABLED", True)
    monkeypatch.setattr(agent_config, "SCRAPING_ENABLED", True)
    _, tool_map = get_active_tools()
    for name, fn in tool_map.items():
        assert name == fn.__name__
