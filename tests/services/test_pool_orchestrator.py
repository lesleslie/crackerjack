"""Tests for PoolOrchestrator service."""

from pathlib import Path
from unittest.mock import MagicMock, Mock
from typing import Any

import pytest

from crackerjack.services.pool_orchestrator import PoolOrchestrator


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    """Create a temporary repository path."""
    return tmp_path


@pytest.fixture
def mock_pool_client() -> Mock:
    """Create a mock MahavishnuPoolClient."""
    client = MagicMock()
    client.is_available = True
    client.pool_id = "test-pool-123"
    return client


@pytest.fixture
def console(repo_path: Path) -> Any:
    """Create Console instance."""
    from crackerjack.core.console import CrackerjackConsole
    return CrackerjackConsole()


@pytest.fixture
def pool_orchestrator(
    repo_path: Path,
    mock_pool_client: Mock,
    console: Any,
) -> PoolOrchestrator:
    """Create PoolOrchestrator instance."""
    return PoolOrchestrator(
        pool_client=mock_pool_client,
        pkg_path=repo_path,
        console=console,
        verbose=True,
        debug=True,
    )


class TestPoolOrchestratorInit:
    """Test PoolOrchestrator initialization."""

    def test_init_with_params(
        self,
        repo_path: Path,
        mock_pool_client: Mock,
        console: Any,
    ) -> None:
        """Test initialization with parameters."""
        orchestrator = PoolOrchestrator(
            pool_client=mock_pool_client,
            pkg_path=repo_path,
            console=console,
        )

        assert orchestrator.pool_client == mock_pool_client
        assert orchestrator.pkg_path == repo_path
        assert orchestrator.console == console
        assert orchestrator.verbose is False
        assert orchestrator.debug is False

    def test_init_with_verbose_debug(
        self,
        repo_path: Path,
        mock_pool_client: Mock,
        console: Any,
    ) -> None:
        """Test initialization with verbose and debug enabled."""
        orchestrator = PoolOrchestrator(
            pool_client=mock_pool_client,
            pkg_path=repo_path,
            console=console,
            verbose=True,
            debug=True,
        )

        assert orchestrator.verbose is True
        assert orchestrator.debug is True


class TestServiceProtocol:
    """Test ServiceProtocol implementation."""

    def test_initialize(self, pool_orchestrator: PoolOrchestrator) -> None:
        """Test initialize method."""
        pool_orchestrator.initialize()
        # Should not raise

    def test_cleanup(self, pool_orchestrator: PoolOrchestrator) -> None:
        """Test cleanup method."""
        pool_orchestrator.cleanup()
        # Should not raise

    def test_health_check(self, pool_orchestrator: PoolOrchestrator) -> None:
        """Test health_check method."""
        assert pool_orchestrator.health_check() is True

    def test_shutdown(self, pool_orchestrator: PoolOrchestrator) -> None:
        """Test shutdown method."""
        pool_orchestrator.shutdown()
        # Should not raise


class TestExecuteHooksWithPools:
    """Test execute_hooks_with_pools() method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_pools_disabled(
        self,
        pool_orchestrator: PoolOrchestrator,
        repo_path: Path,
    ) -> None:
        """Test that fallback happens when use_pool=False."""
        from crackerjack.config.hooks import HookDefinition, HookStage

        hook = HookDefinition(
            name="test-tool",
            command=["test-tool"],
            timeout=60,
            stage=HookStage.FAST,
            accepts_file_paths=True,
        )

        result = await pool_orchestrator.execute_hooks_with_pools(
            hooks=[hook],
            file_filter=None,
            use_pool=False,
        )

        # Should return PoolExecutionResult with fallback_used=True
        assert result is not None
        assert result.fallback_used is True
        assert result.pool_used is False

    @pytest.mark.asyncio
    async def test_fallback_to_standard_when_pool_unavailable(
        self,
        repo_path: Path,
        console: Any,
    ) -> None:
        """Test fallback when pool client reports unavailable."""
        from crackerjack.config.hooks import HookDefinition, HookStage

        # Create mock pool client that reports unavailable
        mock_client = MagicMock()
        mock_client.is_available = False

        orchestrator = PoolOrchestrator(
            pool_client=mock_client,
            pkg_path=repo_path,
            console=console,
        )

        hook = HookDefinition(
            name="test-tool",
            command=["test-tool"],
            timeout=60,
            stage=HookStage.FAST,
            accepts_file_paths=False,
        )

        result = await orchestrator.execute_hooks_with_pools(
            hooks=[hook],
            file_filter=None,
            use_pool=True,
        )

        # Should fallback to standard execution
        assert result is not None
        assert result.fallback_used is True
        assert result.pool_used is False

    @pytest.mark.asyncio
    async def test_successfully_executes_with_mock_pool(
        self,
        pool_orchestrator: PoolOrchestrator,
        mock_pool_client: Mock,
    ) -> None:
        """Test successful execution with mocked pool."""
        from crackerjack.config.hooks import HookDefinition, HookStage

        hook = HookDefinition(
            name="tool1",
            command=["tool1"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            accepts_file_paths=True,
        )

        # Mock pool client methods
        mock_pool_client.ensure_pool.return_value = "test-pool-123"
        mock_pool_client.execute_tools_parallel.return_value = {
            "tool1": {
                "success": True,
                "exit_code": 0,
                "duration": 1.5,
                "files": [],
                "output": "Success",
                "error": "",
            }
        }

        result = await pool_orchestrator.execute_hooks_with_pools(
            hooks=[hook],
            file_filter=None,
            use_pool=True,
        )

        # Should return PoolExecutionResult with success
        assert result is not None
        assert result.success is True
        assert result.pool_used is True
        assert result.fallback_used is False
        assert len(result.results) == 1


class TestGroupHooksByFiles:
    """Test _group_hooks_by_files() method."""

    def test_groups_hooks_accepting_file_paths(
        self,
        pool_orchestrator: PoolOrchestrator,
        repo_path: Path,
    ) -> None:
        """Test grouping hooks that accept file paths."""
        from crackerjack.config.hooks import HookDefinition, HookStage

        hook1 = HookDefinition(
            name="tool1",
            command=["tool1"],
            timeout=60,
            stage=HookStage.FAST,
            accepts_file_paths=True,
        )

        hook2 = HookDefinition(
            name="tool2",
            command=["tool2"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            accepts_file_paths=False,
        )

        file_filter = MagicMock()
        file_filter.get_files_for_scan.return_value = [
            repo_path / "file1.py",
            repo_path / "file2.py",
        ]

        result = pool_orchestrator._group_hooks_by_files(
            hooks=[hook1, hook2],
            file_filter=file_filter,
        )

        # Should return tool_files dict with only hook1
        assert "tool1" in result
        assert "tool2" not in result

    def test_returns_empty_dict_when_no_file_filter(
        self,
        pool_orchestrator: PoolOrchestrator,
    ) -> None:
        """Test that empty dict is returned when no file filter."""
        from crackerjack.config.hooks import HookDefinition, HookStage

        hooks = [
            HookDefinition(
                name="tool1",
                command=["tool1"],
                timeout=60,
                stage=HookStage.FAST,
                accepts_file_paths=False,
            ),
        ]

        result = pool_orchestrator._group_hooks_by_files(
            hooks=hooks,
            file_filter=None,
        )

        # Should return empty dict (no hooks accept file paths)
        assert result == {}


class TestConvertPoolResultsToHookResults:
    """Test _convert_pool_results_to_hook_results() method."""

    def test_converts_success_results(
        self,
        pool_orchestrator: PoolOrchestrator,
    ) -> None:
        """Test converting successful pool results."""
        from crackerjack.config.hooks import HookDefinition, HookStage
        from crackerjack.models.task import HookResult

        hooks = [
            HookDefinition(
                name="tool1",
                command=["tool1"],
                timeout=60,
                stage=HookStage.FAST,
            ),
            HookDefinition(
                name="tool2",
                command=["tool2"],
                timeout=60,
                stage=HookStage.COMPREHENSIVE,
            ),
        ]

        pool_results = {
            "tool1": {
                "success": True,
                "exit_code": 0,
                "duration": 1.5,
                "files": [],
                "output": "output1",
                "error": "",
            },
            "tool2": {
                "success": True,
                "exit_code": 0,
                "duration": 2.0,
                "files": [],
                "output": "output2",
                "error": "",
            },
        }

        result = pool_orchestrator._convert_pool_results_to_hook_results(
            pool_results=pool_results,
            hooks=hooks,
        )

        assert len(result) == 2
        assert all(isinstance(r, HookResult) for r in result)
        assert result[0].hook_name == "tool1"
        assert result[0].status == "passed"
        assert result[1].hook_name == "tool2"
        assert result[1].status == "passed"

    def test_converts_mixed_results(
        self,
        pool_orchestrator: PoolOrchestrator,
    ) -> None:
        """Test converting mixed pool results."""
        from crackerjack.config.hooks import HookDefinition, HookStage
        from crackerjack.models.task import HookResult

        hooks = [
            HookDefinition(
                name="tool1",
                command=["tool1"],
                timeout=60,
                stage=HookStage.FAST,
            ),
            HookDefinition(
                name="tool2",
                command=["tool2"],
                timeout=60,
                stage=HookStage.COMPREHENSIVE,
            ),
        ]

        pool_results = {
            "tool1": {
                "success": True,
                "exit_code": 0,
                "duration": 1.5,
                "files": [],
                "output": "output1",
                "error": "",
            },
            "tool2": {
                "success": False,
                "exit_code": 1,
                "duration": 0.5,
                "files": [],
                "output": "",
                "error": "error2",
            },
        }

        result = pool_orchestrator._convert_pool_results_to_hook_results(
            pool_results=pool_results,
            hooks=hooks,
        )

        assert len(result) == 2
        assert result[0].status == "passed"
        assert result[1].status == "failed"


class TestCleanup:
    """Test cleanup() method."""

    def test_cleanup_closes_pool(
        self,
        pool_orchestrator: PoolOrchestrator,
        mock_pool_client: Mock,
    ) -> None:
        """Test that cleanup closes the pool."""
        pool_orchestrator.cleanup()

        # Verify close was called
        mock_pool_client.close_pool.assert_called_once()

    def test_cleanup_handles_missing_close_method(
        self,
        repo_path: Path,
        console: Any,
    ) -> None:
        """Test cleanup when pool_client doesn't have close_pool."""
        mock_client = MagicMock(spec=[])  # No methods
        orchestrator = PoolOrchestrator(
            pool_client=mock_client,
            pkg_path=repo_path,
            console=console,
        )

        # Should not raise
        orchestrator.cleanup()
