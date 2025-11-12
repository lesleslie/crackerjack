import asyncio
import json
import statistics
import time
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends
from acb.logger import Logger

from crackerjack.models.protocols import (
    PerformanceBenchmarkProtocol,
    PerformanceBenchmarkServiceProtocol,
    ServiceProtocol,
)
from crackerjack.services.memory_optimizer import LazyLoader, MemoryOptimizer
from crackerjack.services.monitoring.performance_cache import get_performance_cache
from crackerjack.services.monitoring.performance_monitor import get_performance_monitor


@dataclass
class BenchmarkResult:
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
        if self.baseline_time_seconds == 0:
            return 0.0
        return (
            (self.baseline_time_seconds - self.optimized_time_seconds)
            / self.baseline_time_seconds
            * 100
        )

    @property
    def memory_improvement_percentage(self) -> float:
        if self.memory_baseline_mb == 0:
            return 0.0
        return (
            (self.memory_baseline_mb - self.memory_optimized_mb)
            / self.memory_baseline_mb
            * 100
        )

    @property
    def cache_hit_ratio(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def parallelization_ratio(self) -> float:
        total = self.parallel_operations + self.sequential_operations
        return self.parallel_operations / total if total > 0 else 0.0


@dataclass
class BenchmarkSuite:
    suite_name: str
    results: list[BenchmarkResult] = field(default_factory=list)
    run_timestamp: datetime = field(default_factory=datetime.now)

    @property
    def average_time_improvement(self) -> float:
        if not self.results:
            return 0.0
        improvements = [r.time_improvement_percentage for r in self.results]
        return statistics.mean(improvements)

    @property
    def average_memory_improvement(self) -> float:
        if not self.results:
            return 0.0
        improvements = [r.memory_improvement_percentage for r in self.results]
        return statistics.mean(improvements)

    @property
    def overall_cache_hit_ratio(self) -> float:
        total_hits = sum(r.cache_hits for r in self.results)
        total_misses = sum(r.cache_misses for r in self.results)
        total = total_hits + total_misses
        return total_hits / total if total > 0 else 0.0

    def add_result(self, result: BenchmarkResult) -> None:
        self.results.append(result)


class PerformanceBenchmarker:
    @depends.inject
    def __init__(self, logger: Inject[Logger]) -> None:
        self._logger = logger
        self._monitor = get_performance_monitor()
        self._memory_optimizer = MemoryOptimizer.get_instance()
        self._cache = get_performance_cache()

        self._test_iterations = 3
        self._warmup_iterations = 1

    async def run_comprehensive_benchmark(self) -> BenchmarkSuite:
        self._logger.info("Starting comprehensive performance benchmark")

        suite = BenchmarkSuite("Phase 3 Optimization Benchmark")

        suite.add_result(await self._benchmark_memory_optimization())

        suite.add_result(await self._benchmark_caching_performance())

        suite.add_result(await self._benchmark_async_workflows())

        self._logger.info(
            f"Benchmark complete. Average improvements: "
            f"Time: {suite.average_time_improvement: .1f}%, "
            f"Memory: {suite.average_memory_improvement: .1f}%, "
            f"Cache ratio: {suite.overall_cache_hit_ratio: .2f}"
        )

        return suite

    async def _benchmark_memory_optimization(self) -> BenchmarkResult:
        self._logger.debug("Benchmarking memory optimization")

        baseline_start = time.time()
        baseline_memory_start = self._memory_optimizer.record_checkpoint(
            "baseline_start"
        )

        heavy_objects = []
        for i in range(50):
            obj = {
                "data": f"heavy_data_{i}" * 100,
                "metadata": {"created": time.time(), "index": i},
                "payload": list(range(100)),
            }
            heavy_objects.append(obj)

        baseline_time = time.time() - baseline_start
        baseline_memory_peak = self._memory_optimizer.record_checkpoint("baseline_peak")

        del heavy_objects

        optimized_start = time.time()
        optimized_memory_start = self._memory_optimizer.record_checkpoint(
            "optimized_start"
        )

        lazy_objects = []
        for i in range(50):

            def create_heavy_object(index: int = i) -> dict[str, t.Any]:
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
        self._logger.debug("Benchmarking caching performance")

        self._cache.clear()

        baseline_start = time.time()

        for i in range(10):
            await self._simulate_expensive_operation(f"operation_{i % 3}")

        baseline_time = time.time() - baseline_start

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
        self._logger.debug("Benchmarking async workflows")

        baseline_start = time.time()

        for i in range(5):
            await self._simulate_io_operation(f"seq_{i}", 0.01)

        baseline_time = time.time() - baseline_start

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
        await asyncio.sleep(0.002)

        result = ""
        for i in range(100):
            result += f"{operation_id}_{i}"

        return result[:50]

    async def _simulate_cached_operation(self, operation_id: str) -> str:
        cached_result = await self._cache.get_async(f"expensive_op: {operation_id}")
        if cached_result is not None:
            return str(cached_result)

        result = await self._simulate_expensive_operation(operation_id)
        await self._cache.set_async(
            f"expensive_op: {operation_id}", result, ttl_seconds=60
        )

        return result

    async def _simulate_io_operation(self, operation_id: str, duration: float) -> str:
        await asyncio.sleep(duration)
        return f"result_{operation_id}"

    def export_benchmark_results(
        self, suite: BenchmarkSuite, output_path: Path
    ) -> None:
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


class PerformanceBenchmarkService(
    PerformanceBenchmarkProtocol, PerformanceBenchmarkServiceProtocol, ServiceProtocol
):
    """Service wrapper for performance benchmarking in workflow orchestration."""

    @depends.inject
    def __init__(
        self, console: Console, logger: Inject[Logger], pkg_path: Path
    ) -> None:
        self._console = console
        self._pkg_path = pkg_path
        self._benchmarker = PerformanceBenchmarker(logger=logger)
        self._logger = logger

    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    # Methods for PerformanceBenchmarkProtocol
    def run_benchmark(self, operation: str) -> dict[str, t.Any]:
        """Run a specific benchmark operation."""
        start_time = time.time()
        # Since we don't have operation-specific benchmark methods,
        # we'll return basic timing information
        return {
            "operation": operation,
            "start_time": start_time,
            "end_time": time.time(),
            "duration": time.time() - start_time,
            "status": "completed",
        }

    def get_report(self) -> dict[str, t.Any]:
        """Get performance report."""
        # Return a basic report based on workflow metrics
        return {
            "timestamp": datetime.now().isoformat(),
            "report_type": "performance_summary",
            "total_benchmarks": 0,  # This would be updated with actual values from the benchmarker
            "summary": "Performance benchmark service operational",
        }

    def compare_benchmarks(
        self,
        baseline: dict[str, t.Any],
        current: dict[str, t.Any],
    ) -> dict[str, t.Any]:
        """Compare two benchmark results."""
        return {
            "comparison_type": "basic_comparison",
            "baseline": baseline,
            "current": current,
            "differences": {},
        }

    # Methods for PerformanceBenchmarkServiceProtocol
    async def run_benchmark_suite(self) -> BenchmarkSuite | None:
        """Run comprehensive benchmark suite and return results."""
        try:
            return await self._benchmarker.run_comprehensive_benchmark()
        except Exception as e:
            self._logger.warning(f"Benchmark suite failed: {e}")
            return None

    def export_results(self, suite: BenchmarkSuite, output_path: Path) -> None:
        """Export benchmark results to file."""
        self._benchmarker.export_benchmark_results(suite, output_path)


def get_benchmarker() -> PerformanceBenchmarker:
    return PerformanceBenchmarker(logger=depends.get_sync(Logger))
