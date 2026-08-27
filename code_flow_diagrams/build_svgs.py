#!/usr/bin/env python3
"""
Full generator for Code Flow Diagrams and Interactive Dashboard.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SVG_DIR = BASE_DIR / "svg"
SVG_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# 1. GENERATE SVGS
# --------------------------------------------------------------------------

def write_svgs():
    # 1. System Architecture
    svg1 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 860" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1e293b"/></linearGradient>
    <linearGradient id="cli" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#3b82f6"/><stop offset="100%" stop-color="#1d4ed8"/></linearGradient>
    <linearGradient id="web" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#10b981"/><stop offset="100%" stop-color="#047857"/></linearGradient>
    <linearGradient id="core" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#8b5cf6"/><stop offset="100%" stop-color="#6d28d9"/></linearGradient>
    <linearGradient id="sec" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#f59e0b"/><stop offset="100%" stop-color="#b45309"/></linearGradient>
    <linearGradient id="tools" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#ec4899"/><stop offset="100%" stop-color="#be185d"/></linearGradient>
    <linearGradient id="sand" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#14b8a6"/><stop offset="100%" stop-color="#0f766e"/></linearGradient>
    <linearGradient id="store" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#64748b"/><stop offset="100%" stop-color="#334155"/></linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%"><feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.45"/></filter>
    <marker id="ar" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#94a3b8"/></marker>
    <marker id="ar-b" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#38bdf8"/></marker>
    <marker id="ar-g" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#34d399"/></marker>
    <marker id="ar-p" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#a78bfa"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 22px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .bt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 14px; fill: #ffffff; }
    .bs { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .bdg { font-family: monospace; font-size: 10px; font-weight: 600; }
    .w { stroke: #64748b; stroke-width: 2; fill: none; }
    .wb { stroke: #38bdf8; stroke-width: 2.5; fill: none; }
    .wg { stroke: #34d399; stroke-width: 2.5; fill: none; }
    .wp { stroke: #a78bfa; stroke-width: 2.5; fill: none; }
    .lbg { rx: 12; ry: 12; fill: rgba(30, 41, 59, 0.75); stroke: #334155; stroke-width: 1.5; filter: url(#shadow); }
    .nb { rx: 8; ry: 8; filter: url(#shadow); }
  </style>

  <rect width="1200" height="860" rx="16" fill="url(#bg)" stroke="#334155" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">SYSTEM ARCHITECTURE — HIGH LEVEL TOPOLOGY</text>
    <text class="st" x="0" y="44">Dual Interaction Surfaces (CLI / Web UI), Core ReAct Engine, Pluggable Gates &amp; Sandbox</text>
  </g>

  <!-- L1 -->
  <rect class="lbg" x="40" y="80" width="1120" height="110"/>
  <text class="bt" x="60" y="104" fill="#93c5fd">1. INTERACTION LAYER (DUAL SURFACES)</text>
  <g transform="translate(70, 115)">
    <rect class="nb" width="280" height="60" fill="url(#cli)"/>
    <text class="bt" x="15" y="25">CLI REPL Terminal</text>
    <text class="bs" x="15" y="45">agent/CLI_agent.py (auto / step)</text>
    <rect x="200" y="8" width="70" height="18" rx="4" fill="#1e3a8a"/><text class="bdg" x="208" y="21" fill="#93c5fd">STDIN/TTY</text>
  </g>
  <g transform="translate(430, 115)">
    <rect class="nb" width="320" height="60" fill="url(#web)"/>
    <text class="bt" x="15" y="25">Web UI (SPA Chat &amp; Config)</text>
    <text class="bs" x="15" y="45">BE/app/static/chat.html &amp; config.html</text>
    <rect x="235" y="8" width="75" height="18" rx="4" fill="#064e3b"/><text class="bdg" x="242" y="21" fill="#6ee7b7">SSE + FETCH</text>
  </g>
  <g transform="translate(830, 115)">
    <rect class="nb" width="290" height="60" fill="url(#store)"/>
    <text class="bt" x="15" y="25">Nginx Reverse Proxy</text>
    <text class="bs" x="15" y="45">BE/nginx/nginx.conf (:80 → :8000)</text>
    <rect x="210" y="8" width="70" height="18" rx="4" fill="#1e293b"/><text class="bdg" x="220" y="21" fill="#cbd5e1">PORT 80</text>
  </g>
  <path d="M 750 145 L 830 145" class="w" marker-end="url(#ar)"/>

  <!-- L2 -->
  <rect class="lbg" x="40" y="210" width="1120" height="135"/>
  <text class="bt" x="60" y="234" fill="#a7f3d0">2. BACKEND API &amp; ASYNC BRIDGES (BE/app/)</text>
  <g transform="translate(70, 248)">
    <rect class="nb" width="240" height="80" fill="#065f46" stroke="#10b981" stroke-width="1.5"/>
    <text class="bt" x="15" y="24">FastAPI Application</text>
    <text class="bs" x="15" y="44">BE/app/main.py</text>
    <text class="bs" x="15" y="62">Routers: /chat, /config, /models</text>
  </g>
  <g transform="translate(340, 248)">
    <rect class="nb" width="370" height="80" fill="#1e293b" stroke="#34d399" stroke-width="1.5"/>
    <text class="bt" x="15" y="24">Approval &amp; Human Bridge</text>
    <text class="bs" x="15" y="44">BE/app/core/approval_bridge.py</text>
    <text class="bs" x="15" y="62">ConversationTurn (Daemon Worker + Queue)</text>
    <rect x="260" y="8" width="95" height="18" rx="4" fill="#047857"/><text class="bdg" x="267" y="21" fill="#a7f3d0">EVENT QUEUE</text>
  </g>
  <g transform="translate(740, 248)">
    <rect class="nb" width="380" height="80" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
    <text class="bt" x="15" y="24">Tool &amp; Agent Bridges</text>
    <text class="bs" x="15" y="44">BE/app/core/tool_bridge.py &amp; agent_bridge.py</text>
    <text class="bs" x="15" y="62">Reuses agent/ shared code &amp; 9 exact tools</text>
  </g>
  <path d="M 975 175 L 975 220 L 190 220 L 190 248" class="w" marker-end="url(#ar)"/>
  <path d="M 310 288 L 340 288" class="wg" marker-end="url(#ar-g)"/>
  <path d="M 710 288 L 740 288" class="wb" marker-end="url(#ar-b)"/>

  <!-- L3 -->
  <rect class="lbg" x="40" y="365" width="1120" height="135"/>
  <text class="bt" x="60" y="389" fill="#c4b5fd">3. CORE AGENT ENGINE (agent/shared.py &amp; auto_runner.py)</text>
  <g transform="translate(70, 405)">
    <rect class="nb" width="260" height="75" fill="url(#core)"/>
    <text class="bt" x="15" y="24">OllamaAgent Wrapper</text>
    <text class="bs" x="15" y="44">Timeout (60s) + Retry (2x)</text>
    <text class="bs" x="15" y="60">Token Tracking (total_tokens)</text>
  </g>
  <g transform="translate(360, 405)">
    <rect class="nb" width="410" height="75" fill="#4c1d95" stroke="#a78bfa" stroke-width="1.5"/>
    <text class="bt" x="15" y="24">run_agent() ReAct Loop</text>
    <text class="bs" x="15" y="44">Max 40 Iterations | Cycle Detect (p=1..3) | Sig Hash</text>
    <text class="bs" x="15" y="60">Arg Validation | Observation Sanitize (4000c limit)</text>
  </g>
  <g transform="translate(800, 405)">
    <rect class="nb" width="320" height="75" fill="#312e81" stroke="#818cf8" stroke-width="1.5"/>
    <text class="bt" x="15" y="24">Auto Mode Orchestration</text>
    <text class="bs" x="15" y="44">auto_runner.py: _generate_plan(tools=None)</text>
    <text class="bs" x="15" y="60">writes plan.md | 30 Tool Cap</text>
  </g>
  <path d="M 150 175 L 150 405" class="wb" marker-end="url(#ar-b)"/>
  <path d="M 525 328 L 525 365 L 450 365 L 450 405" class="wg" marker-end="url(#ar-g)"/>
  <path d="M 330 442 L 360 442" class="wp" marker-end="url(#ar-p)"/>
  <path d="M 770 442 L 800 442" class="wp" marker-end="url(#ar-p)"/>

  <!-- L4 -->
  <rect class="lbg" x="40" y="520" width="1120" height="115"/>
  <text class="bt" x="60" y="544" fill="#fde68a">4. PLUGGABLE APPROVAL GATE &amp; SAFETY BOUNDARIES</text>
  <g transform="translate(70, 555)">
    <rect class="nb" width="340" height="65" fill="url(#sec)"/>
    <text class="bt" x="15" y="22">confirm.py (Fail-Closed Gate)</text>
    <text class="bs" x="15" y="40">TTY Check | _stdin_lock | force_ask Override</text>
    <text class="bs" x="15" y="55">ANSI Strip Sanitization | Timeout (120s)</text>
  </g>
  <g transform="translate(440, 555)">
    <rect class="nb" width="310" height="65" fill="#78350f" stroke="#fbbf24" stroke-width="1.5"/>
    <text class="bt" x="15" y="22">Pluggable Backends</text>
    <text class="bs" x="15" y="40">set_confirm_backend(fn)</text>
    <text class="bs" x="15" y="55">set_human_backend(fn)</text>
  </g>
  <g transform="translate(780, 555)">
    <rect class="nb" width="340" height="65" fill="#7c2d12" stroke="#f97316" stroke-width="1.5"/>
    <text class="bt" x="15" y="22">Shell 4-Layer Defense Gate</text>
    <text class="bs" x="15" y="40">1: Allowlist | 2: Blocklist + Compound | 3: confirm</text>
    <text class="bs" x="15" y="55">4: Subprocess Timeout &amp; os.killpg(SIGKILL)</text>
  </g>

  <!-- L5 -->
  <rect class="lbg" x="40" y="655" width="1120" height="175"/>
  <text class="bt" x="60" y="679" fill="#fbcfe8">5. TOOLS, SANDBOX (workspace/) &amp; PERSISTENCE</text>
  <g transform="translate(70, 695)">
    <rect class="nb" width="250" height="115" fill="url(#tools)"/>
    <text class="bt" x="12" y="20">fs_tools.py (Sandbox)</text>
    <text class="bs" x="12" y="38">list_dir, read_file</text>
    <text class="bs" x="12" y="54">write_file (2MB cap), create_dir</text>
    <text class="bs" x="12" y="70">resolve_path() Choke Point</text>
    <text class="bs" x="12" y="86">Unicode NFKC + Reserved Check</text>
  </g>
  <g transform="translate(340, 695)">
    <rect class="nb" width="220" height="115" fill="url(#tools)"/>
    <text class="bt" x="12" y="20">shell_tools.py</text>
    <text class="bs" x="12" y="38">run_command()</text>
    <text class="bs" x="12" y="54">Cwd = BASE_DIR</text>
    <text class="bs" x="12" y="70">start_new_session=True</text>
    <text class="bs" x="12" y="86">Triple stream cap (_format_result)</text>
  </g>
  <g transform="translate(580, 695)">
    <rect class="nb" width="250" height="115" fill="url(#tools)"/>
    <text class="bt" x="12" y="20">human_tools &amp; memory</text>
    <text class="bs" x="12" y="38">ask_human, ask_human_choice</text>
    <text class="bs" x="12" y="54">remember_fact, recall_memory</text>
    <text class="bs" x="12" y="70">save_session_summary (on exit)</text>
    <text class="bs" x="12" y="86">save_token_usage (in finally)</text>
  </g>
  <g transform="translate(850, 695)">
    <rect class="nb" width="270" height="115" fill="url(#sand)"/>
    <text class="bt" x="12" y="20">Sandbox &amp; External Stores</text>
    <text class="bs" x="12" y="38">workspace/ (Sandboxed BASE_DIR)</text>
    <text class="bs" x="12" y="54">memory.json (Atomic replace)</text>
    <text class="bs" x="12" y="70">logs/*.jsonl (Redacted Secrets)</text>
    <text class="bs" x="12" y="86">agent/.env &amp; BE/.env</text>
  </g>
  <path d="M 240 620 L 240 655 L 195 655 L 195 695" class="w" marker-end="url(#ar)"/>
  <path d="M 950 620 L 950 655 L 450 655 L 450 695" class="w" marker-end="url(#ar)"/>
  <path d="M 700 750 L 850 750" class="w" marker-end="url(#ar)"/>
</svg>"""
    (SVG_DIR / "system_architecture.svg").write_text(svg1, encoding="utf-8")

    # 2. CLI Execution Flow
    svg2 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 840" width="100%" height="100%">
  <defs>
    <linearGradient id="bg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#090d16"/><stop offset="100%" stop-color="#1e293b"/></linearGradient>
    <marker id="arr" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#38bdf8"/></marker>
    <marker id="arr-red" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#f87171"/></marker>
    <marker id="arr-grn" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#4ade80"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .wb { stroke: #38bdf8; stroke-width: 2.5; fill: none; }
    .wr { stroke: #f87171; stroke-width: 2.5; fill: none; }
    .wg { stroke: #4ade80; stroke-width: 2.5; fill: none; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .diamond { stroke-width: 1.5; }
  </style>

  <rect width="1100" height="840" rx="16" fill="url(#bg2)" stroke="#334155" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">CLI AGENT EXECUTION LIFECYCLE (CLI_agent.py)</text>
    <text class="st" x="0" y="44">REPL Loop, Auto vs Step Mode Routing, Exception Boundaries, and Persistent Token Accounting</text>
  </g>

  <!-- Step 1: Init -->
  <g transform="translate(400, 80)">
    <rect class="box" width="300" height="60" fill="#1e3a8a" stroke="#3b82f6"/>
    <text class="nt" x="15" y="24">1. Process Startup &amp; Config</text>
    <text class="ns" x="15" y="42">load_dotenv(), load_token_usage(), OllamaAgent()</text>
  </g>

  <!-- Step 2: Session Banner -->
  <g transform="translate(400, 170)">
    <rect class="box" width="300" height="55" fill="#1e293b" stroke="#64748b"/>
    <text class="nt" x="15" y="22">2. Print Sandbox &amp; Seed System Prompt</text>
    <text class="ns" x="15" y="40">messages = [{"role": "system", "content": SYSTEM_PROMPT}]</text>
  </g>
  <path d="M 550 140 L 550 170" class="wb" marker-end="url(#arr)"/>

  <!-- Step 3: User Input -->
  <g transform="translate(400, 255)">
    <rect class="box" width="300" height="55" fill="#0f766e" stroke="#14b8a6"/>
    <text class="nt" x="15" y="22">3. REPL Prompt: input("You > ")</text>
    <text class="ns" x="15" y="40">chat_logger.user_message(user_input)</text>
  </g>
  <path d="M 550 225 L 550 255" class="wb" marker-end="url(#arr)"/>

  <!-- Step 4: Decision: Exit? -->
  <g transform="translate(450, 340)">
    <polygon points="100,0 200,45 100,90 0,45" fill="#78350f" stroke="#f59e0b" class="diamond"/>
    <text class="nt" x="55" y="48">Is Exit / Quit?</text>
  </g>
  <path d="M 550 310 L 550 340" class="wb" marker-end="url(#arr)"/>

  <!-- Exit Path -->
  <g transform="translate(800, 355)">
    <rect class="box" width="250" height="60" fill="#7f1d1d" stroke="#ef4444"/>
    <text class="nt" x="15" y="24">Exit Cleanly</text>
    <text class="ns" x="15" y="42">save_session_summary() (LLM Turn)</text>
    <text class="ns" x="15" y="54">chat_logger.session_end("user_exit")</text>
  </g>
  <path d="M 650 385 L 800 385" class="wr" marker-end="url(#arr-red)"/>
  <text class="ns" x="690" y="375" fill="#f87171">YES ("exit"/"q")</text>

  <!-- Step 5: Mode Decision -->
  <g transform="translate(450, 470)">
    <polygon points="100,0 200,45 100,90 0,45" fill="#4c1d95" stroke="#a78bfa" class="diamond"/>
    <text class="nt" x="48" y="48">auto_mode == True?</text>
  </g>
  <path d="M 550 430 L 550 470" class="wb" marker-end="url(#arr)"/>
  <text class="ns" x="560" y="450" fill="#cbd5e1">NO</text>

  <!-- Auto Mode Path -->
  <g transform="translate(80, 580)">
    <rect class="box" width="360" height="100" fill="#312e81" stroke="#818cf8"/>
    <text class="nt" x="15" y="22">Auto Mode: run_with_auto_mode()</text>
    <text class="ns" x="15" y="40">1. _generate_plan(tools=None)</text>
    <text class="ns" x="15" y="56">2. Write &amp; display plan.md</text>
    <text class="ns" x="15" y="72">3. confirm("Run plan?", force_ask=True)</text>
    <text class="ns" x="15" y="88">4. run_agent(max_tool_calls=30)</text>
  </g>
  <path d="M 450 515 L 260 515 L 260 580" class="wp" marker-end="url(#arr)"/>
  <text class="ns" x="310" y="505" fill="#a78bfa">YES (auto_mode)</text>

  <!-- Step Mode Path -->
  <g transform="translate(480, 580)">
    <rect class="box" width="360" height="100" fill="#065f46" stroke="#34d399"/>
    <text class="nt" x="15" y="22">Step Mode: run_agent()</text>
    <text class="ns" x="15" y="40">1. messages.append(user_input)</text>
    <text class="ns" x="15" y="56">2. ReAct loop with 9 tools</text>
    <text class="ns" x="15" y="72">3. confirm() prompts on every write/cmd</text>
    <text class="ns" x="15" y="88">4. Print Agent &gt; Answer</text>
  </g>
  <path d="M 650 515 L 660 515 L 660 580" class="wg" marker-end="url(#arr-grn)"/>
  <text class="ns" x="670" y="505" fill="#4ade80">NO (step_mode)</text>

  <!-- Loop back to REPL -->
  <path d="M 260 680 L 260 720 L 550 720" class="wb"/>
  <path d="M 660 680 L 660 720 L 550 720" class="wb"/>
  <path d="M 550 720 L 50 720 L 50 280 L 400 280" class="wb" marker-end="url(#arr)"/>
  <text class="ns" x="70" y="710" fill="#38bdf8">Next REPL Turn</text>

  <!-- Shutdown finally block -->
  <g transform="translate(800, 680)">
    <rect class="box" width="250" height="85" fill="#1e293b" stroke="#f59e0b"/>
    <text class="nt" x="15" y="22">finally: _report_token_usage()</text>
    <text class="ns" x="15" y="40">save_token_usage(session_tokens)</text>
    <text class="ns" x="15" y="56">Persists to memory.json</text>
    <text class="ns" x="15" y="72">Runs even on Crash / Ctrl-C</text>
  </g>
  <path d="M 925 415 L 925 680" class="wr" marker-end="url(#arr-red)"/>

</svg>"""
    (SVG_DIR / "cli_execution_flow.svg").write_text(svg2, encoding="utf-8")

    # 3. Auto vs Step Mode
    svg3 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1150 760" width="100%" height="100%">
  <defs>
    <linearGradient id="bg3" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1e1b4b"/></linearGradient>
    <marker id="ar3" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#38bdf8"/></marker>
    <marker id="ar3-grn" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#34d399"/></marker>
    <marker id="ar3-pur" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#c084fc"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .ht { font-family: system-ui, sans-serif; font-weight: 700; font-size: 15px; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .col-bg { rx: 12; ry: 12; fill: rgba(15, 23, 42, 0.6); stroke-width: 1.5; }
    .w { stroke: #64748b; stroke-width: 2; fill: none; }
    .wg { stroke: #34d399; stroke-width: 2.5; fill: none; }
    .wp { stroke: #c084fc; stroke-width: 2.5; fill: none; }
  </style>

  <rect width="1150" height="760" rx="16" fill="url(#bg3)" stroke="#334155" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">EXECUTION MODES: STEP MODE vs. AUTO MODE</text>
    <text class="st" x="0" y="44">Comparison of Granular Step-by-Step Approval vs. Upfront Plan Approval &amp; Tool Cap</text>
  </g>

  <!-- Left Column: STEP MODE -->
  <rect class="col-bg" x="40" y="80" width="510" height="640" stroke="#059669"/>
  <text class="ht" x="65" y="115" fill="#34d399">STEP MODE (auto_mode = False)</text>
  <text class="ns" x="65" y="135" fill="#94a3b8">Interactive oversight: human confirms every single side-effecting action</text>

  <g transform="translate(65, 160)">
    <rect class="box" width="460" height="60" fill="#064e3b" stroke="#10b981"/>
    <text class="nt" x="15" y="24">1. Direct Execution Request</text>
    <text class="ns" x="15" y="42">User request added to messages; run_agent() called directly</text>
  </g>

  <g transform="translate(65, 250)">
    <rect class="box" width="460" height="85" fill="#1e293b" stroke="#34d399"/>
    <text class="nt" x="15" y="22">2. ReAct Loop with Granular Gates</text>
    <text class="ns" x="15" y="40">• fs_tools.write_file() → calls confirm()</text>
    <text class="ns" x="15" y="56">• fs_tools.create_directory() → calls confirm()</text>
    <text class="ns" x="15" y="72">• shell_tools.run_command() → calls confirm()</text>
  </g>
  <path d="M 295 220 L 295 250" class="wg" marker-end="url(#ar3-grn)"/>

  <g transform="translate(65, 365)">
    <rect class="box" width="460" height="75" fill="#78350f" stroke="#fbbf24"/>
    <text class="nt" x="15" y="22">3. Terminal Interactive Prompt per Tool</text>
    <text class="ns" x="15" y="40">Prompt: "Proceed? (Y/n, Enter = yes)"</text>
    <text class="ns" x="15" y="56">Waits for human input (120s timeout, _stdin_lock protected)</text>
  </g>
  <path d="M 295 335 L 295 365" class="wg" marker-end="url(#ar3-grn)"/>

  <g transform="translate(65, 470)">
    <rect class="box" width="460" height="65" fill="#064e3b" stroke="#10b981"/>
    <text class="nt" x="15" y="22">4. Result Observation Fed Back</text>
    <text class="ns" x="15" y="40">If approved: tool executes and result returns to model</text>
    <text class="ns" x="15" y="56">If denied: "Cancelled by user" returned as tool observation</text>
  </g>
  <path d="M 295 440 L 295 470" class="wg" marker-end="url(#ar3-grn)"/>

  <g transform="translate(65, 565)">
    <rect class="box" width="460" height="65" fill="#1e293b" stroke="#64748b"/>
    <text class="nt" x="15" y="22">5. Final Answer</text>
    <text class="ns" x="15" y="40">Model concludes turn; prompt returned to user for next message</text>
  </g>
  <path d="M 295 535 L 295 565" class="wg" marker-end="url(#ar3-grn)"/>

  <!-- Right Column: AUTO MODE -->
  <rect class="col-bg" x="590" y="80" width="520" height="640" stroke="#7c3aed"/>
  <text class="ht" x="615" y="115" fill="#c084fc">AUTO MODE (auto_mode = True)</text>
  <text class="ns" x="615" y="135" fill="#94a3b8">Autonomous plan execution: approve once upfront, run up to 30 tool calls</text>

  <g transform="translate(615, 160)">
    <rect class="box" width="470" height="60" fill="#4c1d95" stroke="#a78bfa"/>
    <text class="nt" x="15" y="24">1. Plan Generation (tools=None)</text>
    <text class="ns" x="15" y="42">_generate_plan(): model proposes numbered steps with NO tools</text>
  </g>

  <g transform="translate(615, 240)">
    <rect class="box" width="470" height="65" fill="#312e81" stroke="#818cf8"/>
    <text class="nt" x="15" y="22">2. Write &amp; Review plan.md</text>
    <text class="ns" x="15" y="40">Writes plan.md to sandbox; prints full text to terminal</text>
    <text class="ns" x="15" y="56">One confirm(force_ask=True) gate for the ENTIRE plan</text>
  </g>
  <path d="M 850 220 L 850 240" class="wp" marker-end="url(#ar3-pur)"/>

  <g transform="translate(615, 325)">
    <rect class="box" width="470" height="65" fill="#581c87" stroke="#c084fc"/>
    <text class="nt" x="15" y="22">3. Set AUTO_MODE = True &amp; Execute</text>
    <text class="ns" x="15" y="40">shared.run_agent(..., max_tool_calls=30)</text>
    <text class="ns" x="15" y="56">Routine confirm() calls AUTO-APPROVE without prompt</text>
  </g>
  <path d="M 850 305 L 850 325" class="wp" marker-end="url(#ar3-pur)"/>

  <g transform="translate(615, 410)">
    <rect class="box" width="470" height="85" fill="#7c2d12" stroke="#f97316"/>
    <text class="nt" x="15" y="22">4. EXCEPTIONS: Hard Safety Interrupts</text>
    <text class="ns" x="15" y="40">STILL STOP &amp; FORCE PROMPT REGARDLESS OF PLAN:</text>
    <text class="ns" x="15" y="56">• Destructive commands (rm, sudo, curl) → force_ask=True</text>
    <text class="ns" x="15" y="72">• Compound operators (&amp;&amp;, ||, ;) → force_ask=True</text>
  </g>
  <path d="M 850 390 L 850 410" class="wp" marker-end="url(#ar3-pur)"/>

  <g transform="translate(615, 515)">
    <rect class="box" width="470" height="60" fill="#1e293b" stroke="#ec4899"/>
    <text class="nt" x="15" y="22">5. Hard Cap: 30 Tool Calls</text>
    <text class="ns" x="15" y="40">Halts wandering plans if total_tool_calls &gt; 30</text>
  </g>
  <path d="M 850 495 L 850 515" class="wp" marker-end="url(#ar3-pur)"/>

  <g transform="translate(615, 595)">
    <rect class="box" width="470" height="55" fill="#1e293b" stroke="#a855f7"/>
    <text class="nt" x="15" y="22">6. Reset Mode in finally Block</text>
    <text class="ns" x="15" y="40">agent_mode.AUTO_MODE = False (guaranteed return to step mode)</text>
  </g>
  <path d="M 850 575 L 850 595" class="wp" marker-end="url(#ar3-pur)"/>
</svg>"""
    (SVG_DIR / "auto_vs_step_mode.svg").write_text(svg3, encoding="utf-8")

    # 4. Backend SSE & Approval Bridge
    svg4 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1180 820" width="100%" height="100%">
  <defs>
    <linearGradient id="bg4" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#022c22"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
    <marker id="ar4" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#34d399"/></marker>
    <marker id="ar4-b" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#38bdf8"/></marker>
    <marker id="ar4-y" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#fbbf24"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .col-title { font-family: system-ui, sans-serif; font-weight: 700; font-size: 14px; fill: #34d399; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 12px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 10px; fill: #cbd5e1; }
    .wg { stroke: #34d399; stroke-width: 2; fill: none; }
    .wb { stroke: #38bdf8; stroke-width: 2; fill: none; }
    .wy { stroke: #fbbf24; stroke-width: 2; fill: none; }
    .lifeline { stroke: #334155; stroke-dasharray: 4 4; stroke-width: 2; }
  </style>

  <rect width="1180" height="820" rx="16" fill="url(#bg4)" stroke="#065f46" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">BACKEND CHAT &amp; ASYNC APPROVAL BRIDGE (FastAPI + SSE)</text>
    <text class="st" x="0" y="44">Sequence of Thread Handoff, Server-Sent Events, and HTTP Response Unblocking</text>
  </g>

  <!-- Lifeline Headers -->
  <g transform="translate(80, 80)">
    <rect class="box" width="180" height="45" fill="#064e3b" stroke="#10b981"/>
    <text class="col-title" x="25" y="28">Browser (chat.html)</text>
    <line x1="90" y1="45" x2="90" y2="700" class="lifeline"/>
  </g>

  <g transform="translate(360, 80)">
    <rect class="box" width="200" height="45" fill="#1e293b" stroke="#38bdf8"/>
    <text class="col-title" x="20" y="28" fill="#38bdf8">FastAPI (api/chat.py)</text>
    <line x1="100" y1="45" x2="100" y2="700" class="lifeline"/>
  </g>

  <g transform="translate(660, 80)">
    <rect class="box" width="220" height="45" fill="#1e1b4b" stroke="#a78bfa"/>
    <text class="col-title" x="15" y="28" fill="#a78bfa">ConversationTurn Thread</text>
    <line x1="110" y1="45" x2="110" y2="700" class="lifeline"/>
  </g>

  <g transform="translate(960, 80)">
    <rect class="box" width="160" height="45" fill="#78350f" stroke="#fbbf24"/>
    <text class="col-title" x="25" y="28" fill="#fbbf24">confirm.py Gate</text>
    <line x1="80" y1="45" x2="80" y2="700" class="lifeline"/>
  </g>

  <!-- Step 1: POST /stream -->
  <g transform="translate(170, 160)">
    <line x1="0" y1="0" x2="290" y2="0" class="wb" marker-end="url(#ar4-b)"/>
    <text class="nt" x="15" y="-8">1. fetch("POST /api/chat/stream", body={message})</text>
  </g>

  <!-- Step 2: Spawn Background Turn -->
  <g transform="translate(460, 200)">
    <line x1="0" y1="0" x2="310" y2="0" class="wg" marker-end="url(#ar4)"/>
    <text class="nt" x="15" y="-8">2. turn.start() → Thread runs run_agent()</text>
    <text class="ns" x="15" y="14">Installs set_confirm_backend(self._handle_confirm)</text>
  </g>

  <!-- Step 3: SSE Connection Established -->
  <g transform="translate(460, 240)">
    <line x1="0" y1="0" x2="-290" y2="0" class="wg" marker-end="url(#ar4)"/>
    <text class="nt" x="-260" y="-8">3. Returns StreamingResponse(event_generator)</text>
  </g>

  <!-- Step 4: Stream Thoughts & Tool Calls -->
  <g transform="translate(770, 290)">
    <line x1="0" y1="0" x2="-310" y2="0" class="wg" marker-end="url(#ar4)"/>
    <text class="ns" x="-250" y="-8">_logger puts {"type": "thought"} &amp; {"type": "tool_call"}</text>
  </g>
  <g transform="translate(460, 310)">
    <line x1="0" y1="0" x2="-290" y2="0" class="wg" marker-end="url(#ar4)"/>
    <text class="ns" x="-260" y="-8">SSE yields `data: {"type": "tool_call", ...}\n\n`</text>
  </g>

  <!-- Step 5: Side-Effect hits confirm() -->
  <g transform="translate(770, 360)">
    <line x1="0" y1="0" x2="270" y2="0" class="wy" marker-end="url(#ar4-y)"/>
    <text class="nt" x="25" y="-8">4. Tool calls confirm(action)</text>
  </g>
  <g transform="translate(1040, 390)">
    <line x1="0" y1="0" x2="-270" y2="0" class="wy" marker-end="url(#ar4-y)"/>
    <text class="ns" x="-250" y="-8">_confirm_backend() → _handle_confirm()</text>
  </g>

  <!-- Step 6: approval_request SSE event & thread block -->
  <g transform="translate(770, 430)">
    <rect class="box" x="-30" y="-12" width="280" height="40" fill="#78350f" stroke="#fbbf24"/>
    <text class="nt" x="-20" y="8">5. BLOCKS on _pending_answer.get(120s)</text>
    <text class="ns" x="-20" y="22">events.put({"type": "approval_request", id, action})</text>
  </g>
  <g transform="translate(770, 490)">
    <line x1="0" y1="0" x2="-600" y2="0" class="wy" marker-end="url(#ar4-y)"/>
    <text class="nt" x="-500" y="-8">6. SSE pushes approval_request event to Browser UI</text>
  </g>

  <!-- Step 7: User Clicks Approve in Browser -->
  <g transform="translate(170, 540)">
    <line x1="0" y1="0" x2="290" y2="0" class="wb" marker-end="url(#ar4-b)"/>
    <text class="nt" x="15" y="-8">7. fetch("POST /api/chat/respond", {request_id, approved: true})</text>
  </g>

  <!-- Step 8: FastAPI Unblocks Thread -->
  <g transform="translate(460, 580)">
    <line x1="0" y1="0" x2="310" y2="0" class="wb" marker-end="url(#ar4-b)"/>
    <text class="nt" x="15" y="-8">8. turn.submit_answer(id, True) → _pending_answer.put(True)</text>
  </g>

  <!-- Step 9: Worker Thread Resumes & Finishes -->
  <g transform="translate(770, 620)">
    <line x1="0" y1="0" x2="270" y2="0" class="wg" marker-end="url(#ar4)"/>
    <text class="nt" x="25" y="-8">9. _handle_confirm returns True to tool</text>
  </g>
  <g transform="translate(770, 660)">
    <line x1="0" y1="0" x2="-600" y2="0" class="wg" marker-end="url(#ar4)"/>
    <text class="nt" x="-500" y="-8">10. events.put({"type": "final"}) &amp; {"type": "stream_end"}</text>
  </g>
</svg>"""
    (SVG_DIR / "backend_sse_approval_flow.svg").write_text(svg4, encoding="utf-8")

    # 5. ReAct Tool Loop
    svg5 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 840" width="100%" height="100%">
  <defs>
    <linearGradient id="bg5" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1e1b4b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
    <marker id="ar5" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#a78bfa"/></marker>
    <marker id="ar5-r" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#f87171"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .wp { stroke: #a78bfa; stroke-width: 2.5; fill: none; }
    .wr { stroke: #f87171; stroke-width: 2.5; fill: none; }
    .diamond { stroke-width: 1.5; }
  </style>

  <rect width="1100" height="840" rx="16" fill="url(#bg5)" stroke="#6d28d9" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">REACT TOOL-CALLING LOOP &amp; STUCK DETECTION (shared.run_agent)</text>
    <text class="st" x="0" y="44">Argument Validation, SHA-256 Signature Hashing, Cycle Periods (1..3), Timeout &amp; Observation Capping</text>
  </g>

  <!-- Step 1: Start -->
  <g transform="translate(380, 80)">
    <rect class="box" width="340" height="55" fill="#4c1d95" stroke="#a78bfa"/>
    <text class="nt" x="15" y="22">1. Enter Loop: for round in range(MAX_ITERATIONS)</text>
    <text class="ns" x="15" y="40">Checks MAX_WALL_SECONDS (600s ceiling)</text>
  </g>

  <!-- Step 2: Ollama Chat -->
  <g transform="translate(380, 165)">
    <rect class="box" width="340" height="55" fill="#1e293b" stroke="#818cf8"/>
    <text class="nt" x="15" y="22">2. response = agent.chat(messages, tools)</text>
    <text class="ns" x="15" y="40">Retries up to 2x with backoff on failure</text>
  </g>
  <path d="M 550 135 L 550 165" class="wp" marker-end="url(#ar5)"/>

  <!-- Step 3: Tool Call Decision -->
  <g transform="translate(450, 250)">
    <polygon points="100,0 200,40 100,80 0,40" fill="#312e81" stroke="#a78bfa" class="diamond"/>
    <text class="nt" x="35" y="44">Any tool_calls?</text>
  </g>
  <path d="M 550 220 L 550 250" class="wp" marker-end="url(#ar5)"/>

  <!-- Final Answer Branch -->
  <g transform="translate(800, 260)">
    <rect class="box" width="250" height="60" fill="#065f46" stroke="#34d399"/>
    <text class="nt" x="15" y="24">Final Answer Reached</text>
    <text class="ns" x="15" y="42">Returns response.message.content</text>
  </g>
  <path d="M 650 290 L 800 290" class="wp" marker-end="url(#ar5)"/>
  <text class="ns" x="700" y="280" fill="#34d399">NO (Done)</text>

  <!-- Step 4: Tool Execution Steps -->
  <g transform="translate(350, 360)">
    <rect class="box" width="400" height="60" fill="#1e1b4b" stroke="#c084fc"/>
    <text class="nt" x="15" y="22">3. Parse &amp; Validate Tool Arguments</text>
    <text class="ns" x="15" y="40">_parse_arguments(JSON) + _validate_arguments(inspect.signature)</text>
  </g>
  <path d="M 550 330 L 550 360" class="wp" marker-end="url(#ar5)"/>
  <text class="ns" x="560" y="348" fill="#cbd5e1">YES</text>

  <!-- Step 5: Cycle & Stuck Detection -->
  <g transform="translate(350, 450)">
    <rect class="box" width="400" height="75" fill="#78350f" stroke="#fbbf24"/>
    <text class="nt" x="15" y="22">4. Signature Hashing &amp; Cycle Detection</text>
    <text class="ns" x="15" y="40">sig = _call_signature(name, args) (SHA-256)</text>
    <text class="ns" x="15" y="56">_detect_cycle(period=1..3, repeats=3) → Catches A,B,A,B oscillation</text>
  </g>
  <path d="M 550 420 L 550 450" class="wp" marker-end="url(#ar5)"/>

  <!-- Stuck Break Path -->
  <g transform="translate(800, 455)">
    <rect class="box" width="250" height="65" fill="#7f1d1d" stroke="#ef4444"/>
    <text class="nt" x="15" y="22">Halt Stuck Agent</text>
    <text class="ns" x="15" y="40">Returns "(stopped: repeating pattern)"</text>
    <text class="ns" x="15" y="54">chat_logger.error("stuck_loop")</text>
  </g>
  <path d="M 750 485 L 800 485" class="wr" marker-end="url(#ar5-r)"/>
  <text class="ns" x="755" y="475" fill="#f87171">IS STUCK</text>

  <!-- Step 6: Tool Execution with Timeout -->
  <g transform="translate(350, 555)">
    <rect class="box" width="400" height="70" fill="#581c87" stroke="#e879f9"/>
    <text class="nt" x="15" y="22">5. _run_tool_with_timeout(func, args, 30s)</text>
    <text class="ns" x="15" y="40">Runs in ThreadPoolExecutor worker thread</text>
    <text class="ns" x="15" y="56">Exceptions caught as data (never crash loop)</text>
  </g>
  <path d="M 550 525 L 550 555" class="wp" marker-end="url(#ar5)"/>

  <!-- Step 7: Sanitize & Append -->
  <g transform="translate(350, 655)">
    <rect class="box" width="400" height="65" fill="#1e293b" stroke="#38bdf8"/>
    <text class="nt" x="15" y="22">6. Sanitize &amp; Add Observation</text>
    <text class="ns" x="15" y="40">_sanitize_for_model(4000 char max limit)</text>
    <text class="ns" x="15" y="56">messages.append({"role": "tool", "content": result})</text>
  </g>
  <path d="M 550 625 L 550 655" class="wp" marker-end="url(#ar5)"/>

  <!-- Feedback wire to top -->
  <path d="M 350 685 L 180 685 L 180 110 L 380 110" class="wp" marker-end="url(#ar5)"/>
  <text class="ns" x="195" y="400" fill="#a78bfa">Next Round with Tool Observation</text>
</svg>"""
    (SVG_DIR / "react_tool_loop.svg").write_text(svg5, encoding="utf-8")

    # 6. Filesystem Sandbox Gate
    svg6 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 760" width="100%" height="100%">
  <defs>
    <linearGradient id="bg6" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#042f2e"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
    <marker id="ar6" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#2dd4bf"/></marker>
    <marker id="ar6-r" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#f87171"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .wt { stroke: #2dd4bf; stroke-width: 2.5; fill: none; }
    .wr { stroke: #f87171; stroke-width: 2.5; fill: none; }
  </style>

  <rect width="1100" height="760" rx="16" fill="url(#bg6)" stroke="#0d9488" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">FILESYSTEM SANDBOX CHOKE POINT (fs_tools.resolve_path)</text>
    <text class="st" x="0" y="44">Single Security Choke Point for list_dir, read_file, write_file, create_dir</text>
  </g>

  <!-- Input -->
  <g transform="translate(380, 80)">
    <rect class="box" width="340" height="50" fill="#134e4a" stroke="#2dd4bf"/>
    <text class="nt" x="15" y="22">Input: raw path string (e.g. "todo/app.py")</text>
    <text class="ns" x="15" y="38">Originates from model tool call</text>
  </g>

  <!-- Step 1: Control Chars -->
  <g transform="translate(380, 160)">
    <rect class="box" width="340" height="60" fill="#1e293b" stroke="#14b8a6"/>
    <text class="nt" x="15" y="22">1. Control Character &amp; Null Byte Check</text>
    <text class="ns" x="15" y="40">Rejects ord(ch) &lt; 0x20 or ch == 0x7f (prevents NUL smuggling)</text>
  </g>
  <path d="M 550 130 L 550 160" class="wt" marker-end="url(#ar6)"/>

  <!-- Step 2: Unicode Normalization -->
  <g transform="translate(380, 250)">
    <rect class="box" width="340" height="60" fill="#1e293b" stroke="#14b8a6"/>
    <text class="nt" x="15" y="22">2. Unicode NFKC Normalization</text>
    <text class="ns" x="15" y="40">Collapses fullwidth/homoglyphs (e.g. ．．／ → ../)</text>
  </g>
  <path d="M 550 220 L 550 250" class="wt" marker-end="url(#ar6)"/>

  <!-- Step 3: Windows Reserved Names -->
  <g transform="translate(380, 340)">
    <rect class="box" width="340" height="60" fill="#1e293b" stroke="#14b8a6"/>
    <text class="nt" x="15" y="22">3. Reserved Device Name Check</text>
    <text class="ns" x="15" y="40">Checks each segment for CON, PRN, AUX, NUL, COM1-9, LPT1-9</text>
  </g>
  <path d="M 550 310 L 550 340" class="wt" marker-end="url(#ar6)"/>

  <!-- Step 4: Containment Check -->
  <g transform="translate(380, 430)">
    <rect class="box" width="340" height="65" fill="#115e59" stroke="#5eead4"/>
    <text class="nt" x="15" y="22">4. Sandbox Containment Check</text>
    <text class="ns" x="15" y="40">candidate = (BASE_DIR / path).resolve()</text>
    <text class="ns" x="15" y="54">candidate.is_relative_to(BASE_DIR) (not prefix check)</text>
  </g>
  <path d="M 550 400 L 550 430" class="wt" marker-end="url(#ar6)"/>

  <!-- Step 5: Symlink Rejection -->
  <g transform="translate(380, 525)">
    <rect class="box" width="340" height="60" fill="#1e293b" stroke="#14b8a6"/>
    <text class="nt" x="15" y="22">5. Symlink Rejection (TOCTOU Defense)</text>
    <text class="ns" x="15" y="40">Rejects raw_path.is_symlink() before file open</text>
  </g>
  <path d="M 550 495 L 550 525" class="wt" marker-end="url(#ar6)"/>

  <!-- Output Safe Path -->
  <g transform="translate(380, 620)">
    <rect class="box" width="340" height="65" fill="#047857" stroke="#34d399"/>
    <text class="nt" x="15" y="24">Safe Path Returned to Tool</text>
    <text class="ns" x="15" y="42">Guaranteed inside workspace/ sandbox</text>
  </g>
  <path d="M 550 585 L 550 620" class="wt" marker-end="url(#ar6)"/>

  <!-- Rejection Box on Right -->
  <g transform="translate(780, 340)">
    <rect class="box" width="260" height="100" fill="#7f1d1d" stroke="#ef4444"/>
    <text class="nt" x="15" y="24">Raise ValueError &amp; Log</text>
    <text class="ns" x="15" y="44">Logs specific warning reason</text>
    <text class="ns" x="15" y="60">Fed back as tool error to model</text>
    <text class="ns" x="15" y="76">Never crashes agent process</text>
  </g>
  <path d="M 720 190 L 780 190" class="wr" marker-end="url(#ar6-r)"/>
  <path d="M 720 280 L 780 280" class="wr" marker-end="url(#ar6-r)"/>
  <path d="M 720 370 L 780 370" class="wr" marker-end="url(#ar6-r)"/>
  <path d="M 720 460 L 780 460" class="wr" marker-end="url(#ar6-r)"/>
  <path d="M 720 555 L 780 555" class="wr" marker-end="url(#ar6-r)"/>
</svg>"""
    (SVG_DIR / "filesystem_sandbox_gate.svg").write_text(svg6, encoding="utf-8")

    # 7. Shell 4-Layer Defense Gate
    svg7 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1150 780" width="100%" height="100%">
  <defs>
    <linearGradient id="bg7" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#451a03"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
    <marker id="ar7" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#f59e0b"/></marker>
    <marker id="ar7-r" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#ef4444"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .wy { stroke: #f59e0b; stroke-width: 2.5; fill: none; }
    .wr { stroke: #ef4444; stroke-width: 2.5; fill: none; }
  </style>

  <rect width="1150" height="780" rx="16" fill="url(#bg7)" stroke="#b45309" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">SHELL TOOLS 4-LAYER DEFENSE GATE (shell_tools.run_command)</text>
    <text class="st" x="0" y="44">Allowlist, Blocklist/Compound Detection, Human Confirmation &amp; Subprocess Group Isolation</text>
  </g>

  <!-- Input -->
  <g transform="translate(380, 80)">
    <rect class="box" width="380" height="50" fill="#78350f" stroke="#fbbf24"/>
    <text class="nt" x="15" y="22">Command Input: run_command(command)</text>
    <text class="ns" x="15" y="38">e.g. "python3 -m pytest tests/" or "rm -rf /"</text>
  </g>

  <!-- Layer 1 -->
  <g transform="translate(380, 160)">
    <rect class="box" width="380" height="70" fill="#1e293b" stroke="#f59e0b"/>
    <text class="nt" x="15" y="22">Layer 1: Program Allowlist</text>
    <text class="ns" x="15" y="40">first_token = shlex.split(command)[0].split("/")[-1]</text>
    <text class="ns" x="15" y="56">Must be in SHELL_ALLOWED: python, node, pytest, ls, etc.</text>
  </g>
  <path d="M 570 130 L 570 160" class="wy" marker-end="url(#ar7)"/>

  <!-- Layer 2 -->
  <g transform="translate(380, 260)">
    <rect class="box" width="380" height="85" fill="#1e293b" stroke="#f59e0b"/>
    <text class="nt" x="15" y="22">Layer 2: Dangerous Substrings &amp; Compound Operators</text>
    <text class="ns" x="15" y="40">BLOCKED: "rm ", "sudo", "curl", "wget", "chmod", etc.</text>
    <text class="ns" x="15" y="56">COMPOUND: "&amp;&amp;", "||", ";", "|", "&amp;", "$(", "`"</text>
    <text class="ns" x="15" y="72">Triggers confirm(force_ask=True) (interrupts auto mode!)</text>
  </g>
  <path d="M 570 230 L 570 260" class="wy" marker-end="url(#ar7)"/>

  <!-- Layer 3 -->
  <g transform="translate(380, 375)">
    <rect class="box" width="380" height="75" fill="#7c2d12" stroke="#f97316"/>
    <text class="nt" x="15" y="22">Layer 3: Human Confirmation Gate</text>
    <text class="ns" x="15" y="40">Clean command in Step Mode → confirm("run: {command}")</text>
    <text class="ns" x="15" y="56">Flagged in Layer 2 → confirm(force_ask=True)</text>
  </g>
  <path d="M 570 345 L 570 375" class="wy" marker-end="url(#ar7)"/>

  <!-- Layer 4 -->
  <g transform="translate(380, 480)">
    <rect class="box" width="380" height="100" fill="#1e293b" stroke="#ea580c"/>
    <text class="nt" x="15" y="22">Layer 4: Execution &amp; Process Group Isolation</text>
    <text class="ns" x="15" y="40">Popen(command, cwd=BASE_DIR, start_new_session=True)</text>
    <text class="ns" x="15" y="56">communicate(timeout=SHELL_TIMEOUT_SECONDS)</text>
    <text class="ns" x="15" y="72">On Timeout: os.killpg(os.getpgid(pid), SIGKILL) kills whole group</text>
    <text class="ns" x="15" y="88">Drains partial output, no orphaned child daemon left behind</text>
  </g>
  <path d="M 570 450 L 570 480" class="wy" marker-end="url(#ar7)"/>

  <!-- Formatting Output -->
  <g transform="translate(380, 610)">
    <rect class="box" width="380" height="65" fill="#065f46" stroke="#34d399"/>
    <text class="nt" x="15" y="22">5. Triple Stream Formatting (_format_result)</text>
    <text class="ns" x="15" y="40">Outputs exit_code, stdout (capped), stderr (capped)</text>
    <text class="ns" x="15" y="56">Independent truncation prevents stdout drowning out stderr</text>
  </g>
  <path d="M 570 580 L 570 610" class="wy" marker-end="url(#ar7)"/>

  <!-- Blocked Side-Box -->
  <g transform="translate(810, 260)">
    <rect class="box" width="280" height="90" fill="#7f1d1d" stroke="#ef4444"/>
    <text class="nt" x="15" y="24">Blocked / Denied</text>
    <text class="ns" x="15" y="44">Returns string observation to model</text>
    <text class="ns" x="15" y="60">"Blocked: ... is not in allowlist"</text>
    <text class="ns" x="15" y="76">"Command cancelled by user"</text>
  </g>
  <path d="M 760 195 L 810 195" class="wr" marker-end="url(#ar7-r)"/>
  <path d="M 760 300 L 810 300" class="wr" marker-end="url(#ar7-r)"/>
  <path d="M 760 410 L 810 410" class="wr" marker-end="url(#ar7-r)"/>
</svg>"""
    (SVG_DIR / "shell_4layer_defense.svg").write_text(svg7, encoding="utf-8")

    # 8. Confirmation Gate Concurrency
    svg8 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 760" width="100%" height="100%">
  <defs>
    <linearGradient id="bg8" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1e1b4b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
    <marker id="ar8" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#fbbf24"/></marker>
    <marker id="ar8-r" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#f87171"/></marker>
    <marker id="ar8-g" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#4ade80"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .wy { stroke: #fbbf24; stroke-width: 2.5; fill: none; }
    .wr { stroke: #f87171; stroke-width: 2.5; fill: none; }
    .wg { stroke: #4ade80; stroke-width: 2.5; fill: none; }
  </style>

  <rect width="1100" height="760" rx="16" fill="url(#bg8)" stroke="#d97706" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">HUMAN CONFIRMATION GATE &amp; STDIN CONCURRENCY (confirm.py)</text>
    <text class="st" x="0" y="44">Fail-Closed Philosophy, Pluggable Backends, Stdin Thread Races &amp; Orphan Protection</text>
  </g>

  <!-- Step 1: Entry & Sanitize -->
  <g transform="translate(380, 80)">
    <rect class="box" width="350" height="60" fill="#78350f" stroke="#fbbf24"/>
    <text class="nt" x="15" y="22">confirm(action, timeout_seconds=120, force_ask)</text>
    <text class="ns" x="15" y="40">Sanitize action: _ANSI_ESCAPE.sub("", action) + length cap</text>
  </g>

  <!-- Step 2: Auto mode check -->
  <g transform="translate(380, 165)">
    <rect class="box" width="350" height="50" fill="#1e293b" stroke="#a78bfa"/>
    <text class="nt" x="15" y="22">Auto Mode Check</text>
    <text class="ns" x="15" y="38">if agent_mode.AUTO_MODE and not force_ask: return True</text>
  </g>
  <path d="M 555 140 L 555 165" class="wy" marker-end="url(#ar8)"/>

  <!-- Step 3: Backend check -->
  <g transform="translate(380, 240)">
    <rect class="box" width="350" height="50" fill="#1e293b" stroke="#34d399"/>
    <text class="nt" x="15" y="22">Pluggable Backend Check</text>
    <text class="ns" x="15" y="38">if _confirm_backend is not None: return bool(_confirm_backend(...))</text>
  </g>
  <path d="M 555 215 L 555 240" class="wy" marker-end="url(#ar8)"/>

  <!-- Step 4: TTY check -->
  <g transform="translate(380, 315)">
    <rect class="box" width="350" height="50" fill="#1e293b" stroke="#f59e0b"/>
    <text class="nt" x="15" y="22">TTY Check (Headless / CI Guard)</text>
    <text class="ns" x="15" y="38">if not sys.stdin.isatty(): return False (Fail-Closed)</text>
  </g>
  <path d="M 555 290 L 555 315" class="wy" marker-end="url(#ar8)"/>

  <!-- Step 5: Stdin Lock -->
  <g transform="translate(380, 390)">
    <rect class="box" width="350" height="60" fill="#7c2d12" stroke="#ea580c"/>
    <text class="nt" x="15" y="22">Stdin Concurrency Lock</text>
    <text class="ns" x="15" y="40">_stdin_lock.acquire(blocking=False)</text>
    <text class="ns" x="15" y="54">If busy (orphaned prompt alive) → Deny immediately</text>
  </g>
  <path d="M 555 365 L 555 390" class="wy" marker-end="url(#ar8)"/>

  <!-- Step 6: Background Reader Thread -->
  <g transform="translate(380, 480)">
    <rect class="box" width="350" height="75" fill="#1e293b" stroke="#fbbf24"/>
    <text class="nt" x="15" y="22">_read_input_with_timeout(prompt, 120s)</text>
    <text class="ns" x="15" y="40">Spawns daemon Thread calling input(prompt)</text>
    <text class="ns" x="15" y="56">Main caller waits on queue.get(timeout=120s)</text>
    <text class="ns" x="15" y="70">Works in any thread (main thread or worker pool)</text>
  </g>
  <path d="M 555 450 L 555 480" class="wy" marker-end="url(#ar8)"/>

  <!-- Outcomes -->
  <g transform="translate(100, 600)">
    <rect class="box" width="280" height="90" fill="#7f1d1d" stroke="#ef4444"/>
    <text class="nt" x="15" y="22">ConfirmTimeout Path (120s)</text>
    <text class="ns" x="15" y="40">leave_lock_held = True</text>
    <text class="ns" x="15" y="56">Keeps _stdin_lock held to isolate</text>
    <text class="ns" x="15" y="70">abandoned reader thread. Returns False.</text>
  </g>

  <g transform="translate(420, 600)">
    <rect class="box" width="260" height="90" fill="#7f1d1d" stroke="#ef4444"/>
    <text class="nt" x="15" y="22">Denial / Error / Ctrl-C</text>
    <text class="ns" x="15" y="40">Releases _stdin_lock in finally</text>
    <text class="ns" x="15" y="56">Answer != 'y' or EOF or Ctrl-C</text>
    <text class="ns" x="15" y="70">Returns False.</text>
  </g>

  <g transform="translate(720, 600)">
    <rect class="box" width="280" height="90" fill="#065f46" stroke="#34d399"/>
    <text class="nt" x="15" y="22">Approved Path</text>
    <text class="ns" x="15" y="40">Releases _stdin_lock in finally</text>
    <text class="ns" x="15" y="56">Answer is '' (Enter) or 'y' / 'yes'</text>
    <text class="ns" x="15" y="70">Returns True.</text>
  </g>

  <path d="M 450 555 L 240 600" class="wr" marker-end="url(#ar8-r)"/>
  <path d="M 550 555 L 550 600" class="wr" marker-end="url(#ar8-r)"/>
  <path d="M 650 555 L 860 600" class="wg" marker-end="url(#ar8-g)"/>
</svg>"""
    (SVG_DIR / "confirm_gate_concurrency.svg").write_text(svg8, encoding="utf-8")

    # 9. Memory Atomic Persistence
    svg9 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 760" width="100%" height="100%">
  <defs>
    <linearGradient id="bg9" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1e1b4b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
    <marker id="ar9" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#c084fc"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .wp { stroke: #c084fc; stroke-width: 2.5; fill: none; }
  </style>

  <rect width="1100" height="760" rx="16" fill="url(#bg9)" stroke="#7c3aed" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">PERSISTENT MEMORY &amp; ATOMIC SWAP ENGINE (agent/memory.py)</text>
    <text class="st" x="0" y="44">Cross-Session Fact Persistence, Exit Summarization, Token Tracking &amp; .corrupt.bak Recovery</text>
  </g>

  <!-- Left: Operations -->
  <g transform="translate(60, 90)">
    <rect class="box" width="340" height="130" fill="#4c1d95" stroke="#a78bfa"/>
    <text class="nt" x="15" y="24">Model Tools (In-Session)</text>
    <text class="ns" x="15" y="44">• remember_fact(text, tags) → {id, fact, text, ts}</text>
    <text class="ns" x="15" y="62">• recall_memory(query, tags) → Case-insensitive search</text>
    <text class="ns" x="15" y="80">Capped at MEMORY_MAX_ENTRIES (500)</text>
    <text class="ns" x="15" y="98">Recall capped at 10 results</text>
  </g>

  <g transform="translate(60, 245)">
    <rect class="box" width="340" height="115" fill="#312e81" stroke="#818cf8"/>
    <text class="nt" x="15" y="24">Host CLI Operations (Exit / Crash)</text>
    <text class="ns" x="15" y="44">• save_session_summary(agent, msgs)</text>
    <text class="ns" x="15" y="60">  Summarizes last 40 msgs via agent.chat(tools=None)</text>
    <text class="ns" x="15" y="78">• save_token_usage(session_tokens)</text>
    <text class="ns" x="15" y="94">  Runs in finally block on EVERY exit path</text>
  </g>

  <!-- Middle: Load & Write Engine -->
  <g transform="translate(450, 90)">
    <rect class="box" width="310" height="130" fill="#1e293b" stroke="#a78bfa"/>
    <text class="nt" x="15" y="24">Robust Load Engine (_load_data)</text>
    <text class="ns" x="15" y="44">1. Reads PROJECT_ROOT / memory.json</text>
    <text class="ns" x="15" y="62">2. If JSON is Corrupt:</text>
    <text class="ns" x="15" y="80">   Writes memory.json.corrupt.bak for recovery</text>
    <text class="ns" x="15" y="98">   Falls back to {} instead of crashing</text>
  </g>

  <g transform="translate(450, 245)">
    <rect class="box" width="310" height="130" fill="#1e293b" stroke="#a78bfa"/>
    <text class="nt" x="15" y="24">Atomic Write Engine (_save_data)</text>
    <text class="ns" x="15" y="44">1. Writes to temporary file:</text>
    <text class="ns" x="15" y="62">   memory.json.tmp{os.getpid()}</text>
    <text class="ns" x="15" y="80">2. Atomic swap: os.replace(tmp, memory.json)</text>
    <text class="ns" x="15" y="98">3. Zero risk of half-written file corruption</text>
  </g>

  <!-- Right: Storage Layout -->
  <g transform="translate(800, 90)">
    <rect class="box" width="260" height="285" fill="#0f172a" stroke="#38bdf8"/>
    <text class="nt" x="15" y="24">memory.json Layout</text>
    <text class="ns" x="15" y="44" fill="#38bdf8">{</text>
    <text class="ns" x="25" y="62" fill="#93c5fd">"entries": [</text>
    <text class="ns" x="35" y="80" fill="#cbd5e1">{ "id": "a1b2c3d4",</text>
    <text class="ns" x="45" y="98" fill="#cbd5e1">"type": "fact",</text>
    <text class="ns" x="45" y="116" fill="#cbd5e1">"text": "...",</text>
    <text class="ns" x="45" y="134" fill="#cbd5e1">"tags": ["pref"],</text>
    <text class="ns" x="45" y="152" fill="#cbd5e1">"timestamp": "..." }</text>
    <text class="ns" x="25" y="172" fill="#93c5fd">],</text>
    <text class="ns" x="25" y="194" fill="#fbbf24">"token_usage_total": 48291</text>
    <text class="ns" x="15" y="214" fill="#38bdf8">}</text>
    <text class="ns" x="15" y="245" fill="#f87171">OUTSIDE workspace/ sandbox</text>
    <text class="ns" x="15" y="260" fill="#94a3b8">Model tools cannot overwrite file directly</text>
  </g>

  <!-- Bottom: Summary of Guarantees -->
  <g transform="translate(60, 420)">
    <rect class="box" width="1000" height="150" fill="#1e293b" stroke="#334155"/>
    <text class="nt" x="20" y="28">Security &amp; Operational Guarantees</text>
    <text class="ns" x="20" y="52">• Sandbox Isolation: memory.json sits at Project/memory.json, preventing model fs_tools from altering its own memory.</text>
    <text class="ns" x="20" y="72">• Summarizer Safety: save_session_summary calls agent.chat(tools=None), preventing the summarizer from executing actions.</text>
    <text class="ns" x="20" y="92">• Windowed Summary: Only the last 40 messages are summarized, preventing context overflow during automated exit.</text>
    <text class="ns" x="20" y="112">• Cumulative Tracking: Tokens accumulate across both CLI and Web sessions into a single shared counter.</text>
  </g>
</svg>"""
    (SVG_DIR / "memory_atomic_persistence.svg").write_text(svg9, encoding="utf-8")

    # 10. Config Drift Safe Engine
    svg10 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 760" width="100%" height="100%">
  <defs>
    <linearGradient id="bg10" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#064e3b"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
    <marker id="ar10" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#34d399"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .wg { stroke: #34d399; stroke-width: 2.5; fill: none; }
  </style>

  <rect width="1100" height="760" rx="16" fill="url(#bg10)" stroke="#059669" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">CONFIG MANAGEMENT &amp; DRIFT-SAFE DEFAULTS (BE/app/core/config_schema.py)</text>
    <text class="st" x="0" y="44">Unified Schema, Isolated Subprocess Default Extraction, .env Atomic Round-Tripping</text>
  </g>

  <!-- Left: GET /api/config -->
  <g transform="translate(60, 90)">
    <rect class="box" width="460" height="280" fill="#065f46" stroke="#10b981"/>
    <text class="nt" x="15" y="24">GET /api/config (Read Current &amp; Recommended)</text>
    <text class="ns" x="15" y="48">1. Reads active settings from agent/.env &amp; BE/.env</text>
    <text class="ns" x="15" y="70">2. Calls config_schema.agent_defaults():</text>
    <text class="ns" x="25" y="90">• Spawns isolated Python subprocess</text>
    <text class="ns" x="25" y="108">• Strips all agent-related environment variables</text>
    <text class="ns" x="25" y="126">• Neutralizes load_dotenv() in subprocess</text>
    <text class="ns" x="25" y="144">• Freshly imports agent_config &amp; log_config</text>
    <text class="ns" x="25" y="162">• Extracts genuine in-code defaults with zero manual drift</text>
    <text class="ns" x="15" y="190">3. Reads BE defaults from pydantic-settings model fields</text>
    <text class="ns" x="15" y="212">4. Caches agent defaults via @functools.lru_cache</text>
    <text class="ns" x="15" y="234">5. Returns {groups: [...fields, current_value, default_value]}</text>
  </g>

  <!-- Right: POST /api/config -->
  <g transform="translate(560, 90)">
    <rect class="box" width="480" height="280" fill="#1e293b" stroke="#38bdf8"/>
    <text class="nt" x="15" y="24">POST /api/config (Save Settings)</text>
    <text class="ns" x="15" y="48">1. Routes values to their respective config files:</text>
    <text class="ns" x="25" y="70">• Agent fields → written to agent/.env</text>
    <text class="ns" x="25" y="88">• BE_* fields → written to BE/.env</text>
    <text class="ns" x="15" y="115">2. Preserves Existing Comments &amp; Unknown Keys:</text>
    <text class="ns" x="25" y="135">• Non-destructive file update regex</text>
    <text class="ns" x="25" y="153">• Existing custom lines and comments are retained</text>
    <text class="ns" x="15" y="180">3. Escapes Multi-Line Values:</text>
    <text class="ns" x="25" y="200">• Double-quotes &amp; escapes SYSTEM_PROMPT newlines</text>
    <text class="ns" x="25" y="218">• Round-trips cleanly through python-dotenv on next boot</text>
    <text class="ns" x="15" y="245">4. Live: config_reload.reload_all() applies immediately (see next diagram) --</text>
    <text class="ns" x="25" y="263">only BE_HOST/PORT/CORS_ORIGINS still need a restart</text>
  </g>

  <!-- Models Dropdown API -->
  <g transform="translate(60, 400)">
    <rect class="box" width="980" height="150" fill="#1e293b" stroke="#fbbf24"/>
    <text class="nt" x="15" y="24">Model Discovery Endpoints (Parallel Fetch in Web UI)</text>
    <text class="ns" x="15" y="48">GET /api/models → Queries local Ollama daemon (ollama.Client().list()). Returns Local Models with specs (size, quantization, family) &amp; Cloud (in use).</text>
    <text class="ns" x="15" y="72">GET /api/models/catalog → Queries ollama.com/api/tags public cloud catalog (19 models). Includes OLLAMA_API_KEY Bearer auth if set.</text>
    <text class="ns" x="15" y="96">UI Dropdown: Clicking any model fills the Model field in the config editor. Errors in one endpoint degrade cleanly without breaking the other.</text>
  </g>
</svg>"""
    (SVG_DIR / "config_drift_safe_engine.svg").write_text(svg10, encoding="utf-8")

    # 11. Module Dependencies Tree
    svg11 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1150 820" width="100%" height="100%">
  <defs>
    <linearGradient id="bg11" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1e293b"/></linearGradient>
    <marker id="ar11" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#38bdf8"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .wb { stroke: #38bdf8; stroke-width: 2; fill: none; }
  </style>

  <rect width="1150" height="820" rx="16" fill="url(#bg11)" stroke="#334155" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">PROJECT DIRECTORY STRUCTURE &amp; MODULE IMPORT GRAPH</text>
    <text class="st" x="0" y="44">Physical Directory Layout, Module Roles, and Directional Dependency Flow</text>
  </g>

  <!-- Left: Tree layout -->
  <g transform="translate(60, 90)">
    <rect class="box" width="380" height="680" fill="#0f172a" stroke="#475569"/>
    <text class="nt" x="15" y="24">Directory Hierarchy</text>
    <text class="ns" x="15" y="50" fill="#38bdf8">Project/</text>
    <text class="ns" x="25" y="70" fill="#34d399">├── agent/           # Agent Engine</text>
    <text class="ns" x="35" y="88">│   ├── CLI_agent.py   # CLI entry point</text>
    <text class="ns" x="35" y="106">│   ├── shared.py      # OllamaAgent + run_agent</text>
    <text class="ns" x="35" y="124">│   ├── auto_runner.py # Auto mode plan-and-run</text>
    <text class="ns" x="35" y="142">│   ├── fs_tools.py    # 4 Sandboxed FS tools</text>
    <text class="ns" x="35" y="160">│   ├── shell_tools.py # 4-Layer shell execution</text>
    <text class="ns" x="35" y="178">│   ├── confirm.py     # Fail-closed approval gate</text>
    <text class="ns" x="35" y="196">│   ├── agent_mode.py  # AUTO_MODE global state</text>
    <text class="ns" x="35" y="214">│   ├── human_tools.py # Clarification tools</text>
    <text class="ns" x="35" y="232">│   ├── memory.py      # Persistent JSON memory</text>
    <text class="ns" x="35" y="250">│   ├── chat_logger.py # JSONL structured logger</text>
    <text class="ns" x="35" y="268">│   ├── log_config.py  # Logging configuration</text>
    <text class="ns" x="35" y="286">│   └── agent_config.py# Central settings &amp; env</text>
    <text class="ns" x="25" y="310" fill="#a78bfa">├── BE/              # Backend Service</text>
    <text class="ns" x="35" y="328">│   ├── app/main.py    # FastAPI application</text>
    <text class="ns" x="35" y="346">│   ├── app/api/       # chat, config, models, health, memory, ws, shutdown</text>
    <text class="ns" x="35" y="364">│   ├── app/core/      # approval, agent, tool bridges</text>
    <text class="ns" x="35" y="382">│   ├── app/static/    # chat.html, config.html</text>
    <text class="ns" x="35" y="400">│   └── nginx/         # nginx.conf reverse proxy</text>
    <text class="ns" x="25" y="424" fill="#fbbf24">├── workspace/       # Sandbox (BASE_DIR)</text>
    <text class="ns" x="25" y="444" fill="#f43f5e">├── tests/           # Pytest Suite (510 tests: 435 agent + 75 BE)</text>
    <text class="ns" x="25" y="464" fill="#94a3b8">├── logs/            # JSONL Session Logs</text>
    <text class="ns" x="25" y="484" fill="#94a3b8">├── doc/             # Documentation &amp; Audits</text>
    <text class="ns" x="25" y="504" fill="#38bdf8">└── memory.json      # Persistent Memory</text>
  </g>

  <!-- Right: Dependency Architecture Boxes -->
  <g transform="translate(480, 90)">
    <rect class="box" width="600" height="110" fill="#1e293b" stroke="#38bdf8"/>
    <text class="nt" x="15" y="24">Entry Layer</text>
    <text class="ns" x="15" y="44">CLI_agent.py (CLI Mode) | BE/app/main.py (FastAPI Web Mode)</text>
    <text class="ns" x="15" y="62">Both entry points consume identical core modules without duplication.</text>
    <text class="ns" x="15" y="80">BE bridges install pluggable callbacks into confirm.py &amp; human_tools.py.</text>
  </g>

  <g transform="translate(480, 220)">
    <rect class="box" width="600" height="130" fill="#1e293b" stroke="#a78bfa"/>
    <text class="nt" x="15" y="24">Core Engine &amp; ReAct Loop</text>
    <text class="ns" x="15" y="44">shared.py: OllamaAgent, run_agent(), cycle detection, timeouts</text>
    <text class="ns" x="15" y="62">auto_runner.py: Plan generation turn (tools=None) &amp; upfront confirm()</text>
    <text class="ns" x="15" y="80">agent_mode.py: Module-level global AUTO_MODE</text>
    <text class="ns" x="15" y="98">agent_config.py: Single source of truth for all limits, timeouts &amp; models</text>
  </g>

  <g transform="translate(480, 370)">
    <rect class="box" width="600" height="140" fill="#1e293b" stroke="#fbbf24"/>
    <text class="nt" x="15" y="24">Gate &amp; Pluggable Backend Layer</text>
    <text class="ns" x="15" y="44">confirm.py: confirm(), set_confirm_backend(), _stdin_lock</text>
    <text class="ns" x="15" y="62">human_tools.py: ask_human(), ask_human_choice(), set_human_backend()</text>
    <text class="ns" x="15" y="80">approval_bridge.py: ConversationTurn thread relaying SSE events &amp; queuing answers</text>
  </g>

  <g transform="translate(480, 530)">
    <rect class="box" width="600" height="120" fill="#1e293b" stroke="#ec4899"/>
    <text class="nt" x="15" y="24">9 Tools Suite &amp; Sandbox Enforcement</text>
    <text class="ns" x="15" y="44">fs_tools.py: list_directory, read_file, write_file, create_directory (via resolve_path)</text>
    <text class="ns" x="15" y="62">shell_tools.py: run_command (Allowlist, Blocklist, Process group kill)</text>
    <text class="ns" x="15" y="80">memory.py: remember_fact, recall_memory, save_session_summary, save_token_usage</text>
    <text class="ns" x="15" y="98">chat_logger.py: JSONL logging with secret masking &amp; rotation</text>
  </g>
</svg>"""
    (SVG_DIR / "module_dependencies.svg").write_text(svg11, encoding="utf-8")

    svg12 = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1150 900" width="100%" height="100%">
  <defs>
    <linearGradient id="bg12" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#451a03"/><stop offset="100%" stop-color="#0f172a"/></linearGradient>
    <marker id="ar12" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 8 5 L 0 9 z" fill="#f59e0b"/></marker>
  </defs>
  <style>
    .t { font-family: system-ui, sans-serif; font-weight: 800; font-size: 20px; fill: #f8fafc; }
    .st { font-family: system-ui, sans-serif; font-size: 13px; fill: #94a3b8; }
    .nt { font-family: system-ui, sans-serif; font-weight: 700; font-size: 13px; fill: #ffffff; }
    .ns { font-family: system-ui, sans-serif; font-size: 11px; fill: #cbd5e1; }
    .box { rx: 8; ry: 8; stroke-width: 1.5; }
    .wa { stroke: #f59e0b; stroke-width: 2.5; fill: none; }
  </style>

  <rect width="1150" height="900" rx="16" fill="url(#bg12)" stroke="#b45309" stroke-width="2"/>
  <g transform="translate(40, 24)">
    <text class="t" x="0" y="24">CONFIG HOT-RELOAD PROPAGATION (agent/config_reload.py)</text>
    <text class="st" x="0" y="44">Save Applies Immediately -- No Restart Required, Except Three Process-Startup-Bound BE Settings</text>
  </g>

  <g transform="translate(60, 80)">
    <rect class="box" width="1030" height="70" fill="#78350f" stroke="#f59e0b"/>
    <text class="nt" x="15" y="26">1. POST /api/config -- config_schema.save_values(request.values)</text>
    <text class="ns" x="15" y="48">Writes ONLY changed keys to agent/.env and/or BE/.env. An empty value REMOVES that key's line (falls back to code default) instead of writing KEY="".</text>
  </g>
  <path d="M 575 150 L 575 180" class="wa" marker-end="url(#ar12)"/>

  <g transform="translate(60, 180)">
    <rect class="box" width="1030" height="90" fill="#1e293b" stroke="#38bdf8"/>
    <text class="nt" x="15" y="26">2. If agent keys changed: config_reload.reload_all()</text>
    <text class="ns" x="15" y="48">load_dotenv(agent/.env, override=True) -- authoritative over whatever this process already loaded --</text>
    <text class="ns" x="15" y="66">then importlib.reload(agent_config), importlib.reload(log_config): re-executes both modules IN PLACE (same object identity).</text>
    <text class="ns" x="15" y="84">If BE keys changed: get_settings.cache_clear() -- every BE module already reads via a fresh get_settings() call, so this alone is the whole fix.</text>
  </g>
  <path d="M 575 270 L 575 300" class="wa" marker-end="url(#ar12)"/>

  <g transform="translate(60, 300)">
    <rect class="box" width="500" height="230" fill="#1e293b" stroke="#a78bfa"/>
    <text class="nt" x="15" y="24">3. Push into every consumer that copied a value by name</text>
    <text class="ns" x="15" y="46">`from agent_config import X` COPIES the value at import time --</text>
    <text class="ns" x="15" y="64">reassigning agent_config.X later never reaches that copy.</text>
    <text class="ns" x="15" y="88">setattr() on each already-imported module (sys.modules lookup,</text>
    <text class="ns" x="15" y="106">never a fresh import -- avoids circular-import ordering):</text>
    <text class="ns" x="25" y="128">shared, shell_tools (aliased names), confirm,</text>
    <text class="ns" x="25" y="146">auto_runner, fs_tools, memory</text>
    <text class="ns" x="15" y="172">Derived values recomputed from their source, not read</text>
    <text class="ns" x="15" y="190">from agent_config directly: fs_tools.BASE_DIR = WORKSPACE_DIR.resolve(),</text>
    <text class="ns" x="15" y="208">shell_tools.BASE_DIR, memory.MEMORY_PATH = Path(MEMORY_FILE)</text>
  </g>

  <g transform="translate(590, 300)">
    <rect class="box" width="500" height="230" fill="#1e293b" stroke="#34d399"/>
    <text class="nt" x="15" y="24">4. Same idea, one hop further: BE-side modules</text>
    <text class="ns" x="15" y="46">app.api.memory (MEMORY_FILE), app.core.approval_bridge</text>
    <text class="ns" x="15" y="64">(CONFIRM_TIMEOUT_SECONDS), app.core.agent_bridge AND</text>
    <text class="ns" x="15" y="82">app.api.chat -- chat.py copied agent_bridge's OWN copy of</text>
    <text class="ns" x="15" y="100">CHAT_SYSTEM_PROMPT again at ITS import time; missing this one</text>
    <text class="ns" x="15" y="118">meant Save updated the schema's answer but not what "New chat"</text>
    <text class="ns" x="15" y="136">actually seeded _messages with.</text>
    <text class="ns" x="15" y="162">OllamaAgent.model is an instance attribute set once at</text>
    <text class="ns" x="15" y="180">construction, not a module-level name -- a model change instead</text>
    <text class="ns" x="15" y="198">drops agent_bridge's cached singleton so the next chat request</text>
    <text class="ns" x="15" y="216">builds a fresh one.</text>
  </g>
  <path d="M 575 530 L 575 560" class="wa" marker-end="url(#ar12)"/>

  <g transform="translate(60, 560)">
    <rect class="box" width="1030" height="70" fill="#3f0f0f" stroke="#f43f5e"/>
    <text class="nt" x="15" y="26">Exception: BE_HOST / BE_PORT / BE_CORS_ORIGINS still need a real restart</text>
    <text class="ns" x="15" y="48">Bound to the process at startup -- the socket is already listening and CORS middleware already installed into the ASGI app by the time Save runs.</text>
  </g>

  <g transform="translate(60, 650)">
    <rect class="box" width="1030" height="200" fill="#1e293b" stroke="#fbbf24"/>
    <text class="nt" x="15" y="24">UNLIMITED_MODE -- same reload mechanism, one setting, many call sites</text>
    <text class="ns" x="15" y="46">Checked directly as a global at each site (not via that cap's own value), so flipping it always means "wait/run as long as it takes":</text>
    <text class="ns" x="25" y="68">shared.py -- run_agent()'s wall-clock check skipped; round loop uses itertools.count() instead of range(max_iterations)</text>
    <text class="ns" x="25" y="86">(checked as a body-level global on purpose -- max_iterations is a default-argument value, frozen at def time, so a reload can't change it retroactively)</text>
    <text class="ns" x="25" y="104">_effective_tool_timeout() returns None; CHAT_TIMEOUT_SECONDS / CHAT_STREAM_IDLE_TIMEOUT_SECONDS waits become unbounded</text>
    <text class="ns" x="25" y="122">shell_tools.py -- run_command's subprocess timeout removed</text>
    <text class="ns" x="25" y="140">confirm.py -- confirm() forces timeout_seconds=None regardless of the default or any explicit caller value</text>
    <text class="ns" x="25" y="158">auto_runner.py -- auto-mode's max_tool_calls becomes None (run_agent's own "no extra cap" sentinel)</text>
    <text class="ns" x="15" y="182">Deliberately does NOT touch MAX_REPEAT_CALLS (stuck-loop detection) -- a malfunction, never legitimate work.</text>
  </g>
</svg>"""
    (SVG_DIR / "config_hot_reload.svg").write_text(svg12, encoding="utf-8")

    print(f"Generated 12 standalone SVGs in {SVG_DIR}")

if __name__ == "__main__":
    write_svgs()
