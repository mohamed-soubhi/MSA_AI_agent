"""Tests for human_tools.py — conversational human-in-the-loop tools.

These are model-invoked conversation tools (ask_human, ask_human_choice,
approve_action), distinct from confirm.py's hard gate: the model can
choose not to call them, so they carry no security guarantee on their
own. approve_action() delegates to the real confirm() gate so there's
exactly one approval experience in the project.
"""

import pytest

import human_tools as ht_mod
from human_tools import approve_action, ask_human, ask_human_choice


# --------------------------------------------------------------------------
# ask_human
# --------------------------------------------------------------------------

class TestAskHuman:
    @pytest.mark.tid("HUMAN-001")
    def test_returns_stripped_response(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "  blue  ")
        assert ask_human("What color?") == "blue"

    @pytest.mark.tid("HUMAN-002")
    def test_empty_response_returns_ask_again_message(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "")
        result = ask_human("What color?")
        assert "no answer" in result.lower()

    @pytest.mark.tid("HUMAN-003")
    def test_whitespace_only_response_treated_as_empty(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "   ")
        result = ask_human("What color?")
        assert "no answer" in result.lower()

    @pytest.mark.tid("HUMAN-004")
    def test_prints_the_question(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda prompt: "answer")
        ask_human("What is your favorite color?")
        captured = capsys.readouterr()
        assert "What is your favorite color?" in captured.out


# --------------------------------------------------------------------------
# ask_human_choice
# --------------------------------------------------------------------------

class TestAskHumanChoice:
    @pytest.mark.tid("HUMAN-005")
    def test_returns_selected_option_on_valid_choice(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "2")
        result = ask_human_choice("Pick one", ["red", "green", "blue"])
        assert result == "SELECTED: green"

    @pytest.mark.tid("HUMAN-006")
    def test_reprompts_on_non_numeric_input(self, monkeypatch):
        answers = iter(["not a number", "1"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
        result = ask_human_choice("Pick one", ["red", "green"])
        assert result == "SELECTED: red"

    @pytest.mark.tid("HUMAN-007")
    def test_reprompts_on_out_of_range_choice(self, monkeypatch):
        answers = iter(["0", "99", "2"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
        result = ask_human_choice("Pick one", ["red", "green"])
        assert result == "SELECTED: green"

    @pytest.mark.tid("HUMAN-008")
    def test_first_option_selectable(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "1")
        result = ask_human_choice("Pick one", ["only", "other"])
        assert result == "SELECTED: only"

    @pytest.mark.tid("HUMAN-009")
    def test_last_option_selectable(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "3")
        result = ask_human_choice("Pick one", ["a", "b", "c"])
        assert result == "SELECTED: c"

    @pytest.mark.tid("HUMAN-010")
    def test_fewer_than_two_options_returns_error_without_prompting(self, monkeypatch):
        called = []
        monkeypatch.setattr("builtins.input", lambda prompt: called.append(prompt) or "1")
        result = ask_human_choice("Pick one", ["only"])
        assert result.startswith("ERROR")
        assert called == []

    @pytest.mark.tid("HUMAN-011")
    def test_zero_options_returns_error(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "1")
        result = ask_human_choice("Pick one", [])
        assert result.startswith("ERROR")

    @pytest.mark.tid("HUMAN-012")
    def test_prints_numbered_options(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda prompt: "1")
        ask_human_choice("Pick one", ["alpha", "beta"])
        captured = capsys.readouterr()
        assert "1. alpha" in captured.out
        assert "2. beta" in captured.out


# --------------------------------------------------------------------------
# approve_action
# --------------------------------------------------------------------------

class TestApproveAction:
    @pytest.mark.tid("HUMAN-013")
    def test_approved_when_confirm_returns_true(self, monkeypatch):
        monkeypatch.setattr(ht_mod, "confirm", lambda action: True)
        assert approve_action("delete the file") == "APPROVED"

    @pytest.mark.tid("HUMAN-014")
    def test_rejected_when_confirm_returns_false(self, monkeypatch):
        monkeypatch.setattr(ht_mod, "confirm", lambda action: False)
        assert approve_action("delete the file") == "REJECTED"

    @pytest.mark.tid("HUMAN-015")
    def test_passes_action_text_through_to_confirm(self, monkeypatch):
        seen = []
        monkeypatch.setattr(ht_mod, "confirm", lambda action: seen.append(action) or True)
        approve_action("deploy to production")
        assert seen == ["deploy to production"]

    @pytest.mark.tid("HUMAN-016")
    def test_delegates_to_real_confirm_gate_not_a_reimplementation(self, monkeypatch):
        # approve_action must not have its own y/n prompt logic -- it
        # should call confirm() exactly once and return based on that.
        calls = []
        monkeypatch.setattr(ht_mod, "confirm", lambda action: calls.append(action) or False)
        approve_action("risky action")
        assert len(calls) == 1


# --------------------------------------------------------------------------
# human_tools — pluggable backend (set_human_backend / clear_human_backend)
# --------------------------------------------------------------------------

class TestHumanBackend:
    @pytest.mark.tid("HUMAN-017")
    def test_set_human_backend_routes_ask_human(self):
        calls = []
        def mock_backend(kind, question, options):
            calls.append((kind, question, options))
            return "Paris"

        ht_mod.set_human_backend(mock_backend)
        try:
            assert ask_human("What is the capital?") == "Paris"
            assert calls == [("ask", "What is the capital?", None)]
        finally:
            ht_mod.clear_human_backend()

    @pytest.mark.tid("HUMAN-018")
    def test_set_human_backend_routes_ask_human_choice(self):
        calls = []
        def mock_backend(kind, question, options):
            calls.append((kind, question, options))
            return "2"

        ht_mod.set_human_backend(mock_backend)
        try:
            assert ask_human_choice("Pick a color", ["red", "green", "blue"]) == "SELECTED: green"
            assert calls == [("choice", "Pick a color", ["red", "green", "blue"])]
        finally:
            ht_mod.clear_human_backend()

    @pytest.mark.tid("HUMAN-019")
    def test_set_human_backend_invalid_choice_returns_error_string(self):
        ht_mod.set_human_backend(lambda k, q, opts: "invalid")
        try:
            res = ask_human_choice("Pick", ["a", "b"])
            assert "invalid choice" in res.lower()
        finally:
            ht_mod.clear_human_backend()

    @pytest.mark.tid("HUMAN-020")
    def test_clear_human_backend_restores_terminal(self, monkeypatch):
        ht_mod.set_human_backend(lambda k, q, opts: "mocked")
        ht_mod.clear_human_backend()
        monkeypatch.setattr("builtins.input", lambda prompt: "live input")
        assert ask_human("Question?") == "live input"

