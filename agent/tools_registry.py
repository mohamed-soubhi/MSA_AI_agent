"""The single place the agent's tool set is assembled.

Imported by BOTH CLI_agent.py and BE's tool_bridge.py so the two entry
points can never drift into offering different tools -- the same
reasoning tool_bridge.py's own docstring already gives for importing
implementations from one place instead of re-listing them.

The base 9 (files, shell, human-in-the-loop, memory) are always on.
Optional groups are appended per config flag, each read at call time
(get_active_tools() runs per chat turn in chat.py, once at startup in
CLI_agent.py) so a config-editor toggle takes effect on the next turn
with no restart -- config_reload.reload_all() already reloads
agent_config in place:

  - web_search / web_fetch      when WEB_TOOLS_ENABLED
  - scrape_page / scrape_extract when SCRAPING_ENABLED
"""

import agent_config
from fs_tools import create_directory, list_directory, read_file, write_file
from human_tools import ask_human, ask_human_choice
from memory import recall_memory, remember_fact
from scrape_tools import scrape_extract, scrape_page
from shell_tools import run_command
from web_tools import web_fetch, web_search

BASE_TOOLS = [
    list_directory, read_file, write_file, create_directory,
    run_command, ask_human, ask_human_choice,
    remember_fact, recall_memory,
]

WEB_TOOLS = [web_search, web_fetch]
SCRAPE_TOOLS = [scrape_page, scrape_extract]


def get_active_tools() -> tuple[list, dict]:
    """Return (tools, tool_map) for the current config: the base 9,
    plus web_search / web_fetch when WEB_TOOLS_ENABLED, plus
    scrape_page / scrape_extract when SCRAPING_ENABLED."""
    tools = list(BASE_TOOLS)
    if agent_config.WEB_TOOLS_ENABLED:
        tools += WEB_TOOLS
    if agent_config.SCRAPING_ENABLED:
        tools += SCRAPE_TOOLS
    return tools, {fn.__name__: fn for fn in tools}
