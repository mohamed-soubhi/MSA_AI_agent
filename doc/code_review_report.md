# Code Review & Architecture Audit Report

**Target:** AI Agent Core System (`CLI_agent.py`, `shared.py`, `fs_tools.py`, `shell_tools.py`, `confirm.py`, `auto_runner.py`, `memory.py`, `chat_logger.py`, `agent_config.py`, `log_config.py`, `config_reload.py`)  
**Date:** 2026-08-27  
**Status:** Active Defects Remediated & Dropped from Backlog  
**HTML Version:** [code_review_report.html](code_review_report.html)  
**Test Suite:** 524 Passed / 0 Failed (100% across core agent & backend)  

---

## Executive Summary & Audit State

All 9 previously identified defects have been **fully resolved, verified with unit and integration tests, and dropped from the active defect backlog**.

The active defect backlog currently contains **0 open defects**, and the one previously-documented design tradeoff (`ARCH-01`) has since been **fixed** — see below.

| Metric | Value | Notes |
|---|---|---|
| **Active / Open Defects** | **0** | Clean active backlog |
| **Remediated & Dropped Issues** | **10** | Resolved in code and verified by test suite |
| **Documented Design Tradeoffs** | **0** | ARCH-01 (formerly accepted) is now fixed |
| **Test Suite Pass Rate** | **100% (524/524)** | Zero failing tests across 22 test modules (446 agent + 78 BE) |
| **Modules Audited** | **15 Source Modules** | ~4,000 LoC core + ~6,500 LoC tests/docs |

---

## Active Defect Backlog

> **Status:** **CLEAN (0 Active Defects)**  
> All security vulnerabilities, concurrency race conditions, memory wipe hazards, sandbox-escape paths, and ReAct loop cycle defects have been fixed in the codebase and validated by automated tests.

---

## Documented Design Tradeoffs

None currently open. `ARCH-01` (below) was accepted as a tradeoff at the time of the original audit, then fixed once a real bug report (agent reading/modifying its own source) made the underlying risk concrete rather than theoretical.

---

## Remediated & Dropped Issues History

The following 9 issues have been remediated in code and dropped from the active defect backlog:

| ID | Title | Severity | Fixed Location | Resolution Summary | Verification Test Cases |
|---|---|---|---|---|---|
| `SEC-01` | Shell Command Chaining & Operator Bypass | Critical | [`agent/shell_tools.py:L52-L71`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/shell_tools.py#L52-L71) | Compound operator detection (`_is_compound`) forces `confirm(..., force_ask=True)` | `SHELL-028`–`SHELL-031` |
| `SEC-02` | Subprocess Group Leak on Timeout | High | [`agent/shell_tools.py:L127-L156`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/shell_tools.py#L127-L156) | Process group isolation (`start_new_session=True`) and group kill (`os.killpg`) | `SHELL-032`–`SHELL-033` |
| `ROB-01` | Signal / Thread Conflict in Confirmation Gate | High | [`agent/confirm.py:L55-L92`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/confirm.py#L55-L92) | Thread-safe `_read_input_with_timeout` daemon reader queue | `CONFIRM-010`–`CONFIRM-012`, `CONFIRM-033` |
| `ROB-02` | Non-Atomic Persistence & Memory Corruption | High | [`agent/memory.py:L43-L94`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/memory.py#L43-L94) | Atomic `tempfile` + `os.replace()` and `.corrupt.bak` backup preservation | `MEMORY-019`, `MEMORY-026`–`MEMORY-027` |
| `ROB-03` | Alternating Tool Call Stuck-Loop Blindspot | Medium | [`agent/shared.py:L163-L180`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/shared.py#L163-L180) | 2-gram and 3-gram cycle detection (`_detect_cycle`) | `SHARED-050`–`SHARED-052` |
| `ROB-04` | Summarizer Context Window Overflow | Medium | [`agent/memory.py:L184-L213`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/memory.py#L184-L213) | History windowing (`messages[-MEMORY_SUMMARY_MAX_MESSAGES:]`) | `MEMORY-028`–`MEMORY-029` |
| `UX-01` | Plan Generator Missing System Prompt | Medium | [`agent/auto_runner.py:L41-L65`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/auto_runner.py#L41-L65) | `SYSTEM_PROMPT` prepended to planning messages | `AUTORUN-013` |
| `SEC-03` | Plaintext Secrets in JSONL Audit Logs | Low | [`agent/chat_logger.py:L44-L80`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/chat_logger.py#L44-L80) | `_mask_secrets()` regex redaction for API keys, tokens, and headers | `CHATLOG-025`–`CHATLOG-032` |
| `ROB-05` | Numeric Environment Variable Crash | Low | [`agent/agent_config.py:L30-L48`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/agent_config.py#L30-L48) | Integer conversion wrapped in `try...except ValueError` with default fallback | `CONFIG-010`, `CONFIG-011` |
| `ARCH-01` | Sandbox Escape via cwd-Relative BASE_DIR | High | [`agent/fs_tools.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/fs_tools.py), [`agent/agent_config.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/agent_config.py) | Escalated from an accepted design tradeoff to a real fix after a bug report: the agent's own source read the repo root as `Path.cwd()` and was normally launched from there, so its own sandbox let it read/overwrite its own source. Source moved to `agent/`; `BASE_DIR` now `agent_config.WORKSPACE_DIR`, resolved from the config file's own on-disk location (`agent/`'s parent), fixed at `<project_root>/workspace/` regardless of launch cwd. `MEMORY_FILE`/`LOG_DIR` similarly fixed at the project root, outside the sandbox. | `AGENTCFG-028`–`031` |

---

## Module Architecture & Quality Matrix

### Agent Core Modules (446 Tests)

| Module | Primary Responsibility | Safety & Isolation Gate | Concurrency Safety | Test Count | Status |
|---|---|---|---|---|---|
| [`agent/CLI_agent.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/CLI_agent.py) | Agent CLI orchestrator & REPL loop | Human confirmation / System prompt | Single-threaded loop | 24 tests | **Robust** |
| [`agent/agent_config.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/agent_config.py) | Central configuration & env parsing | Type-safe defaults & error fallback | Immutable constants | 45 tests | **Robust** |
| [`agent/agent_mode.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/agent_mode.py) | Single global AUTO_MODE switch | Checked inside confirm() | Global variable (non-TLS) | Integrated | **Robust** |
| [`agent/auto_runner.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/auto_runner.py) | Plan generation & auto execution | Plan review + System prompt context | Scoped AUTO_MODE flag | 14 tests | **Robust** |
| [`agent/chat_logger.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/chat_logger.py) | Structured JSONL audit logging | Secret redaction & rotation | Thread lock protected | 44 tests | **Robust** |
| [`agent/confirm.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/confirm.py) | Human confirmation gate | ANSI sanitization & timed reader queue | Thread-safe non-blocking I/O | 43 tests | **Robust** |
| [`agent/fs_tools.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/fs_tools.py) | Sandboxed filesystem CRUD tools | resolve_path + Win reserved + Symlink check | Stateless I/O | 49 tests | **Robust** |
| [`agent/human_tools.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/human_tools.py) | Conversational HITL clarification | Option validation & confirm() delegation | Blocking stdin | 20 tests | **Robust** |
| [`agent/log_config.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/log_config.py) | Logging configuration switches | Env var overrides | Immutable constants | 25 tests | **Robust** |
| [`agent/config_reload.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/config_reload.py) | Hot-reload coordinator for live settings | In-place module reload & sys.modules lookup | Safe single-threaded reload | 11 tests | **Robust** |
| [`agent/memory.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/memory.py) | Cross-session durable memory | Atomic replace, score search & deduplication | Thread lock + Atomic rename | 43 tests | **Robust** |
| [`agent/shared.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/shared.py) | ReAct loop, Ollama wrapper & timeout | N-gram cycle detection & token accumulator | ThreadPoolExecutor per tool | 69 tests | **Robust** |
| [`agent/shell_tools.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/shell_tools.py) | Allowlisted terminal execution | Compound operator gate & killpg | Process group scoping | 48 tests | **Robust** |
| [`agent/web_tools.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/web_tools.py) | Config-gated internet web search & fetch | Confirmation gate & truncation limit | Non-blocking API wrapper | 11 tests | **Robust** |
| [`agent/tools_registry.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/agent/tools_registry.py) | Unified active tool assembly | Dynamic config flag resolution | Thread-safe registry lookup | Integrated | **Robust** |

### Backend Service Modules (78 Tests)

| Module | Primary Responsibility | Safety & Isolation Gate | Concurrency Safety | Test Count | Status |
|---|---|---|---|---|---|
| [`BE/app/core/approval_bridge.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/BE/app/core/approval_bridge.py) | Async approval & human bridge | ID mismatch rejection & timeout handling | Multi-threaded event queue | 7 tests | **Robust** |
| [`BE/app/core/tool_bridge.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/BE/app/core/tool_bridge.py) | Tool registry re-exporter & wrapper | Live `WEB_TOOLS_ENABLED` evaluation | Thread-safe tool map | 3 tests | **Robust** |
| [`BE/app/api/chat.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/BE/app/api/chat.py) | Streaming chat & history API | `_turn_lock` active-turn concurrency limit | Async lock + SSE disconnect | 14 tests | **Robust** |
| [`BE/app/api/config.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/BE/app/api/config.py) | Config editor & directory picker | Comment-preserving diff & restart gating | Live hot-reloading | 21 tests | **Robust** |
| [`BE/app/api/health.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/BE/app/api/health.py) | Service health monitoring | Liveness probing | Stateless ASGI | 2 tests | **Robust** |
| [`BE/app/api/memory.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/BE/app/api/memory.py) | Read-only memory inspector | Non-modifying memory viewer | Thread-safe read fallback | 4 tests | **Robust** |
| [`BE/app/api/models.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/BE/app/api/models.py) | Model catalog & spec inspection | Local & cloud model segregation | Non-blocking HTTP catalog | 12 tests | **Robust** |
| [`BE/app/api/shutdown.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/BE/app/api/shutdown.py) | Graceful process termination | Process signal dispatch | Process group `SIGTERM` | 4 tests | **Robust** |
| [`BE/app/api/workspace.py`](file:///mnt/c/MSA/build-ai-agents-from-scratch/Project/BE/app/api/workspace.py) | Sandboxed file preview & OS file manager open | Enforces `fs_tools.resolve_path()` | Read-only sandboxed I/O | 11 tests | **Robust** |
