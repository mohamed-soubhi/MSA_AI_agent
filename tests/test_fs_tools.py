"""Tests for fs_tools.py — sandboxed filesystem tools.

Covers resolve_path()'s sandbox/validation rules (the single choke point
all four tools go through) plus each tool's own behavior: confirmation
gating, size limits, missing files/dirs, and non-recursive listing.
"""

import sys

import pytest

import fs_tools


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    """Point BASE_DIR at an isolated tmp dir for every test in this file."""
    monkeypatch.setattr(fs_tools, "BASE_DIR", tmp_path.resolve())
    return tmp_path


@pytest.fixture
def always_confirm(monkeypatch):
    """Auto-approve every confirm() call."""
    monkeypatch.setattr(fs_tools, "confirm", lambda action: True)


@pytest.fixture
def always_deny(monkeypatch):
    """Auto-deny every confirm() call."""
    monkeypatch.setattr(fs_tools, "confirm", lambda action: False)


# --------------------------------------------------------------------------
# resolve_path
# --------------------------------------------------------------------------

class TestResolvePath:
    @pytest.mark.tid("FSTOOLS-001")
    def test_simple_relative_path_resolves_inside_base_dir(self, sandbox):
        result = fs_tools.resolve_path("file.txt")
        assert result == (sandbox / "file.txt").resolve()

    @pytest.mark.tid("FSTOOLS-002")
    def test_nested_relative_path(self, sandbox):
        result = fs_tools.resolve_path("todo-app/style.css")
        assert result == (sandbox / "todo-app" / "style.css").resolve()

    @pytest.mark.tid("FSTOOLS-003")
    def test_dot_path_resolves_to_base_dir(self, sandbox):
        assert fs_tools.resolve_path(".") == sandbox.resolve()

    @pytest.mark.parametrize("bad", [None, 123, [], {}])
    @pytest.mark.tid("FSTOOLS-004")
    def test_non_string_path_raises(self, bad):
        with pytest.raises(ValueError, match="non-empty string"):
            fs_tools.resolve_path(bad)

    @pytest.mark.tid("FSTOOLS-005")
    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            fs_tools.resolve_path("")

    @pytest.mark.parametrize("bad", ["a\x00b.txt", "a\x1fb", "a\x7fb"])
    @pytest.mark.tid("FSTOOLS-006")
    def test_control_characters_rejected(self, bad):
        with pytest.raises(ValueError, match="control characters"):
            fs_tools.resolve_path(bad)

    @pytest.mark.tid("FSTOOLS-007")
    def test_parent_traversal_rejected(self):
        with pytest.raises(ValueError, match="outside the working directory"):
            fs_tools.resolve_path("../escape.txt")

    @pytest.mark.tid("FSTOOLS-008")
    def test_deep_parent_traversal_rejected(self):
        with pytest.raises(ValueError, match="outside the working directory"):
            fs_tools.resolve_path("a/b/../../../../etc/passwd")

    @pytest.mark.tid("FSTOOLS-009")
    def test_absolute_path_rejected(self):
        absolute = "/etc/passwd" if sys.platform != "win32" else "C:\\Windows\\system.ini"
        with pytest.raises(ValueError, match="outside the working directory"):
            fs_tools.resolve_path(absolute)

    @pytest.mark.parametrize(
        "name", ["CON", "con.txt", "PRN", "AUX", "NUL", "COM1", "com9.log", "LPT1"]
    )
    @pytest.mark.tid("FSTOOLS-010")
    def test_windows_reserved_names_rejected(self, name):
        with pytest.raises(ValueError, match="reserved device name"):
            fs_tools.resolve_path(name)

    @pytest.mark.tid("FSTOOLS-011")
    def test_windows_reserved_name_in_nested_segment_rejected(self):
        with pytest.raises(ValueError, match="reserved device name"):
            fs_tools.resolve_path("reports/con.txt")

    @pytest.mark.tid("FSTOOLS-012")
    def test_non_reserved_name_that_shares_a_prefix_is_allowed(self, sandbox):
        # "console.txt" must NOT be blocked — only the exact reserved stem.
        result = fs_tools.resolve_path("console.txt")
        assert result == (sandbox / "console.txt").resolve()

    @pytest.mark.tid("FSTOOLS-013")
    def test_fullwidth_unicode_traversal_normalized_and_rejected(self):
        # Fullwidth "．．／" NFKC-normalizes to "../" before the check runs.
        with pytest.raises(ValueError, match="outside the working directory"):
            fs_tools.resolve_path("\uff0e\uff0e\uff0fescape.txt")

    @pytest.mark.tid("FSTOOLS-014")
    def test_symlink_target_rejected_even_if_inside_base_dir(self, sandbox):
        real_target = sandbox / "real.txt"
        real_target.write_text("secret")
        link = sandbox / "link.txt"
        try:
            link.symlink_to(real_target)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported in this environment")
        with pytest.raises(ValueError, match="symlink"):
            fs_tools.resolve_path("link.txt")

    @pytest.mark.tid("FSTOOLS-015")
    def test_base_dir_prefix_lookalike_directory_is_not_a_bypass(self, sandbox, monkeypatch):
        # A sibling dir whose name merely starts with BASE_DIR's name must
        # not pass the containment check via naive string prefixing.
        lookalike = sandbox.parent / (sandbox.name + "-evil")
        lookalike.mkdir(exist_ok=True)
        with pytest.raises(ValueError, match="outside the working directory"):
            fs_tools.resolve_path(f"../{lookalike.name}/data.txt")


# --------------------------------------------------------------------------
# create_directory
# --------------------------------------------------------------------------

class TestCreateDirectory:
    @pytest.mark.tid("FSTOOLS-016")
    def test_creates_directory_when_confirmed(self, sandbox, always_confirm):
        result = fs_tools.create_directory("newdir")
        assert (sandbox / "newdir").is_dir()
        assert "Created directory" in result

    @pytest.mark.tid("FSTOOLS-017")
    def test_creates_nested_parents(self, sandbox, always_confirm):
        fs_tools.create_directory("a/b/c")
        assert (sandbox / "a" / "b" / "c").is_dir()

    @pytest.mark.tid("FSTOOLS-018")
    def test_idempotent_on_existing_directory(self, sandbox, always_confirm):
        (sandbox / "existing").mkdir()
        result = fs_tools.create_directory("existing")
        assert "Created directory" in result

    @pytest.mark.tid("FSTOOLS-019")
    def test_cancelled_when_confirmation_denied(self, sandbox, always_deny):
        result = fs_tools.create_directory("nope")
        assert "Cancelled by user" in result
        assert not (sandbox / "nope").exists()

    @pytest.mark.tid("FSTOOLS-020")
    def test_traversal_path_raises_before_confirmation(self, sandbox, monkeypatch):
        called = []
        monkeypatch.setattr(fs_tools, "confirm", lambda action: called.append(action) or True)
        with pytest.raises(ValueError):
            fs_tools.create_directory("../escape")
        assert called == []


# --------------------------------------------------------------------------
# write_file
# --------------------------------------------------------------------------

class TestWriteFile:
    @pytest.mark.tid("FSTOOLS-021")
    def test_writes_content_when_confirmed(self, sandbox, always_confirm):
        result = fs_tools.write_file("out.txt", "hello world")
        assert (sandbox / "out.txt").read_text() == "hello world"
        assert "Wrote 11 chars" in result

    @pytest.mark.tid("FSTOOLS-022")
    def test_overwrites_existing_file(self, sandbox, always_confirm):
        target = sandbox / "out.txt"
        target.write_text("old")
        fs_tools.write_file("out.txt", "new")
        assert target.read_text() == "new"

    @pytest.mark.tid("FSTOOLS-023")
    def test_creates_missing_parent_directories(self, sandbox, always_confirm):
        fs_tools.write_file("nested/dir/out.txt", "content")
        assert (sandbox / "nested" / "dir" / "out.txt").read_text() == "content"

    @pytest.mark.tid("FSTOOLS-024")
    def test_cancelled_when_confirmation_denied(self, sandbox, always_deny):
        result = fs_tools.write_file("out.txt", "content")
        assert "Cancelled by user" in result
        assert not (sandbox / "out.txt").exists()

    @pytest.mark.tid("FSTOOLS-025")
    def test_oversized_content_refused_without_confirmation(self, sandbox, monkeypatch):
        called = []
        monkeypatch.setattr(fs_tools, "confirm", lambda action: called.append(action) or True)
        monkeypatch.setattr(fs_tools, "MAX_WRITE_BYTES", 10)
        result = fs_tools.write_file("big.txt", "this is way more than ten bytes")
        assert "Refused" in result
        assert "exceeds" in result
        assert called == []
        assert not (sandbox / "big.txt").exists()

    @pytest.mark.tid("FSTOOLS-026")
    def test_empty_content_is_allowed(self, sandbox, always_confirm):
        result = fs_tools.write_file("empty.txt", "")
        assert (sandbox / "empty.txt").read_text() == ""
        assert "Wrote 0 chars" in result


# --------------------------------------------------------------------------
# read_file
# --------------------------------------------------------------------------

class TestReadFile:
    @pytest.mark.tid("FSTOOLS-027")
    def test_reads_existing_file(self, sandbox):
        (sandbox / "a.txt").write_text("data here")
        assert fs_tools.read_file("a.txt") == "data here"

    @pytest.mark.tid("FSTOOLS-028")
    def test_missing_file_returns_message_not_raise(self, sandbox):
        result = fs_tools.read_file("missing.txt")
        assert "No such file" in result

    @pytest.mark.tid("FSTOOLS-029")
    def test_directory_path_returns_message_not_raise(self, sandbox):
        (sandbox / "adir").mkdir()
        result = fs_tools.read_file("adir")
        assert "Not a file" in result

    @pytest.mark.tid("FSTOOLS-030")
    def test_no_confirmation_required(self, sandbox, monkeypatch):
        called = []
        monkeypatch.setattr(fs_tools, "confirm", lambda action: called.append(action) or True)
        (sandbox / "a.txt").write_text("x")
        fs_tools.read_file("a.txt")
        assert called == []


# --------------------------------------------------------------------------
# list_directory
# --------------------------------------------------------------------------

class TestListDirectory:
    @pytest.mark.tid("FSTOOLS-031")
    def test_lists_files_and_dirs_with_kind_prefix(self, sandbox):
        (sandbox / "file.txt").write_text("x")
        (sandbox / "subdir").mkdir()
        result = fs_tools.list_directory(".")
        assert "[file] file.txt" in result
        assert "[dir] subdir" in result

    @pytest.mark.tid("FSTOOLS-032")
    def test_dirs_sorted_before_files(self, sandbox):
        (sandbox / "zfile.txt").write_text("x")
        (sandbox / "adir").mkdir()
        result = fs_tools.list_directory(".")
        assert result.index("[dir] adir") < result.index("[file] zfile.txt")

    @pytest.mark.tid("FSTOOLS-033")
    def test_empty_directory_message(self, sandbox):
        (sandbox / "empty").mkdir()
        result = fs_tools.list_directory("empty")
        assert "is empty" in result

    @pytest.mark.tid("FSTOOLS-034")
    def test_default_path_is_current_directory(self, sandbox):
        (sandbox / "x.txt").write_text("x")
        assert "[file] x.txt" in fs_tools.list_directory()

    @pytest.mark.tid("FSTOOLS-035")
    def test_missing_directory_returns_message_not_raise(self, sandbox):
        result = fs_tools.list_directory("nope")
        assert "No such directory" in result

    @pytest.mark.tid("FSTOOLS-036")
    def test_file_path_returns_message_not_raise(self, sandbox):
        (sandbox / "f.txt").write_text("x")
        result = fs_tools.list_directory("f.txt")
        assert "Not a directory" in result

    @pytest.mark.tid("FSTOOLS-037")
    def test_only_one_level_deep(self, sandbox):
        (sandbox / "sub").mkdir()
        (sandbox / "sub" / "deep.txt").write_text("x")
        result = fs_tools.list_directory(".")
        assert "deep.txt" not in result
