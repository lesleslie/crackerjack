"""
File context reader with thread-safe caching for AI agents.

Ensures agents always have full file context before generating fixes.
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FileContextReader:
    """
    Thread-safe file context reader with caching.

    Prevents race conditions when multiple agents read files concurrently.
    """

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def read_file(self, file_path: str | Path) -> str:
        """
        Read file content with thread-safe caching.

        Args:
            file_path: Path to file to read

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        cache_key = str(Path(file_path).absolute())

        async with self._lock:
            if cache_key in self._cache:
                logger.debug(f"Cache hit for {file_path}")
                return self._cache[cache_key]

            logger.debug(f"Cache miss for {file_path}, reading from disk")

            try:
                content = await asyncio.to_thread(
                    Path.read_text, Path(file_path), encoding="utf-8"
                )
                self._cache[cache_key] = content
                return content
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
                raise

    def clear_cache(self) -> None:
        """Clear all cached file contents."""
        self._cache.clear()
        logger.debug("File context cache cleared")

    def clear_cache_for_file(self, file_path: str | Path) -> None:
        """Clear cache for specific file."""
        cache_key = str(Path(file_path).absolute())
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.debug(f"Cleared cache for {file_path}")
