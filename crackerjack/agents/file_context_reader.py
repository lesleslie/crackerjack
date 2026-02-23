
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FileContextReader:

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._lock = asyncio.Lock()
        logger.debug("FileContextReader initialized with cache and lock")

    async def read_file(self, file_path: str | Path) -> str:

        path = Path(file_path)

        async with self._lock:

            cache_key = str(path.absolute())
            if cache_key in self._cache:
                logger.debug(f"Cache hit for {cache_key}")
                return self._cache[cache_key]


            try:
                content = await asyncio.to_thread(path.read_text, encoding="utf-8")
                logger.debug(f"Read {len(content)} bytes from {file_path}")
            except FileNotFoundError:
                logger.error(f"File not found: {file_path}")
                raise
            except UnicodeDecodeError as e:
                logger.error(f"Encoding error reading {file_path}: {e}")
                raise


            self._cache[cache_key] = content
            logger.debug(f"Cached {cache_key}")

            return content

    def clear_cache(self) -> None:
        self._cache.clear()
        logger.debug(f"Cleared cache ({len(self._cache)} entries removed)")

    async def get_cached_files(self) -> dict[str, str]:
        async with self._lock:
            return self._cache.copy()
