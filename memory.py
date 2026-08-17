"""Persistent memory: what the agent learns survives past one session.

Two things live here, and they are populated differently:
  - remember_fact() / recall_memory() -- MODEL-invoked tools, same pattern
    as human_tools.py. The model decides something is worth keeping (a
    user preference, a decision made, a fact about the project) and
    calls remember_fact(); later, in this or a future session, it calls
    recall_memory() to look it back up.
  - save_session_summary() -- NOT a tool. Called once by the host CLI
    (09_full_agent.py) right before a session ends, so every
    conversation leaves behind a short summary even if the model never
    called remember_fact() during the run.

Both write to one JSON file (MEMORY_FILE in agent_config.py), a flat
list of {id, type, text, tags, timestamp} entries. Kept deliberately
simple -- no embeddings, no vector search -- recall_memory() is a
case-insensitive substring/tag filter, which is enough at the scale one
person's agent memory reaches before it would need anything heavier.

Memory persists across different BASE_DIR sandboxes on purpose (it is
NOT resolved through fs_tools.resolve_path): the point is for the agent
to remember things about the user/project across runs, not to be
another sandboxed file the model can point anywhere.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from agent_config import (
    MEMORY_ENABLED, MEMORY_FILE, MEMORY_MAX_ENTRIES,
    MEMORY_MAX_TEXT_CHARS, MEMORY_MAX_RECALL_RESULTS,
)

logger = logging.getLogger("agent.memory")

MEMORY_PATH = Path(MEMORY_FILE)


def _load() -> list[dict]:
    """Read all entries from disk. Missing/corrupt file -> empty list, never raises."""
    if not MEMORY_PATH.exists():
        return []
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("memory_load_failed path=%s error=%s", MEMORY_PATH, exc)
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, list) else []


def _save(entries: list[dict]) -> None:
    """Write all entries back to disk. Never raises -- a full disk or
    permissions error degrades to a log warning, same as chat_logger."""
    try:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(
            json.dumps({"entries": entries}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("memory_save_failed path=%s error=%s", MEMORY_PATH, exc)


def _append(entry_type: str, text: str, tags: list[str] | None = None) -> dict:
    """Build one entry, append it, trim to MEMORY_MAX_ENTRIES, and persist."""
    entry = {
        "id": uuid.uuid4().hex[:8],
        "type": entry_type,
        "text": text.strip()[:MEMORY_MAX_TEXT_CHARS],
        "tags": sorted({t.strip().lower() for t in (tags or []) if t and t.strip()}),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    entries = _load()
    entries.append(entry)
    if len(entries) > MEMORY_MAX_ENTRIES:
        entries = entries[-MEMORY_MAX_ENTRIES:]
    _save(entries)
    logger.info("memory_saved id=%s type=%s", entry["id"], entry_type)
    return entry


def remember_fact(text: str, tags: list[str] | None = None) -> str:
    """Save one fact worth remembering in future sessions.

    Call this when you learn something durable -- a user preference, a
    decision that was made, a fact about the project -- that a future
    conversation (which starts with no memory of this one) would
    benefit from knowing. Do not call this for throwaway details that
    only matter for the rest of THIS conversation.

    Args:
        text: The fact itself, written so it stands alone and still
              makes sense later, e.g. "User prefers pytest over
              unittest for this project."
        tags: Optional short keywords for later recall_memory() lookups,
              e.g. ["preferences", "testing"].
    """
    if not MEMORY_ENABLED:
        return "Memory is disabled; fact was not saved."
    if not isinstance(text, str) or not text.strip():
        return "Error: text must be a non-empty string."

    entry = _append("fact", text, tags)
    return f"Remembered ({entry['id']}): {entry['text']}"


def recall_memory(query: str = "", tags: list[str] | None = None) -> str:
    """Search saved memory (facts and past session summaries) and return matches.

    Call this at the start of a task, or whenever something from a past
    session could help -- e.g. "what did we decide about X before?".
    Matching is a case-insensitive substring search over each entry's
    text, plus an optional tag filter. Leave query empty and tags empty
    to list the most recent entries instead of searching.

    Args:
        query: Text to search for inside remembered facts/summaries.
               Empty string matches every entry's text.
        tags: Optional list of tags to filter by -- an entry matches if
              it has ANY of the given tags. Empty list applies no filter.
    """
    if not MEMORY_ENABLED:
        return "Memory is disabled; nothing to recall."

    entries = _load()
    if not entries:
        return "No memories saved yet."

    query_lower = query.strip().lower()
    tag_filter = {t.strip().lower() for t in (tags or []) if t and t.strip()}

    matches = []
    for entry in entries:
        if query_lower and query_lower not in entry.get("text", "").lower():
            continue
        if tag_filter and not tag_filter.intersection(entry.get("tags", [])):
            continue
        matches.append(entry)

    matches = matches[-MEMORY_MAX_RECALL_RESULTS:]
    if not matches:
        return f"No memories matched query={query!r} tags={sorted(tag_filter)}."

    lines = [
        f"[{e['timestamp']}] ({e['type']}) {e['text']}"
        + (f" tags={e['tags']}" if e.get("tags") else "")
        for e in matches
    ]
    return "\n".join(lines)


def save_session_summary(agent, messages: list[dict]) -> None:
    """Condense a finished conversation into one memory entry, then save it.

    Called by the host CLI once per session, right before exit -- never
    by the model itself, since a mid-conversation call would summarize
    an unfinished conversation. Uses one extra agent.chat() call with no
    tools offered, so the summarizer can't itself start calling
    write_file/run_command. Skips conversations too short to be worth
    summarizing (e.g. the user typed "exit" immediately).

    Failures here are swallowed to a log warning -- losing a summary
    must never crash the shutdown path.
    """
    if not MEMORY_ENABLED:
        return

    real_turns = [m for m in messages if m.get("role") in ("user", "assistant")]
    if len(real_turns) < 2:
        return

    summarizer_messages = messages + [{
        "role": "user",
        "content": (
            "Summarize this conversation in 2-4 sentences, for your own "
            "future memory: what was the goal, what was decided or "
            "built, and any preference the user expressed. Plain text, "
            "no lists, no preamble."
        ),
    }]
    try:
        response = agent.chat(summarizer_messages, tools=None)
        summary = (response.message.content or "").strip()
    except Exception as exc:
        logger.warning("memory_summary_failed error=%s", exc)
        return

    if summary:
        _append("summary", summary)
