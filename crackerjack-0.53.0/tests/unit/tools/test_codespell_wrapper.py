"""Tests for codespell_wrapper tool."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.tools.codespell_wrapper import main


class TestCodespellMain:
    """Test codespell main function."""

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_with_files(self, mock_run, mock_get_files):
        """Test main with git-tracked files."""
        mock_get_files.return_value = [
            Path("README.md"),
            Path("src/file.py"),
        ]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = main()

        assert result == 0
        mock_run.assert_called_once()

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_with_spelling_errors(self, mock_run, mock_get_files):
        """Test main when spelling errors are found."""
        mock_get_files.return_value = [Path("README.md")]

        mock_result = Mock()
        mock_result.returncode = 1  # Codespell returns non-zero on errors
        mock_run.return_value = mock_result

        result = main()

        assert result == 1

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    def test_main_no_files(self, mock_get_files, capsys):
        """Test main with no git-tracked files."""
        mock_get_files.return_value = []

        result = main()

        captured = capsys.readouterr()
        assert result == 1
        assert "No git-tracked files found" in captured.err

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_codespell_not_found(self, mock_run, mock_get_files):
        """Test handling when codespell is not found."""
        mock_get_files.return_value = [Path("README.md")]

        mock_run.side_effect = FileNotFoundError()

        result = main()

        assert result == 127

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_with_custom_args(self, mock_run, mock_get_files):
        """Test main with custom arguments."""
        mock_get_files.return_value = [Path("README.md")]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = main(["--ignore-words-list", "foo,bar"])

        assert result == 0

        # Verify custom args were passed
        call_args = mock_run.call_args[0][0]
        assert "--ignore-words-list" in call_args
        assert "foo,bar" in call_args

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_with_write_changes_flag(self, mock_run, mock_get_files):
        """Test that --write-changes is always included."""
        mock_get_files.return_value = [Path("README.md")]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = main()

        assert result == 0

        # Verify --write-changes is in command
        call_args = mock_run.call_args[0][0]
        assert "--write-changes" in call_args

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_exception_handling(self, mock_run, mock_get_files):
        """Test exception handling in codespell execution."""
        mock_get_files.return_value = [Path("README.md")]

        mock_run.side_effect = Exception("Unexpected error")

        result = main()

        assert result == 1

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_with_multiple_files(self, mock_run, mock_get_files):
        """Test main with multiple files."""
        mock_get_files.return_value = [
            Path("README.md"),
            Path("docs/guide.md"),
            Path("src/module.py"),
        ]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = main()

        assert result == 0

        # Verify all files are passed to codespell
        call_args = mock_run.call_args[0][0]
        assert "README.md" in call_args
        assert "docs/guide.md" in call_args
        assert "src/module.py" in call_args

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_absolute_paths(self, mock_run, mock_get_files, tmp_path):
        """Test main with absolute paths."""
        test_file = tmp_path / "README.md"
        mock_get_files.return_value = [test_file]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = main()

        assert result == 0

        # Verify absolute path is used
        call_args = mock_run.call_args[0][0]
        assert str(test_file) in call_args
