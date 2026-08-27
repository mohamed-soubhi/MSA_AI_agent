"""GET /api/workspace/file(-raw) -- read-only preview of a file the
agent wrote inside its own sandbox (workspace/), for the chat page's
Preview tab (see app/static/chat.html). Data-analysis output is
typically an HTML report/plot the agent wrote with write_file.

Deliberately reuses fs_tools.read_file()/resolve_path() -- the SAME
sandbox enforcement (control-char checks, ".." rejection, symlink
rejection, BASE_DIR containment) every agent tool already goes through,
rather than re-implementing path safety a second time here.
"""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

BE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = BE_DIR.parent / "agent"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from fs_tools import read_file  # noqa: E402

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


class WorkspaceFileResponse(BaseModel):
    path: str
    content: str


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
