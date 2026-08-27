"""Tests for GET/POST /api/config -- the interactive config editor's API.

Each test points config_schema.AGENT_ENV_FILE / BE_ENV_FILE at an
isolated tmp_path so nothing ever touches the real agent/.env or BE/.env.
"""

from fastapi.testclient import TestClient

from app.core import config_schema
from app.main import create_app


def client():
    return TestClient(create_app())


def test_get_config_returns_all_fields():
    response = client().get("/api/config")
    assert response.status_code == 200
    fields = response.json()["fields"]
    assert len(fields) == len(config_schema.FIELDS)


def test_get_config_field_shape():
    fields = client().get("/api/config").json()["fields"]
    field = next(f for f in fields if f["key"] == "CHAT_TIMEOUT_SECONDS")
    assert field["section"] == "Chat / Ollama"
    assert field["type"] == "int"
    assert field["value"] == "60"


def test_be_field_reflects_live_settings():
    fields = client().get("/api/config").json()["fields"]
    field = next(f for f in fields if f["key"] == "BE_PORT")
    assert field["value"] == "8000"


def test_agent_field_includes_true_default():
    # Computed via an isolated subprocess (config_schema.agent_defaults()),
    # not a hand-maintained duplicate -- see that function's docstring.
    fields = client().get("/api/config").json()["fields"]
    field = next(f for f in fields if f["key"] == "CHAT_TIMEOUT_SECONDS")
    assert field["default"] == "60"


def test_be_field_includes_true_default():
    fields = client().get("/api/config").json()["fields"]
    field = next(f for f in fields if f["key"] == "BE_PORT")
    assert field["default"] == "8000"


def test_default_ignores_a_real_env_var_override(monkeypatch):
    # The whole point of computing defaults via an isolated subprocess:
    # an env var set in THIS process must not leak into the reported default.
    config_schema.agent_defaults.cache_clear()
    monkeypatch.setenv("CHAT_TIMEOUT_SECONDS", "99999")
    try:
        fields = client().get("/api/config").json()["fields"]
        field = next(f for f in fields if f["key"] == "CHAT_TIMEOUT_SECONDS")
        assert field["default"] == "60"
    finally:
        config_schema.agent_defaults.cache_clear()


def test_save_config_writes_agent_env_file(tmp_path, monkeypatch):
    agent_env = tmp_path / "agent.env"
    monkeypatch.setattr(config_schema, "AGENT_ENV_FILE", agent_env)

    response = client().post("/api/config", json={"values": {"CHAT_TIMEOUT_SECONDS": "99"}})
    assert response.status_code == 200
    assert response.json()["saved"]["agent"] == ["CHAT_TIMEOUT_SECONDS"]
    assert 'CHAT_TIMEOUT_SECONDS="99"' in agent_env.read_text()


def test_save_config_writes_be_env_file(tmp_path, monkeypatch):
    be_env = tmp_path / "be.env"
    monkeypatch.setattr(config_schema, "BE_ENV_FILE", be_env)

    response = client().post("/api/config", json={"values": {"BE_PORT": "9000"}})
    assert response.json()["saved"]["be"] == ["BE_PORT"]
    assert 'BE_PORT="9000"' in be_env.read_text()


def test_save_config_splits_agent_and_be_keys(tmp_path, monkeypatch):
    agent_env = tmp_path / "agent.env"
    be_env = tmp_path / "be.env"
    monkeypatch.setattr(config_schema, "AGENT_ENV_FILE", agent_env)
    monkeypatch.setattr(config_schema, "BE_ENV_FILE", be_env)

    response = client().post(
        "/api/config",
        json={"values": {"CHAT_TIMEOUT_SECONDS": "99", "BE_PORT": "9000"}},
    )
    saved = response.json()["saved"]
    assert saved["agent"] == ["CHAT_TIMEOUT_SECONDS"]
    assert saved["be"] == ["BE_PORT"]


def test_save_config_ignores_unknown_keys(tmp_path, monkeypatch):
    agent_env = tmp_path / "agent.env"
    monkeypatch.setattr(config_schema, "AGENT_ENV_FILE", agent_env)

    response = client().post("/api/config", json={"values": {"NOT_A_REAL_SETTING": "x"}})
    saved = response.json()["saved"]
    assert saved["agent"] == []
    assert saved["be"] == []


def test_save_config_preserves_existing_unrelated_lines(tmp_path, monkeypatch):
    agent_env = tmp_path / "agent.env"
    agent_env.write_text('# a comment\nMEMORY_ENABLED="true"\n', encoding="utf-8")
    monkeypatch.setattr(config_schema, "AGENT_ENV_FILE", agent_env)

    client().post("/api/config", json={"values": {"CHAT_TIMEOUT_SECONDS": "99"}})
    content = agent_env.read_text()
    assert "# a comment" in content
    assert 'MEMORY_ENABLED="true"' in content
    assert 'CHAT_TIMEOUT_SECONDS="99"' in content


def test_save_config_updates_existing_key_in_place(tmp_path, monkeypatch):
    agent_env = tmp_path / "agent.env"
    agent_env.write_text('CHAT_TIMEOUT_SECONDS="10"\n', encoding="utf-8")
    monkeypatch.setattr(config_schema, "AGENT_ENV_FILE", agent_env)

    client().post("/api/config", json={"values": {"CHAT_TIMEOUT_SECONDS": "99"}})
    content = agent_env.read_text()
    assert content.count("CHAT_TIMEOUT_SECONDS") == 1
    assert '"99"' in content


def test_save_config_escapes_newlines_for_round_trip(tmp_path, monkeypatch):
    agent_env = tmp_path / "agent.env"
    monkeypatch.setattr(config_schema, "AGENT_ENV_FILE", agent_env)

    multiline = "line one\nline two"
    client().post("/api/config", json={"values": {"SYSTEM_PROMPT": multiline}})
    content = agent_env.read_text()
    assert "\\n" in content
    assert "\nline two" not in content  # not a literal raw newline mid-value


def test_save_config_empty_value_removes_existing_key_line(tmp_path, monkeypatch):
    agent_env = tmp_path / "agent.env"
    agent_env.write_text(
        '# a comment\nWORKSPACE_DIR="/mnt/c/old/workspace"\nMEMORY_ENABLED="true"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(config_schema, "AGENT_ENV_FILE", agent_env)

    response = client().post("/api/config", json={"values": {"WORKSPACE_DIR": ""}})
    assert response.status_code == 200
    content = agent_env.read_text()
    assert "WORKSPACE_DIR" not in content
    # unrelated lines untouched
    assert "# a comment" in content
    assert 'MEMORY_ENABLED="true"' in content


def test_save_config_empty_value_for_new_key_writes_nothing(tmp_path, monkeypatch):
    agent_env = tmp_path / "agent.env"
    monkeypatch.setattr(config_schema, "AGENT_ENV_FILE", agent_env)

    response = client().post("/api/config", json={"values": {"WORKSPACE_DIR": ""}})
    assert response.status_code == 200
    assert not agent_env.exists() or "WORKSPACE_DIR" not in agent_env.read_text()


def test_config_page_is_served():
    response = client().get("/config")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Agent Configuration" in response.text
