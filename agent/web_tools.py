"""Ollama's hosted web_search / web_fetch, exposed as agent tools.

Unlike every other tool in this project -- which stays inside
WORKSPACE_DIR (fs_tools), a vetted shell allowlist (shell_tools), or a
human prompt (human_tools) -- these two reach the public internet. The
request is made by Ollama's servers rather than this process, so there
is no local-network SSRF surface, but it is still an external call that
spends Ollama Cloud quota and sends the query / URL off the machine.

Two independent guards:

  1. Off unless agent_config.WEB_TOOLS_ENABLED -- tools_registry
     .get_active_tools() simply never hands these to the model
     otherwise, so the model cannot call a tool it was never given.
  2. confirm() before every call when WEB_TOOLS_REQUIRE_CONFIRMATION
     (default true) -- the same hard gate write_file / run_command use.

OLLAMA_API_KEY is read from the environment by the ollama client
itself; it is deliberately NOT a config-editor field, so the
credential never lands in agent/.env or a GET /api/config response.

Config values are read as agent_config.<NAME> at call time (not copied
in via `from agent_config import ...`), so config_reload.reload_all()'s
in-place importlib.reload of agent_config is picked up automatically
with no propagation entry needed.
"""

import os

import ollama

import agent_config
from confirm import confirm

_SNIPPET_MAX_CHARS = 500  # per-result text shown by web_search


def _api_key_missing() -> bool:
    return not (os.getenv("OLLAMA_API_KEY") or "").strip()


def _client() -> "ollama.Client":
    """A fresh ollama client that carries the Bearer token explicitly,
    built from OLLAMA_API_KEY at call time.

    NOT the module-level ollama.web_search() / ollama.web_fetch()
    helpers: those use one lazily-built default client that bakes its
    Authorization header from whatever os.environ held the first time
    any ollama.* module function ran. OLLAMA_API_KEY is normally loaded
    from agent/.env during agent_config import, and can change on a
    config reload -- so that default client is often built with NO
    token and then never picks one up ("Authorization header with
    Bearer token is required"). Constructing our own client per call
    with headers={"Authorization": "Bearer <key>"} is the pattern
    Ollama's own examples use, and always reflects the current key.
    OLLAMA_HOST is still honoured for anyone pointing at a proxy.
    """
    key = (os.environ.get("OLLAMA_API_KEY") or "").strip()
    kwargs = {"headers": {"Authorization": f"Bearer {key}"}}
    host = os.environ.get("OLLAMA_HOST")
    if host:
        kwargs["host"] = host
    return ollama.Client(**kwargs)


def web_search(query: str, max_results: int | None = None) -> str:
    """Search the web via Ollama's hosted search and return ranked results.

    Args:
        query: What to search for.
        max_results: How many results to return. Capped at, and
            defaulting to, the WEB_SEARCH_MAX_RESULTS config value.
    """
    query = (query or "").strip()
    if not query:
        return "Error: query must be a non-empty string."
    if _api_key_missing():
        return "Error: OLLAMA_API_KEY is not set in the environment; web tools are unavailable."
    if agent_config.WEB_TOOLS_REQUIRE_CONFIRMATION and not confirm(f"web_search: {query}"):
        return "Web search denied by user."

    ceiling = agent_config.WEB_SEARCH_MAX_RESULTS
    limit = max_results if isinstance(max_results, int) and max_results > 0 else ceiling
    limit = max(1, min(limit, ceiling))

    try:
        response = _client().web_search(query, max_results=limit)
    except ollama.ResponseError as exc:
        return f"Error: Ollama web search failed ({exc})."
    except Exception as exc:  # network / auth / unexpected -- never crash the tool loop
        return f"Error: web search could not be completed ({exc})."

    results = getattr(response, "results", None) or []
    if not results:
        return f"No web results for {query!r}."

    lines = []
    for i, r in enumerate(results, 1):
        title = (getattr(r, "title", "") or "").strip() or "(untitled)"
        url = (getattr(r, "url", "") or "").strip()
        snippet = " ".join((getattr(r, "content", "") or "").split())
        if len(snippet) > _SNIPPET_MAX_CHARS:
            snippet = snippet[:_SNIPPET_MAX_CHARS] + "…"
        lines.append(f"{i}. {title}\n   {url}\n   {snippet}")
    return "\n".join(lines)


def web_fetch(url: str) -> str:
    """Fetch one web page via Ollama's hosted fetch and return its text.

    Args:
        url: The absolute http:// or https:// URL to fetch.
    """
    url = (url or "").strip()
    if not url:
        return "Error: url must be a non-empty string."
    if not (url.startswith("http://") or url.startswith("https://")):
        return "Error: url must start with http:// or https://."
    if _api_key_missing():
        return "Error: OLLAMA_API_KEY is not set in the environment; web tools are unavailable."
    if agent_config.WEB_TOOLS_REQUIRE_CONFIRMATION and not confirm(f"web_fetch: {url}"):
        return "Web fetch denied by user."

    try:
        response = _client().web_fetch(url)
    except ollama.ResponseError as exc:
        return f"Error: Ollama web fetch failed ({exc})."
    except Exception as exc:  # network / auth / unexpected -- never crash the tool loop
        return f"Error: web fetch could not be completed ({exc})."

    title = (getattr(response, "title", "") or "").strip()
    content = getattr(response, "content", "") or ""
    cap = agent_config.WEB_FETCH_MAX_CHARS
    truncated = len(content) > cap
    if truncated:
        content = content[:cap]

    header = f"# {title}\n{url}\n\n" if title else f"{url}\n\n"
    footer = f"\n\n[content truncated at {cap} chars]" if truncated else ""
    return header + content + footer
