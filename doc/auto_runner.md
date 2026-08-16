# auto_runner.py

Auto mode orchestration: **plan once, approve once, run to the end.**

The core idea: fifty one-at-a-time confirmations is exhausting and,
past a certain point, not real consent — nobody's actually reading
command #47. Auto mode trades "approve every step" for "approve the
whole plan up front, then let it run," with three things that still
always interrupt regardless of the plan:

1. Paths outside the sandbox — already a hard block in `fs_tools.py`
   (raises `ValueError`, never even reaches `confirm()`), stronger than
   merely asking.
2. Destructive shell patterns like `rm`/`sudo`/`curl` — handled in
   `shell_tools.py` via `confirm(..., force_ask=True)` (see
   [shell_tools.md](shell_tools.md)).
3. A hard cap of `MAX_AUTO_TOOL_CALLS` (`30`) tool calls, so a plan that
   wanders doesn't run forever.

`AUTO_MODE` (from [agent_mode.md](agent_mode.md)) is flipped on **only
for the duration of one approved plan's execution**, then always reset
back to `False` in a `finally` block — so if this module's entry point
is never called, or the plan is rejected, the agent stays in ordinary
step mode where `confirm()` asks every time, exactly as before.

## `MAX_AUTO_TOOL_CALLS = 30`

Imported from [agent_config.py](agent_config.md), env
`MAX_AUTO_TOOL_CALLS`. Passed as `run_agent(...,
max_tool_calls=MAX_AUTO_TOOL_CALLS)` — see
[shared.md](shared.md) for how that cap is enforced.

## `_generate_plan(agent, user_request: str) -> str`

Asks the model for a plain-text plan via `agent.chat(planning_messages,
tools=None)` — **`tools=None` is deliberate**: during planning the
model should only describe what it intends to do, never actually do it.
If tools were available here, "write a plan" could quietly turn into
"start executing," defeating the whole point of asking for approval
before anything runs.

The planning prompt asks for a clear, numbered, concrete plan (naming
actual files/commands/directories, not vague descriptions) and
explicitly instructs the model not to perform any actions. Returns
`response.message.content`, or the literal string `"(model returned an
empty plan)"` if that's falsy.

## `run_with_auto_mode(agent, user_request, tools, tool_map, chat_logger=None) -> str`

Plans, writes `plan.md`, prints the plan, asks **one** approval
question, then runs to completion (or the tool-call cap). Returns the
final answer string — same shape `run_agent()` would return.

### Flow

1. `plan_text = _generate_plan(agent, user_request)`.
2. Writes `plan.md` directly via `fs_tools.resolve_path("plan.md")` —
   **not** through `confirm()`, since this is the artifact *being*
   reviewed, not a side effect the plan is asking permission for. Still
   goes through the sandboxed path resolver like every other write in
   the project. A write failure (`OSError`) prints a warning but doesn't
   block review — the human can still read the plan on screen.
3. Prints the plan to the terminal inside a bannered block, plus the
   saved path.
4. Asks **one** real question via `confirm(..., force_ask=True)` — this
   *is* the one real approval and must never be auto-skipped, even if
   `AUTO_MODE` somehow ended up `True` already. Not approved → returns
   `"Plan not approved — nothing was run."` without touching
   `AUTO_MODE` at all.
5. If approved: sets `agent_mode.AUTO_MODE = True`, builds a fresh
   3-message history (original request, the approved plan as an
   `"assistant"` message, and an instruction to execute it), and calls
   `run_agent(agent, messages, tools, tool_map, chat_logger=chat_logger,
   max_tool_calls=MAX_AUTO_TOOL_CALLS)`.
6. `finally`: always sets `agent_mode.AUTO_MODE = False`, whether the
   run finished normally, hit the tool-call cap, or raised. Auto mode
   never silently stays "on" past the plan it was approved for.

## Test coverage (`tests/test_auto_runner.py`)

`OllamaAgent`/`agent.chat`, `confirm()`, `fs_tools.resolve_path`, and
`shared.run_agent` are all mocked — no live model, filesystem writes,
or terminal prompts.

- `_generate_plan`: passes `tools=None` to `agent.chat`, returns the
  model's content, and falls back to the "(model returned an empty
  plan)" placeholder when content is falsy.
- `run_with_auto_mode`: plan.md written via the sandboxed resolver
  (verified it's not written through `confirm()`); a disk write failure
  is swallowed with a warning rather than blocking review; rejection
  returns the "not approved" message and leaves `AUTO_MODE` `False`;
  approval sets `AUTO_MODE = True` for the duration of `run_agent()`
  and resets it to `False` afterward — including when `run_agent`
  raises, proving the `finally` reset fires on the exception path too;
  `run_agent` is called with `max_tool_calls=MAX_AUTO_TOOL_CALLS` and
  the expected 3-message history; the approval prompt itself uses
  `force_ask=True`.
