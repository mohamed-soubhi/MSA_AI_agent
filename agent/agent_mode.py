"""The single auto/step mode toggle for the agent.

One boolean, checked in exactly one place: confirm() in confirm.py.
Every side effect in this project (fs_tools.write_file,
fs_tools.create_directory, shell_tools.run_command, human_tools.
approve_action) already goes through confirm() as its one approval
choke point -- so flipping THIS ONE FLAG changes approval behavior
everywhere, without touching any of those files individually.

Deliberately not a function parameter threaded through every call site:
the whole point of "checked in one place" is that tool code doesn't
need to know or care which mode it's running in. It just calls
confirm() like always; confirm() decides whether to actually ask.
"""

AUTO_MODE = False  # step mode, the default: confirm() asks every time
