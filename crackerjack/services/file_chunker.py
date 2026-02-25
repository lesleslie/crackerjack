from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.config.settings import FileChunkingSettings

logger = logging.getLogger(__name__)


class FileChunker:
    def __init__(
        self,
        chunk_size: int = 50,
        overlap_percentage: int = 10,
        settings: FileChunkingSettings | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.overlap_percentage = overlap_percentage
        self.settings = settings

        if settings:
            self.chunk_size = settings.chunk_size
            self.overlap_percentage = settings.overlap_percentage

    def chunk_files(self, files: list[Path]) -> list[list[Path]]:
        if not files:
            logger.debug("No files to chunk")
            return []

        if len(files) <= self.chunk_size:
            logger.debug(
                f"File count ({len(files)}) <= chunk size ({self.chunk_size}), "
                "not chunking"
            )
            return [files]

        chunks = []
        overlap_count = max(1, int(self.chunk_size * self.overlap_percentage / 100))

        start_idx = 0
        chunk_num = 0

        while start_idx < len(files):
            end_idx = min(start_idx + self.chunk_size, len(files))
            chunk = files[start_idx: end_idx]

            if chunk_num > 0 and overlap_count > 0:
                overlap_start = max(0, start_idx - overlap_count)
                overlap_files = files[overlap_start: start_idx]

                chunk = overlap_files + chunk

            chunks.append(chunk)
            chunk_num += 1

            start_idx = end_idx - overlap_count if chunk_num > 1 else end_idx

        logger.info(
            f"Split {len(files)} files into {len(chunks)} chunks "
            f"(size: {self.chunk_size}, overlap: {self.overlap_percentage}%)"
        )

        return chunks

    def should_chunk_files(self, files: list[Path]) -> bool:

        if self.settings and not self.settings.enabled:
            return False

        return len(files) > self.chunk_size

    def estimate_parallel_benefit(
        self,
        files: list[Path],
        workers: int = 6,
    ) -> dict[str, float]:
        if not files:
            return {
                "files_per_worker": 0,
                "chunks_per_worker": 0,
                "speedup_factor": 1.0,
            }

        total_files = len(files)
        chunks = len(self.chunk_files(files))

        files_per_chunk = total_files / chunks
        files_per_worker = total_files / workers
        chunks_per_worker = chunks / workers

        speedup_factor = min(workers, chunks)

        return {
            "files_per_chunk": round(files_per_chunk, 1),
            "files_per_worker": round(files_per_worker, 1),
            "chunks_per_worker": round(chunks_per_worker, 1),
            "speedup_factor": round(speedup_factor, 1),
        }
