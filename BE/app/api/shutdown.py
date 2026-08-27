"""POST /api/shutdown -- gracefully stop this BE process, triggered
from the config page's Close button.

The goal is the exact same outcome as pressing Ctrl+C in the terminal
that launched run_be.sh / run_be.bat: EVERYTHING started by that
command goes away -- the uvicorn worker, the `--reload` supervisor
that spawned it (WatchFiles), and the `uv run` wrapper above them.

A bare os.kill(os.getpid(), SIGTERM) is not enough: under --reload the
current process is only the worker *child*. Killing it leaves the
reloader parent alive with no worker (port closed, but the launching
terminal never returns). So:

  - POSIX: signal the whole process group (os.killpg). A terminal
    Ctrl+C does exactly this -- SIGINT/SIGTERM to every process in the
    foreground group -- so the reloader and the uv wrapper get it too.
    The worker (this process) is in that group as well, so uvicorn's
    own SIGTERM handler still runs the graceful lifespan shutdown.

  - Windows / no process groups: fall back to signalling this process
    and its immediate parent (the reloader, or the uv wrapper when
    run without --reload).

Python delivers the signal on the next asyncio event-loop tick, not
synchronously inside this handler, so the 200 response below still
gets flushed to the client before teardown begins -- and the config
page treats a dropped connection here as success regardless.
"""

import os
import signal

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["shutdown"])


def _terminate_process_tree() -> None:
    """Ask the whole uvicorn/uv process tree to stop -- see module docstring."""
    sig = signal.SIGTERM
    try:
        os.killpg(os.getpgrp(), sig)  # POSIX: the entire foreground group
        return
    except (AttributeError, OSError):
        # AttributeError: no killpg/getpgrp (Windows). OSError: group
        # gone / not permitted. Fall back to self + immediate parent.
        pass

    for pid in {os.getpid(), os.getppid()}:
        try:
            os.kill(pid, sig)
        except OSError:
            pass


@router.post("/shutdown")
def shutdown() -> dict:
    """Signals this process (and its --reload supervisor / uv wrapper)
    to shut down gracefully right after this response is sent."""
    _terminate_process_tree()
    return {"status": "shutting_down"}
