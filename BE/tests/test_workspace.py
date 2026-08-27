"""Tests for GET /api/workspace/file -- the chat page's Preview tab
backend (app/api/workspace.py). Deliberately reuses fs_tools.read_file()/
resolve_path(), so this covers the route wiring (200/400 shape, response
model) rather than re-testing sandbox enforcement itself (already covered
in tests/test_fs_tools.py). fs_tools.BASE_DIR is isolated to tmp_path so a
real read can't touch the real workspace/.
"""

from fastapi.testclient import TestClient

import fs_tools
from app.main import create_app


def client():
    return TestClient(create_app())


def test_get_existing_file_returns_path_and_content(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)
    (tmp_path / "report.html").write_text("<h1>Report</h1>", encoding="utf-8")

    response = client().get("/api/workspace/file", params={"path": "report.html"})
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == "report.html"
    assert data["content"] == "<h1>Report</h1>"


def test_get_missing_file_returns_200_with_friendly_message(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)

    response = client().get("/api/workspace/file", params={"path": "missing.html"})
    assert response.status_code == 200
    assert "No such file" in response.json()["content"]


def test_get_directory_returns_200_with_friendly_message(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)
    (tmp_path / "subdir").mkdir()

    response = client().get("/api/workspace/file", params={"path": "subdir"})
    assert response.status_code == 200
    assert "Not a file" in response.json()["content"]


def test_sandbox_escape_attempt_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)

    response = client().get("/api/workspace/file", params={"path": "../outside.html"})
    assert response.status_code == 400
    assert "outside the working directory" in response.json()["detail"]


def test_nested_path_reads_from_subdirectory(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)
    nested = tmp_path / "plots"
    nested.mkdir()
    (nested / "chart.html").write_text("<div>chart</div>", encoding="utf-8")

    response = client().get("/api/workspace/file", params={"path": "plots/chart.html"})
    assert response.status_code == 200
    assert response.json()["content"] == "<div>chart</div>"
