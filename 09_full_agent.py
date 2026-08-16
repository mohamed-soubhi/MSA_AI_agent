"""The full agent: read/write/list/create files, run terminal commands,
and ask the human for clarification — all inside one sandbox, one
confirm() gate, and one JSONL log.

This merges the filesystem agent (07) and the terminal agent (08).
Nothing is reimplemented twice: write_file, run_command, ask_human, and
ask_human_choice are each imported from their one real implementation
(fs_tools.py, shell_tools.py, human_tools.py) — this file only wires
them together and owns the conversation loop.
"""

from shared import OllamaAgent, run_agent, section
from fs_tools import BASE_DIR, create_directory, list_directory, read_file, write_file
from shell_tools import run_command
from human_tools import ask_human, ask_human_choice
from chat_logger import get_logger
from auto_runner import run_with_auto_mode

# Control mode with this one flag. step (False) asks before every tool
# call, like before. auto (True) writes plan.md, prints the plan in
# full, asks ONE question, then runs to the end (still stopping for
# anything outside the sandbox or a destructive command — see
# auto_runner.py and shell_tools.py for exactly what still interrupts).
auto_mode = False

# PROMPT-LEVEL GUIDANCE — quality, not safety (pattern vs guarantee).
# The prompt ASKS for good behavior; the sandbox/allowlist/blocklist/
# confirm/timeout layers in fs_tools.py and shell_tools.py GUARANTEE
# the boundary. The non-interactive rule matters most: an interactive
# command ("npm create", a pip confirm) doesn't error here — it just
# hangs until the timeout kills it. And "--yes/--force" flags are only
# safe to suggest because the human still approves every command's
# exact text before it runs.
SYSTEM_PROMPT = """
You are an AI software engineering assistant.

You have access to tools for listing, reading, and writing files,
creating directories, running terminal commands, and asking the human
for clarification or a choice when something is ambiguous.

Rules:
- Always prefer non-interactive terminal commands.
- Never run commands that wait for user input.
- If a command has a non-interactive flag (such as --yes, --template, --force), use it.
- Before running a command, think about whether it could block.
- If a command fails, inspect the error and fix the problem.
- If a request is ambiguous, use ask_human or ask_human_choice instead of guessing.
- Keep changes as small as possible.
- Do not call run_command unless it is necessary.
- Do not invent tool results.
"""


def main() -> None:
    """Run the full agent: files, terminal, and human-in-the-loop clarification."""
    agent = OllamaAgent()
    tools = [
        list_directory, read_file, write_file, create_directory,
        run_command, ask_human, ask_human_choice,
    ]
    tool_map = {
        "list_directory": list_directory,
        "read_file": read_file,
        "write_file": write_file,
        "create_directory": create_directory,
        "run_command": run_command,
        "ask_human": ask_human,
        "ask_human_choice": ask_human_choice,
    }

    chat_logger = get_logger("full_agent", agent.model)

    print(section("Full agent (files + terminal + human-in-the-loop)"))
    print(f"Sandbox: {BASE_DIR}")
    print(f"Mode: {'auto (plan once, run to the end)' if auto_mode else 'step (asks before every tool call)'}")
    print("The agent can list, read, write, and create files, run terminal")
    print("commands, and ask you clarifying questions or offer a choice.")
    print("Writes, directory creation, and every command need your 'y' first")
    print("(hard gate, not skippable) — unless auto mode is on, in which case")
    print("you approve the whole plan once instead.")
    print("Type 'exit' to quit.")

    # The system prompt shapes behavior on EVERY turn — seed it once, up front.
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    try:
        while True:
            user_input = input("\nYou > ").strip()
            if user_input.lower() in {"exit", "quit", "q"}:
                chat_logger.session_end(reason="user_exit")
                break

            chat_logger.user_message(user_input)

            if auto_mode:
                # One plan, one approval, runs to the end (or the
                # tool-call cap) on its own. messages isn't extended
                # here — run_with_auto_mode manages its own message
                # list for the plan + execution turns.
                answer = run_with_auto_mode(agent, user_input, tools, tool_map, chat_logger=chat_logger)
            else:
                messages.append({"role": "user", "content": user_input})
                answer = run_agent(agent, messages, tools, tool_map, chat_logger=chat_logger)

            print(f"Agent > {answer}")

    except KeyboardInterrupt:
        print("\nInterrupted.")
        chat_logger.session_end(reason="keyboard_interrupt")

    except Exception as exc:
        chat_logger.error("main_loop_crashed", detail=str(exc))
        chat_logger.session_end(reason="crashed")
        raise


if __name__ == "__main__":
    main()
