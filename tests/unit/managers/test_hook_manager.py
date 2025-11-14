"""Unit tests for HookManager.

Tests hook execution, orchestration, executor configuration,
and statistics collection functionality.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.models.task import HookResult


@pytest.mark.unit
class TestHookManagerInitialization:
    """Test HookManager initialization."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for HookManager."""
        with patch("crackerjack.managers.hook_manager.depends.get_sync") as mock_get:
            mock_console = Mock()
            mock_get.return_value = mock_console
            with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                yield mock_console

    def test_initialization_with_defaults(self, mock_dependencies, tmp_path):
        """Test HookManager initializes with default settings."""
        with patch("crackerjack.managers.hook_manager.ProgressHookExecutor") as mock_executor:
            manager = HookManagerImpl(pkg_path=tmp_path)

            assert manager.pkg_path == tmp_path
            assert manager.debug is False
            assert manager.lsp_optimization_enabled is False
            assert manager.tool_proxy_enabled is True
            assert manager._config_path is None
            mock_executor.assert_called_once()

    def test_initialization_with_lsp_optimization(self, mock_dependencies, tmp_path):
        """Test HookManager initializes with LSP optimization."""
        with patch("crackerjack.managers.hook_manager.LSPAwareHookExecutor") as mock_lsp_exec:
            manager = HookManagerImpl(
                pkg_path=tmp_path,
                enable_lsp_optimization=True,
            )

            assert manager.lsp_optimization_enabled is True
            mock_lsp_exec.assert_called_once()

    def test_initialization_with_incremental_mode(self, mock_dependencies, tmp_path):
        """Test HookManager initializes with incremental execution."""
        with patch("crackerjack.managers.hook_manager.ProgressHookExecutor"):
            with patch("crackerjack.managers.hook_manager.GitService") as mock_git:
                manager = HookManagerImpl(
                    pkg_path=tmp_path,
                    use_incremental=True,
                )

                # GitService should be instantiated for incremental mode
                mock_git.assert_called_once()

    def test_initialization_with_verbose_and_debug(self, mock_dependencies, tmp_path):
        """Test HookManager initializes with verbose and debug flags."""
        with patch("crackerjack.managers.hook_manager.ProgressHookExecutor") as mock_executor:
            manager = HookManagerImpl(
                pkg_path=tmp_path,
                verbose=True,
                debug=True,
            )

            assert manager.debug is True
            call_args = mock_executor.call_args
            assert call_args[1]["verbose"] is True
            assert call_args[1]["debug"] is True

    def test_initialization_loads_orchestration_config(self, mock_dependencies, tmp_path):
        """Test HookManager loads orchestration configuration."""
        with patch("crackerjack.managers.hook_manager.ProgressHookExecutor"):
            with patch("crackerjack.managers.hook_manager.depends.get_sync") as mock_get:
                mock_settings = Mock()
                mock_settings.enable_orchestration = True
                mock_settings.orchestration_mode = "acb"
                mock_get.return_value = mock_settings

                manager = HookManagerImpl(pkg_path=tmp_path)

                assert hasattr(manager, "_orchestration_config")
                assert hasattr(manager, "orchestration_enabled")


@pytest.mark.unit
class TestHookManagerConfiguration:
    """Test HookManager configuration methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager instance for testing."""
        with patch("crackerjack.managers.hook_manager.depends.get_sync"):
            with patch("crackerjack.managers.hook_manager.ProgressHookExecutor"):
                with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                    return HookManagerImpl(pkg_path=tmp_path)

    def test_set_config_path(self, manager, tmp_path):
        """Test setting configuration path."""
        config_path = tmp_path / ".crackerjack.yaml"

        manager.set_config_path(config_path)

        assert manager._config_path == config_path

    def test_configure_lsp_optimization_enable(self, manager):
        """Test enabling LSP optimization."""
        manager.console = Mock()
        manager.lsp_optimization_enabled = False

        with patch("crackerjack.managers.hook_manager.LSPAwareHookExecutor") as mock_lsp:
            manager.configure_lsp_optimization(True)

            assert manager.lsp_optimization_enabled is True
            mock_lsp.assert_called_once()

    def test_configure_lsp_optimization_disable(self, manager):
        """Test disabling LSP optimization."""
        manager.console = Mock()
        manager.lsp_optimization_enabled = True

        with patch("crackerjack.managers.hook_manager.HookExecutor") as mock_exec:
            manager.configure_lsp_optimization(False)

            assert manager.lsp_optimization_enabled is False
            mock_exec.assert_called_once()

    def test_configure_lsp_optimization_already_enabled(self, manager):
        """Test configure LSP optimization when already in correct state."""
        manager.lsp_optimization_enabled = True

        with patch("crackerjack.managers.hook_manager.LSPAwareHookExecutor") as mock_lsp:
            manager.configure_lsp_optimization(True)

            # Should not recreate executor
            mock_lsp.assert_not_called()

    def test_configure_tool_proxy_enable(self, manager):
        """Test enabling tool proxy."""
        manager.console = Mock()
        manager.tool_proxy_enabled = False
        manager.executor = Mock(spec=["verbose", "quiet"])

        with patch("crackerjack.managers.hook_manager.LSPAwareHookExecutor"):
            # Set executor to LSP-aware to trigger recreation
            from crackerjack.executors.lsp_aware_hook_executor import LSPAwareHookExecutor
            manager.executor = Mock(spec=LSPAwareHookExecutor)

            manager.configure_tool_proxy(True)

            assert manager.tool_proxy_enabled is True

    def test_configure_tool_proxy_already_enabled(self, manager):
        """Test configure tool proxy when already enabled."""
        manager.tool_proxy_enabled = True

        with patch("crackerjack.managers.hook_manager.LSPAwareHookExecutor") as mock_lsp:
            manager.configure_tool_proxy(True)

            # Should not recreate executor
            mock_lsp.assert_not_called()


@pytest.mark.unit
class TestHookManagerExecution:
    """Test hook execution methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager with mocked dependencies."""
        with patch("crackerjack.managers.hook_manager.depends.get_sync"):
            with patch("crackerjack.managers.hook_manager.ProgressHookExecutor") as mock_exec_cls:
                with patch("crackerjack.managers.hook_manager.HookConfigLoader") as mock_loader_cls:
                    mock_executor = Mock()
                    mock_exec_cls.return_value = mock_executor

                    mock_loader = Mock()
                    mock_loader_cls.return_value = mock_loader

                    manager = HookManagerImpl(pkg_path=tmp_path)
                    manager.orchestration_enabled = False  # Use legacy path for simplicity
                    return manager

    def test_run_fast_hooks_success(self, manager):
        """Test successful fast hooks execution."""
        expected_results = [
            HookResult(name="ruff", status="passed", duration=1.0),
            HookResult(name="black", status="passed", duration=0.5),
        ]

        mock_strategy = Mock()
        mock_strategy.hooks = []
        manager.config_loader.load_strategy.return_value = mock_strategy

        mock_execution_result = Mock()
        mock_execution_result.results = expected_results
        manager.executor.execute_strategy.return_value = mock_execution_result

        results = manager.run_fast_hooks()

        assert results == expected_results
        manager.config_loader.load_strategy.assert_called_once_with("fast")

    def test_run_comprehensive_hooks_success(self, manager):
        """Test successful comprehensive hooks execution."""
        expected_results = [
            HookResult(name="pyright", status="passed", duration=5.0),
            HookResult(name="bandit", status="passed", duration=3.0),
        ]

        mock_strategy = Mock()
        mock_strategy.hooks = []
        manager.config_loader.load_strategy.return_value = mock_strategy

        mock_execution_result = Mock()
        mock_execution_result.results = expected_results
        manager.executor.execute_strategy.return_value = mock_execution_result

        results = manager.run_comprehensive_hooks()

        assert results == expected_results
        manager.config_loader.load_strategy.assert_called_once_with("comprehensive")

    def test_run_hooks_sequential(self, manager):
        """Test sequential hook execution."""
        fast_results = [HookResult(name="ruff", status="passed", duration=1.0)]
        comp_results = [HookResult(name="pyright", status="passed", duration=5.0)]

        mock_strategy = Mock()
        mock_strategy.hooks = []
        manager.config_loader.load_strategy.return_value = mock_strategy

        # Mock execution results for both strategies
        mock_execution_result1 = Mock()
        mock_execution_result1.results = fast_results
        mock_execution_result2 = Mock()
        mock_execution_result2.results = comp_results

        manager.executor.execute_strategy.side_effect = [
            mock_execution_result1,
            mock_execution_result2,
        ]

        results = manager.run_hooks()

        assert len(results) == 2
        assert results[0] == fast_results[0]
        assert results[1] == comp_results[0]

    def test_run_fast_hooks_with_config_path(self, manager, tmp_path):
        """Test fast hooks execution with config path set."""
        config_path = tmp_path / ".crackerjack.yaml"
        manager.set_config_path(config_path)

        mock_hook1 = Mock()
        mock_hook2 = Mock()
        mock_strategy = Mock()
        mock_strategy.hooks = [mock_hook1, mock_hook2]

        manager.config_loader.load_strategy.return_value = mock_strategy

        mock_execution_result = Mock()
        mock_execution_result.results = []
        manager.executor.execute_strategy.return_value = mock_execution_result

        manager.run_fast_hooks()

        # Verify config path was set on hooks
        assert mock_hook1.config_path == config_path
        assert mock_hook2.config_path == config_path


@pytest.mark.unit
@pytest.mark.asyncio
class TestHookManagerOrchestration:
    """Test orchestrated hook execution."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager with orchestration enabled."""
        with patch("crackerjack.managers.hook_manager.depends.get_sync"):
            with patch("crackerjack.managers.hook_manager.ProgressHookExecutor"):
                with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                    manager = HookManagerImpl(pkg_path=tmp_path)
                    manager.orchestration_enabled = True
                    manager._orchestrator = None
                    return manager

    async def test_init_orchestrator(self, manager):
        """Test orchestrator initialization."""
        with patch("crackerjack.managers.hook_manager.HookOrchestratorAdapter") as mock_orch:
            mock_instance = AsyncMock()
            mock_orch.return_value = mock_instance

            await manager._init_orchestrator()

            assert manager._orchestrator is not None
            mock_instance.init.assert_called_once()

    async def test_init_orchestrator_already_initialized(self, manager):
        """Test orchestrator initialization when already initialized."""
        manager._orchestrator = Mock()

        with patch("crackerjack.managers.hook_manager.HookOrchestratorAdapter") as mock_orch:
            await manager._init_orchestrator()

            # Should not create new orchestrator
            mock_orch.assert_not_called()

    async def test_run_fast_hooks_orchestrated(self, manager):
        """Test orchestrated fast hooks execution."""
        expected_results = [
            HookResult(name="ruff", status="passed", duration=1.0),
        ]

        mock_strategy = Mock()
        mock_strategy.hooks = []
        manager.config_loader.load_strategy.return_value = mock_strategy

        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute_strategy.return_value = expected_results

        with patch.object(manager, "_init_orchestrator", new_callable=AsyncMock):
            manager._orchestrator = mock_orchestrator

            results = await manager._run_fast_hooks_orchestrated()

            assert results == expected_results
            mock_orchestrator.execute_strategy.assert_called_once()

    async def test_run_comprehensive_hooks_orchestrated(self, manager):
        """Test orchestrated comprehensive hooks execution."""
        expected_results = [
            HookResult(name="pyright", status="passed", duration=5.0),
        ]

        mock_strategy = Mock()
        mock_strategy.hooks = []
        manager.config_loader.load_strategy.return_value = mock_strategy

        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute_strategy.return_value = expected_results

        with patch.object(manager, "_init_orchestrator", new_callable=AsyncMock):
            manager._orchestrator = mock_orchestrator

            results = await manager._run_comprehensive_hooks_orchestrated()

            assert results == expected_results

    async def test_run_hooks_parallel(self, manager):
        """Test parallel hook execution."""
        fast_results = [HookResult(name="ruff", status="passed", duration=1.0)]
        comp_results = [HookResult(name="pyright", status="passed", duration=5.0)]

        with patch.object(
            manager, "_run_fast_hooks_orchestrated", new_callable=AsyncMock
        ) as mock_fast:
            with patch.object(
                manager, "_run_comprehensive_hooks_orchestrated", new_callable=AsyncMock
            ) as mock_comp:
                mock_fast.return_value = fast_results
                mock_comp.return_value = comp_results

                results = await manager._run_hooks_parallel()

                assert len(results) == 2
                assert results[0] == fast_results[0]
                assert results[1] == comp_results[0]

    async def test_get_orchestration_stats_enabled(self, manager):
        """Test getting orchestration statistics when enabled."""
        expected_stats = {
            "cache_hits": 10,
            "cache_misses": 5,
            "cache_size": 1024,
        }

        mock_orchestrator = AsyncMock()
        mock_orchestrator.get_cache_stats.return_value = expected_stats

        manager._orchestrator = mock_orchestrator
        manager.orchestration_enabled = True

        stats = await manager.get_orchestration_stats()

        assert stats == expected_stats

    async def test_get_orchestration_stats_disabled(self, manager):
        """Test getting orchestration statistics when disabled."""
        manager.orchestration_enabled = False

        stats = await manager.get_orchestration_stats()

        assert stats is None

    async def test_get_orchestration_stats_not_initialized(self, manager):
        """Test getting orchestration statistics when not initialized."""
        manager.orchestration_enabled = True
        manager._orchestrator = None

        stats = await manager.get_orchestration_stats()

        assert stats is None


@pytest.mark.unit
class TestHookManagerInformation:
    """Test information and statistics methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager instance."""
        with patch("crackerjack.managers.hook_manager.depends.get_sync"):
            with patch("crackerjack.managers.hook_manager.ProgressHookExecutor"):
                with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                    return HookManagerImpl(pkg_path=tmp_path)

    def test_get_execution_info_basic(self, manager):
        """Test getting basic execution information."""
        manager.lsp_optimization_enabled = False
        manager.tool_proxy_enabled = True
        manager.orchestration_enabled = False

        info = manager.get_execution_info()

        assert info["lsp_optimization_enabled"] is False
        assert info["tool_proxy_enabled"] is True
        assert info["orchestration_enabled"] is False
        assert "executor_type" in info

    def test_get_execution_info_with_orchestration(self, manager):
        """Test getting execution info with orchestration enabled."""
        manager.orchestration_enabled = True
        manager.orchestration_mode = "acb"
        manager._orchestration_config = Mock()
        manager._orchestration_config.enable_caching = True
        manager._orchestration_config.cache_backend = "memory"

        info = manager.get_execution_info()

        assert info["orchestration_enabled"] is True
        assert info["orchestration_mode"] == "acb"
        assert info["caching_enabled"] is True
        assert info["cache_backend"] == "memory"

    def test_get_hook_ids(self, manager):
        """Test getting hook IDs."""
        mock_hook1 = Mock()
        mock_hook1.name = "ruff"
        mock_hook2 = Mock()
        mock_hook2.name = "black"
        mock_hook3 = Mock()
        mock_hook3.name = "pyright"

        fast_strategy = Mock()
        fast_strategy.hooks = [mock_hook1, mock_hook2]
        comp_strategy = Mock()
        comp_strategy.hooks = [mock_hook3]

        manager.config_loader.load_strategy.side_effect = [fast_strategy, comp_strategy]

        hook_ids = manager.get_hook_ids()

        assert hook_ids == ["ruff", "black", "pyright"]

    def test_get_hook_count_fast(self, manager):
        """Test getting hook count for fast suite."""
        mock_strategy = Mock()
        mock_strategy.hooks = [Mock(), Mock(), Mock()]

        manager.config_loader.load_strategy.return_value = mock_strategy

        count = manager.get_hook_count("fast")

        assert count == 3
        manager.config_loader.load_strategy.assert_called_once_with("fast")

    def test_get_hook_count_comprehensive(self, manager):
        """Test getting hook count for comprehensive suite."""
        mock_strategy = Mock()
        mock_strategy.hooks = [Mock(), Mock(), Mock(), Mock(), Mock()]

        manager.config_loader.load_strategy.return_value = mock_strategy

        count = manager.get_hook_count("comprehensive")

        assert count == 5
        manager.config_loader.load_strategy.assert_called_once_with("comprehensive")

    def test_get_hook_summary_success(self):
        """Test getting hook summary with successful results."""
        results = [
            HookResult(name="ruff", status="passed", duration=1.0),
            HookResult(name="black", status="passed", duration=0.5),
            HookResult(name="pyright", status="passed", duration=5.0),
        ]

        summary = HookManagerImpl.get_hook_summary(results)

        assert summary["total"] == 3
        assert summary["passed"] == 3
        assert summary["failed"] == 0
        assert summary["errors"] == 0
        assert summary["total_duration"] == 6.5
        assert summary["success_rate"] == 100.0

    def test_get_hook_summary_with_failures(self):
        """Test getting hook summary with failures."""
        results = [
            HookResult(name="ruff", status="passed", duration=1.0),
            HookResult(name="black", status="failed", duration=0.5),
            HookResult(name="pyright", status="passed", duration=5.0),
        ]

        summary = HookManagerImpl.get_hook_summary(results)

        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["errors"] == 0
        assert summary["success_rate"] == pytest.approx(66.67, rel=0.01)

    def test_get_hook_summary_with_errors(self):
        """Test getting hook summary with errors."""
        results = [
            HookResult(name="ruff", status="passed", duration=1.0),
            HookResult(name="black", status="timeout", duration=30.0),
            HookResult(name="pyright", status="error", duration=0.0),
        ]

        summary = HookManagerImpl.get_hook_summary(results)

        assert summary["total"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 0
        assert summary["errors"] == 2
        assert summary["success_rate"] == pytest.approx(33.33, rel=0.01)

    def test_get_hook_summary_empty_results(self):
        """Test getting hook summary with empty results."""
        summary = HookManagerImpl.get_hook_summary([])

        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["errors"] == 0
        assert summary["total_duration"] == 0
        assert summary["success_rate"] == 0

    def test_get_hook_summary_with_elapsed_time(self):
        """Test getting hook summary with wall-clock elapsed time."""
        results = [
            HookResult(name="ruff", status="passed", duration=1.0),
            HookResult(name="black", status="passed", duration=0.5),
        ]

        # In parallel execution, wall-clock time is less than sum of durations
        summary = HookManagerImpl.get_hook_summary(results, elapsed_time=1.2)

        assert summary["total_duration"] == 1.2  # Wall-clock time, not sum


@pytest.mark.unit
class TestHookManagerDeprecatedMethods:
    """Test deprecated methods for backward compatibility."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create HookManager instance."""
        with patch("crackerjack.managers.hook_manager.depends.get_sync"):
            with patch("crackerjack.managers.hook_manager.ProgressHookExecutor"):
                with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                    manager = HookManagerImpl(pkg_path=tmp_path)
                    manager.console = Mock()
                    return manager

    def test_validate_hooks_config(self):
        """Test validate_hooks_config always returns True."""
        result = HookManagerImpl.validate_hooks_config()

        assert result is True

    def test_install_hooks(self, manager):
        """Test install_hooks returns True with info message."""
        result = manager.install_hooks()

        assert result is True
        manager.console.print.assert_called_once()

    def test_update_hooks(self, manager):
        """Test update_hooks returns True with info message."""
        result = manager.update_hooks()

        assert result is True
        manager.console.print.assert_called_once()


@pytest.mark.unit
class TestHookManagerOrchestrationConfig:
    """Test orchestration configuration loading."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.enable_orchestration = True
        settings.orchestration_mode = "acb"
        return settings

    def test_load_config_from_explicit_param(self, tmp_path, mock_settings):
        """Test loading config from explicit parameter."""
        with patch("crackerjack.managers.hook_manager.depends.get_sync") as mock_get:
            mock_get.return_value = mock_settings
            with patch("crackerjack.managers.hook_manager.ProgressHookExecutor"):
                with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                    explicit_config = Mock()
                    explicit_config.orchestration_mode = "custom"
                    explicit_config.enable_caching = True

                    manager = HookManagerImpl(
                        pkg_path=tmp_path,
                        orchestration_config=explicit_config,
                    )

                    assert manager._orchestration_config == explicit_config

    def test_load_config_from_project_file(self, tmp_path, mock_settings):
        """Test loading config from project .crackerjack.yaml."""
        # Create project config file
        config_path = tmp_path / ".crackerjack.yaml"
        config_path.write_text("enable_orchestration: true\norchestration_mode: acb\n")

        with patch("crackerjack.managers.hook_manager.depends.get_sync") as mock_get:
            mock_get.return_value = mock_settings
            with patch("crackerjack.managers.hook_manager.ProgressHookExecutor"):
                with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                    with patch("crackerjack.managers.hook_manager.OrchestrationConfig") as mock_config:
                        mock_loaded = Mock()
                        mock_loaded.enable_orchestration = True
                        mock_loaded.orchestration_mode = "acb"
                        mock_config.load.return_value = mock_loaded

                        manager = HookManagerImpl(pkg_path=tmp_path)

                        assert manager._orchestration_config == mock_loaded

    def test_load_config_creates_default(self, tmp_path, mock_settings):
        """Test creating default config when no project file exists."""
        with patch("crackerjack.managers.hook_manager.depends.get_sync") as mock_get:
            mock_get.return_value = mock_settings
            with patch("crackerjack.managers.hook_manager.ProgressHookExecutor"):
                with patch("crackerjack.managers.hook_manager.HookConfigLoader"):
                    with patch("crackerjack.managers.hook_manager.HookOrchestratorSettings") as mock_settings_cls:
                        mock_default = Mock()
                        mock_settings_cls.return_value = mock_default

                        manager = HookManagerImpl(
                            pkg_path=tmp_path,
                            enable_caching=True,
                            cache_backend="redis",
                        )

                        mock_settings_cls.assert_called_once()
                        assert manager._orchestration_config == mock_default
