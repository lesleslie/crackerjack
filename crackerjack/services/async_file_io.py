from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from itertools import starmap
from pathlib import Path

logger = logging.getLogger(__name__)

_io_executor_lock = threading.Lock()
_io_executor: ThreadPoolExecutor | None = None


def get_io_executor() -> ThreadPoolExecutor:
    global _io_executor

    if _io_executor is None:
        with _io_executor_lock:
            if _io_executor is None:
                try:
                    from crackerjack.config import CrackerjackSettings

                    settings = CrackerjackSettings()
                    max_workers = settings.max_parallel_hooks
                except Exception:
                    max_workers = 4
                    logger.warning(
                        "Could not load max_parallel_hooks from settings, using default: 4"
                    )

                _io_executor = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix="async_io_",
                )

    return _io_executor


async def async_write_file(
    file_path: Path,
    content: str,
) -> None:
    loop = asyncio.get_event_loop()

    try:
        await loop.run_in_executor(
            get_io_executor(),
            partial(file_path.write_text, content),
        )
    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        raise


async def async_read_files_batch(file_paths: list[Path]) -> dict[Path, str]:

    tasks = [async_read_file(fp) for fp in file_paths]
    contents = await asyncio.gather(*tasks)

    return dict(zip(file_paths, contents))


async def async_write_files_batch(
    file_writes: list[tuple[Path, str]],
) -> None:

    tasks = list(starmap(async_write_file, file_writes))
    await asyncio.gather(*tasks)


def shutdown_io_executor() -> None:
    global _io_executor
    if _io_executor is not None:
        _io_executor.shutdown(wait=True)
        _io_executor = None


__all__ = [
    "async_read_file",
    "async_write_file",
    "async_read_files_batch",
    "async_write_files_batch",
    "shutdown_io_executor",
]


async def async_read_file(file_path: Path) -> str:
    self._process_general_1()


async def async_read_file(file_path: Path) -> str:
    loop = asyncio.get_event_loop()

    try:
        content = await loop.run_in_executor(
            None,
            lambda: file_path.read_text(),
        )
        return content
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise
