# config_reload.py

Hot-reloading coordinator for `agent_config.py` and `log_config.py`.
Allows settings saved via the Backend Config Editor (`POST /api/config`) to take
effect immediately in the running process without requiring a manual restart.

## Background & Problem

Python modules frequently bind imported configuration constants directly into their
own local namespace via `from agent_config import X`. For example:
- `shell_tools.py` binds `from agent_config import SHELL_ALLOWED as ALLOWED`
- `confirm.py` binds `from agent_config import CONFIRM_TIMEOUT_SECONDS`
- `fs_tools.py` binds `from agent_config import MAX_WRITE_BYTES, WORKSPACE_DIR`

Because `from X import Y` binds the object by value at import time, re-running
`dotenv.load_dotenv()` or reloading `agent_config` with `importlib.reload(agent_config)`
updates `agent_config`'s attributes, but leaves all consumer modules holding stale
copies.

## Architecture & Mechanism

`config_reload.reload_all()` coordinates hot-reloading across four explicit phases:

```
+-------------------------------------------------------------------------------+
| 1. Authoritative .env Ingestion                                               |
|    load_dotenv(agent/.env, override=True)                                     |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
| 2. In-Place Module Reloads                                                    |
|    importlib.reload(agent_config), importlib.reload(log_config)               |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
| 3. Explicit Namespace Propagation via sys.modules                            |
|    - _PROPAGATE: auto_runner, CLI_agent, confirm, fs_tools, memory, shared    |
|    - _PROPAGATE_ALIASED: shell_tools (ALLOWED, BLOCKED, etc.)                 |
|    - _PROPAGATE_BE: app.api.memory, app.core.approval_bridge                  |
|    - _PROPAGATE_BE_ALIASED: app.core.agent_bridge (CHAT_SYSTEM_PROMPT),      |
|                             app.api.chat (CHAT_SYSTEM_PROMPT)                 |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
| 4. Derived Path & Singleton Refresh                                           |
|    - fs_tools.BASE_DIR = agent_config.WORKSPACE_DIR.resolve()                 |
|    - shell_tools.BASE_DIR = fs_tools.BASE_DIR                                 |
|    - app.core.tool_bridge.BASE_DIR = fs_tools.BASE_DIR                        |
|    - memory.MEMORY_PATH = Path(agent_config.MEMORY_FILE)                      |
|    - app.core.agent_bridge._agent = None (invalidates cached LLM singleton)   |
+-------------------------------------------------------------------------------+
```

### Safety Features
1. **Lazy & Safe Lookup**: Modules are inspected via `sys.modules.get(...)`. If a module has not been imported, it is never forcefully imported, preventing unexpected side effects or circular import order issues.
2. **Deterministic Precedence**: `override=True` ensures the newly saved values in `agent/.env` take precedence over previous runtime state.
3. **Singleton Cache Dropping**: Since `OllamaAgent` sets `self.model` at initialization, `agent_bridge._agent` is reset to `None` so subsequent chat turns construct a fresh client with the updated model and timeouts.

## Restart Boundary

As documented in `BE/app/api/config.py`, the following settings cannot be hot-reloaded
at runtime because they bind to the OS network socket and ASGI middleware at process boot:
- `BE_HOST`
- `BE_PORT`
- `BE_CORS_ORIGINS`

All other settings (agent tool limits, timeouts, sandbox root, shell allow/block lists,
system prompts, and logging) hot-reload immediately.

## Test Coverage (`tests/test_config_reload.py`)

Every reload pathway is verified through unit tests:
- `CFGRELOAD-001`: In-place reload of `agent_config` and `log_config`
- `CFGRELOAD-002`: Unaliased variable propagation (`confirm`, `memory`, `shared`)
- `CFGRELOAD-003`: Aliased variable propagation (`shell_tools.ALLOWED`, `TIMEOUT_SECONDS`, `MAX_OUTPUT_LINES`)
- `CFGRELOAD-004`: Derived `BASE_DIR` synchronization (`fs_tools`, `shell_tools`)
- `CFGRELOAD-005`: Derived `MEMORY_PATH` path conversion
- `CFGRELOAD-006`: `agent_bridge._agent` cache eviction
- `CFGRELOAD-007`: Safe handling when consumer modules are not in `sys.modules`
- `CFGRELOAD-008`: Backend consumer module propagation (`app.api.memory`, `app.core.approval_bridge`, `app.core.agent_bridge`)
- `CFGRELOAD-009`: Live propagation into `app.api.chat` (`CHAT_SYSTEM_PROMPT`) ensuring `reset_chat()` seeds fresh prompts
- `CFGRELOAD-010`: Derived `app.core.tool_bridge.BASE_DIR` synchronization
