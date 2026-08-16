"""Tests for shell_tools.py — sandboxed shell command execution.

Four independent layers, each tested in isolation: allowlist (layer 1),
blocklist (layer 2, which now force-asks via confirm() rather than
hard-rejecting), confirm() human gate (layer 3), and subprocess timeout
(layer 4) — plus output capture/line-based truncation and error
handling. subprocess.run and confirm() are mocked throughout; no real
commands run.
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


def fake_completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


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
        monkeypatch.setattr(st_mod.subprocess, "run", lambda *a, **k: fake_completed(stdout="ok"))
        result = run_command("/usr/bin/python3 -c 'print(1)'")
        assert "stdout:\nok" in result

    @pytest.mark.tid("SHELL-006")
    def test_every_allowlisted_program_passes_layer_one(self, monkeypatch, always_confirm):
        monkeypatch.setattr(st_mod.subprocess, "run", lambda *a, **k: fake_completed(stdout="ok"))
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
        monkeypatch.setattr(
            st_mod.subprocess, "run", lambda *a, **k: fake_completed(stdout="removed")
        )
        result = run_command("python3 -c 'x'; rm -rf ./tmp")
        assert "stdout:\nremoved" in result

    @pytest.mark.tid("SHELL-010")
    def test_layer_three_confirm_not_called_when_blocklist_triggers(self, monkeypatch):
        calls = []
        monkeypatch.setattr(st_mod, "confirm", lambda action, **kwargs: calls.append(kwargs) or False)
        run_command("python3 -c 'x'; rm -rf .")
        # Exactly one confirm() call (the force_ask one) -- layer 3 never runs.
        assert calls == [{"force_ask": True}]


class TestConfirmationGate:
    """Layer 3 -- reached only for commands that did NOT trip the blocklist."""

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
        monkeypatch.setattr(
            st_mod.subprocess, "run", lambda *a, **k: fake_completed(stdout="hello\n")
        )
        result = run_command("echo hello")
        assert "exit_code: 0" in result
        assert "stdout:\nhello" in result

    @pytest.mark.tid("SHELL-014")
    def test_stdout_and_stderr_kept_as_separate_fields(self, monkeypatch, always_confirm):
        monkeypatch.setattr(
            st_mod.subprocess, "run",
            lambda *a, **k: fake_completed(stdout="out", stderr="err"),
        )
        result = run_command("python3 script.py")
        assert "stdout:\nout" in result
        assert "stderr:\nerr" in result

    @pytest.mark.tid("SHELL-015")
    def test_empty_streams_render_as_empty_placeholder(self, monkeypatch, always_confirm):
        monkeypatch.setattr(st_mod.subprocess, "run", lambda *a, **k: fake_completed())
        result = run_command("echo")
        assert "stdout:\n(empty)" in result
        assert "stderr:\n(empty)" in result

    @pytest.mark.tid("SHELL-016")
    def test_runs_inside_base_dir_sandbox(self, monkeypatch, always_confirm):
        captured = {}

        def fake_run(command, shell, cwd, capture_output, text, timeout):
            captured["cwd"] = cwd
            return fake_completed(stdout="ok")

        monkeypatch.setattr(st_mod.subprocess, "run", fake_run)
        run_command("ls")
        assert captured["cwd"] == st_mod.BASE_DIR

    @pytest.mark.tid("SHELL-017")
    def test_stdout_truncated_past_max_lines_keeps_last_lines(self, monkeypatch, always_confirm):
        monkeypatch.setattr(st_mod, "MAX_OUTPUT_LINES", 3)
        stdout = "\n".join(f"line{i}" for i in range(1, 11))  # 10 lines
        monkeypatch.setattr(
            st_mod.subprocess, "run",
            lambda *a, **k: fake_completed(stdout=stdout, stderr="short"),
        )
        result = run_command("cat bigfile")
        assert "[... 7 lines omitted ...]" in result
        assert "line8\nline9\nline10" in result
        assert "line1\n" not in result  # earliest lines dropped, not kept
        assert "stderr:\nshort" in result

    @pytest.mark.tid("SHELL-018")
    def test_timeout_reports_none_exit_code_and_note(self, monkeypatch, always_confirm):
        def raise_timeout(*a, **k):
            raise subprocess.TimeoutExpired(cmd="python3 slow.py", timeout=120)

        monkeypatch.setattr(st_mod.subprocess, "run", raise_timeout)
        result = run_command("python3 slow_script.py")
        assert "exit_code: (none — process killed)" in result
        assert "note: Timed out after 120s and was killed." in result

    @pytest.mark.tid("SHELL-019")
    def test_timeout_preserves_partial_output(self, monkeypatch, always_confirm):
        def raise_timeout(*a, **k):
            raise subprocess.TimeoutExpired(
                cmd="python3 slow.py", timeout=120,
                output="partial stdout", stderr="partial stderr",
            )

        monkeypatch.setattr(st_mod.subprocess, "run", raise_timeout)
        result = run_command("python3 slow_script.py")
        assert "stdout:\npartial stdout" in result
        assert "stderr:\npartial stderr" in result

    @pytest.mark.tid("SHELL-020")
    def test_unexpected_exception_returns_note_not_raise(self, monkeypatch, always_confirm):
        def raise_err(*a, **k):
            raise OSError("permission denied")

        monkeypatch.setattr(st_mod.subprocess, "run", raise_err)
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
