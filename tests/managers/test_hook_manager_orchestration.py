"""Integration tests for HookManager with HookOrchestratorAdapter (Phase 3).

Tests the integration between HookManagerImpl and HookOrchestratorAdapter to ensure:
- Orchestrator initialization on first use
- Dual execution paths (legacy vs orchestrated)
- Configuration propagation
- Statistics tracking
- Backward compatibility with existing workflows
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.models.task import HookResult


@pytest.fixture
def console() -> Console:
    """Create Rich console for testing."""
    return Console()


@pytest.fixture
def pkg_path(tmp_path: Path) -> Path:
    """Create temporary package path."""
    return tmp_path


class TestHookManagerOrchestrationIntegration:
    """Test HookManager integration with orchestrator."""

    def test_initialization_without_orchestration(self, console: Console, pkg_path: Path):
        """Test that orchestration is disabled by default."""
        manager = HookManagerImpl(console=console, pkg_path=pkg_path)

        assert manager.orchestration_enabled is False
        assert manager._orchestrator is None

    def test_initialization_with_orchestration(self, console: Console, pkg_path: Path):
        """Test initialization with orchestration enabled."""
        manager = HookManagerImpl(
            console=console,
            pkg_path=pkg_path,
            enable_orchestration=True,
            orchestration_mode="acb",
            enable_caching=True,
            cache_backend="memory",
        )

        assert manager.orchestration_enabled is True
        assert manager.orchestration_mode == "acb"
        assert manager._enable_caching is True
        assert manager._cache_backend == "memory"
        assert manager._orchestrator is None  # Lazy init

    @pytest.mark.asyncio
    async def test_orchestrator_lazy_initialization(self, console: Console, pkg_path: Path):
        """Test that orchestrator is initialized on first use."""
        manager = HookManagerImpl(
            console=console, pkg_path=pkg_path, enable_orchestration=True
        )

        assert manager._orchestrator is None

        # Initialize orchestrator
        await manager._init_orchestrator()

        assert manager._orchestrator is not None
        assert manager._orchestrator._initialized

    @pytest.mark.asyncio
    async def test_orchestrator_init_idempotent(self, console: Console, pkg_path: Path):
        """Test that calling _init_orchestrator multiple times is safe."""
        manager = HookManagerImpl(
            console=console, pkg_path=pkg_path, enable_orchestration=True
        )

        await manager._init_orchestrator()
        orchestrator1 = manager._orchestrator

        await manager._init_orchestrator()
        orchestrator2 = manager._orchestrator

        # Should be the same instance
        assert orchestrator1 is orchestrator2

    def test_execution_info_without_orchestration(self, console: Console, pkg_path: Path):
        """Test execution info when orchestration is disabled."""
        manager = HookManagerImpl(console=console, pkg_path=pkg_path)

        info = manager.get_execution_info()

        assert info["orchestration_enabled"] is False
        assert info["orchestration_mode"] is None
        assert info["caching_enabled"] is False
        assert info["cache_backend"] is None

    def test_execution_info_with_orchestration(self, console: Console, pkg_path: Path):
        """Test execution info when orchestration is enabled."""
        manager = HookManagerImpl(
            console=console,
            pkg_path=pkg_path,
            enable_orchestration=True,
            orchestration_mode="acb",
            enable_caching=True,
            cache_backend="memory",
        )

        info = manager.get_execution_info()

        assert info["orchestration_enabled"] is True
        assert info["orchestration_mode"] == "acb"
        assert info["caching_enabled"] is True
        assert info["cache_backend"] == "memory"

    @pytest.mark.asyncio
    async def test_get_orchestration_stats_disabled(self, console: Console, pkg_path: Path):
        """Test that orchestration stats return None when disabled."""
        manager = HookManagerImpl(console=console, pkg_path=pkg_path)

        stats = await manager.get_orchestration_stats()

        assert stats is None

    @pytest.mark.asyncio
    async def test_get_orchestration_stats_enabled(self, console: Console, pkg_path: Path):
        """Test orchestration stats when enabled and initialized."""
        manager = HookManagerImpl(
            console=console, pkg_path=pkg_path, enable_orchestration=True
        )

        # Initialize orchestrator
        await manager._init_orchestrator()

        stats = await manager.get_orchestration_stats()

        assert stats is not None
        assert "caching_enabled" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "total_requests" in stats


class TestHookManagerDualExecutionPaths:
    """Test that both legacy and orchestrated execution paths work."""

    def test_run_fast_hooks_legacy_path(self, console: Console, pkg_path: Path):
        """Test fast hooks execution using legacy executor."""
        manager = HookManagerImpl(
            console=console, pkg_path=pkg_path, enable_orchestration=False
        )

        # Mock executor to avoid actual hook execution
        mock_result = MagicMock()
        mock_result.results = [
            HookResult(id="ruff-format", name="ruff-format", status="passed", duration=1.0)
        ]
        manager.executor.execute_strategy = MagicMock(return_value=mock_result)

        results = manager.run_fast_hooks()

        # Verify legacy path was used
        assert len(results) == 1
        assert results[0].name == "ruff-format"
        manager.executor.execute_strategy.assert_called_once()

    def test_run_comprehensive_hooks_legacy_path(self, console: Console, pkg_path: Path):
        """Test comprehensive hooks execution using legacy executor."""
        manager = HookManagerImpl(
            console=console, pkg_path=pkg_path, enable_orchestration=False
        )

        # Mock executor to avoid actual hook execution
        mock_result = MagicMock()
        mock_result.results = [
            HookResult(id="bandit", name="bandit", status="passed", duration=2.0)
        ]
        manager.executor.execute_strategy = MagicMock(return_value=mock_result)

        results = manager.run_comprehensive_hooks()

        # Verify legacy path was used
        assert len(results) == 1
        assert results[0].name == "bandit"
        manager.executor.execute_strategy.assert_called_once()

    def test_run_hooks_legacy_path(self, console: Console, pkg_path: Path):
        """Test combined hooks execution using legacy executor."""
        manager = HookManagerImpl(
            console=console, pkg_path=pkg_path, enable_orchestration=False
        )

        # Mock executor to avoid actual hook execution
        mock_result = MagicMock()
        mock_result.results = [
            HookResult(id="test-hook", name="test-hook", status="passed", duration=1.0)
        ]
        manager.executor.execute_strategy = MagicMock(return_value=mock_result)

        results = manager.run_hooks()

        # Should have called executor twice (fast + comprehensive)
        assert manager.executor.execute_strategy.call_count == 2
        assert len(results) == 2  # Both fast and comprehensive results


class TestBackwardCompatibility:
    """Test that existing workflows continue working unchanged."""

    def test_default_initialization_unchanged(self, console: Console, pkg_path: Path):
        """Test that default initialization doesn't enable orchestration."""
        manager = HookManagerImpl(console=console, pkg_path=pkg_path)

        # Orchestration should be disabled by default
        assert manager.orchestration_enabled is False

        # Legacy features should still work
        assert manager.lsp_optimization_enabled is False
        assert manager.tool_proxy_enabled is True
        assert manager.executor is not None

    def test_existing_configuration_methods_work(self, console: Console, pkg_path: Path):
        """Test that existing configuration methods still work."""
        manager = HookManagerImpl(console=console, pkg_path=pkg_path)

        # Test LSP optimization toggle
        manager.configure_lsp_optimization(enable=True)
        assert manager.lsp_optimization_enabled is True

        manager.configure_lsp_optimization(enable=False)
        assert manager.lsp_optimization_enabled is False

        # Test tool proxy toggle
        manager.configure_tool_proxy(enable=False)
        assert manager.tool_proxy_enabled is False

        manager.configure_tool_proxy(enable=True)
        assert manager.tool_proxy_enabled is True

    def test_existing_utility_methods_work(self, console: Console, pkg_path: Path):
        """Test that existing utility methods still work."""
        manager = HookManagerImpl(console=console, pkg_path=pkg_path)

        # Test config path setting
        config_path = Path("/tmp/test-config.yaml")
        manager.set_config_path(config_path)
        assert manager._config_path == config_path

        # Test hook summary
        results = [
            HookResult(id="hook1", name="hook1", status="passed", duration=1.0),
            HookResult(id="hook2", name="hook2", status="failed", duration=2.0),
        ]

        summary = manager.get_hook_summary(results)
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
