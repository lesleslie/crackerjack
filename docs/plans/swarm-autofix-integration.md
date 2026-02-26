# Swarm-Based Auto-Fix Integration Plan

## Overview

Integrate Mahavishnu MCP worker pools for parallel agent execution with soft failover when the MCP server is unavailable.

## Goals

1. **Parallel Auto-Fixing**: Use Mahavishnu worker pools to run multiple AI agents concurrently
2. **Soft Failover**: Gracefully degrade to sequential execution when Mahavishnu is unavailable
3. **Worktree Isolation**: Each worker operates in an isolated git worktree for safe parallel development
4. **Result Aggregation**: Collect and merge results from all workers

## Architecture

### Protocol-Based Design

```python
@runtime_checkable
class SwarmClientProtocol(Protocol):
    """Protocol for swarm-based agent execution."""

    async def is_available(self) -> bool:
        """Check if the swarm backend is available."""
        ...

    async def spawn_workers(
        self,
        worker_type: str,
        count: int,
    ) -> list[str]:
        """Spawn worker instances and return their IDs."""
        ...

    async def execute_batch(
        self,
        worker_ids: list[str],
        tasks: list[SwarmTask],
    ) -> dict[str, SwarmResult]:
        """Execute tasks on workers in parallel."""
        ...

    async def close_workers(self, worker_ids: list[str]) -> None:
        """Close worker instances."""
        ...


@dataclass(frozen=True)
class SwarmTask:
    """A task to be executed by a swarm worker."""
    task_id: str
    issue_type: str  # typing, refurb, complexity, etc.
    file_paths: list[str]
    prompt: str
    priority: int = 0


@dataclass
class SwarmResult:
    """Result from a swarm worker execution."""
    task_id: str
    worker_id: str
    success: bool
    files_modified: list[str]
    fixes_applied: int
    errors: list[str]
    duration_seconds: float
```

### Two Implementations

1. **MahavishnuSwarmClient** - Uses MCP tools when available
2. **LocalSequentialClient** - Fallback that runs tasks sequentially

### Integration Points

```
AutofixCoordinator
    │
    ├── SwarmManager (NEW)
    │       ├── MahavishnuSwarmClient (primary)
    │       └── LocalSequentialClient (fallback)
    │
    └── AgentCoordinator (existing)
            └── Individual agents (RefactoringAgent, SecurityAgent, etc.)
```

## Implementation

### Phase 1: Core Protocol and Clients

#### File: `crackerjack/services/swarm_client.py`

```python
"""Swarm client with Mahavishnu MCP integration and local fallback."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SwarmTask:
    """A task to be executed by a swarm worker."""
    task_id: str
    issue_type: str
    file_paths: list[str]
    prompt: str
    priority: int = 0


@dataclass
class SwarmResult:
    """Result from a swarm worker execution."""
    task_id: str
    worker_id: str
    success: bool
    files_modified: list[str] = field(default_factory=list)
    fixes_applied: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@runtime_checkable
class SwarmClientProtocol(Protocol):
    """Protocol for swarm-based agent execution."""

    async def is_available(self) -> bool:
        """Check if the swarm backend is available."""
        ...

    async def spawn_workers(
        self,
        worker_type: str,
        count: int,
    ) -> list[str]:
        """Spawn worker instances and return their IDs."""
        ...

    async def execute_batch(
        self,
        worker_ids: list[str],
        tasks: list[SwarmTask],
    ) -> dict[str, SwarmResult]:
        """Execute tasks on workers in parallel."""
        ...

    async def close_workers(self, worker_ids: list[str]) -> None:
        """Close worker instances."""
        ...


class MahavishnuSwarmClient:
    """Swarm client using Mahavishnu MCP tools."""

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self._available: bool | None = None
        self._worker_pool: str | None = None

    async def is_available(self) -> bool:
        """Check if Mahavishnu MCP is available."""
        if self._available is not None:
            return self._available

        try:
            # Try to spawn a minimal test pool
            # This will fail fast if MCP is not available
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex(('localhost', 8680))
            sock.close()
            self._available = result == 0
            return self._available
        except Exception as e:
            logger.debug(f"Mahavishnu MCP not available: {e}")
            self._available = False
            return False

    async def spawn_workers(
        self,
        worker_type: str,
        count: int,
    ) -> list[str]:
        """Spawn workers via Mahavishnu MCP."""
        try:
            # Use MCP tool to spawn workers
            # This would be called via the MCP client
            # For now, return mock IDs
            return [f"mcp-worker-{i}" for i in range(count)]
        except Exception as e:
            logger.error(f"Failed to spawn workers: {e}")
            return []

    async def execute_batch(
        self,
        worker_ids: list[str],
        tasks: list[SwarmTask],
    ) -> dict[str, SwarmResult]:
        """Execute tasks via Mahavishnu worker_execute_batch."""
        results: dict[str, SwarmResult] = {}

        # Map tasks to workers
        prompts = [task.prompt for task in tasks]

        try:
            # This would use mcp__mahavishnu__worker_execute_batch
            # For now, return placeholder results
            for i, (worker_id, task) in enumerate(zip(worker_ids, tasks)):
                results[task.task_id] = SwarmResult(
                    task_id=task.task_id,
                    worker_id=worker_id,
                    success=True,
                    files_modified=task.file_paths,
                    fixes_applied=len(task.file_paths),
                    duration_seconds=0.1 * len(task.file_paths),
                )
            return results
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            for task in tasks:
                results[task.task_id] = SwarmResult(
                    task_id=task.task_id,
                    worker_id="",
                    success=False,
                    errors=[str(e)],
                )
            return results

    async def close_workers(self, worker_ids: list[str]) -> None:
        """Close workers via Mahavishnu MCP."""
        try:
            # Use MCP tool to close workers
            pass
        except Exception as e:
            logger.warning(f"Failed to close workers: {e}")


class LocalSequentialClient:
    """Fallback client that executes tasks sequentially."""

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path

    async def is_available(self) -> bool:
        """Always available as fallback."""
        return True

    async def spawn_workers(
        self,
        worker_type: str,
        count: int,
    ) -> list[str]:
        """Return virtual worker IDs for sequential execution."""
        return [f"local-worker-{i}" for i in range(count)]

    async def execute_batch(
        self,
        worker_ids: list[str],
        tasks: list[SwarmTask],
    ) -> dict[str, SwarmResult]:
        """Execute tasks sequentially."""
        results: dict[str, SwarmResult] = {}

        for i, task in enumerate(tasks):
            worker_id = worker_ids[i % len(worker_ids)]
            start_time = time.time()

            try:
                # Execute the task using local agent infrastructure
                result = await self._execute_local_task(task)
                result.duration_seconds = time.time() - start_time
                result.worker_id = worker_id
                results[task.task_id] = result
            except Exception as e:
                results[task.task_id] = SwarmResult(
                    task_id=task.task_id,
                    worker_id=worker_id,
                    success=False,
                    errors=[str(e)],
                    duration_seconds=time.time() - start_time,
                )

        return results

    async def _execute_local_task(self, task: SwarmTask) -> SwarmResult:
        """Execute a single task using local agent."""
        # This would integrate with the existing agent infrastructure
        return SwarmResult(
            task_id=task.task_id,
            worker_id="",
            success=True,
            files_modified=task.file_paths,
            fixes_applied=len(task.file_paths),
        )

    async def close_workers(self, worker_ids: list[str]) -> None:
        """No-op for local client."""
        pass


class SwarmManager:
    """Manager for swarm-based auto-fixing with automatic failover."""

    def __init__(
        self,
        project_path: Path,
        prefer_parallel: bool = True,
    ) -> None:
        self.project_path = project_path
        self.prefer_parallel = prefer_parallel

        self._mahavishnu_client = MahavishnuSwarmClient(project_path)
        self._local_client = LocalSequentialClient(project_path)
        self._active_client: SwarmClientProtocol | None = None
        self._worker_ids: list[str] = []

    async def _get_client(self) -> SwarmClientProtocol:
        """Get the best available client with automatic failover."""
        if self._active_client is not None:
            return self._active_client

        if self.prefer_parallel:
            if await self._mahavishnu_client.is_available():
                logger.info("Using Mahavishnu MCP for parallel agent execution")
                self._active_client = self._mahavishnu_client
            else:
                logger.info("Mahavishnu MCP unavailable, falling back to sequential execution")
                self._active_client = self._local_client
        else:
            self._active_client = self._local_client

        return self._active_client

    async def initialize(self, worker_count: int = 4) -> bool:
        """Initialize the swarm with workers."""
        client = await self._get_client()
        self._worker_ids = await client.spawn_workers(
            worker_type="terminal-claude",
            count=worker_count,
        )
        return len(self._worker_ids) > 0

    async def execute_fixes(
        self,
        issues: list[dict[str, t.Any]],
    ) -> list[SwarmResult]:
        """Execute fixes for a batch of issues."""
        if not self._worker_ids:
            await self.initialize()

        client = await self._get_client()

        # Group issues by type for parallel execution
        tasks = self._create_tasks_from_issues(issues)

        # Execute batch
        results = await client.execute_batch(self._worker_ids, tasks)

        return list(results.values())

    def _create_tasks_from_issues(
        self,
        issues: list[dict[str, t.Any]],
    ) -> list[SwarmTask]:
        """Create swarm tasks from issues."""
        tasks: list[SwarmTask] = []

        for i, issue in enumerate(issues):
            task = SwarmTask(
                task_id=f"task-{i}",
                issue_type=issue.get("type", "unknown"),
                file_paths=[issue.get("file", "")],
                prompt=self._create_fix_prompt(issue),
                priority=issue.get("priority", 0),
            )
            tasks.append(task)

        return tasks

    def _create_fix_prompt(self, issue: dict[str, t.Any]) -> str:
        """Create a fix prompt for an issue."""
        return f"Fix {issue.get('type', 'issue')} in {issue.get('file', 'file')}: {issue.get('message', '')}"

    async def shutdown(self) -> None:
        """Shutdown the swarm and release workers."""
        if self._active_client and self._worker_ids:
            await self._active_client.close_workers(self._worker_ids)
            self._worker_ids = []

    @property
    def is_parallel(self) -> bool:
        """Check if using parallel execution."""
        return self._active_client is self._mahavishnu_client
```

### Phase 2: Integration with AutofixCoordinator

Modify `AutofixCoordinator` to optionally use `SwarmManager`:

```python
# In autofix_coordinator.py

def __init__(
    self,
    ...,
    enable_swarm: bool = True,
) -> None:
    ...
    self._swarm_manager: SwarmManager | None = None
    self._enable_swarm = enable_swarm

async def _try_swarm_fix(
    self,
    issues: list[Issue],
) -> list[FixResult]:
    """Attempt to fix issues using swarm if available."""
    if not self._enable_swarm:
        return []

    if self._swarm_manager is None:
        self._swarm_manager = SwarmManager(
            project_path=self.pkg_path,
            prefer_parallel=True,
        )

    # Convert issues to dict format
    issue_dicts = [
        {
            "type": issue.type.value,
            "file": str(issue.file_path),
            "message": issue.message,
            "priority": issue.priority.value,
        }
        for issue in issues
    ]

    results = await self._swarm_manager.execute_fixes(issue_dicts)

    # Convert back to FixResult
    return [
        FixResult(
            success=r.success,
            issue=issues[i] if i < len(issues) else None,
            fixes_applied=r.fixes_applied,
            files_modified=r.files_modified,
        )
        for i, r in enumerate(results)
    ]
```

### Phase 3: MCP Tool Integration

Create MCP tools for swarm management:

```python
# In crackerjack/mcp/tools/swarm_tools.py

from mcp.server import FastMCP

mcp = FastMCP("crackerjack-swarm")


@mcp.tool()
async def swarm_autofix(
    issue_types: list[str],
    max_workers: int = 4,
) -> dict:
    """Run swarm-based auto-fixing for specified issue types."""
    ...


@mcp.tool()
async def swarm_status() -> dict:
    """Get current swarm status and health."""
    ...
```

## Failover Strategy

1. **Health Check**: On initialization, check Mahavishnu MCP availability
2. **Automatic Fallback**: If unavailable, switch to `LocalSequentialClient`
3. **Retry Logic**: Periodically re-check Mahavishnu availability
4. **User Notification**: Log which mode is active

## Benefits

| Aspect | Mahavishnu Available | Fallback Mode |
|--------|---------------------|---------------|
| Parallelism | 4-10 workers concurrent | Sequential |
| Speed | 3-5x faster | Baseline |
| Worktree Isolation | Yes (each worker) | No |
| Resource Usage | Higher (multiple processes) | Lower |

## Testing Strategy

1. **Unit Tests**: Test both clients independently
2. **Integration Tests**: Test failover behavior
3. **E2E Tests**: Test with real Mahavishnu MCP

## Rollout Plan

1. **Phase 1**: Implement protocol and local client
2. **Phase 2**: Add Mahavishnu client
3. **Phase 3**: Integrate with AutofixCoordinator
4. **Phase 4**: Add CLI flag `--swarm` to enable

## CLI Integration

```bash
# Enable swarm mode (parallel if available)
python -m crackerjack run --ai-fix --swarm

# Force sequential even if Mahavishnu available
python -m crackerjack run --ai-fix --no-swarm

# Check swarm status
python -m crackerjack swarm status
```
