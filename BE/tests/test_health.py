"""Tests for the /health endpoint -- the only route this scaffold has."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok_status():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_includes_service_name_and_version():
    client = TestClient(create_app())
    response = client.get("/health")
    body = response.json()
    assert body["service"] == "agent-backend"
    assert body["version"] == "0.1.0"
