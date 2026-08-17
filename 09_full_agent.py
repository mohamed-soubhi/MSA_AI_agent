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
from memory import (
    load_token_usage, recall_memory, remember_fact, save_session_summary, save_token_usage,
)
from chat_logger import get_logger
from auto_runner import run_with_auto_mode
from agent_config import SYSTEM_PROMPT

# Control mode with this one flag. step (False) asks before every tool
# call, like before. auto (True) writes plan.md, prints the plan in
# full, asks ONE question, then runs to the end (still stopping for
# anything outside the sandbox or a destructive command — see
# auto_runner.py and shell_tools.py for exactly what still interrupts).
auto_mode = False

# SYSTEM_PROMPT now lives in agent_config.py (prompt-level guidance —
# quality, not safety; the sandbox/allowlist/blocklist/confirm/timeout
# layers in fs_tools.py and shell_tools.py are what GUARANTEE the
# boundary) — see that file to tune it or override it wholesale via the
# SYSTEM_PROMPT environment variable.


def _report_token_usage(agent) -> None:
    """Save this session's token count and print both numbers.

    Called exactly once, in a `finally` block around the whole session,
    so it always runs regardless of how the session ends (normal exit,
    Ctrl-C, or an unhandled crash) -- unlike save_session_summary(),
    this makes no extra model call, so there's no extra-failure risk to
    avoid on the crash path.

    agent.total_tokens is coerced to a plain int defensively (a test
    double without that attribute, or a non-numeric value, degrades to
    0 rather than crashing the shutdown path over a display feature).
    """
    session_tokens = agent.total_tokens if isinstance(agent.total_tokens, int) else 0
    new_total = save_token_usage(session_tokens)
    print(f"\nTokens used this session: {session_tokens}")
    print(f"Tokens used all-time (saved to memory): {new_total}")


def main() -> None:
    """Run the full agent: files, terminal, and human-in-the-loop clarification."""
    agent = OllamaAgent()
    tools = [
        list_directory, read_file, write_file, create_directory,
        run_command, ask_human, ask_human_choice,
        remember_fact, recall_memory,
    ]
    tool_map = {
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

    chat_logger = get_logger("full_agent", agent.model)

    print(section("Full agent (files + terminal + human-in-the-loop)"))
    print(f"Sandbox: {BASE_DIR}")
    print(f"Mode: {'auto (plan once, run to the end)' if auto_mode else 'step (asks before every tool call)'}")
    print("The agent can list, read, write, and create files, run terminal")
    print("commands, and ask you clarifying questions or offer a choice.")
    print("Writes, directory creation, and every command need your 'y' first")
    print("(hard gate, not skippable) — unless auto mode is on, in which case")
    print("you approve the whole plan once instead.")
    print(f"Tokens used all-time so far (loaded from memory): {load_token_usage()}")
    print("Type 'exit' to quit.")

    # The system prompt shapes behavior on EVERY turn — seed it once, up front.
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    try:
        while True:
            user_input = input("\nYou > ").strip()
            if user_input.lower() in {"exit", "quit", "q"}:
                save_session_summary(agent, messages)
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
        save_session_summary(agent, messages)
        chat_logger.session_end(reason="keyboard_interrupt")

    except Exception as exc:
        chat_logger.error("main_loop_crashed", detail=str(exc))
        chat_logger.session_end(reason="crashed")
        raise

    finally:
        _report_token_usage(agent)


if __name__ == "__main__":
    main()
