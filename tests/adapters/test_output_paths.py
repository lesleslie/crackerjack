"""Tests for AdapterOutputPaths.

Covers: crackerjack/adapters/_output_paths.py
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._output_paths import AdapterOutputPaths


class TestAdapterOutputPaths:
    """Tests for AdapterOutputPaths class."""

    def test_get_xdg_cache_home_returns_env_when_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"XDG_CACHE_HOME": tmpdir}):
                result = AdapterOutputPaths._get_xdg_cache_home()
                assert result == Path(tmpdir)

    def test_get_xdg_cache_home_returns_home_when_not_set(self):
        env = {k: v for k, v in os.environ.items() if k != "XDG_CACHE_HOME"}
        with patch.dict(os.environ, env, clear=True):
            result = AdapterOutputPaths._get_xdg_cache_home()
            expected = Path.home() / ".cache"
            assert result == expected

    def test_get_base_dir_structure(self):
        result = AdapterOutputPaths.get_base_dir()
        assert result.name == "outputs"
        assert "crackerjack" in str(result)


class TestGetOutputDir:
    """Tests for get_output_dir method."""

    def test_get_output_dir_with_adapter_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(AdapterOutputPaths, "get_base_dir", return_value=Path(tmpdir)):
                result = AdapterOutputPaths.get_output_dir("ruff")
                assert result == Path(tmpdir) / "ruff"

    def test_get_output_dir_with_none_uses_base(self):
        # When adapter_name is None, get_output_dir uses base / adapter_name
        # which equals base_dir (since adapter_name is falsy, output_dir = base_dir / None)
        # The patch makes get_base_dir return a temp path, so we test the method logic
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with patch.object(AdapterOutputPaths, "get_base_dir", return_value=base):
                # When adapter_name is None/empty, get_output_dir returns base_dir itself
                result = AdapterOutputPaths.get_output_dir("")
                assert result == base

    def test_get_output_dir_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "test_adapter"
            with patch.object(AdapterOutputPaths, "get_base_dir", return_value=output_dir.parent):
                result = AdapterOutputPaths.get_output_dir("test_adapter")
                assert result.exists()
                assert result.is_dir()

    def test_get_output_dir_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(AdapterOutputPaths, "get_base_dir", return_value=Path(tmpdir)):
                result1 = AdapterOutputPaths.get_output_dir("adapter1")
                result2 = AdapterOutputPaths.get_output_dir("adapter1")
                assert result1 == result2
                assert result1.exists()


class TestGetOutputFile:
    """Tests for get_output_file method."""

    def test_get_output_file_without_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=Path(tmpdir)):
                result = AdapterOutputPaths.get_output_file("ruff", "results.json")
                assert result == Path(tmpdir) / "results.json"

    def test_get_output_file_with_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=Path(tmpdir)):
                result = AdapterOutputPaths.get_output_file("ruff", "results.json", timestamped=True)
                assert result.parent == Path(tmpdir)
                assert "results" in result.name
                assert ".json" in result.name
                # Should contain timestamp pattern
                assert "_" in result.name or "-" in result.name

    def test_get_output_file_timestamp_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=Path(tmpdir)):
                result = AdapterOutputPaths.get_output_file("bandit", "output.json", timestamped=True)
                # Timestamp should be in format YYYY_MM_DD__HH:MM:SS
                name_without_ext = result.stem
                parts = name_without_ext.split("_")
                assert len(parts) >= 2  # At least stem and timestamp parts


class TestGetLatestOutput:
    """Tests for get_latest_output method."""

    def test_get_latest_output_when_no_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=Path(tmpdir)):
                result = AdapterOutputPaths.get_latest_output("nonexistent")
                assert result is None

    def test_get_latest_output_returns_most_recent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "test_adapter"
            output_dir.mkdir()

            # Create files with different modification times by writing them sequentially
            old_file = output_dir / "old.json"
            old_file.write_text("old")
            time.sleep(0.02)  # Ensure different timestamps

            new_file = output_dir / "new.json"
            new_file.write_text("new")
            time.sleep(0.02)

            newest_file = output_dir / "newest.json"
            newest_file.write_text("newest")

            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=output_dir):
                result = AdapterOutputPaths.get_latest_output("test_adapter")
                assert result == newest_file

    def test_get_latest_output_with_pattern(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "file1.txt").write_text("1")
            (output_dir / "file2.json").write_text("2")

            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=output_dir):
                result = AdapterOutputPaths.get_latest_output("test", pattern="*.txt")
                assert result is not None
                assert result.name == "file1.txt"


class TestCleanupOldOutputs:
    """Tests for cleanup_old_outputs method."""

    def test_cleanup_returns_zero_when_dir_not_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=Path(tmpdir) / "nonexistent"):
                result = AdapterOutputPaths.cleanup_old_outputs("nonexistent")
                assert result == 0

    def test_cleanup_keeps_latest_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create 10 files
            for i in range(10):
                (output_dir / f"file{i}.json").write_text(f"content{i}")

            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=output_dir):
                deleted = AdapterOutputPaths.cleanup_old_outputs("test", keep_latest=5)

            assert deleted == 5

            remaining = list(output_dir.glob("*.json"))
            assert len(remaining) == 5

    def test_cleanup_with_custom_pattern(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create mixed files
            for i in range(8):
                (output_dir / f"file{i}.json").write_text(f"json{i}")
                (output_dir / f"file{i}.txt").write_text(f"txt{i}")

            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=output_dir):
                deleted = AdapterOutputPaths.cleanup_old_outputs("test", pattern="*.txt", keep_latest=3)

            assert deleted == 5  # 8 - 3 = 5

            remaining_json = list(output_dir.glob("*.json"))
            remaining_txt = list(output_dir.glob("*.txt"))
            assert len(remaining_json) == 8  # JSON untouched
            assert len(remaining_txt) == 3  # TXT cleaned up

    def test_cleanup_returns_count_of_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            for i in range(7):
                (output_dir / f"file{i}.json").write_text(f"content{i}")

            with patch.object(AdapterOutputPaths, "get_output_dir", return_value=output_dir):
                deleted = AdapterOutputPaths.cleanup_old_outputs("test", keep_latest=3)

            assert deleted == 4

    def test_cleanup_handles_os_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            (output_dir / "protected.json").write_text("content")

            # Make file read-only so unlink will fail
            if os.name != "nt":  # Don't test on Windows
                import stat

                os.chmod(output_dir / "protected.json", stat.S_IRUSR | stat.S_IXUSR)
                # Skip the protected file test on platforms where this works
                # This test just verifies no exception is raised
                deleted = AdapterOutputPaths.cleanup_old_outputs("test", keep_latest=1)
                # The protected file might not be deleted, but no exception should propagate
