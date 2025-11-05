"""Integration tests for HookManager with triple parallelism (Phase 5-7).

Tests the complete triple parallelism implementation:
- Tier 1: Strategy-level parallelism (fast + comprehensive concurrent)
- Tier 2: Hook-level parallelism (adaptive execution with dependency-aware waves)
- Configuration options for enabling/disabling parallelism features
- Performance improvements from concurrent execution

These tests verify that the Phase 5-7 implementation delivers the expected
performance improvements while maintaining correctness and reliability.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.models.task import HookResult
from crackerjack.orchestration.config import OrchestrationConfig


@pytest.fixture
def console() -> Console:
    """Create Rich console for testing."""
    return Console()


@pytest.fixture
def pkg_path(tmp_path: Path) -> Path:
    """Create temporary package path."""
    return tmp_path


class TestStrategyLevelParallelism:
    """Test Tier 1 parallelism: concurrent execution of fast + comprehensive strategies."""

    @pytest.mark.asyncio
    async def test_concurrent_strategy_execution(self, console: Console, pkg_path: Path):
        """Test that fast and comprehensive strategies execute concurrently when enabled."""
        config = OrchestrationConfig(
            enable_orchestration=True,
            orchestration_mode="acb",
            enable_strategy_parallelism=True,
            enable_adaptive_execution=True,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        # Mock the orchestrated execution methods to track timing
        fast_start_time = None
        fast_end_time = None
        comp_start_time = None
        comp_end_time = None

        async def mock_fast_hooks():
            nonlocal fast_start_time, fast_end_time
            fast_start_time = time.time()
            await asyncio.sleep(0.1)  # Simulate 100ms execution
            fast_end_time = time.time()
            return [
                HookResult(id="fast-1", name="fast-1", status="passed", duration=0.1)
            ]

        async def mock_comp_hooks():
            nonlocal comp_start_time, comp_end_time
            comp_start_time = time.time()
            await asyncio.sleep(0.2)  # Simulate 200ms execution
            comp_end_time = time.time()
            return [
                HookResult(id="comp-1", name="comp-1", status="passed", duration=0.2)
            ]

        manager._run_fast_hooks_orchestrated = mock_fast_hooks
        manager._run_comprehensive_hooks_orchestrated = mock_comp_hooks

        # Execute both strategies
        start_time = time.time()
        results = manager.run_hooks()
        total_time = time.time() - start_time

        # Verify results
        assert len(results) == 2
        assert results[0].name == "fast-1"
        assert results[1].name == "comp-1"

        # Verify concurrent execution (strategies started roughly at the same time)
        assert fast_start_time is not None
        assert comp_start_time is not None
        time_diff = abs(fast_start_time - comp_start_time)
        assert time_diff < 0.05, f"Strategies should start concurrently, but started {time_diff}s apart"

        # Verify total time is approximately max(fast, comp) not sum
        # Should be ~0.2s (max) not ~0.3s (sum)
        assert total_time < 0.25, f"Total time {total_time}s should be ~max(0.1, 0.2) not sum(0.3)"

    @pytest.mark.asyncio
    async def test_sequential_when_parallelism_disabled(self, console: Console, pkg_path: Path):
        """Test that strategies execute sequentially when strategy parallelism is disabled."""
        config = OrchestrationConfig(
            enable_orchestration=True,
            orchestration_mode="acb",
            enable_strategy_parallelism=False,  # Disable parallelism
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        # Mock the orchestrated execution methods
        execution_order = []

        async def mock_fast_hooks():
            execution_order.append("fast_start")
            await asyncio.sleep(0.05)
            execution_order.append("fast_end")
            return [
                HookResult(id="fast-1", name="fast-1", status="passed", duration=0.05)
            ]

        async def mock_comp_hooks():
            execution_order.append("comp_start")
            await asyncio.sleep(0.05)
            execution_order.append("comp_end")
            return [
                HookResult(id="comp-1", name="comp-1", status="passed", duration=0.05)
            ]

        manager._run_fast_hooks_orchestrated = mock_fast_hooks
        manager._run_comprehensive_hooks_orchestrated = mock_comp_hooks

        # Execute both strategies
        results = manager.run_hooks()

        # Verify results
        assert len(results) == 2

        # Verify sequential execution order
        assert execution_order == [
            "fast_start",
            "fast_end",
            "comp_start",
            "comp_end",
        ], "Strategies should execute sequentially when parallelism is disabled"

    @pytest.mark.asyncio
    async def test_result_combining(self, console: Console, pkg_path: Path):
        """Test that results from both strategies are correctly combined."""
        config = OrchestrationConfig(
            enable_orchestration=True,
            orchestration_mode="acb",
            enable_strategy_parallelism=True,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        # Mock strategies with multiple results each
        async def mock_fast_hooks():
            return [
                HookResult(id="fast-1", name="fast-1", status="passed", duration=0.1),
                HookResult(id="fast-2", name="fast-2", status="passed", duration=0.1),
            ]

        async def mock_comp_hooks():
            return [
                HookResult(id="comp-1", name="comp-1", status="passed", duration=0.2),
                HookResult(id="comp-2", name="comp-2", status="failed", duration=0.2),
                HookResult(id="comp-3", name="comp-3", status="passed", duration=0.2),
            ]

        manager._run_fast_hooks_orchestrated = mock_fast_hooks
        manager._run_comprehensive_hooks_orchestrated = mock_comp_hooks

        # Execute
        results = manager.run_hooks()

        # Verify all results are present
        assert len(results) == 5

        # Verify fast results come first
        assert results[0].name == "fast-1"
        assert results[1].name == "fast-2"

        # Verify comprehensive results follow
        assert results[2].name == "comp-1"
        assert results[3].name == "comp-2"
        assert results[4].name == "comp-3"

        # Verify statuses are preserved
        assert results[3].status == "failed"

    def test_error_handling_one_strategy_fails(self, console: Console, pkg_path: Path):
        """Test that if one strategy fails, the exception is propagated."""
        config = OrchestrationConfig(
            enable_orchestration=True,
            orchestration_mode="acb",
            enable_strategy_parallelism=True,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        # Mock fast hooks to succeed
        async def mock_fast_hooks():
            return [
                HookResult(id="fast-1", name="fast-1", status="passed", duration=0.1)
            ]

        # Mock comprehensive hooks to raise an exception
        async def mock_comp_hooks():
            raise RuntimeError("Comprehensive strategy failed")

        manager._run_fast_hooks_orchestrated = mock_fast_hooks
        manager._run_comprehensive_hooks_orchestrated = mock_comp_hooks

        # Execute should raise the exception (asyncio.gather propagates exceptions)
        with pytest.raises(RuntimeError, match="Comprehensive strategy failed"):
            manager.run_hooks()


class TestConfigurationOptions:
    """Test configuration options for triple parallelism."""

    def test_enable_strategy_parallelism_flag(self, console: Console, pkg_path: Path):
        """Test that enable_strategy_parallelism flag controls Tier 1 parallelism."""
        # Test with parallelism enabled
        config_enabled = OrchestrationConfig(
            enable_orchestration=True,
            enable_strategy_parallelism=True,
        )

        manager_enabled = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config_enabled,
        )

        assert manager_enabled._orchestration_config.enable_strategy_parallelism is True

        # Test with parallelism disabled
        config_disabled = OrchestrationConfig(
            enable_orchestration=True,
            enable_strategy_parallelism=False,
        )

        manager_disabled = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config_disabled,
        )

        assert manager_disabled._orchestration_config.enable_strategy_parallelism is False

    def test_enable_adaptive_execution_flag(self, console: Console, pkg_path: Path):
        """Test that enable_adaptive_execution flag is properly propagated."""
        config = OrchestrationConfig(
            enable_orchestration=True,
            enable_adaptive_execution=True,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        assert manager._orchestration_config.enable_adaptive_execution is True

        # Verify it's passed to orchestrator settings
        settings = config.to_orchestrator_settings()
        assert settings.enable_adaptive_execution is True

    def test_max_concurrent_strategies_limit(self, console: Console, pkg_path: Path):
        """Test that max_concurrent_strategies setting is configurable."""
        config = OrchestrationConfig(
            enable_orchestration=True,
            max_concurrent_strategies=4,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        assert manager._orchestration_config.max_concurrent_strategies == 4

    def test_configuration_from_yaml(self, console: Console, tmp_path: Path):
        """Test loading triple parallelism configuration from YAML file."""
        config_path = tmp_path / ".crackerjack.yaml"
        config_content = """
orchestration:
  enable: true
  mode: acb
  enable_strategy_parallelism: true
  enable_adaptive_execution: true
  max_concurrent_strategies: 3
"""
        config_path.write_text(config_content)

        manager = HookManagerImpl(pkg_path=tmp_path)

        assert manager.orchestration_enabled is True
        assert manager._orchestration_config.enable_strategy_parallelism is True
        assert manager._orchestration_config.enable_adaptive_execution is True
        assert manager._orchestration_config.max_concurrent_strategies == 3

    def test_configuration_defaults(self, console: Console, pkg_path: Path):
        """Test that triple parallelism features are enabled by default."""
        config = OrchestrationConfig(enable_orchestration=True)

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        # Verify defaults
        assert manager._orchestration_config.enable_strategy_parallelism is True
        assert manager._orchestration_config.enable_adaptive_execution is True
        assert manager._orchestration_config.max_concurrent_strategies == 2


class TestIntegrationScenarios:
    """Test complete integration scenarios with triple parallelism."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_triple_parallelism(self, console: Console, pkg_path: Path):
        """Test complete workflow with both Tier 1 and Tier 2 parallelism enabled."""
        config = OrchestrationConfig(
            enable_orchestration=True,
            orchestration_mode="acb",
            enable_strategy_parallelism=True,
            enable_adaptive_execution=True,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        # Initialize orchestrator
        await manager._init_orchestrator()

        # Verify orchestrator settings
        assert manager._orchestrator is not None
        assert manager._orchestrator.settings.enable_adaptive_execution is True

        # Verify execution info reflects triple parallelism
        info = manager.get_execution_info()
        assert info["orchestration_enabled"] is True
        assert info["orchestration_mode"] == "acb"

    def test_backward_compatibility_legacy_mode(self, console: Console, pkg_path: Path):
        """Test that legacy mode (orchestration disabled) still works."""
        manager = HookManagerImpl(
            pkg_path=pkg_path,
            enable_orchestration=False,
        )

        # Mock executor
        mock_result = MagicMock()
        mock_result.results = [
            HookResult(id="test", name="test", status="passed", duration=1.0)
        ]
        manager.executor.execute_strategy = MagicMock(return_value=mock_result)

        # Execute should use legacy path
        results = manager.run_hooks()

        # Verify legacy execution
        assert len(results) == 2  # Both fast and comprehensive called
        assert manager.executor.execute_strategy.call_count == 2

    @pytest.mark.asyncio
    async def test_performance_comparison(self, console: Console, pkg_path: Path):
        """Compare performance with and without strategy-level parallelism."""
        # Test with parallelism enabled
        config_parallel = OrchestrationConfig(
            enable_orchestration=True,
            enable_strategy_parallelism=True,
        )

        manager_parallel = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config_parallel,
        )

        # Mock strategies with simulated delays
        async def mock_fast_parallel():
            await asyncio.sleep(0.1)
            return [HookResult(id="fast", name="fast", status="passed", duration=0.1)]

        async def mock_comp_parallel():
            await asyncio.sleep(0.2)
            return [HookResult(id="comp", name="comp", status="passed", duration=0.2)]

        manager_parallel._run_fast_hooks_orchestrated = mock_fast_parallel
        manager_parallel._run_comprehensive_hooks_orchestrated = mock_comp_parallel

        # Measure parallel execution time
        start = time.time()
        results_parallel = manager_parallel.run_hooks()
        parallel_time = time.time() - start

        # Test with parallelism disabled
        config_sequential = OrchestrationConfig(
            enable_orchestration=True,
            enable_strategy_parallelism=False,
        )

        manager_sequential = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config_sequential,
        )

        async def mock_fast_sequential():
            await asyncio.sleep(0.1)
            return [HookResult(id="fast", name="fast", status="passed", duration=0.1)]

        async def mock_comp_sequential():
            await asyncio.sleep(0.2)
            return [HookResult(id="comp", name="comp", status="passed", duration=0.2)]

        manager_sequential._run_fast_hooks_orchestrated = mock_fast_sequential
        manager_sequential._run_comprehensive_hooks_orchestrated = mock_comp_sequential

        # Measure sequential execution time
        start = time.time()
        results_sequential = manager_sequential.run_hooks()
        sequential_time = time.time() - start

        # Verify results are the same
        assert len(results_parallel) == len(results_sequential) == 2

        # Verify parallel is faster
        # Parallel should be ~0.2s (max), sequential should be ~0.3s (sum)
        assert parallel_time < 0.25, f"Parallel execution took {parallel_time}s, expected ~0.2s"
        assert sequential_time > 0.28, f"Sequential execution took {sequential_time}s, expected ~0.3s"

        # Verify speedup
        speedup = sequential_time / parallel_time
        assert speedup > 1.2, f"Parallel execution should be at least 20% faster, got {speedup:.2f}x"

    def test_get_execution_info_with_parallelism(self, console: Console, pkg_path: Path):
        """Test that get_execution_info() shows triple parallelism status."""
        config = OrchestrationConfig(
            enable_orchestration=True,
            enable_strategy_parallelism=True,
            enable_adaptive_execution=True,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        info = manager.get_execution_info()

        # Verify orchestration info
        assert info["orchestration_enabled"] is True
        assert info["orchestration_mode"] == "acb"
        assert info["caching_enabled"] is True
