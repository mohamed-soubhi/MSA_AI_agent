"""Sandboxed filesystem tools for a coding agent.

All four tools resolve every path against BASE_DIR (the directory the
process was started from) and refuse anything that would land outside
it -- absolute paths, "..", symlink escapes, all of it. The agent should
never need to know or care where BASE_DIR actually is on disk; from its
point of view, paths like "todo-app/style.css" are the whole world.

The docstrings below are not just documentation -- Ollama's tool-calling
builds each tool's JSON schema from the function signature and docstring,
and the model reads that description to decide when and how to call the
tool. A vague description ("reads a file") gets skipped or misused; a
precise one gets called correctly on the first try.

Hardening added on top of the original version:
  - resolve_path() rejects control characters and null bytes, not just ".."
    and absolute paths, and logs every blocked attempt (a repeated
    escape attempt from the model is a signal worth knowing about).
  - write_file() enforces a maximum content size, so a runaway agent
    can't fill the disk with one call.
  - write_file() and create_directory() -- the two side-effecting tools
    -- ask for human confirmation before acting, via the confirm()
    gate. read_file() and list_directory() are read-only and stay
    unconfirmed, since gating every read would make the agent unusable.
"""

import logging
import re
import unicodedata
from pathlib import Path

from confirm import confirm
from agent_config import MAX_WRITE_BYTES, REQUIRE_CONFIRMATION

logger = logging.getLogger("agent.fs_tools")

BASE_DIR = Path.cwd().resolve()

# MAX_WRITE_BYTES and REQUIRE_CONFIRMATION now live in agent_config.py —
# see that file to tune or override either via environment variable.

# Reserved device names on Windows that are dangerous even inside a
# sandboxed path (CON, PRN, AUX, NUL, COM1-9, LPT1-9). Harmless on
# Linux, cheap to block -- relevant if this workspace or its backups
# ever get mounted/copied to a Windows host. Checked per path SEGMENT
# (not the whole string), since resolve_path supports nested paths like
# "todo-app/style.css" and any single segment could be a reserved name.
_WINDOWS_RESERVED = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.[^.]*)?$", re.IGNORECASE
)


def resolve_path(path: str) -> Path:
    """Turn a relative path into an absolute one, enforcing the sandbox.

    Joins `path` onto BASE_DIR and resolves any ".." or symlinks, then
    checks the result is still inside BASE_DIR. Raises ValueError if not.
    This is the single choke point all four public tools call through,
    so the sandbox rule only has to be correct in one place.

    Public (no leading underscore) on purpose: other modules that need
    the same "stay inside BASE_DIR" guarantee -- e.g. a future tool that
    isn't one of the four below -- should import and reuse THIS
    function rather than reimplementing the check elsewhere. One
    correct sandbox implementation beats several similar ones drifting
    apart over time.

    This absorbs the protections from the standalone safe_path.py guard
    (unicode normalization, symlink rejection, Windows reserved names),
    adapted to work on nested paths -- safe_path's original allowlist
    regex only validated a single flat filename and would have broken
    "todo-app/style.css"-style paths, which this project needs.
    """
    # Reject control characters and null bytes before touching the
    # filesystem at all -- these can smuggle a different path/extension
    # past a naive check on some platforms (e.g. "ok.txt\x00.exe").
    if not isinstance(path, str) or not path:
        raise ValueError("Path must be a non-empty string.")
    if any(ord(ch) < 0x20 or ch == "\x7f" for ch in path):
        logger.warning("fs_blocked_control_chars path=%r", path)
        raise ValueError(f"Path '{path}' contains control characters and is not allowed.")

    # Normalize unicode BEFORE any other validation, so homoglyph or
    # fullwidth tricks (e.g. fullwidth "．．／", which visually reads as
    # "../") get collapsed to their plain-ASCII equivalent first, rather
    # than sneaking past the checks below in disguise.
    path = unicodedata.normalize("NFKC", path)

    # Check every path segment against Windows reserved device names.
    # E.g. "reports/con.txt" or "con/data.txt" -- either position matters.
    for segment in Path(path).parts:
        stem = segment.split(".", 1)[0]
        if _WINDOWS_RESERVED.match(stem):
            logger.warning("fs_blocked_reserved_name path=%r segment=%r", path, segment)
            raise ValueError(f"Path '{path}' contains a reserved device name ('{segment}').")

    candidate = (BASE_DIR / path).resolve()

    # is_relative_to(), not a string prefix check -- a prefix check
    # would let "BASE_DIR-evil/..." slip past because the *string*
    # "BASE_DIR" is a prefix of "BASE_DIR-evil".
    if not candidate.is_relative_to(BASE_DIR):
        logger.warning("fs_blocked_traversal path=%r resolved=%s base=%s",
                        path, candidate, BASE_DIR)
        raise ValueError(
            f"Path '{path}' resolves outside the working directory "
            f"({BASE_DIR}) and is not allowed."
        )

    # Explicit symlink rejection, on top of resolve() already following
    # symlinks for the containment check above. Defense in depth against
    # TOCTOU: even if the resolved target lands inside BASE_DIR right
    # now, a symlink could be swapped to point elsewhere between this
    # check and the caller actually opening the file. Simplest fix:
    # don't allow symlinks in the sandbox at all.
    raw_path = BASE_DIR / path
    if raw_path.is_symlink():
        logger.warning("fs_blocked_symlink path=%r", path)
        raise ValueError(f"Path '{path}' is a symlink; not permitted.")

    return candidate


def create_directory(path: str) -> str:
    """Create a folder (and any missing parent folders) inside the working directory.

    Use this before writing files into a new subfolder, e.g. call
    create_directory("todo-app") before write_file("todo-app/index.html", ...).
    Safe to call on a folder that already exists -- it will not error or
    overwrite anything. Asks for human confirmation before creating
    anything, like every other tool that changes the filesystem.

    Args:
        path: Folder path relative to the working directory, e.g.
              "todo-app" or "todo-app/assets". Never an absolute path
              and never one that starts with "..".
    """
    target = resolve_path(path)

    if REQUIRE_CONFIRMATION and not confirm(f"Create directory: {path}"):
        return f"Cancelled by user: create_directory({path})"

    target.mkdir(parents=True, exist_ok=True)
    return f"Created directory: {path}"


def write_file(path: str, content: str) -> str:
    """Write text content to a file inside the working directory, overwriting it if it exists.

    Creates any missing parent folders automatically, so you do not need
    to call create_directory first for a nested path. Always writes the
    FULL file content -- there is no append or partial-edit mode, so when
    changing an existing file, read it first with read_file, edit the
    text yourself, then write the complete new version back. Asks for
    human confirmation before writing, since this can overwrite existing
    work.

    Args:
        path: File path relative to the working directory, e.g.
              "todo-app/style.css". Never an absolute path and never one
              that starts with "..".
        content: The complete text to write to the file, as a plain
                 string (e.g. full HTML, CSS, JS, or Markdown source).
                 Capped at MAX_WRITE_BYTES.
    """
    target = resolve_path(path)

    size = len(content.encode("utf-8"))
    if size > MAX_WRITE_BYTES:
        logger.warning("fs_blocked_oversized_write path=%r size=%d limit=%d",
                        path, size, MAX_WRITE_BYTES)
        return (
            f"Refused: content for '{path}' is {size} bytes, "
            f"which exceeds the {MAX_WRITE_BYTES}-byte limit."
        )

    if REQUIRE_CONFIRMATION and not confirm(f"Write {size} bytes to: {path}"):
        return f"Cancelled by user: write_file({path})"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {path}"


def read_file(path: str) -> str:
    """Read and return the full text content of a file inside the working directory.

    Call this before editing anything you (or a previous turn) already
    created -- it is the only way to see the file's current, exact
    content before changing it. If the file does not exist yet, this
    returns a short "not found" message instead of raising, so you can
    treat "file missing" as a normal observation and decide whether to
    create it. This tool only works on FILES -- to see what folders and
    files already exist, use list_directory instead. Read-only, so no
    confirmation is required.

    Args:
        path: File path relative to the working directory, e.g.
              "todo-app/index.html". Never an absolute path and never
              one that starts with "..".
    """
    target = resolve_path(path)
    if not target.exists():
        return f"No such file: {path}"
    if not target.is_file():
        return f"Not a file: {path}. Use list_directory to inspect folders."
    return target.read_text(encoding="utf-8")


def list_directory(path: str = ".") -> str:
    """List the files and subfolders directly inside a folder in the working directory.

    Use this to discover what already exists -- e.g. at the start of a
    conversation before assuming nothing has been built, or when asked
    "what did we make before" / "what's in this project". Work already
    done in past sessions is still sitting on disk even though the chat
    itself has no memory of it, so this is how you rediscover it. This
    only lists one level deep (it does not recurse into subfolders);
    call it again with a subfolder's path to look inside that one.
    Read-only, so no confirmation is required.

    Args:
        path: Folder path relative to the working directory. Use "." for
              the working directory itself (the default). Never an
              absolute path and never one that starts with "..".
    """
    target = resolve_path(path)
    if not target.exists():
        return f"No such directory: {path}"
    if not target.is_dir():
        return f"Not a directory: {path}. Use read_file to read a file."

    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    if not entries:
        return f"'{path}' is empty."

    lines = []
    for entry in entries:
        kind = "dir" if entry.is_dir() else "file"
        lines.append(f"[{kind}] {entry.name}")
    return "\n".join(lines)
