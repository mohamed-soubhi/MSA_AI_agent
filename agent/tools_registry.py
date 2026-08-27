"""The single place the agent's tool set is assembled.

Imported by BOTH CLI_agent.py and BE's tool_bridge.py so the two entry
points can never drift into offering different tools -- the same
reasoning tool_bridge.py's own docstring already gives for importing
implementations from one place instead of re-listing them.

The base 9 (files, shell, human-in-the-loop, memory) are always on.
web_search / web_fetch are appended only when
agent_config.WEB_TOOLS_ENABLED is true. Because that flag is read at
call time (get_active_tools() is called per chat turn by chat.py, once
at startup by CLI_agent.py), toggling it in the config editor takes
effect on the next turn with no restart -- config_reload.reload_all()
already reloads agent_config in place.
"""

import agent_config
from fs_tools import create_directory, list_directory, read_file, write_file
from human_tools import ask_human, ask_human_choice
from memory import recall_memory, remember_fact
from shell_tools import run_command
from web_tools import web_fetch, web_search

BASE_TOOLS = [
    list_directory, read_file, write_file, create_directory,
    run_command, ask_human, ask_human_choice,
    remember_fact, recall_memory,
]

WEB_TOOLS = [web_search, web_fetch]


def get_active_tools() -> tuple[list, dict]:
    """Return (tools, tool_map) for the current config: the base 9,
    plus web_search / web_fetch when WEB_TOOLS_ENABLED."""
    tools = list(BASE_TOOLS)
    if agent_config.WEB_TOOLS_ENABLED:
        tools += WEB_TOOLS
    return tools, {fn.__name__: fn for fn in tools}
