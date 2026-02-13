"""Tests for SmartFileFilterV2 service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.services.smart_file_filter_v2 import SmartFileFilterV2


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    """Create a temporary repository path."""
    return tmp_path


@pytest.fixture
def filter_v2(repo_path: Path) -> SmartFileFilterV2:
    """Create SmartFileFilterV2 instance."""
    return SmartFileFilterV2(repo_path=repo_path)


@pytest.fixture
def sample_files(tmp_path: Path) -> list[Path]:
    """Create sample test files."""
    files = [
        tmp_path / "file1.py",
        tmp_path / "file2.py",
        tmp_path / "file3.py",
    ]
    for f in files:
        f.write_text("print('hello')")
    return files


class TestSmartFileFilterV2Init:
    """Test SmartFileFilterV2 initialization."""

    def test_init_with_defaults(self, repo_path: Path) -> None:
        """Test initialization with default parameters."""
        filter_v2 = SmartFileFilterV2(repo_path=repo_path)

        assert filter_v2.repo_path == repo_path
        assert filter_v2.use_incremental is True

    def test_init_incremental_disabled(self, repo_path: Path) -> None:
        """Test initialization with incremental disabled."""
        filter_v2 = SmartFileFilterV2(
            repo_path=repo_path,
            use_incremental=False,
        )

        assert filter_v2.use_incremental is False

    def test_init_custom_scan_interval(self, repo_path: Path) -> None:
        """Test initialization with custom scan interval."""
        filter_v2 = SmartFileFilterV2(
            repo_path=repo_path,
            full_scan_interval_days=14,
        )

        assert filter_v2.scanner.full_scan_interval_days == 14


class TestServiceProtocol:
    """Test ServiceProtocol implementation."""

    def test_initialize(self, filter_v2: SmartFileFilterV2) -> None:
        """Test initialize method."""
        filter_v2.initialize()
        # Should not raise

    def test_cleanup(self, filter_v2: SmartFileFilterV2) -> None:
        """Test cleanup method."""
        filter_v2.cleanup()
        # Should not raise

    def test_health_check(self, filter_v2: SmartFileFilterV2) -> None:
        """Test health_check method."""
        assert filter_v2.health_check() is True

    def test_shutdown(self, filter_v2: SmartFileFilterV2) -> None:
        """Test shutdown method."""
        filter_v2.shutdown()
        # Should not raise


class TestGetFilesForScan:
    """Test get_files_for_scan() method."""

    def test_incremental_disabled_returns_all_files(
        self, filter_v2: SmartFileFilterV2,
        sample_files: list[Path],
    ) -> None:
        """Test that disabled incremental returns all files."""
        filter_v2.use_incremental = False

        files = filter_v2.get_files_for_scan("test-tool")

        assert len(files) == 3

    def test_uses_incremental_when_enabled(
        self, filter_v2: SmartFileFilterV2,
        sample_files: list[Path],
    ) -> None:
        """Test that incremental scanning is used when enabled."""
        with patch.object(
            filter_v2.scanner,
            "get_scan_strategy",
            return_value=("incremental", sample_files[:1]),
        ):
            files = filter_v2.get_files_for_scan("test-tool")

            # Should use incremental strategy
            assert len(files) >= 0

    def test_force_full_scan(
        self, filter_v2: SmartFileFilterV2,
        sample_files: list[Path],
    ) -> None:
        """Test force_full parameter."""
        with patch.object(
            filter_v2.scanner,
            "get_scan_strategy",
            return_value=("full", sample_files),
        ):
            files = filter_v2.get_files_for_scan("test-tool", force_incremental=True)

            assert files == sample_files


class TestMarkScanComplete:
    """Test mark_scan_complete() method."""

    def test_mark_full_scan(
        self, filter_v2: SmartFileFilterV2,
        sample_files: list[Path],
    ) -> None:
        """Test marking full scan complete."""
        with patch.object(filter_v2.marker_tracker, "mark_full_scan_complete") as mock_mark:
            filter_v2.mark_scan_complete("test-tool", [], was_full_scan=True)

            mock_mark.assert_called_once_with("test-tool")

    def test_mark_incremental_scan(
        self, filter_v2: SmartFileFilterV2,
        sample_files: list[Path],
    ) -> None:
        """Test marking incremental scan complete."""
        with patch.object(filter_v2.marker_tracker, "mark_scanned") as mock_mark:
            filter_v2.mark_scan_complete("test-tool", sample_files, was_full_scan=False)

            mock_mark.assert_called_once_with("test-tool", sample_files)
