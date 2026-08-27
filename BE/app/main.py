"""FastAPI application entry point.

Health check, an interactive config editor (GET /config), and a plain
conversational chat page (GET /chat) over the agent's own OllamaAgent
(see app/core/agent_bridge.py) -- no tool-calling wired in yet, since
that needs its own design for how a human approves a tool call over
HTTP instead of a blocking terminal confirm().

Run directly for local dev:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Or via the run_be.sh / run_be.bat scripts at the project root, which
read the same BE_HOST/BE_PORT settings this app itself reads.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import chat as chat_api
from app.api import config as config_api
from app.api import health
from app.api import memory as memory_api
from app.api import models as models_api
from app.api import shutdown as shutdown_api
from app.api import workspace as workspace_api
from app.core.config import get_settings

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield
    # On shutdown, close out whatever chat conversation was open, same
    # as CLI_agent.py always logging session_end before exiting -- so a
    # server restart never leaves a JSONL file implicitly "still open".
    chat_api._close_chat_logger(reason="server_shutdown")


def create_app() -> FastAPI:
    """App factory -- lets tests build a fresh app instance per test
    run instead of importing one shared module-level singleton."""
    settings = get_settings()

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=_lifespan)

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
    app.include_router(models_api.router)
    app.include_router(chat_api.router)
    app.include_router(memory_api.router)
    app.include_router(workspace_api.router)
    app.include_router(shutdown_api.router)

    @app.get("/config", include_in_schema=False)
    def config_page() -> FileResponse:
        """Interactive settings editor -- see app/static/config.html
        and app/api/config.py (GET/POST /api/config, which this page
        calls client-side)."""
        return FileResponse(STATIC_DIR / "config.html")

    @app.get("/chat", include_in_schema=False)
    def chat_page() -> FileResponse:
        """Conversational chat page -- see app/static/chat.html and
        app/api/chat.py (the streaming GET/POST /api/chat/* endpoints
        it calls client-side)."""
        return FileResponse(STATIC_DIR / "chat.html")

    return app


app = create_app()
