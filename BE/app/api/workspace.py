"""GET /api/workspace/file -- read-only preview of a file the agent
wrote inside its own sandbox (workspace/), for the chat page's Preview
tab (see app/static/chat.html). Data-analysis output is typically an
HTML report/plot the agent wrote with write_file -- this lets the chat
page load that file's content into a sandboxed <iframe srcdoc="...">
without a raw file:// link or a second unsandboxed static-file route.

Deliberately reuses fs_tools.read_file()/resolve_path() -- the SAME
sandbox enforcement (control-char checks, ".." rejection, symlink
rejection, BASE_DIR containment) every agent tool already goes through,
rather than re-implementing path safety a second time here.
"""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
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
