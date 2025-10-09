"""Integration tests for Phase 10.3.1: ToolProfiler with real usage patterns."""

import time
from pathlib import Path

import pytest

from crackerjack.services.profiler import ToolProfiler


class TestToolProfilerIntegration:
    """Integration tests for realistic profiler usage."""

    @pytest.fixture
    def profiler(self, tmp_path: Path) -> ToolProfiler:
        """Create ToolProfiler instance with temp cache dir."""
        return ToolProfiler(cache_dir=tmp_path / "cache")

    def test_realistic_workflow_profiling(self, profiler: ToolProfiler):
        """Test profiling a realistic workflow with multiple tools."""

        # Simulate fast formatting tools
        def ruff_format():
            time.sleep(0.05)  # 50ms - typical fast formatter

        def ruff_isort():
            time.sleep(0.03)  # 30ms - typical import sorter

        # Simulate comprehensive analysis tools
        def zuban():
            time.sleep(0.5)  # 500ms - type checking

        def bandit():
            time.sleep(0.3)  # 300ms - security scanning

        # Profile each tool
        profiler.profile_tool("ruff-format", ruff_format, runs=5)
        profiler.profile_tool("ruff-isort", ruff_isort, runs=5)
        profiler.profile_tool("zuban", zuban, runs=3)
        profiler.profile_tool("bandit", bandit, runs=3)

        # Verify all tools were profiled
        assert len(profiler.results) == 4

        # Verify fast tools are faster than comprehensive tools
        fast_time = (
            profiler.results["ruff-format"].mean_time
            + profiler.results["ruff-isort"].mean_time
        )
        comp_time = (
            profiler.results["zuban"].mean_time + profiler.results["bandit"].mean_time
        )

        assert comp_time > fast_time * 5  # Comprehensive should be 5x+ slower

    def test_report_generation_workflow(self, profiler: ToolProfiler):
        """Test complete workflow: profile -> compare -> report."""

        # Profile some tools
        def fast_tool():
            time.sleep(0.01)

        def slow_tool():
            time.sleep(0.1)

        profiler.profile_tool("fast-tool", fast_tool, runs=3)
        profiler.profile_tool("slow-tool", slow_tool, runs=3)

        # Compare phases
        report = profiler.compare_phases()
        assert report.tools_profiled == 2

        # Generate markdown report
        markdown = profiler.generate_report()

        # Verify report contains key sections
        assert "# Performance Profile Report" in markdown
        assert "## Summary" in markdown
        assert "Tools Profiled: 2" in markdown
        assert "## Tool Performance" in markdown
        assert "fast-tool" in markdown
        assert "slow-tool" in markdown

    def test_bottleneck_detection_workflow(self, profiler: ToolProfiler):
        """Test bottleneck detection in realistic scenario."""

        # Create tools with different characteristics
        def normal_tool():
            time.sleep(0.1)  # Normal execution time

        def slow_tool():
            time.sleep(3.5)  # Triggers time bottleneck (>2s)

        # Profile tools
        profiler.profile_tool("normal-tool", normal_tool, runs=2)
        profiler.profile_tool("slow-tool", slow_tool, runs=2)

        # Add cache metrics to slow tool
        profiler.results["slow-tool"].cache_hits = 2
        profiler.results["slow-tool"].cache_misses = 18  # Triggers cache bottleneck (<50%)

        # Identify bottlenecks
        bottlenecks = profiler.identify_bottlenecks()

        # Should have bottlenecks for slow tool
        assert len(bottlenecks) >= 1

        # Find time bottleneck
        time_bottlenecks = [b for b in bottlenecks if b.metric_type == "time"]
        assert len(time_bottlenecks) >= 1
        assert time_bottlenecks[0].tool_name == "slow-tool"

        # Find cache bottleneck
        cache_bottlenecks = [b for b in bottlenecks if b.metric_type == "cache"]
        assert len(cache_bottlenecks) >= 1
        assert cache_bottlenecks[0].tool_name == "slow-tool"
