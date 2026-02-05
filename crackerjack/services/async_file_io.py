from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

logger = logging.getLogger(__name__)


_IO_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async_io_")


async def async_read_file(file_path: Path) -> str:
    loop = asyncio.get_event_loop()

    try:
        content = await loop.run_in_executor(
            _IO_EXECUTOR,
            file_path.read_text,
        )
        return content
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise


async def async_write_file(
    file_path: Path,
    content: str,
) -> None:
    loop = asyncio.get_event_loop()

    try:
        await loop.run_in_executor(
            _IO_EXECUTOR,
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

    tasks = [async_write_file(fp, content) for fp, content in file_writes]
    await asyncio.gather(*tasks)


def shutdown_io_executor() -> None:
    _IO_EXECUTOR.shutdown(wait=True)


__all__ = [
    "async_read_file",
    "async_write_file",
    "async_read_files_batch",
    "async_write_files_batch",
    "shutdown_io_executor",
]
