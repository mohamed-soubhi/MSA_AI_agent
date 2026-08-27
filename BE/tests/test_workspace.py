"""Tests for GET /api/workspace/file -- the chat page's Preview tab
backend (app/api/workspace.py). Deliberately reuses fs_tools.read_file()/
resolve_path(), so this covers the route wiring (200/400 shape, response
model) rather than re-testing sandbox enforcement itself (already covered
in tests/test_fs_tools.py). fs_tools.BASE_DIR is isolated to tmp_path so a
real read can't touch the real workspace/.
"""

from fastapi.testclient import TestClient

import fs_tools
from app.api import workspace as workspace_api
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


# --------------------------------------------------------------------------
# GET /api/workspace/file-raw -- same sandbox, served as a real HTML
# document (Content-Type: text/html) for the Preview <iframe> to
# navigate to directly, instead of JSON-wrapped for srcdoc injection.
# --------------------------------------------------------------------------

def test_raw_existing_file_returns_content_as_html_document(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)
    (tmp_path / "report.html").write_text(
        "<h1>Report</h1><script>console.log('plot')</script>", encoding="utf-8"
    )

    response = client().get("/api/workspace/file-raw", params={"path": "report.html"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == "<h1>Report</h1><script>console.log('plot')</script>"


def test_raw_missing_file_returns_200_with_friendly_message(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)

    response = client().get("/api/workspace/file-raw", params={"path": "missing.html"})
    assert response.status_code == 200
    assert "No such file" in response.text


def test_raw_sandbox_escape_attempt_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)

    response = client().get("/api/workspace/file-raw", params={"path": "../outside.html"})
    assert response.status_code == 400
    assert "outside the working directory" in response.json()["detail"]


# --------------------------------------------------------------------------
# POST /api/workspace/open -- open the workspace folder in the OS file
# manager. The real launcher (explorer.exe / xdg-open / open) is
# monkeypatched so tests never spawn a window.
# --------------------------------------------------------------------------

def test_open_workspace_launches_file_manager_on_base_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)
    opened = []
    monkeypatch.setattr(workspace_api, "_open_in_file_manager", lambda target: opened.append(target))

    response = client().post("/api/workspace/open")

    assert response.status_code == 200
    assert response.json() == {"path": str(tmp_path), "opened": True}
    assert opened == [tmp_path]


def test_open_workspace_returns_500_when_launcher_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path)

    def _boom(target):
        raise OSError("no file manager")

    monkeypatch.setattr(workspace_api, "_open_in_file_manager", _boom)

    response = client().post("/api/workspace/open")
    assert response.status_code == 500
    assert "Could not open" in response.json()["detail"]


def test_running_under_wsl_is_false_off_linux(monkeypatch):
    monkeypatch.setattr(workspace_api.sys, "platform", "win32")
    assert workspace_api._running_under_wsl() is False
