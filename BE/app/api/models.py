"""GET /api/models -- lists Ollama models this machine already knows
about (locally pulled + cloud models already registered/used).

GET /api/models/catalog -- browses Ollama's full PUBLIC cloud model
catalog (ollama.com/api/tags), independent of what's already pulled or
registered locally. Verified live: returns 19 models unauthenticated
today; OLLAMA_API_KEY (plain env var, Ollama's own naming convention --
deliberately NOT BE_-prefixed) is sent as a Bearer token when set, in
case that endpoint ever requires it for your account.

Both back the "Load models" dropdown on the config editor's Model field
(GET /config) -- lets you pick WORKSHOP_MODEL from a real list with
specs instead of typing a model tag blind.

ollama.Client().list() (used by the plain /api/models route) already
returns local + already-registered-cloud models in one call: a cloud
model shows up with an empty/near-empty `details` block (it's a remote
pointer, nothing pulled locally to inspect) and a name ending in
":cloud" by Ollama's own naming convention -- that's the only signal
used to split the two groups.
"""

import os

import ollama
import requests
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/models", tags=["models"])

CLOUD_CATALOG_URL = "https://ollama.com/api/tags"


class ModelInfo(BaseModel):
    name: str
    kind: str  # "local" | "cloud"
    size_bytes: int
    size_human: str
    family: str
    parameter_size: str
    quantization_level: str
    modified_at: str | None


class ModelsResponse(BaseModel):
    local: list[ModelInfo]
    cloud: list[ModelInfo]
    error: str | None = None


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def _to_model_info(model) -> ModelInfo:
    name = model.model or ""
    details = model.details
    return ModelInfo(
        name=name,
        kind="cloud" if name.endswith(":cloud") else "local",
        size_bytes=model.size or 0,
        size_human=_human_size(model.size or 0),
        family=(details.family if details else "") or "",
        parameter_size=(details.parameter_size if details else "") or "",
        quantization_level=(details.quantization_level if details else "") or "",
        modified_at=str(model.modified_at) if model.modified_at else None,
    )


@router.get("", response_model=ModelsResponse)
def list_models() -> ModelsResponse:
    """Query the local Ollama server for every model it knows about.

    Never raises -- if Ollama isn't running or unreachable, returns
    empty lists plus a human-readable `error` field instead of a 500,
    so the UI can show a clear message ("Ollama not running") rather
    than a broken page.
    """
    try:
        response = ollama.Client().list()
    except Exception as exc:
        return ModelsResponse(local=[], cloud=[], error=str(exc))

    local: list[ModelInfo] = []
    cloud: list[ModelInfo] = []
    for model in response.models:
        info = _to_model_info(model)
        (cloud if info.kind == "cloud" else local).append(info)

    return ModelsResponse(local=local, cloud=cloud)


class CatalogModelInfo(BaseModel):
    name: str
    size_bytes: int
    size_human: str
    modified_at: str | None


class CatalogResponse(BaseModel):
    models: list[CatalogModelInfo]
    error: str | None = None


def _to_catalog_info(raw: dict) -> CatalogModelInfo:
    size = raw.get("size") or 0
    return CatalogModelInfo(
        name=raw.get("name") or raw.get("model") or "",
        size_bytes=size,
        size_human=_human_size(size),
        modified_at=raw.get("modified_at"),
    )


@router.get("/catalog", response_model=CatalogResponse)
def list_cloud_catalog() -> CatalogResponse:
    """Browse Ollama's full public cloud model catalog -- every model
    ollama.com currently offers, not just ones already pulled/registered
    on this machine (that's the plain GET /api/models above).

    Never raises. Mirrors the exact status-code handling requested:
    200 -> parsed list; 401 -> "set OLLAMA_API_KEY" message; any other
    status -> the status code, verbatim; network failure -> the
    exception text. All surfaced via `error`, never a 500, so the UI
    can show a clear message instead of a broken page.
    """
    api_key = os.getenv("OLLAMA_API_KEY")
    cloud_headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        response = requests.get(CLOUD_CATALOG_URL, headers=cloud_headers, timeout=10)
    except requests.exceptions.RequestException as exc:
        return CatalogResponse(models=[], error=f"Could not reach Ollama Cloud API: {exc}")

    if response.status_code == 401:
        return CatalogResponse(
            models=[],
            error="Authentication required: set the OLLAMA_API_KEY environment variable.",
        )
    if response.status_code != 200:
        return CatalogResponse(models=[], error=f"Cloud API returned status code {response.status_code}")

    try:
        raw_models = response.json().get("models", [])
    except ValueError as exc:
        return CatalogResponse(models=[], error=f"Could not parse Ollama Cloud API response: {exc}")

    return CatalogResponse(models=[_to_catalog_info(m) for m in raw_models])
