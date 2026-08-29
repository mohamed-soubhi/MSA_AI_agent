"""Tests for scrape_tools.scrape_page / scrape_extract -- the Scrapling
web-scraping tools. scrape_tools._fetch is monkeypatched in the tests
that reach it so nothing here touches the network or a browser, and
scrapling itself is never imported.
"""

import pytest

import agent_config
import scrape_tools


class _Element:
    def __init__(self, text):
        self._text = text

    def get_all_text(self):
        return self._text


class _Response:
    """Stand-in for a Scrapling Response."""

    def __init__(self, markdown=None, text="", css_map=None):
        self._markdown = markdown
        self._text = text
        self._css_map = css_map or {}

    def markdown(self):
        if self._markdown is None:
            raise AttributeError("no markdown")
        return self._markdown

    def get_all_text(self):
        return self._text

    def css(self, selector):
        return self._css_map.get(selector, [])


def _use_fetch(monkeypatch, fn):
    monkeypatch.setattr(scrape_tools, "_fetch", fn)


@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
    monkeypatch.setattr(agent_config, "SCRAPING_FETCHER", "http")
    monkeypatch.setattr(agent_config, "SCRAPING_ALLOW_BROWSER", False)
    monkeypatch.setattr(agent_config, "SCRAPING_BLOCK_PRIVATE_HOSTS", True)
    monkeypatch.setattr(agent_config, "SCRAPING_MAX_CHARS", 100_000)
    monkeypatch.setattr(agent_config, "SCRAPING_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(agent_config, "SCRAPING_REQUIRE_CONFIRMATION", True)
    monkeypatch.setattr(scrape_tools, "confirm", lambda _msg: True)
    # _fetch must not be reached unless a test wires one up.
    monkeypatch.setattr(
        scrape_tools, "_fetch",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("_fetch called unexpectedly")),
    )


# -- scrape_page --------------------------------------------------------

@pytest.mark.tid("SCRAPE-001")
def test_scrape_page_returns_markdown(monkeypatch):
    _use_fetch(monkeypatch, lambda url, mode, t: _Response(markdown="# Title\n\nbody text"))
    out = scrape_tools.scrape_page("https://example.com")
    assert out == "# Title\n\nbody text"


@pytest.mark.tid("SCRAPE-002")
def test_scrape_page_falls_back_to_plain_text_without_markdown(monkeypatch):
    _use_fetch(monkeypatch, lambda url, mode, t: _Response(markdown=None, text="just text"))
    out = scrape_tools.scrape_page("https://example.com")
    assert out == "just text"


@pytest.mark.tid("SCRAPE-003")
def test_scrape_page_truncates_to_config_cap(monkeypatch):
    monkeypatch.setattr(agent_config, "SCRAPING_MAX_CHARS", 10)
    _use_fetch(monkeypatch, lambda url, mode, t: _Response(markdown="x" * 500))
    out = scrape_tools.scrape_page("https://example.com")
    assert out.startswith("xxxxxxxxxx")
    assert "[content truncated at 10 chars]" in out
    assert "x" * 11 not in out


@pytest.mark.tid("SCRAPE-004")
def test_scrape_page_rejects_non_http_scheme():
    assert scrape_tools.scrape_page("ftp://example.com").startswith("Error:")
    assert scrape_tools.scrape_page("file:///etc/passwd").startswith("Error:")
    assert scrape_tools.scrape_page("   ").startswith("Error:")


@pytest.mark.tid("SCRAPE-005")
def test_scrape_page_rejects_unknown_mode():
    out = scrape_tools.scrape_page("https://example.com", mode="turbo")
    assert out.startswith("Error:") and "http" in out


# -- browser-mode gate ------------------------------------------------

@pytest.mark.tid("SCRAPE-006")
@pytest.mark.parametrize("mode", ["stealth", "dynamic"])
def test_browser_mode_blocked_without_allow_browser(mode):
    out = scrape_tools.scrape_page("https://example.com", mode=mode)
    assert out.startswith("Error:") and "SCRAPING_ALLOW_BROWSER" in out


@pytest.mark.tid("SCRAPE-007")
def test_browser_mode_runs_when_allowed(monkeypatch):
    monkeypatch.setattr(agent_config, "SCRAPING_ALLOW_BROWSER", True)
    seen = {}

    def fake(url, mode, t):
        seen["mode"] = mode
        return _Response(markdown="ok")

    _use_fetch(monkeypatch, fake)
    out = scrape_tools.scrape_page("https://example.com", mode="dynamic")
    assert out == "ok"
    assert seen["mode"] == "dynamic"


# -- private-host SSRF guard ----------------------------------------

@pytest.mark.tid("SCRAPE-008")
@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://10.0.0.5/",
    "http://169.254.169.254/latest/meta-data/",
    "http://localhost:8000/",
])
def test_private_hosts_blocked_by_default(url):
    out = scrape_tools.scrape_page(url)
    assert out.startswith("Error:") and "private" in out.lower()


@pytest.mark.tid("SCRAPE-009")
def test_private_host_allowed_when_guard_disabled(monkeypatch):
    monkeypatch.setattr(agent_config, "SCRAPING_BLOCK_PRIVATE_HOSTS", False)
    _use_fetch(monkeypatch, lambda url, mode, t: _Response(markdown="local ok"))
    out = scrape_tools.scrape_page("http://127.0.0.1/x")
    assert out == "local ok"


# -- confirm gate ----------------------------------------------------

@pytest.mark.tid("SCRAPE-010")
def test_confirm_denied_never_fetches(monkeypatch):
    monkeypatch.setattr(scrape_tools, "confirm", lambda _msg: False)

    def _must_not_run(*a, **k):
        raise AssertionError("_fetch reached despite a denied confirm")

    monkeypatch.setattr(scrape_tools, "_fetch", _must_not_run)
    out = scrape_tools.scrape_page("https://example.com")
    assert out == "scrape_page denied by user."


# -- scrapling not installed / fetch errors ------------------------

@pytest.mark.tid("SCRAPE-011")
def test_missing_scrapling_gives_install_hint(monkeypatch):
    def _no_scrapling(*a, **k):
        raise ImportError("No module named 'scrapling'")

    _use_fetch(monkeypatch, _no_scrapling)
    out = scrape_tools.scrape_page("https://example.com")
    assert "pip install 'scrapling[fetchers]'" in out
    assert "scrapling install" in out


@pytest.mark.tid("SCRAPE-012")
def test_fetch_exception_is_friendly(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("connection reset")

    _use_fetch(monkeypatch, _boom)
    out = scrape_tools.scrape_page("https://example.com")
    assert out.startswith("Error: scrape failed") and "connection reset" in out


# -- scrape_extract ------------------------------------------------

@pytest.mark.tid("SCRAPE-013")
def test_scrape_extract_joins_matched_text(monkeypatch):
    resp = _Response(css_map={"td.price": [_Element("$10"), _Element("$25")]})
    _use_fetch(monkeypatch, lambda url, mode, t: resp)
    out = scrape_tools.scrape_extract("https://shop.example", "td.price")
    assert out == "$10\n$25"


@pytest.mark.tid("SCRAPE-014")
def test_scrape_extract_empty_selector_rejected():
    assert scrape_tools.scrape_extract("https://example.com", "  ").startswith("Error:")


@pytest.mark.tid("SCRAPE-015")
def test_scrape_extract_no_matches(monkeypatch):
    _use_fetch(monkeypatch, lambda url, mode, t: _Response(css_map={}))
    out = scrape_tools.scrape_extract("https://example.com", "h1.missing")
    assert "No elements matched" in out


# -- mode defaulting ---------------------------------------------

@pytest.mark.tid("SCRAPE-016")
def test_mode_defaults_to_config_fetcher(monkeypatch):
    monkeypatch.setattr(agent_config, "SCRAPING_FETCHER", "stealth")
    monkeypatch.setattr(agent_config, "SCRAPING_ALLOW_BROWSER", True)
    seen = {}
    _use_fetch(monkeypatch, lambda url, mode, t: seen.setdefault("mode", mode) or _Response(markdown="x"))
    scrape_tools.scrape_page("https://example.com")
    assert seen["mode"] == "stealth"
