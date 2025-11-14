"""Incremental execution with intelligent caching.

Phase 10.3.2: Implements file hash tracking and persistent caching to skip
unchanged files and reuse previous results.
"""

import hashlib
import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crackerjack.services.profiler import ToolProfiler


@dataclass
class FileHash:
    """File hash metadata."""

    path: str
    hash: str
    size: int
    modified_time: float


@dataclass
class CacheEntry:
    """Cached execution result."""

    tool_name: str
    file_hash: FileHash
    result: Any
    timestamp: float
    success: bool
    error_message: str | None = None


@dataclass
class ExecutionResult:
    """Result of incremental execution."""

    tool_name: str
    files_processed: int
    files_cached: int
    files_changed: int
    cache_hit_rate: float
    execution_time: float
    results: dict[str, Any] = field(default_factory=dict)

    @property
    def cache_effective(self) -> bool:
        """Whether caching was effective (>50% hit rate)."""
        return self.cache_hit_rate >= 50.0


class IncrementalExecutor:
    """Executes tools incrementally with intelligent caching."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_seconds: int = 86400,  # 24 hours
        profiler: ToolProfiler | None = None,
    ):
        """Initialize incremental executor.

        Args:
            cache_dir: Directory for cache storage
            ttl_seconds: Time-to-live for cache entries (default: 24 hours)
            profiler: Optional profiler for performance tracking
        """
        self.cache_dir = cache_dir or Path.cwd() / ".crackerjack" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.profiler = profiler
        self._cache: dict[str, CacheEntry] = {}
        self._file_hashes: dict[str, FileHash] = {}
        self._load_cache()

    def _compute_file_hash(self, file_path: Path) -> FileHash:
        """Compute hash for a file.

        Args:
            file_path: Path to file

        Returns:
            FileHash with metadata
        """
        try:
            content = file_path.read_bytes()
            hash_value = hashlib.sha256(content).hexdigest()
            stat = file_path.stat()

            return FileHash(
                path=str(file_path),
                hash=hash_value,
                size=stat.st_size,
                modified_time=stat.st_mtime,
            )
        except OSError:
            # Return empty hash for files that can't be read
            return FileHash(
                path=str(file_path),
                hash="",
                size=0,
                modified_time=0.0,
            )

    def _cache_key(self, tool_name: str, file_hash: FileHash) -> str:
        """Generate cache key.

        Args:
            tool_name: Name of the tool
            file_hash: File hash metadata

        Returns:
            Cache key string
        """
        return f"{tool_name}:{file_hash.hash}"

    def _load_cache(self) -> None:
        """Load cache from disk."""
        cache_file = self.cache_dir / "incremental_cache.json"
        if not cache_file.exists():
            return

        try:
            data = json.loads(cache_file.read_text())
            import time

            current_time = time.time()

            for entry_data in data.get("entries", []):
                # Skip expired entries
                if current_time - entry_data["timestamp"] > self.ttl_seconds:
                    continue

                file_hash = FileHash(**entry_data["file_hash"])
                entry = CacheEntry(
                    tool_name=entry_data["tool_name"],
                    file_hash=file_hash,
                    result=entry_data["result"],
                    timestamp=entry_data["timestamp"],
                    success=entry_data["success"],
                    error_message=entry_data.get("error_message"),
                )

                key = self._cache_key(entry.tool_name, file_hash)
                self._cache[key] = entry
        except (json.JSONDecodeError, KeyError, OSError):
            # Corrupted cache - start fresh
            self._cache = {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        cache_file = self.cache_dir / "incremental_cache.json"

        data = {
            "entries": [
                {
                    "tool_name": entry.tool_name,
                    "file_hash": {
                        "path": entry.file_hash.path,
                        "hash": entry.file_hash.hash,
                        "size": entry.file_hash.size,
                        "modified_time": entry.file_hash.modified_time,
                    },
                    "result": entry.result,
                    "timestamp": entry.timestamp,
                    "success": entry.success,
                    "error_message": entry.error_message,
                }
                for entry in self._cache.values()
            ]
        }

        with suppress(OSError):
            cache_file.write_text(json.dumps(data, indent=2))

    def execute_incremental(
        self,
        tool_name: str,
        files: list[Path],
        tool_func: Callable[[Path], Any],
        force_rerun: bool = False,
    ) -> ExecutionResult:
        """Execute tool incrementally with caching.

        Args:
            tool_name: Name of the tool
            files: List of files to process
            tool_func: Function to execute on each file
            force_rerun: Skip cache and rerun all files

        Returns:
            ExecutionResult with statistics
        """
        import time

        start_time = time.perf_counter()

        files_cached = 0
        files_changed = 0
        results: dict[str, Any] = {}

        for file_path in files:
            # Compute current hash
            current_hash = self._compute_file_hash(file_path)
            cache_key = self._cache_key(tool_name, current_hash)

            # Check cache
            if not force_rerun and cache_key in self._cache:
                cached_entry = self._cache[cache_key]
                results[str(file_path)] = cached_entry.result
                files_cached += 1

                # Update profiler cache stats
                if self.profiler and tool_name in self.profiler.results:
                    self.profiler.results[tool_name].cache_hits += 1
            else:
                # Execute tool
                try:
                    result = tool_func(file_path)
                    success = True
                    error_msg = None
                except Exception as e:
                    result = None
                    success = False
                    error_msg = str(e)

                results[str(file_path)] = result
                files_changed += 1

                # Update profiler cache stats
                if self.profiler and tool_name in self.profiler.results:
                    self.profiler.results[tool_name].cache_misses += 1

                # Store in cache
                entry = CacheEntry(
                    tool_name=tool_name,
                    file_hash=current_hash,
                    result=result,
                    timestamp=time.time(),
                    success=success,
                    error_message=error_msg,
                )
                self._cache[cache_key] = entry

        # Calculate statistics
        total_files = len(files)
        cache_hit_rate = (files_cached / total_files * 100) if total_files > 0 else 0.0
        execution_time = time.perf_counter() - start_time

        # Save cache
        self._save_cache()

        return ExecutionResult(
            tool_name=tool_name,
            files_processed=total_files,
            files_cached=files_cached,
            files_changed=files_changed,
            cache_hit_rate=cache_hit_rate,
            execution_time=execution_time,
            results=results,
        )

    def get_changed_files(
        self,
        tool_name: str,
        files: list[Path],
    ) -> list[Path]:
        """Get list of files that have changed since last execution.

        Args:
            tool_name: Name of the tool
            files: List of files to check

        Returns:
            List of changed files
        """
        changed_files: list[Path] = []

        for file_path in files:
            current_hash = self._compute_file_hash(file_path)
            cache_key = self._cache_key(tool_name, current_hash)

            # If not in cache or hash differs, it's changed
            if cache_key not in self._cache:
                changed_files.append(file_path)

        return changed_files

    def invalidate_file(self, file_path: Path) -> int:
        """Invalidate all cache entries for a file.

        Args:
            file_path: Path to file

        Returns:
            Number of entries invalidated
        """
        file_str = str(file_path)
        invalidated = 0

        # Remove all cache entries for this file
        keys_to_remove = [
            key
            for key, entry in self._cache.items()
            if entry.file_hash.path == file_str
        ]

        for key in keys_to_remove:
            del self._cache[key]
            invalidated += 1

        if invalidated > 0:
            self._save_cache()

        return invalidated

    def clear_cache(self, tool_name: str | None = None) -> int:
        """Clear cache entries.

        Args:
            tool_name: Optional tool name to clear (clears all if None)

        Returns:
            Number of entries cleared
        """
        if tool_name is None:
            # Clear all
            count = len(self._cache)
            self._cache = {}
        else:
            # Clear specific tool
            keys_to_remove = [
                key
                for key, entry in self._cache.items()
                if entry.tool_name == tool_name
            ]
            count = len(keys_to_remove)
            for key in keys_to_remove:
                del self._cache[key]

        if count > 0:
            self._save_cache()

        return count

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_entries = len(self._cache)
        tools = {entry.tool_name for entry in self._cache.values()}
        success_count = sum(1 for entry in self._cache.values() if entry.success)

        return {
            "total_entries": total_entries,
            "unique_tools": len(tools),
            "success_rate": (success_count / total_entries * 100)
            if total_entries > 0
            else 0.0,
            "cache_size_mb": self._estimate_cache_size(),
        }

    def _estimate_cache_size(self) -> float:
        """Estimate cache size in MB.

        Returns:
            Estimated size in megabytes
        """
        cache_file = self.cache_dir / "incremental_cache.json"
        if cache_file.exists():
            return cache_file.stat().st_size / 1024 / 1024
        return 0.0
