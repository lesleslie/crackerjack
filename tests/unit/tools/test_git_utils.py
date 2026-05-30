"""Tests for git utilities."""

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

        # Mock exists to return True only for exists.py
        exists_map = {"exists.py": True, "deleted.py": False}

        def mock_exists(self):
            return exists_map.get(str(self), False)

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
        # Mock to return files for *.py pattern
        def mock_side_effect(pattern=None):
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
        def mock_side_effect(pattern=None):
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

        # Mock is_file behavior
        is_file_map = {
            file1: True,
            file2: True,
            dir1: False,
        }

        def mock_is_file(self):
            return is_file_map.get(self, False)

        def mock_side_effect(pattern=None):
            return [file1, file2, dir1]

        mock_git_files.side_effect = mock_side_effect

        with patch.object(Path, "is_file", mock_is_file):
            files = get_files_by_extension([".py"])

        assert len(files) == 2
        assert dir1 not in files
