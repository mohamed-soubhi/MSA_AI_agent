"""Tests for GET /api/models -- backs the config editor's "Load models"
button. ollama.Client is mocked throughout; no real Ollama server needed.
"""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import models as models_api
from app.main import create_app


def client():
    return TestClient(create_app())


def fake_model(name, size=0, family="", parameter_size="", quantization_level="",
                modified_at=None):
    details = SimpleNamespace(
        family=family, parameter_size=parameter_size, quantization_level=quantization_level,
    )
    return SimpleNamespace(model=name, size=size, details=details, modified_at=modified_at)


class FakeOllamaClient:
    def __init__(self, models):
        self._models = models

    def list(self):
        return SimpleNamespace(models=self._models)


def test_splits_local_and_cloud_by_suffix(monkeypatch):
    fake_models = [
        fake_model("qwen2.5:latest", size=4_683_087_332, family="qwen2",
                    parameter_size="7.6B", quantization_level="Q4_K_M"),
        fake_model("qwen3.5:cloud", size=346),
    ]
    monkeypatch.setattr(models_api.ollama, "Client", lambda: FakeOllamaClient(fake_models))

    response = client().get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert [m["name"] for m in data["local"]] == ["qwen2.5:latest"]
    assert [m["name"] for m in data["cloud"]] == ["qwen3.5:cloud"]
    assert data["error"] is None


def test_local_model_includes_specs(monkeypatch):
    fake_models = [
        fake_model("qwen2.5:latest", size=4_683_087_332, family="qwen2",
                    parameter_size="7.6B", quantization_level="Q4_K_M"),
    ]
    monkeypatch.setattr(models_api.ollama, "Client", lambda: FakeOllamaClient(fake_models))

    data = client().get("/api/models").json()
    model = data["local"][0]
    assert model["family"] == "qwen2"
    assert model["parameter_size"] == "7.6B"
    assert model["quantization_level"] == "Q4_K_M"
    assert model["size_human"] == "4.4 GB"


def test_size_human_formats_bytes():
    assert models_api._human_size(500) == "500 B"
    assert models_api._human_size(2048) == "2.0 KB"
    assert models_api._human_size(4_683_087_332).endswith("GB")


def test_empty_model_list(monkeypatch):
    monkeypatch.setattr(models_api.ollama, "Client", lambda: FakeOllamaClient([]))
    data = client().get("/api/models").json()
    assert data["local"] == []
    assert data["cloud"] == []
    assert data["error"] is None


def test_connection_error_returns_error_field_not_500(monkeypatch):
    class BrokenClient:
        def list(self):
            raise ConnectionError("Failed to connect to Ollama.")

    monkeypatch.setattr(models_api.ollama, "Client", lambda: BrokenClient())

    response = client().get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert data["local"] == []
    assert data["cloud"] == []
    assert "Failed to connect" in data["error"]


def test_cloud_model_without_details_does_not_crash(monkeypatch):
    fake_models = [fake_model("qwen3.5:cloud", size=346)]
    monkeypatch.setattr(models_api.ollama, "Client", lambda: FakeOllamaClient(fake_models))

    data = client().get("/api/models").json()
    cloud_model = data["cloud"][0]
    assert cloud_model["family"] == ""
    assert cloud_model["parameter_size"] == ""


# --------------------------------------------------------------------------
# GET /api/models/catalog -- Ollama's full public cloud catalog
# --------------------------------------------------------------------------

class FakeCatalogResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class TestCloudCatalog:
    def test_success_returns_parsed_models(self, monkeypatch):
        payload = {"models": [
            {"name": "glm-5.2", "size": 0, "modified_at": "2026-06-16T08:00:00-07:00"},
            {"name": "kimi-k2.7-code", "size": 595148192736, "modified_at": "2026-06-12T00:00:00Z"},
        ]}
        monkeypatch.setattr(
            models_api.requests, "get",
            lambda *a, **k: FakeCatalogResponse(200, payload),
        )

        response = client().get("/api/models/catalog")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert [m["name"] for m in data["models"]] == ["glm-5.2", "kimi-k2.7-code"]
        assert data["models"][1]["size_human"].endswith("GB")

    def test_401_returns_auth_required_message(self, monkeypatch):
        monkeypatch.setattr(
            models_api.requests, "get",
            lambda *a, **k: FakeCatalogResponse(401),
        )

        data = client().get("/api/models/catalog").json()
        assert data["models"] == []
        assert "OLLAMA_API_KEY" in data["error"]

    def test_other_status_code_reported_verbatim(self, monkeypatch):
        monkeypatch.setattr(
            models_api.requests, "get",
            lambda *a, **k: FakeCatalogResponse(503),
        )

        data = client().get("/api/models/catalog").json()
        assert data["models"] == []
        assert "503" in data["error"]

    def test_network_failure_returns_error_not_500(self, monkeypatch):
        def raise_connection_error(*a, **k):
            raise models_api.requests.exceptions.RequestException("timed out")

        monkeypatch.setattr(models_api.requests, "get", raise_connection_error)

        response = client().get("/api/models/catalog")
        assert response.status_code == 200
        data = response.json()
        assert data["models"] == []
        assert "timed out" in data["error"]

    def test_api_key_sent_as_bearer_header_when_set(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_API_KEY", "secret-token")
        seen = {}

        def fake_get(url, headers=None, timeout=None):
            seen["headers"] = headers
            return FakeCatalogResponse(200, {"models": []})

        monkeypatch.setattr(models_api.requests, "get", fake_get)

        client().get("/api/models/catalog")
        assert seen["headers"] == {"Authorization": "Bearer secret-token"}

    def test_no_auth_header_when_api_key_unset(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        seen = {}

        def fake_get(url, headers=None, timeout=None):
            seen["headers"] = headers
            return FakeCatalogResponse(200, {"models": []})

        monkeypatch.setattr(models_api.requests, "get", fake_get)

        client().get("/api/models/catalog")
        assert seen["headers"] == {}
