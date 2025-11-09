"""Tests for AsyncHookExecutor process tracking and cleanup."""

import asyncio
from pathlib import Path

from crackerjack.executors.async_hook_executor import AsyncHookExecutor


def test_async_hook_executor_initialization():
    """Test that AsyncHookExecutor initializes with empty process tracking."""
    executor = AsyncHookExecutor(Path("."))
    assert len(executor._running_processes) == 0


async def test_async_hook_executor_process_tracking():
    """Test that AsyncHookExecutor tracks running processes."""
    executor = AsyncHookExecutor(Path("."))

    # Create a simple subprocess to track
    proc = await asyncio.create_subprocess_exec(
        "python", "-c", "import time; time.sleep(0.1)",
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


async def test_async_hook_executor_cleanup():
    """Test that AsyncHookExecutor cleanup terminates running processes."""
    executor = AsyncHookExecutor(Path("."))

    # Create a subprocess that will run for a bit
    proc = await asyncio.create_subprocess_exec(
        "python", "-c", "import time; time.sleep(1)",
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
    import pytest
    import sys

    # For direct execution
    async def run_tests():
        await test_async_hook_executor_process_tracking()
        await test_async_hook_executor_cleanup()
        print("All async tests passed!")

    asyncio.run(run_tests())
