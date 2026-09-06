"""Tests for git utilities."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import crackerjack.tools._git_utils as git_utils
from crackerjack.tools._git_utils import (
    _iter_gitignore_files,
    _load_gitignore_spec,
    filter_gitignored_files,
    get_files_by_extension,
    get_git_root,
    get_git_tracked_files,
)


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    """Clear lru_cache before/after each test to prevent state bleed."""
    get_git_root.cache_clear()
    _load_gitignore_spec.cache_clear()
    yield
    get_git_root.cache_clear()
    _load_gitignore_spec.cache_clear()


class TestGetGitTrackedFiles:
    """Test get_git_tracked_files function."""

    @patch("subprocess.run")
    def test_get_tracked_files_success(self, mock_run):
        """Test successful retrieval of git tracked files."""
        mock_result = Mock()
        mock_result.stdout = "file1.py\nfile2.py\nfile3.py\n"
        mock_result.check_returncode = lambda: None
        mock_run.return_value = mock_result

        # Mock Path.exists to return True
        with patch.object(Path, "exists", return_value=True):
            files = get_git_tracked_files()

        assert len(files) == 3
        assert all(isinstance(f, Path) for f in files)

    @patch("subprocess.run")
    def test_get_tracked_files_with_pattern(self, mock_run):
        """Test retrieval with file pattern."""
        mock_result = Mock()
        mock_result.stdout = "file1.py\nfile2.py\n"
        mock_result.check_returncode = lambda: None
        mock_run.return_value = mock_result

        with patch.object(Path, "exists", return_value=True):
            files = get_git_tracked_files("*.py")

        assert len(files) == 2
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_tracked_filters_nonexistent(self, mock_run):
        """Test that nonexistent files are filtered out."""
        mock_result = Mock()
        mock_result.stdout = "exists.py\ndeleted.py\n"
        mock_result.check_returncode = lambda: None
        mock_run.return_value = mock_result

        # Mock exists to return True only for exists.py.
        # The production code constructs absolute paths via cwd / f,
        # so the mock matches by basename rather than full path.
        def mock_exists(self):
            return self.name == "exists.py"

        with patch.object(Path, "exists", mock_exists):
            files = get_git_tracked_files()

        assert len(files) == 1
        assert files[0].name == "exists.py"

    @patch("subprocess.run")
    def test_get_tracked_files_subprocess_error(self, mock_run):
        """Test handling of subprocess errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        files = get_git_tracked_files()

        assert files == []

    @patch("subprocess.run")
    def test_get_tracked_files_git_not_found(self, mock_run):
        """Test handling when git is not found."""
        mock_run.side_effect = FileNotFoundError()

        files = get_git_tracked_files()

        assert files == []

    @patch("subprocess.run")
    def test_get_tracked_empty_output(self, mock_run):
        """Test handling of empty git output."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.check_returncode = lambda: None
        mock_run.return_value = mock_result

        files = get_git_tracked_files()

        assert files == []

    @patch("subprocess.run")
    def test_get_tracked_filters_whitespace(self, mock_run):
        """Test that empty lines are filtered."""
        mock_result = Mock()
        mock_result.stdout = "file1.py\n\n   \nfile2.py\n"
        mock_result.check_returncode = lambda: None
        mock_run.return_value = mock_result

        with patch.object(Path, "exists", return_value=True):
            files = get_git_tracked_files()

        assert len(files) == 2

    @patch("subprocess.run")
    def test_get_tracked_filters_gitignored_files(self, mock_run, tmp_path, monkeypatch):
        """Test that files matched by .gitignore are excluded."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gitignore").write_text(".skylos/\n")
        (tmp_path / "README.md").write_text("readme")
        skylos_file = tmp_path / ".skylos" / "cache.sqlite"
        skylos_file.parent.mkdir(parents=True)
        skylos_file.write_text("cache")

        mock_result = Mock()
        mock_result.stdout = "README.md\n.skylos/cache.sqlite\n"
        mock_result.check_returncode = lambda: None
        mock_run.return_value = mock_result

        files = get_git_tracked_files()

        assert Path("README.md") in files
        assert all(".skylos" not in str(path) for path in files)


class TestGitignoreHelpers:
    """Test internal gitignore helper functions."""

    def test_load_gitignore_spec_skips_non_files(self, monkeypatch, tmp_path):
        """Test that non-file .gitignore paths are ignored."""
        fake_gitignore = tmp_path / ".gitignore"

        def fake_rglob(self, pattern):
            return [fake_gitignore] if pattern == ".gitignore" else []

        monkeypatch.setattr(Path, "rglob", fake_rglob)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        git_utils._load_gitignore_spec.cache_clear()

        assert git_utils._load_gitignore_spec(str(tmp_path)) is None

    def test_load_gitignore_spec_collects_nested_and_negated_patterns(self, tmp_path):
        """Test gitignore loading across nested directories and negations."""
        (tmp_path / ".gitignore").write_text(
            "# comment\n"
            "!\n"
            "build/\n"
            "!build/keep.txt\n"
            "\n",
        )
        nested = tmp_path / "pkg"
        nested.mkdir()
        (nested / ".gitignore").write_text("*.log\n")

        git_utils._load_gitignore_spec.cache_clear()
        spec = git_utils._load_gitignore_spec(str(tmp_path))

        assert spec is not None
        assert spec.match_file("build/output.txt")
        assert not spec.match_file("build/keep.txt")
        assert spec.match_file("pkg/debug.log")
        assert not spec.match_file("pkg/notes.txt")

    def test_load_gitignore_spec_skips_gitignore_outside_root(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ):
        """Test that gitignore files outside the root are skipped."""
        outside_root = tmp_path.parent / "outside-gitignore"
        outside_root.mkdir(exist_ok=True)
        outside_gitignore = outside_root / ".gitignore"
        outside_gitignore.write_text("ignored\n")

        def fake_rglob(self, pattern):
            return [outside_gitignore] if pattern == ".gitignore" else []

        monkeypatch.setattr(Path, "rglob", fake_rglob)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        git_utils._load_gitignore_spec.cache_clear()

        assert git_utils._load_gitignore_spec(str(tmp_path)) is None

    def test_is_gitignored_returns_false_without_spec(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ):
        """Test that paths are treated as tracked when no gitignore exists."""
        monkeypatch.setattr(git_utils, "_load_gitignore_spec", lambda _root=None: None)

        assert not git_utils._is_gitignored(tmp_path / "file.txt", root=tmp_path)

    def test_is_gitignored_uses_relative_path_for_outside_files(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ):
        """Test that non-root paths are matched against their POSIX form."""
        spec = Mock()
        spec.match_file.return_value = True
        monkeypatch.setattr(git_utils, "_load_gitignore_spec", lambda _root=None: spec)

        outside_path = tmp_path.parent / "external.txt"

        assert git_utils._is_gitignored(outside_path, root=tmp_path)
        spec.match_file.assert_called_once_with(outside_path.as_posix())


class TestGetFilesByExtension:
    """Test get_files_by_extension function."""

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_get_files_single_extension(self, mock_git_files):
        """Test getting files by single extension."""
        # Mock to return files for *.py pattern.
        # The production code passes `root=cwd` as a keyword argument,
        # so the side_effect must accept it (even if unused).
        def mock_side_effect(pattern=None, root=None):
            if pattern == "*.py":
                return [Path("file1.py"), Path("file2.py")]
            return []

        mock_git_files.side_effect = mock_side_effect

        with patch.object(Path, "is_file", return_value=True):
            files = get_files_by_extension([".py"])

        assert len(files) == 2
        assert all(f.suffix == ".py" for f in files)

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_get_files_multiple_extensions(self, mock_git_files):
        """Test getting files by multiple extensions."""
        def mock_side_effect(pattern=None, root=None):
            if pattern == "*.py":
                return [Path("file1.py"), Path("file3.py")]
            elif pattern == "*.md":
                return [Path("file2.md"), Path("file4.md")]
            return []

        mock_git_files.side_effect = mock_side_effect

        with patch.object(Path, "is_file", return_value=True):
            files = get_files_by_extension([".py", ".md"])

        assert len(files) == 4

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_get_files_no_git_fallback(self, mock_git_files):
        """Test fallback to rglob when git returns no files."""
        mock_git_files.return_value = []

        with (
            patch("crackerjack.tools._git_utils._load_gitignore_spec", return_value=None),
            patch.object(Path, "rglob") as mock_rglob,
        ):
            mock_rglob.return_value = [
                Path("dir/file1.py"),
                Path("dir/file2.py"),
            ]
            with patch.object(Path, "is_file", return_value=True):
                files = get_files_by_extension([".py"])

        assert len(files) == 2

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_get_files_use_git_false(self, mock_git_files):
        """Test not using git when use_git=False."""
        mock_git_files.return_value = [
            Path("file1.py"),
            Path("file2.py"),
        ]

        with patch.object(Path, "rglob") as mock_rglob:
            mock_rglob.return_value = [Path("file3.py")]
            with patch.object(Path, "is_file", return_value=True):
                files = get_files_by_extension([".py"], use_git=False)

        # Should not call git when use_git=False
        mock_git_files.assert_not_called()
        # Should use rglob instead
        assert len(files) == 1

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_get_files_filters_directories(self, mock_git_files):
        """Test that directories are filtered out."""
        # Create mock paths where some are directories
        file1 = Path("file1.py")
        file2 = Path("file2.py")
        dir1 = Path("dir.py")

        # Match by basename: the production code constructs new Paths
        # via `cwd / f`, so the Path identity differs from the originals.
        def mock_is_file(self):
            return self.name in {"file1.py", "file2.py"}

        def mock_side_effect(pattern=None, root=None):
            return [file1, file2, dir1]

        mock_git_files.side_effect = mock_side_effect

        # get_git_tracked_files now calls filter_gitignored_files; mock
        # _load_gitignore_spec to None so no .gitignore filtering occurs.
        with (
            patch("crackerjack.tools._git_utils._load_gitignore_spec", return_value=None),
            patch.object(Path, "is_file", mock_is_file),
        ):
            files = get_files_by_extension([".py"])

        assert len(files) == 2
        assert dir1 not in files


class TestGetGitRoot:
    """Test get_git_root helper."""

    def test_walks_up_to_dot_git_directory(self, tmp_path: Path) -> None:
        """get_git_root walks up to find the directory containing .git."""
        git_utils.get_git_root.cache_clear()
        (tmp_path / ".git").mkdir()
        nested = tmp_path / "src" / "pkg"
        nested.mkdir(parents=True)
        assert git_utils.get_git_root(start=nested) == tmp_path

    def test_returns_none_when_no_dot_git_above(self, tmp_path: Path) -> None:
        """get_git_root returns None or a directory outside tmp_path when no .git is found above the leaf."""
        git_utils.get_git_root.cache_clear()
        leaf = tmp_path / "no_repo_here"
        leaf.mkdir()
        result = git_utils.get_git_root(start=leaf)
        if result is not None:
            assert tmp_path not in result.parents, (
                f"get_git_root returned {result} which is inside tmp_path"
            )

    def test_handles_dot_git_as_file(self, tmp_path: Path) -> None:
        """get_git_root recognizes .git as a file (git submodule/worktree)."""
        git_utils.get_git_root.cache_clear()
        (tmp_path / ".git").write_text("gitdir: /tmp/elsewhere\n")
        assert git_utils.get_git_root(start=tmp_path) == tmp_path

    def test_default_start_is_none(self) -> None:
        """get_git_root defaults start to None (resolved to Path.cwd() at call time)."""
        import inspect

        sig = inspect.signature(git_utils.get_git_root)
        assert sig.parameters["start"].default is None

    def test_accepts_relative_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_git_root resolves relative paths via .resolve()."""
        git_utils.get_git_root.cache_clear()
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        nested = Path("src/pkg")
        (tmp_path / nested).mkdir(parents=True)
        assert git_utils.get_git_root(start=nested) == tmp_path

    def test_recognizes_dot_git_symlink(self, tmp_path: Path) -> None:
        """get_git_root accepts a .git that is a symlink to a real directory."""
        git_utils.get_git_root.cache_clear()
        real_git = tmp_path / "real_git"
        real_git.mkdir()
        (real_git / "HEAD").write_text("ref: refs/heads/main\n")
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        os.symlink(real_git, worktree / ".git")
        assert git_utils.get_git_root(start=worktree) == worktree

    def test_uses_start_parameter_when_given(self, tmp_path: Path) -> None:
        """get_git_root accepts a custom start path."""
        (tmp_path / ".git").mkdir()
        nested = tmp_path / "deep" / "nested" / "dir"
        nested.mkdir(parents=True)
        assert get_git_root(start=nested) == tmp_path

    def test_uses_cwd_when_start_is_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_git_root falls back to Path.cwd() when start is None."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        assert get_git_root() == tmp_path

    def test_returns_none_for_filesystem_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_git_root returns None when no .git exists anywhere above start."""
        # Use tmp_path with no .git anywhere up the tree (tmp_path parents
        # won't have .git either in CI).
        result = get_git_root(start=tmp_path)
        # Either None (no .git found) or some directory outside tmp_path
        # that happens to contain .git (unlikely in test env).
        if result is not None:
            assert tmp_path not in result.parents

    def test_lru_cache_returns_same_path_object(self, tmp_path: Path) -> None:
        """lru_cache returns identical Path object for repeated calls."""
        (tmp_path / ".git").mkdir()
        first = get_git_root(start=tmp_path)
        second = get_git_root(start=tmp_path)
        # lru_cache hits return the exact same object.
        assert first is second

    def test_walks_through_multiple_levels(self, tmp_path: Path) -> None:
        """get_git_root walks up through multiple parent levels."""
        (tmp_path / ".git").mkdir()
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        assert get_git_root(start=deep) == tmp_path


class TestIterGitignoreFiles:
    """Test _iter_gitignore_files walker."""

    def test_yields_root_gitignore(self, tmp_path: Path) -> None:
        """Yields the root .gitignore when present."""
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        files = list(_iter_gitignore_files(tmp_path))
        assert tmp_path / ".gitignore" in files

    def test_yields_nested_gitignore_files(self, tmp_path: Path) -> None:
        """Yields nested .gitignore files in subdirectories."""
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        nested = tmp_path / "pkg" / "subpkg"
        nested.mkdir(parents=True)
        (nested / ".gitignore").write_text("*.log\n")
        files = list(_iter_gitignore_files(tmp_path))
        assert tmp_path / ".gitignore" in files
        assert nested / ".gitignore" in files

    def test_skips_directories_without_gitignore(self, tmp_path: Path) -> None:
        """Does not yield non-existent .gitignore paths."""
        subdir = tmp_path / "noignore"
        subdir.mkdir()
        files = list(_iter_gitignore_files(tmp_path))
        # subdir/.gitignore does not exist and shouldn't be yielded.
        assert subdir / ".gitignore" not in files

    def test_prunes_skip_directories(self, tmp_path: Path) -> None:
        """Skips traversal of noise directories like .venv and node_modules."""
        (tmp_path / "real").mkdir()
        (tmp_path / "real" / ".gitignore").write_text("*.log\n")
        # .venv and node_modules should NOT be traversed.
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / ".gitignore").write_text("should_not_be_seen\n")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / ".gitignore").write_text("should_not_be_seen\n")

        files = list(_iter_gitignore_files(tmp_path))
        names = [f.name for f in files]
        # Only real/.gitignore should be present.
        assert (tmp_path / "real" / ".gitignore") in files
        assert (tmp_path / ".venv" / ".gitignore") not in files
        assert (tmp_path / "node_modules" / ".gitignore") not in files

    def test_prunes_multiple_skip_directories(self, tmp_path: Path) -> None:
        """Prunes all directory names in _GITIGNORE_SKIP_PARTS."""
        skip_dirs = [
            ".venv",
            "node_modules",
            "__pycache__",
            ".worktrees",
            ".claude",
            ".backups",
            ".crackerjack",
            ".superpowers",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".complexipy_cache",
            ".hypothesis",
            ".tox",
            "htmlcov",
            ".idea",
            ".vscode",
        ]
        for skip in skip_dirs:
            d = tmp_path / skip
            d.mkdir()
            (d / ".gitignore").write_text("blocked\n")
        files = list(_iter_gitignore_files(tmp_path))
        # No file from any of the skipped dirs should be present.
        for f in files:
            parts = f.parts
            assert not any(skip in parts for skip in skip_dirs), (
                f"Skipped dir traversed: {f}"
            )

    def test_yields_nothing_when_no_gitignore_exists(self, tmp_path: Path) -> None:
        """Yields nothing when no .gitignore exists in tree."""
        (tmp_path / "empty").mkdir()
        files = list(_iter_gitignore_files(tmp_path))
        assert files == []


class TestLoadGitignoreSpec:
    """Test _load_gitignore_spec path."""

    def test_returns_none_when_no_gitignore_files(self, tmp_path: Path) -> None:
        """Returns None when there are no .gitignore files."""
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is None

    def test_returns_pathspec_when_patterns_exist(self, tmp_path: Path) -> None:
        """Returns a PathSpec object when patterns are present."""
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is not None
        assert spec.match_file("foo.pyc")
        assert not spec.match_file("foo.py")

    def test_handles_negated_patterns(self, tmp_path: Path) -> None:
        """Handles `!`-prefixed (negated) patterns correctly."""
        (tmp_path / ".gitignore").write_text("*.pyc\n!important.pyc\n")
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is not None
        assert not spec.match_file("important.pyc")
        assert spec.match_file("other.pyc")

    def test_strips_leading_slash_from_anchored_patterns(self, tmp_path: Path) -> None:
        """Strips `/` prefix from anchored patterns."""
        (tmp_path / ".gitignore").write_text("/build/\n")
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is not None
        # /build/ becomes build/ — matches files inside build/, not bare 'build'.
        assert spec.match_file("build/output.txt")
        assert not spec.match_file("build")
        assert not spec.match_file("src/main.py")

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        """Skips blank lines and lines that become blank after negation strip."""
        (tmp_path / ".gitignore").write_text("\n   \n\t\n*.log\n")
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is not None
        assert spec.match_file("debug.log")
        # Only the *.log pattern should be in effect.
        assert not spec.match_file("foo.py")

    def test_skips_bang_only_lines(self, tmp_path: Path) -> None:
        """Skips `!` lines that have no pattern after negation."""
        (tmp_path / ".gitignore").write_text("!\n!   \n*.tmp\n")
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is not None
        assert spec.match_file("scratch.tmp")

    def test_skips_comment_lines(self, tmp_path: Path) -> None:
        """Skips `#`-prefixed comment lines."""
        (tmp_path / ".gitignore").write_text("# this is a comment\n*.bak\n")
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is not None
        assert spec.match_file("backup.bak")
        # Comments are not patterns.
        assert not spec.match_file("# this is a comment")

    def test_prefixes_nested_patterns_with_relative_dir(self, tmp_path: Path) -> None:
        """Nested gitignore patterns get prefixed with their relative dir."""
        nested = tmp_path / "pkg"
        nested.mkdir()
        (nested / ".gitignore").write_text("*.log\n")
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is not None
        assert spec.match_file("pkg/debug.log")
        # The pattern is scoped to pkg/, so debug.log at root should NOT match.
        assert not spec.match_file("debug.log")

    def test_handles_negated_nested_pattern(self, tmp_path: Path) -> None:
        """Negation flag preserved when prefixing nested patterns."""
        nested = tmp_path / "pkg"
        nested.mkdir()
        (nested / ".gitignore").write_text("*.log\n!keep.log\n")
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is not None
        assert spec.match_file("pkg/debug.log")
        assert not spec.match_file("pkg/keep.log")

    def test_handles_anchored_nested_pattern(self, tmp_path: Path) -> None:
        """Slash-anchored patterns in nested gitignore get prefix + lstrip."""
        nested = tmp_path / "pkg"
        nested.mkdir()
        (nested / ".gitignore").write_text("/only_this/\n")
        spec = _load_gitignore_spec(str(tmp_path))
        assert spec is not None
        assert spec.match_file("pkg/only_this/file.txt")


class TestIsGitignored:
    """Test _is_gitignored helper."""

    def test_returns_false_when_no_spec(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns False when no gitignore spec is loaded."""
        monkeypatch.setattr(git_utils, "_load_gitignore_spec", lambda _root=None: None)
        assert not git_utils._is_gitignored(tmp_path / "any.py", root=tmp_path)

    def test_returns_true_for_matching_path(self, tmp_path: Path) -> None:
        """Returns True when path matches the gitignore spec."""
        (tmp_path / ".gitignore").write_text("*.log\n")
        assert git_utils._is_gitignored(tmp_path / "debug.log", root=tmp_path)

    def test_returns_false_for_non_matching_path(self, tmp_path: Path) -> None:
        """Returns False when path does not match the gitignore spec."""
        (tmp_path / ".gitignore").write_text("*.log\n")
        assert not git_utils._is_gitignored(tmp_path / "main.py", root=tmp_path)

    def test_falls_back_to_absolute_for_outside_path(self, tmp_path: Path) -> None:
        """Uses absolute path when relative_to() raises ValueError."""
        (tmp_path / ".gitignore").write_text("outside.txt\n")
        outside_path = tmp_path.parent / "external.txt"
        # The spec should still be tested against the absolute path's posix form.
        result = git_utils._is_gitignored(outside_path, root=tmp_path)
        # The path is not within tmp_path; spec.match_file gets the absolute posix.
        assert isinstance(result, bool)


class TestFilterGitignoredFiles:
    """Test filter_gitignored_files filter."""

    def test_filters_gitignored_files(self, tmp_path: Path) -> None:
        """Removes paths that are gitignored."""
        (tmp_path / ".gitignore").write_text("*.log\n")
        keep = tmp_path / "main.py"
        skip = tmp_path / "debug.log"
        result = filter_gitignored_files([keep, skip], root=tmp_path)
        assert keep in result
        assert skip not in result

    def test_keeps_all_when_no_gitignore(self, tmp_path: Path) -> None:
        """Keeps all files when no .gitignore is present."""
        files = [tmp_path / "a.py", tmp_path / "b.py"]
        result = filter_gitignored_files(files, root=tmp_path)
        assert result == files

    def test_empty_input_returns_empty(self, tmp_path: Path) -> None:
        """Empty input list returns empty output."""
        result = filter_gitignored_files([], root=tmp_path)
        assert result == []


class TestGetGitTrackedFilesCmd:
    """Test subprocess invocation in get_git_tracked_files."""

    @patch("subprocess.run")
    def test_pattern_passed_to_subprocess_cmd(self, mock_run: Mock, tmp_path: Path) -> None:
        """Pattern is appended to the git ls-files command."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.check_returncode = lambda: None
        mock_run.return_value = mock_result

        get_git_tracked_files("*.py", root=tmp_path)
        cmd = mock_run.call_args[0][0]
        assert "git" in cmd
        assert "ls-files" in cmd
        assert "*.py" in cmd

    @patch("subprocess.run")
    def test_no_pattern_omitted_from_cmd(self, mock_run: Mock, tmp_path: Path) -> None:
        """No extra arg appended when pattern is None."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.check_returncode = lambda: None
        mock_run.return_value = mock_result

        get_git_tracked_files(root=tmp_path)
        cmd = mock_run.call_args[0][0]
        assert cmd == ["git", "ls-files"]

    @patch("subprocess.run")
    def test_filters_gitignored_tracked_files(
        self,
        mock_run: Mock,
        tmp_path: Path,
    ) -> None:
        """Files matching .gitignore are filtered from output."""
        (tmp_path / ".gitignore").write_text(".cache/\n")
        mock_result = Mock()
        mock_result.stdout = "main.py\n.cache/data.py\n"
        mock_result.check_returncode = lambda: None
        mock_run.return_value = mock_result

        def mock_exists(self: Path) -> bool:
            return True

        with patch.object(Path, "exists", mock_exists):
            files = get_git_tracked_files(root=tmp_path)

        names = [f.name for f in files]
        assert "main.py" in names
        assert "data.py" not in names


class TestGetFilesByExtensionFallback:
    """Test get_files_by_extension fallback paths."""

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_use_git_true_falls_back_to_rglob_when_empty(
        self,
        mock_git_files: Mock,
        tmp_path: Path,
    ) -> None:
        """Falls back to rglob when git returns no files."""
        mock_git_files.return_value = []

        with patch.object(Path, "rglob") as mock_rglob:
            mock_rglob.return_value = [Path("foo.py"), Path("bar.py")]
            with patch.object(Path, "is_file", return_value=True):
                files = get_files_by_extension([".py"], root=tmp_path)

        assert len(files) == 2
        # rglob should have been called as fallback.
        assert mock_rglob.called

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_use_git_true_with_files_returns_git_files(
        self,
        mock_git_files: Mock,
        tmp_path: Path,
    ) -> None:
        """When git returns files, rglob is not called."""
        git_file = Path("tracked.py")
        mock_git_files.return_value = [git_file]

        with patch.object(Path, "rglob") as mock_rglob:
            with patch.object(Path, "is_file", return_value=True):
                files = get_files_by_extension([".py"], root=tmp_path)

        assert files == [git_file]
        mock_rglob.assert_not_called()

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_use_git_false_calls_rglob_directly(
        self,
        mock_git_files: Mock,
        tmp_path: Path,
    ) -> None:
        """use_git=False bypasses git and uses rglob directly."""
        with patch.object(Path, "rglob") as mock_rglob:
            mock_rglob.return_value = [Path("a.py"), Path("b.py")]
            with patch.object(Path, "is_file", return_value=True):
                files = get_files_by_extension([".py"], use_git=False, root=tmp_path)

        # git is not invoked when use_git=False
        mock_git_files.assert_not_called()
        assert len(files) == 2

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_filters_directories_in_use_git_false(
        self,
        mock_git_files: Mock,
        tmp_path: Path,
    ) -> None:
        """use_git=False path filters non-files via is_file()."""
        file = Path("a.py")
        dir_ = Path("b.py")  # Same name but pretend it's a directory.

        def mock_is_file(self: Path) -> bool:
            return self.name == "a.py"

        with patch.object(Path, "rglob") as mock_rglob:
            mock_rglob.return_value = [file, dir_]
            with patch.object(Path, "is_file", mock_is_file):
                files = get_files_by_extension([".py"], use_git=False, root=tmp_path)

        assert file in files
        assert dir_ not in files

    @patch("crackerjack.tools._git_utils.get_git_tracked_files")
    def test_use_git_true_rglob_fallback_filters_non_files(
        self,
        mock_git_files: Mock,
        tmp_path: Path,
    ) -> None:
        """rglob fallback also filters via is_file()."""
        mock_git_files.return_value = []

        file = Path("keep.py")
        non_file = Path("skip.py")

        def mock_is_file(self: Path) -> bool:
            return self.name == "keep.py"

        with patch.object(Path, "rglob") as mock_rglob:
            mock_rglob.return_value = [file, non_file]
            with patch.object(Path, "is_file", mock_is_file):
                files = get_files_by_extension([".py"], root=tmp_path)

        assert file in files
        assert non_file not in files
