"""GET /api/memory -- read-only view of the agent's persistent memory
file (memory.json), for display on the config page (see
app/static/config.html). Never writes to it; editing memory is the
model's job (remember_fact()/recall_memory() in agent/memory.py), not
this HTTP surface's.
"""

import json
import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

BE_DIR = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = BE_DIR.parent / "agent"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from agent_config import MEMORY_FILE  # noqa: E402

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryEntry(BaseModel):
    id: str
    type: str
    text: str
    tags: list[str]
    timestamp: str


class MemoryResponse(BaseModel):
    path: str
    exists: bool
    entries: list[MemoryEntry]
    token_usage_total: int


@router.get("", response_model=MemoryResponse)
def get_memory() -> MemoryResponse:
    """Everything in memory.json, newest entry first. Missing or
    corrupt file reads back as empty rather than erroring -- same
    "never raises" contract agent/memory.py's own loader keeps."""
    path = Path(MEMORY_FILE)
    if not path.exists():
        return MemoryResponse(path=str(path), exists=False, entries=[], token_usage_total=0)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return MemoryResponse(path=str(path), exists=True, entries=[], token_usage_total=0)

    entries = raw.get("entries", []) if isinstance(raw, dict) else []
    token_usage_total = raw.get("token_usage_total", 0) if isinstance(raw, dict) else 0

    return MemoryResponse(
        path=str(path),
        exists=True,
        entries=list(reversed(entries)),
        token_usage_total=token_usage_total,
    )
