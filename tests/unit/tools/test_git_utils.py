"""Tests for git utilities."""

import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import crackerjack.tools._git_utils as git_utils
from crackerjack.tools._git_utils import get_files_by_extension, get_git_tracked_files


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
