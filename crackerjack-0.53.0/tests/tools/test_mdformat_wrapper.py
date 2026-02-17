"""Tests for mdformat_wrapper tool."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from crackerjack.tools.mdformat_wrapper import main, should_skip_file


def test_should_skip_file_archive_patterns():
    """Test should_skip_file with archive patterns."""
    # Test archive patterns
    assert should_skip_file(Path("docs/archive/test.md"))
    assert should_skip_file(Path("project/archives/old.md"))
    assert should_skip_file(Path("REMEDIATION_COMPLETE.md"))
    assert should_skip_file(Path("ANALYSIS_COMPLETE.md"))


def test_should_skip_file_special_files():
    """Test should_skip_file with special documentation files."""
    # Test special file patterns
    assert should_skip_file(Path("CHECKPOINT_2026-01-01.md"))
    assert should_skip_file(Path("CLEANUP_NEEDED.md"))
    assert should_skip_file(Path("COMPREHENSIVE_REVIEW.md"))
    assert should_skip_file(Path("PYPROJECT_LOCK.md"))
    assert should_skip_file(Path("TEST_RESULTS.md"))


def test_should_skip_file_regular_files():
    """Test should_skip_file with regular markdown files."""
    # Test files that should NOT be skipped
    assert not should_skip_file(Path("README.md"))
    assert not should_skip_file(Path("docs/guide.md"))
    assert not should_skip_file(Path("CHANGELOG.md"))
    assert not should_skip_file(Path("CONTRIBUTING.md"))


def test_mdformat_no_files(monkeypatch):
    """Test mdformat_wrapper with no git-tracked files."""
    with patch('crackerjack.tools.mdformat_wrapper.get_git_tracked_files') as mock:
        mock.return_value = []
        result = main()
        assert result == 0, "Should return 0 when no files found"


def test_mdformat_all_files_skipped(monkeypatch):
    """Test mdformat_wrapper when all files are skipped."""
    with patch('crackerjack.tools.mdformat_wrapper.get_git_tracked_files') as mock:
        # Return files that should all be skipped
        mock.return_value = [Path("ARCHIVE_COMPLETE.md"), Path("docs/archive/old.md")]
        result = main()
        assert result == 0, "Should return 0 when all files are skipped"


def test_mdformat_already_formatted(monkeypatch):
    """Test mdformat_wrapper when files are already formatted."""
    mock_file = Path("README.md")

    with patch('crackerjack.tools.mdformat_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            # Simulate files already formatted (check passes)
            mock_check = MagicMock()
            mock_check.returncode = 0
            mock_run.return_value = mock_check

            result = main()
            assert result == 0, "Should return 0 when already formatted"
            # Should only run check, not format
            assert mock_run.call_count == 1
            assert "--check" in mock_run.call_args[0][0]


def test_mdformat_needs_formatting(monkeypatch):
    """Test mdformat_wrapper when files need formatting."""
    mock_file = Path("README.md")

    with patch('crackerjack.tools.mdformat_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            # First call (check) fails, second call (format) succeeds
            mock_check = MagicMock()
            mock_check.returncode = 1  # Needs formatting
            mock_check.stdout = "Would format README.md"

            mock_format = MagicMock()
            mock_format.returncode = 1  # Format was applied (changes made)
            mock_format.stdout = ""
            mock_format.stderr = ""

            mock_run.side_effect = [mock_check, mock_format]

            result = main()
            assert result == 1, "Should return 1 when formatting was applied"
            assert mock_run.call_count == 2  # Check + Format


def test_mdformat_not_installed(monkeypatch):
    """Test mdformat_wrapper when mdformat is not installed."""
    mock_file = Path("README.md")

    with patch('crackerjack.tools.mdformat_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = main()
            assert result == 127, "Should return 127 when mdformat not found"


def test_mdformat_with_custom_args(monkeypatch):
    """Test mdformat_wrapper with custom command-line arguments."""
    mock_file = Path("README.md")

    with patch('crackerjack.tools.mdformat_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # Pass custom arguments
            result = main(['--wrap', '80'])

            assert result == 0
            # Verify custom args were passed
            call_args = mock_run.call_args
            assert '--wrap' in call_args[0][0]
            assert '80' in call_args[0][0]


def test_mdformat_exception_handling(monkeypatch):
    """Test mdformat_wrapper handles unexpected exceptions."""
    mock_file = Path("README.md")

    with patch('crackerjack.tools.mdformat_wrapper.get_git_tracked_files') as mock_files:
        mock_files.return_value = [mock_file]

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Unexpected error")

            result = main()
            assert result == 1, "Should return 1 on exception"
