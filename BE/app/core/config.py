"""Central configuration for the BE service — every setting in one
place, each overridable by an environment variable of the same name.
Mirrors the pattern agent/agent_config.py already established: plain
settings object, env-var overrides, no hardcoded values scattered
across the app.

All env vars are BE_-prefixed so they never collide with the agent's
own env vars (WORKSPACE_DIR, MEMORY_FILE, etc.) if both processes ever
share an environment.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# This file lives in BE/app/core/ -- BE_DIR is BE/ itself, resolved
# from this file's own location so env_file below finds BE/.env
# regardless of the process's working directory at launch (previously
# a bare relative ".env" only worked when cwd happened to be BE/,
# which run_be.sh/.bat arrange but nothing enforces).
BE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """One object, one source of truth for BE configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BE_", env_file=str(BE_DIR / ".env"), extra="ignore",
    )

    # Identity / metadata
    app_name: str = "agent-backend"
    app_version: str = "0.1.0"

    # Server (used by run_be.sh/.bat -- Uvicorn reads these directly)
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS -- comma-separated origins the future UI will be served from.
    # Empty by default (no cross-origin access) until a real frontend
    # origin is known; set BE_CORS_ORIGINS=http://localhost:3000 etc.
    cors_origins: str = ""

    log_level: str = "info"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached singleton -- Settings() reads env vars once per process,
    not on every request. FastAPI's Depends(get_settings) pattern reuses
    this same instance everywhere."""
    return Settings()
