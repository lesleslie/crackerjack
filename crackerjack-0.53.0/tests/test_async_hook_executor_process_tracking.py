"""Tests for AsyncHookExecutor process tracking and cleanup."""

import asyncio
import logging
from pathlib import Path

from rich.console import Console

from crackerjack.executors.async_hook_executor import AsyncHookExecutor


def test_async_hook_executor_initialization() -> None:
    """Test that AsyncHookExecutor initializes with empty process tracking."""
    console = Console()
    executor = AsyncHookExecutor(
        console=console,
        pkg_path=Path(),
    )
    assert len(executor._running_processes) == 0


async def test_async_hook_executor_process_tracking() -> None:
    """Test that AsyncHookExecutor tracks running processes."""
    console = Console()
    executor = AsyncHookExecutor(
        console=console,
        pkg_path=Path(),
    )

    # Create a simple subprocess to track
    proc = await asyncio.create_subprocess_exec(
        "python", "-c", "import time; time.sleep(0.05)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Add the process to tracking
    executor._running_processes.add(proc)

    # Verify it's in the tracking set
    assert len(executor._running_processes) == 1
    assert proc in executor._running_processes

    # Wait for process to complete
    await proc.wait()

    # Remove from tracking
    executor._running_processes.discard(proc)

    # Verify it's removed
    assert len(executor._running_processes) == 0


async def test_async_hook_executor_cleanup() -> None:
    """Test that AsyncHookExecutor cleanup terminates running processes."""
    console = Console()
    executor = AsyncHookExecutor(
        console=console,
        pkg_path=Path(),
    )

    # Create a subprocess that will run for a bit
    proc = await asyncio.create_subprocess_exec(
        "python", "-c", "import time; time.sleep(0.2)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Add the process to tracking
    executor._running_processes.add(proc)
    assert len(executor._running_processes) == 1

    # Call cleanup, which should terminate the process
    await executor.cleanup()

    # Process should be terminated and tracking set should be empty
    assert len(executor._running_processes) == 0


if __name__ == "__main__":
    # Run the async tests
    import sys

    import pytest

    # For direct execution
    async def run_tests() -> None:
        await test_async_hook_executor_process_tracking()
        await test_async_hook_executor_cleanup()

    asyncio.run(run_tests())
