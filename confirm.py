"""
confirm.py — hardened human-in-the-loop confirmation gate.

Threat model: `action` is a human-readable description of something an
LLM agent wants to do (write a file, run a shell command, delete data).
The STRING ITSELF may be attacker/model-influenced (e.g. via prompt
injection), so it must be treated as untrusted before it's ever printed
to a terminal or logged.

Design principle: fail CLOSED (deny) on every ambiguous or abnormal
condition — no stdin, timeout, unexpected exception, malformed input.
A confirmation gate that can be tricked into "fail open" is worse than
no gate at all.
"""

import logging
import re
import signal
import sys
import time
import uuid
from typing import Optional

import agent_mode
from agent_config import CONFIRM_TIMEOUT_SECONDS, CONFIRM_MAX_ACTION_LEN

logger = logging.getLogger("agent.confirm")

# Strip ANSI/terminal escape sequences before ever printing or logging
# `action`. Without this, a crafted action string could rewrite the
# terminal prompt, hide text, or (on vulnerable terminals) inject
# further escape-sequence attacks — a "confirm" prompt is exactly the
# place an attacker most wants to lie to the human reading it.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|[\x00-\x08\x0b-\x1f\x7f]")

# _MAX_ACTION_LEN now lives in agent_config.py (CONFIRM_MAX_ACTION_LEN) —
# see that file to tune or override it via environment variable.
_MAX_ACTION_LEN = CONFIRM_MAX_ACTION_LEN


class ConfirmTimeout(Exception):
    """Raised internally when the human doesn't answer in time."""


def _sanitize(action: str) -> str:
    """Make `action` safe to print/log: strip control chars, cap length."""
    if not isinstance(action, str):
        action = str(action)
    cleaned = _ANSI_ESCAPE.sub("", action)
    if len(cleaned) > _MAX_ACTION_LEN:
        cleaned = cleaned[:_MAX_ACTION_LEN] + " …[truncated]"
    return cleaned


def _timeout_handler(signum, frame):
    raise ConfirmTimeout()


def confirm(action: str, *, timeout_seconds: Optional[int] = CONFIRM_TIMEOUT_SECONDS, force_ask: bool = False) -> bool:
    """Ask the human before anything with side effects (write, run, delete).

    Confirm-before-act. The agent proposes; the human approves. Non-negotiable
    for tools that change the world. Every outcome (approved, denied, timed
    out, no-tty, auto-approved) is logged with a correlation id for audit
    purposes.

    THE ONE PLACE auto/step mode is decided: if agent_mode.AUTO_MODE is
    True and force_ask is False, this auto-approves immediately without
    prompting -- the human already approved the plan once, up front.
    Callers that represent one of the "always ask, even in auto mode"
    exceptions (a path outside the sandbox, a destructive shell pattern
    like rm/sudo/curl) pass force_ask=True to opt back into a real
    prompt regardless of mode. This is the single checkpoint every
    caller in the project shares -- individual tools never need their
    own mode-checking logic.

    Args:
        action: human-readable description of the proposed action.
                Treated as UNTRUSTED — sanitized before display/logging.
        timeout_seconds: if the human doesn't answer in time, deny and
                move on rather than hang the agent forever. None disables
                the timeout (use only for genuinely interactive sessions).
        force_ask: if True, always prompt even when AUTO_MODE is on.
                Use this for anything that must never be silently
                approved by a pre-approved plan.

    Returns:
        True if approved (explicitly, by empty-input default, or via
        auto-mode). False on every other outcome — no tty, timeout, bad
        input, Ctrl-C, unexpected exception. This function must never
        raise.
    """

    request_id = uuid.uuid4().hex[:8]
    clean_action = _sanitize(action)

    if agent_mode.AUTO_MODE and not force_ask:
        logger.info("confirm_auto_approved id=%s action=%r", request_id, clean_action)
        return True

    logger.info("confirm_requested id=%s action=%r auto_mode=%s force_ask=%s",
                request_id, clean_action, agent_mode.AUTO_MODE, force_ask)

    # No stdin attached (headless / CI / piped subprocess) -> nobody can
    # approve anything -> fail safe.
    if not sys.stdin.isatty():
        logger.warning("confirm_denied id=%s reason=no_tty", request_id)
        return False

    old_handler = None
    try:
        # --- Set a hard timeout so a forgotten prompt can't hang the ---
        # agent indefinitely (SIGALRM is POSIX-only; fine for Linux/RPi).
        if timeout_seconds is not None and hasattr(signal, "SIGALRM"):
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout_seconds)

        # Default is YES on empty input (bare Enter) -- shown explicitly
        # in the prompt so a human skimming fast still sees what a blank
        # answer means before they hit Enter.
        prompt = f"  [confirm:{request_id}] {clean_action}\n            Proceed? (Y/n, Enter = yes) "
        raw_answer = input(prompt)

    except ConfirmTimeout:
        logger.warning(
            "confirm_denied id=%s reason=timeout_%ss", request_id, timeout_seconds
        )
        return False

    except EOFError:
        # stdin closed mid-read -> no human to ask -> fail safe (deny).
        logger.warning("confirm_denied id=%s reason=eof", request_id)
        return False

    except KeyboardInterrupt:
        # Human explicitly hit Ctrl-C -> treat as an explicit denial,
        # not a crash.
        logger.warning("confirm_denied id=%s reason=keyboard_interrupt", request_id)
        return False

    except Exception:
        # Any other unexpected error talking to the terminal -> deny,
        # never let a confirmation gate crash into an unclear state.
        logger.exception("confirm_denied id=%s reason=unexpected_error", request_id)
        return False

    finally:
        # Always disarm the alarm and restore the previous handler,
        # even on the happy path, so we never leak a pending SIGALRM
        # into unrelated code later in the process.
        if timeout_seconds is not None and hasattr(signal, "SIGALRM"):
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)

    answer = raw_answer.strip().lower()
    # Empty input (bare Enter) counts as approval, same as "y"/"yes".
    # Every other non-empty answer that isn't y/yes is a denial.
    approved = answer == "" or answer in {"y", "yes"}

    logger.info(
        "confirm_%s id=%s raw_answer=%r",
        "approved" if approved else "denied",
        request_id,
        answer,
    )
    return approved
