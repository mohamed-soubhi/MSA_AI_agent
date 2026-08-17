"""
shared.py — hardened plumbing for the workshop agents.

Combines the best of both prior versions:
  - friendly, readable RuntimeError messages (from the simplified version)
  - timeout + retry + structured logging on the network call (from the
    hardened version)
  - chat_stream() now gets the SAME friendly-error treatment as chat(),
    which the hardened version had missed
  - run_agent(), the tool-calling loop, included and sharing the same
    logger/constants as OllamaAgent

One default model, defined once, so there's no drift between files.
"""

import concurrent.futures
import hashlib
import inspect
import json
import logging
import time
import traceback
import uuid

from ollama import Client

from chat_logger import NullChatLogger
from agent_config import (
    DEFAULT_MODEL, CHAT_TIMEOUT_SECONDS, CHAT_MAX_RETRIES, CHAT_RETRY_BACKOFF_SECONDS,
    MAX_ITERATIONS, MAX_WALL_SECONDS, TOOL_TIMEOUT_SECONDS, MAX_REPEAT_CALLS,
    MAX_OBSERVATION_CHARS,
)

logger = logging.getLogger("agent.core")


# All "how long / how many / which model" settings now live in
# agent_config.py, not here — see that file to tune or override any of
# them via environment variable.


def section(title):
    """Return a terminal heading with an underline."""

    line = "=" * len(title)

    return f"\n{title}\n{line}"


def _extract_token_count(response) -> int:
    """Sum prompt + completion tokens off a chat response, 0 if absent.

    Ollama exposes `prompt_eval_count` (input tokens) and `eval_count`
    (output tokens) on the response when the backend reports them —
    same fields chat_logger._extract_model_timing already reads for
    logging. Missing/None on either -> counted as 0, not a crash;
    not every backend exposes both.
    """
    prompt = getattr(response, "prompt_eval_count", 0) or 0
    completion = getattr(response, "eval_count", 0) or 0
    return prompt + completion


class OllamaAgent:
    """A small, hardened wrapper around the Ollama client.

    On top of the original workshop wrapper, this adds:
      - a timeout on chat(), so a stalled network call can't hang the
        whole agent
      - a small retry with backoff, since a cloud model over the network
        is the single most failure-prone call in this system
      - a friendly RuntimeError with a clear message on final failure,
        instead of a raw exception traceback — for BOTH chat() and
        chat_stream(), not just chat()
      - logging of every attempt/failure, for audit purposes
    """

    def __init__(self, model=DEFAULT_MODEL):
        """Create an Ollama client bound to one model.

        Args:
            model: Model name/tag to use for every chat() call on this
                   instance. Defaults to the WORKSHOP_MODEL env var, or
                   the built-in DEFAULT_MODEL if that isn't set.
        """
        self.model = model
        self.client = Client()
        # Running total across every successful chat() call made through
        # this instance -- i.e. this whole session, since CLI_agent.py
        # creates exactly one OllamaAgent per run. Not reset between
        # chat() calls; the host CLI reads it once at shutdown.
        self.total_tokens = 0
        # Set by chat_stream() after each call, from the stream's final
        # chunk (done=True) -- the same prompt_eval_count/eval_count/
        # duration fields chat()'s response carries, but streaming only
        # yields plain text chunks (chunk.message.content), so a caller
        # that wants those stats (e.g. BE/app/api/chat.py's JSONL
        # logging) reads them from here right after fully consuming the
        # generator. None until the first chat_stream() call completes.
        self.last_stream_stats: dict | None = None

    def chat(self, messages, tools=None):
        """Send the message history to the model and return one response.

        The model does not remember previous requests by itself.
        To continue a conversation, we send the message history again
        with every request.

        Times out after CHAT_TIMEOUT_SECONDS, retries transient failures
        a few times, and raises a friendly RuntimeError (not a raw
        connection traceback) if every attempt fails.
        """
        last_error = None
        for attempt in range(1, CHAT_MAX_RETRIES + 2):  # +1 initial try
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        self.client.chat,
                        model=self.model,
                        messages=messages,
                        tools=tools,
                    )
                    response = future.result(timeout=CHAT_TIMEOUT_SECONDS)
                    self.total_tokens += _extract_token_count(response)
                    return response

            except concurrent.futures.TimeoutError:
                last_error = TimeoutError(
                    f"chat() exceeded {CHAT_TIMEOUT_SECONDS}s timeout"
                )
                logger.warning("chat_timeout attempt=%s/%s model=%s",
                                attempt, CHAT_MAX_RETRIES + 1, self.model)

            except Exception as exc:
                last_error = exc
                logger.warning("chat_error attempt=%s/%s model=%s error=%s",
                                attempt, CHAT_MAX_RETRIES + 1, self.model, exc)

            if attempt <= CHAT_MAX_RETRIES:
                time.sleep(CHAT_RETRY_BACKOFF_SECONDS * attempt)

        # All attempts exhausted — surface ONE clear, friendly error
        # instead of whatever the last raw exception happened to be.
        logger.error("chat_failed_all_retries model=%s", self.model)
        raise RuntimeError(
            f"Could not reach Ollama model '{self.model}' after "
            f"{CHAT_MAX_RETRIES + 1} attempts: {last_error}"
        ) from last_error

    def chat_stream(self, messages):
        """Send the message history and yield the response piece by piece.

        Streaming lets us display text as it is generated instead of
        waiting for the complete response.

        The stream's final chunk (done=True) carries the same token/
        timing stats a non-streaming chat() response does. This method
        still only YIELDS plain text (unchanged contract) -- those stats
        are captured as a side effect into self.total_tokens (added to)
        and self.last_stream_stats (overwritten), readable by the caller
        once the generator is fully consumed.

        NOTE: intentionally NOT retried, same reasoning as before — once
        a stream has partially yielded content to the caller, retrying
        would duplicate output already shown/used. It DOES get the same
        friendly-error treatment as chat(), so a failure mid-stream is
        still a clear RuntimeError rather than a raw traceback.
        """
        try:
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                if getattr(chunk, "done", False):
                    self.total_tokens += _extract_token_count(chunk)
                    self.last_stream_stats = {
                        field: getattr(chunk, field, None)
                        for field in (
                            "total_duration", "load_duration", "prompt_eval_count",
                            "prompt_eval_duration", "eval_count", "eval_duration",
                        )
                    }
                yield chunk.message.content

        except Exception as exc:
            logger.error("chat_stream_failed model=%s error=%s", self.model, exc)
            raise RuntimeError(
                f"Could not reach Ollama model '{self.model}': {exc}"
            ) from exc


# --------------------------------------------------------------------------
# Tool-calling loop — shares this module's logger and constants with
# OllamaAgent above, so one run produces one coherent audit trail.
# --------------------------------------------------------------------------

def _call_signature(name, arguments):
    """Stable hash of a (tool_name, arguments) pair, for loop detection."""
    try:
        arg_str = json.dumps(arguments, sort_keys=True, default=str)
    except TypeError:
        arg_str = str(arguments)
    return hashlib.sha256(f"{name}:{arg_str}".encode()).hexdigest()[:16]


def _detect_cycle(signatures, period, repeats):
    """True if the last `period * repeats` signatures are exactly
    `repeats` consecutive repetitions of one `period`-length pattern.

    ROB-03: the single-tool repeat check (recent_call_signatures[
    -MAX_REPEAT_CALLS:].count(sig) >= MAX_REPEAT_CALLS) only catches
    A,A,A,... -- an agent oscillating A,B,A,B,A,B,... never has any one
    signature repeat 3 times in a row, so it sails through undetected.
    period=2 catches that; period=3 catches A,B,C,A,B,C,... the same
    way. Called with period in (2, 3) alongside the existing period=1
    check, all sharing the same `repeats` threshold (MAX_REPEAT_CALLS).
    """
    window = period * repeats
    if len(signatures) < window:
        return False
    tail = signatures[-window:]
    pattern = tail[:period]
    return all(tail[i:i + period] == pattern for i in range(0, window, period))


def _parse_arguments(raw_arguments):
    """Normalize tool call arguments to a dict, regardless of whether the
    client library handed us a dict or a JSON string. Never crash the
    loop on malformed input — raise ValueError so it becomes tool data
    the model can see and correct."""
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError as e:
            raise ValueError(f"malformed tool arguments (not valid JSON): {e}")
        if not isinstance(parsed, dict):
            raise ValueError("tool arguments must decode to a JSON object")
        return parsed
    raise ValueError(f"unsupported arguments type: {type(raw_arguments).__name__}")


def _sanitize_for_model(text):
    """Truncate long tool output before it re-enters the message history,
    so one chatty tool can't silently blow up the context window."""
    if len(text) > MAX_OBSERVATION_CHARS:
        return text[:MAX_OBSERVATION_CHARS] + f"\n…[truncated, {len(text)} chars total]"
    return text


def _run_tool_with_timeout(func, arguments, timeout_seconds):
    """Run one tool call with a hard wall-clock timeout, so a hung tool
    (network call, blocked subprocess) can never stall the agent loop."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(func, **arguments)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"tool exceeded {timeout_seconds}s timeout and was abandoned"
            )


def _validate_arguments(func, arguments: dict) -> None:
    """Check that `arguments` actually bind to `func`'s real parameters
    before calling it.

    Without this, a malformed tool call — an empty-string key, a typo'd
    parameter name, a missing required argument, an extra one the model
    invented — reaches func(**arguments) directly and blows up with a
    raw TypeError from Python's own argument binding (e.g. "got an
    unexpected keyword argument ''"). That's not actionable for the
    model reading it back as a tool result, and it's a generic-looking
    crash for a human reading the log. Validating here turns it into a
    clear message naming exactly what was expected vs what arrived, fed
    back as ordinary tool data the model can read and correct on its
    next attempt — same "errors are data, not crashes" principle as
    everywhere else in this loop.
    """
    signature = inspect.signature(func)
    try:
        signature.bind(**arguments)
    except TypeError as e:
        expected = list(signature.parameters.keys())
        given = list(arguments.keys())
        raise ValueError(
            f"invalid arguments for '{func.__name__}': {e}. "
            f"Expected parameters: {expected}. Got: {given}."
        )


def run_agent(agent, messages, tools, tool_map, verbose=True,
              max_iterations=MAX_ITERATIONS,
              max_wall_seconds=MAX_WALL_SECONDS,
              chat_logger=None,
              max_tool_calls=None):
    """Run the tool loop until the model gives a final answer.

    Every round is logged with a run id for audit purposes via Python's
    logging module (terminal/standard log handlers). If a `chat_logger`
    (a ChatLogger from chat_logger.py) is also passed in, every stage
    additionally gets a structured JSONL record — model call timing,
    each tool call/result with duration, and any stop reason. Pass
    nothing and it's a silent no-op (NullChatLogger), so callers that
    don't care about JSONL logs don't have to think about it.

    `max_tool_calls` is a separate, optional cap on the total number of
    tool calls across the whole run (not rounds — a single round can
    contain several calls). This matters for auto mode: "stop after 30
    tool calls if the task isn't finished" is a call-count budget, not
    a round-count one, and max_iterations alone doesn't express that.
    None (the default) means no extra cap beyond max_iterations.

    Tool errors, timeouts, malformed arguments, and repeated/stuck calls
    are all fed back to the model as data (never crash the loop). Full
    exception detail goes only to the log — never into the model's
    context — so internal paths or tracebacks don't leak into chat.
    """

    if chat_logger is None:
        chat_logger = NullChatLogger()

    run_id = uuid.uuid4().hex[:8]
    started_at = time.monotonic()
    recent_call_signatures = []
    total_tool_calls = 0

    logger.info("agent_run_started id=%s max_iterations=%s max_tool_calls=%s",
                run_id, max_iterations, max_tool_calls)

    for round_num in range(max_iterations):

        elapsed = time.monotonic() - started_at
        if elapsed > max_wall_seconds:
            logger.warning("agent_run_stopped id=%s reason=wall_timeout elapsed=%.1fs",
                            run_id, elapsed)
            chat_logger.error("wall_timeout", elapsed_seconds=round(elapsed, 1))
            return "(stopped: exceeded maximum run time)"

        # agent.chat() (OllamaAgent.chat above) already retries, times
        # out, and raises a friendly RuntimeError internally — this
        # except is the final backstop once that's exhausted.
        chat_logger.model_call_start(len(messages), tools)
        try:
            response = agent.chat(messages, tools=tools)
        except Exception as exc:
            logger.exception("agent_run_stopped id=%s reason=chat_failed round=%s",
                              run_id, round_num)
            chat_logger.error("chat_failed", round=round_num, detail=str(exc))
            return "(stopped: error communicating with the model)"

        messages.append(response.message)

        tool_calls_for_log = [
            {"name": c.function.name, "arguments": c.function.arguments}
            for c in (response.message.tool_calls or [])
        ]
        chat_logger.model_response(response.message.content, tool_calls_for_log, response=response)

        if response.message.content and verbose:
            print(f"  [thought] {response.message.content}")

        if not response.message.tool_calls:
            logger.info("agent_run_finished id=%s round=%s reason=final_answer",
                        run_id, round_num)
            return response.message.content or ""

        for call in response.message.tool_calls:
            tool_name = call.function.name

            total_tool_calls += 1
            if max_tool_calls is not None and total_tool_calls > max_tool_calls:
                logger.warning("agent_run_stopped id=%s reason=max_tool_calls calls=%s",
                                run_id, total_tool_calls - 1)
                chat_logger.error("max_tool_calls_reached", tool_calls=total_tool_calls - 1)
                return (
                    f"(stopped: reached the {max_tool_calls}-tool-call limit — "
                    "not a failure, just a sign the plan wandered; check plan.md "
                    "and the log to see where)"
                )

            if verbose:
                print(f"  [action] {tool_name}({call.function.arguments})")
            logger.info("tool_call id=%s round=%s tool=%s", run_id, round_num, tool_name)
            tool_start = chat_logger.tool_call(tool_name, call.function.arguments)
            func = tool_map.get(tool_name)

            try:
                arguments = _parse_arguments(call.function.arguments)
                if func is not None:
                    _validate_arguments(func, arguments)
                sig = _call_signature(tool_name, arguments)
                recent_call_signatures.append(sig)
                repeat_count = recent_call_signatures[-MAX_REPEAT_CALLS:].count(sig)
                # ROB-03: period=1 is the original "same call N times in a
                # row" check; periods 2 and 3 additionally catch an agent
                # oscillating between two or three distinct calls
                # (A,B,A,B,... or A,B,C,A,B,C,...), which period=1 alone
                # can never see since no single signature repeats back-to-back.
                is_stuck = repeat_count >= MAX_REPEAT_CALLS or any(
                    _detect_cycle(recent_call_signatures, period, MAX_REPEAT_CALLS)
                    for period in (2, 3)
                )
                if is_stuck:
                    logger.warning("agent_run_stopped id=%s reason=stuck_loop tool=%s",
                                   run_id, tool_name)
                    chat_logger.error("stuck_loop", tool=tool_name)
                    return f"(stopped: '{tool_name}' is part of a repeating tool-call pattern — agent appears stuck)"
            except ValueError as e:
                result = f"Error: {e}"
                chat_logger.tool_result(tool_name, result, tool_start, error=True)
                messages.append({"role": "tool", "name": tool_name, "content": result})
                if verbose:
                    print(f"  [observation] {result}")
                continue

            if func is None:
                result = f"Error: unknown tool '{tool_name}'"
                logger.warning("tool_call_unknown id=%s tool=%s", run_id, tool_name)
                chat_logger.tool_result(tool_name, result, tool_start, error=True)
            else:
                try:
                    raw_result = _run_tool_with_timeout(func, arguments, TOOL_TIMEOUT_SECONDS)
                    result = _sanitize_for_model(str(raw_result))
                    chat_logger.tool_result(tool_name, result, tool_start, error=False)
                except TimeoutError as e:
                    result = f"Error: {e}"
                    logger.warning("tool_call_timeout id=%s tool=%s", run_id, tool_name)
                    chat_logger.tool_result(tool_name, result, tool_start, error=True)
                except Exception as e:
                    logger.error("tool_call_error id=%s tool=%s\n%s",
                                 run_id, tool_name, traceback.format_exc())
                    result = f"Error: {type(e).__name__}: {e}"
                    chat_logger.tool_result(tool_name, result, tool_start, error=True)

            if verbose:
                print(f"  [observation] {result}")
            messages.append({"role": "tool", "name": tool_name, "content": str(result)})

    logger.warning("agent_run_stopped id=%s reason=max_iterations", run_id)
    chat_logger.loop_limit_hit(max_iterations)
    return "(stopped: too many tool rounds)"
