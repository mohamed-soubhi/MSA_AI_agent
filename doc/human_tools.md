# human_tools.py

Human-in-the-loop as a **tool** pattern: clarify, choose, approve — the
conversation, not the safety gate.

Two different things live in this project and must not be confused:

- **`ask_human` / `ask_human_choice` / `approve_action` (this file)**:
  the model *chooses* to call these. Great for judgment calls, but
  useless as a security boundary — a model that decides not to call
  `approve_action` just doesn't, and nothing stops it.
- **`confirm()` (`confirm.py`)**: a hard gate that host code calls
  directly around real side effects (`write_file`, `create_directory`
  in `fs_tools.py`). The model cannot skip it — it isn't a tool the
  model invokes, it's wired into the tool's own implementation. See
  [confirm.md](confirm.md).

`approve_action()` calls `confirm()` itself rather than reimplementing
its own y/n prompt, so there's exactly one approval experience in the
whole project instead of two that could quietly drift apart.

## `ask_human(question: str) -> str`

Prints the question, reads one line via `input()`, returns the stripped
response. Empty/whitespace-only input returns the literal string
`"The human provided no answer. Ask again more clearly."` instead of an
empty string — gives the model something actionable to do next rather
than silently propagating `""`.

## `ask_human_choice(question: str, options: list[str]) -> str`

Presents a numbered list of `options` and loops on `input()` until the
human enters a valid number.

- `len(options) < 2` → returns `"ERROR: provide at least two choices."`
  immediately, **without prompting** (nothing sensible to choose between).
- Valid selection → `f"SELECTED: {selected}"`.
- Invalid input (non-digit, out of range) → reprints the prompt and
  loops; never raises or returns garbage.

## `approve_action(action: str) -> str`

Delegates straight to `confirm(action)` and returns `"APPROVED"` or
`"REJECTED"`. No independent prompt logic, no independent timeout or
sanitization — all of that is `confirm()`'s job (see
[confirm.md](confirm.md)). Because this is a tool the model *chooses*
to invoke, it is **not** a substitute for the hard gate on `write_file`/
`create_directory` — those still go through `confirm()` directly and
cannot be bypassed by the model skipping this tool.

## Wiring

`07_filesystem_tools.py` offers `ask_human` and `ask_human_choice` to
the agent (not `approve_action` — the banner text explicitly notes it
would just duplicate the same `confirm()` prompt the real gate already
provides).

## Test coverage (`tests/test_human_tools.py`)

- **`ask_human`**: stripped response, empty response → ask-again
  message, whitespace-only response treated as empty, question text is
  printed.
- **`ask_human_choice`**: valid selection, reprompt on non-numeric
  input, reprompt on out-of-range input, first/last option selectable,
  fewer-than-two options returns an error *without* ever calling
  `input()`, zero options returns an error, numbered options are
  printed correctly.
- **`approve_action`**: approved/rejected mapped from `confirm()`'s
  return value, the exact `action` string is passed through unchanged,
  and `confirm()` is called exactly once per invocation (confirming
  there's no parallel prompt logic left in this file).
