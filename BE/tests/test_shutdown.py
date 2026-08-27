"""Tests for POST /api/shutdown -- the config page's Close button.

os.kill is monkeypatched throughout: the real implementation sends
SIGTERM to THIS process's own PID, which -- called from inside a
pytest process via TestClient -- would kill the test run itself. Every
test here captures the call instead of letting it fire.
"""

import os
import signal

from fastapi.testclient import TestClient

from app.api import shutdown as shutdown_api
from app.main import create_app


def client():
    return TestClient(create_app())


def test_shutdown_returns_status_shutting_down(monkeypatch):
    monkeypatch.setattr(shutdown_api.os, "kill", lambda pid, sig: None)

    response = client().post("/api/shutdown")
    assert response.status_code == 200
    assert response.json() == {"status": "shutting_down"}


def test_shutdown_sends_sigterm_to_its_own_pid(monkeypatch):
    calls = []
    monkeypatch.setattr(shutdown_api.os, "kill", lambda pid, sig: calls.append((pid, sig)))

    client().post("/api/shutdown")

    assert calls == [(os.getpid(), signal.SIGTERM)]
