"""Tests for MarkerTracker service."""

from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.services.marker_tracker import MarkerTracker


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    """Create a temporary repository path."""
    return tmp_path


@pytest.fixture
def tracker(repo_path: Path) -> MarkerTracker:
    """Create MarkerTracker instance."""
    return MarkerTracker(repo_path=repo_path)


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


class TestMarkerTrackerInit:
    """Test MarkerTracker initialization."""

    def test_init_creates_database(self, repo_path: Path) -> None:
        """Test that initialization creates database."""
        tracker = MarkerTracker(repo_path=repo_path)

        assert tracker.db_path.exists()
        assert tracker.db_path.name == "scan_markers.db"

    def test_init_creates_crackerjack_dir(self, repo_path: Path) -> None:
        """Test that initialization creates .crackerjack directory."""
        MarkerTracker(repo_path=repo_path)

        crackerjack_dir = repo_path / ".crackerjack"
        assert crackerjack_dir.exists()
        assert crackerjack_dir.is_dir()


class TestGetFilesNeedingScan:
    """Test get_files_needing_scan() method."""

    def test_first_scan_returns_all_files(
        self, tracker: MarkerTracker,
        sample_files: list[Path],
    ) -> None:
        """Test that first scan returns all files (no markers exist)."""
        files_needing_scan = tracker.get_files_needing_scan("test-tool", sample_files)

        assert len(files_needing_scan) == 3
        assert set(files_needing_scan) == set(sample_files)

    def test_unchanged_files_skipped(
        self, tracker: MarkerTracker,
        sample_files: list[Path],
    ) -> None:
        """Test that unchanged files are skipped on subsequent scan."""
        # Mark files as scanned
        tracker.mark_scanned("test-tool", sample_files)

        # Check again without modifying files
        files_needing_scan = tracker.get_files_needing_scan("test-tool", sample_files)

        assert len(files_needing_scan) == 0

    def test_modified_files_detected(
        self, tracker: MarkerTracker,
        sample_files: list[Path],
    ) -> None:
        """Test that modified files are detected."""
        # Mark files as scanned
        tracker.mark_scanned("test-tool", sample_files)

        # Modify one file
        sample_files[0].write_text("print('modified')")

        files_needing_scan = tracker.get_files_needing_scan("test-tool", sample_files)

        assert len(files_needing_scan) == 1
        assert sample_files[0] in files_needing_scan

    def test_per_tool_tracking(self, tracker: MarkerTracker, sample_files: list[Path]) -> None:
        """Test that tracking is separate per tool."""
        # Mark for tool1
        tracker.mark_scanned("tool1", sample_files)

        # Check for tool2 (should still need scan)
        files_needing_scan = tracker.get_files_needing_scan("tool2", sample_files)

        assert len(files_needing_scan) == 3

    def test_skips_missing_files(
        self, tracker: MarkerTracker,
        sample_files: list[Path],
    ) -> None:
        """Test that missing files are skipped."""
        # Add a non-existent file
        missing_file = sample_files[0].parent / "missing.py"
        all_files = sample_files + [missing_file]

        files_needing_scan = tracker.get_files_needing_scan("test-tool", all_files)

        assert len(files_needing_scan) == 3
        assert missing_file not in files_needing_scan


class TestMarkScanned:
    """Test mark_scanned() method."""

    def test_mark_scanned_stores_hashes(
        self, tracker: MarkerTracker,
        sample_files: list[Path],
    ) -> None:
        """Test that mark_scanned stores file hashes."""
        tracker.mark_scanned("test-tool", sample_files)

        # Verify files are marked
        files_needing_scan = tracker.get_files_needing_scan("test-tool", sample_files)
        assert len(files_needing_scan) == 0

    def test_mark_scanned_empty_list(self, tracker: MarkerTracker) -> None:
        """Test that marking empty list doesn't error."""
        tracker.mark_scanned("test-tool", [])
        # Should not raise

    def test_mark_scanned_updates_existing(
        self, tracker: MarkerTracker,
        sample_files: list[Path],
    ) -> None:
        """Test that re-marking updates existing hash."""
        # Mark files
        tracker.mark_scanned("test-tool", sample_files)

        # Modify and re-mark
        sample_files[0].write_text("new content")
        tracker.mark_scanned("test-tool", sample_files)

        # Should not need scan
        files_needing_scan = tracker.get_files_needing_scan("test-tool", sample_files)
        assert len(files_needing_scan) == 0


class TestMarkFullScanComplete:
    """Test mark_full_scan_complete() method."""

    def test_creates_marker_file(self, tracker: MarkerTracker) -> None:
        """Test that marker file is created."""
        tracker.mark_full_scan_complete("test-tool")

        marker_file = tracker.repo_path / ".crackerjack" / "test-tool_last_full.txt"
        assert marker_file.exists()

    def test_updates_existing_marker(self, tracker: MarkerTracker) -> None:
        """Test that existing marker is updated."""
        tracker.mark_full_scan_complete("test-tool")

        import time
        time.sleep(0.1)  # Small delay

        tracker.mark_full_scan_complete("test-tool")

        marker_file = tracker.repo_path / ".crackerjack" / "test-tool_last_full.txt"
        assert marker_file.exists()


class TestDatabaseErrors:
    """Test database error handling."""

    def test_get_files_handles_db_errors(
        self, tracker: MarkerTracker,
        sample_files: list[Path],
    ) -> None:
        """Test graceful handling of database errors."""
        # Corrupt database
        tracker.db_path.write_text("corrupted data")

        # Should fallback to returning all files
        files_needing_scan = tracker.get_files_needing_scan("test-tool", sample_files)

        assert len(files_needing_scan) == 3
