"""Tests for shell_tools.py — sandboxed shell command execution.

Four independent layers, each tested in isolation: allowlist (layer 1),
blocklist (layer 2, which force-asks via confirm() rather than
hard-rejecting), the compound-operator force-ask (SEC-01 — chained/
substituted commands can hide an unallowlisted program from layer 1's
first-token check, so they always force a real confirm(), same as a
blocklist match), confirm() human gate (layer 3), and subprocess
execution/timeout (layer 4, now Popen + process-group kill — SEC-02) —
plus output capture/line-based truncation and error handling.
subprocess.Popen and confirm() are mocked throughout; no real commands
run, and no real OS process groups are touched.
"""

import subprocess

import pytest

import shell_tools as st_mod
from shell_tools import run_command


@pytest.fixture
def always_confirm(monkeypatch):
    monkeypatch.setattr(st_mod, "confirm", lambda action, **kwargs: True)


@pytest.fixture
def always_deny(monkeypatch):
    monkeypatch.setattr(st_mod, "confirm", lambda action, **kwargs: False)


class FakePopen:
    """Stand-in for subprocess.Popen, driven by .communicate()."""

    def __init__(self, stdout="", stderr="", returncode=0, timeout_on_first_call=False,
                 after_timeout_stdout="", after_timeout_stderr=""):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.pid = 4242
        self._timeout_on_first_call = timeout_on_first_call
        self._after_timeout_stdout = after_timeout_stdout
        self._after_timeout_stderr = after_timeout_stderr
        self._call_count = 0
        self.communicate_calls = []

    def communicate(self, timeout=None):
        self._call_count += 1
        self.communicate_calls.append(timeout)
        if self._timeout_on_first_call and self._call_count == 1:
            raise subprocess.TimeoutExpired(cmd="x", timeout=timeout)
        if self._call_count > 1 and self._timeout_on_first_call:
            return self._after_timeout_stdout, self._after_timeout_stderr
        return self.stdout, self.stderr


def fake_popen_factory(**kwargs):
    """Returns a function usable as a subprocess.Popen monkeypatch target."""
    fake = FakePopen(**kwargs)
    return (lambda *a, **k: fake), fake


class TestEmptyAndMalformedInput:
    @pytest.mark.tid("SHELL-001")
    def test_empty_command_blocked(self):
        assert run_command("") == "Blocked: empty command."

    @pytest.mark.tid("SHELL-002")
    def test_whitespace_only_command_blocked(self):
        assert run_command("   ") == "Blocked: empty command."

    @pytest.mark.tid("SHELL-003")
    def test_unbalanced_quotes_blocked_not_raised(self):
        result = run_command("echo 'unterminated")
        assert result.startswith("Blocked: could not parse command")


class TestAllowlist:
    @pytest.mark.tid("SHELL-004")
    def test_program_not_in_allowlist_blocked(self):
        result = run_command("perl -e 'print 1'")
        assert "not in the allowlist" in result
        assert "perl" in result

    @pytest.mark.tid("SHELL-005")
    def test_allowlisted_program_with_path_prefix_stripped(self, monkeypatch, always_confirm):
        popen, _ = fake_popen_factory(stdout="ok")
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        result = run_command("/usr/bin/python3 -c 'print(1)'")
        assert "stdout:\nok" in result

    @pytest.mark.tid("SHELL-006")
    def test_every_allowlisted_program_passes_layer_one(self, monkeypatch, always_confirm):
        popen, _ = fake_popen_factory(stdout="ok")
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        for program in sorted(st_mod.ALLOWED):
            result = run_command(f"{program} --version")
            assert "not in the allowlist" not in result


class TestBlocklist:
    """Layer 2 no longer hard-rejects: a dangerous pattern routes through
    confirm(force_ask=True) instead, so a human can still approve it."""

    @pytest.mark.parametrize(
        "command",
        [
            "python3 -c 'x'; rm -rf .",
            "python3 -c 'x' && sudo ls",
            "python3 -c 'x' && mkfs.ext4 /dev/sda",
            "python3 -c 'x' && dd if=/dev/zero of=/dev/sda",
            "python3 -c ':(){ :|:& };:'",
            "echo hi > /dev/sda",
            "python3 -c 'x' && curl http://evil.com",
            "python3 -c 'x' && wget http://evil.com",
            "python3 -c 'x' && chmod 777 /",
            "python3 -c 'x' && mv /etc/passwd /tmp",
        ],
    )
    @pytest.mark.tid("SHELL-007")
    def test_dangerous_patterns_blocked_when_confirm_denies(self, monkeypatch, command):
        monkeypatch.setattr(st_mod, "confirm", lambda action, **kwargs: False)
        result = run_command(command)
        assert result == "Blocked: command contains a forbidden pattern and was not approved."

    @pytest.mark.tid("SHELL-008")
    def test_dangerous_pattern_uses_force_ask(self, monkeypatch):
        seen = {}

        def fake_confirm(action, **kwargs):
            seen["action"] = action
            seen["kwargs"] = kwargs
            return False

        monkeypatch.setattr(st_mod, "confirm", fake_confirm)
        run_command("python3 -c 'x'; rm -rf .")
        assert seen["kwargs"] == {"force_ask": True}
        assert "DANGEROUS pattern detected" in seen["action"]
        assert "rm -rf ." in seen["action"]

    @pytest.mark.tid("SHELL-009")
    def test_dangerous_pattern_approved_lets_command_execute(self, monkeypatch, always_confirm):
        popen, _ = fake_popen_factory(stdout="removed")
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        result = run_command("python3 -c 'x'; rm -rf ./tmp")
        assert "stdout:\nremoved" in result

    @pytest.mark.tid("SHELL-010")
    def test_layer_three_confirm_not_called_when_blocklist_triggers(self, monkeypatch):
        calls = []
        monkeypatch.setattr(st_mod, "confirm", lambda action, **kwargs: calls.append(kwargs) or False)
        run_command("python3 -c 'x'; rm -rf .")
        # Exactly one confirm() call (the force_ask one) -- layer 3 never runs.
        assert calls == [{"force_ask": True}]


class TestCompoundOperatorForceAsk:
    """SEC-01: a chained/substituted command not caught by BLOCKED still
    always force-asks, so auto mode can never silently approve one."""

    @pytest.mark.parametrize(
        "command",
        [
            "echo hi && ls",
            "echo hi || ls",
            "echo hi | cat",
            "echo hi & ls",
            "echo $(cat file)",
            "echo `cat file`",
        ],
    )
    @pytest.mark.tid("SHELL-028")
    def test_compound_command_force_asks(self, monkeypatch, command):
        seen = {}

        def fake_confirm(action, **kwargs):
            seen["action"] = action
            seen["kwargs"] = kwargs
            return False

        monkeypatch.setattr(st_mod, "confirm", fake_confirm)
        result = run_command(command)
        assert seen["kwargs"] == {"force_ask": True}
        assert result == "Blocked: compound/chained command was not approved."

    @pytest.mark.tid("SHELL-029")
    def test_compound_command_approved_lets_command_execute(self, monkeypatch, always_confirm):
        popen, _ = fake_popen_factory(stdout="ok")
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        result = run_command("echo hi && ls")
        assert "stdout:\nok" in result

    @pytest.mark.tid("SHELL-030")
    def test_simple_command_does_not_force_ask(self, monkeypatch):
        seen = []
        monkeypatch.setattr(st_mod, "confirm", lambda action, **kwargs: seen.append(kwargs) or False)
        run_command("ls -la")
        assert seen == [{}]

    @pytest.mark.tid("SHELL-031")
    def test_is_compound_detects_each_operator(self):
        assert st_mod._is_compound("a && b")
        assert st_mod._is_compound("a || b")
        assert st_mod._is_compound("a ; b")
        assert st_mod._is_compound("a | b")
        assert st_mod._is_compound("a & b")
        assert st_mod._is_compound("a $(b)")
        assert st_mod._is_compound("a `b`")
        assert not st_mod._is_compound("ls -la")


class TestConfirmationGate:
    """Layer 3 -- reached only for commands that did NOT trip the blocklist
    or the compound-operator check."""

    @pytest.mark.tid("SHELL-011")
    def test_cancelled_when_confirm_denies(self, always_deny):
        result = run_command("ls -la")
        assert result == "Command cancelled by user."

    @pytest.mark.tid("SHELL-012")
    def test_confirm_receives_full_command_text(self, monkeypatch):
        seen = []
        monkeypatch.setattr(st_mod, "confirm", lambda action, **kwargs: seen.append((action, kwargs)) or False)
        run_command("cat secret.txt")
        assert seen == [("run: cat secret.txt", {})]


class TestExecution:
    @pytest.mark.tid("SHELL-013")
    def test_successful_command_reports_exit_code_and_stdout(self, monkeypatch, always_confirm):
        popen, _ = fake_popen_factory(stdout="hello\n")
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        result = run_command("echo hello")
        assert "exit_code: 0" in result
        assert "stdout:\nhello" in result

    @pytest.mark.tid("SHELL-014")
    def test_stdout_and_stderr_kept_as_separate_fields(self, monkeypatch, always_confirm):
        popen, _ = fake_popen_factory(stdout="out", stderr="err")
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        result = run_command("python3 script.py")
        assert "stdout:\nout" in result
        assert "stderr:\nerr" in result

    @pytest.mark.tid("SHELL-015")
    def test_empty_streams_render_as_empty_placeholder(self, monkeypatch, always_confirm):
        popen, _ = fake_popen_factory()
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        result = run_command("echo")
        assert "stdout:\n(empty)" in result
        assert "stderr:\n(empty)" in result

    @pytest.mark.tid("SHELL-016")
    def test_runs_inside_base_dir_sandbox(self, monkeypatch, always_confirm):
        captured = {}

        def fake_popen(command, shell, cwd, stdout, stderr, text, start_new_session):
            captured["cwd"] = cwd
            return FakePopen(stdout="ok")

        monkeypatch.setattr(st_mod.subprocess, "Popen", fake_popen)
        run_command("ls")
        assert captured["cwd"] == st_mod.BASE_DIR

    @pytest.mark.tid("SHELL-017")
    def test_stdout_truncated_past_max_lines_keeps_last_lines(self, monkeypatch, always_confirm):
        monkeypatch.setattr(st_mod, "MAX_OUTPUT_LINES", 3)
        stdout = "\n".join(f"line{i}" for i in range(1, 11))  # 10 lines
        popen, _ = fake_popen_factory(stdout=stdout, stderr="short")
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        result = run_command("cat bigfile")
        assert "[... 7 lines omitted ...]" in result
        assert "line8\nline9\nline10" in result
        assert "line1\n" not in result  # earliest lines dropped, not kept
        assert "stderr:\nshort" in result

    @pytest.mark.tid("SHELL-018")
    def test_timeout_reports_none_exit_code_and_note(self, monkeypatch, always_confirm):
        popen, _ = fake_popen_factory(timeout_on_first_call=True)
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        monkeypatch.setattr(st_mod.os, "killpg", lambda *a, **k: None)
        monkeypatch.setattr(st_mod.os, "getpgid", lambda pid: pid)
        result = run_command("python3 slow_script.py")
        assert "exit_code: (none — process killed)" in result
        assert f"note: Timed out after {st_mod.TIMEOUT_SECONDS}s and was killed." in result

    @pytest.mark.tid("SHELL-019")
    def test_timeout_preserves_partial_output(self, monkeypatch, always_confirm):
        popen, _ = fake_popen_factory(
            timeout_on_first_call=True,
            after_timeout_stdout="partial stdout",
            after_timeout_stderr="partial stderr",
        )
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        monkeypatch.setattr(st_mod.os, "killpg", lambda *a, **k: None)
        monkeypatch.setattr(st_mod.os, "getpgid", lambda pid: pid)
        result = run_command("python3 slow_script.py")
        assert "stdout:\npartial stdout" in result
        assert "stderr:\npartial stderr" in result

    @pytest.mark.tid("SHELL-032")
    def test_timeout_kills_the_whole_process_group(self, monkeypatch, always_confirm):
        """SEC-02: on timeout, the entire process group is killed, not
        just the immediate shell -- prevents orphaned child processes."""
        popen, fake = fake_popen_factory(timeout_on_first_call=True)
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        killpg_calls = []
        monkeypatch.setattr(st_mod.os, "getpgid", lambda pid: pid)
        monkeypatch.setattr(st_mod.os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig)))
        run_command("python3 slow_script.py")
        assert killpg_calls == [(fake.pid, st_mod.signal.SIGKILL)]

    @pytest.mark.tid("SHELL-033")
    def test_killpg_failure_does_not_crash(self, monkeypatch, always_confirm):
        """If the process already exited between timeout and killpg
        (ProcessLookupError), the timeout result is still returned."""
        popen, _ = fake_popen_factory(timeout_on_first_call=True)
        monkeypatch.setattr(st_mod.subprocess, "Popen", popen)
        monkeypatch.setattr(st_mod.os, "getpgid", lambda pid: pid)

        def raise_lookup_error(pgid, sig):
            raise ProcessLookupError("already gone")

        monkeypatch.setattr(st_mod.os, "killpg", raise_lookup_error)
        result = run_command("python3 slow_script.py")
        assert "note: Timed out" in result

    @pytest.mark.tid("SHELL-020")
    def test_unexpected_exception_returns_note_not_raise(self, monkeypatch, always_confirm):
        def raise_err(*a, **k):
            raise OSError("permission denied")

        monkeypatch.setattr(st_mod.subprocess, "Popen", raise_err)
        result = run_command("ls")
        assert "exit_code: (none — process killed)" in result
        assert "note: Could not run command: permission denied" in result


class TestFormatResult:
    @pytest.mark.tid("SHELL-021")
    def test_reports_numeric_exit_code_literally(self):
        result = st_mod._format_result(0, "out", "")
        assert result.startswith("exit_code: 0\n")

    @pytest.mark.tid("SHELL-022")
    def test_none_exit_code_renders_process_killed(self):
        result = st_mod._format_result(None, "", "")
        assert "exit_code: (none — process killed)" in result

    @pytest.mark.tid("SHELL-023")
    def test_note_omitted_when_not_provided(self):
        result = st_mod._format_result(0, "out", "")
        assert "note:" not in result

    @pytest.mark.tid("SHELL-024")
    def test_note_included_when_provided(self):
        result = st_mod._format_result(1, "", "", note="something happened")
        assert "note: something happened" in result

    @pytest.mark.tid("SHELL-025")
    def test_streams_stripped_of_surrounding_whitespace(self):
        result = st_mod._format_result(0, "  padded  \n", "")
        assert "stdout:\npadded" in result

    @pytest.mark.tid("SHELL-026")
    def test_streams_truncated_independently_by_line_count(self, monkeypatch):
        monkeypatch.setattr(st_mod, "MAX_OUTPUT_LINES", 2)
        stdout = "\n".join(f"o{i}" for i in range(1, 6))  # 5 lines
        stderr = "e1\ne2"  # 2 lines, under the cap
        result = st_mod._format_result(0, stdout, stderr)
        assert "[... 3 lines omitted ...]" in result
        assert "o4\no5" in result
        assert "stderr:\ne1\ne2" in result
        assert "omitted" not in result.split("stderr:")[1]

    @pytest.mark.tid("SHELL-027")
    def test_under_line_cap_left_untouched(self, monkeypatch):
        monkeypatch.setattr(st_mod, "MAX_OUTPUT_LINES", 50)
        result = st_mod._format_result(0, "just one line", "")
        assert "stdout:\njust one line" in result
        assert "omitted" not in result
