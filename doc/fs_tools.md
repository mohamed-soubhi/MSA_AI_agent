# fs_tools.py

Sandboxed filesystem tools exposed to the agent as Ollama tool-calling
functions. All four public tools resolve every path against `BASE_DIR`
(a fixed `workspace/` folder at the project root — see below) and
refuse anything that would land outside it.

Docstrings on the tool functions are not just documentation — Ollama
builds each tool's JSON schema from the function signature and
docstring, and the model reads that description to decide when/how to
call it.

## Sandbox-escape fix (agent could read/edit its own source)

**Before**: `BASE_DIR = Path.cwd().resolve()` — the directory the
process happened to be launched from. This project's agent source
lived at the repo root and was normally launched from there too, so
`BASE_DIR` ended up *being* the repo root — meaning the sandbox let the
agent read and overwrite its own source files (`shared.py`,
`confirm.py`, `fs_tools.py`, ...) through the exact tools meant to
sandbox it.

**Fix**: the agent's source now lives in `agent/` (one level under the
project root), and `BASE_DIR = agent_config.WORKSPACE_DIR` — a fixed
`<project_root>/workspace/` folder, resolved from `agent_config.py`'s
own file location (`Path(__file__).resolve().parent.parent`), **not**
the process's working directory. Two consequences:
- It no longer matters which directory you launch the agent from — the
  sandbox root is always the same fixed folder.
- The agent's own source is structurally outside the sandbox — there is
  no path a model could construct that resolves back into `agent/`,
  the same way `../etc/passwd`-style traversal is already blocked.

`fs_tools.py` also creates `BASE_DIR` on import
(`BASE_DIR.mkdir(parents=True, exist_ok=True)`) so a first run never
fails because `workspace/` doesn't exist yet. Override the whole
sandbox location via the `WORKSPACE_DIR` environment variable
(`agent_config.py`).

## Module constants

| Name | Value | Purpose |
|---|---|---|
| `BASE_DIR` | `agent_config.WORKSPACE_DIR.resolve()` | Sandbox root — a fixed `<project_root>/workspace/` folder. All paths must resolve inside this. |
| `MAX_WRITE_BYTES` | `2_000_000` (2 MB) | Hard cap on a single `write_file()` call. Imported from [agent_config.py](agent_config.md), env `MAX_WRITE_BYTES`. |
| `REQUIRE_CONFIRMATION` | `True` | Gate `write_file`/`create_directory` behind `confirm()`. Set `False` only for unattended/batch runs (which `confirm()` denies anyway, absent a tty). Imported from [agent_config.py](agent_config.md), env `REQUIRE_CONFIRMATION`. |
| `_WINDOWS_RESERVED` | regex | Matches `CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9` (case-insensitive, with or without extension). |

## `resolve_path(path: str) -> Path`

The single choke point every tool goes through. Turns a relative path
into a validated absolute one inside `BASE_DIR`. Raises `ValueError` on
any violation.

Validation order:
1. Reject non-string / empty input.
2. Reject control characters and null bytes (`ord(ch) < 0x20` or DEL),
   before touching the filesystem — blocks smuggling tricks like
   `"ok.txt\x00.exe"`.
3. NFKC-normalize unicode *before* other checks, so homoglyph/fullwidth
   tricks (e.g. fullwidth `．．／` reading as `../`) collapse to plain
   ASCII first.
4. Check every path segment (not just the whole string) against
   `_WINDOWS_RESERVED` — matters for nested paths like `reports/con.txt`.
5. Join onto `BASE_DIR` and `.resolve()` (follows `..` and symlinks).
6. Containment check via `candidate.is_relative_to(BASE_DIR)` — **not**
   a string-prefix check, since `"BASE_DIR-evil/..."` would falsely pass
   a naive prefix test.
7. Explicit symlink rejection on the *unresolved* path (`raw_path.is_symlink()`)
   — defense in depth against TOCTOU: even if the resolved target is
   inside `BASE_DIR` right now, a symlink could be swapped later.

Every blocked attempt is logged via `logging.getLogger("agent.fs_tools")`.

## `create_directory(path: str) -> str`

Creates a folder (and missing parents) inside `BASE_DIR`. Idempotent —
safe to call on an existing folder. Confirmed via `confirm()` before
acting (if `REQUIRE_CONFIRMATION`). Returns a cancellation message
string (not an exception) if denied.

## `write_file(path: str, content: str) -> str`

Writes/overwrites a file's full text content. No append or partial-edit
mode — callers must `read_file()` first, edit locally, then write the
complete new version back.

- Refuses (returns a message, doesn't raise) if `len(content.encode("utf-8"))`
  exceeds `MAX_WRITE_BYTES` — checked **before** asking for confirmation.
- Confirmed via `confirm()` before writing.
- Creates missing parent directories automatically.

## `read_file(path: str) -> str`

Reads a file's full text content. Read-only — no confirmation required.

- Missing file → returns `"No such file: {path}"` (not an exception).
- Path is a directory → returns `"Not a file: {path}. Use list_directory..."`.

## `list_directory(path: str = ".") -> str`

Lists immediate children of a folder, one level deep only (does not
recurse). Read-only — no confirmation required.

- Entries sorted `(is_file, name.lower())` — directories first,
  alphabetically, then files, alphabetically.
- Each line formatted `"[dir] name"` or `"[file] name"`.
- Empty directory → `"'{path}' is empty."`
- Missing path → `"No such directory: {path}"`.
- Path is a file → `"Not a directory: {path}. Use read_file..."`.

## Test coverage (`tests/test_fs_tools.py`)

49 tests (`FS-001` .. `FS-035`). All tests run against an isolated `tmp_path`
monkeypatched onto `fs_tools.BASE_DIR`, with `confirm()` stubbed to auto-approve/deny.

- **`resolve_path`**: simple/nested/`"."` paths, non-string/empty input,
  control characters, `..` traversal (shallow and deep), absolute paths,
  every Windows reserved name (flat and nested), a non-reserved
  lookalike name (`console.txt`) correctly *not* blocked, fullwidth
  unicode traversal, symlink rejection, and a `BASE_DIR`-prefix-lookalike
  sibling directory confirming the containment check isn't a naive
  string-prefix test.
- **`create_directory`**: creation, nested parents, idempotency,
  cancellation on denial, and traversal errors raised *before*
  `confirm()` is ever called.
- **`write_file`**: writing, overwriting, parent-dir auto-creation,
  cancellation on denial, oversized-content refusal (confirmed to happen
  before the confirm prompt), and empty-content writes.
- **`read_file`**: existing file, missing file, directory-as-file,
  confirmed to never call `confirm()`.
- **`list_directory`**: file+dir listing, dir-before-file sort order,
  empty-dir message, default `"."` path, missing dir, file-as-directory,
  and non-recursion into subfolders.
