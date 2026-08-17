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
  - load_token_usage() / save_token_usage() -- also NOT tools, also
    host-CLI-only. Track a running cumulative token count (prompt +
    completion tokens, from OllamaAgent.total_tokens) across every
    session ever run, so the CLI can show "tokens used this session"
    and "tokens used all-time" on every start and exit.

All of the above write to one JSON file (MEMORY_FILE in
agent_config.py): a top-level object with an "entries" list (flat
{id, type, text, tags, timestamp} records for remember_fact/
recall_memory/save_session_summary) and a sibling "token_usage_total"
integer. Kept deliberately simple -- no embeddings, no vector search --
recall_memory() is a case-insensitive substring/tag filter, which is
enough at the scale one person's agent memory reaches before it would
need anything heavier.

Memory persists across different BASE_DIR sandboxes on purpose (it is
NOT resolved through fs_tools.resolve_path): the point is for the agent
to remember things about the user/project across runs, not to be
another sandboxed file the model can point anywhere.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from agent_config import (
    MEMORY_ENABLED, MEMORY_FILE, MEMORY_MAX_ENTRIES,
    MEMORY_MAX_TEXT_CHARS, MEMORY_MAX_RECALL_RESULTS, MEMORY_SUMMARY_MAX_MESSAGES,
)

logger = logging.getLogger("agent.memory")

MEMORY_PATH = Path(MEMORY_FILE)


def _load_data() -> dict:
    """Read the full JSON object from disk. Missing/corrupt file -> {}, never raises.

    The full object, not just "entries" -- so sibling top-level keys
    (currently just "token_usage_total") round-trip through _save_data()
    unmodified whenever _save() only touches "entries", and vice versa.

    ROB-02: a corrupt file (e.g. from an interrupted non-atomic write,
    before that was fixed) is preserved as a `.corrupt.bak` alongside
    it before we fall back to {} -- so a human can still recover it by
    hand, instead of the next save silently overwriting the only copy
    of whatever was salvageable.
    """
    if not MEMORY_PATH.exists():
        return {}
    raw = ""
    try:
        raw = MEMORY_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("memory_load_failed path=%s error=%s", MEMORY_PATH, exc)
        if raw:  # nothing to back up if read_text() itself failed
            try:
                backup_path = MEMORY_PATH.with_suffix(MEMORY_PATH.suffix + ".corrupt.bak")
                backup_path.write_text(raw, encoding="utf-8")
                logger.warning("memory_corrupt_backup_written path=%s", backup_path)
            except OSError:
                pass  # backup is best-effort; losing it must not block the fallback
        return {}
    return data if isinstance(data, dict) else {}


def _save_data(data: dict) -> None:
    """Write the full JSON object to disk. Never raises -- a full disk or
    permissions error degrades to a log warning, same as chat_logger.

    ROB-02: writes to a temporary file in the same directory, then
    atomically swaps it into place with os.replace(). A direct
    write_text() can be interrupted mid-write (process killed, power
    loss); os.replace() is atomic on POSIX and Windows, so MEMORY_PATH
    is always either the old complete file or the new complete file,
    never a half-written one -- closing the "corrupted file wipes all
    memories on next load" hazard.
    """
    try:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = MEMORY_PATH.with_suffix(MEMORY_PATH.suffix + f".tmp{os.getpid()}")
        tmp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_path, MEMORY_PATH)
    except OSError as exc:
        logger.warning("memory_save_failed path=%s error=%s", MEMORY_PATH, exc)


def _load() -> list[dict]:
    """Read just the entries list from disk. Missing/corrupt -> []."""
    entries = _load_data().get("entries")
    return entries if isinstance(entries, list) else []


def _save(entries: list[dict]) -> None:
    """Write the entries list back to disk, preserving any other
    top-level keys already on file (e.g. token_usage_total)."""
    data = _load_data()
    data["entries"] = entries
    _save_data(data)


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

    ROB-04: only the last MEMORY_SUMMARY_MAX_MESSAGES messages are sent
    to the summarizer, not the full conversation -- `messages` grows
    unboundedly across a long CLI session, and this is the one call
    that happens automatically at shutdown with no human watching for
    an overflow. A summary of "roughly what happened recently" is good
    enough for cross-session memory; it doesn't need the entire
    transcript.

    Failures here are swallowed to a log warning -- losing a summary
    must never crash the shutdown path.
    """
    if not MEMORY_ENABLED:
        return

    real_turns = [m for m in messages if m.get("role") in ("user", "assistant")]
    if len(real_turns) < 2:
        return

    windowed_messages = messages[-MEMORY_SUMMARY_MAX_MESSAGES:]
    summarizer_messages = windowed_messages + [{
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


def load_token_usage() -> int:
    """Return the cumulative token total saved across all previous
    sessions, or 0 if none has ever been saved (or memory is disabled).

    Called by the host CLI once at startup, so a new session can show
    "here's how much you've used so far" before a single tool call runs.
    """
    if not MEMORY_ENABLED:
        return 0
    total = _load_data().get("token_usage_total")
    return total if isinstance(total, int) else 0


def save_token_usage(session_tokens: int) -> int:
    """Add this session's token count to the running cumulative total,
    persist it, and return the new grand total.

    Called by the host CLI once per session, right before exit --
    unlike save_session_summary(), this makes no model call, so it's
    safe to call on every exit path including a crash (nothing extra
    can fail here that isn't already covered by _save_data()'s own
    fail-to-a-log-warning behavior). session_tokens <= 0 (nothing used,
    or memory disabled) is a no-op that just returns the existing total.

    Args:
        session_tokens: OllamaAgent.total_tokens at the end of this run.
    """
    if not MEMORY_ENABLED or session_tokens <= 0:
        return load_token_usage()

    data = _load_data()
    current_total = data.get("token_usage_total")
    current_total = current_total if isinstance(current_total, int) else 0
    new_total = current_total + session_tokens
    data["token_usage_total"] = new_total
    _save_data(data)
    logger.info("token_usage_saved session_tokens=%s new_total=%s", session_tokens, new_total)
    return new_total
