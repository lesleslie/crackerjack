"""Tests for codespell_wrapper tool."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from crackerjack.tools.codespell_wrapper import main


def test_codespell_no_files(monkeypatch):
    """Test codespell_wrapper with no git-tracked files."""
    # Mock get_git_tracked_files to return empty list
    with patch('crackerjack.tools.codespell_wrapper.get_git_tracked_files') as mock:
        mock.return_value = []
        result = main()
        assert result == 1, "Should return 1 when no files found"


def test_codespell_with_errors(monkeypatch):
    """Test codespell_wrapper when codespell finds errors."""
    # Mock a file path
    mock_file = Path("/tmp/test_file.py")

    with patch('crackerjack.tools.codespell_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            # Simulate codespell finding spelling errors
            mock_result = MagicMock()
            mock_result.returncode = 1  # Codespell found errors
            mock_run.return_value = mock_result

            result = main()
            assert result == 1, "Should return 1 when codespell finds errors"
            mock_run.assert_called_once()


def test_codespell_success(monkeypatch):
    """Test codespell_wrapper when codespell succeeds."""
    # Mock a file path
    mock_file = Path("/tmp/test_file.py")

    with patch('crackerjack.tools.codespell_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            # Simulate codespell succeeding (no spelling errors)
            mock_result = MagicMock()
            mock_result.returncode = 0  # Success
            mock_run.return_value = mock_result

            result = main()
            assert result == 0, "Should return 0 on success"
            mock_run.assert_called_once()


def test_codespell_not_installed(monkeypatch):
    """Test codespell_wrapper when codespell is not installed."""
    mock_file = Path("/tmp/test_file.py")

    with patch('crackerjack.tools.codespell_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            # Simulate FileNotFoundError (codespell not installed)
            mock_run.side_effect = FileNotFoundError()

            result = main()
            assert result == 127, "Should return 127 when codespell not found"


def test_codespell_with_custom_args(monkeypatch):
    """Test codespell_wrapper with custom command-line arguments."""
    mock_file = Path("/tmp/test_file.py")

    with patch('crackerjack.tools.codespell_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # Pass custom arguments
            result = main(['--ignore-words-list', 'foo,bar'])

            assert result == 0
            # Verify custom args were passed to codespell
            call_args = mock_run.call_args
            assert '--ignore-words-list' in call_args[0][0]
            assert 'foo,bar' in call_args[0][0]


def test_codespell_exception_handling(monkeypatch):
    """Test codespell_wrapper handles unexpected exceptions."""
    mock_file = Path("/tmp/test_file.py")

    with patch('crackerjack.tools.codespell_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            # Simulate unexpected exception
            mock_run.side_effect = Exception("Unexpected error")

            result = main()
            assert result == 1, "Should return 1 on exception"
