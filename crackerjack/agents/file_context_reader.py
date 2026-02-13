"""File context reader for AI agents.

Provides thread-safe file content caching to prevent redundant I/O operations
and ensure consistent file context across parallel agent execution.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class FileContextReader:
    """Thread-safe file context reader with caching for AI agents.

    This class provides:
    - Async file reading with thread-safe caching
    - Cache management with clear capability
    - Thread-safe operations using asyncio.Lock

    Usage:
        reader = FileContextReader()
        content = await reader.read_file("path/to/file.py")
        # Later: reader.clear_cache()
    """

    def __init__(self) -> None:
        """Initialize file context reader with cache and lock."""
        self._cache: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        logger.debug("FileContextReader initialized with cache and lock")

    async def read_file(self, file_path: str | Path) -> str:
        """Read file with caching. Thread-safe.

        Args:
            file_path: Path to file (str or Path object)

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            UnicodeDecodeError: If file encoding fails
        """
        # Convert to Path object for consistent handling
        path = Path(file_path)

        async with self._lock:
            # Check cache first (while holding lock)
            cache_key = str(path.absolute())
            if cache_key in self._cache:
                logger.debug(f"Cache hit for {cache_key}")
                return self._cache[cache_key]

            # Read file (asyncio.to_thread for non-blocking I/O)
            try:
                content = await asyncio.to_thread(path.read_text, encoding="utf-8")
                logger.debug(f"Read {len(content)} bytes from {file_path}")
            except FileNotFoundError:
                logger.error(f"File not found: {file_path}")
                raise
            except UnicodeDecodeError as e:
                logger.error(f"Encoding error reading {file_path}: {e}")
                raise

            # Store in cache
            self._cache[cache_key] = content
            logger.debug(f"Cached {cache_key}")

            return content

    def clear_cache(self) -> None:
        """Clear all cached file contents.

        Useful for:
        - Testing scenarios requiring fresh file reads
        - Memory management in long-running processes
        """
        self._cache.clear()
        logger.debug(f"Cleared cache ({len(self._cache)} entries removed)")

    async def get_cached_files(self) -> Dict[str, str]:
        """Get all currently cached files.

        Returns:
            Dictionary mapping cache keys to file contents

        Useful for:
        - Debugging cache state
        - Monitoring memory usage
        """
        async with self._lock:
            return self._cache.copy()
