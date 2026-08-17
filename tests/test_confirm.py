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
