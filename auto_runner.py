"""Auto mode orchestration: plan once, approve once, run to the end.

The core idea (from the assignment): what you approve IS the plan.
Fifty one-at-a-time confirmations is exhausting and, past a certain
point, not real consent — nobody's actually reading command #47. So
auto mode trades "approve every step" for "approve the whole plan up
front, then let it run," with three things that still always interrupt
regardless of the plan: paths outside the sandbox (already a hard block
in fs_tools.py, stronger than merely asking), destructive shell
patterns like rm/sudo/curl (shell_tools.py, force_ask=True), and a hard
cap of 30 tool calls so a plan that wanders doesn't run forever.

AUTO_MODE is flipped on ONLY for the duration of one approved plan's
execution, then always reset back to False in a finally block — so if
this function is never called, or the plan is rejected, the agent stays
in ordinary step mode where confirm() asks every time, exactly as
before.
"""

from pathlib import Path

import agent_mode
from confirm import confirm
from fs_tools import BASE_DIR
from shared import run_agent
from agent_config import MAX_AUTO_TOOL_CALLS

# MAX_AUTO_TOOL_CALLS now lives in agent_config.py — see that file to
# tune or override it via environment variable.


def _generate_plan(agent, user_request: str) -> str:
    """Ask the model for a plain-text plan, with NO tools available.

    Passing tools=None here is deliberate: during planning the model
    should only be describing what it intends to do, never actually
    doing it. If tools were available, "write a plan" could quietly
    turn into "start executing," defeating the whole point of asking
    for approval before anything runs.
    """
    planning_messages = [{
        "role": "user",
        "content": (
            f"Task: {user_request}\n\n"
            "Write a clear, numbered, step-by-step plan for how you would "
            "accomplish this task using the available tools (reading/writing "
            "files, creating directories, running terminal commands, asking "
            "for clarification). Do NOT perform any actions — this is a plan "
            "only, to be reviewed by a human before anything runs. Be "
            "concrete: name the actual files, commands, and directories "
            "you'd use, not vague descriptions."
        ),
    }]
    response = agent.chat(planning_messages, tools=None)
    return response.message.content or "(model returned an empty plan)"


def run_with_auto_mode(agent, user_request: str, tools, tool_map, chat_logger=None) -> str:
    """Plan, write plan.md, print it, ask once, then run to completion.

    Returns the final answer string, same shape as run_agent() would.
    If the human doesn't approve the plan, returns without running
    anything and AUTO_MODE is never turned on.
    """
    plan_text = _generate_plan(agent, user_request)

    # Write plan.md directly (not through confirm()) -- this is the
    # artifact BEING reviewed, not a side effect the plan itself is
    # asking permission for. Still goes through the sandboxed path
    # resolver, same as every other file write in this project.
    from fs_tools import resolve_path
    plan_path = resolve_path("plan.md")
    try:
        plan_path.write_text(plan_text, encoding="utf-8")
    except OSError as exc:
        # Plan couldn't be saved to disk, but the human can still review
        # it on screen and decide -- don't let a disk error block that.
        print(f"  (warning: could not write plan.md: {exc})")

    print("\n" + "=" * 60)
    print("PROPOSED PLAN")
    print("=" * 60)
    print(plan_text)
    print("=" * 60)
    print(f"(also saved to {plan_path})\n")

    approved = confirm(
        "Run the plan above to completion? File writes and commands inside "
        "the sandbox will run WITHOUT further prompts; anything outside the "
        "sandbox or a destructive command (rm/sudo/curl/etc) will still stop "
        f"and ask; hard cap of {MAX_AUTO_TOOL_CALLS} tool calls.",
        force_ask=True,  # this IS the one real approval — never auto-skip it
    )
    if not approved:
        return "Plan not approved — nothing was run."

    agent_mode.AUTO_MODE = True
    try:
        messages = [
            {"role": "user", "content": user_request},
            {"role": "assistant", "content": f"Plan (approved by human):\n\n{plan_text}"},
            {"role": "user", "content": "The plan is approved. Execute it now using the available tools."},
        ]
        return run_agent(
            agent, messages, tools, tool_map,
            chat_logger=chat_logger,
            max_tool_calls=MAX_AUTO_TOOL_CALLS,
        )
    finally:
        # Always return to step mode once this run ends, whether it
        # finished, hit the tool-call cap, or raised. Auto mode should
        # never silently stay "on" past the plan it was approved for.
        agent_mode.AUTO_MODE = False
