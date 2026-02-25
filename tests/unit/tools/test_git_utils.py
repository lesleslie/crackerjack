"""Tests for git utilities."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, call

import pytest

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

        with patch.object(Path, "rglob") as mock_rglob:
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
