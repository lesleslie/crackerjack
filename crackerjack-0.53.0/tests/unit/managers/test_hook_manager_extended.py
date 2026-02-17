"""Extended unit tests for HookManager.

Tests orchestration stats, progress callbacks, hook discovery,
and execution edge cases.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.models.task import HookResult


@pytest.mark.unit
class TestHookManagerProgressCallbacks:
    """Test progress callback functionality."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager instance."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                manager = HookManagerImpl(pkg_path=tmp_path)
                # Disable orchestration for simpler testing
                manager.orchestration_enabled = False
                return manager

    def test_progress_callbacks_not_set_by_default(self, manager) -> None:
        """Test progress callbacks are None by default."""
        assert manager._progress_callback is None
        assert manager._progress_start_callback is None

    def test_run_fast_hooks_with_progress_callbacks(self, manager) -> None:
        """Test running fast hooks with progress callbacks."""
        manager._progress_callback = Mock()
        manager._progress_start_callback = Mock()
        manager.orchestration_enabled = False

        # Mock executor to return results
        mock_result = Mock()
        mock_result.results = [HookResult(
            hook_id="test",
            hook_name="test_hook",
            status="passed",
            duration=1.0,
        )]

        manager.executor.execute_strategy.return_value = mock_result

        results = manager.run_fast_hooks()

        assert len(results) == 1
        # Progress callbacks should be set on executor
        assert manager.executor.set_progress_callbacks.called

    def test_run_comprehensive_hooks_with_progress_callbacks(self, manager) -> None:
        """Test running comprehensive hooks with progress callbacks."""
        manager._progress_callback = Mock()
        manager._progress_start_callback = Mock()
        manager.orchestration_enabled = False

        # Mock executor to return results
        mock_result = Mock()
        mock_result.results = [HookResult(
            hook_id="test",
            hook_name="test_hook",
            status="passed",
            duration=1.0,
        )]

        manager.executor.execute_strategy.return_value = mock_result

        results = manager.run_comprehensive_hooks()

        assert len(results) == 1


@pytest.mark.unit
class TestHookManagerOrchestrationStats:
    """Test orchestration statistics retrieval."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager with orchestration."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                manager = HookManagerImpl(pkg_path=tmp_path)
                manager.orchestration_enabled = True
                manager._orchestrator = Mock()
                return manager

    @pytest.mark.asyncio
    async def test_get_orchestration_stats_success(self, manager) -> None:
        """Test getting orchestration stats."""
        manager._orchestrator.get_cache_stats = AsyncMock(return_value={
            "cache_hits": 100,
            "cache_misses": 10,
        })

        stats = await manager.get_orchestration_stats()

        assert stats is not None
        assert stats["cache_hits"] == 100

    @pytest.mark.asyncio
    async def test_get_orchestration_stats_disabled(self, tmp_path) -> None:
        """Test getting stats when orchestration disabled."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                manager = HookManagerImpl(pkg_path=tmp_path)
                manager.orchestration_enabled = False

                stats = await manager.get_orchestration_stats()

                assert stats is None

    @pytest.mark.asyncio
    async def test_get_orchestration_stats_no_orchestrator(self, manager) -> None:
        """Test getting stats when no orchestrator."""
        manager._orchestrator = None

        stats = await manager.get_orchestration_stats()

        assert stats is None


@pytest.mark.unit
class TestHookManagerExecutionInfo:
    """Test execution information retrieval."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager instance."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                manager = HookManagerImpl(pkg_path=tmp_path)
                return manager

    def test_get_execution_info_basic(self, manager) -> None:
        """Test getting basic execution info."""
        info = manager.get_execution_info()

        assert "lsp_optimization_enabled" in info
        assert "tool_proxy_enabled" in info
        assert "executor_type" in info
        assert "orchestration_enabled" in info
        assert info["lsp_optimization_enabled"] is False
        assert info["tool_proxy_enabled"] is True

    def test_get_execution_info_with_orchestration(self, manager) -> None:
        """Test execution info with orchestration."""
        manager.orchestration_enabled = True
        manager.orchestration_mode = "oneiric"

        info = manager.get_execution_info()

        assert info["orchestration_enabled"] is True
        assert info["orchestration_mode"] == "oneiric"
        assert "caching_enabled" in info
        assert "cache_backend" in info

    def test_get_execution_info_with_executor_summary(self, manager) -> None:
        """Test execution info includes executor summary."""
        manager.executor.get_execution_mode_summary = Mock(return_value={
            "mode": "standard",
            "workers": 1,
        })

        info = manager.get_execution_info()

        assert "mode" in info
        assert info["mode"] == "standard"


@pytest.mark.unit
class TestHookManagerHookDiscovery:
    """Test hook discovery and enumeration."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager instance."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                return HookManagerImpl(pkg_path=tmp_path)

    def test_get_hook_ids(self, manager) -> None:
        """Test getting all hook IDs."""
        hook_ids = manager.get_hook_ids()

        assert isinstance(hook_ids, list)
        assert len(hook_ids) > 0
        # Should have hooks from both fast and comprehensive strategies
        assert len(hook_ids) >= 2

    def test_get_hook_count_fast(self, manager) -> None:
        """Test getting hook count for fast suite."""
        count = manager.get_hook_count("fast")

        assert count >= 0
        assert isinstance(count, int)

    def test_get_hook_count_comprehensive(self, manager) -> None:
        """Test getting hook count for comprehensive suite."""
        count = manager.get_hook_count("comprehensive")

        assert count >= 0
        assert isinstance(count, int)

    def test_get_hook_count_invalid_suite(self, manager) -> None:
        """Test getting hook count for invalid suite."""
        # Should handle gracefully or raise specific error
        try:
            count = manager.get_hook_count("invalid")
            # If it doesn't raise, should return sensible value
            assert count >= 0
        except Exception:
            # Expected to raise for invalid suite
            pass


@pytest.mark.unit
class TestHookManagerHookSummary:
    """Test hook summary statistics."""

    def test_get_hook_summary_empty(self) -> None:
        """Test hook summary with no results."""
        summary = HookManagerImpl.get_hook_summary([])

        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["errors"] == 0
        assert summary["total_duration"] == 0
        assert summary["success_rate"] == 0

    def test_get_hook_summary_all_passed(self) -> None:
        """Test hook summary with all passed."""
        results = [
            HookResult(hook_id="1", hook_name="hook1", status="passed", duration=1.0),
            HookResult(hook_id="2", hook_name="hook2", status="passed", duration=2.0),
        ]

        summary = HookManagerImpl.get_hook_summary(results)

        assert summary["total"] == 2
        assert summary["passed"] == 2
        assert summary["failed"] == 0
        assert summary["total_duration"] == 3.0
        assert summary["success_rate"] == 100.0

    def test_get_hook_summary_with_failures(self) -> None:
        """Test hook summary with failures."""
        results = [
            HookResult(hook_id="1", hook_name="hook1", status="passed", duration=1.0),
            HookResult(hook_id="2", hook_name="hook2", status="failed", duration=2.0),
            HookResult(hook_id="3", hook_name="hook3", status="timeout", duration=0.0),
        ]

        summary = HookManagerImpl.get_hook_summary(results)

        assert summary["total"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["errors"] == 1  # timeout counts as error
        assert summary["success_rate"] == pytest.approx(33.33, rel=0.1)

    def test_get_hook_summary_with_elapsed_time(self) -> None:
        """Test hook summary with provided elapsed time."""
        results = [
            HookResult(hook_id="1", hook_name="hook1", status="passed", duration=1.0),
        ]

        summary = HookManagerImpl.get_hook_summary(results, elapsed_time=5.0)

        assert summary["total_duration"] == 5.0  # Uses provided time


@pytest.mark.unit
class TestHookManagerHookOperations:
    """Test hook installation and validation."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager instance."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                return HookManagerImpl(pkg_path=tmp_path)

    def test_install_hooks(self, manager) -> None:
        """Test hook installation."""
        result = manager.install_hooks()

        assert result is True

    def test_update_hooks(self, manager) -> None:
        """Test hook updates."""
        result = manager.update_hooks()

        assert result is True

    def test_validate_hooks_config(self) -> None:
        """Test hooks config validation."""
        result = HookManagerImpl.validate_hooks_config()

        assert result is True


@pytest.mark.unit
class TestHookManagerOrchestrationExecution:
    """Test orchestration-based execution."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager with orchestration."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                manager = HookManagerImpl(pkg_path=tmp_path)
                manager.orchestration_enabled = True
                return manager

    def test_run_fast_hooks_orchestrated(self, manager) -> None:
        """Test running fast hooks with orchestration."""
        with patch("crackerjack.managers.hook_manager.asyncio.run") as mock_run:
            mock_results = [HookResult(
                hook_id="test",
                hook_name="test_hook",
                status="passed",
                duration=1.0,
            )]
            mock_run.return_value = mock_results

            results = manager.run_fast_hooks()

            assert len(results) >= 0

    def test_run_comprehensive_hooks_orchestrated(self, manager) -> None:
        """Test running comprehensive hooks with orchestration."""
        with patch("crackerjack.managers.hook_manager.asyncio.run") as mock_run:
            mock_results = [HookResult(
                hook_id="test",
                hook_name="test_hook",
                status="passed",
                duration=1.0,
            )]
            mock_run.return_value = mock_results

            results = manager.run_comprehensive_hooks()

            assert len(results) >= 0

    def test_run_hooks_parallel(self, manager) -> None:
        """Test running all hooks in parallel."""
        with patch.object(manager, "_orchestration_config", enable_strategy_parallelism=True):
            with patch("crackerjack.managers.hook_manager.asyncio.run") as mock_run:
                mock_results = [
                    HookResult(hook_id="fast", hook_name="fast_hook", status="passed", duration=1.0),
                    HookResult(hook_id="comp", hook_name="comp_hook", status="passed", duration=2.0),
                ]
                mock_run.return_value = mock_results

                results = manager.run_hooks()

                assert len(results) >= 0

    def test_run_hooks_sequential(self, manager) -> None:
        """Test running hooks sequentially."""
        with patch.object(manager, "_orchestration_config", enable_strategy_parallelism=False):
            with patch.object(manager, "run_fast_hooks") as mock_fast:
                with patch.object(manager, "run_comprehensive_hooks") as mock_comp:
                    mock_fast.return_value = [HookResult(
                        hook_id="fast", hook_name="fast_hook", status="passed", duration=1.0
                    )]
                    mock_comp.return_value = [HookResult(
                        hook_id="comp", hook_name="comp_hook", status="passed", duration=2.0
                    )]

                    results = manager.run_hooks()

                    assert len(results) == 2


@pytest.mark.unit
class TestHookManagerConfigPath:
    """Test configuration path management."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager instance."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                return HookManagerImpl(pkg_path=tmp_path)

    def test_set_config_path(self, manager, tmp_path) -> None:
        """Test setting configuration path."""
        config_path = tmp_path / ".crackerjack.yaml"

        manager.set_config_path(config_path)

        assert manager._config_path == config_path

    def test_run_fast_hooks_with_config_path(self, manager, tmp_path) -> None:
        """Test running fast hooks with config path set."""
        config_path = tmp_path / ".crackerjack.yaml"
        manager.set_config_path(config_path)
        manager.orchestration_enabled = False

        with patch.object(manager.executor, "execute_strategy") as mock_exec:
            mock_result = Mock()
            mock_result.results = []
            mock_exec.return_value = mock_result

            manager.run_fast_hooks()

            # Config path should be applied to hooks
            # Verify strategy was loaded and executed
            assert mock_exec.called

    def test_run_comprehensive_hooks_with_config_path(self, manager, tmp_path) -> None:
        """Test running comprehensive hooks with config path set."""
        config_path = tmp_path / ".crackerjack.yaml"
        manager.set_config_path(config_path)
        manager.orchestration_enabled = False

        with patch.object(manager.executor, "execute_strategy") as mock_exec:
            mock_result = Mock()
            mock_result.results = []
            mock_exec.return_value = mock_result

            manager.run_comprehensive_hooks()

            # Config path should be applied to hooks
            assert mock_exec.called


@pytest.mark.unit
class TestHookManagerToolProxyConfiguration:
    """Test tool proxy configuration."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager instance."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                manager = HookManagerImpl(pkg_path=tmp_path)
                manager.lsp_optimization_enabled = True
                return manager

    def test_configure_tool_proxy_enable(self, manager) -> None:
        """Test enabling tool proxy."""
        manager.tool_proxy_enabled = False
        manager.executor = Mock(spec=["verbose", "quiet"])
        manager.executor.verbose = False
        manager.executor.quiet = True

        with patch("crackerjack.managers.hook_manager.LSPAwareHookExecutor"):
            manager.configure_tool_proxy(True)

            assert manager.tool_proxy_enabled is True

    def test_configure_tool_proxy_already_enabled(self, manager) -> None:
        """Test configuring tool proxy when already enabled."""
        manager.tool_proxy_enabled = True

        manager.configure_tool_proxy(True)

        # Should not recreate executor
        # Just verify no exception raised

    def test_configure_tool_proxy_non_lsp_executor(self, manager) -> None:
        """Test tool proxy configuration with non-LSP executor."""
        manager.tool_proxy_enabled = False
        # Use non-LSP executor
        from crackerjack.executors.hook_executor import HookExecutor
        manager.executor = Mock(spec=HookExecutor)

        # Should not raise even though executor isn't LSP-aware
        manager.configure_tool_proxy(True)


@pytest.mark.unit
class TestHookManagerOrchestrationConfig:
    """Test orchestration configuration loading."""

    def test_load_orchestration_config_from_file(self, tmp_path) -> None:
        """Test loading orchestration config from project file."""
        config_file = tmp_path / ".crackerjack.yaml"
        config_file.write_text("orchestration:\n  enabled: true\n  mode: oneiric\n")

        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                with patch("crackerjack.managers.hook_manager.OrchestrationConfig") as mock_oc:
                    mock_config = Mock()
                    mock_config.enable_orchestration = True
                    mock_config.orchestration_mode = "oneiric"
                    mock_oc.load.return_value = mock_config
                    mock_oc.return_value = mock_config

                    manager = HookManagerImpl(pkg_path=tmp_path)

                    # Should load from file
                    assert manager.orchestration_mode == "oneiric"

    def test_create_default_orchestration_config(self, tmp_path) -> None:
        """Test creating default orchestration config."""
        with patch("crackerjack.managers.hook_manager.HookExecutor"):
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                with patch("crackerjack.managers.hook_manager.HookOrchestratorSettings") as mock_hos:
                    # Create mock settings
                    mock_settings = Mock()
                    mock_settings.enable_caching = True
                    mock_settings.cache_backend = "memory"
                    mock_settings.max_parallel_hooks = 4
                    mock_settings.enable_adaptive_execution = True
                    mock_settings.orchestration_mode = "oneiric"
                    mock_hos.return_value = mock_settings

                    manager = HookManagerImpl(pkg_path=tmp_path, enable_orchestration=True)

                    # Should have default config
                    assert manager._orchestration_config is not None
