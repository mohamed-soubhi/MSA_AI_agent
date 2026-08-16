"""Tests for log_config.py — env-var-overridable logging settings.

Only the two parsing helpers have real branching logic; the module-level
constants are exercised indirectly through chat_logger's tests.
"""

import pytest

from log_config import _env_bool, _env_int_or_none


class TestEnvBool:
    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "True", "yes", "YES", "on", "On"])
    @pytest.mark.tid("LOGCFG-001")
    def test_truthy_values(self, monkeypatch, raw):
        monkeypatch.setenv("SOME_FLAG", raw)
        assert _env_bool("SOME_FLAG", False) is True

    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", "", "banana"])
    @pytest.mark.tid("LOGCFG-002")
    def test_falsy_or_unrecognized_values(self, monkeypatch, raw):
        monkeypatch.setenv("SOME_FLAG", raw)
        assert _env_bool("SOME_FLAG", True) is False

    @pytest.mark.tid("LOGCFG-003")
    def test_missing_env_var_uses_default_true(self, monkeypatch):
        monkeypatch.delenv("SOME_FLAG", raising=False)
        assert _env_bool("SOME_FLAG", True) is True

    @pytest.mark.tid("LOGCFG-004")
    def test_missing_env_var_uses_default_false(self, monkeypatch):
        monkeypatch.delenv("SOME_FLAG", raising=False)
        assert _env_bool("SOME_FLAG", False) is False

    @pytest.mark.tid("LOGCFG-005")
    def test_whitespace_is_trimmed(self, monkeypatch):
        monkeypatch.setenv("SOME_FLAG", "  true  ")
        assert _env_bool("SOME_FLAG", False) is True


class TestEnvIntOrNone:
    @pytest.mark.tid("LOGCFG-006")
    def test_missing_env_var_uses_default(self, monkeypatch):
        monkeypatch.delenv("SOME_INT", raising=False)
        assert _env_int_or_none("SOME_INT", 42) == 42

    @pytest.mark.tid("LOGCFG-007")
    def test_missing_env_var_default_none(self, monkeypatch):
        monkeypatch.delenv("SOME_INT", raising=False)
        assert _env_int_or_none("SOME_INT", None) is None

    @pytest.mark.parametrize("raw", ["none", "None", "NONE", "  none  "])
    @pytest.mark.tid("LOGCFG-008")
    def test_literal_none_string_returns_none(self, monkeypatch, raw):
        monkeypatch.setenv("SOME_INT", raw)
        assert _env_int_or_none("SOME_INT", 42) is None

    @pytest.mark.tid("LOGCFG-009")
    def test_numeric_string_parsed_as_int(self, monkeypatch):
        monkeypatch.setenv("SOME_INT", "12345")
        assert _env_int_or_none("SOME_INT", 42) == 12345

    @pytest.mark.tid("LOGCFG-010")
    def test_non_numeric_string_raises(self, monkeypatch):
        monkeypatch.setenv("SOME_INT", "not-a-number")
        with pytest.raises(ValueError):
            _env_int_or_none("SOME_INT", 42)
