from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from crackerjack.config.settings import FileChunkingSettings
from crackerjack.services.file_chunker import FileChunker

if TYPE_CHECKING:
    pass


def _make_files(tmp_path: Path, count: int, name_template: str = "f{}.py") -> list[Path]:
    """Create ``count`` dummy files under ``tmp_path`` and return their paths."""
    files: list[Path] = []
    for i in range(count):
        p = tmp_path / name_template.format(i)
        p.write_text(f"content {i}\n")
        files.append(p)
    return files


class TestFileChunkerInit:
    """FileChunker construction and configuration plumbing."""

    def test_defaults(self) -> None:
        chunker = FileChunker()
        assert chunker.chunk_size == 50
        assert chunker.overlap_percentage == 10
        assert chunker.settings is None

    def test_explicit_values(self) -> None:
        chunker = FileChunker(chunk_size=20, overlap_percentage=25)
        assert chunker.chunk_size == 20
        assert chunker.overlap_percentage == 25

    def test_settings_overrides_explicit(self) -> None:
        settings = FileChunkingSettings(chunk_size=7, overlap_percentage=50)
        chunker = FileChunker(chunk_size=999, overlap_percentage=0, settings=settings)
        assert chunker.chunk_size == 7
        assert chunker.overlap_percentage == 50
        assert chunker.settings is settings

    def test_settings_enabled_flag(self) -> None:
        settings = FileChunkingSettings(enabled=True)
        chunker = FileChunker(settings=settings)
        assert chunker.settings is not None
        assert chunker.settings.enabled is True


class TestChunkFilesNoOp:
    """Paths through ``chunk_files`` that produce 0 or 1 chunk."""

    def test_empty_input_returns_empty_list(self) -> None:
        chunker = FileChunker()
        assert chunker.chunk_files([]) == []

    def test_under_threshold_returns_single_chunk(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=10)
        files = _make_files(tmp_path, 5)
        result = chunker.chunk_files(files)
        assert result == [files]

    def test_equal_to_threshold_returns_single_chunk(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=10)
        files = _make_files(tmp_path, 10)
        result = chunker.chunk_files(files)
        assert result == [files]

    def test_default_chunk_size_no_op_on_50_files(self, tmp_path: Path) -> None:
        chunker = FileChunker()
        files = _make_files(tmp_path, 50)
        result = chunker.chunk_files(files)
        assert len(result) == 1
        assert result[0] == files

    def test_no_op_preserves_order(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=10)
        files = _make_files(tmp_path, 7)
        assert chunker.chunk_files(files)[0] is files


class TestChunkFilesSplitting:
    """Behaviour when the input is larger than ``chunk_size``."""

    def test_basic_split_without_overlap(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=5, overlap_percentage=0)
        files = _make_files(tmp_path, 12)
        chunks = chunker.chunk_files(files)
        # 12 files / chunk_size 5 -> 3 chunks (5, 5, 2)
        assert len(chunks) == 3
        assert len(chunks[0]) == 5
        assert len(chunks[1]) == 5
        assert len(chunks[2]) == 2

    def test_basic_split_with_default_overlap(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=10, overlap_percentage=10)
        files = _make_files(tmp_path, 25)
        chunks = chunker.chunk_files(files)
        # overlap_count = max(1, 10 * 10 / 100) = 1
        assert len(chunks) == 3

    def test_overlap_includes_previous_files(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=10, overlap_percentage=20)
        files = _make_files(tmp_path, 25)
        chunks = chunker.chunk_files(files)
        # overlap_count = 10 * 20 / 100 = 2
        assert len(chunks) == 3
        # Second chunk should start with files[8] and files[9] (the last 2 from chunk 0)
        assert chunks[1][:2] == files[8:10]
        # Third chunk should start with last 2 of second chunk's pre-overlap content
        assert chunks[2][:2] == files[16:18]

    def test_first_chunk_has_no_overlap_prefix(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=10, overlap_percentage=20)
        files = _make_files(tmp_path, 30)
        chunks = chunker.chunk_files(files)
        assert chunks[0] == files[0:10]

    def test_overlap_clamped_to_start(self, tmp_path: Path) -> None:
        """When chunk_size is tiny and overlap is large, overlap_start clamps to 0."""
        chunker = FileChunker(chunk_size=3, overlap_percentage=100)
        files = _make_files(tmp_path, 5)
        chunks = chunker.chunk_files(files)
        # overlap_count = 3 * 100 / 100 = 3
        # First chunk: files[0:3]
        # Second chunk: overlap_start = max(0, 3-3) = 0 -> files[0:3] + files[3:5]
        assert len(chunks) == 2
        assert chunks[0] == files[0:3]
        assert chunks[1] == files[0:5]

    def test_split_covers_all_files_with_overlap_duplication(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=4, overlap_percentage=50)
        files = _make_files(tmp_path, 8)
        chunks = chunker.chunk_files(files)
        # overlap_count = 4 * 50 / 100 = 2
        # chunk 0: [0:4] -> 4 files
        # chunk 1: [2:6] -> 4 files (2 overlap + 2 new)
        # chunk 2: [4:8] -> 4 files (2 overlap + 2 new)
        assert len(chunks) == 3
        # Each file from index 2 onward should appear in at least one chunk
        # Index 0 and 1 only appear in chunk 0
        for f in files[2:]:
            assert any(f in chunk for chunk in chunks)

    def test_very_large_input(self, tmp_path: Path) -> None:
        """Larger file list still terminates and produces a sensible number of chunks."""
        chunker = FileChunker(chunk_size=20, overlap_percentage=10)
        files = _make_files(tmp_path, 200)
        chunks = chunker.chunk_files(files)
        # overlap_count = 2
        # With 200 files and chunk_size 20, the loop iterates multiple times
        assert len(chunks) > 1
        # The very last chunk should include the final file
        assert files[-1] in chunks[-1]

    def test_overlap_zero_still_advances(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=4, overlap_percentage=0)
        files = _make_files(tmp_path, 9)
        chunks = chunker.chunk_files(files)
        # 9 files / chunk_size 4 = 3 chunks (4, 4, 1)
        assert len(chunks) == 3
        assert len(chunks[2]) == 1
        assert chunks[2] == files[8:9]

    def test_input_list_is_not_mutated(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=3, overlap_percentage=20)
        files = _make_files(tmp_path, 10)
        snapshot = list(files)
        chunker.chunk_files(files)
        assert files == snapshot


class TestShouldChunkFiles:
    """Decision boundary for ``should_chunk_files``."""

    def test_returns_false_when_below_threshold(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=5)
        files = _make_files(tmp_path, 5)
        assert chunker.should_chunk_files(files) is False

    def test_returns_true_when_above_threshold(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=5)
        files = _make_files(tmp_path, 6)
        assert chunker.should_chunk_files(files) is True

    def test_returns_false_for_empty(self) -> None:
        chunker = FileChunker()
        assert chunker.should_chunk_files([]) is False

    def test_settings_disabled_forces_false(self, tmp_path: Path) -> None:
        settings = FileChunkingSettings(enabled=False, chunk_size=2)
        chunker = FileChunker(settings=settings)
        files = _make_files(tmp_path, 100)
        assert chunker.should_chunk_files(files) is False

    def test_settings_enabled_uses_chunk_size(self, tmp_path: Path) -> None:
        settings = FileChunkingSettings(enabled=True, chunk_size=2)
        chunker = FileChunker(settings=settings)
        files = _make_files(tmp_path, 5)
        assert chunker.should_chunk_files(files) is True


class TestEstimateParallelBenefit:
    """Shape and values of the benefit-estimate dict."""

    def test_empty_input_returns_defaults(self) -> None:
        chunker = FileChunker()
        result = chunker.estimate_parallel_benefit([])
        assert result == {
            "files_per_chunk": 0,
            "chunks_per_worker": 0,
            "speedup_factor": 1.0,
        }

    def test_single_chunk_no_chunking(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=10)
        files = _make_files(tmp_path, 5)
        result = chunker.estimate_parallel_benefit(files, workers=2)
        # 1 chunk, 5 files
        assert result["files_per_chunk"] == 5.0
        assert result["chunks_per_worker"] == 0.5
        # speedup_factor = min(2, 1) = 1
        assert result["speedup_factor"] == 1.0

    def test_multi_chunk_speedup(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=5, overlap_percentage=0)
        files = _make_files(tmp_path, 20)
        result = chunker.estimate_parallel_benefit(files, workers=4)
        # 4 chunks of 5 files each
        assert result["files_per_chunk"] == 5.0
        assert result["files_per_worker"] == 5.0  # 20 / 4
        assert result["chunks_per_worker"] == 1.0
        # speedup_factor = min(4, 4) = 4
        assert result["speedup_factor"] == 4.0

    def test_workers_clamp_speedup(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=5, overlap_percentage=0)
        files = _make_files(tmp_path, 15)
        result = chunker.estimate_parallel_benefit(files, workers=100)
        # 3 chunks; speedup_factor = min(100, 3) = 3
        assert result["speedup_factor"] == 3.0

    def test_default_workers_is_six(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=5, overlap_percentage=0)
        files = _make_files(tmp_path, 30)
        result = chunker.estimate_parallel_benefit(files)
        # 6 chunks of 5 -> files_per_worker = 30/6 = 5
        assert result["files_per_worker"] == 5.0

    def test_returns_only_known_keys(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=5, overlap_percentage=0)
        files = _make_files(tmp_path, 20)
        result = chunker.estimate_parallel_benefit(files, workers=4)
        assert set(result.keys()) == {
            "files_per_chunk",
            "files_per_worker",
            "chunks_per_worker",
            "speedup_factor",
        }


class TestLogging:
    """Smoke checks on logger usage (no assertion on log content; just that it exists)."""

    def test_module_logger_is_named(self) -> None:
        from crackerjack.services import file_chunker

        assert isinstance(file_chunker.logger, logging.Logger)
        assert file_chunker.logger.name == "crackerjack.services.file_chunker"

    def test_debug_log_on_empty(self, caplog: pytest.LogCaptureFixture) -> None:
        chunker = FileChunker()
        with caplog.at_level(logging.DEBUG, logger="crackerjack.services.file_chunker"):
            chunker.chunk_files([])
        assert "No files to chunk" in caplog.text

    def test_info_log_on_real_chunking(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        chunker = FileChunker(chunk_size=3, overlap_percentage=0)
        files = _make_files(tmp_path, 10)
        with caplog.at_level(logging.INFO, logger="crackerjack.services.file_chunker"):
            chunker.chunk_files(files)
        assert "Split 10 files" in caplog.text
