"""Tests for POST /api/shutdown -- the config page's Close button.

The signal calls are monkeypatched throughout: the real implementation
SIGTERMs this process's whole process group (os.killpg), which --
called from inside a pytest process via TestClient -- would kill the
test run itself. Every test here captures the call instead of letting
it fire.
"""

import os
import signal

from fastapi.testclient import TestClient

from app.api import shutdown as shutdown_api
from app.main import create_app


def client():
    return TestClient(create_app())


def test_shutdown_returns_status_shutting_down(monkeypatch):
    monkeypatch.setattr(shutdown_api.os, "killpg", lambda pgid, sig: None)

    response = client().post("/api/shutdown")
    assert response.status_code == 200
    assert response.json() == {"status": "shutting_down"}


def test_shutdown_sigterms_the_whole_process_group(monkeypatch):
    calls = []
    monkeypatch.setattr(shutdown_api.os, "killpg", lambda pgid, sig: calls.append((pgid, sig)))

    client().post("/api/shutdown")

    assert calls == [(os.getpgrp(), signal.SIGTERM)]


def test_shutdown_falls_back_to_self_and_parent_without_process_groups(monkeypatch):
    # Simulate Windows: no killpg. The endpoint must then SIGTERM this
    # process and its immediate parent (the --reload supervisor / uv wrapper).
    def _no_killpg(pgid, sig):
        raise AttributeError("no killpg on this platform")

    kills = []
    monkeypatch.setattr(shutdown_api.os, "killpg", _no_killpg)
    monkeypatch.setattr(shutdown_api.os, "kill", lambda pid, sig: kills.append((pid, sig)))

    client().post("/api/shutdown")

    assert set(kills) == {(os.getpid(), signal.SIGTERM), (os.getppid(), signal.SIGTERM)}


def test_shutdown_swallows_errors_from_a_dead_parent(monkeypatch):
    # A failing os.kill (parent already gone) must not 500 the request.
    def _no_killpg(pgid, sig):
        raise OSError("no such process group")

    def _kill_raises(pid, sig):
        raise OSError("no such process")

    monkeypatch.setattr(shutdown_api.os, "killpg", _no_killpg)
    monkeypatch.setattr(shutdown_api.os, "kill", _kill_raises)

    response = client().post("/api/shutdown")
    assert response.status_code == 200
    assert response.json() == {"status": "shutting_down"}
