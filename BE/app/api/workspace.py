"""GET /api/workspace/file(-raw) -- read-only preview of a file the
agent wrote inside its own sandbox (workspace/), for the chat page's
Preview tab (see app/static/chat.html). Data-analysis output is
typically an HTML report/plot the agent wrote with write_file.

Deliberately reuses fs_tools.read_file()/resolve_path() -- the SAME
sandbox enforcement (control-char checks, ".." rejection, symlink
rejection, BASE_DIR containment) every agent tool already goes through,
rather than re-implementing path safety a second time here.
"""

import platform
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

BE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = BE_DIR.parent / "agent"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import fs_tools  # noqa: E402
from fs_tools import read_file  # noqa: E402

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


class WorkspaceFileResponse(BaseModel):
    path: str
    content: str


class WorkspaceOpenResponse(BaseModel):
    path: str      # the workspace directory that was opened (fs_tools.BASE_DIR)
    opened: bool


def _running_under_wsl() -> bool:
    """True when this Linux process is actually WSL -- so "open the
    folder" should reach Windows Explorer, not a Linux file manager
    that isn't there."""
    if sys.platform != "linux":
        return False
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
    except OSError:
        return "microsoft" in platform.uname().release.lower()


def _open_in_file_manager(target: Path) -> None:
    """Launch the OS file manager on `target`. Fire-and-forget (Popen,
    no wait): explorer.exe in particular returns a non-zero exit code
    even on success, and we only care that the launch itself worked."""
    if sys.platform.startswith("win"):
        subprocess.Popen(["explorer", str(target)])
    elif _running_under_wsl():
        # Translate the Linux path to its \\wsl.localhost\... (or drive)
        # form so Windows Explorer can actually resolve it.
        win_path = subprocess.check_output(
            ["wslpath", "-w", str(target)], text=True
        ).strip()
        subprocess.Popen(["explorer.exe", win_path])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])


@router.get("/file", response_model=WorkspaceFileResponse)
def get_workspace_file(path: str) -> WorkspaceFileResponse:
    """Read one file's content, sandboxed to workspace/ exactly like
    every agent tool. 400 on an out-of-sandbox path (ValueError from
    resolve_path()); read_file()'s own "No such file"/"Not a file"
    messages come back as normal 200 content, same as the agent itself
    seeing them as a tool result -- not an HTTP error, just a message
    to show in the preview pane."""
    try:
        content = read_file(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return WorkspaceFileResponse(path=path, content=content)


@router.post("/open", response_model=WorkspaceOpenResponse)
def open_workspace() -> WorkspaceOpenResponse:
    """Open the agent's workspace directory (fs_tools.BASE_DIR --
    agent_config.WORKSPACE_DIR) in the OS file manager. Under WSL this
    opens Windows Explorer via explorer.exe on the translated path.

    No path input: the target is the one fixed sandbox root, and the
    BE service is meant to run bound to localhost."""
    target = fs_tools.BASE_DIR
    try:
        _open_in_file_manager(target)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(
            status_code=500, detail=f"Could not open {target}: {exc}"
        )
    return WorkspaceOpenResponse(path=str(target), opened=True)


@router.get("/file-raw")
def get_workspace_file_raw(path: str) -> Response:
    """Same file, same sandbox, but served as a real HTML document
    (Content-Type: text/html) for the Preview iframe to navigate to
    directly (<iframe src="...">) instead of JSON-fetching the content
    and injecting it via srcdoc.

    Why this exists on top of GET /file: srcdoc's base URL is
    about:srcdoc, which broke relative-asset resolution some Plotly
    exports depend on (a report referencing its own bundled JS/CSS by
    relative path). Navigating the iframe to a real URL like this one
    fixes that. Its sandbox stays opaque/null origin either way --
    chat.html's <iframe> is sandbox="allow-scripts" WITHOUT
    allow-same-origin, deliberately: this content is model-written
    (write_file/run_command output), and allow-same-origin would grant
    it BE's own real origin -- ambient-credentialed access to
    window.parent and every other /api/* endpoint, not just the
    sandboxed workspace/ read this route itself already enforces via
    resolve_path().
    """
    try:
        content = read_file(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(content=content, media_type="text/html")
