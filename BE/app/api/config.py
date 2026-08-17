"""GET/POST /api/config -- read and update every editable setting.

Backs the interactive config editor at GET /config (see
app/static/config.html). See config_schema.py for the field list, the
current-value readers, and the .env-writing logic -- this module is
just the thin HTTP wrapper around it.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import config_schema

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigField(BaseModel):
    key: str
    section: str
    label: str
    type: str
    description: str
    value: str
    default: str


class ConfigResponse(BaseModel):
    fields: list[ConfigField]


class SaveConfigRequest(BaseModel):
    values: dict[str, str]


class SaveConfigResponse(BaseModel):
    saved: dict[str, list[str]]
    message: str


@router.get("", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Every editable field, with its current effective value."""
    return ConfigResponse(fields=config_schema.get_form_schema())


@router.post("", response_model=SaveConfigResponse)
def save_config(request: SaveConfigRequest) -> SaveConfigResponse:
    """Write submitted values to agent/.env and/or BE/.env.

    Does NOT restart or hot-reload anything -- both the agent and this
    BE process only read their .env file once, at startup. Changes take
    effect the next time each process is restarted.
    """
    saved = config_schema.save_values(request.values)
    total = len(saved["agent"]) + len(saved["be"])
    return SaveConfigResponse(
        saved=saved,
        message=(
            f"Saved {total} setting(s). Restart the agent and/or BE "
            "service for changes to take effect."
        ),
    )
