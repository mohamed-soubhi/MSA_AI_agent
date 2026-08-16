"""Structured JSONL logging for agent chat sessions.

Every event (session start, user message, model response, each tool
call and its result, errors, session end) is written as one JSON object
per line to a log file, so you can `tail -f` it live or load it with
`pandas.read_json(path, lines=True)` for analysis.

All behavior is controlled by log_config.py -- this module only
implements it. If log_config.LOG_ENABLED is False, get_logger() returns
a NullChatLogger whose methods all do nothing, so call sites never need
an `if logging_enabled:` check.

Hardening added on top of the original version:
  - _write() can never crash the caller. Logging is a side channel, not
    part of the agent's critical path -- a full disk or permissions
    error here should degrade to a stderr warning, not take down the
    whole agent loop.
  - a lock around file writes, so this stays correct if tool calls are
    ever run concurrently in the future.
  - simple size-based log rotation, so a long "single" mode session (or
    an unexpectedly chatty per_run session) can't grow forever.
"""

import json
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import log_config as cfg


def _truncate(value):
    """Shorten long strings for logging, per cfg.MAX_FIELD_CHARS.

    Leaves non-strings and short strings untouched. Applied recursively
    to dict values and list items so a big tool-call argument dict (e.g.
    write_file's `content`) gets truncated even when nested.
    """
    limit = cfg.MAX_FIELD_CHARS
    if limit is None:
        return value
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"...[truncated {len(value) - limit} more chars]"
    if isinstance(value, dict):
        return {k: _truncate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v) for v in value]
    return value


def _extract_model_timing(response) -> dict:
    """Pull Ollama's own performance counters off a chat response, if present.

    Ollama responses commonly carry fields like total_duration (ns),
    load_duration (ns), prompt_eval_count, prompt_eval_duration (ns),
    eval_count, and eval_duration (ns). These are gold for debugging
    "why is this slow" -- prompt_eval_count growing every turn is a
    direct sign your context is bloating. Missing fields are just
    omitted rather than logged as null/0, since not every backend
    exposes all of them.
    """
    if not cfg.LOG_MODEL_TIMING:
        return {}
    fields = [
        "total_duration", "load_duration", "prompt_eval_count",
        "prompt_eval_duration", "eval_count", "eval_duration",
    ]
    timing = {}
    for field in fields:
        value = getattr(response, field, None)
        if value is not None:
            timing[field] = value
    return timing


class ChatLogger:
    """Writes one JSON line per event to a per-session or shared log file."""

    def __init__(self, agent_name: str, model: str):
        """Open (or create) the log file for this session and record the start.

        Args:
            agent_name: Short label for which agent is running, e.g.
                        "file_agent" or "memory_agent" -- lets you grep
                        logs from multiple agents apart if they share a
                        LOG_DIR.
            model: The Ollama model name in use, logged on every event
                   that touches the model so you can compare runs across
                   models later.
        """
        cfg.LOG_DIR.mkdir(parents=True, exist_ok=True)
        if cfg.LOG_FILE_MODE == "single":
            self.path = cfg.LOG_DIR / cfg.SINGLE_LOG_FILENAME
        else:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.path = cfg.LOG_DIR / f"{agent_name}_{stamp}.jsonl"

        self.agent_name = agent_name
        self.model = model
        self.session_id = uuid.uuid4().hex[:12]
        self.turn_index = 0
        self._model_call_start = None
        self._lock = threading.Lock()  # protects file writes + rotation

        self._write("session_start", working_dir=str(Path.cwd()))

    # -- internal ---------------------------------------------------------

    def _rotate_if_needed(self) -> None:
        """Roll the current log file over to a numbered backup if it has
        grown past cfg.MAX_LOG_FILE_BYTES. Called with self._lock held.
        No-op if rotation is disabled (MAX_LOG_FILE_BYTES is None) or the
        file doesn't exist yet."""
        limit = cfg.MAX_LOG_FILE_BYTES
        if limit is None or not self.path.exists():
            return
        if self.path.stat().st_size < limit:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated = self.path.with_name(f"{self.path.stem}.{stamp}{self.path.suffix}")
        try:
            self.path.rename(rotated)
        except OSError as exc:
            # Rotation failing (e.g. permissions) should not stop logging
            # from continuing to the same file -- just warn and move on.
            print(f"  [log] warning: could not rotate log file: {exc}", file=sys.stderr)

    def _write(self, event: str, **fields) -> None:
        """Append one JSON line describing `event`.

        Never raises. Logging is a side channel to the agent's real job;
        a disk-full or permissions error here degrades to a stderr
        warning instead of crashing the caller (the agent loop, a tool,
        etc). If you need to know logging is broken, watch stderr or
        LOG_DIR's free space -- don't rely on this raising.
        """
        record = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "session_id": self.session_id,
            "agent": self.agent_name,
            "model": self.model,
            "turn": self.turn_index,
            "event": event,
            **_truncate(fields),
        }
        try:
            line = json.dumps(record, default=str, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            # A field that genuinely can't be JSON-serialized (rare, but
            # possible with exotic tool return types) -- log a stub
            # instead of losing the event or crashing.
            line = json.dumps(
                {"ts": record["ts"], "event": event, "log_error": f"unserializable fields: {exc}"}
            )

        try:
            with self._lock:
                self._rotate_if_needed()
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except OSError as exc:
            # Disk full, permissions revoked mid-run, log dir deleted
            # out from under us, etc. Warn once to stderr and continue --
            # the agent's actual work must not depend on logging succeeding.
            print(f"  [log] warning: failed to write log event '{event}': {exc}", file=sys.stderr)

        if cfg.ECHO_TO_TERMINAL:
            print(f"  [log] {event}: { {k: v for k, v in fields.items()} }")

    # -- public API ---------------------------------------------------------

    def user_message(self, text: str) -> None:
        """Log an incoming user message and advance the turn counter."""
        self.turn_index += 1
        self._write("user_message", content=text)

    def model_call_start(self, message_count: int, tools: list) -> None:
        """Log that a model call is about to be made; starts a latency timer.

        Args:
            message_count: Length of the messages list sent, so you can
                            see prompt size growth over the conversation.
            tools: The list of tool functions offered to the model this
                   call, logged by name only.
        """
        self._model_call_start = time.perf_counter()
        self._write(
            "model_call_start",
            message_count=message_count,
            tools=[t.__name__ for t in tools],
        )

    def model_response(self, content: str | None, tool_calls: list, response=None) -> None:
        """Log what the model returned: any text plus any requested tool calls.

        Args:
            content: The model's plain-text content for this turn, if any.
            tool_calls: List of {"name": ..., "arguments": ...} dicts
                        describing every tool call the model requested.
            response: The raw Ollama response object, used only to pull
                      timing counters (see _extract_model_timing) -- not
                      logged in full to avoid duplicating tool_calls/content.
        """
        elapsed_ms = None
        if self._model_call_start is not None:
            elapsed_ms = round((time.perf_counter() - self._model_call_start) * 1000, 1)
            self._model_call_start = None
        timing = _extract_model_timing(response) if response is not None else {}
        self._write(
            "model_response",
            content=content,
            tool_call_count=len(tool_calls),
            tool_calls=tool_calls,
            elapsed_ms=elapsed_ms,
            **timing,
        )

    def tool_call(self, name: str, arguments: dict) -> float:
        """Log that a tool is about to run. Returns a start-time token for tool_result()."""
        self._write("tool_call", tool=name, arguments=arguments)
        return time.perf_counter()

    def tool_result(self, name: str, result, start_time: float, error: bool = False) -> None:
        """Log a tool's outcome and how long it took to run.

        Args:
            name: Tool function name, matching the prior tool_call() log.
            result: The string result/observation returned to the model
                    (or the error message, if error=True).
            start_time: The value returned by the matching tool_call() call.
            error: True if the tool raised and `result` is an error string.
        """
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        self._write(
            "tool_result",
            tool=name,
            result=str(result),
            elapsed_ms=elapsed_ms,
            error=error,
        )

    def loop_limit_hit(self, max_iterations: int) -> None:
        """Log that the ReAct loop hit MAX_ITERATIONS without a final answer."""
        self._write("loop_limit_hit", max_iterations=max_iterations)

    def error(self, message: str, **context) -> None:
        """Log a non-tool error, e.g. the model call itself failing."""
        self._write("error", message=message, **context)

    def session_end(self, reason: str = "user_exit") -> None:
        """Log the end of the session (call this before the process exits)."""
        self._write("session_end", reason=reason)


class NullChatLogger:
    """No-op logger used when log_config.LOG_ENABLED is False.

    Mirrors ChatLogger's public method signatures so call sites never
    need to branch on whether logging is on -- they just call the logger.
    """

    def user_message(self, *a, **k): pass
    def model_call_start(self, *a, **k): pass
    def model_response(self, *a, **k): pass
    def tool_call(self, *a, **k): return 0.0
    def tool_result(self, *a, **k): pass
    def loop_limit_hit(self, *a, **k): pass
    def error(self, *a, **k): pass
    def session_end(self, *a, **k): pass


def get_logger(agent_name: str, model: str):
    """Return a ChatLogger, or a NullChatLogger if logging is disabled in config.

    This is the only entry point call sites should use -- it reads
    log_config.LOG_ENABLED so agents don't need their own if-checks.

    If ChatLogger's own setup fails (e.g. LOG_DIR can't be created --
    read-only filesystem, permissions), fall back to a NullChatLogger
    rather than crashing agent startup over a logging problem.
    """
    if not cfg.LOG_ENABLED:
        return NullChatLogger()
    try:
        return ChatLogger(agent_name, model)
    except OSError as exc:
        print(f"  [log] warning: could not initialize logging ({exc}); continuing without it", file=sys.stderr)
        return NullChatLogger()
