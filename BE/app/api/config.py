"""GET/POST /api/config -- read and update every editable setting.

Backs the interactive config editor at GET /config (see
app/static/config.html). See config_schema.py for the field list, the
current-value readers, and the .env-writing logic -- this module is
just the thin HTTP wrapper around it.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import config_schema
from app.core.config import get_settings

import config_reload  # noqa: E402 -- agent/ added to sys.path by config_schema

router = APIRouter(prefix="/api/config", tags=["config"])

# Bound to the process at startup (socket already listening, CORS
# middleware already installed into the ASGI app) -- these three
# genuinely cannot take effect without restarting the BE service, no
# matter what. Everything else (agent settings + all other BE_*
# settings) applies immediately on Save.
_RESTART_REQUIRED_KEYS = {"BE_HOST", "BE_PORT", "BE_CORS_ORIGINS"}


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


class BrowseEntry(BaseModel):
    name: str
    path: str


class BrowseResponse(BaseModel):
    path: str            # absolute, resolved path currently being listed
    parent: str | None   # its parent, or None at a filesystem root
    entries: list[BrowseEntry]  # immediate sub-directories only


@router.get("/browse", response_model=BrowseResponse)
def browse_dirs(path: str = "") -> BrowseResponse:
    """List the sub-directories of `path`, for the config page's "Browse"
    button on directory fields (WORKSPACE_DIR, LOG_DIR).

    Deliberately NOT sandboxed: the whole point is to pick a directory
    anywhere on this machine (WORKSPACE_DIR *is* the agent sandbox root),
    and the same page already lets you type any path straight into
    agent/.env. This endpoint is read-only, returns directory names
    only -- never file contents -- and the BE service is meant to run
    bound to localhost.

    Empty/blank `path` starts at the user's home directory.
    """
    target = Path(path).expanduser() if path.strip() else Path.home()
    try:
        target = target.resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Bad path: {exc}")

    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {target}")

    try:
        subdirs = sorted(
            (p for p in target.iterdir() if p.is_dir()),
            key=lambda p: p.name.lower(),
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {target}")
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot list {target}: {exc}")

    parent = None if target.parent == target else str(target.parent)
    return BrowseResponse(
        path=str(target),
        parent=parent,
        entries=[BrowseEntry(name=p.name, path=str(p)) for p in subdirs],
    )


@router.post("", response_model=SaveConfigResponse)
def save_config(request: SaveConfigRequest) -> SaveConfigResponse:
    """Write submitted values to agent/.env and/or BE/.env, then apply
    them live in this running process -- see config_reload.py for why
    agent settings need active propagation (most were copied by value
    into their consumer modules at import time) and get_settings's
    lru_cache for why BE settings don't (every BE module already reads
    settings via a fresh get_settings() call).

    BE_HOST/BE_PORT/BE_CORS_ORIGINS are the one exception: the socket
    is already listening and the CORS middleware already installed by
    the time Save runs, so those three still need a real restart.
    """
    saved = config_schema.save_values(request.values)
    total = len(saved["agent"]) + len(saved["be"])

    if saved["agent"]:
        config_reload.reload_all()
    if saved["be"]:
        get_settings.cache_clear()

    restart_needed = sorted(_RESTART_REQUIRED_KEYS & set(saved["be"]))
    message = f"Saved and applied {total} setting(s) immediately."
    if restart_needed:
        message += (
            f" Restart the BE service for: {', '.join(restart_needed)} "
            "(bound to the process at startup)."
        )

    return SaveConfigResponse(saved=saved, message=message)
