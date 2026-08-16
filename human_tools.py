"""Human-in-the-loop as a tool pattern: clarify, choose, approve — the
conversation, not the safety gate.

Two different things live in this project and must not be confused:
  - ask_human / ask_human_choice / approve_action (this file): the model
    CHOOSES to call these. They're conversational -- great for judgment
    calls, useless as a security boundary, because a model that decides
    not to call approve_action just... doesn't.
  - confirm() (confirm.py): a HARD gate that host code calls directly
    around real side effects (write_file, create_directory in
    fs_tools.py). The model cannot skip it -- it isn't a tool the model
    invokes, it's wired into the tool's own implementation.

approve_action() below now calls confirm() itself rather than
reimplementing its own y/n prompt. That was the one place this file
duplicated confirm()'s logic (timeout, sanitized prompt text, the
empty-input-means-yes default, audit logging) -- collapsing it onto the
real gate means there's exactly one approval experience in the whole
project, not two that can quietly drift apart.
"""

from confirm import confirm


def ask_human(question: str) -> str:
    """Ask the human for missing information and return the response.

    Args:
        question: The precise question the agent needs answered.
    """
    print(f"\n  [human input needed] {question}")
    response = input("  Your response > ").strip()
    return response or "The human provided no answer. Ask again more clearly."


def ask_human_choice(question: str, options: list[str]) -> str:
    """Ask the human to choose one option and return the selected value.

    Args:
        question: The decision the human needs to make.
        options: Two or more concrete choices to display.
    """
    if len(options) < 2:
        return "ERROR: provide at least two choices."

    print(f"\n  [human choice needed] {question}")
    for number, option in enumerate(options, start=1):
        print(f"    {number}. {option}")

    while True:
        response = input(f"  Choose 1-{len(options)} > ").strip()
        if response.isdigit() and 1 <= int(response) <= len(options):
            selected = options[int(response) - 1]
            return f"SELECTED: {selected}"
        print("  Please enter one of the displayed numbers.")


def approve_action(action: str) -> str:
    """Ask the human to approve or reject a proposed action.

    Args:
        action: A concrete description of the proposed side effect.

    NOTE: this is still a conversation pattern, not a hard gate — the
    model can choose not to call it at all. For a REAL side effect,
    the hard gate is confirm() wired directly into host code (see
    fs_tools.write_file / create_directory), which the model cannot
    skip. What changed here is only that WHEN the model does call this,
    it now goes through the exact same confirm() prompt, timeout, and
    fail-safe behavior as every other approval in the project — instead
    of a second, slightly different y/n prompt that could drift out of
    sync with the real one over time.
    """
    return "APPROVED" if confirm(action) else "REJECTED"
