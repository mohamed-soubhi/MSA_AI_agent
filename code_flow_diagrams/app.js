// ==========================================================================
// Project Code Flow & Architecture Visualizer - Interactive Controller
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initPanZoom();
  initSimulator();
  initSearch();
  initTheme();
});

// 1. Tab Switching & Deep Linking
function initTabs() {
  const navItems = document.querySelectorAll('.nav-item');
  const tabContents = document.querySelectorAll('.tab-content');

  function activateTab(tabId) {
    if (!tabId) return;

    navItems.forEach(item => {
      if (item.dataset.tab === tabId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    tabContents.forEach(content => {
      if (content.id === tabId) {
        content.classList.add('active');
      } else {
        content.classList.remove('active');
      }
    });

    window.location.hash = tabId;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const tabId = item.dataset.tab;
      activateTab(tabId);
    });
  });

  // Handle URL hash on load
  const initialHash = window.location.hash.replace('#', '');
  if (initialHash && document.getElementById(initialHash)) {
    activateTab(initialHash);
  }
}

// 2. SVG Diagram Pan and Zoom Controller
function initPanZoom() {
  const containers = document.querySelectorAll('.diagram-container');

  containers.forEach(container => {
    const viewport = container.querySelector('.svg-viewport');
    if (!viewport) return;
    const targetElement = viewport.querySelector('svg, object, img');
    if (!targetElement) return;

    // "Open in new tab" -- generic across every diagram, reading
    // whichever attribute actually holds the file's own URL rather
    // than hardcoding a per-diagram link in index.html.
    const svgUrl = targetElement.getAttribute('data') || targetElement.getAttribute('src');
    const toolbar = container.querySelector('.diagram-toolbar');
    if (svgUrl && toolbar && !toolbar.querySelector('.btn-open-tab')) {
      const openBtn = document.createElement('a');
      openBtn.className = 'diagram-btn btn-open-tab';
      openBtn.href = svgUrl;
      openBtn.target = '_blank';
      openBtn.rel = 'noopener noreferrer';
      openBtn.title = 'Open in new tab';
      openBtn.textContent = '⇱';
      toolbar.appendChild(openBtn);
    }

    let scale = 1;
    let pointX = 0;
    let pointY = 0;
    let isPanning = false;
    let startX = 0;
    let startY = 0;

    function updateTransform() {
      targetElement.style.transform = `translate(${pointX}px, ${pointY}px) scale(${scale})`;
      targetElement.style.transformOrigin = 'center center';
    }

    // Zoom Buttons
    const btnIn = container.querySelector('.btn-zoom-in');
    const btnOut = container.querySelector('.btn-zoom-out');
    const btnReset = container.querySelector('.btn-zoom-reset');

    if (btnIn) {
      btnIn.addEventListener('click', () => {
        scale = Math.min(scale + 0.25, 3.5);
        updateTransform();
      });
    }

    if (btnOut) {
      btnOut.addEventListener('click', () => {
        scale = Math.max(scale - 0.25, 0.5);
        updateTransform();
      });
    }

    if (btnReset) {
      btnReset.addEventListener('click', () => {
        scale = 1;
        pointX = 0;
        pointY = 0;
        updateTransform();
      });
    }

    // Mouse Pan
    viewport.addEventListener('mousedown', (e) => {
      isPanning = true;
      startX = e.clientX - pointX;
      startY = e.clientY - pointY;
    });

    window.addEventListener('mousemove', (e) => {
      if (!isPanning) return;
      pointX = e.clientX - startX;
      pointY = e.clientY - startY;
      updateTransform();
    });

    window.addEventListener('mouseup', () => {
      isPanning = false;
    });

    // Wheel Zoom
    viewport.addEventListener('wheel', (e) => {
      e.preventDefault();
      const xs = (e.clientX - pointX) / scale;
      const ys = (e.clientY - pointY) / scale;
      const delta = e.deltaY < 0 ? 1.15 : 0.85;
      
      const newScale = Math.min(Math.max(scale * delta, 0.5), 3.5);
      pointX = e.clientX - xs * newScale;
      pointY = e.clientY - ys * newScale;
      scale = newScale;
      updateTransform();
    });
  });
}

// 3. Interactive Code Flow Simulator
const scenarios = {
  step_mode_file: {
    title: 'Scenario 1: Step-Mode File Creation (write_file)',
    steps: [
      {
        num: 'Step 1: User REPL Input',
        title: 'CLI Prompt Received',
        desc: 'User inputs "Create a hello.py file that prints hello world" in CLI_agent.py REPL. Logger records chat_logger.user_message().'
      },
      {
        num: 'Step 2: Model Tool Proposal',
        title: 'Ollama Proposes write_file',
        desc: "OllamaAgent calls model with tools list. Model emits tool call write_file(path='hello.py', content='print(\"hello world\")')."
      },
      {
        num: 'Step 3: Argument Validation & Signature Hashing',
        title: 'Loop & Cycle Guard Check',
        desc: '_validate_arguments() verifies path and content match fs_tools.write_file signature. _call_signature generates SHA-256 hash. _detect_cycle checks period=1..3 repetition.'
      },
      {
        num: 'Step 4: Path Resolution Choke Point',
        title: 'fs_tools.resolve_path Sandbox Check',
        desc: 'resolve_path("hello.py") checks: 1. No control chars, 2. Unicode NFKC normalize, 3. No Windows reserved names (CON/NUL), 4. candidate.is_relative_to(BASE_DIR), 5. is_symlink() is False. Returns safe Path.'
      },
      {
        num: 'Step 5: Human Confirmation Gate',
        title: 'confirm.py Interactive Prompt',
        desc: 'write_file checks REQUIRE_CONFIRMATION=True and invokes confirm("Write 22 bytes to: hello.py"). Stdin lock acquired, background daemon thread calls input(). User hits Enter (Yes).'
      },
      {
        num: 'Step 6: Disk Write & Observation Return',
        title: 'Sandbox I/O & Tool Result',
        desc: 'target.write_text() saves file to workspace/hello.py. Returns observation "Wrote 22 chars to hello.py" to run_agent() loop.'
      },
      {
        num: 'Step 7: Final Conclusion',
        title: 'Assistant Final Reply',
        desc: 'Model receives tool observation, determines task is finished, and emits final text "Created hello.py with the requested print statement."'
      }
    ]
  },
  auto_mode_run: {
    title: 'Scenario 2: Auto-Mode Plan & Run (30-Tool Cap)',
    steps: [
      {
        num: 'Step 1: Plan Generation (tools=None)',
        title: 'Plan Formulation Turn',
        desc: 'auto_mode=True invokes auto_runner._generate_plan(). Model is queried with tools=None so it cannot execute actions prematurely.'
      },
      {
        num: 'Step 2: Plan Artifact Written',
        title: 'Save & Display plan.md',
        desc: 'Plan text written to workspace/plan.md. Full plan displayed to user with numbered step breakdown.'
      },
      {
        num: 'Step 3: Single Upfront Confirmation',
        title: 'confirm(force_ask=True)',
        desc: 'confirm() prompts user once to approve the entire plan to completion. User enters "y".'
      },
      {
        num: 'Step 4: AUTO_MODE Enabled',
        title: 'agent_mode.AUTO_MODE = True',
        desc: 'AUTO_MODE flag is set to True. shared.run_agent() starts with max_tool_calls=30.'
      },
      {
        num: 'Step 5: Auto-Approved Tool Execution',
        title: 'confirm() Auto-Approves Routine Steps',
        desc: 'Subsequent write_file and create_directory calls hit confirm(), which checks agent_mode.AUTO_MODE and immediately returns True without pausing.'
      },
      {
        num: 'Step 6: Automatic Mode Teardown',
        title: 'finally: AUTO_MODE = False',
        desc: 'When the run finishes (or hits 30 tool cap), finally block guarantees AUTO_MODE resets to False.'
      }
    ]
  },
  web_sse_approval: {
    title: 'Scenario 3: Web Chat SSE & Remote HTTP Approval',
    steps: [
      {
        num: 'Step 1: Client POST /stream',
        title: 'fetch() Starts ReadableStream',
        desc: 'Browser chat.html sends POST /api/chat/stream. FastAPI acquires _turn_lock and spawns ConversationTurn on a daemon thread.'
      },
      {
        num: 'Step 2: Pluggable Backend Installation',
        title: 'set_confirm_backend(self._handle_confirm)',
        desc: 'ConversationTurn sets module-level callback hooks on confirm.py and human_tools.py. Starts shared.run_agent().'
      },
      {
        num: 'Step 3: SSE Event Streaming',
        title: '_EventForwardingLogger Relays Events',
        desc: 'Thoughts and tool calls are queued onto turn.events. StreamingResponse yields SSE events: thought, tool_call, tool_result.'
      },
      {
        num: 'Step 4: Approval Bridge Intercept',
        title: 'Thread Blocks on _pending_answer',
        desc: 'Tool calls confirm(). _handle_confirm pushes approval_request SSE event with UUID to browser and blocks on _pending_answer.get(timeout=120s).'
      },
      {
        num: 'Step 5: Client Action & HTTP Response',
        title: 'POST /api/chat/respond',
        desc: 'User clicks "Approve" in browser modal. Browser sends POST /api/chat/respond with request_id and approved=True.'
      },
      {
        num: 'Step 6: Worker Thread Resume & Finish',
        title: 'submit_answer() Unblocks Thread',
        desc: 'FastAPI puts True into _pending_answer queue. _handle_confirm returns True to tool. Loop completes and streams final answer.'
      }
    ]
  },
  blocked_shell: {
    title: 'Scenario 4: Dangerous Shell Command Defense',
    steps: [
      {
        num: 'Step 1: Model Proposes Dangerous Command',
        title: "run_command('rm -rf workspace/old')",
        desc: 'Model attempts to run a deletion command via shell_tools.run_command().'
      },
      {
        num: 'Step 2: Layer 1 Allowlist Check',
        title: 'shlex.split() First Token',
        desc: 'Extracts program "rm". Not in SHELL_ALLOWED -> Blocked immediately if standalone program.'
      },
      {
        num: 'Step 3: Layer 2 Substring & Compound Scan',
        title: 'SHELL_BLOCKED & _is_compound Check',
        desc: 'Detects "rm " in command string or compound operators (&&, ||, ;, `). Flags command as dangerous.'
      },
      {
        num: 'Step 4: Layer 3 Force-Ask Override',
        title: 'confirm(force_ask=True) Interruption',
        desc: 'Bypasses AUTO_MODE auto-approval! Halts execution and forces an explicit human confirmation prompt on terminal/web.'
      },
      {
        num: 'Step 5: Human Denial & Process Safety',
        title: 'Human Rejects Action',
        desc: 'User enters "n". run_command returns "Blocked: command contains a forbidden pattern and was not approved". Subprocess never spawns.'
      }
    ]
  }
};

let currentScenarioKey = 'step_mode_file';
let currentStepIndex = 0;

function initSimulator() {
  const buttons = document.querySelectorAll('.sim-scenario-btn');
  const prevBtn = document.getElementById('sim-prev');
  const nextBtn = document.getElementById('sim-next');

  function renderStep() {
    const sc = scenarios[currentScenarioKey];
    if (!sc) return;
    const step = sc.steps[currentStepIndex];
    if (!step) return;

    const titleEl = document.getElementById('sim-scenario-title');
    const numEl = document.getElementById('sim-step-num');
    const stepTitleEl = document.getElementById('sim-step-title');
    const descEl = document.getElementById('sim-step-desc');
    const progressEl = document.getElementById('sim-progress');

    if (titleEl) titleEl.textContent = sc.title;
    if (numEl) numEl.textContent = step.num;
    if (stepTitleEl) stepTitleEl.textContent = step.title;
    if (descEl) descEl.textContent = step.desc;
    if (progressEl) progressEl.textContent = `Step ${currentStepIndex + 1} of ${sc.steps.length}`;

    if (prevBtn) prevBtn.disabled = currentStepIndex === 0;
    if (nextBtn) nextBtn.disabled = currentStepIndex === sc.steps.length - 1;
  }

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentScenarioKey = btn.dataset.scenario;
      currentStepIndex = 0;
      renderStep();
    });
  });

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentStepIndex > 0) {
        currentStepIndex--;
        renderStep();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      const sc = scenarios[currentScenarioKey];
      if (sc && currentStepIndex < sc.steps.length - 1) {
        currentStepIndex++;
        renderStep();
      }
    });
  }

  renderStep();
}

// 4. Live Search Filter
function initSearch() {
  const searchInput = document.getElementById('global-search');
  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase().trim();
    if (!query) {
      document.querySelectorAll('.searchable').forEach(el => el.style.display = '');
      return;
    }

    document.querySelectorAll('.searchable').forEach(el => {
      const text = el.textContent.toLowerCase();
      if (text.includes(query)) {
        el.style.display = '';
      } else {
        el.style.display = 'none';
      }
    });
  });
}

// 5. Theme Toggle
function initTheme() {
  const themeBtn = document.getElementById('theme-toggle');
  if (!themeBtn) return;

  const savedTheme = localStorage.getItem('app-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  themeBtn.textContent = savedTheme === 'dark' ? '☀️ Light' : '🌙 Dark';

  themeBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('app-theme', next);
    themeBtn.textContent = next === 'dark' ? '☀️ Light' : '🌙 Dark';
  });
}
