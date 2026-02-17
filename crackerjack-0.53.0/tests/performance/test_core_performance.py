"""Performance benchmarks for core components."""

import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.timeout_manager import AsyncTimeoutManager, TimeoutConfig


class TestCorePerformanceBenchmarks:
    """Performance benchmarks for core components."""

    def test_session_coordinator_creation_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark SessionCoordinator creation performance."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")

        def create_session_coordinator():
            return SessionCoordinator(console=console, pkg_path=pkg_path)

        coordinator = benchmark(create_session_coordinator)
        assert coordinator is not None

    def test_phase_coordinator_creation_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark PhaseCoordinator creation performance."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")

        def create_phase_coordinator():
            return PhaseCoordinator(console=console, pkg_path=pkg_path)

        coordinator = benchmark(create_phase_coordinator)
        assert coordinator is not None

    def test_timeout_manager_get_timeout_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark AsyncTimeoutManager get_timeout performance."""
        config = TimeoutConfig()
        manager = AsyncTimeoutManager(config)

        def get_timeout():
            return manager.get_timeout("fast_hooks")

        timeout = benchmark(get_timeout)
        assert isinstance(timeout, float)

    def test_timeout_manager_multiple_get_timeout_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark multiple AsyncTimeoutManager get_timeout calls performance."""
        config = TimeoutConfig()
        manager = AsyncTimeoutManager(config)

        def get_multiple_timeouts():
            for _ in range(100):
                manager.get_timeout("fast_hooks")
                manager.get_timeout("comprehensive_hooks")
                manager.get_timeout("test_execution")

        benchmark(get_multiple_timeouts)

    def test_session_tracking_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark session tracking performance."""
        coordinator = SessionCoordinator()

        def track_multiple_tasks():
            for i in range(100):
                task_id = f"task_{i}"
                coordinator.track_task(task_id, f"Task {i}", f"Details for task {i}")
                coordinator.update_task(task_id, "in_progress", details=f"Progress on task {i}")
                coordinator.complete_task(task_id, f"Completed task {i}", [f"file_{i}.py"])

        benchmark(track_multiple_tasks)

    @pytest.mark.asyncio
    async def test_async_timeout_context_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark async timeout context performance."""
        manager = AsyncTimeoutManager()

        async def run_with_timeout_context():
            for _ in range(10):
                async with manager.timeout_context("test_op", timeout=1.0):
                    await asyncio.sleep(0.01)

        await benchmark(run_with_timeout_context)

    def test_timeout_manager_with_timeout_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark AsyncTimeoutManager with_timeout performance."""
        manager = AsyncTimeoutManager()

        async def async_operation():
            await asyncio.sleep(0.01)
            return "result"

        def run_with_timeout():
            # Using asyncio.run for each call to simulate real usage
            return asyncio.run(
                manager.with_timeout("test_op", async_operation(), timeout=1.0)
            )

        result = benchmark(run_with_timeout)
        assert result == "result"

    @pytest.mark.benchmark(group="timeout-strategies")
    def test_timeout_manager_fail_fast_strategy_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark timeout manager with fail-fast strategy."""
        from crackerjack.core.timeout_manager import TimeoutStrategy

        manager = AsyncTimeoutManager()

        async def async_operation():
            await asyncio.sleep(0.01)
            return "result"

        def run_with_strategy():
            return asyncio.run(
                manager.with_timeout(
                    "test_op",
                    async_operation(),
                    timeout=1.0,
                    strategy=TimeoutStrategy.FAIL_FAST,
                )
            )

        result = benchmark(run_with_strategy)
        assert result == "result"

    @pytest.mark.benchmark(group="timeout-strategies")
    def test_timeout_manager_circuit_breaker_strategy_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark timeout manager with circuit breaker strategy."""
        from crackerjack.core.timeout_manager import TimeoutStrategy

        manager = AsyncTimeoutManager()

        async def async_operation():
            await asyncio.sleep(0.01)
            return "result"

        def run_with_strategy():
            return asyncio.run(
                manager.with_timeout(
                    "test_op",
                    async_operation(),
                    timeout=1.0,
                    strategy=TimeoutStrategy.CIRCUIT_BREAKER,
                )
            )

        result = benchmark(run_with_strategy)
        assert result == "result"

    def test_phase_coordinator_task_operations_performance(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark phase coordinator task operations performance."""
        coordinator = PhaseCoordinator()

        options = MagicMock()
        options.skip_hooks = True  # Skip actual hook execution

        def run_multiple_phase_operations():
            for i in range(10):
                coordinator.run_config_cleanup_phase(options)
                coordinator.run_cleaning_phase(options)
                coordinator.run_configuration_phase(options)

        benchmark(run_multiple_phase_operations)


def test_performance_thresholds() -> None:
    """Test that core operations meet performance thresholds."""
    # Test SessionCoordinator creation time
    start = time.time()
    coordinator = SessionCoordinator()
    creation_time = time.time() - start

    # Creation should be fast (< 100ms)
    assert creation_time < 0.1, f"SessionCoordinator creation took {creation_time:.3f}s, expected < 0.1s"

    # Test PhaseCoordinator creation time
    start = time.time()
    phase_coordinator = PhaseCoordinator()
    creation_time = time.time() - start

    # Creation should be reasonably fast (< 500ms, as it has more dependencies)
    assert creation_time < 0.5, f"PhaseCoordinator creation took {creation_time:.3f}s, expected < 0.5s"

    # Test multiple session tracking operations
    start = time.time()
    for i in range(50):
        task_id = f"perf_task_{i}"
        coordinator.track_task(task_id, f"Perf Task {i}", f"Details {i}")
        coordinator.update_task(task_id, "in_progress")
        coordinator.complete_task(task_id, f"Completed {i}", [f"file_{i}.py"])
    tracking_time = time.time() - start

    # Should handle 50 operations quickly (< 100ms)
    assert tracking_time < 0.1, f"50 session operations took {tracking_time:.3f}s, expected < 0.1s"
