"""Performance profiling for tool execution.

Phase 10.3.1: Provides baseline metrics and bottleneck identification for optimization.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

import psutil


@dataclass
class ProfileResult:
    """Results from profiling a single tool."""

    tool_name: str
    runs: int
    execution_times: list[float] = field(default_factory=list)
    memory_usage: list[float] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def mean_time(self) -> float:
        """Average execution time."""
        return mean(self.execution_times) if self.execution_times else 0.0

    @property
    def median_time(self) -> float:
        """Median execution time."""
        return median(self.execution_times) if self.execution_times else 0.0

    @property
    def std_dev_time(self) -> float:
        """Standard deviation of execution times."""
        return stdev(self.execution_times) if len(self.execution_times) > 1 else 0.0

    @property
    def mean_memory(self) -> float:
        """Average memory usage in MB."""
        return mean(self.memory_usage) if self.memory_usage else 0.0

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate as percentage."""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0


@dataclass
class Bottleneck:
    """Identified performance bottleneck."""

    tool_name: str
    metric_type: str  # 'time', 'memory', 'cache'
    severity: str  # 'high', 'medium', 'low'
    value: float
    threshold: float
    recommendation: str


@dataclass
class ComparisonReport:
    """Comparison between fast and comprehensive hook phases."""

    fast_phase_time: float
    comprehensive_phase_time: float
    total_time: float
    tools_profiled: int
    bottlenecks: list[Bottleneck] = field(default_factory=list)

    @property
    def time_ratio(self) -> float:
        """Ratio of comprehensive to fast phase time."""
        return (
            self.comprehensive_phase_time / self.fast_phase_time
            if self.fast_phase_time > 0
            else 0.0
        )


class ToolProfiler:
    """Profiles tool execution for performance optimization."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize profiler.

        Args:
            cache_dir: Directory for cache statistics tracking
        """
        self.cache_dir = cache_dir or Path.cwd() / ".crackerjack" / "cache"
        self.results: dict[str, ProfileResult] = {}

    def profile_tool(
        self,
        tool_name: str,
        tool_func: Callable[[], Any],
        runs: int = 10,
    ) -> ProfileResult:
        """Profile a tool's execution performance.

        Args:
            tool_name: Name of the tool being profiled
            tool_func: Function to execute and profile
            runs: Number of profiling runs (default: 10)

        Returns:
            ProfileResult with timing and memory statistics
        """
        result = ProfileResult(tool_name=tool_name, runs=runs)
        process = psutil.Process()

        for _ in range(runs):
            # Memory before execution
            mem_before = process.memory_info().rss / 1024 / 1024  # MB

            # Time execution
            start_time = time.perf_counter()
            tool_func()
            end_time = time.perf_counter()

            # Memory after execution
            mem_after = process.memory_info().rss / 1024 / 1024  # MB

            # Record metrics
            result.execution_times.append(end_time - start_time)
            result.memory_usage.append(mem_after - mem_before)

        # Store result
        self.results[tool_name] = result
        return result

    def compare_phases(self) -> ComparisonReport:
        """Compare fast vs comprehensive hook phase performance.

        Returns:
            ComparisonReport with phase timing comparison
        """
        fast_tools = ["ruff-format", "ruff-isort"]
        comp_tools = ["zuban", "bandit", "complexipy"]

        fast_time = sum(
            self.results[t].mean_time for t in fast_tools if t in self.results
        )
        comp_time = sum(
            self.results[t].mean_time for t in comp_tools if t in self.results
        )

        report = ComparisonReport(
            fast_phase_time=fast_time,
            comprehensive_phase_time=comp_time,
            total_time=fast_time + comp_time,
            tools_profiled=len(self.results),
        )

        # Identify bottlenecks
        report.bottlenecks = self.identify_bottlenecks()

        return report

    def identify_bottlenecks(self) -> list[Bottleneck]:
        """Identify performance bottlenecks across all profiled tools.

        Returns:
            List of identified bottlenecks ordered by severity
        """
        bottlenecks: list[Bottleneck] = []

        for tool_name, result in self.results.items():
            # Time bottlenecks (>2s mean time)
            if result.mean_time > 2.0:
                severity = "high" if result.mean_time > 5.0 else "medium"
                bottlenecks.append(
                    Bottleneck(
                        tool_name=tool_name,
                        metric_type="time",
                        severity=severity,
                        value=result.mean_time,
                        threshold=2.0,
                        recommendation=(
                            "Consider incremental execution or caching strategy"
                        ),
                    )
                )

            # Memory bottlenecks (>100MB mean usage)
            if result.mean_memory > 100.0:
                severity = "high" if result.mean_memory > 500.0 else "medium"
                bottlenecks.append(
                    Bottleneck(
                        tool_name=tool_name,
                        metric_type="memory",
                        severity=severity,
                        value=result.mean_memory,
                        threshold=100.0,
                        recommendation="Optimize memory usage or implement streaming",
                    )
                )

            # Cache bottlenecks (<50% hit rate with >10 requests)
            total_requests = result.cache_hits + result.cache_misses
            if total_requests > 10 and result.cache_hit_rate < 50.0:
                bottlenecks.append(
                    Bottleneck(
                        tool_name=tool_name,
                        metric_type="cache",
                        severity="medium",
                        value=result.cache_hit_rate,
                        threshold=50.0,
                        recommendation="Improve cache strategy or increase cache TTL",
                    )
                )

        # Sort by severity (high -> medium -> low)
        severity_order = {"high": 0, "medium": 1, "low": 2}
        bottlenecks.sort(key=lambda b: severity_order[b.severity])

        return bottlenecks

    def generate_report(self) -> str:
        """Generate formatted performance report.

        Returns:
            Formatted report string with all profiling results
        """
        lines = ["# Performance Profile Report", ""]

        # Summary statistics
        if self.results:
            total_tools = len(self.results)
            total_time = sum(r.mean_time for r in self.results.values())
            total_memory = sum(r.mean_memory for r in self.results.values())

            lines.extend(
                [
                    "## Summary",
                    f"- Tools Profiled: {total_tools}",
                    f"- Total Mean Time: {total_time:.2f}s",
                    f"- Total Mean Memory: {total_memory:.2f}MB",
                    "",
                ]
            )

        # Individual tool results
        lines.append("## Tool Performance")
        for tool_name, result in sorted(self.results.items()):
            lines.extend(
                [
                    f"### {tool_name}",
                    f"- Runs: {result.runs}",
                    f"- Mean Time: {result.mean_time:.3f}s",
                    f"- Median Time: {result.median_time:.3f}s",
                    f"- Std Dev: {result.std_dev_time:.3f}s",
                    f"- Mean Memory: {result.mean_memory:.2f}MB",
                    f"- Cache Hit Rate: {result.cache_hit_rate:.1f}%",
                    "",
                ]
            )

        # Bottlenecks
        bottlenecks = self.identify_bottlenecks()
        if bottlenecks:
            lines.extend(["## Identified Bottlenecks", ""])
            for bottleneck in bottlenecks:
                lines.extend(
                    [
                        f"### {bottleneck.tool_name} ({bottleneck.severity.upper()})",
                        f"- Type: {bottleneck.metric_type}",
                        f"- Value: {bottleneck.value:.2f}",
                        f"- Threshold: {bottleneck.threshold:.2f}",
                        f"- Recommendation: {bottleneck.recommendation}",
                        "",
                    ]
                )

        return "\n".join(lines)
