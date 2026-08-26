"""Tests for GET /api/memory endpoint."""

import json
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.api import memory as memory_api


def client():
    return TestClient(create_app())


def test_get_memory_file_not_found(tmp_path, monkeypatch):
    non_existent = tmp_path / "missing_memory.json"
    monkeypatch.setattr(memory_api, "MEMORY_FILE", str(non_existent))
    response = client().get("/api/memory")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is False
    assert data["entries"] == []
    assert data["token_usage_total"] == 0
    assert data["path"] == str(non_existent)


def test_get_memory_valid_file(tmp_path, monkeypatch):
    mem_file = tmp_path / "memory.json"
    sample_data = {
        "entries": [
            {"id": "1", "type": "fact", "text": "First fact", "tags": ["tag1"], "timestamp": "2026-08-01 10:00:00"},
            {"id": "2", "type": "summary", "text": "Second summary", "tags": ["tag2"], "timestamp": "2026-08-01 11:00:00"},
        ],
        "token_usage_total": 4200,
    }
    mem_file.write_text(json.dumps(sample_data), encoding="utf-8")
    monkeypatch.setattr(memory_api, "MEMORY_FILE", str(mem_file))

    response = client().get("/api/memory")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["token_usage_total"] == 4200
    assert len(data["entries"]) == 2
    # Should be reversed (newest first)
    assert data["entries"][0]["id"] == "2"
    assert data["entries"][0]["text"] == "Second summary"
    assert data["entries"][1]["id"] == "1"


def test_get_memory_corrupt_file(tmp_path, monkeypatch):
    mem_file = tmp_path / "corrupt_memory.json"
    mem_file.write_text("INVALID JSON CONTENT { [", encoding="utf-8")
    monkeypatch.setattr(memory_api, "MEMORY_FILE", str(mem_file))

    response = client().get("/api/memory")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["entries"] == []
    assert data["token_usage_total"] == 0


def test_get_memory_non_dict_json(tmp_path, monkeypatch):
    mem_file = tmp_path / "array_memory.json"
    mem_file.write_text("[\"not\", \"a\", \"dict\"]", encoding="utf-8")
    monkeypatch.setattr(memory_api, "MEMORY_FILE", str(mem_file))

    response = client().get("/api/memory")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["entries"] == []
    assert data["token_usage_total"] == 0
