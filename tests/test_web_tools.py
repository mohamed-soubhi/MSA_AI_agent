"""Tests for web_tools.web_search / web_fetch -- the Ollama-hosted web
tools. The real ollama.web_search / ollama.web_fetch are monkeypatched
throughout so nothing here makes a network call, and OLLAMA_API_KEY is
set on the environment unless a test is specifically about it missing.
"""

import types

import pytest

import agent_config
import web_tools


@pytest.fixture(autouse=True)
def _with_key_and_no_confirm(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    # Default: confirmation ON in config, but the gate auto-approves so
    # the happy-path tests don't hang. Individual tests override.
    monkeypatch.setattr(agent_config, "WEB_TOOLS_REQUIRE_CONFIRMATION", True)
    monkeypatch.setattr(web_tools, "confirm", lambda _msg: True)


def _search_response(items):
    return types.SimpleNamespace(
        results=[types.SimpleNamespace(**it) for it in items]
    )


def _fetch_response(title, content, links=None):
    return types.SimpleNamespace(title=title, content=content, links=links or [])


# -- web_search -----------------------------------------------------------

@pytest.mark.tid("WEBTOOL-001")
def test_web_search_formats_ranked_results(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_SEARCH_MAX_RESULTS", 5)
    monkeypatch.setattr(
        web_tools.ollama, "web_search",
        lambda q, max_results: _search_response([
            {"title": "First", "url": "https://a.example", "content": "alpha body"},
            {"title": "Second", "url": "https://b.example", "content": "beta body"},
        ]),
    )

    out = web_tools.web_search("python typing")

    assert "1. First" in out and "https://a.example" in out and "alpha body" in out
    assert "2. Second" in out


@pytest.mark.tid("WEBTOOL-002")
def test_web_search_clamps_max_results_to_config_ceiling(monkeypatch):
    seen = {}
    monkeypatch.setattr(agent_config, "WEB_SEARCH_MAX_RESULTS", 3)

    def fake(q, max_results):
        seen["max_results"] = max_results
        return _search_response([])

    monkeypatch.setattr(web_tools.ollama, "web_search", fake)

    web_tools.web_search("q", max_results=99)
    assert seen["max_results"] == 3


@pytest.mark.tid("WEBTOOL-003")
def test_web_search_empty_query_is_rejected():
    assert web_tools.web_search("   ").startswith("Error:")


@pytest.mark.tid("WEBTOOL-004")
def test_web_search_missing_api_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    out = web_tools.web_search("q")
    assert "OLLAMA_API_KEY" in out and out.startswith("Error:")


@pytest.mark.tid("WEBTOOL-005")
def test_web_search_denied_by_confirm(monkeypatch):
    monkeypatch.setattr(web_tools, "confirm", lambda _msg: False)
    called = {"hit": False}
    monkeypatch.setattr(
        web_tools.ollama, "web_search",
        lambda *a, **k: called.__setitem__("hit", True) or _search_response([]),
    )

    out = web_tools.web_search("q")
    assert out == "Web search denied by user."
    assert called["hit"] is False  # gate ran before the network call


@pytest.mark.tid("WEBTOOL-006")
def test_web_search_response_error_is_friendly(monkeypatch):
    def boom(q, max_results):
        raise web_tools.ollama.ResponseError("401 unauthorized")

    monkeypatch.setattr(web_tools.ollama, "web_search", boom)
    out = web_tools.web_search("q")
    assert out.startswith("Error:") and "401" in out


# -- web_fetch ----------------------------------------------------------

@pytest.mark.tid("WEBTOOL-007")
def test_web_fetch_returns_title_and_body(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_FETCH_MAX_CHARS", 8000)
    monkeypatch.setattr(
        web_tools.ollama, "web_fetch",
        lambda url: _fetch_response("Doc Title", "the page body"),
    )

    out = web_tools.web_fetch("https://example.com/doc")
    assert "# Doc Title" in out
    assert "https://example.com/doc" in out
    assert "the page body" in out
    assert "truncated" not in out


@pytest.mark.tid("WEBTOOL-008")
def test_web_fetch_truncates_to_config_cap(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_FETCH_MAX_CHARS", 20)
    monkeypatch.setattr(
        web_tools.ollama, "web_fetch",
        lambda url: _fetch_response("T", "x" * 500),
    )

    out = web_tools.web_fetch("https://example.com")
    assert "xxxxxxxxxxxxxxxxxxxx" in out          # 20 kept
    assert "x" * 21 not in out
    assert "[content truncated at 20 chars]" in out


@pytest.mark.tid("WEBTOOL-009")
def test_web_fetch_rejects_non_http_scheme():
    assert web_tools.web_fetch("ftp://example.com").startswith("Error:")
    assert web_tools.web_fetch("file:///etc/passwd").startswith("Error:")


@pytest.mark.tid("WEBTOOL-010")
def test_web_fetch_missing_api_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    out = web_tools.web_fetch("https://example.com")
    assert "OLLAMA_API_KEY" in out


@pytest.mark.tid("WEBTOOL-011")
def test_web_fetch_denied_by_confirm(monkeypatch):
    monkeypatch.setattr(web_tools, "confirm", lambda _msg: False)
    out = web_tools.web_fetch("https://example.com")
    assert out == "Web fetch denied by user."
