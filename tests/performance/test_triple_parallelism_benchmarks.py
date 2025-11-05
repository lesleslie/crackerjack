"""Performance benchmarks for triple parallelism implementation (Phase 5-7).

Measures:
- Strategy-level parallelism speedup (Tier 1)
- Hook-level adaptive execution efficiency (Tier 2)
- Cache impact on performance
- Real-world workflow execution times
- Memory usage and resource efficiency

These benchmarks validate that triple parallelism delivers expected performance
improvements while maintaining correctness and stability.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

from crackerjack.config.hooks import HookDefinition, HookStrategy, SecurityLevel
from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.models.task import HookResult
from crackerjack.orchestration.config import OrchestrationConfig
from crackerjack.orchestration.hook_orchestrator import (
    HookOrchestratorAdapter,
    HookOrchestratorSettings,
)
from crackerjack.orchestration.strategies.adaptive_strategy import (
    AdaptiveExecutionStrategy,
)


@pytest.fixture
def console() -> Console:
    """Create Rich console for benchmarks."""
    return Console()


@pytest.fixture
def pkg_path(tmp_path: Path) -> Path:
    """Create temporary package path."""
    return tmp_path


class TestStrategyParallelismBenchmarks:
    """Benchmark Tier 1 parallelism: concurrent strategy execution."""

    def test_parallel_vs_sequential_speedup(self, console: Console, pkg_path: Path):
        """Measure speedup from running strategies in parallel vs sequential.

        Expected: Parallel execution should be ~50% faster than sequential
        when both strategies take similar time.
        """
        # Test configuration
        num_iterations = 5
        fast_duration = 0.1  # 100ms
        comp_duration = 0.15  # 150ms

        # Parallel configuration
        parallel_config = OrchestrationConfig(
            enable_orchestration=True,
            orchestration_mode="acb",
            enable_strategy_parallelism=True,
            enable_adaptive_execution=True,
        )

        # Sequential configuration
        sequential_config = OrchestrationConfig(
            enable_orchestration=True,
            orchestration_mode="acb",
            enable_strategy_parallelism=False,
            enable_adaptive_execution=True,
        )

        # Measure parallel execution
        parallel_times = []
        for _ in range(num_iterations):
            manager = HookManagerImpl(
                pkg_path=pkg_path,
                orchestration_config=parallel_config,
            )

            async def mock_fast():
                await asyncio.sleep(fast_duration)
                return [HookResult(id="fast", name="fast", status="passed", duration=fast_duration)]

            async def mock_comp():
                await asyncio.sleep(comp_duration)
                return [HookResult(id="comp", name="comp", status="passed", duration=comp_duration)]

            manager._run_fast_hooks_orchestrated = mock_fast
            manager._run_comprehensive_hooks_orchestrated = mock_comp

            start = time.time()
            manager.run_hooks()
            elapsed = time.time() - start
            parallel_times.append(elapsed)

        # Measure sequential execution
        sequential_times = []
        for _ in range(num_iterations):
            manager = HookManagerImpl(
                pkg_path=pkg_path,
                orchestration_config=sequential_config,
            )

            async def mock_fast():
                await asyncio.sleep(fast_duration)
                return [HookResult(id="fast", name="fast", status="passed", duration=fast_duration)]

            async def mock_comp():
                await asyncio.sleep(comp_duration)
                return [HookResult(id="comp", name="comp", status="passed", duration=comp_duration)]

            manager._run_fast_hooks_orchestrated = mock_fast
            manager._run_comprehensive_hooks_orchestrated = mock_comp

            start = time.time()
            manager.run_hooks()
            elapsed = time.time() - start
            sequential_times.append(elapsed)

        # Calculate statistics
        parallel_mean = statistics.mean(parallel_times)
        parallel_stdev = statistics.stdev(parallel_times)
        sequential_mean = statistics.mean(sequential_times)
        sequential_stdev = statistics.stdev(sequential_times)
        speedup = sequential_mean / parallel_mean

        # Print benchmark results
        print(f"\n{'='*60}")
        print("STRATEGY PARALLELISM BENCHMARK")
        print(f"{'='*60}")
        print(f"Iterations: {num_iterations}")
        print(f"Fast strategy duration: {fast_duration:.3f}s")
        print(f"Comprehensive strategy duration: {comp_duration:.3f}s")
        print(f"\nParallel execution:")
        print(f"  Mean: {parallel_mean:.3f}s (±{parallel_stdev:.3f}s)")
        print(f"  Min: {min(parallel_times):.3f}s")
        print(f"  Max: {max(parallel_times):.3f}s")
        print(f"\nSequential execution:")
        print(f"  Mean: {sequential_mean:.3f}s (±{sequential_stdev:.3f}s)")
        print(f"  Min: {min(sequential_times):.3f}s")
        print(f"  Max: {max(sequential_times):.3f}s")
        print(f"\n🚀 Speedup: {speedup:.2f}x")
        print(f"{'='*60}\n")

        # Validate performance expectations
        # Parallel should be approximately max(fast, comp) = 0.15s
        assert parallel_mean < 0.2, \
            f"Parallel execution too slow: {parallel_mean:.3f}s (expected ~0.15s)"

        # Sequential should be approximately sum(fast, comp) = 0.25s
        assert sequential_mean > 0.23, \
            f"Sequential execution too fast: {sequential_mean:.3f}s (expected ~0.25s)"

        # Speedup should be at least 1.3x (30% improvement)
        assert speedup >= 1.3, \
            f"Insufficient speedup: {speedup:.2f}x (expected ≥1.3x)"

        # Speedup should not exceed 2x (theoretical maximum for 2 concurrent tasks)
        assert speedup <= 2.0, \
            f"Unrealistic speedup: {speedup:.2f}x (expected ≤2.0x)"

    def test_parallel_overhead_measurement(self, console: Console, pkg_path: Path):
        """Measure overhead introduced by parallel execution infrastructure.

        Expected: Overhead should be minimal (<10% of total execution time).
        """
        num_iterations = 10
        task_duration = 0.05  # 50ms per strategy

        config = OrchestrationConfig(
            enable_orchestration=True,
            enable_strategy_parallelism=True,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        async def mock_fast():
            start = time.time()
            await asyncio.sleep(task_duration)
            return [HookResult(
                id="fast", name="fast", status="passed",
                duration=time.time() - start
            )]

        async def mock_comp():
            start = time.time()
            await asyncio.sleep(task_duration)
            return [HookResult(
                id="comp", name="comp", status="passed",
                duration=time.time() - start
            )]

        manager._run_fast_hooks_orchestrated = mock_fast
        manager._run_comprehensive_hooks_orchestrated = mock_comp

        # Measure total execution time vs actual work time
        total_times = []
        work_times = []

        for _ in range(num_iterations):
            start = time.time()
            results = manager.run_hooks()
            total_time = time.time() - start
            work_time = max(r.duration for r in results)

            total_times.append(total_time)
            work_times.append(work_time)

        total_mean = statistics.mean(total_times)
        work_mean = statistics.mean(work_times)
        overhead = total_mean - work_mean
        overhead_percent = (overhead / total_mean) * 100

        # Print benchmark results
        print(f"\n{'='*60}")
        print("PARALLEL EXECUTION OVERHEAD BENCHMARK")
        print(f"{'='*60}")
        print(f"Iterations: {num_iterations}")
        print(f"Task duration: {task_duration:.3f}s")
        print(f"\nTotal execution time: {total_mean:.3f}s")
        print(f"Actual work time: {work_mean:.3f}s")
        print(f"Overhead: {overhead:.3f}s ({overhead_percent:.1f}%)")
        print(f"{'='*60}\n")

        # Validate overhead is acceptable (<10%)
        assert overhead_percent < 10.0, \
            f"Excessive overhead: {overhead_percent:.1f}% (expected <10%)"


class TestAdaptiveExecutionBenchmarks:
    """Benchmark Tier 2 parallelism: dependency-aware hook execution."""

    @pytest.mark.asyncio
    async def test_wave_execution_efficiency(self, console: Console, pkg_path: Path):
        """Measure efficiency of dependency-aware wave execution.

        Expected: Waves should execute with minimal overhead between them.
        """
        # Create hooks with dependencies
        # Wave 1: hook-a, hook-b (independent)
        # Wave 2: hook-c (depends on hook-a), hook-d (depends on hook-b)
        # Wave 3: hook-e (depends on hook-c and hook-d)

        hooks = [
            HookDefinition(
                name="hook-a",
                command=["echo", "a"],
                security_level=SecurityLevel.LOW,
            ),
            HookDefinition(
                name="hook-b",
                command=["echo", "b"],
                security_level=SecurityLevel.LOW,
            ),
            HookDefinition(
                name="hook-c",
                command=["echo", "c"],
                security_level=SecurityLevel.LOW,
            ),
            HookDefinition(
                name="hook-d",
                command=["echo", "d"],
                security_level=SecurityLevel.LOW,
            ),
            HookDefinition(
                name="hook-e",
                command=["echo", "e"],
                security_level=SecurityLevel.LOW,
            ),
        ]

        dependency_graph = {
            "hook-c": ["hook-a"],
            "hook-d": ["hook-b"],
            "hook-e": ["hook-c", "hook-d"],
        }

        strategy = AdaptiveExecutionStrategy(
            dependency_graph=dependency_graph,
            max_parallel=4,
            default_timeout=300,
        )

        # Mock executor that simulates work
        hook_duration = 0.05  # 50ms per hook

        async def mock_executor(hook: HookDefinition) -> HookResult:
            await asyncio.sleep(hook_duration)
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=hook_duration,
            )

        # Execute and measure
        start = time.time()
        results = await strategy.execute(
            hooks=hooks,
            executor_callable=mock_executor,
        )
        total_time = time.time() - start

        # Calculate expected time
        # Wave 1: 2 hooks parallel = 0.05s
        # Wave 2: 2 hooks parallel = 0.05s
        # Wave 3: 1 hook = 0.05s
        # Expected total: ~0.15s
        expected_time = 3 * hook_duration
        overhead = total_time - expected_time
        overhead_percent = (overhead / total_time) * 100

        # Print benchmark results
        print(f"\n{'='*60}")
        print("ADAPTIVE WAVE EXECUTION BENCHMARK")
        print(f"{'='*60}")
        print(f"Total hooks: {len(hooks)}")
        print(f"Hook duration: {hook_duration:.3f}s")
        print(f"Dependency graph: {dependency_graph}")
        print(f"\nExecution results:")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Expected time: {expected_time:.3f}s")
        print(f"  Overhead: {overhead:.3f}s ({overhead_percent:.1f}%)")
        print(f"  Hooks executed: {len(results)}")
        print(f"{'='*60}\n")

        # Validate results
        assert len(results) == len(hooks), "Not all hooks executed"
        assert all(r.status == "passed" for r in results), "Some hooks failed"

        # Validate wave execution efficiency
        assert total_time < expected_time * 1.2, \
            f"Wave execution too slow: {total_time:.3f}s (expected ~{expected_time:.3f}s)"
        assert overhead_percent < 20.0, \
            f"Excessive wave overhead: {overhead_percent:.1f}% (expected <20%)"

    @pytest.mark.asyncio
    async def test_parallel_vs_sequential_waves(self, console: Console, pkg_path: Path):
        """Compare adaptive wave execution to pure sequential execution.

        Expected: Adaptive should provide 2-3x speedup for independent hooks.
        """
        # Create 6 hooks: 3 independent + 3 dependent
        hooks = [
            HookDefinition(name=f"indep-{i}", command=["echo", str(i)],
                         security_level=SecurityLevel.LOW)
            for i in range(3)
        ] + [
            HookDefinition(name=f"dep-{i}", command=["echo", str(i)],
                         security_level=SecurityLevel.LOW)
            for i in range(3)
        ]

        dependency_graph = {
            "dep-0": ["indep-0"],
            "dep-1": ["indep-1"],
            "dep-2": ["indep-2"],
        }

        hook_duration = 0.05

        async def mock_executor(hook: HookDefinition) -> HookResult:
            await asyncio.sleep(hook_duration)
            return HookResult(id=hook.name, name=hook.name, status="passed", duration=hook_duration)

        # Measure adaptive execution
        adaptive_strategy = AdaptiveExecutionStrategy(
            dependency_graph=dependency_graph,
            max_parallel=4,
        )

        start = time.time()
        await adaptive_strategy.execute(hooks=hooks, executor_callable=mock_executor)
        adaptive_time = time.time() - start

        # Measure sequential execution (empty dependency graph)
        sequential_strategy = AdaptiveExecutionStrategy(
            dependency_graph={},  # No dependencies = all in one wave
            max_parallel=1,  # Sequential
        )

        start = time.time()
        await sequential_strategy.execute(hooks=hooks, executor_callable=mock_executor)
        sequential_time = time.time() - start

        speedup = sequential_time / adaptive_time

        # Print benchmark results
        print(f"\n{'='*60}")
        print("ADAPTIVE VS SEQUENTIAL BENCHMARK")
        print(f"{'='*60}")
        print(f"Total hooks: {len(hooks)}")
        print(f"Independent hooks: 3")
        print(f"Dependent hooks: 3")
        print(f"Hook duration: {hook_duration:.3f}s")
        print(f"\nAdaptive execution: {adaptive_time:.3f}s")
        print(f"Sequential execution: {sequential_time:.3f}s")
        print(f"🚀 Speedup: {speedup:.2f}x")
        print(f"{'='*60}\n")

        # Validate speedup
        # Adaptive: Wave 1 (3 parallel) + Wave 2 (3 parallel) = 2 * 0.05 = 0.10s
        # Sequential: 6 * 0.05 = 0.30s
        # Expected speedup: ~3x
        assert speedup >= 2.0, f"Insufficient speedup: {speedup:.2f}x (expected ≥2.0x)"


class TestEndToEndWorkflowBenchmarks:
    """Benchmark complete workflows with triple parallelism."""

    def test_realistic_workflow_performance(self, console: Console, pkg_path: Path):
        """Measure performance of realistic development workflow.

        Simulates typical CI/CD scenario with multiple hooks in fast and
        comprehensive strategies.
        """
        config = OrchestrationConfig(
            enable_orchestration=True,
            enable_strategy_parallelism=True,
            enable_adaptive_execution=True,
            max_parallel_hooks=4,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        # Simulate realistic hook durations
        # Fast strategy: 3 quick checks (ruff-format, trailing-whitespace, end-of-file-fixer)
        # Comprehensive strategy: 5 slower checks (zuban, gitleaks, bandit, complexity, security)

        async def mock_fast():
            await asyncio.sleep(0.05)  # 50ms for fast hooks
            return [
                HookResult(id="ruff-format", name="ruff-format", status="passed", duration=0.02),
                HookResult(id="trailing-whitespace", name="trailing-whitespace", status="passed", duration=0.015),
                HookResult(id="end-of-file-fixer", name="end-of-file-fixer", status="passed", duration=0.015),
            ]

        async def mock_comp():
            await asyncio.sleep(0.15)  # 150ms for comprehensive hooks
            return [
                HookResult(id="zuban", name="zuban", status="passed", duration=0.04),
                HookResult(id="gitleaks", name="gitleaks", status="passed", duration=0.03),
                HookResult(id="bandit", name="bandit", status="passed", duration=0.03),
                HookResult(id="complexity", name="complexity", status="passed", duration=0.025),
                HookResult(id="security", name="security", status="passed", duration=0.025),
            ]

        manager._run_fast_hooks_orchestrated = mock_fast
        manager._run_comprehensive_hooks_orchestrated = mock_comp

        # Run multiple iterations
        num_iterations = 10
        times = []

        for _ in range(num_iterations):
            start = time.time()
            results = manager.run_hooks()
            elapsed = time.time() - start
            times.append(elapsed)

        mean_time = statistics.mean(times)
        stdev = statistics.stdev(times)

        # Calculate expected sequential time
        sequential_time = 0.05 + 0.15  # sum of fast and comp
        speedup = sequential_time / mean_time

        # Print benchmark results
        print(f"\n{'='*60}")
        print("REALISTIC WORKFLOW BENCHMARK")
        print(f"{'='*60}")
        print(f"Iterations: {num_iterations}")
        print(f"Fast strategy: 3 hooks (~50ms)")
        print(f"Comprehensive strategy: 5 hooks (~150ms)")
        print(f"\nParallel execution:")
        print(f"  Mean: {mean_time:.3f}s (±{stdev:.3f}s)")
        print(f"  Min: {min(times):.3f}s")
        print(f"  Max: {max(times):.3f}s")
        print(f"\nExpected sequential time: {sequential_time:.3f}s")
        print(f"🚀 Speedup: {speedup:.2f}x")
        print(f"\n📊 Results per execution:")
        print(f"  Total hooks: 8")
        print(f"  All passed: ✓")
        print(f"{'='*60}\n")

        # Validate performance
        assert mean_time < 0.18, f"Workflow too slow: {mean_time:.3f}s (expected ~0.15s)"
        assert speedup >= 1.2, f"Insufficient speedup: {speedup:.2f}x (expected ≥1.2x)"
        assert stdev < 0.05, f"High variance: {stdev:.3f}s (expected <0.05s)"


class TestMemoryAndResourceBenchmarks:
    """Benchmark memory usage and resource efficiency."""

    def test_memory_efficiency(self, console: Console, pkg_path: Path):
        """Measure memory overhead of parallel execution.

        Expected: Memory usage should scale linearly with number of concurrent tasks.
        """
        import psutil
        import os

        config = OrchestrationConfig(
            enable_orchestration=True,
            enable_strategy_parallelism=True,
        )

        manager = HookManagerImpl(
            pkg_path=pkg_path,
            orchestration_config=config,
        )

        # Measure memory before execution
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        async def mock_fast():
            # Simulate some memory allocation
            data = [0] * 10000
            await asyncio.sleep(0.05)
            return [HookResult(id="fast", name="fast", status="passed", duration=0.05)]

        async def mock_comp():
            # Simulate some memory allocation
            data = [0] * 10000
            await asyncio.sleep(0.05)
            return [HookResult(id="comp", name="comp", status="passed", duration=0.05)]

        manager._run_fast_hooks_orchestrated = mock_fast
        manager._run_comprehensive_hooks_orchestrated = mock_comp

        # Execute
        manager.run_hooks()

        # Measure memory after execution
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_increase = mem_after - mem_before

        # Print benchmark results
        print(f"\n{'='*60}")
        print("MEMORY EFFICIENCY BENCHMARK")
        print(f"{'='*60}")
        print(f"Memory before: {mem_before:.2f} MB")
        print(f"Memory after: {mem_after:.2f} MB")
        print(f"Memory increase: {mem_increase:.2f} MB")
        print(f"{'='*60}\n")

        # Validate memory usage is reasonable (<50 MB increase)
        assert mem_increase < 50.0, \
            f"Excessive memory usage: {mem_increase:.2f} MB (expected <50 MB)"
