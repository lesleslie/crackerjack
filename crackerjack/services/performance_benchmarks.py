"""Performance benchmarking service to measure Phase 3 optimization improvements.

This module provides comprehensive benchmarking capabilities to measure the performance
gains from async workflows, caching, memory optimization, and parallel execution.
"""

import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from crackerjack.services.logging import get_logger
from crackerjack.services.memory_optimizer import get_memory_optimizer
from crackerjack.services.performance_cache import get_performance_cache
from crackerjack.services.performance_monitor import get_performance_monitor


@dataclass
class BenchmarkResult:
    """Individual benchmark test result."""

    test_name: str
    baseline_time_seconds: float
    optimized_time_seconds: float
    memory_baseline_mb: float
    memory_optimized_mb: float
    cache_hits: int = 0
    cache_misses: int = 0
    parallel_operations: int = 0
    sequential_operations: int = 0

    @property
    def time_improvement_percentage(self) -> float:
        """Calculate time improvement percentage."""
        if self.baseline_time_seconds == 0:
            return 0.0
        return (
            (self.baseline_time_seconds - self.optimized_time_seconds)
            / self.baseline_time_seconds
            * 100
        )

    @property
    def memory_improvement_percentage(self) -> float:
        """Calculate memory improvement percentage."""
        if self.memory_baseline_mb == 0:
            return 0.0
        return (
            (self.memory_baseline_mb - self.memory_optimized_mb)
            / self.memory_baseline_mb
            * 100
        )

    @property
    def cache_hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def parallelization_ratio(self) -> float:
        """Calculate parallelization ratio."""
        total = self.parallel_operations + self.sequential_operations
        return self.parallel_operations / total if total > 0 else 0.0


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""

    suite_name: str
    results: list[BenchmarkResult] = field(default_factory=list)
    run_timestamp: datetime = field(default_factory=datetime.now)

    @property
    def average_time_improvement(self) -> float:
        """Calculate average time improvement across all tests."""
        if not self.results:
            return 0.0
        improvements = [r.time_improvement_percentage for r in self.results]
        return statistics.mean(improvements)

    @property
    def average_memory_improvement(self) -> float:
        """Calculate average memory improvement across all tests."""
        if not self.results:
            return 0.0
        improvements = [r.memory_improvement_percentage for r in self.results]
        return statistics.mean(improvements)

    @property
    def overall_cache_hit_ratio(self) -> float:
        """Calculate overall cache hit ratio."""
        total_hits = sum(r.cache_hits for r in self.results)
        total_misses = sum(r.cache_misses for r in self.results)
        total = total_hits + total_misses
        return total_hits / total if total > 0 else 0.0

    def add_result(self, result: BenchmarkResult) -> None:
        """Add a benchmark result to the suite."""
        self.results.append(result)


class PerformanceBenchmarker:
    """Service for benchmarking Phase 3 performance optimizations."""

    def __init__(self):
        self._logger = get_logger("crackerjack.benchmarker")
        self._monitor = get_performance_monitor()
        self._memory_optimizer = get_memory_optimizer()
        self._cache = get_performance_cache()

        # Benchmark configurations
        self._test_iterations = 3
        self._warmup_iterations = 1

    async def run_comprehensive_benchmark(self) -> BenchmarkSuite:
        """Run comprehensive benchmark suite comparing baseline vs optimized performance."""
        self._logger.info("Starting comprehensive performance benchmark")

        suite = BenchmarkSuite("Phase 3 Optimization Benchmark")

        # Memory optimization benchmark
        suite.add_result(await self._benchmark_memory_optimization())

        # Caching benchmark
        suite.add_result(await self._benchmark_caching_performance())

        # Async workflow benchmark
        suite.add_result(await self._benchmark_async_workflows())

        self._logger.info(
            f"Benchmark complete. Average improvements: "
            f"Time: {suite.average_time_improvement:.1f}%, "
            f"Memory: {suite.average_memory_improvement:.1f}%, "
            f"Cache ratio: {suite.overall_cache_hit_ratio:.2f}"
        )

        return suite

    async def _benchmark_memory_optimization(self) -> BenchmarkResult:
        """Benchmark memory optimization improvements."""
        self._logger.debug("Benchmarking memory optimization")

        # Baseline: Create objects without optimization
        baseline_start = time.time()
        baseline_memory_start = self._memory_optimizer.record_checkpoint(
            "baseline_start"
        )

        # Simulate heavy object creation (baseline)
        heavy_objects = []
        for i in range(50):  # Reduced for faster testing
            obj = {
                "data": f"heavy_data_{i}" * 100,  # Smaller for testing
                "metadata": {"created": time.time(), "index": i},
                "payload": list(range(100)),
            }
            heavy_objects.append(obj)

        baseline_time = time.time() - baseline_start
        baseline_memory_peak = self._memory_optimizer.record_checkpoint("baseline_peak")

        # Clean up baseline objects
        del heavy_objects

        # Optimized: Use lazy loading
        optimized_start = time.time()
        optimized_memory_start = self._memory_optimizer.record_checkpoint(
            "optimized_start"
        )

        from crackerjack.services.memory_optimizer import LazyLoader

        lazy_objects = []
        for i in range(50):

            def create_heavy_object(index: int = i):
                return {
                    "data": f"heavy_data_{index}" * 100,
                    "metadata": {"created": time.time(), "index": index},
                    "payload": list(range(100)),
                }

            lazy_obj = LazyLoader(create_heavy_object, f"heavy_object_{i}")
            lazy_objects.append(lazy_obj)

        optimized_time = time.time() - optimized_start
        optimized_memory_peak = self._memory_optimizer.record_checkpoint(
            "optimized_peak"
        )

        del lazy_objects

        return BenchmarkResult(
            test_name="memory_optimization",
            baseline_time_seconds=baseline_time,
            optimized_time_seconds=optimized_time,
            memory_baseline_mb=max(0, baseline_memory_peak - baseline_memory_start),
            memory_optimized_mb=max(0, optimized_memory_peak - optimized_memory_start),
        )

    async def _benchmark_caching_performance(self) -> BenchmarkResult:
        """Benchmark caching performance improvements."""
        self._logger.debug("Benchmarking caching performance")

        self._cache.clear()

        # Baseline: No caching
        baseline_start = time.time()

        for i in range(10):  # Reduced for testing
            await self._simulate_expensive_operation(f"operation_{i % 3}")

        baseline_time = time.time() - baseline_start

        # Optimized: With caching
        optimized_start = time.time()
        cache_stats_start = self._cache.get_stats()

        for i in range(10):
            await self._simulate_cached_operation(f"operation_{i % 3}")

        optimized_time = time.time() - optimized_start
        cache_stats_end = self._cache.get_stats()

        cache_hits = cache_stats_end.hits - cache_stats_start.hits
        cache_misses = cache_stats_end.misses - cache_stats_start.misses

        return BenchmarkResult(
            test_name="caching_performance",
            baseline_time_seconds=baseline_time,
            optimized_time_seconds=optimized_time,
            memory_baseline_mb=0.0,
            memory_optimized_mb=0.0,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        )

    async def _benchmark_async_workflows(self) -> BenchmarkResult:
        """Benchmark async workflow improvements."""
        self._logger.debug("Benchmarking async workflows")

        # Baseline: Sequential operations
        baseline_start = time.time()

        for i in range(5):  # Reduced for testing
            await self._simulate_io_operation(f"seq_{i}", 0.01)  # Reduced delay

        baseline_time = time.time() - baseline_start

        # Optimized: Parallel operations
        optimized_start = time.time()

        tasks = [self._simulate_io_operation(f"par_{i}", 0.01) for i in range(5)]
        await asyncio.gather(*tasks)

        optimized_time = time.time() - optimized_start

        return BenchmarkResult(
            test_name="async_workflows",
            baseline_time_seconds=baseline_time,
            optimized_time_seconds=optimized_time,
            memory_baseline_mb=0.0,
            memory_optimized_mb=0.0,
            parallel_operations=5,
            sequential_operations=5,
        )

    async def _simulate_expensive_operation(self, operation_id: str) -> str:
        """Simulate an expensive operation without caching."""
        await asyncio.sleep(0.002)  # 2ms delay for testing

        result = ""
        for i in range(100):  # Reduced computation
            result += f"{operation_id}_{i}"

        return result[:50]

    async def _simulate_cached_operation(self, operation_id: str) -> str:
        """Simulate an expensive operation with caching."""
        cached_result = await self._cache.get_async(f"expensive_op:{operation_id}")
        if cached_result is not None:
            return cached_result

        result = await self._simulate_expensive_operation(operation_id)
        await self._cache.set_async(
            f"expensive_op:{operation_id}", result, ttl_seconds=60
        )

        return result

    async def _simulate_io_operation(self, operation_id: str, duration: float) -> str:
        """Simulate I/O bound operation."""
        await asyncio.sleep(duration)
        return f"result_{operation_id}"

    def export_benchmark_results(
        self, suite: BenchmarkSuite, output_path: Path
    ) -> None:
        """Export benchmark results to JSON file."""
        data = {
            "suite_name": suite.suite_name,
            "run_timestamp": suite.run_timestamp.isoformat(),
            "summary": {
                "average_time_improvement_percentage": suite.average_time_improvement,
                "average_memory_improvement_percentage": suite.average_memory_improvement,
                "overall_cache_hit_ratio": suite.overall_cache_hit_ratio,
                "total_tests": len(suite.results),
            },
            "results": [
                {
                    "test_name": r.test_name,
                    "baseline_time_seconds": r.baseline_time_seconds,
                    "optimized_time_seconds": r.optimized_time_seconds,
                    "time_improvement_percentage": r.time_improvement_percentage,
                    "memory_baseline_mb": r.memory_baseline_mb,
                    "memory_optimized_mb": r.memory_optimized_mb,
                    "memory_improvement_percentage": r.memory_improvement_percentage,
                    "cache_hits": r.cache_hits,
                    "cache_misses": r.cache_misses,
                    "cache_hit_ratio": r.cache_hit_ratio,
                    "parallel_operations": r.parallel_operations,
                    "sequential_operations": r.sequential_operations,
                    "parallelization_ratio": r.parallelization_ratio,
                }
                for r in suite.results
            ],
        }

        with output_path.open("w") as f:
            json.dump(data, f, indent=2)

        self._logger.info(f"Exported benchmark results to {output_path}")


# Global benchmarker instance
def get_benchmarker() -> PerformanceBenchmarker:
    """Get performance benchmarker instance."""
    return PerformanceBenchmarker()
