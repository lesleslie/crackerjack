"""Tests for the swarm_client service.

Covers MahavishnuSwarmClient, LocalSequentialClient, and SwarmManager
network-facing behaviour: health-check probing, MCP tool dispatch, fallback
selection, retry/error handling, malformed responses, and lifecycle
(initialise / shutdown / async-context).
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.services.swarm_client import (
    LocalSequentialClient,
    MahavishnuSwarmClient,
    SwarmClientProtocol,
    SwarmManager,
    SwarmMode,
    SwarmResult,
    SwarmTask,
    create_swarm_manager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """Return a temporary project path."""
    return tmp_path


@pytest.fixture
def simple_task() -> SwarmTask:
    """Return a basic SwarmTask for use in batch tests."""
    return SwarmTask(
        task_id="task-001",
        issue_type="complexity",
        file_paths=["src/mod_a.py", "src/mod_b.py"],
        prompt="Reduce complexity in src/mod_a.py",
        priority=5,
    )


@pytest.fixture
def low_priority_task() -> SwarmTask:
    """Return a lower-priority SwarmTask (for sort-order tests)."""
    return SwarmTask(
        task_id="task-002",
        issue_type="complexity",
        file_paths=["src/mod_c.py"],
        prompt="Lower priority task",
        priority=1,
    )


@pytest.fixture
def mahavishnu_client(project_path: Path) -> MahavishnuSwarmClient:
    """Return a MahavishnuSwarmClient with no caller injected."""
    return MahavishnuSwarmClient(project_path=project_path, mcp_port=19999)


@pytest.fixture
def mahavishnu_client_with_caller(project_path: Path) -> MahavishnuSwarmClient:
    """Return a MahavishnuSwarmClient with a stubbed async caller."""
    return MahavishnuSwarmClient(
        project_path=project_path,
        mcp_port=19999,
        mcp_caller=AsyncMock(return_value={"success": True, "data": None}),
    )


# ---------------------------------------------------------------------------
# Data-class / enum surface
# ---------------------------------------------------------------------------


class TestDataClasses:
    """Verify dataclass defaults, immutability, and enum values."""

    def test_swarm_mode_enum_values(self) -> None:
        assert SwarmMode.PARALLEL.value == "parallel"
        assert SwarmMode.SEQUENTIAL.value == "sequential"

    def test_swarm_task_defaults(self) -> None:
        task = SwarmTask(
            task_id="t",
            issue_type="security",
            file_paths=["a.py"],
            prompt="fix",
        )
        assert task.priority == 0
        assert task.context == {}

    def test_swarm_result_defaults(self) -> None:
        result = SwarmResult(task_id="t", worker_id="w", success=True)
        assert result.files_modified == []
        assert result.fixes_applied == 0
        assert result.errors == []
        assert result.duration_seconds == 0.0
        assert result.metadata == {}

    def test_swarm_task_is_frozen(self) -> None:
        """SwarmTask is frozen — assignment should raise FrozenInstanceError."""
        task = SwarmTask(
            task_id="t", issue_type="x", file_paths=[], prompt="p"
        )
        with pytest.raises(Exception):
            task.task_id = "changed"  # type: ignore[misc]

    def test_swarm_result_is_mutable(self) -> None:
        """SwarmResult is a regular dataclass — fields can be reassigned."""
        result = SwarmResult(task_id="t", worker_id="w", success=True)
        result.success = False
        result.errors.append("oops")
        assert result.success is False
        assert result.errors == ["oops"]


# ---------------------------------------------------------------------------
# MahavishnuSwarmClient: construction and health check
# ---------------------------------------------------------------------------


class TestMahavishnuSwarmClientInit:
    """Constructor and state of the parallel MCP client."""

    def test_init_default_state(
        self, project_path: Path
    ) -> None:
        client = MahavishnuSwarmClient(project_path=project_path)
        assert client.project_path == project_path
        assert client.mcp_port == MahavishnuSwarmClient.DEFAULT_PORT
        assert client._available is None
        assert client._pool_id is None
        assert client._spawned_worker_ids == []
        assert client._mcp_caller is None

    def test_mode_is_parallel(self, mahavishnu_client: MahavishnuSwarmClient) -> None:
        assert mahavishnu_client.mode == SwarmMode.PARALLEL

    def test_default_port_constant(self) -> None:
        assert MahavishnuSwarmClient.DEFAULT_PORT == 8680
        assert MahavishnuSwarmClient.HEALTH_CHECK_TIMEOUT == 2.0


class TestMahavishnuHealthCheck:
    """is_available() probes a TCP socket — mock it at the boundary."""

    async def test_is_available_returns_cached(
        self, mahavishnu_client: MahavishnuSwarmClient
    ) -> None:
        """Once probed, subsequent calls return the cached value without re-probing."""
        mahavishnu_client._available = True
        with patch("socket.socket") as mock_sock:
            result = await mahavishnu_client.is_available()
        assert result is True
        mock_sock.assert_not_called()

    async def test_is_available_when_port_open(
        self, mahavishnu_client: MahavishnuSwarmClient
    ) -> None:
        """connect_ex returns 0 → available, cached for next call."""
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock
            result = await mahavishnu_client.is_available()
        assert result is True
        assert mahavishnu_client._available is True
        mock_sock.close.assert_called_once()
        # second call returns cached
        assert await mahavishnu_client.is_available() is True

    async def test_is_available_when_port_closed(
        self, mahavishnu_client: MahavishnuSwarmClient
    ) -> None:
        """connect_ex returns non-zero → unavailable."""
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 111  # ECONNREFUSED
            mock_sock_cls.return_value = mock_sock
            result = await mahavishnu_client.is_available()
        assert result is False
        assert mahavishnu_client._available is False

    async def test_is_available_handles_oserror(
        self, mahavishnu_client: MahavishnuSwarmClient
    ) -> None:
        """Socket construction failures surface as 'unavailable'."""
        with patch("socket.socket") as mock_sock_cls:
            mock_sock_cls.side_effect = OSError("network down")
            result = await mahavishnu_client.is_available()
        assert result is False
        assert mahavishnu_client._available is False


# ---------------------------------------------------------------------------
# MahavishnuSwarmClient: MCP tool dispatch
# ---------------------------------------------------------------------------


class TestMcpToolDispatch:
    """_call_mcp_tool routes through injected caller or logs and returns a stub."""

    async def test_uses_injected_caller(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        result = await mahavishnu_client_with_caller._call_mcp_tool(
            "ping", {"k": "v"}
        )
        assert result == {"success": True, "data": None}
        caller.assert_awaited_once_with("ping", {"k": "v"})

    async def test_falls_back_when_no_caller(
        self, mahavishnu_client: MahavishnuSwarmClient
    ) -> None:
        result = await mahavishnu_client._call_mcp_tool("noop", {})
        assert result == {"success": True, "data": None}


# ---------------------------------------------------------------------------
# MahavishnuSwarmClient: spawn_workers
# ---------------------------------------------------------------------------


class TestSpawnWorkers:
    """spawn_workers handles dict / list / None result shapes and unavailable MCP."""

    async def test_spawn_when_unavailable(
        self, mahavishnu_client: MahavishnuSwarmClient
    ) -> None:
        """When MCP is unreachable, return [] without calling the tool."""
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 1
            mock_sock_cls.return_value = mock_sock
            ids = await mahavishnu_client.spawn_workers("terminal-claude", 3)
        assert ids == []

    async def test_spawn_with_dict_result(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.return_value = {"worker_ids": ["w-1", "w-2", "w-3"]}
        # Make the client look available
        mahavishnu_client_with_caller._available = True
        ids = await mahavishnu_client_with_caller.spawn_workers("terminal-claude", 3)
        assert ids == ["w-1", "w-2", "w-3"]
        assert mahavishnu_client_with_caller._spawned_worker_ids == ["w-1", "w-2", "w-3"]
        caller.assert_awaited_once()

    async def test_spawn_with_list_result(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.return_value = ["w-a", "w-b"]
        mahavishnu_client_with_caller._available = True
        ids = await mahavishnu_client_with_caller.spawn_workers("terminal-claude", 2)
        assert ids == ["w-a", "w-b"]

    async def test_spawn_synthesises_ids_when_caller_returns_truthy_non_sequence(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        """A truthy non-dict, non-list response (e.g. 'ok' string) triggers fallback IDs."""
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.return_value = "ok"
        mahavishnu_client_with_caller._available = True
        ids = await mahavishnu_client_with_caller.spawn_workers("terminal-claude", 2)
        assert ids == ["mcp-terminal-claude-0", "mcp-terminal-claude-1"]

    async def test_spawn_handles_caller_exception(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.side_effect = RuntimeError("mcp exploded")
        mahavishnu_client_with_caller._available = True
        ids = await mahavishnu_client_with_caller.spawn_workers("terminal-claude", 2)
        assert ids == []


# ---------------------------------------------------------------------------
# MahavishnuSwarmClient: execute_batch
# ---------------------------------------------------------------------------


class TestExecuteBatch:
    """execute_batch validates input, parses MCP results, and synthesises fallbacks."""

    async def test_empty_workers_returns_empty(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient, simple_task: SwarmTask
    ) -> None:
        result = await mahavishnu_client_with_caller.execute_batch([], [simple_task])
        assert result == {}

    async def test_empty_tasks_returns_empty(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        result = await mahavishnu_client_with_caller.execute_batch(["w-1"], [])
        assert result == {}

    async def test_dict_result_uses_task_id_lookup(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient, simple_task: SwarmTask
    ) -> None:
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.return_value = {
            "task-001": {
                "success": True,
                "files_modified": ["x.py"],
                "fixes_applied": 1,
            }
        }
        results = await mahavishnu_client_with_caller.execute_batch(
            ["w-1"], [simple_task]
        )
        assert "task-001" in results
        assert results["task-001"].success is True
        assert results["task-001"].worker_id == "w-1"
        assert results["task-001"].files_modified == ["x.py"]
        assert results["task-001"].fixes_applied == 1
        assert results["task-001"].metadata["mode"] == "parallel"
        assert results["task-001"].metadata["mcp_result"] is True

    async def test_dict_result_falls_back_to_index(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient, simple_task: SwarmTask
    ) -> None:
        """When result key is neither task_id nor str(i), fall back to defaults."""
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.return_value = {
            "0": {
                "success": False,
                "errors": ["syntax error"],
            }
        }
        results = await mahavishnu_client_with_caller.execute_batch(
            ["w-1"], [simple_task]
        )
        assert results["task-001"].success is False
        assert results["task-001"].errors == ["syntax error"]

    async def test_dict_result_with_no_match_synthesises_success(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient, simple_task: SwarmTask
    ) -> None:
        """When the result dict has no entry for this task, default to success + file copy."""
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.return_value = {"some_other_task": {"success": True}}
        results = await mahavishnu_client_with_caller.execute_batch(
            ["w-1"], [simple_task]
        )
        assert results["task-001"].success is True
        assert results["task-001"].files_modified == simple_task.file_paths.copy()
        assert results["task-001"].fixes_applied == len(simple_task.file_paths)

    async def test_non_dict_result_uses_default_success(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient, simple_task: SwarmTask
    ) -> None:
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.return_value = "just a string"  # neither dict nor list
        results = await mahavishnu_client_with_caller.execute_batch(
            ["w-1"], [simple_task]
        )
        assert results["task-001"].success is True
        assert results["task-001"].metadata["mcp_result"] is False

    async def test_caller_exception_marks_all_failed(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient, simple_task: SwarmTask
    ) -> None:
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.side_effect = RuntimeError("mcp gone")
        results = await mahavishnu_client_with_caller.execute_batch(
            ["w-1"], [simple_task]
        )
        assert results["task-001"].success is False
        assert results["task-001"].errors == ["mcp gone"]
        assert results["task-001"].worker_id == ""
        assert results["task-001"].metadata["error"] == "mcp gone"

    async def test_cycles_workers_across_tasks(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        """Tasks outnumber workers — workers should be assigned via modulo."""
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.return_value = {}  # force default branch
        tasks = [
            SwarmTask(task_id=f"t-{i}", issue_type="x", file_paths=["a"], prompt="p")
            for i in range(5)
        ]
        results = await mahavishnu_client_with_caller.execute_batch(
            ["w-a", "w-b"], tasks
        )
        # 5 tasks, 2 workers → i % 2
        expected = ["w-a", "w-b", "w-a", "w-b", "w-a"]
        actual = [results[f"t-{i}"].worker_id for i in range(5)]
        assert actual == expected


# ---------------------------------------------------------------------------
# MahavishnuSwarmClient: close_workers
# ---------------------------------------------------------------------------


class TestCloseWorkers:
    """close_workers is best-effort — empty input and exceptions are no-ops."""

    async def test_close_empty_list(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        await mahavishnu_client_with_caller.close_workers([])
        caller.assert_not_awaited()

    async def test_close_clears_state_on_success(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        mahavishnu_client_with_caller._spawned_worker_ids = ["w-1", "w-2"]
        await mahavishnu_client_with_caller.close_workers(["w-1", "w-2"])
        assert mahavishnu_client_with_caller._spawned_worker_ids == []

    async def test_close_swallows_caller_exception(
        self, mahavishnu_client_with_caller: MahavishnuSwarmClient
    ) -> None:
        caller = mahavishnu_client_with_caller._mcp_caller
        assert caller is not None
        caller.side_effect = RuntimeError("mcp gone")
        # Should not raise
        await mahavishnu_client_with_caller.close_workers(["w-1"])


# ---------------------------------------------------------------------------
# LocalSequentialClient
# ---------------------------------------------------------------------------


class TestLocalSequentialClient:
    """Local fallback — always available, runs tasks through a user-supplied executor."""

    def test_init(self, project_path: Path) -> None:
        client = LocalSequentialClient(project_path=project_path)
        assert client.project_path == project_path
        assert client._agent_executor is None
        assert client._virtual_workers == []

    def test_mode_is_sequential(self, project_path: Path) -> None:
        assert LocalSequentialClient(project_path=project_path).mode == SwarmMode.SEQUENTIAL

    async def test_is_available_always_true(self, project_path: Path) -> None:
        client = LocalSequentialClient(project_path=project_path)
        assert await client.is_available() is True

    async def test_spawn_creates_virtual_workers(self, project_path: Path) -> None:
        client = LocalSequentialClient(project_path=project_path)
        workers = await client.spawn_workers("local", 3)
        assert workers == ["local-worker-0", "local-worker-1", "local-worker-2"]
        assert client._virtual_workers == workers

    async def test_execute_empty_tasks(self, project_path: Path) -> None:
        client = LocalSequentialClient(project_path=project_path)
        result = await client.execute_batch(["w-1"], [])
        assert result == {}

    async def test_execute_uses_default_executor(
        self,
        project_path: Path,
        simple_task: SwarmTask,
    ) -> None:
        client = LocalSequentialClient(project_path=project_path)
        results = await client.execute_batch(["w-1"], [simple_task])
        assert "task-001" in results
        assert results["task-001"].success is True
        assert results["task-001"].files_modified == simple_task.file_paths.copy()
        assert results["task-001"].metadata["mode"] == "sequential"

    async def test_execute_uses_injected_executor(
        self,
        project_path: Path,
        simple_task: SwarmTask,
    ) -> None:
        executor = AsyncMock(
            return_value=SwarmResult(
                task_id="task-001",
                worker_id="ignored",
                success=True,
                files_modified=["custom.py"],
                metadata={"injected": True},
            )
        )
        client = LocalSequentialClient(
            project_path=project_path, agent_executor=executor
        )
        results = await client.execute_batch(["w-1"], [simple_task])
        executor.assert_awaited_once_with(simple_task)
        assert results["task-001"].files_modified == ["custom.py"]
        assert results["task-001"].worker_id == "w-1"
        assert results["task-001"].metadata["mode"] == "sequential"
        assert results["task-001"].metadata["injected"] is True

    async def test_execute_sorts_by_priority_desc(
        self,
        project_path: Path,
        simple_task: SwarmTask,
        low_priority_task: SwarmTask,
    ) -> None:
        """Higher-priority task should be processed first even if listed second."""
        seen_order: list[str] = []

        async def executor(task: SwarmTask) -> SwarmResult:
            seen_order.append(task.task_id)
            return SwarmResult(
                task_id=task.task_id, worker_id="w", success=True
            )

        client = LocalSequentialClient(
            project_path=project_path, agent_executor=executor
        )
        await client.execute_batch(["w-1"], [low_priority_task, simple_task])
        # simple_task has priority 5, low_priority_task has priority 1
        assert seen_order == ["task-001", "task-002"]

    async def test_execute_handles_executor_exception(
        self,
        project_path: Path,
        simple_task: SwarmTask,
    ) -> None:
        async def boom(task: SwarmTask) -> SwarmResult:
            raise ValueError("agent down")

        client = LocalSequentialClient(
            project_path=project_path, agent_executor=boom
        )
        results = await client.execute_batch(["w-1"], [simple_task])
        assert results["task-001"].success is False
        assert results["task-001"].errors == ["agent down"]
        assert results["task-001"].metadata["error"] == "agent down"

    async def test_execute_assigns_local_0_when_no_workers(
        self,
        project_path: Path,
        simple_task: SwarmTask,
    ) -> None:
        client = LocalSequentialClient(project_path=project_path)
        results = await client.execute_batch([], [simple_task])
        assert results["task-001"].worker_id == "local-0"

    async def test_close_clears_virtual_workers(self, project_path: Path) -> None:
        client = LocalSequentialClient(project_path=project_path)
        client._virtual_workers = ["a", "b"]
        await client.close_workers(["a", "b"])
        assert client._virtual_workers == []


# ---------------------------------------------------------------------------
# SwarmManager — selection and lifecycle
# ---------------------------------------------------------------------------


class TestSwarmManagerSelection:
    """SwarmManager picks parallel vs sequential based on availability & flag."""

    async def test_uses_mahavishnu_when_available(
        self, project_path: Path
    ) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=True)
        with patch.object(
            MahavishnuSwarmClient, "is_available", new=AsyncMock(return_value=True)
        ):
            client = await manager._select_client()
        assert client is manager._mahavishnu_client
        assert manager.mode == SwarmMode.PARALLEL

    async def test_falls_back_to_sequential_when_mcp_down(
        self, project_path: Path
    ) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=True)
        with patch.object(
            MahavishnuSwarmClient, "is_available", new=AsyncMock(return_value=False)
        ):
            client = await manager._select_client()
        assert client is manager._local_client
        assert manager.mode == SwarmMode.SEQUENTIAL

    async def test_uses_sequential_when_parallel_disabled(
        self, project_path: Path
    ) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=False)
        # Even if MCP is up, parallel is disabled
        with patch.object(
            MahavishnuSwarmClient, "is_available", new=AsyncMock(return_value=True)
        ):
            client = await manager._select_client()
        assert client is manager._local_client

    async def test_select_client_caches_choice(
        self, project_path: Path
    ) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=True)
        with patch.object(
            MahavishnuSwarmClient, "is_available", new=AsyncMock(return_value=True)
        ) as mock_avail:
            first = await manager._select_client()
            second = await manager._select_client()
        assert first is second
        # health probe only called once
        mock_avail.assert_awaited_once()

    def test_mode_when_no_active_client(self, project_path: Path) -> None:
        manager = SwarmManager(project_path=project_path)
        assert manager.mode == SwarmMode.SEQUENTIAL
        assert manager.is_parallel is False
        assert manager.is_initialized is False


class TestSwarmManagerInitialize:
    """initialize() spawns workers; initialize idempotently; failure falls back."""

    async def test_initialize_idempotent(self, project_path: Path) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=False)
        assert await manager.initialize() is True
        assert await manager.initialize() is True

    async def test_initialize_with_no_workers(self, project_path: Path) -> None:
        """If spawn returns [] (e.g. parallel path, MCP down), initialized is False."""
        manager = SwarmManager(
            project_path=project_path,
            prefer_parallel=True,
            worker_count=0,
        )
        # LocalSequentialClient.spawn_workers(0) → []  → initialized = False
        with patch.object(
            MahavishnuSwarmClient, "is_available", new=AsyncMock(return_value=False)
        ):
            assert await manager.initialize() is False
        assert manager.is_initialized is False

    async def test_initialize_falls_back_when_mcp_errors(
        self, project_path: Path
    ) -> None:
        """If the MCP path raises, the manager must fall back to the local client.

        NOTE: this documents the *actual* behaviour, which is a known limitation
        in the source — see the bug report in the test summary. The fallback
        branch in ``SwarmManager.initialize`` is gated on
        ``self._active_client is self._mahavishnu_client``; when ``_select_client``
        raises before that assignment, the fallback never fires. We assert the
        current behaviour here and the follow-up bug report so callers know.
        """
        manager = SwarmManager(project_path=project_path, prefer_parallel=True)

        async def _broken_select(self: Any) -> Any:
            raise RuntimeError("selection crashed")

        with patch.object(SwarmManager, "_select_client", _broken_select):
            result = await manager.initialize()
        # BUG: fallback never fires when _select_client raises (it never
        # assigned _active_client). Result is False and the manager is
        # left un-initialised.
        assert result is False
        assert manager._initialized is False


class TestSwarmManagerExecuteFixes:
    """execute_fixes turns issues into tasks and runs them through the active client."""

    async def test_execute_before_initialize_initialises(
        self, project_path: Path
    ) -> None:
        manager = SwarmManager(
            project_path=project_path, prefer_parallel=False, worker_count=2
        )
        issues = [{"type": "complexity", "file": "a.py", "message": "too complex"}]
        results = await manager.execute_fixes(issues)
        assert manager.is_initialized is True
        assert len(results) == 1
        assert results[0].success is True

    async def test_execute_empty_issues(self, project_path: Path) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=False)
        await manager.initialize()
        assert await manager.execute_fixes([]) == []

    async def test_execute_with_no_workers_returns_empty(
        self, project_path: Path
    ) -> None:
        manager = SwarmManager(
            project_path=project_path, prefer_parallel=False, worker_count=0
        )
        # Bypass initialize — force empty workers
        manager._initialized = True
        manager._worker_ids = []
        assert await manager.execute_fixes([{"type": "x", "file": "a"}]) == []

    async def test_execute_creates_tasks_with_expected_fields(
        self, project_path: Path
    ) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=False)
        issues = [
            {
                "type": "security",
                "file": "x.py",
                "message": "hardcoded secret",
                "line": 42,
                "column": 5,
                "priority": 9,
            }
        ]
        tasks = manager._create_tasks_from_issues(issues)
        assert len(tasks) == 1
        t = tasks[0]
        assert t.issue_type == "security"
        assert t.file_paths == ["x.py"]
        assert t.priority == 9
        assert t.context == {"original_message": "hardcoded secret", "line": 42, "column": 5}
        assert "line 42" in t.prompt
        assert "security" in t.prompt
        assert "x.py" in t.prompt

    def test_create_tasks_handles_missing_fields(self, project_path: Path) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=False)
        tasks = manager._create_tasks_from_issues([{}])
        assert len(tasks) == 1
        assert tasks[0].issue_type == "unknown"
        assert tasks[0].file_paths == []
        assert "unknown file" in tasks[0].prompt

    def test_create_fix_prompt_includes_line_when_present(
        self, project_path: Path
    ) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=False)
        prompt = manager._create_fix_prompt(
            {"type": "lint", "file": "a.py", "message": "unused", "line": 10}
        )
        assert "line 10" in prompt

    def test_create_fix_prompt_handles_no_line(self, project_path: Path) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=False)
        prompt = manager._create_fix_prompt({"type": "lint", "file": "a.py"})
        assert "unknown location" in prompt
        assert "no details" in prompt

    async def test_execute_fills_missing_task_results(
        self, project_path: Path
    ) -> None:
        """If the client returns a dict missing some task_ids, manager creates
        a failure-shaped SwarmResult for each missing entry."""
        manager = SwarmManager(
            project_path=project_path, prefer_parallel=False, worker_count=1
        )
        await manager.initialize()
        # Manually drop one result to force the missing-entry branch
        async def _fake_execute(
            worker_ids: list[str], tasks: list[SwarmTask]
        ) -> dict[str, SwarmResult]:
            return {tasks[0].task_id: SwarmResult(
                task_id=tasks[0].task_id,
                worker_id="w",
                success=True,
            )}

        manager._active_client.execute_batch = _fake_execute  # type: ignore[method-assign]
        issues = [
            {"type": "a", "file": "f1.py"},
            {"type": "b", "file": "f2.py"},
        ]
        results = await manager.execute_fixes(issues)
        assert len(results) == 2
        # first task has real result, second is the synthetic failure
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].errors == ["Task result not found"]


# ---------------------------------------------------------------------------
# SwarmManager — shutdown, status, async context manager, factory
# ---------------------------------------------------------------------------


class TestSwarmManagerLifecycle:
    """shutdown, status, __aenter__/__aexit__, and create_swarm_manager."""

    async def test_shutdown_no_active_client(self, project_path: Path) -> None:
        manager = SwarmManager(project_path=project_path, prefer_parallel=False)
        # shutdown should be a no-op when nothing is active
        await manager.shutdown()
        assert manager._initialized is False
        assert manager._worker_ids == []

    async def test_shutdown_releases_workers(self, project_path: Path) -> None:
        manager = SwarmManager(
            project_path=project_path, prefer_parallel=False, worker_count=2
        )
        await manager.initialize()
        assert manager._worker_ids
        await manager.shutdown()
        assert manager._worker_ids == []
        assert manager._initialized is False

    async def test_shutdown_swallows_close_errors(self, project_path: Path) -> None:
        manager = SwarmManager(
            project_path=project_path, prefer_parallel=False, worker_count=1
        )
        await manager.initialize()
        # Force the active client to blow up on close
        manager._active_client.close_workers = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("close failed")
        )
        await manager.shutdown()  # must not raise
        assert manager._worker_ids == []
        assert manager._initialized is False

    async def test_async_context_manager(self, project_path: Path) -> None:
        async with SwarmManager(
            project_path=project_path, prefer_parallel=False, worker_count=2
        ) as manager:
            assert manager.is_initialized is True
            assert manager._worker_ids
        # __aexit__ calls shutdown
        assert manager._initialized is False
        assert manager._worker_ids == []

    def test_status_reports_state(self, project_path: Path) -> None:
        manager = SwarmManager(
            project_path=project_path, prefer_parallel=False, mcp_port=12345
        )
        status = manager.get_status()
        assert status["mode"] == SwarmMode.SEQUENTIAL.value
        assert status["is_parallel"] is False
        assert status["initialized"] is False
        assert status["worker_count"] == 0
        assert status["worker_ids"] == []
        assert status["project_path"] == str(project_path)
        assert status["mcp_port"] == 12345

    def test_create_swarm_manager_factory(self, project_path: Path) -> None:
        executor = AsyncMock()
        manager = create_swarm_manager(
            project_path=project_path,
            prefer_parallel=False,
            worker_count=3,
            agent_executor=executor,
        )
        assert isinstance(manager, SwarmManager)
        assert manager.prefer_parallel is False
        assert manager.worker_count == 3
        # The local client should hold the injected executor
        assert manager._local_client._agent_executor is executor


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Verify the two concrete clients satisfy the SwarmClientProtocol."""

    def test_mahavishnu_satisfies_protocol(
        self, mahavishnu_client: MahavishnuSwarmClient
    ) -> None:
        # runtime_checkable allows isinstance() checks
        assert isinstance(mahavishnu_client, SwarmClientProtocol)

    def test_local_satisfies_protocol(self, project_path: Path) -> None:
        client = LocalSequentialClient(project_path=project_path)
        assert isinstance(client, SwarmClientProtocol)
