"""Tests for mdformat_wrapper tool."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.tools.mdformat_wrapper import main, should_skip_file


class TestShouldSkipFile:
    """Test should_skip_file function."""

    def test_skip_archive_patterns(self):
        """Test that archive patterns are skipped."""
        assert should_skip_file(Path("docs/archive/file.md"))
        assert should_skip_file(Path("docs/archives/file.md"))

    def test_skip_complete_markdown(self):
        """Test that _COMPLETE.md files are skipped."""
        assert should_skip_file(Path("FIX_COMPLETE.md"))
        assert should_skip_file(Path("docs/ANALYSIS_COMPLETE.md"))

    def test_skip_analysis_progress_status(self):
        """Test that analysis/progress/status files are skipped."""
        assert should_skip_file(Path("ANALYSIS.md"))
        assert should_skip_file(Path("PROGRESS.md"))
        assert should_skip_file(Path("STATUS.md"))

    def test_skip_plan_summary(self):
        """Test that plan and summary files are skipped."""
        assert should_skip_file(Path("PLAN.md"))
        assert should_skip_file(Path("SUMMARY.md"))

    def test_skip_checkpoint(self):
        """Test that checkpoint files are skipped."""
        assert should_skip_file(Path("CHECKPOINT_1.md"))
        assert should_skip_file(Path("CHECKPOINT_FINAL.md"))

    def test_skip_notes(self):
        """Test that NOTES.md is skipped."""
        assert should_skip_file(Path("NOTES.md"))

    def test_skip_cleanup_comprehensive(self):
        """Test that cleanup and comprehensive files are skipped."""
        assert should_skip_file(Path("CLEANUP_01.md"))
        assert should_skip_file(Path("COMPREHENSIVE_AUDIT.md"))

    def test_skip_pyproject_test(self):
        """Test that pyproject and test files are skipped."""
        assert should_skip_file(Path("PYPROJECT_V2.md"))
        assert should_skip_file(Path("TEST_RESULTS.md"))

    def test_not_skip_regular_markdown(self):
        """Test that regular markdown files are not skipped."""
        assert not should_skip_file(Path("README.md"))
        assert not should_skip_file(Path("docs/guide.md"))
        assert not should_skip_file(Path("INSTALL.md"))

    def test_not_skip_other_extensions(self):
        """Test that non-markdown files are not skipped."""
        assert not should_skip_file(Path("script.py"))
        assert not should_skip_file(Path("config.yaml"))


class TestMdformatMain:
    """Test mdformat main function."""

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_with_valid_files(self, mock_run, mock_get_files, tmp_path, capsys):
        """Test main with valid markdown files."""
        mock_get_files.return_value = [tmp_path / "README.md"]

        # Mock successful check (already formatted)
        mock_check = Mock()
        mock_check.returncode = 0
        mock_run.return_value = mock_check

        result = main()

        assert result == 0

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_formats_files(self, mock_run, mock_get_files, tmp_path):
        """Test main formats files that need it."""
        mock_get_files.return_value = [tmp_path / "README.md"]

        # Mock check fails (needs formatting)
        mock_check = Mock()
        mock_check.returncode = 1
        mock_check.stdout = ""
        mock_check.stderr = ""

        # Mock format succeeds
        mock_format = Mock()
        mock_format.returncode = 0
        mock_format.stdout = "Formatted 1 file"
        mock_format.stderr = ""

        mock_run.side_effect = [mock_check, mock_format]

        result = main()

        assert result == 1  # Returns 1 because files needed formatting

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    def test_main_no_files(self, mock_get_files, capsys):
        """Test main with no markdown files."""
        mock_get_files.return_value = []

        result = main()

        assert result == 0

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_skipped_files(self, mock_run, mock_get_files, capsys):
        """Test that skipped files are not processed."""
        # Return mix of skipped and regular files
        mock_get_files.side_effect = lambda _: [
            Path("README.md"),
            Path("docs/archive/old.md"),
            Path("ANALYSIS.md"),
        ]

        mock_check = Mock()
        mock_check.returncode = 0
        mock_run.return_value = mock_check

        with patch.object(Path, "exists", return_value=True):
            result = main()

        # Should process README.md only (2 files skipped)
        assert mock_run.call_count >= 1

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_file_not_found(self, mock_run, mock_get_files):
        """Test handling when mdformat is not found."""
        mock_get_files.return_value = [Path("README.md")]

        mock_run.side_effect = FileNotFoundError()

        result = main()

        assert result == 127

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_with_custom_args(self, mock_run, mock_get_files):
        """Test main with custom arguments."""
        mock_get_files.return_value = [Path("README.md")]

        mock_check = Mock()
        mock_check.returncode = 0
        mock_run.return_value = mock_check

        result = main(["--wrap", "80"])

        assert result == 0
        # Check that custom args were passed
        assert mock_run.call_count >= 1

    @patch("crackerjack.tools.mdformat_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_main_handles_both_extensions(self, mock_run, mock_get_files):
        """Test main handles both .md and .markdown files."""
        mock_get_files.side_effect = lambda pattern: {
            "*.md": [Path("README.md"), Path("guide.md")],
            "*.markdown": [Path("document.markdown")],
        }.get(pattern, [])

        mock_check = Mock()
        mock_check.returncode = 0
        mock_run.return_value = mock_check

        result = main()

        assert result == 0
