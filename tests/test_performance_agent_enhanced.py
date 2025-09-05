"""
Enhanced tests for the optimized PerformanceAgent with real performance scenarios.
Tests the Qwen-audit recommended improvements for O(n²) detection and optimization.
"""

import tempfile
import time
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.performance_agent import PerformanceAgent


@pytest.fixture
def temp_context():
    with tempfile.TemporaryDirectory() as temp_dir:
        context = AgentContext(project_path=Path(temp_dir))
        yield context


@pytest.fixture
def performance_agent(temp_context):
    return PerformanceAgent(temp_context)


@pytest.fixture
def temp_python_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        yield Path(f.name)


class TestEnhancedPerformanceDetection:
    """Test enhanced performance issue detection capabilities."""

    @pytest.mark.asyncio
    async def test_enhanced_confidence_scoring(self, performance_agent) -> None:
        """Test that enhanced confidence scoring works for specific patterns."""
        high_confidence_issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            message="Nested loop causing O(n²) complexity",
            file_path="/test/main.py",
            severity=Priority.HIGH,
        )

        standard_issue = Issue(
            id="perf-002",
            type=IssueType.PERFORMANCE,
            message="Performance issue detected",
            file_path="/test/main.py",
            severity=Priority.MEDIUM,
        )

        high_confidence = await performance_agent.can_handle(high_confidence_issue)
        standard_confidence = await performance_agent.can_handle(standard_issue)

        assert high_confidence == 0.9  # Enhanced confidence for O(n²) patterns
        assert standard_confidence == 0.85  # Standard confidence


class TestNestedLoopDetection:
    """Test enhanced nested loop detection with O(n²) analysis."""

    @pytest.mark.asyncio
    async def test_detect_simple_nested_loops(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test detection of simple O(n²) nested loops."""
        temp_python_file.write_text("""
def simple_nested():
    for i in range(100):
        for j in range(100):
            print(i, j)

def triple_nested():
    for i in items:
        for j in other_items:
            for k in more_items:
                process(i, j, k)
""")

        issue = Issue(
            id="nested-001",
            type=IssueType.PERFORMANCE,
            message="Nested loop performance issue",
            file_path=str(temp_python_file),
            severity=Priority.HIGH,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True
        assert result.confidence >= 0.8

        # Check that optimizations were detected and applied
        assert result.fixes_applied is not None
        assert len(result.fixes_applied) > 0

        # Check that nested loop issues were detected in recommendations
        assert result.recommendations is not None
        recommendations_text = " ".join(result.recommendations).lower()
        assert any(
            keyword in recommendations_text
            for keyword in ["nested", "o(n", "complexity", "loop"]
        )

    @pytest.mark.asyncio
    async def test_complexity_priority_classification(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test that nested loops are classified by priority correctly."""
        temp_python_file.write_text("""
def critical_complexity():
    for a in range(1000):
        for b in range(1000):
            for c in range(1000):
                for d in range(1000):  # O(n⁴) - should be critical
                    expensive_operation(a, b, c, d)

def high_complexity():
    for x in data:
        for y in data:
            for z in data:  # O(n³) - should be high priority
                process(x, y, z)
""")

        issue = Issue(
            id="complexity-001",
            type=IssueType.PERFORMANCE,
            message="Complex nested loops",
            file_path=str(temp_python_file),
            severity=Priority.HIGH,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True
        assert result.fixes_applied is not None
        assert len(result.fixes_applied) > 0

        # Check that critical complexity issues were detected
        assert result.recommendations is not None
        recommendations_text = " ".join(result.recommendations).lower()
        assert any(
            keyword in recommendations_text
            for keyword in ["critical", "o(n", "high", "complexity"]
        )


class TestListOperationOptimization:
    """Test enhanced list operation optimization with performance impact assessment."""

    @pytest.mark.asyncio
    async def test_list_concatenation_in_loops(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test optimization of list concatenation in loops."""
        temp_python_file.write_text("""
def inefficient_list_building():
    results = []
    for i in range(1000):  # Large loop - high impact
        results += [i * 2]  # Should be replaced with append

    data = []
    for item in items:
        data += [item, item * 2, item * 3]  # Should use extend

    return results, data

def efficient_baseline():
    results = []
    for i in range(1000):
        results.append(i * 2)  # Already optimized
    return results
""")

        issue = Issue(
            id="list-001",
            type=IssueType.PERFORMANCE,
            message="Inefficient list operations",
            file_path=str(temp_python_file),
            severity=Priority.MEDIUM,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True
        assert result.confidence >= 0.8

        # Check that optimizations were applied
        optimized_content = temp_python_file.read_text()
        assert "results.append(i * 2)" in optimized_content
        assert "Performance:" in optimized_content  # Performance comments added

        # Check performance statistics are tracked
        assert performance_agent.optimization_stats["list_ops_optimized"] > 0

    @pytest.mark.asyncio
    async def test_performance_impact_assessment(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test that performance impact is correctly assessed."""
        temp_python_file.write_text("""
def high_impact_scenario():
    results = []
    for i in range(10000):  # Very large range - high impact
        for j in range(100):   # Nested - even higher impact
            results += [i + j]  # Should have high impact factor
    return results

def low_impact_scenario():
    data = []
    for x in small_list:  # Small iteration
        data += [x]  # Lower impact
    return data
""")

        issue = Issue(
            id="impact-001",
            type=IssueType.PERFORMANCE,
            message="List operations with varying impact",
            file_path=str(temp_python_file),
            severity=Priority.MEDIUM,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True
        # Should detect performance issues with various impacts
        recommendations_text = " ".join(result.recommendations or []).lower()
        assert any(
            keyword in recommendations_text
            for keyword in ["impact", "performance", "optimization", "improvement"]
        )


class TestStringOptimization:
    """Test enhanced string concatenation optimization."""

    @pytest.mark.asyncio
    async def test_string_concatenation_patterns(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test detection and optimization of string concatenation patterns."""
        temp_python_file.write_text("""
def inefficient_string_building():
    result = ""
    for i in range(1000):  # High impact string building
        result += str(i) + " "

    output = ""
    for line in lines:
        output += line + "\\n"  # More string concatenation

    # Inefficient empty join
    empty = "".join([])

    return result, output, empty

def with_repeated_formatting():
    output = ""
    for item in items:
        output += f"Processing {item.name} with {item.value}"  # Repeated formatting
    return output
""")

        issue = Issue(
            id="string-001",
            type=IssueType.PERFORMANCE,
            message="String concatenation inefficiencies",
            file_path=str(temp_python_file),
            severity=Priority.MEDIUM,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True

        optimized_content = temp_python_file.read_text()

        # Check string building optimization applied
        assert "result_parts = []" in optimized_content
        assert "result_parts.append" in optimized_content
        assert "result = ''.join(result_parts)" in optimized_content

        # Check performance comments added
        assert "Performance:" in optimized_content

        # Check optimization stats
        assert performance_agent.optimization_stats["string_concat_optimized"] > 0

    @pytest.mark.asyncio
    async def test_string_impact_assessment(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test string concatenation impact assessment."""
        temp_python_file.write_text("""
def high_impact_string_ops():
    result = ""
    for i in range(50000):  # Very large loop
        result += f"Item {i}: processing\\n"
    return result

def moderate_impact():
    text = ""
    for line in moderate_list:
        text += line + "\\n"
    return text
""")

        issue = Issue(
            id="string-impact-001",
            type=IssueType.PERFORMANCE,
            message="String operations with impact assessment",
            file_path=str(temp_python_file),
            severity=Priority.HIGH,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True
        assert any(
            "high-impact" in rec.lower() or "impact factor" in rec.lower()
            for rec in (result.recommendations or [])
        )


class TestBuiltinOptimization:
    """Test detection of inefficient builtin usage in loops."""

    @pytest.mark.asyncio
    async def test_repeated_builtin_calls(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test detection of repeated expensive builtin calls in loops."""
        temp_python_file.write_text("""
def inefficient_builtins():
    items = list(range(1000))
    results = []

    for i in range(len(items)):  # len() called repeatedly
        if i < len(items) - 1:   # More repeated len() calls
            results.append(items[i] + len(items))

    # More expensive operations in loops
    for item in data:
        sorted_data = sorted(large_dataset)  # Repeated sorting
        max_val = max(numbers)  # Repeated max
        results.append(item + max_val)

    return results
""")

        issue = Issue(
            id="builtin-001",
            type=IssueType.PERFORMANCE,
            message="Inefficient builtin usage",
            file_path=str(temp_python_file),
            severity=Priority.MEDIUM,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True

        optimized_content = temp_python_file.read_text()

        # Check caching comments added
        assert any("Cache len(" in line for line in optimized_content.split("\n"))
        assert any(
            "Cache sorted(" in line or "Cache max(" in line
            for line in optimized_content.split("\n")
        )


class TestComprehensiveOptimization:
    """Test comprehensive optimization scenarios with multiple issue types."""

    @pytest.mark.asyncio
    async def test_multiple_optimization_types(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test handling of files with multiple performance issues."""
        temp_python_file.write_text("""
def complex_inefficient_function():
    # Nested loops (O(n²))
    results = []
    for i in range(100):
        for j in range(100):
            # List concatenation in nested loop (high impact)
            results += [i * j]

    # String building inefficiency
    output = ""
    for result in results:
        output += str(result) + ", "

    # Repeated expensive calls
    processed = []
    for item in results:
        if len(results) > 100:  # Repeated len() call
            processed.append(max(results) + item)  # Repeated max() call

    # List comprehension opportunity
    doubled = []
    for x in processed:
        doubled.append(x * 2)

    return output, doubled

def already_optimized():
    # This should not trigger optimizations
    results = [i * j for i in range(10) for j in range(10)]
    return results
""")

        issue = Issue(
            id="multi-001",
            type=IssueType.PERFORMANCE,
            message="Multiple performance issues",
            file_path=str(temp_python_file),
            severity=Priority.HIGH,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True
        assert result.confidence >= 0.8

        # Check optimization summary
        summary = performance_agent._generate_optimization_summary()
        assert "Total:" in summary
        assert any(count > 0 for count in performance_agent.optimization_stats.values())

        optimized_content = temp_python_file.read_text()

        # Verify multiple optimization types applied
        performance_comments = [
            line for line in optimized_content.split("\n") if "Performance:" in line
        ]
        assert len(performance_comments) > 3  # Multiple optimizations

        # Check specific optimizations
        assert "results.append(i * j)" in optimized_content  # List optimization
        assert "output_parts = []" in optimized_content  # String optimization
        assert "Cache len(" in optimized_content  # Builtin caching
        assert "O(n^2)" in optimized_content  # Nested loop detection


class TestPerformanceMetrics:
    """Test performance measurement and tracking capabilities."""

    @pytest.mark.asyncio
    async def test_performance_measurement_tracking(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test that performance metrics are properly tracked."""
        temp_python_file.write_text("""
def sample_function():
    results = []
    for i in range(10):
        results += [i]
    return results
""")

        start_time = time.time()

        issue = Issue(
            id="metrics-001",
            type=IssueType.PERFORMANCE,
            message="Test performance tracking",
            file_path=str(temp_python_file),
            severity=Priority.MEDIUM,
        )

        await performance_agent.analyze_and_fix(issue)

        # Check performance metrics were recorded
        assert str(temp_python_file) in performance_agent.performance_metrics
        metrics = performance_agent.performance_metrics[str(temp_python_file)]

        assert "analysis_duration" in metrics
        assert metrics["analysis_duration"] > 0
        assert "timestamp" in metrics
        assert metrics["timestamp"] >= start_time
        assert "optimizations_applied" in metrics

    def test_optimization_statistics_tracking(self, performance_agent) -> None:
        """Test that optimization statistics are properly initialized and tracked."""
        # Check initial state
        assert performance_agent.optimization_stats["nested_loops_optimized"] == 0
        assert performance_agent.optimization_stats["list_ops_optimized"] == 0
        assert performance_agent.optimization_stats["string_concat_optimized"] == 0
        assert performance_agent.optimization_stats["repeated_ops_cached"] == 0
        assert performance_agent.optimization_stats["comprehensions_applied"] == 0

        # Check summary generation
        summary = performance_agent._generate_optimization_summary()
        assert summary == "No optimizations applied in this session"


class TestRealWorldScenarios:
    """Test with real-world performance scenarios."""

    @pytest.mark.asyncio
    async def test_data_processing_scenario(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test optimization of typical data processing code."""
        temp_python_file.write_text("""
def process_large_dataset(data):
    # Typical inefficient data processing
    results = []
    summary = ""

    for i, record in enumerate(data):
        for j, other_record in enumerate(data):  # O(n²) comparison
            if record.id != other_record.id:
                results += [{"pair": (i, j), "similarity": calculate_similarity(record, other_record)}]

        summary += f"Processed record {i}: {record.name}\\n"

        if len(results) > 1000:  # Repeated len() check
            break

    # String processing
    output = ""
    for result in results:
        output += f"Similarity: {result['similarity']:.2f}\\n"

    return results, summary, output

def calculate_similarity(a, b):
    return 0.5  # Placeholder
""")

        issue = Issue(
            id="realworld-001",
            type=IssueType.PERFORMANCE,
            message="Data processing performance issues",
            file_path=str(temp_python_file),
            severity=Priority.HIGH,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True

        optimized_content = temp_python_file.read_text()

        # Should detect and comment on O(n²) algorithm
        assert "O(n^2)" in optimized_content
        assert "CRITICAL" in optimized_content or "HIGH" in optimized_content

        # Should optimize list operations
        assert (
            "results.append(" in optimized_content
            or "results.extend(" in optimized_content
        )

        # Should optimize string building
        assert "_parts = []" in optimized_content

        # Should suggest caching len()
        assert "Cache len(" in optimized_content


if __name__ == "__main__":
    pytest.main([__file__])
