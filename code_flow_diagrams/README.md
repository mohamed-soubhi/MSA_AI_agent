# Project Code Flow & Architecture Visualizer

An interactive HTML + SVG architectural dashboard and code flow visualizer for the sandboxed AI agent system.

## Features

- **🏛️ High-Level System Topology (SVG)**: Complete 30,000-ft diagram showing dual entry points (CLI & Web), core ReAct loop, 4-layer security gates, sandboxed workspace, and persistence stores.
- **📁 Directory & Module Reference**: Interactive visual file tree and complete module matrix detailing roles, responsibilities, line counts, and security invariants.
- **🔀 9 Interactive Flow Graphs (SVG)**:
  1. `cli_execution_flow.svg` — REPL loop, exit handling, and token accounting in `finally`.
  2. `auto_vs_step_mode.svg` — Granular step-by-step confirmation vs. upfront plan approval with 30-tool cap.
  3. `backend_sse_approval_flow.svg` — FastAPI HTTP threads, background `ConversationTurn` daemon worker, SSE event stream, and HTTP response unblocking.
  4. `react_tool_loop.svg` — ReAct tool loop, argument parsing, parameter validation, SHA-256 signature hashing, multi-period cycle detection (periods 1..3), and observation capping.
  5. `filesystem_sandbox_gate.svg` — Single choke point `resolve_path()` with control character checks, Unicode NFKC normalization, Windows reserved device names, and TOCTOU symlink checks.
  6. `shell_4layer_defense.svg` — Program Allowlist, Substring Blocklist & Compound operator detection (`&&`, `||`, `;`), Human confirm gate, and `os.killpg()` process group isolation.
  7. `confirm_gate_concurrency.svg` — Fail-closed approval gate, TTY checks, non-blocking `_stdin_lock`, background daemon reader thread, and orphan lock retention.
  8. `memory_atomic_persistence.svg` — Atomic JSON swap (`os.replace`), `.corrupt.bak` recovery, 40-message windowed summarization, and cumulative token tracking.
  9. `config_drift_safe_engine.svg` — Drift-safe default values extraction via isolated subprocess and comment-preserving `.env` file updates.
- **📞 Calls & Sequence Maps**: Detailed inter-module call hierarchy, method signatures, parameter types, return values, and failure paths.
- **⚡ Interactive Code Flow Simulator**: Step-by-step interactive simulator stepping through 4 real-world execution scenarios.
- **🔒 Security & Defense-in-Depth**: Deep-dive analysis of the 10 structural security and robustness decisions across the codebase.

## How to View

You can open the visualizer directly in any modern browser:

```bash
# Option 1: Open directly in your browser
xdg-open code_flow_diagrams/index.html   # On Linux
open code_flow_diagrams/index.html       # On macOS
start code_flow_diagrams/index.html      # On Windows

# Option 2: Serve via Python HTTP server
python3 -m http.server 8080 --directory code_flow_diagrams
# Then navigate to: http://localhost:8080/
```

## Directory Layout

```
code_flow_diagrams/
├── index.html                     — Main interactive dashboard application
├── style.css                      — Modern dark/light theme stylesheet with glassmorphism
├── app.js                         — Interactive controller (pan/zoom, tabs, search, simulator)
├── README.md                      — This index and guide
├── build_svgs.py                  — Generator for standalone SVG diagrams
├── build_site.py                  — Generator for HTML, CSS, JS, and documentation
└── svg/                           — 11 standalone, scalable SVG diagram files
    ├── system_architecture.svg
    ├── cli_execution_flow.svg
    ├── auto_vs_step_mode.svg
    ├── backend_sse_approval_flow.svg
    ├── react_tool_loop.svg
    ├── filesystem_sandbox_gate.svg
    ├── shell_4layer_defense.svg
    ├── confirm_gate_concurrency.svg
    ├── memory_atomic_persistence.svg
    ├── config_drift_safe_engine.svg
    └── module_dependencies.svg
```
