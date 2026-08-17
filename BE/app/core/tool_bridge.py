"""Exposes the exact same 9 tools CLI_agent.py wires up -- imported
from their one real implementation (fs_tools.py, shell_tools.py,
human_tools.py, memory.py), never reimplemented here. Mirrors
CLI_agent.py's main()'s `tools`/`tool_map` construction verbatim.

Importing this module (rather than importing those tool modules
directly) guarantees BE's tool list can never silently drift from
CLI_agent.py's -- both read from the same functions.
"""

import sys
from pathlib import Path

BE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = BE_DIR.parent / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from fs_tools import BASE_DIR, create_directory, list_directory, read_file, write_file  # noqa: E402
from shell_tools import run_command  # noqa: E402
from human_tools import ask_human, ask_human_choice  # noqa: E402
from memory import recall_memory, remember_fact  # noqa: E402

TOOLS = [
    list_directory, read_file, write_file, create_directory,
    run_command, ask_human, ask_human_choice,
    remember_fact, recall_memory,
]

TOOL_MAP = {
    "list_directory": list_directory,
    "read_file": read_file,
    "write_file": write_file,
    "create_directory": create_directory,
    "run_command": run_command,
    "ask_human": ask_human,
    "ask_human_choice": ask_human_choice,
    "remember_fact": remember_fact,
    "recall_memory": recall_memory,
}
