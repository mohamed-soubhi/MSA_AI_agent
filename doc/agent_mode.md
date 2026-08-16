# agent_mode.py

The single auto/step mode toggle for the whole agent. One module-level
boolean, checked in exactly one place.

## `AUTO_MODE: bool` (default `False`)

- `False` (**step mode**, the default): `confirm()` asks before every
  side effect, as always.
- `True` (**auto mode**): `confirm()` auto-approves immediately, unless
  the caller passed `force_ask=True`.

Every side effect in this project (`fs_tools.write_file`,
`fs_tools.create_directory`, `shell_tools.run_command`,
`human_tools.approve_action`) already goes through `confirm()` as its
one approval choke point — so flipping this one flag changes approval
behavior everywhere, without touching any of those files individually.
See [confirm.md](confirm.md) for exactly how the flag is read.

**Deliberately not a function parameter** threaded through every call
site. The whole point of "checked in one place" is that tool code
doesn't need to know or care which mode it's running in — it just calls
`confirm()` like always, and `confirm()` decides whether to actually
ask.

## Lifecycle

Nothing in this module flips the flag — that's owned entirely by
`auto_runner.run_with_auto_mode()` (see [auto_runner.md](auto_runner.md)),
which sets it to `True` only for the duration of one approved plan's
execution and always resets it to `False` in a `finally` block. If
`run_with_auto_mode()` is never called, or a plan is rejected, the agent
stays in ordinary step mode for its entire session.

## Test coverage

Exercised indirectly through `tests/test_confirm.py` (mode-check
branches in `confirm()`) and `tests/test_auto_runner.py` (the flag is
set `True` during execution and reset to `False` afterward, including
on the reject/exception paths). No dedicated test file — a single
module-level boolean with no logic of its own doesn't need one; its
only behavior is what other modules do when they read/write it.
