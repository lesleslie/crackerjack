from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import aiofiles

from crackerjack.errors import FileError
from crackerjack.models.protocols import (
    EnhancedFileSystemServiceProtocol,
    ServiceProtocol,
)
from crackerjack.services.logging import LoggingContext

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class FileCache:
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,
    ) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, dict[str, Any]] = {}
        self._access_times: dict[str, float] = {}
        self.logger = logger

    def get(self, key: str) -> str | None:
        if key not in self._cache:
            return None

        cache_entry = self._cache[key]
        now = time.time()

        if now - cache_entry["timestamp"] > cache_entry["ttl"]:
            self._evict(key)
            return None

        self._access_times[key] = now
        self.logger.debug("Cache hit", key=key)
        content: str | None = cache_entry["content"]
        return content

    def put(self, key: str, content: str, ttl: float | None = None) -> None:
        if len(self._cache) >= self.max_size:
            self._evict_lru()

        now = time.time()
        self._cache[key] = {
            "content": content,
            "timestamp": now,
            "ttl": ttl or self.default_ttl,
            "size": len(content),
        }
        self._access_times[key] = now
        self.logger.debug("Cache put", key=key, size=len(content))

    def _evict(self, key: str) -> None:
        self._cache.pop(key, None)
        self._access_times.pop(key, None)

    def _evict_lru(self) -> None:
        if not self._access_times:
            return

        lru_key = min(self._access_times, key=lambda k: self._access_times.get(k, 0.0))
        self._evict(lru_key)
        self.logger.debug("Cache LRU eviction", key=lru_key)

    def clear(self) -> None:
        self._cache.clear()
        self._access_times.clear()
        self.logger.debug("Cache cleared")

    def get_stats(self) -> dict[str, Any]:
        total_size = sum(entry["size"] for entry in self._cache.values())
        return {
            "entries": len(self._cache),
            "max_size": self.max_size,
            "total_content_size": total_size,
            "memory_usage_mb": total_size / (1024 * 1024),
        }


class BatchFileOperations:
    def __init__(
        self,
        batch_size: int = 10,
    ) -> None:
        self.batch_size = batch_size
        self.read_queue: list[tuple[Path, asyncio.Future[str]]] = []
        self.write_queue: list[tuple[Path, str, asyncio.Future[None]]] = []
        self.logger = logger

    async def queue_read(self, path: Path) -> str:
        future: asyncio.Future[str] = asyncio.Future()
        self.read_queue.append((path, future))

        if len(self.read_queue) >= self.batch_size:
            await self._flush_reads()

        return await future

    async def queue_write(self, path: Path, content: str) -> None:
        future: asyncio.Future[None] = asyncio.Future[None]()
        self.write_queue.append((path, content, future))

        if len(self.write_queue) >= self.batch_size:
            await self._flush_writes()

        await future

    async def flush_all(self) -> None:
        await asyncio.gather(
            self._flush_reads(),
            self._flush_writes(),
            return_exceptions=True,
        )

    async def _flush_reads(self) -> None:
        if not self.read_queue:
            return

        with LoggingContext("batch_file_reads", count=len(self.read_queue)):
            batch = self.read_queue.copy()
            self.read_queue.clear()

            from itertools import starmap

            tasks = list(starmap(self._read_single_async, batch))

            await asyncio.gather(*tasks, return_exceptions=True)

    async def _flush_writes(self) -> None:
        if not self.write_queue:
            return

        with LoggingContext("batch_file_writes", count=len(self.write_queue)):
            batch = self.write_queue.copy()
            self.write_queue.clear()

            from itertools import starmap

            tasks = list(starmap(self._write_single_async, batch))

            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def _read_single_async(path: Path, future: asyncio.Future[str]) -> None:
        try:
            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()
            future.set_result(content)
        except Exception as e:
            future.set_exception(e)

    @staticmethod
    async def _write_single_async(
        path: Path,
        content: str,
        future: asyncio.Future[None],
    ) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)
            future.set_result(None)
        except Exception as e:
            future.set_exception(e)


class EnhancedFileSystemService(EnhancedFileSystemServiceProtocol, ServiceProtocol):
    def __init__(
        self,
        cache_size: int = 1000,
        cache_ttl: float = 300.0,
        batch_size: int = 10,
        enable_async: bool = True,
    ) -> None:
        # Use keyword args to avoid DI/positional ambiguity
        self.cache = FileCache(max_size=cache_size, default_ttl=cache_ttl)
        self.batch_ops = BatchFileOperations(batch_size) if enable_async else None
        self.enable_async = enable_async
        self.logger = logger

        self._file_timestamps: dict[str, float] = {}

    def read_file(self, path: str | Path) -> str:
        path_obj = Path(path) if isinstance(path, str) else path

        with LoggingContext("read_file", path=str(path_obj)):
            cache_key = self._get_cache_key(path_obj)
            cached_content = self._get_from_cache(cache_key, path_obj)

            if cached_content is not None:
                return cached_content

            content = self._read_file_direct(path_obj)

            self.cache.put(cache_key, content)
            self._file_timestamps[str(path_obj)] = path_obj.stat().st_mtime

            return content

    def write_file(self, path: str | Path, content: str) -> None:
        path_obj = Path(path) if isinstance(path, str) else path
        # Validate content type before logging/length computation
        if not isinstance(content, str):
            raise TypeError("Content must be a string")

        with LoggingContext("write_file", path=str(path_obj), size=len(content)):
            self._write_file_direct(path_obj, content)

            cache_key = self._get_cache_key(path_obj)
            self.cache._evict(cache_key)
            self._file_timestamps[str(path_obj)] = time.time()

    async def read_file_async(self, path: Path) -> str:
        if not self.enable_async or not self.batch_ops:
            return self.read_file(path)

        cache_key = self._get_cache_key(path)
        cached_content = self._get_from_cache(cache_key, path)

        if cached_content is not None:
            return cached_content

        content = await self.batch_ops.queue_read(path)

        self.cache.put(cache_key, content)
        self._file_timestamps[str(path)] = path.stat().st_mtime

        return content

    async def write_file_async(self, path: Path, content: str) -> None:
        if not self.enable_async or not self.batch_ops:
            self.write_file(path, content)
            return

        await self.batch_ops.queue_write(path, content)

        cache_key = self._get_cache_key(path)
        self.cache._evict(cache_key)
        self._file_timestamps[str(path)] = time.time()

    async def read_multiple_files(self, paths: list[Path]) -> dict[Path, str]:
        results = {}

        if not self.enable_async or not self.batch_ops:
            for path in paths:
                try:
                    results[path] = self.read_file(path)
                except Exception as e:
                    self.logger.exception(
                        "Failed to read file",
                        path=str(path),
                        error=str(e),
                    )
                    results[path] = ""
            return results

        with LoggingContext("read_multiple_files", count=len(paths)):
            tasks = [self.read_file_async(path) for path in paths]

            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            for path, result in zip(paths, results_list, strict=False):
                if isinstance(result, Exception):
                    self.logger.error(
                        "Failed to read file",
                        path=str(path),
                        error=str(result),
                    )
                    results[path] = ""
                elif isinstance(result, str):  # Explicit check for mypy
                    results[path] = result

            return results

    async def write_multiple_files(self, file_data: dict[Path, str]) -> None:
        if not self.enable_async or not self.batch_ops:
            for path, content in file_data.items():
                try:
                    self.write_file(path, content)
                except Exception as e:
                    self.logger.exception(
                        "Failed to write file",
                        path=str(path),
                        error=str(e),
                    )
            return

        with LoggingContext("write_multiple_files", count=len(file_data)):
            from itertools import starmap

            tasks = list(starmap(self.write_file_async, file_data.items()))

            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _get_cache_key(path: Path) -> str:
        path_str = str(path.resolve())
        return hashlib.md5(path_str.encode(), usedforsecurity=False).hexdigest()

    def _get_from_cache(self, cache_key: str, path: Path) -> str | None:
        if not path.exists():
            return None

        path_str = str(path)
        if path_str in self._file_timestamps:
            current_mtime = path.stat().st_mtime
            cached_mtime = self._file_timestamps[path_str]

            if current_mtime > cached_mtime:
                self.cache._evict(cache_key)
                del self._file_timestamps[path_str]
                return None

        return self.cache.get(cache_key)

    @staticmethod
    def _validate_file_exists(path: Path) -> None:
        """Validate that a file exists."""
        if not path.exists():
            raise FileError(
                message=f"File does not exist: {path}",
                details=f"Attempted to read file at {path.absolute()}",
                recovery="Check file path and ensure file exists",
            )

    @staticmethod
    def _handle_read_error(error: Exception, path: Path) -> None:
        """Handle file read errors."""
        if isinstance(error, PermissionError):
            raise FileError(
                message=f"Permission denied reading file: {path}",
                details=str(error),
                recovery="Check file permissions and user access rights",
            ) from error
        elif isinstance(error, UnicodeDecodeError):
            raise FileError(
                message=f"Unable to decode file as UTF-8: {path}",
                details=str(error),
                recovery="Ensure file is text - based and UTF-8 encoded",
            ) from error
        elif isinstance(error, OSError):
            raise FileError(
                message=f"System error reading file: {path}",
                details=str(error),
                recovery="Check disk space and file system integrity",
            ) from error

    @staticmethod
    def _read_file_direct(path: Path) -> str:
        try:
            EnhancedFileSystemService._validate_file_exists(path)
            return path.read_text(encoding="utf-8")
        except (PermissionError, UnicodeDecodeError, OSError) as e:
            EnhancedFileSystemService._handle_read_error(e, path)
            raise  # Ensure type checker knows this doesn't return

    @staticmethod
    def _write_file_direct(path: Path, content: str) -> None:
        try:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise FileError(
                    message=f"Cannot create parent directory: {path.parent}",
                    details=str(e),
                    recovery="Check directory permissions and disk space",
                ) from e

            path.write_text(content, encoding="utf-8")

        except PermissionError as e:
            raise FileError(
                message=f"Permission denied writing file: {path}",
                details=str(e),
                recovery="Check file and directory permissions",
            ) from e
        except OSError as e:
            raise FileError(
                message=f"System error writing file: {path}",
                details=str(e),
                recovery="Check disk space and file system integrity",
            ) from e

    @staticmethod
    def file_exists(path: str | Path) -> bool:
        return (Path(path) if isinstance(path, str) else path).exists()

    def create_directory(self, path: str | Path) -> None:
        path_obj = Path(path) if isinstance(path, str) else path
        try:
            path_obj.mkdir(parents=True, exist_ok=True)
            self.logger.debug("Directory created", path=str(path_obj))
        except OSError as e:
            raise FileError(
                message=f"Cannot create directory: {path_obj}",
                details=str(e),
                recovery="Check parent directory permissions and disk space",
            ) from e

    def delete_file(self, path: str | Path) -> None:
        path_obj = Path(path) if isinstance(path, str) else path

        try:
            if path_obj.exists():
                path_obj.unlink()

                cache_key = self._get_cache_key(path_obj)
                self.cache._evict(cache_key)
                self._file_timestamps.pop(str(path_obj), None)

                self.logger.debug("File deleted", path=str(path_obj))
        except OSError as e:
            raise FileError(
                message=f"Cannot delete file: {path_obj}",
                details=str(e),
                recovery="Check file permissions",
            ) from e

    @staticmethod
    def list_files(path: str | Path, pattern: str = "*") -> Iterator[Path]:
        path_obj = Path(path) if isinstance(path, str) else path

        if not path_obj.is_dir():
            raise FileError(
                message=f"Path is not a directory: {path_obj}",
                details=f"Cannot list[t.Any] files in {path_obj}",
                recovery="Ensure path points to a valid directory",
            )

        try:
            yield from path_obj.glob(pattern)
        except OSError as e:
            raise FileError(
                message=f"Cannot list[t.Any] files in directory: {path_obj}",
                details=str(e),
                recovery="Check directory permissions",
            ) from e

    async def flush_operations(self) -> None:
        if self.batch_ops:
            await self.batch_ops.flush_all()

    def get_cache_stats(self) -> dict[str, Any]:
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        self.cache.clear()
        self._file_timestamps.clear()

    def exists(self, path: str | Path) -> bool:
        return (Path(path) if isinstance(path, str) else path).exists()

    def mkdir(self, path: str | Path, parents: bool = False) -> None:
        path_obj = Path(path) if isinstance(path, str) else path
        try:
            path_obj.mkdir(parents=parents, exist_ok=True)
        except OSError as e:
            raise FileError(
                message=f"Cannot create directory: {path_obj}",
                details=str(e),
                recovery="Check parent directory permissions",
            ) from e

    async def _on_start(self) -> None:
        """
        Lifecycle method called when the service is started.
        """
        self.logger.debug("EnhancedFileSystemService started")

    async def _on_stop(self) -> None:
        """
        Lifecycle method called when the service is stopped.
        """
        self.logger.debug("EnhancedFileSystemService stopped")

    async def _on_reload(self) -> None:
        """
        Lifecycle method called when the service is reloaded.
        """
        self.logger.debug("EnhancedFileSystemService reloaded")
