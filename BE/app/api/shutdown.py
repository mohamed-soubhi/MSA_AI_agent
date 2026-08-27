"""POST /api/shutdown -- gracefully stop this BE process, triggered
from the config page's Close button.

Sends SIGTERM to this process's own PID -- the exact same signal
Ctrl+C/a normal `kill` sends, and the exact same one uvicorn's own
signal handler already reacts to (stop accepting new connections, run
the lifespan shutdown hook -- see main.py's _lifespan, which closes
out any open chat JSONL log with session_end(reason="server_shutdown")
-- then exit). Deliberately not a separate/parallel shutdown path;
this just requests the normal one from an HTTP call instead of a
terminal signal.

The signal is delivered synchronously here, but Python's signal
handling runs on the next asyncio event-loop tick, not synchronously
inside this handler -- so the 200 response below still reaches the
client before the process actually starts tearing down.
"""

import os
import signal

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["shutdown"])


@router.post("/shutdown")
def shutdown() -> dict:
    """Signals this process to shut down gracefully right after this
    response is sent."""
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "shutting_down"}
