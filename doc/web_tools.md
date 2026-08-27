# Web Tools (`web_tools.py` & `tools_registry.py`)

## 1. Overview & Architectural Role

`web_tools.py` provides optional, config-gated internet search and page fetching capabilities using Ollama's hosted web search and web fetch APIs (`ollama.web_search` and `ollama.web_fetch`).

Unlike local filesystem tools (`fs_tools.py`), allowlisted shell execution (`shell_tools.py`), or human-in-the-loop prompts (`human_tools.py`), these tools interact with the public web. Requests are proxied through Ollama's hosted infrastructure rather than initiating outbound TCP connections directly from the local host, eliminating local-network SSRF vulnerabilities while preserving full auditability.

### Security Invariants & Isolation Gates

1. **Config Activation Gate**: `WEB_TOOLS_ENABLED=false` by default. `tools_registry.get_active_tools()` only includes `web_search` and `web_fetch` in the tool definitions sent to Ollama if explicitly enabled.
2. **Confirmation Gate**: When `WEB_TOOLS_REQUIRE_CONFIRMATION=true` (default), every search query and fetch URL must be explicitly approved via `confirm()`. Denied requests return immediately without invoking the network.
3. **Credential Isolation**: `OLLAMA_API_KEY` is read strictly from host environment variables (`os.getenv("OLLAMA_API_KEY")`) by the official Ollama SDK. It is never placed in `.env` files or exposed via config API endpoints.
4. **Output Bounded Truncation**: Search snippets are bounded by `_SNIPPET_MAX_CHARS` (500 chars/result); fetched page contents are bounded by `WEB_FETCH_MAX_CHARS` (default 8,000 characters).
5. **Scheme Enforcement**: `web_fetch` strictly verifies that URLs start with `http://` or `https://`, blocking `file://`, `ftp://`, or custom URI schemes.

---

## 2. Exported Tool Functions

### `web_search(query: str, max_results: int | None = None) -> str`
- Searches the web via Ollama's hosted search.
- Arguments:
  - `query` (str): Search keywords or query phrase (must be non-empty).
  - `max_results` (int, optional): Number of results returned, clamped between 1 and `agent_config.WEB_SEARCH_MAX_RESULTS` (default 5).
- Returns ranked, numbered search results formatted with title, URL, and snippet.
- Safe error handling: Missing API key, empty query, denial by confirmation gate, or API errors return descriptive error messages without crashing the ReAct loop.

### `web_fetch(url: str) -> str`
- Fetches the textual content of a single web page.
- Arguments:
  - `url` (str): Absolute `http://` or `https://` target URL.
- Returns formatted Markdown containing page title, URL, body text, and truncation indicators if length exceeds `agent_config.WEB_FETCH_MAX_CHARS`.
- Safe error handling: Validates URL prefix, checks API key, confirms with user, and handles `ollama.ResponseError` gracefully.

---

## 3. Tool Registry (`tools_registry.py`)

`tools_registry.py` provides a single centralized source of truth for agent tools across both the CLI (`CLI_agent.py`) and the Web/Backend (`BE/app/core/tool_bridge.py`).

```python
BASE_TOOLS = [
    list_directory, read_file, write_file, create_directory,
    run_command, ask_human, ask_human_choice,
    remember_fact, recall_memory,
]

WEB_TOOLS = [web_search, web_fetch]

def get_active_tools() -> tuple[list, dict]:
    """Return (tools, tool_map) for current config: base 9 + web tools when enabled."""
```

- **Dynamic Hot-Reloading**: In the Backend, `get_active_tools()` is evaluated on each chat turn. Enabling or disabling web tools in the Config Editor takes effect immediately without server restart.

---

## 4. Configuration Parameters

| Variable | Type | Default | Description |
|---|---|---|---|
| `WEB_TOOLS_ENABLED` | bool | `false` | Master toggle enabling `web_search` and `web_fetch` tools. |
| `WEB_SEARCH_MAX_RESULTS` | int | `5` | Upper ceiling for search results returned per query. |
| `WEB_FETCH_MAX_CHARS` | int | `8000` | Character ceiling for page content returned by `web_fetch`. |
| `WEB_TOOLS_REQUIRE_CONFIRMATION` | bool | `true` | When true, prompts user confirmation before executing searches or fetches. |

---

## 5. Test Coverage (11 Tests)

Unit tests in [`tests/test_web_tools.py`](../tests/test_web_tools.py):

- `WEBTOOL-001`: Result ranking and multi-field formatting.
- `WEBTOOL-002`: Clamping `max_results` to `WEB_SEARCH_MAX_RESULTS` ceiling.
- `WEBTOOL-003`: Rejection of whitespace and empty search queries.
- `WEBTOOL-004`: Friendly error message when `OLLAMA_API_KEY` is missing.
- `WEBTOOL-005`: Confirmation gate rejection before dispatching network request.
- `WEBTOOL-006`: `ollama.ResponseError` translation to friendly error output.
- `WEBTOOL-007`: Page title, URL, and body extraction in `web_fetch`.
- `WEBTOOL-008`: Character truncation at `WEB_FETCH_MAX_CHARS` with notice.
- `WEBTOOL-009`: Rejection of non-HTTP schemes (`ftp://`, `file://`).
- `WEBTOOL-010`: Missing API key detection in `web_fetch`.
- `WEBTOOL-011`: User confirmation rejection in `web_fetch`.
