"""Tests for IncrementalScanner service."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from crackerjack.services.incremental_scanner import IncrementalScanner, ScanStrategy


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    """Create a temporary repository path."""
    return tmp_path


@pytest.fixture
def scanner(repo_path: Path) -> IncrementalScanner:
    """Create IncrementalScanner instance."""
    return IncrementalScanner(repo_path=repo_path)


class TestIncrementalScannerInit:
    """Test IncrementalScanner initialization."""

    def test_init_with_defaults(self, repo_path: Path) -> None:
        """Test initialization with default parameters."""
        scanner = IncrementalScanner(repo_path=repo_path)

        assert scanner.repo_path == repo_path
        assert scanner.full_scan_interval_days == 7

    def test_init_with_custom_interval(self, repo_path: Path) -> None:
        """Test initialization with custom full scan interval."""
        scanner = IncrementalScanner(
            repo_path=repo_path,
            full_scan_interval_days=14,
        )

        assert scanner.full_scan_interval_days == 14


class TestGetScanStrategy:
    """Test get_scan_strategy() method."""

    def test_force_full_scan(self, scanner: IncrementalScanner, repo_path: Path) -> None:
        """Test force_full parameter triggers full scan."""
        # Create some Python files
        (repo_path / "test1.py").touch()
        (repo_path / "test2.py").touch()

        strategy, files = scanner.get_scan_strategy(
            tool_name="test-tool",
            force_full=True,
        )

        assert strategy == "full"
        assert len(files) == 2

    def test_incremental_with_git_changes(
        self,
        scanner: IncrementalScanner,
        repo_path: Path,
    ) -> None:
        """Test incremental scan when git reports changes."""
        # Create test files
        file1 = repo_path / "changed.py"
        file2 = repo_path / "other.py"
        file1.touch()
        file2.touch()

        # Mock git to return changes
        # Mock git to return changes by setting method directly
        original_method = scanner._get_changed_files_git
        scanner._get_changed_files_git = lambda: [file1]

        # Mock _should_force_full_scan to return False so incremental path is taken
        with patch.object(
            scanner,
            "_should_force_full_scan",
            return_value=False,
        ):
            strategy, files = scanner.get_scan_strategy(
                    tool_name="test-tool",
                    force_full=False,
                )

            # Verify mock was called
            assert scanner._get_changed_files_git is not original_method

            assert strategy == "incremental"
            assert files == [file1]

    def test_fallback_to_full_when_no_git_changes(
        self, scanner: IncrementalScanner,
        repo_path: Path,
    ) -> None:
        """Test fallback to full scan when git has no changes."""
        # Create test files
        (repo_path / "file1.py").touch()
        (repo_path / "file2.py").touch()

        # Mock git to return None (no changes/unavailable)
        with patch.object(
            scanner,
            "_get_changed_files_git",
            return_value=None,
        ):
            strategy, files = scanner.get_scan_strategy(
                tool_name="test-tool",
                force_full=False,
            )

            assert strategy == "full"
            assert len(files) == 2


class TestGetChangedFilesGit:
    """Test _get_changed_files_git() method."""

    def test_git_diff_success(self, scanner: IncrementalScanner, repo_path: Path) -> None:
        """Test successful git diff execution."""
        # Create test files
        (repo_path / "file1.py").touch()
        (repo_path / "file2.py").touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="file1.py\nfile2.py\n",
                stderr="",
            )

            changed = scanner._get_changed_files_git()

            assert len(changed) == 2
            mock_run.assert_called_once()

    def test_git_diff_failure(self, scanner: IncrementalScanner) -> None:
        """Test git diff failure handling."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="fatal: not a git repository",
            )

            changed = scanner._get_changed_files_git()

            assert changed is None

    def test_git_diff_filters_non_python(
        self, scanner: IncrementalScanner,
        repo_path: Path,
    ) -> None:
        """Test that only .py files are returned."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="file1.py\nfile2.md\nfile3.py\nfile4.txt\n",
                stderr="",
            )

            changed = scanner._get_changed_files_git()

            assert len(changed) == 2
            assert all(f.suffix == ".py" for f in changed)

    def test_git_unavailable(self, scanner: IncrementalScanner) -> None:
        """Test handling when git is not available."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            changed = scanner._get_changed_files_git()

            assert changed is None


class TestShouldForceFullScan:
    """Test _should_force_full_scan() method."""

    def test_no_marker_file(self, scanner: IncrementalScanner) -> None:
        """Test that missing marker file triggers full scan."""
        result = scanner._should_force_full_scan("test-tool")

        assert result is True

    def test_old_marker_triggers_full_scan(
        self, scanner: IncrementalScanner,
        repo_path: Path,
    ) -> None:
        """Test that old marker (>7 days) triggers full scan."""
        import time
        from datetime import datetime, timedelta

        marker_dir = repo_path / ".crackerjack"
        marker_dir.mkdir(parents=True, exist_ok=True)

        marker_file = marker_dir / "test-tool_last_full.txt"
        marker_file.touch()

        # Set mtime to 10 days ago
        old_time = time.time() - (10 * 24 * 3600)
        import os

        os.utime(marker_file, (old_time, old_time))

        result = scanner._should_force_full_scan("test-tool")

        assert result is True

    def test_recent_marker_no_full_scan(
        self, scanner: IncrementalScanner,
        repo_path: Path,
    ) -> None:
        """Test that recent marker (<7 days) doesn't trigger full scan."""
        marker_dir = repo_path / ".crackerjack"
        marker_dir.mkdir(parents=True, exist_ok=True)

        marker_file = marker_dir / "test-tool_last_full.txt"
        marker_file.touch()

        result = scanner._should_force_full_scan("test-tool")

        assert result is False


class TestGetAllPythonFiles:
    """Test _get_all_python_files() method."""

    def test_finds_python_files(
        self, scanner: IncrementalScanner,
        repo_path: Path,
    ) -> None:
        """Test finding all Python files in repository."""
        # Create test structure
        (repo_path / "file1.py").touch()
        (repo_path / "file2.py").touch()
        (repo_path / "subdir").mkdir()
        (repo_path / "subdir" / "file3.py").touch()
        (repo_path / "file.txt").touch()
        (repo_path / "file.md").touch()

        files = scanner._get_all_python_files()

        assert len(files) == 3
        assert all(f.suffix == ".py" for f in files)

    def test_empty_repository(
        self, scanner: IncrementalScanner,
        repo_path: Path,
    ) -> None:
        """Test handling empty repository."""
        files = scanner._get_all_python_files()

        assert files == []
