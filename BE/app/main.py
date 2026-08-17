"""FastAPI application entry point.

Bare scaffold -- health check only. No agent wiring yet (that comes in
a later session, once the chat/UI contract is designed): this file's
job right now is to prove the FastAPI + Uvicorn + Nginx stack actually
runs end to end.

Run directly for local dev:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Or via the run_be.sh / run_be.bat scripts at the project root, which
read the same BE_HOST/BE_PORT settings this app itself reads.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import config as config_api
from app.api import health
from app.core.config import get_settings

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    """App factory -- lets tests build a fresh app instance per test
    run instead of importing one shared module-level singleton."""
    settings = get_settings()

    app = FastAPI(title=settings.app_name, version=settings.app_version)

    # Empty allow_origins (the default) means no cross-origin access at
    # all -- deliberately locked down until a real UI origin is known.
    # Set BE_CORS_ORIGINS once the frontend exists.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(config_api.router)

    @app.get("/config", include_in_schema=False)
    def config_page() -> FileResponse:
        """Interactive settings editor -- see app/static/config.html
        and app/api/config.py (GET/POST /api/config, which this page
        calls client-side)."""
        return FileResponse(STATIC_DIR / "config.html")

    return app


app = create_app()
