"""Give the agent a terminal, safely: allowlist + blocklist + human confirm
+ timeout — a layer, not a fortress.

Four independent layers, stacked. Each one narrows what a command could
do; none of them alone is a guarantee, but together the surviving space
is small and every command still needs a human's explicit "y" before it
touches anything:

  1. Allowlist — only these programs may be launched at all.
  2. Blocklist  — a command containing an obviously dangerous pattern
                   (rm, sudo, curl, wget, chmod, a ">" redirect, etc)
                   always forces a real human prompt, even in auto
                   mode. Not a silent reject — a human can still say
                   yes to the exact text, but a pre-approved plan can
                   never run one of these unattended.
  3. confirm()  — every other command still goes through the normal
                   confirm() gate, which auto-approves in auto mode
                   (the plan already covered it) or asks in step mode.
  4. Timeout    — a command that hangs (waiting on stdin, an infinite
                   loop) is killed after TIMEOUT_SECONDS rather than
                   blocking the agent loop forever.

Honest limitation, stated rather than hidden: layers 1-2 can be talked
around by an ALLOWED interpreter (python3, node) running arbitrary code
internally — `python3 -c "..."` is still "python3", and a blocklist
built from string patterns can't reason about what a script does. This
is why layer 3 is not optional: the human reviewing the exact command
text before it runs is the real backstop here, not the lists.
"""

import logging
import shlex
import subprocess

from confirm import confirm
from fs_tools import BASE_DIR
from agent_config import (
    SHELL_ALLOWED as ALLOWED,
    SHELL_BLOCKED as BLOCKED,
    SHELL_TIMEOUT_SECONDS as TIMEOUT_SECONDS,
    SHELL_MAX_OUTPUT_LINES as MAX_OUTPUT_LINES,
)

logger = logging.getLogger("agent.shell_tools")

# ALLOWED, BLOCKED, TIMEOUT_SECONDS, and MAX_OUTPUT_LINES now live in
# agent_config.py — see that file to tune or override any of them via
# environment variable (SHELL_ALLOWED, SHELL_BLOCKED are comma-separated).


def run_command(command: str) -> str:
    """Run a non-interactive shell command inside the sandboxed working directory.

    Commands must not require keyboard input. For package generators,
    always use flags that disable prompts, such as --yes, --template,
    or other non-interactive options.

    Returns exit_code, stdout, and stderr as clearly labeled fields, so
    you can tell "succeeded with noisy stderr" apart from "failed" —
    check exit_code, not just whether stderr is non-empty.

    Args:
        command: A complete non-interactive shell command.
    """
    command = command.strip()
    if not command:
        return "Blocked: empty command."

    # Extract the program name properly (shlex, not a naive .split()) so
    # quoted arguments containing spaces don't confuse which token is
    # actually the program being launched.
    try:
        first_token = shlex.split(command)[0]
    except ValueError as e:
        # Unbalanced quotes etc -- malformed input, not a crash.
        logger.warning("shell_blocked_unparseable command=%r error=%s", command, e)
        return f"Blocked: could not parse command ({e})."

    program = first_token.split("/")[-1]  # strip any path prefix, e.g. "/usr/bin/python3"

    if program not in ALLOWED:  # Layer 1
        logger.warning("shell_blocked_not_allowlisted program=%r command=%r", program, command)
        return f"Blocked: '{program}' is not in the allowlist {sorted(ALLOWED)}."

    if any(bad in command for bad in BLOCKED):  # Layer 2
        # Not an unconditional reject: a human can still approve this
        # exact command text. force_ask=True means it interrupts and
        # asks even when agent_mode.AUTO_MODE is on -- a pre-approved
        # plan does not get to silently run rm/sudo/curl/etc, no matter
        # how thorough the plan looked when it was approved.
        logger.warning("shell_dangerous_pattern_detected command=%r", command)
        if not confirm(f"DANGEROUS pattern detected, approve anyway?\nrun: {command}", force_ask=True):
            return "Blocked: command contains a forbidden pattern and was not approved."
    elif not confirm(f"run: {command}"):  # Layer 3 — human sees the exact text
        return "Command cancelled by user."

    logger.info("shell_running command=%r cwd=%s", command, BASE_DIR)
    try:
        result = subprocess.run(
            command, shell=True, cwd=BASE_DIR,  # cwd sandbox: runs inside the workspace
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        )
        logger.info("shell_finished command=%r exit_code=%s", command, result.returncode)
        return _format_result(result.returncode, result.stdout, result.stderr)

    except subprocess.TimeoutExpired as exc:
        logger.warning("shell_timeout command=%r timeout=%ss", command, TIMEOUT_SECONDS)
        # A killed process has no real exit code -- report what's known
        # (partial output, if any was captured before the kill) plus a
        # clear reason, rather than a bare "timed out" with no context.
        partial_stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        partial_stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return _format_result(
            None, partial_stdout, partial_stderr,
            note=f"Timed out after {TIMEOUT_SECONDS}s and was killed.",
        )

    except Exception as error:
        logger.error("shell_error command=%r error=%s", command, error)
        return _format_result(None, "", "", note=f"Could not run command: {error}")


def _format_result(exit_code, stdout: str, stderr: str, note: str = "") -> str:
    """Format a command's outcome as distinct, clearly-labeled fields —
    exit code, stdout, stderr — instead of merging them into one blob.
    The model (and a human reading the log) needs the exit code and the
    two streams kept separate: a nonzero exit with empty stderr means
    something different than a zero exit with stderr chatter on it.
    Each stream is truncated independently so a giant stdout can't
    crowd out a short but important stderr message, or vice versa.
    """
    def _cap(text: str) -> str:
        text = text.strip()
        if not text:
            return "(empty)"
        lines = text.split("\n")
        if len(lines) > MAX_OUTPUT_LINES:
            omitted = len(lines) - MAX_OUTPUT_LINES
            kept = "\n".join(lines[-MAX_OUTPUT_LINES:])
            return f"[... {omitted} lines omitted ...]\n\n{kept}"
        return text

    lines = [f"exit_code: {exit_code if exit_code is not None else '(none — process killed)'}"]
    if note:
        lines.append(f"note: {note}")
    lines.append(f"stdout:\n{_cap(stdout)}")
    lines.append(f"stderr:\n{_cap(stderr)}")
    return "\n".join(lines)
