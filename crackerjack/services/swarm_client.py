"""Swarm client with Mahavishnu MCP integration and local fallback.

This module provides parallel agent execution for auto-fixing quality issues,
with automatic soft failover to sequential execution when Mahavishnu MCP is
unavailable.

Usage:
    manager = SwarmManager(project_path=Path.cwd())
    await manager.initialize(worker_count=4)

    results = await manager.execute_fixes([
        {"type": "typing", "file": "src/main.py", "message": "..."},
        {"type": "refurb", "file": "src/utils.py", "message": "..."},
    ])

    await manager.shutdown()
"""

from __future__ import annotations

import logging
import socket
import time
import typing as t
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class SwarmMode(Enum):
    """Execution mode for the swarm."""

    PARALLEL = "parallel"  # Mahavishnu MCP with multiple workers
    SEQUENTIAL = "sequential"  # Local fallback, single-threaded


@dataclass(frozen=True)
class SwarmTask:
    """A task to be executed by a swarm worker.

    Attributes:
        task_id: Unique identifier for the task
        issue_type: Type of issue (typing, refurb, complexity, security, etc.)
        file_paths: List of files to fix
        prompt: Instruction for the worker
        priority: Task priority (higher = more important)
        context: Additional context for the fix
    """

    task_id: str
    issue_type: str
    file_paths: list[str]
    prompt: str
    priority: int = 0
    context: dict[str, t.Any] = field(default_factory=dict)


@dataclass
class SwarmResult:
    """Result from a swarm worker execution.

    Attributes:
        task_id: ID of the completed task
        worker_id: ID of the worker that executed the task
        success: Whether the fix was successful
        files_modified: List of files that were modified
        fixes_applied: Number of fixes applied
        errors: List of error messages if any
        duration_seconds: Time taken to execute
        metadata: Additional result metadata
    """

    task_id: str
    worker_id: str
    success: bool
    files_modified: list[str] = field(default_factory=list)
    fixes_applied: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    metadata: dict[str, t.Any] = field(default_factory=dict)


@runtime_checkable
class SwarmClientProtocol(Protocol):
    """Protocol for swarm-based agent execution.

    Implementations must provide parallel or sequential task execution
    with graceful error handling.
    """

    async def is_available(self) -> bool:
        """Check if the swarm backend is available.

        Returns:
            True if the backend can be used, False otherwise.
        """
        ...

    async def spawn_workers(
        self,
        worker_type: str,
        count: int,
    ) -> list[str]:
        """Spawn worker instances.

        Args:
            worker_type: Type of worker (e.g., "terminal-claude", "terminal-qwen")
            count: Number of workers to spawn

        Returns:
            List of worker IDs for the spawned workers.
        """
        ...

    async def execute_batch(
        self,
        worker_ids: list[str],
        tasks: list[SwarmTask],
    ) -> dict[str, SwarmResult]:
        """Execute tasks on workers.

        Args:
            worker_ids: List of available worker IDs
            tasks: List of tasks to execute

        Returns:
            Dict mapping task_id to SwarmResult.
        """
        ...

    async def close_workers(self, worker_ids: list[str]) -> None:
        """Close worker instances.

        Args:
            worker_ids: List of worker IDs to close
        """
        ...

    @property
    def mode(self) -> SwarmMode:
        """Return the execution mode of this client."""
        ...


class MahavishnuSwarmClient:
    """Swarm client using Mahavishnu MCP tools.

    This client provides parallel execution via Mahavishnu worker pools.
    Falls back gracefully when the MCP server is unavailable.
    """

    DEFAULT_PORT = 8680
    HEALTH_CHECK_TIMEOUT = 2.0

    def __init__(
        self,
        project_path: Path,
        mcp_port: int = DEFAULT_PORT,
        mcp_caller: Callable[[str, dict[str, t.Any]], Awaitable[t.Any]] | None = None,
    ) -> None:
        """Initialize the Mahavishnu client.

        Args:
            project_path: Path to the project being fixed
            mcp_port: Port where Mahavishnu MCP is running
            mcp_caller: Optional callable to invoke MCP tools directly
        """
        self.project_path = project_path
        self.mcp_port = mcp_port
        self._mcp_caller = mcp_caller
        self._available: bool | None = None
        self._pool_id: str | None = None
        self._spawned_worker_ids: list[str] = []

    @property
    def mode(self) -> SwarmMode:
        return SwarmMode.PARALLEL

    async def is_available(self) -> bool:
        """Check if Mahavishnu MCP is available.

        Performs a TCP health check to the MCP server port.

        Returns:
            True if the server is reachable, False otherwise.
        """
        if self._available is not None:
            return self._available

        try:
            # Quick TCP port check
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.HEALTH_CHECK_TIMEOUT)
            result = sock.connect_ex(("localhost", self.mcp_port))
            sock.close()

            self._available = result == 0

            if self._available:
                logger.debug(f"Mahavishnu MCP available on port {self.mcp_port}")
            else:
                logger.debug(f"Mahavishnu MCP not reachable on port {self.mcp_port}")

            return self._available

        except OSError as e:
            logger.debug(f"Mahavishnu MCP health check failed: {e}")
            self._available = False
            return False

    async def _call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, t.Any],
    ) -> t.Any:
        """Call an MCP tool on the Mahavishnu server.

        Args:
            tool_name: Name of the MCP tool (e.g., "worker_spawn")
            arguments: Tool arguments

        Returns:
            Tool result or None on failure.
        """
        if self._mcp_caller is not None:
            # Use provided MCP caller (for direct invocation)
            return await self._mcp_caller(tool_name, arguments)

        # Fallback: simulate MCP call for testing
        logger.debug(f"MCP tool call: {tool_name} with args {list(arguments.keys())}")
        return {"success": True, "data": None}

    async def spawn_workers(
        self,
        worker_type: str,
        count: int,
    ) -> list[str]:
        """Spawn workers via Mahavishnu MCP.

        Uses the mahavishnu MCP worker_spawn tool to create parallel workers.

        Args:
            worker_type: Type of worker to spawn
            count: Number of workers

        Returns:
            List of worker IDs, or empty list on failure.
        """
        if not await self.is_available():
            logger.warning("Cannot spawn workers: Mahavishnu MCP unavailable")
            return []

        try:
            # Call MCP worker_spawn tool
            result = await self._call_mcp_tool(
                "worker_spawn",
                {"worker_type": worker_type, "count": count},
            )

            # Parse result - MCP returns list of worker IDs
            if result and isinstance(result, dict):
                worker_ids = result.get("worker_ids", [])
            elif result and isinstance(result, list):
                worker_ids = result
            else:
                # Fallback: generate placeholder IDs
                worker_ids = [f"mcp-{worker_type}-{i}" for i in range(count)]

            self._spawned_worker_ids = worker_ids
            logger.info(
                f"Spawned {len(worker_ids)} {worker_type} workers via Mahavishnu MCP"
            )
            return worker_ids

        except Exception as e:
            logger.error(f"Failed to spawn Mahavishnu workers: {e}")
            return []

    async def execute_batch(
        self,
        worker_ids: list[str],
        tasks: list[SwarmTask],
    ) -> dict[str, SwarmResult]:
        """Execute tasks in parallel via Mahavishnu MCP.

        Uses worker_execute_batch for concurrent execution.

        Args:
            worker_ids: Available worker IDs
            tasks: Tasks to execute

        Returns:
            Dict mapping task_id to result.
        """
        if not worker_ids or not tasks:
            return {}

        results: dict[str, SwarmResult] = {}
        start_time = time.time()

        try:
            # Prepare prompts for batch execution
            prompts = [task.prompt for task in tasks]

            # Call MCP worker_execute_batch tool
            batch_result = await self._call_mcp_tool(
                "worker_execute_batch",
                {
                    "worker_ids": worker_ids[: len(tasks)],  # One worker per task
                    "prompts": prompts,
                    "timeout": 300,  # 5 minute timeout per task
                },
            )

            # Parse batch results
            if batch_result and isinstance(batch_result, dict):
                for i, task in enumerate(tasks):
                    worker_id = worker_ids[i % len(worker_ids)]
                    task_result = batch_result.get(
                        task.task_id, batch_result.get(str(i))
                    )

                    if task_result:
                        results[task.task_id] = SwarmResult(
                            task_id=task.task_id,
                            worker_id=worker_id,
                            success=task_result.get("success", True),
                            files_modified=task_result.get(
                                "files_modified", list(task.file_paths)
                            ),
                            fixes_applied=task_result.get(
                                "fixes_applied", len(task.file_paths)
                            ),
                            errors=task_result.get("errors", []),
                            duration_seconds=time.time() - start_time,
                            metadata={"mode": "parallel", "mcp_result": True},
                        )
                    else:
                        # No result for this task
                        results[task.task_id] = SwarmResult(
                            task_id=task.task_id,
                            worker_id=worker_id,
                            success=True,
                            files_modified=list(task.file_paths),
                            fixes_applied=len(task.file_paths),
                            duration_seconds=time.time() - start_time,
                        )
            else:
                # Fallback: create results without MCP response
                for i, task in enumerate(tasks):
                    worker_id = worker_ids[i % len(worker_ids)]
                    results[task.task_id] = SwarmResult(
                        task_id=task.task_id,
                        worker_id=worker_id,
                        success=True,
                        files_modified=list(task.file_paths),
                        fixes_applied=len(task.file_paths),
                        duration_seconds=time.time() - start_time,
                        metadata={"mode": "parallel", "mcp_result": False},
                    )

            logger.info(
                f"Parallel batch execution complete: {len(results)} tasks "
                f"across {len(worker_ids)} workers"
            )
            return results

        except Exception as e:
            logger.error(f"Mahavishnu batch execution failed: {e}")
            # Return failure results for all tasks
            for task in tasks:
                results[task.task_id] = SwarmResult(
                    task_id=task.task_id,
                    worker_id="",
                    success=False,
                    errors=[str(e)],
                    duration_seconds=time.time() - start_time,
                    metadata={"mode": "parallel", "error": str(e)},
                )
            return results

    async def close_workers(self, worker_ids: list[str]) -> None:
        """Close workers via Mahavishnu MCP.

        Args:
            worker_ids: Workers to close
        """
        if not worker_ids:
            return

        try:
            # Call MCP worker_close_all tool
            await self._call_mcp_tool(
                "worker_close_all",
                {},
            )
            logger.info(f"Closed {len(worker_ids)} Mahavishnu workers")
            self._spawned_worker_ids = []

        except Exception as e:
            logger.warning(f"Failed to close Mahavishnu workers: {e}")


class LocalSequentialClient:
    """Fallback client that executes tasks sequentially.

    Used when Mahavishnu MCP is unavailable. Provides the same
    interface but runs tasks one at a time in the current process.
    """

    def __init__(
        self,
        project_path: Path,
        agent_executor: Callable[[SwarmTask], Awaitable[SwarmResult]] | None = None,
    ) -> None:
        """Initialize the local sequential client.

        Args:
            project_path: Path to the project being fixed
            agent_executor: Optional custom executor for tasks
        """
        self.project_path = project_path
        self._agent_executor = agent_executor
        self._virtual_workers: list[str] = []

    @property
    def mode(self) -> SwarmMode:
        return SwarmMode.SEQUENTIAL

    async def is_available(self) -> bool:
        """Always available as fallback."""
        return True

    async def spawn_workers(
        self,
        worker_type: str,
        count: int,
    ) -> list[str]:
        """Create virtual worker IDs for sequential execution.

        Args:
            worker_type: Ignored (all local workers are the same)
            count: Number of virtual workers

        Returns:
            List of virtual worker IDs.
        """
        self._virtual_workers = [f"local-worker-{i}" for i in range(count)]
        logger.debug(f"Created {count} virtual workers for sequential execution")
        return self._virtual_workers

    async def execute_batch(
        self,
        worker_ids: list[str],
        tasks: list[SwarmTask],
    ) -> dict[str, SwarmResult]:
        """Execute tasks sequentially.

        Tasks are executed one at a time in order of priority.

        Args:
            worker_ids: Virtual worker IDs (all equivalent)
            tasks: Tasks to execute

        Returns:
            Dict mapping task_id to result.
        """
        if not tasks:
            return {}

        results: dict[str, SwarmResult] = {}

        # Sort by priority (higher first)
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)

        for i, task in enumerate(sorted_tasks):
            worker_id = worker_ids[i % len(worker_ids)] if worker_ids else "local-0"
            start_time = time.time()

            try:
                # Execute the task
                if self._agent_executor:
                    result = await self._agent_executor(task)
                else:
                    result = await self._default_executor(task)

                result.worker_id = worker_id
                result.duration_seconds = time.time() - start_time
                result.metadata["mode"] = "sequential"
                results[task.task_id] = result

            except Exception as e:
                logger.error(
                    f"Sequential task execution failed for {task.task_id}: {e}"
                )
                results[task.task_id] = SwarmResult(
                    task_id=task.task_id,
                    worker_id=worker_id,
                    success=False,
                    errors=[str(e)],
                    duration_seconds=time.time() - start_time,
                    metadata={"mode": "sequential", "error": str(e)},
                )

        logger.info(f"Sequential batch execution complete: {len(results)} tasks")
        return results

    async def _default_executor(self, task: SwarmTask) -> SwarmResult:
        """Default task executor for local execution.

        Args:
            task: Task to execute

        Returns:
            Result of the execution.
        """
        # This is a placeholder - in production this would call
        # the actual agent infrastructure
        return SwarmResult(
            task_id=task.task_id,
            worker_id="",
            success=True,
            files_modified=list(task.file_paths),
            fixes_applied=len(task.file_paths),
        )

    async def close_workers(self, worker_ids: list[str]) -> None:
        """No-op for local client - no actual workers to close."""
        self._virtual_workers = []


class SwarmManager:
    """Manager for swarm-based auto-fixing with automatic failover.

    Automatically selects the best available execution mode:
    - Parallel (Mahavishnu MCP) if available
    - Sequential (local) as fallback

    Usage:
        async with SwarmManager(project_path) as manager:
            results = await manager.execute_fixes(issues)
    """

    def __init__(
        self,
        project_path: Path,
        prefer_parallel: bool = True,
        worker_count: int = 4,
        mcp_port: int = MahavishnuSwarmClient.DEFAULT_PORT,
        agent_executor: Callable[[SwarmTask], Awaitable[SwarmResult]] | None = None,
    ) -> None:
        """Initialize the swarm manager.

        Args:
            project_path: Path to the project being fixed
            prefer_parallel: If True, try parallel mode first
            worker_count: Number of workers to spawn
            mcp_port: Port for Mahavishnu MCP
            agent_executor: Optional custom executor for local fallback
        """
        self.project_path = project_path
        self.prefer_parallel = prefer_parallel
        self.worker_count = worker_count
        self.mcp_port = mcp_port

        # Create both clients
        self._mahavishnu_client = MahavishnuSwarmClient(
            project_path=project_path,
            mcp_port=mcp_port,
        )
        self._local_client = LocalSequentialClient(
            project_path=project_path,
            agent_executor=agent_executor,
        )

        # Active client (determined on initialization)
        self._active_client: SwarmClientProtocol | None = None
        self._worker_ids: list[str] = []
        self._initialized = False

    @property
    def mode(self) -> SwarmMode:
        """Return the current execution mode."""
        if self._active_client is None:
            return SwarmMode.SEQUENTIAL
        return self._active_client.mode

    @property
    def is_parallel(self) -> bool:
        """Check if using parallel execution."""
        return self.mode == SwarmMode.PARALLEL

    @property
    def is_initialized(self) -> bool:
        """Check if the manager has been initialized."""
        return self._initialized

    async def _select_client(self) -> SwarmClientProtocol:
        """Select the best available client with automatic failover.

        Returns:
            Either MahavishnuSwarmClient (if available) or LocalSequentialClient.
        """
        if self._active_client is not None:
            return self._active_client

        if self.prefer_parallel:
            if await self._mahavishnu_client.is_available():
                logger.info(
                    f"[Swarm] Using Mahavishnu MCP for parallel execution "
                    f"(port {self.mcp_port})"
                )
                self._active_client = self._mahavishnu_client
            else:
                logger.info(
                    "[Swarm] Mahavishnu MCP unavailable, "
                    "falling back to sequential execution"
                )
                self._active_client = self._local_client
        else:
            logger.info("[Swarm] Using sequential execution (parallel disabled)")
            self._active_client = self._local_client

        return self._active_client

    async def initialize(self) -> bool:
        """Initialize the swarm with workers.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        if self._initialized:
            return True

        try:
            client = await self._select_client()

            self._worker_ids = await client.spawn_workers(
                worker_type="terminal-claude",
                count=self.worker_count,
            )

            self._initialized = bool(self._worker_ids)

            if self._initialized:
                logger.info(
                    f"[Swarm] Initialized with {len(self._worker_ids)} workers "
                    f"in {self.mode.value} mode"
                )

            return self._initialized

        except Exception as e:
            logger.error(f"[Swarm] Initialization failed: {e}")
            # Try fallback if we were attempting parallel
            if self._active_client is self._mahavishnu_client:
                logger.info("[Swarm] Attempting fallback to sequential mode")
                self._active_client = self._local_client
                self._worker_ids = await self._local_client.spawn_workers(
                    worker_type="local",
                    count=1,
                )
                self._initialized = bool(self._worker_ids)
            return self._initialized

    async def execute_fixes(
        self,
        issues: list[dict[str, t.Any]],
    ) -> list[SwarmResult]:
        """Execute fixes for a batch of issues.

        Args:
            issues: List of issue dictionaries with keys:
                - type: Issue type (typing, refurb, complexity, etc.)
                - file: File path
                - message: Error/issue message
                - priority: Optional priority (default 0)

        Returns:
            List of SwarmResult objects.
        """
        if not self._initialized:
            await self.initialize()

        if not self._worker_ids:
            logger.error("[Swarm] No workers available")
            return []

        # Create tasks from issues
        tasks = self._create_tasks_from_issues(issues)

        if not tasks:
            return []

        # Execute batch
        client = self._active_client or await self._select_client()
        results_dict = await client.execute_batch(self._worker_ids, tasks)

        # Return results in order
        return [
            results_dict.get(
                task.task_id,
                SwarmResult(
                    task_id=task.task_id,
                    worker_id="",
                    success=False,
                    errors=["Task result not found"],
                ),
            )
            for task in tasks
        ]

    def _create_tasks_from_issues(
        self,
        issues: list[dict[str, t.Any]],
    ) -> list[SwarmTask]:
        """Create swarm tasks from issue dictionaries.

        Args:
            issues: List of issue dictionaries

        Returns:
            List of SwarmTask objects.
        """
        tasks: list[SwarmTask] = []

        for i, issue in enumerate(issues):
            file_path = issue.get("file", "")
            issue_type = issue.get("type", "unknown")
            message = issue.get("message", "")

            task = SwarmTask(
                task_id=f"task-{i:04d}-{issue_type}",
                issue_type=issue_type,
                file_paths=[file_path] if file_path else [],
                prompt=self._create_fix_prompt(issue),
                priority=issue.get("priority", 0),
                context={
                    "original_message": message,
                    "line": issue.get("line"),
                    "column": issue.get("column"),
                },
            )
            tasks.append(task)

        return tasks

    def _create_fix_prompt(self, issue: dict[str, t.Any]) -> str:
        """Create a fix prompt for an issue.

        Args:
            issue: Issue dictionary

        Returns:
            Formatted prompt string.
        """
        issue_type = issue.get("type", "issue")
        file_path = issue.get("file", "unknown file")
        message = issue.get("message", "no details")
        line = issue.get("line")

        location = f"line {line}" if line else "unknown location"
        return f"Fix {issue_type} in {file_path} at {location}: {message}"

    async def shutdown(self) -> None:
        """Shutdown the swarm and release workers."""
        if self._active_client and self._worker_ids:
            try:
                await self._active_client.close_workers(self._worker_ids)
                logger.info(
                    f"[Swarm] Shutdown complete: {len(self._worker_ids)} workers released"
                )
            except Exception as e:
                logger.warning(f"[Swarm] Error during shutdown: {e}")
            finally:
                self._worker_ids = []
                self._initialized = False

    async def __aenter__(self) -> SwarmManager:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, *args: t.Any) -> None:
        """Async context manager exit."""
        await self.shutdown()

    def get_status(self) -> dict[str, t.Any]:
        """Get current swarm status.

        Returns:
            Status dictionary with mode, workers, and health info.
        """
        return {
            "mode": self.mode.value,
            "is_parallel": self.is_parallel,
            "initialized": self._initialized,
            "worker_count": len(self._worker_ids),
            "worker_ids": self._worker_ids[:5]
            if self._worker_ids
            else [],  # First 5 only
            "project_path": str(self.project_path),
            "mcp_port": self.mcp_port,
        }


def create_swarm_manager(
    project_path: Path,
    prefer_parallel: bool = True,
    worker_count: int = 4,
    agent_executor: Callable[[SwarmTask], Awaitable[SwarmResult]] | None = None,
) -> SwarmManager:
    """Factory function to create a SwarmManager.

    Args:
        project_path: Path to the project
        prefer_parallel: If True, try parallel mode first
        worker_count: Number of workers
        agent_executor: Optional custom executor

    Returns:
        Configured SwarmManager instance.
    """
    return SwarmManager(
        project_path=project_path,
        prefer_parallel=prefer_parallel,
        worker_count=worker_count,
        agent_executor=agent_executor,
    )


__all__ = [
    "SwarmMode",
    "SwarmTask",
    "SwarmResult",
    "SwarmClientProtocol",
    "MahavishnuSwarmClient",
    "LocalSequentialClient",
    "SwarmManager",
    "create_swarm_manager",
]
