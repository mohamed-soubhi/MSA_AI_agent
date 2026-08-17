"""Tests for confirm.py — the human-in-the-loop confirmation gate.

confirm() must fail CLOSED (return False) on every ambiguous/abnormal
condition. These tests exercise every branch: happy path (y/yes/empty),
every denial path (no/other, no tty, EOF, KeyboardInterrupt, timeout,
unexpected exception), and the untrusted-input sanitizer.
"""

import time

import pytest

import agent_mode
import confirm as confirm_mod
from confirm import ConfirmTimeout, _sanitize, confirm


@pytest.fixture(autouse=True)
def reset_auto_mode():
    """Guarantee AUTO_MODE starts (and ends) False for every test in this
    file, regardless of what TestAutoMode below does to it."""
    agent_mode.AUTO_MODE = False
    yield
    agent_mode.AUTO_MODE = False


@pytest.fixture(autouse=True)
def reset_stdin_lock():
    """Guarantee confirm._stdin_lock starts (and ends) unlocked for every
    test in this file.

    _stdin_lock is a real, process-global threading.Lock -- one test
    (the real-timeout case) deliberately leaves it held, on purpose,
    mirroring the actual orphaned-reader-thread scenario the lock
    exists to guard against. Without this reset, that held lock would
    leak into every later test in the same pytest process and make them
    fail with "stdin_busy" for a reason that has nothing to do with
    what they're testing.
    """
    if confirm_mod._stdin_lock.locked():
        confirm_mod._stdin_lock.release()
    yield
    if confirm_mod._stdin_lock.locked():
        confirm_mod._stdin_lock.release()


# --------------------------------------------------------------------------
# _sanitize
# --------------------------------------------------------------------------

class TestSanitize:
    @pytest.mark.tid("CONFIRM-001")
    def test_plain_string_passes_through(self):
        assert _sanitize("write config.txt") == "write config.txt"

    @pytest.mark.tid("CONFIRM-002")
    def test_strips_ansi_escape_sequences(self):
        assert _sanitize("\x1b[31mDANGER\x1b[0m delete all") == "DANGER delete all"

    @pytest.mark.tid("CONFIRM-003")
    def test_strips_control_characters(self):
        assert _sanitize("ok\x00.txt\x07") == "ok.txt"

    @pytest.mark.tid("CONFIRM-004")
    def test_truncates_long_action_and_marks_it(self):
        long_action = "a" * 1000
        result = _sanitize(long_action)
        assert len(result) < 1000
        assert result.endswith("…[truncated]")

    @pytest.mark.tid("CONFIRM-005")
    def test_non_string_input_is_stringified(self):
        assert _sanitize(12345) == "12345"

    @pytest.mark.tid("CONFIRM-006")
    def test_empty_string(self):
        assert _sanitize("") == ""


# --------------------------------------------------------------------------
# confirm() — no tty
# --------------------------------------------------------------------------

class TestConfirmNoTty:
    @pytest.mark.tid("CONFIRM-007")
    def test_denies_when_stdin_is_not_a_tty(self, monkeypatch):
        monkeypatch.setattr(confirm_mod.sys.stdin, "isatty", lambda: False)
        assert confirm("delete everything") is False


# --------------------------------------------------------------------------
# confirm() — interactive answers (tty simulated)
# --------------------------------------------------------------------------

@pytest.fixture
def tty(monkeypatch):
    """Pretend stdin is a real terminal so confirm() proceeds to input()."""
    monkeypatch.setattr(confirm_mod.sys.stdin, "isatty", lambda: True)


class TestConfirmAnswers:
    @pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES", "  yes  ", ""])
    @pytest.mark.tid("CONFIRM-008")
    def test_approves_on_yes_variants_and_bare_enter(self, tty, monkeypatch, answer):
        monkeypatch.setattr("builtins.input", lambda prompt: answer)
        assert confirm("write file", timeout_seconds=None) is True

    @pytest.mark.parametrize("answer", ["n", "no", "N", "nope", "maybe", "1"])
    @pytest.mark.tid("CONFIRM-009")
    def test_denies_on_anything_else(self, tty, monkeypatch, answer):
        monkeypatch.setattr("builtins.input", lambda prompt: answer)
        assert confirm("write file", timeout_seconds=None) is False

    @pytest.mark.tid("CONFIRM-010")
    def test_denies_on_eof(self, tty, monkeypatch):
        def raise_eof(prompt):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        assert confirm("write file", timeout_seconds=None) is False

    @pytest.mark.tid("CONFIRM-011")
    def test_denies_on_keyboard_interrupt(self, tty, monkeypatch):
        def raise_kbi(prompt):
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", raise_kbi)
        assert confirm("write file", timeout_seconds=None) is False

    @pytest.mark.tid("CONFIRM-012")
    def test_denies_on_unexpected_exception(self, tty, monkeypatch):
        def raise_err(prompt):
            raise RuntimeError("terminal exploded")

        monkeypatch.setattr("builtins.input", raise_err)
        assert confirm("write file", timeout_seconds=None) is False

    @pytest.mark.tid("CONFIRM-013")
    def test_action_string_is_sanitized_before_use(self, tty, monkeypatch):
        seen_prompt = {}

        def fake_input(prompt):
            seen_prompt["value"] = prompt
            return "y"

        monkeypatch.setattr("builtins.input", fake_input)
        confirm("\x1b[31minjected\x1b[0m", timeout_seconds=None)
        assert "\x1b" not in seen_prompt["value"]


# --------------------------------------------------------------------------
# confirm() — timeout handling
#
# ROB-01: timeout is enforced via a background daemon thread + queue.get(
# timeout=...), not signal.alarm() -- the old approach raised ValueError
# ("signal only works in main thread") whenever confirm() was called
# from a worker thread, which shared._run_tool_with_timeout does for
# every tool call. The new mechanism works from any calling thread and
# needs no POSIX-only signal, so there's no skipif guard here anymore.
# --------------------------------------------------------------------------

class TestConfirmTimeout:
    @pytest.mark.tid("CONFIRM-014")
    def test_denies_on_timeout(self, tty, monkeypatch):
        def blocking_input(prompt):
            raise ConfirmTimeout()

        monkeypatch.setattr("builtins.input", blocking_input)
        assert confirm("slow action", timeout_seconds=1) is False

    @pytest.mark.tid("CONFIRM-015")
    def test_real_timeout_denies_when_input_never_returns_in_time(self, tty, monkeypatch):
        # input() genuinely outlives the timeout window -- confirms the
        # queue.get(timeout=...) wait itself, not just ConfirmTimeout
        # being raised synchronously like CONFIRM-014 does.
        def slow_input(prompt):
            time.sleep(0.3)
            return "y"

        monkeypatch.setattr("builtins.input", slow_input)
        assert confirm("slow action", timeout_seconds=0.05) is False

    @pytest.mark.tid("CONFIRM-016")
    def test_none_timeout_disables_timeout(self, tty, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        assert confirm("write file", timeout_seconds=None) is True

    @pytest.mark.tid("CONFIRM-023")
    def test_timeout_works_when_called_from_a_worker_thread(self, tty, monkeypatch):
        # The exact ROB-01 scenario: confirm() invoked from a non-main
        # thread. signal.alarm() would raise ValueError here; the
        # thread+queue approach must not.
        import threading

        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        outcome = {}

        def call_from_thread():
            outcome["result"] = confirm("write file", timeout_seconds=5)

        worker = threading.Thread(target=call_from_thread)
        worker.start()
        worker.join(timeout=5)
        assert outcome.get("result") is True


# --------------------------------------------------------------------------
# confirm() — stdin lock / orphaned-reader race
#
# Regression tests for a real bug found via log analysis (2026-08-17): a
# tool call abandoned by shared.TOOL_TIMEOUT_SECONDS (30s) while a human
# was still deciding on a confirm() prompt left that prompt's background
# input() reader thread alive, still listening on stdin, for up to
# CONFIRM_TIMEOUT_SECONDS (120s) more. The very next confirm() call (a
# different, unrelated prompt) started a SECOND input() reader on the
# same stdin -- two threads racing for one line of input. The human's
# answer to the second prompt could be silently consumed by the first,
# orphaned one instead, leaving the second prompt hanging with nothing
# arriving (observed as: type an answer, session goes silent, no
# tool_result or session_end ever logged).
# --------------------------------------------------------------------------

class TestStdinLockRace:
    @pytest.mark.tid("CONFIRM-024")
    def test_second_confirm_denied_while_first_still_holds_lock(self, tty, monkeypatch):
        # Reproduce the bug: first call times out (leaving its reader
        # thread -- and the lock -- alive), second call must NOT start
        # its own input() reader to race for the same stdin.
        def slow_input(prompt):
            time.sleep(0.3)
            return "y"

        monkeypatch.setattr("builtins.input", slow_input)
        first = confirm("first, slow action", timeout_seconds=0.05)
        assert first is False  # ConfirmTimeout -- lock deliberately left held

        second_input_called = []
        monkeypatch.setattr(
            "builtins.input",
            lambda prompt: second_input_called.append(prompt) or "y",
        )
        second = confirm("second, unrelated action", timeout_seconds=1)

        assert second is False
        assert second_input_called == []  # never raced for stdin

    @pytest.mark.tid("CONFIRM-025")
    def test_stdin_busy_denial_is_logged(self, tty, monkeypatch, caplog):
        def slow_input(prompt):
            time.sleep(0.3)
            return "y"

        monkeypatch.setattr("builtins.input", slow_input)
        confirm("first, slow action", timeout_seconds=0.05)

        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        with caplog.at_level("WARNING", logger="agent.confirm"):
            confirm("second, unrelated action", timeout_seconds=1)

        assert any("stdin_busy" in r.message for r in caplog.records)

    @pytest.mark.tid("CONFIRM-026")
    def test_lock_released_after_normal_answer_so_next_call_proceeds(self, tty, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        first = confirm("first action", timeout_seconds=None)
        assert first is True

        second_input_called = []
        monkeypatch.setattr(
            "builtins.input",
            lambda prompt: second_input_called.append(prompt) or "y",
        )
        second = confirm("second action", timeout_seconds=None)

        assert second is True
        assert len(second_input_called) == 1  # got its own real prompt

    @pytest.mark.tid("CONFIRM-027")
    def test_lock_released_after_eof_so_next_call_proceeds(self, tty, monkeypatch):
        def raise_eof(prompt):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        first = confirm("first action", timeout_seconds=None)
        assert first is False

        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        second = confirm("second action", timeout_seconds=None)
        assert second is True

    @pytest.mark.tid("CONFIRM-028")
    def test_lock_not_held_after_no_tty_denial(self, monkeypatch):
        # The no-tty short-circuit returns before ever touching the lock
        # -- must not leave it (wrongly) held for the next real call.
        monkeypatch.setattr(confirm_mod.sys.stdin, "isatty", lambda: False)
        confirm("write file")
        assert not confirm_mod._stdin_lock.locked()

    @pytest.mark.tid("CONFIRM-029")
    def test_lock_not_held_after_auto_mode_approval(self, monkeypatch):
        # Auto-mode short-circuit also never touches the lock.
        monkeypatch.setattr(agent_mode, "AUTO_MODE", True)
        confirm("write file")
        assert not confirm_mod._stdin_lock.locked()


# --------------------------------------------------------------------------
# confirm() — auto mode (agent_mode.AUTO_MODE / force_ask)
# --------------------------------------------------------------------------

class TestAutoMode:
    @pytest.mark.tid("CONFIRM-017")
    def test_auto_mode_approves_without_prompting(self, monkeypatch):
        monkeypatch.setattr(agent_mode, "AUTO_MODE", True)
        monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(
            AssertionError("input() must not be called when auto-approved")
        ))
        assert confirm("write file") is True

    @pytest.mark.tid("CONFIRM-018")
    def test_auto_mode_skips_tty_check_too(self, monkeypatch):
        monkeypatch.setattr(agent_mode, "AUTO_MODE", True)
        monkeypatch.setattr(confirm_mod.sys.stdin, "isatty", lambda: False)
        assert confirm("write file") is True

    @pytest.mark.tid("CONFIRM-019")
    def test_force_ask_still_prompts_in_auto_mode(self, tty, monkeypatch):
        monkeypatch.setattr(agent_mode, "AUTO_MODE", True)
        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        assert confirm("dangerous command", force_ask=True, timeout_seconds=None) is True

    @pytest.mark.tid("CONFIRM-020")
    def test_force_ask_in_auto_mode_can_still_be_denied(self, tty, monkeypatch):
        monkeypatch.setattr(agent_mode, "AUTO_MODE", True)
        monkeypatch.setattr("builtins.input", lambda prompt: "n")
        assert confirm("dangerous command", force_ask=True, timeout_seconds=None) is False

    @pytest.mark.tid("CONFIRM-021")
    def test_step_mode_prompts_regardless_of_force_ask(self, tty, monkeypatch):
        monkeypatch.setattr(agent_mode, "AUTO_MODE", False)
        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        assert confirm("write file", force_ask=True, timeout_seconds=None) is True

    @pytest.mark.tid("CONFIRM-022")
    def test_default_force_ask_is_false(self, monkeypatch):
        monkeypatch.setattr(agent_mode, "AUTO_MODE", True)
        # No force_ask passed at all -- should still auto-approve.
        assert confirm("write file") is True
