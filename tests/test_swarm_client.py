"""Tests for the swarm client with Mahavishnu MCP integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.services.swarm_client import (
    LocalSequentialClient,
    MahavishnuSwarmClient,
    SwarmManager,
    SwarmMode,
    SwarmResult,
    SwarmTask,
    create_swarm_manager,
)


class TestMahavishnuSwarmClient:
    """Tests for the Mahavishnu MCP client."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> MahavishnuSwarmClient:
        return MahavishnuSwarmClient(project_path=tmp_path, mcp_port=8680)

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_port_unreachable(
        self, client: MahavishnuSwarmClient
    ) -> None:
        """Should return False when MCP port is not reachable."""
        # Use a port that's very unlikely to be open
        client.mcp_port = 59999
        result = await client.is_available()
        assert result is False
        assert client.mode == SwarmMode.PARALLEL

    @pytest.mark.asyncio
    async def test_is_available_caches_result(
        self, client: MahavishnuSwarmClient
    ) -> None:
        """Should cache availability check result."""
        client.mcp_port = 59999  # Unreachable port

        # First check
        result1 = await client.is_available()
        assert result1 is False

        # Second check should use cached value
        result2 = await client.is_available()
        assert result2 is False

    @pytest.mark.asyncio
    async def test_spawn_workers_returns_empty_when_unavailable(
        self, client: MahavishnuSwarmClient
    ) -> None:
        """Should return empty list when MCP is unavailable."""
        client.mcp_port = 59999
        worker_ids = await client.spawn_workers("terminal-claude", 4)
        assert worker_ids == []

    @pytest.mark.asyncio
    async def test_spawn_workers_returns_ids_when_available(
        self, client: MahavishnuSwarmClient
    ) -> None:
        """Should return worker IDs when MCP is available."""

        async def mock_mcp_caller(tool_name: str, args: dict) -> dict:
            if tool_name == "worker_spawn":
                return {"worker_ids": [f"mcp-worker-{i}" for i in range(args["count"])]}
            return {}

        client._mcp_caller = mock_mcp_caller
        client._available = True

        worker_ids = await client.spawn_workers("terminal-claude", 4)
        assert len(worker_ids) == 4
        assert all("mcp-worker-" in wid for wid in worker_ids)

    @pytest.mark.asyncio
    async def test_execute_batch_creates_results(self, client: MahavishnuSwarmClient) -> None:
        """Should create results for all tasks."""
        client._available = True

        tasks = [
            SwarmTask(
                task_id="task-1",
                issue_type="typing",
                file_paths=["src/main.py"],
                prompt="Fix typing",
            ),
            SwarmTask(
                task_id="task-2",
                issue_type="refurb",
                file_paths=["src/utils.py"],
                prompt="Fix refurb",
            ),
        ]

        worker_ids = ["mcp-worker-0", "mcp-worker-1"]
        results = await client.execute_batch(worker_ids, tasks)

        assert len(results) == 2
        assert "task-1" in results
        assert "task-2" in results
        assert results["task-1"].success is True
        assert results["task-2"].success is True

    @pytest.mark.asyncio
    async def test_close_workers_no_error(self, client: MahavishnuSwarmClient) -> None:
        """Should not raise error when closing workers."""
        # Should not raise
        await client.close_workers(["mcp-worker-0", "mcp-worker-1"])


class TestLocalSequentialClient:
    """Tests for the local sequential fallback client."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> LocalSequentialClient:
        return LocalSequentialClient(project_path=tmp_path)

    @pytest.mark.asyncio
    async def test_is_always_available(self, client: LocalSequentialClient) -> None:
        """Should always return True as fallback."""
        assert await client.is_available() is True
        assert client.mode == SwarmMode.SEQUENTIAL

    @pytest.mark.asyncio
    async def test_spawn_workers_creates_virtual_ids(
        self, client: LocalSequentialClient
    ) -> None:
        """Should create virtual worker IDs."""
        worker_ids = await client.spawn_workers("local", 4)
        assert len(worker_ids) == 4
        assert all("local-worker-" in wid for wid in worker_ids)

    @pytest.mark.asyncio
    async def test_execute_batch_runs_sequentially(
        self, client: LocalSequentialClient
    ) -> None:
        """Should execute tasks sequentially."""
        tasks = [
            SwarmTask(
                task_id="task-1",
                issue_type="typing",
                file_paths=["src/main.py"],
                prompt="Fix typing",
                priority=1,
            ),
            SwarmTask(
                task_id="task-2",
                issue_type="refurb",
                file_paths=["src/utils.py"],
                prompt="Fix refurb",
                priority=2,  # Higher priority
            ),
        ]

        worker_ids = await client.spawn_workers("local", 2)
        results = await client.execute_batch(worker_ids, tasks)

        assert len(results) == 2
        assert all(r.success for r in results.values())

    @pytest.mark.asyncio
    async def test_execute_batch_with_custom_executor(
        self, tmp_path: Path
    ) -> None:
        """Should use custom executor when provided."""
        custom_results: list[str] = []

        async def custom_executor(task: SwarmTask) -> SwarmResult:
            custom_results.append(task.task_id)
            return SwarmResult(
                task_id=task.task_id,
                worker_id="",
                success=True,
                fixes_applied=99,
            )

        client = LocalSequentialClient(
            project_path=tmp_path,
            agent_executor=custom_executor,
        )

        tasks = [
            SwarmTask(
                task_id="custom-task",
                issue_type="test",
                file_paths=[],
                prompt="Test",
            ),
        ]

        worker_ids = await client.spawn_workers("local", 1)
        results = await client.execute_batch(worker_ids, tasks)

        assert custom_results == ["custom-task"]
        assert results["custom-task"].fixes_applied == 99

    @pytest.mark.asyncio
    async def test_close_workers_no_error(self, client: LocalSequentialClient) -> None:
        """Should not raise error when closing virtual workers."""
        # Should not raise
        await client.close_workers(["local-worker-0"])


class TestSwarmManager:
    """Tests for the SwarmManager with automatic failover."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> SwarmManager:
        return SwarmManager(
            project_path=tmp_path,
            prefer_parallel=True,
            worker_count=4,
            mcp_port=59999,  # Unreachable to force fallback
        )

    @pytest.mark.asyncio
    async def test_falls_back_to_sequential_when_mcp_unavailable(
        self, manager: SwarmManager
    ) -> None:
        """Should use sequential mode when Mahavishnu is unavailable."""
        await manager.initialize()

        assert manager.is_initialized is True
        assert manager.is_parallel is False
        assert manager.mode == SwarmMode.SEQUENTIAL

    @pytest.mark.asyncio
    async def test_uses_parallel_when_mcp_available(self, tmp_path: Path) -> None:
        """Should use parallel mode when Mahavishnu is available."""

        async def mock_mcp_caller(tool_name: str, args: dict) -> dict:
            if tool_name == "worker_spawn":
                return {"worker_ids": [f"mcp-worker-{i}" for i in range(args.get("count", 4))]}
            return {}

        manager = SwarmManager(
            project_path=tmp_path,
            prefer_parallel=True,
            worker_count=4,
            mcp_port=8680,
        )

        # Mock the availability check and provide MCP caller
        manager._mahavishnu_client._available = True
        manager._mahavishnu_client._mcp_caller = mock_mcp_caller

        await manager.initialize()

        assert manager.is_initialized is True
        assert manager.mode == SwarmMode.PARALLEL
        assert manager.is_parallel is True

    @pytest.mark.asyncio
    async def test_can_disable_parallel(self, tmp_path: Path) -> None:
        """Should use sequential when parallel is disabled."""
        manager = SwarmManager(
            project_path=tmp_path,
            prefer_parallel=False,  # Disabled
            worker_count=4,
        )

        await manager.initialize()

        assert manager.mode == SwarmMode.SEQUENTIAL

    @pytest.mark.asyncio
    async def test_execute_fixes_creates_tasks(
        self, manager: SwarmManager
    ) -> None:
        """Should create tasks from issues and execute them."""
        await manager.initialize()

        issues = [
            {"type": "typing", "file": "src/main.py", "message": "Name defined"},
            {"type": "refurb", "file": "src/utils.py", "message": "FURB123"},
        ]

        results = await manager.execute_fixes(issues)

        assert len(results) == 2
        assert all(r.task_id.startswith("task-") for r in results)

    @pytest.mark.asyncio
    async def test_shutdown_releases_workers(
        self, manager: SwarmManager
    ) -> None:
        """Should release workers on shutdown."""
        await manager.initialize()
        assert manager.is_initialized is True

        await manager.shutdown()

        assert manager.is_initialized is False
        assert len(manager._worker_ids) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, tmp_path: Path) -> None:
        """Should work as async context manager."""
        manager = SwarmManager(
            project_path=tmp_path,
            prefer_parallel=False,  # Force sequential for test
            mcp_port=59999,
        )

        async with manager as m:
            assert m.is_initialized is True
            results = await m.execute_fixes([
                {"type": "test", "file": "test.py", "message": "Test issue"}
            ])
            assert len(results) == 1

        # After context exit, should be shut down
        assert manager.is_initialized is False

    @pytest.mark.asyncio
    async def test_get_status(self, manager: SwarmManager) -> None:
        """Should return status dictionary."""
        await manager.initialize()

        status = manager.get_status()

        assert "mode" in status
        assert "is_parallel" in status
        assert "initialized" in status
        assert "worker_count" in status
        assert status["initialized"] is True

    @pytest.mark.asyncio
    async def test_empty_issues_returns_empty_results(
        self, manager: SwarmManager
    ) -> None:
        """Should return empty list when no issues provided."""
        await manager.initialize()

        results = await manager.execute_fixes([])

        assert results == []


class TestCreateSwarmManager:
    """Tests for the factory function."""

    def test_creates_manager_with_defaults(self, tmp_path: Path) -> None:
        """Should create manager with default settings."""
        manager = create_swarm_manager(project_path=tmp_path)

        assert manager.project_path == tmp_path
        assert manager.prefer_parallel is True
        assert manager.worker_count == 4

    def test_creates_manager_with_custom_settings(self, tmp_path: Path) -> None:
        """Should create manager with custom settings."""
        manager = create_swarm_manager(
            project_path=tmp_path,
            prefer_parallel=False,
            worker_count=8,
        )

        assert manager.prefer_parallel is False
        assert manager.worker_count == 8


class TestSwarmTask:
    """Tests for SwarmTask dataclass."""

    def test_task_creation(self) -> None:
        """Should create task with all fields."""
        task = SwarmTask(
            task_id="test-1",
            issue_type="typing",
            file_paths=["a.py", "b.py"],
            prompt="Fix typing issues",
            priority=5,
            context={"line": 10},
        )

        assert task.task_id == "test-1"
        assert task.issue_type == "typing"
        assert len(task.file_paths) == 2
        assert task.priority == 5
        assert task.context["line"] == 10

    def test_task_defaults(self) -> None:
        """Should use default values."""
        task = SwarmTask(
            task_id="test-2",
            issue_type="refurb",
            file_paths=[],
            prompt="Fix",
        )

        assert task.priority == 0
        assert task.context == {}


class TestSwarmResult:
    """Tests for SwarmResult dataclass."""

    def test_result_creation(self) -> None:
        """Should create result with all fields."""
        result = SwarmResult(
            task_id="test-1",
            worker_id="worker-1",
            success=True,
            files_modified=["a.py"],
            fixes_applied=3,
            errors=[],
            duration_seconds=1.5,
            metadata={"mode": "parallel"},
        )

        assert result.success is True
        assert result.fixes_applied == 3
        assert result.duration_seconds == 1.5

    def test_result_defaults(self) -> None:
        """Should use default values."""
        result = SwarmResult(
            task_id="test-2",
            worker_id="worker-2",
            success=False,
        )

        assert result.files_modified == []
        assert result.fixes_applied == 0
        assert result.errors == []
        assert result.metadata == {}
