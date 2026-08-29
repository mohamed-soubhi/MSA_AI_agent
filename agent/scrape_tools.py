"""Web scraping tools backed by Scrapling (https://github.com/D4Vinci/Scrapling).

Wired in as agent tools only when agent_config.SCRAPING_ENABLED (see
tools_registry.get_active_tools()). Gated harder than the Ollama web
tools because the request is made FROM THIS MACHINE:

  - scheme must be http/https;
  - SCRAPING_BLOCK_PRIVATE_HOSTS (default on) refuses hosts that
    resolve to loopback / private / link-local / reserved addresses --
    the real SSRF surface an on-box fetch has that ollama.web_fetch
    (run on Ollama's servers) does not;
  - the "stealth" and "dynamic" fetchers run a local browser engine,
    so they additionally require SCRAPING_ALLOW_BROWSER;
  - confirm() before every call when SCRAPING_REQUIRE_CONFIRMATION.

scrapling is an OPTIONAL dependency -- when it is not installed the
tools return a one-line "how to install" message instead of raising.

Config is read as agent_config.<NAME> at call time (not copied in via
`from agent_config import ...`), so config_reload.reload_all()'s
in-place reload of agent_config is picked up with no propagation entry.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import agent_config
from confirm import confirm

_BROWSER_MODES = ("stealth", "dynamic")
_VALID_MODES = ("http",) + _BROWSER_MODES

_INSTALL_HINT = (
    "Error: scrapling is not installed. Run: "
    "pip install 'scrapling[fetchers]' && scrapling install"
)


def _resolve_mode(mode: str | None) -> str:
    return (mode or agent_config.SCRAPING_FETCHER or "http").strip().lower()


def _host_is_private(url: str) -> bool:
    """True if url's host is 'localhost' or resolves to any loopback /
    private / link-local / reserved / multicast / unspecified address.
    A DNS failure returns False -- the fetch itself will then fail with
    a normal error rather than being silently blocked."""
    host = (urlparse(url).hostname or "").strip().lower()
    if not host:
        return True
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (ip.is_loopback or ip.is_private or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return True
    return False


def _fetch(url: str, mode: str, timeout_s: int):
    """Run the chosen Scrapling fetcher and return its Response.

    Raises ImportError if scrapling is missing (the callers turn that
    into _INSTALL_HINT); any other exception propagates to the callers'
    broad handler and becomes a friendly "scrape failed" string.
    """
    from scrapling.fetchers import DynamicFetcher, Fetcher, StealthyFetcher

    if mode == "http":
        return Fetcher.get(url, timeout=timeout_s)
    if mode == "stealth":
        return StealthyFetcher.fetch(
            url, headless=True, solve_cloudflare=True, timeout=timeout_s * 1000
        )
    return DynamicFetcher.fetch(url, headless=True, timeout=timeout_s * 1000)


def _response_markdown(response) -> str:
    """Scrapling's Response.markdown ('LLM-ready Markdown'), tolerant of
    it being a method, a property, or absent (fall back to plain text)."""
    md = getattr(response, "markdown", None)
    if callable(md):
        try:
            return md()
        except Exception:
            pass
    elif isinstance(md, str):
        return md
    getter = getattr(response, "get_all_text", None)
    if callable(getter):
        return getter()
    return str(response)


def _response_css_text(response, selector: str) -> str:
    elements = response.css(selector)
    if elements is None:
        return ""
    if not isinstance(elements, (list, tuple)):
        elements = [elements]
    parts = []
    for el in elements:
        getter = getattr(el, "get_all_text", None)
        text = getter() if callable(getter) else getattr(el, "text", None) or str(el)
        text = " ".join(str(text).split())
        if text:
            parts.append(text)
    return "\n".join(parts)


def _truncate(text: str) -> str:
    cap = agent_config.SCRAPING_MAX_CHARS
    if len(text) <= cap:
        return text
    return text[:cap] + f"\n\n[content truncated at {cap} chars]"


def _guard(url: str, mode: str, action: str) -> str | None:
    """Shared pre-flight checks. Returns an error string to return to
    the model, or None when the fetch may proceed."""
    url = (url or "").strip()
    if not url:
        return "Error: url must be a non-empty string."
    if not (url.startswith("http://") or url.startswith("https://")):
        return "Error: url must start with http:// or https://."
    if mode not in _VALID_MODES:
        return f"Error: mode must be one of {', '.join(_VALID_MODES)} (got {mode!r})."
    if mode in _BROWSER_MODES and not agent_config.SCRAPING_ALLOW_BROWSER:
        return (
            f"Error: the {mode!r} fetcher runs a local browser; set "
            "SCRAPING_ALLOW_BROWSER to use it (and run `scrapling install`)."
        )
    if agent_config.SCRAPING_BLOCK_PRIVATE_HOSTS and _host_is_private(url):
        return "Error: refusing to scrape a private / loopback host (SCRAPING_BLOCK_PRIVATE_HOSTS)."
    if agent_config.SCRAPING_REQUIRE_CONFIRMATION and not confirm(f"{action} [{mode}]: {url}"):
        return f"{action} denied by user."
    return None


def scrape_page(url: str, mode: str | None = None) -> str:
    """Fetch a web page with Scrapling and return it as clean Markdown.

    Args:
        url: Absolute http:// or https:// URL.
        mode: Fetcher to use -- "http" (fast, no browser), "stealth"
            (anti-bot browser), or "dynamic" (full JavaScript browser).
            Defaults to the SCRAPING_FETCHER config value. The browser
            modes require SCRAPING_ALLOW_BROWSER.
    """
    resolved = _resolve_mode(mode)
    blocked = _guard(url, resolved, "scrape_page")
    if blocked is not None:
        return blocked

    try:
        response = _fetch(url.strip(), resolved, agent_config.SCRAPING_TIMEOUT_SECONDS)
    except ImportError:
        return _INSTALL_HINT
    except Exception as exc:  # network / browser / parse -- never crash the tool loop
        return f"Error: scrape failed ({exc})."

    return _truncate(_response_markdown(response))


def scrape_extract(url: str, css: str, mode: str | None = None) -> str:
    """Fetch a web page with Scrapling and return the text of every
    element matching a CSS selector (one match per line).

    Args:
        url: Absolute http:// or https:// URL.
        css: A CSS selector, e.g. "table.prices td" or "article h2".
        mode: Fetcher to use -- see scrape_page. Defaults to
            SCRAPING_FETCHER; browser modes need SCRAPING_ALLOW_BROWSER.
    """
    css = (css or "").strip()
    if not css:
        return "Error: css selector must be a non-empty string."

    resolved = _resolve_mode(mode)
    blocked = _guard(url, resolved, "scrape_extract")
    if blocked is not None:
        return blocked

    try:
        response = _fetch(url.strip(), resolved, agent_config.SCRAPING_TIMEOUT_SECONDS)
    except ImportError:
        return _INSTALL_HINT
    except Exception as exc:
        return f"Error: scrape failed ({exc})."

    text = _response_css_text(response, css)
    if not text:
        return f"No elements matched {css!r}."
    return _truncate(text)
