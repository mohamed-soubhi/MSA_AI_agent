"""Tests for web_tools.web_search / web_fetch -- the Ollama-hosted web
tools. web_tools._client() is monkeypatched in the tests that reach it
so nothing here makes a network call; OLLAMA_API_KEY is set on the
environment unless a test is specifically about it missing.
"""

import types

import pytest

import agent_config
import web_tools


class _FakeClient:
    """Stand-in for ollama.Client -- only the two methods web_tools uses."""

    def __init__(self, search=None, fetch=None):
        self._search = search
        self._fetch = fetch

    def web_search(self, query, max_results):
        return self._search(query, max_results)

    def web_fetch(self, url):
        return self._fetch(url)


def _use_client(monkeypatch, *, search=None, fetch=None):
    monkeypatch.setattr(web_tools, "_client", lambda: _FakeClient(search=search, fetch=fetch))


@pytest.fixture(autouse=True)
def _with_key_and_auto_confirm(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    # Confirmation is ON in config, but auto-approve so happy-path tests
    # don't hang. Tests about the deny path override this.
    monkeypatch.setattr(agent_config, "WEB_TOOLS_REQUIRE_CONFIRMATION", True)
    monkeypatch.setattr(web_tools, "confirm", lambda _msg: True)


def _search_response(items):
    return types.SimpleNamespace(
        results=[types.SimpleNamespace(**it) for it in items]
    )


def _fetch_response(title, content, links=None):
    return types.SimpleNamespace(title=title, content=content, links=links or [])


# -- _client() : the fix -- explicit Bearer header from the env --------

@pytest.mark.tid("WEBTOOL-000")
def test_client_sets_bearer_header_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "abc123")
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    captured = {}

    class _Spy:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(web_tools.ollama, "Client", _Spy)

    web_tools._client()

    assert captured["headers"]["Authorization"] == "Bearer abc123"
    assert "host" not in captured  # OLLAMA_HOST unset -> ollama's default


@pytest.mark.tid("WEBTOOL-012")
def test_client_passes_ollama_host_when_set(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "abc123")
    monkeypatch.setenv("OLLAMA_HOST", "https://proxy.example")
    captured = {}

    class _Spy:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(web_tools.ollama, "Client", _Spy)

    web_tools._client()
    assert captured["host"] == "https://proxy.example"


# -- web_search -----------------------------------------------------------

@pytest.mark.tid("WEBTOOL-001")
def test_web_search_formats_ranked_results(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_SEARCH_MAX_RESULTS", 5)
    _use_client(monkeypatch, search=lambda q, max_results: _search_response([
        {"title": "First", "url": "https://a.example", "content": "alpha body"},
        {"title": "Second", "url": "https://b.example", "content": "beta body"},
    ]))

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

    _use_client(monkeypatch, search=fake)

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

    def _must_not_run():
        raise AssertionError("_client() reached despite a denied confirm")

    monkeypatch.setattr(web_tools, "_client", _must_not_run)

    out = web_tools.web_search("q")
    assert out == "Web search denied by user."


@pytest.mark.tid("WEBTOOL-006")
def test_web_search_response_error_is_friendly(monkeypatch):
    def boom(q, max_results):
        raise web_tools.ollama.ResponseError("401 unauthorized")

    _use_client(monkeypatch, search=boom)
    out = web_tools.web_search("q")
    assert out.startswith("Error:") and "401" in out


# -- web_fetch ----------------------------------------------------------

@pytest.mark.tid("WEBTOOL-007")
def test_web_fetch_returns_title_and_body(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_FETCH_MAX_CHARS", 8000)
    _use_client(monkeypatch, fetch=lambda url: _fetch_response("Doc Title", "the page body"))

    out = web_tools.web_fetch("https://example.com/doc")
    assert "# Doc Title" in out
    assert "https://example.com/doc" in out
    assert "the page body" in out
    assert "truncated" not in out


@pytest.mark.tid("WEBTOOL-008")
def test_web_fetch_truncates_to_config_cap(monkeypatch):
    monkeypatch.setattr(agent_config, "WEB_FETCH_MAX_CHARS", 20)
    _use_client(monkeypatch, fetch=lambda url: _fetch_response("T", "x" * 500))

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
