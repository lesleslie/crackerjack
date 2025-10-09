"""Tests for Phase 10.3.1: Performance Profiling."""

import time
from pathlib import Path

import pytest

from crackerjack.services.profiler import (
    Bottleneck,
    ComparisonReport,
    ProfileResult,
    ToolProfiler,
)


class TestProfileResult:
    """Test ProfileResult dataclass and properties."""

    def test_profile_result_initialization(self):
        """Test ProfileResult can be initialized."""
        result = ProfileResult(tool_name="test-tool", runs=5)

        assert result.tool_name == "test-tool"
        assert result.runs == 5
        assert result.execution_times == []
        assert result.memory_usage == []
        assert result.cache_hits == 0
        assert result.cache_misses == 0

    def test_mean_time_calculation(self):
        """Test mean_time property calculates correctly."""
        result = ProfileResult(
            tool_name="test-tool",
            runs=3,
            execution_times=[1.0, 2.0, 3.0],
        )

        assert result.mean_time == 2.0

    def test_median_time_calculation(self):
        """Test median_time property calculates correctly."""
        result = ProfileResult(
            tool_name="test-tool",
            runs=3,
            execution_times=[1.0, 2.0, 3.0],
        )

        assert result.median_time == 2.0

    def test_std_dev_time_calculation(self):
        """Test std_dev_time property calculates correctly."""
        result = ProfileResult(
            tool_name="test-tool",
            runs=3,
            execution_times=[1.0, 2.0, 3.0],
        )

        # Standard deviation of [1.0, 2.0, 3.0] is 1.0
        assert result.std_dev_time == pytest.approx(1.0, abs=0.01)

    def test_mean_memory_calculation(self):
        """Test mean_memory property calculates correctly."""
        result = ProfileResult(
            tool_name="test-tool",
            runs=3,
            memory_usage=[10.0, 20.0, 30.0],
        )

        assert result.mean_memory == 20.0

    def test_cache_hit_rate_calculation(self):
        """Test cache_hit_rate property calculates correctly."""
        result = ProfileResult(
            tool_name="test-tool",
            runs=10,
            cache_hits=7,
            cache_misses=3,
        )

        assert result.cache_hit_rate == 70.0

    def test_cache_hit_rate_zero_requests(self):
        """Test cache_hit_rate returns 0 when no cache requests."""
        result = ProfileResult(
            tool_name="test-tool",
            runs=10,
            cache_hits=0,
            cache_misses=0,
        )

        assert result.cache_hit_rate == 0.0

    def test_empty_execution_times(self):
        """Test properties handle empty execution_times list."""
        result = ProfileResult(tool_name="test-tool", runs=0)

        assert result.mean_time == 0.0
        assert result.median_time == 0.0
        assert result.std_dev_time == 0.0

    def test_single_execution_time(self):
        """Test std_dev handles single execution time."""
        result = ProfileResult(
            tool_name="test-tool",
            runs=1,
            execution_times=[1.5],
        )

        assert result.mean_time == 1.5
        assert result.median_time == 1.5
        assert result.std_dev_time == 0.0  # Single value has no deviation


class TestBottleneck:
    """Test Bottleneck dataclass."""

    def test_bottleneck_initialization(self):
        """Test Bottleneck can be initialized."""
        bottleneck = Bottleneck(
            tool_name="slow-tool",
            metric_type="time",
            severity="high",
            value=5.5,
            threshold=2.0,
            recommendation="Optimize algorithm",
        )

        assert bottleneck.tool_name == "slow-tool"
        assert bottleneck.metric_type == "time"
        assert bottleneck.severity == "high"
        assert bottleneck.value == 5.5
        assert bottleneck.threshold == 2.0
        assert bottleneck.recommendation == "Optimize algorithm"


class TestComparisonReport:
    """Test ComparisonReport dataclass and properties."""

    def test_comparison_report_initialization(self):
        """Test ComparisonReport can be initialized."""
        report = ComparisonReport(
            fast_phase_time=1.5,
            comprehensive_phase_time=8.5,
            total_time=10.0,
            tools_profiled=5,
        )

        assert report.fast_phase_time == 1.5
        assert report.comprehensive_phase_time == 8.5
        assert report.total_time == 10.0
        assert report.tools_profiled == 5
        assert report.bottlenecks == []

    def test_time_ratio_calculation(self):
        """Test time_ratio property calculates correctly."""
        report = ComparisonReport(
            fast_phase_time=2.0,
            comprehensive_phase_time=8.0,
            total_time=10.0,
            tools_profiled=5,
        )

        assert report.time_ratio == 4.0  # 8.0 / 2.0

    def test_time_ratio_zero_fast_phase(self):
        """Test time_ratio handles zero fast_phase_time."""
        report = ComparisonReport(
            fast_phase_time=0.0,
            comprehensive_phase_time=8.0,
            total_time=8.0,
            tools_profiled=5,
        )

        assert report.time_ratio == 0.0


class TestToolProfiler:
    """Test ToolProfiler class."""

    @pytest.fixture
    def profiler(self, tmp_path: Path) -> ToolProfiler:
        """Create ToolProfiler instance with temp cache dir."""
        return ToolProfiler(cache_dir=tmp_path / "cache")

    def test_profiler_initialization(self, tmp_path: Path):
        """Test ToolProfiler initializes correctly."""
        profiler = ToolProfiler(cache_dir=tmp_path / "cache")

        assert profiler.cache_dir == tmp_path / "cache"
        assert profiler.results == {}

    def test_profiler_default_cache_dir(self):
        """Test ToolProfiler uses default cache_dir when not provided."""
        profiler = ToolProfiler()

        expected_dir = Path.cwd() / ".crackerjack" / "cache"
        assert profiler.cache_dir == expected_dir

    def test_profile_tool_execution(self, profiler: ToolProfiler):
        """Test profile_tool profiles a simple function."""

        def dummy_tool():
            time.sleep(0.01)  # 10ms sleep

        result = profiler.profile_tool("test-tool", dummy_tool, runs=3)

        assert result.tool_name == "test-tool"
        assert result.runs == 3
        assert len(result.execution_times) == 3
        assert len(result.memory_usage) == 3
        assert all(t >= 0.01 for t in result.execution_times)

    def test_profile_tool_stores_result(self, profiler: ToolProfiler):
        """Test profile_tool stores result in profiler.results."""

        def dummy_tool():
            pass

        profiler.profile_tool("test-tool", dummy_tool, runs=2)

        assert "test-tool" in profiler.results
        assert profiler.results["test-tool"].tool_name == "test-tool"

    def test_identify_bottlenecks_time(self, profiler: ToolProfiler):
        """Test identify_bottlenecks detects slow tools."""
        # Create result with slow execution time
        profiler.results["slow-tool"] = ProfileResult(
            tool_name="slow-tool",
            runs=5,
            execution_times=[3.0, 3.5, 3.2, 3.1, 3.3],
        )

        bottlenecks = profiler.identify_bottlenecks()

        assert len(bottlenecks) >= 1
        time_bottleneck = next(b for b in bottlenecks if b.metric_type == "time")
        assert time_bottleneck.tool_name == "slow-tool"
        assert time_bottleneck.severity in ["high", "medium"]
        assert time_bottleneck.value > 2.0

    def test_identify_bottlenecks_memory(self, profiler: ToolProfiler):
        """Test identify_bottlenecks detects memory-heavy tools."""
        # Create result with high memory usage
        profiler.results["memory-hog"] = ProfileResult(
            tool_name="memory-hog",
            runs=3,
            memory_usage=[150.0, 160.0, 155.0],
        )

        bottlenecks = profiler.identify_bottlenecks()

        assert len(bottlenecks) >= 1
        memory_bottleneck = next(b for b in bottlenecks if b.metric_type == "memory")
        assert memory_bottleneck.tool_name == "memory-hog"
        assert memory_bottleneck.severity in ["high", "medium"]
        assert memory_bottleneck.value > 100.0

    def test_identify_bottlenecks_cache(self, profiler: ToolProfiler):
        """Test identify_bottlenecks detects poor cache performance."""
        # Create result with low cache hit rate
        profiler.results["cache-poor"] = ProfileResult(
            tool_name="cache-poor",
            runs=20,
            cache_hits=3,
            cache_misses=17,
        )

        bottlenecks = profiler.identify_bottlenecks()

        assert len(bottlenecks) >= 1
        cache_bottleneck = next(b for b in bottlenecks if b.metric_type == "cache")
        assert cache_bottleneck.tool_name == "cache-poor"
        assert cache_bottleneck.severity == "medium"
        assert cache_bottleneck.value < 50.0

    def test_identify_bottlenecks_sorted_by_severity(self, profiler: ToolProfiler):
        """Test identify_bottlenecks sorts by severity (high -> medium -> low)."""
        # Create results with different severities
        profiler.results["high-severity"] = ProfileResult(
            tool_name="high-severity",
            runs=5,
            execution_times=[6.0, 6.5, 6.2, 6.3, 6.1],  # >5s = high
        )
        profiler.results["medium-severity"] = ProfileResult(
            tool_name="medium-severity",
            runs=5,
            execution_times=[3.0, 3.5, 3.2, 3.1, 3.3],  # 2-5s = medium
        )

        bottlenecks = profiler.identify_bottlenecks()

        # First bottleneck should be high severity
        assert bottlenecks[0].severity == "high"
        # Second should be medium
        assert bottlenecks[1].severity == "medium"

    def test_compare_phases(self, profiler: ToolProfiler):
        """Test compare_phases generates comparison report."""
        # Add fast phase tools
        profiler.results["ruff-format"] = ProfileResult(
            tool_name="ruff-format",
            runs=3,
            execution_times=[0.5, 0.6, 0.55],
        )
        profiler.results["ruff-isort"] = ProfileResult(
            tool_name="ruff-isort",
            runs=3,
            execution_times=[0.3, 0.35, 0.32],
        )

        # Add comprehensive phase tools
        profiler.results["zuban"] = ProfileResult(
            tool_name="zuban",
            runs=3,
            execution_times=[2.0, 2.1, 2.05],
        )
        profiler.results["bandit"] = ProfileResult(
            tool_name="bandit",
            runs=3,
            execution_times=[1.5, 1.6, 1.55],
        )

        report = profiler.compare_phases()

        assert report.fast_phase_time > 0
        assert report.comprehensive_phase_time > 0
        assert report.total_time == report.fast_phase_time + report.comprehensive_phase_time
        assert report.tools_profiled == 4
        assert report.time_ratio > 1.0  # Comprehensive should be slower

    def test_generate_report_format(self, profiler: ToolProfiler):
        """Test generate_report creates formatted markdown."""
        # Add a simple result
        profiler.results["test-tool"] = ProfileResult(
            tool_name="test-tool",
            runs=5,
            execution_times=[1.0, 1.1, 1.05, 1.08, 1.02],
            memory_usage=[50.0, 51.0, 50.5, 50.8, 50.2],
            cache_hits=8,
            cache_misses=2,
        )

        report = profiler.generate_report()

        # Check for key sections
        assert "# Performance Profile Report" in report
        assert "## Summary" in report
        assert "## Tool Performance" in report
        assert "### test-tool" in report
        assert "Mean Time:" in report
        assert "Cache Hit Rate:" in report

    def test_generate_report_includes_bottlenecks(self, profiler: ToolProfiler):
        """Test generate_report includes bottleneck section when present."""
        # Add slow tool to trigger bottleneck
        profiler.results["slow-tool"] = ProfileResult(
            tool_name="slow-tool",
            runs=3,
            execution_times=[3.5, 3.6, 3.55],
        )

        report = profiler.generate_report()

        assert "## Identified Bottlenecks" in report
        assert "slow-tool" in report
        assert "Recommendation:" in report

    def test_generate_report_empty_results(self, profiler: ToolProfiler):
        """Test generate_report handles empty results gracefully."""
        report = profiler.generate_report()

        assert "# Performance Profile Report" in report
        assert "## Tool Performance" in report
        # Should not crash with empty results
