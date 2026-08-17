# Code Review & Defect Assessment Report

**Target:** AI Agent Core System (`09_full_agent.py`, `shared.py`, `fs_tools.py`, `shell_tools.py`, `confirm.py`, `auto_runner.py`, `memory.py`, `chat_logger.py`, `agent_config.py`, `log_config.py`)  
**Date:** 2026-08-17  
**Status:** Read-Only Audit Completed  
**HTML Version:** [code_review_report.html](code_review_report.html)

---

## Executive Summary

An exhaustive security, concurrency, robustness, and architectural audit was conducted across the 12 Python modules, 331 tests, and supporting tools of the sandboxed AI agent codebase.

All 331 unit and integration tests currently pass (100% pass rate). The architecture demonstrates strong foundations: single-choke-point path resolution in `fs_tools.py`, structured JSONL audit trails with rotation in `chat_logger.py`, fail-closed confirmation gates in `confirm.py`, and clean separation of concerns.

However, several critical and high-severity design edge cases were identified—primarily concerning compound shell command parsing under auto-mode, POSIX signal handling within secondary worker threads, subprocess orphan leaks upon timeout, and non-atomic JSON memory persistence.

---

## Audit Metrics

| Metric | Value | Notes |
|---|---|---|
| **Total Findings** | 10 | 1 Critical, 3 High, 4 Medium, 2 Low |
| **Test Suite Pass Rate** | 100% (331/331) | Zero failing tests |
| **Modules Audited** | 12 Source Modules | ~3,500 LoC core + ~5,000 LoC tests/docs |
| **Primary Risk Area** | Shell Execution & Concurrency | `shell_tools.py`, `confirm.py`, `memory.py` |

---

## Key Findings by Severity

### 1. [SEC-01] Shell Command Chaining & Operator Bypass in Auto Mode
- **Severity:** Critical
- **Location:** `shell_tools.py` (lines 72–104)
- **Description:** `first_token = shlex.split(command)[0]` inspects only the first token of a command string, then passes the full unparsed string to `subprocess.run(command, shell=True)`. In compound commands (`echo hello && /bin/bash -c '...'` or `echo test | sh`), the first binary is allowlisted (`echo`), no substring matches `BLOCKED`, and under `agent_mode.AUTO_MODE = True`, the gate auto-approves.
- **Impact:** Arbitrary command execution without human authorization in auto mode.
- **Mitigation:** Parse compound shell statements or split on shell operators (`&&`, `||`, `;`, `|`, `&`, `$()`, backticks) and validate each command token, or switch to `shell=False` execution with direct argument arrays.

---

### 2. [SEC-02] Subprocess Process Group Leak on Shell Timeout
- **Severity:** High
- **Location:** `shell_tools.py` (lines 99–116)
- **Description:** When `subprocess.run(command, shell=True, timeout=TIMEOUT_SECONDS)` times out, Python sends `SIGKILL` only to the immediate `/bin/sh` shell process. Child processes spawned by the shell (e.g. servers, build tools, background workers) become orphaned and continue running in the background.
- **Impact:** Lingering background processes, CPU/RAM exhaustion, locked socket ports.
- **Mitigation:** Use `start_new_session=True` when spawning subprocesses and terminate the entire process group with `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` on timeout.

---

### 3. [ROB-01] POSIX Signal / Threading Conflict in Confirmation Gate
- **Severity:** High
- **Location:** `confirm.py` (lines 114–116) vs `shared.py` (line 192)
- **Description:** `_run_tool_with_timeout` executes tool functions within a worker thread via `ThreadPoolExecutor`. If a tool inside that thread invokes `confirm()`, `signal.signal(signal.SIGALRM, ...)` raises `ValueError: signal only works in main thread of the main interpreter`. `confirm()` catches `Exception` and defaults to denying the request.
- **Impact:** Unintended tool denials when confirmation timeouts are active on worker threads.
- **Mitigation:** Use non-blocking terminal polling (e.g. `select.select([sys.stdin], [], [], timeout)` on POSIX) instead of `signal.alarm`.

---

### 4. [ROB-02] Non-Atomic Persistence & Memory Corruption Wipe Hazard
- **Severity:** High
- **Location:** `memory.py` (lines 42–66)
- **Description:** `_save()` writes JSON directly to `MEMORY_PATH` without atomic file replacement. If the process is killed or interrupted mid-write, `memory.json` is corrupted. Upon restart, `_load()` catches `json.JSONDecodeError`, returns `[]`, and the next write overwrites the file—permanently destroying all project memories.
- **Impact:** Permanent data loss of durable memories upon unexpected shutdown.
- **Mitigation:** Write to a temporary file in the same directory and atomically replace with `os.replace()`. Save corrupted files to a `.corrupt.bak` backup.

---

### 5. [ARCH-01] Module-Level Static Path and Sandbox Resolution
- **Severity:** Medium
- **Location:** `fs_tools.py` (line 37), `memory.py` (line 39)
- **Description:** `BASE_DIR = Path.cwd().resolve()` is evaluated once upon module import. If the current working directory changes dynamically or if multiple workspace contexts run concurrently in one process, `BASE_DIR` does not adapt.
- **Mitigation:** Encapsulate workspace paths inside an injectable `WorkspaceContext` or pass `base_dir` explicitly.

---

### 6. [ROB-03] Alternating Tool Call Stuck-Loop Blindspot
- **Severity:** Medium
- **Location:** `shared.py` (lines 330–337)
- **Description:** Stuck loop detection checks `recent_call_signatures[-MAX_REPEAT_CALLS:].count(sig)`. If the agent oscillates between two tools (A &rarr; B &rarr; A &rarr; B), the single-tool repetition count in any window of 3 calls never reaches 3.
- **Mitigation:** Implement 2-gram / 3-gram periodic cycle detection in recent call history.

---

### 7. [ROB-04] Unbounded Multi-Turn History & Summarization Context Bloat
- **Severity:** Medium
- **Location:** `09_full_agent.py` (line 93), `memory.py` (lines 176–187)
- **Description:** `messages` grows indefinitely across user turns in the CLI loop. `save_session_summary` transmits the complete conversation history to Ollama in a single prompt at shutdown, risking context length overflows.
- **Mitigation:** Introduce sliding-window history management and tool observation trimming for long conversations.

---

### 8. [UX-01] Auto-Mode Plan Generator Disconnected from System Persona
- **Severity:** Medium
- **Location:** `auto_runner.py` (lines 41–55)
- **Description:** `_generate_plan` sends a user prompt without the agent's `SYSTEM_PROMPT`. The model creates plans without knowledge of project constraints, non-interactive flags, or memory tools.
- **Mitigation:** Include `SYSTEM_PROMPT` in planning messages.

---

### 9. [SEC-03] Secret and Sensitive Data Exposure in Audit Logs
- **Severity:** Low
- **Location:** `chat_logger.py` (lines 140–169)
- **Description:** Tool arguments and model outputs are written to JSONL logs without credential filtering. Inspecting `.env` files or tokens records them in plaintext logs.
- **Mitigation:** Add regex masking for API tokens and private keys in `_truncate()`.

---

### 10. [ROB-05] Environment Variable Parsing Crash on Non-Integer Values
- **Severity:** Low
- **Location:** `agent_config.py` (lines 27–30)
- **Description:** `_env_int` calls `int(raw)` directly without catching `ValueError`, causing unhandled exceptions on invalid environment variables.
- **Mitigation:** Wrap `int(raw)` in a `try...except ValueError` block with fallback to `default`.

---

## Architectural & Concurrency Summary Matrix

| Module | Purpose | Security Gate | Concurrency | Test Coverage |
|---|---|---|---|---|
| `09_full_agent.py` | REPL & Entry point | Confirmation & System Prompt | Single-threaded | 18 tests (Pass) |
| `agent_config.py` | Configuration constants | Type-safe defaults | Immutable constants | 37 tests (Pass) |
| `agent_mode.py` | Global AUTO_MODE toggle | Checked in `confirm()` | Global flag | Integrated (Pass) |
| `auto_runner.py` | Auto-mode orchestration | Plan approval + Tool cap | Scoped flag toggle | 12 tests (Pass) |
| `chat_logger.py` | JSONL session logging | Exception swallowing | Thread-locked | 32 tests (Pass) |
| `confirm.py` | Confirmation gate | ANSI strip, TTY check | Signal hazard in threads | 32 tests (Pass) |
| `fs_tools.py` | Sandboxed FS tools | `resolve_path` single choke | Stateless | 49 tests (Pass) |
| `human_tools.py` | HITL clarification tools | Delegation to `confirm()` | Blocking stdin | 16 tests (Pass) |
| `log_config.py` | Logging config constants | Env var overrides | Immutable constants | 25 tests (Pass) |
| `memory.py` | Durable memory storage | Substring & Tag filters | Non-atomic write | 25 tests (Pass) |
| `shared.py` | ReAct loop & Ollama wrapper | Arg validation, Stuck loop | ThreadPool per tool | 49 tests (Pass) |
| `shell_tools.py` | Terminal execution | Allowlist & Blocklist | Subprocess execution | 36 tests (Pass) |

---

## Strategic Remediation Roadmap

1. **Phase 1 (Immediate Security):**
   - Disallow unparsed shell chaining operators in `shell_tools.py` or switch to `shell=False`.
   - Add process group scoping (`start_new_session=True` / `os.killpg`) to eliminate orphan process leaks.
2. **Phase 2 (Concurrency & Data Safety):**
   - Replace POSIX `signal.alarm` in `confirm.py` with non-blocking polling (`select.select`).
   - Implement atomic temporary file replacement (`os.replace`) in `memory.py`.
3. **Phase 3 (Robustness & Context):**
   - Introduce n-gram cycle detection in `shared.py` to prevent oscillating tool loops.
   - Add sliding-window context trimming in `09_full_agent.py` and `memory.py`.
