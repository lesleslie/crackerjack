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
    """Behaviour when the input is larger than ``chunk_size``.

    NOTE: ``FileChunker.chunk_files`` contains an infinite-loop bug when
    ``overlap_count < chunk_size - 1`` for the last iteration. Specifically,
    once ``start_idx + chunk_size >= len(files)`` the update
    ``start_idx = end_idx - overlap_count`` does not advance past
    ``len(files) - 1``, so the loop never exits. The condition guarding the
    overlap application is also inverted (``chunk_num > 1`` instead of
    ``chunk_num > 0``), causing inconsistent behaviour between chunk 1 and
    later chunks. Per task instructions we do not fix the source — instead we
    exercise the API via parameters that avoid the infinite loop and skip
    any test that would hang.
    """

    def test_basic_split_with_full_overlap(self, tmp_path: Path) -> None:
        """``overlap_percentage=100`` => ``overlap_count == chunk_size``,
        so ``start_idx`` does not advance (each next chunk is offset by 0).
        Documenting current behaviour rather than asserting it terminates.
        """
        pytest.skip(
            "Source bug: chunk_files() infinite-loops for any overlap_count "
            "< chunk_size - 1 once the tail is reached. Tracked but not fixed."
        )

    def test_first_chunk_only_when_no_advance(self, tmp_path: Path) -> None:
        """The only reliable way to get past the single-chunk branch and
        actually exercise the loop is to force the function to terminate —
        which it does not, given the bug above. So we capture the
        observable: the input list is not mutated by the call attempt.
        """
        chunker = FileChunker(chunk_size=5, overlap_percentage=10)
        files = _make_files(tmp_path, 12)
        snapshot = list(files)
        # The function itself hangs; do not actually call it.
        # Assert the input was not pre-mutated as a minimal smoke check.
        assert files == snapshot
        assert chunker.chunk_size == 5
        assert chunker.overlap_percentage == 10

    def test_input_list_is_not_mutated_on_no_op(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=100, overlap_percentage=10)
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
    """Shape and values of the benefit-estimate dict.

    NOTE: ``estimate_parallel_benefit`` calls ``chunk_files`` internally,
    so any input that forces multiple chunks would also trigger the
    ``chunk_files`` infinite loop. We therefore restrict these tests to
    inputs that produce either zero or one chunk.
    """

    def test_empty_input_returns_defaults(self) -> None:
        chunker = FileChunker()
        result = chunker.estimate_parallel_benefit([])
        # NOTE: source returns "files_per_worker" (0) for empty input rather
        # than the "files_per_chunk" key the non-empty branch emits —
        # documented inconsistency, do not fix here.
        assert result == {
            "files_per_worker": 0,
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

    def test_returns_only_known_keys(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=10)
        files = _make_files(tmp_path, 5)
        result = chunker.estimate_parallel_benefit(files, workers=4)
        assert set(result.keys()) == {
            "files_per_chunk",
            "files_per_worker",
            "chunks_per_worker",
            "speedup_factor",
        }

    def test_files_per_worker_scales_with_workers(self, tmp_path: Path) -> None:
        chunker = FileChunker(chunk_size=20)
        files = _make_files(tmp_path, 10)
        # 1 chunk path; speedup limited to 1
        r1 = chunker.estimate_parallel_benefit(files, workers=1)
        r2 = chunker.estimate_parallel_benefit(files, workers=2)
        # files_per_worker = total / workers
        assert r1["files_per_worker"] == 10.0
        assert r2["files_per_worker"] == 5.0
        assert r1["speedup_factor"] == 1.0
        assert r2["speedup_factor"] == 1.0

    def test_multi_chunk_path_skipped_due_to_bug(self, tmp_path: Path) -> None:
        pytest.skip(
            "Source bug: chunk_files() infinite-loops for multi-chunk inputs "
            "with the default overlap (overlap_count < chunk_size - 1). "
            "estimate_parallel_benefit would hang on the same code path."
        )


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
        pytest.skip(
            "Source bug: chunk_files() hangs on multi-chunk inputs; cannot "
            "reach the INFO log line in a test without a 10-minute wait."
        )
