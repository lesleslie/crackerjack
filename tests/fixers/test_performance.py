"""Tests for crackerjack.fixers.performance.

Ported from tests/unit/agents/test_performance_agent.py,
tests/test_performance_agent_enhanced.py, and
tests/test_performance_agent_simple.py, keeping only the cases that exercise
real AST-based hot-spot detection and deterministic content transforms.

Cases exercising SubAgent/coordinator dispatch (``can_handle``,
``get_supported_types``) and the semantic/session-buddy enhancement
machinery (``_detect_semantic_performance_issues``, ``semantic_enhancer``
mocking, and the agent-level ``performance_metrics``/
``_generate_optimization_summary`` cross-call session bookkeeping) were
dropped, since that machinery no longer exists. See the module docstring of
``crackerjack/fixers/performance.py`` for the full kept/dropped rationale.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.fixers import performance
from crackerjack.models.issues import Issue, IssueType, Priority


class TestExtractPerformanceCriticalFunctions:
    def test_detects_function_with_nested_loops(self) -> None:
        content = """
def process_items(items):
    result = []
    for item in items:
        for subitem in item:
            result.append(subitem)
    return result
"""
        functions = performance.extract_performance_critical_functions(content)

        assert len(functions) == 1
        assert functions[0]["name"] == "process_items"
        assert functions[0]["estimated_complexity"] >= 2

    def test_ignores_simple_non_critical_function(self) -> None:
        content = """
def add(a, b):
    return a + b
"""
        functions = performance.extract_performance_critical_functions(content)

        assert functions == []

    def test_detects_by_name_heuristic(self) -> None:
        content = """
def calculate_totals(data):
    x = data[0]
    return x
"""
        functions = performance.extract_performance_critical_functions(content)

        assert len(functions) == 1
        assert functions[0]["name"] == "calculate_totals"

    def test_estimated_complexity_grows_with_loop_nesting(self) -> None:
        content = """
def triple_nested():
    for i in a:
        for j in b:
            for k in c:
                process(i, j, k)
"""
        functions = performance.extract_performance_critical_functions(content)

        assert len(functions) == 1
        assert functions[0]["estimated_complexity"] >= 3


class TestDetectPerformanceIssues:
    def test_detects_nested_loops_with_correct_complexity_notation(self) -> None:
        content = """
def nested():
    for i in range(100):
        for j in range(100):
            print(i, j)
"""
        issues = performance.detect_performance_issues(content, "test.py")

        nested_issue = next(i for i in issues if i["type"] == "nested_loops_enhanced")
        assert nested_issue["total_count"] == 1
        assert nested_issue["instances"][0]["complexity"] == "O(n²)"
        assert nested_issue["instances"][0]["priority"] == "high"

    def test_detects_critical_quadruple_nested_loops(self) -> None:
        content = """
def critical():
    for a in range(10):
        for b in range(10):
            for c in range(10):
                for d in range(10):
                    x = a + b + c + d
"""
        issues = performance.detect_performance_issues(content, "test.py")

        nested_issue = next(i for i in issues if i["type"] == "nested_loops_enhanced")
        priorities = [inst["priority"] for inst in nested_issue["instances"]]
        assert "critical" in priorities

    def test_detects_inefficient_list_concat_as_append(self) -> None:
        content = """
def build():
    results = []
    for i in range(10):
        results += [i]
    return results
"""
        issues = performance.detect_performance_issues(content, "test.py")

        list_issue = next(
            i for i in issues if i["type"] == "inefficient_list_operations_enhanced"
        )
        assert list_issue["instances"][0]["optimization"] == "append"

    def test_detects_inefficient_list_concat_as_extend(self) -> None:
        content = """
def build():
    data = []
    for item in items:
        data += [item, item * 2]
    return data
"""
        issues = performance.detect_performance_issues(content, "test.py")

        list_issue = next(
            i for i in issues if i["type"] == "inefficient_list_operations_enhanced"
        )
        assert list_issue["instances"][0]["optimization"] == "extend"

    def test_detects_list_comprehension_opportunity(self) -> None:
        content = """
def build():
    results = []
    for i in range(10):
        results.append(i * 2)
    return results
"""
        issues = performance.detect_performance_issues(content, "test.py")

        assert any(i["type"] == "list_comprehension_opportunities" for i in issues)

    def test_detects_repeated_builtin_in_loop(self) -> None:
        content = """
def process(items):
    for i in range(len(items)):
        if i < len(items) - 1:
            pass
"""
        issues = performance.detect_performance_issues(content, "test.py")

        builtin_issue = next(
            i for i in issues if i["type"] == "inefficient_builtin_usage"
        )
        assert builtin_issue["total_count"] >= 1

    def test_returns_empty_on_syntax_error(self) -> None:
        issues = performance.detect_performance_issues("def broken(:", "test.py")

        assert issues == []

    def test_clean_code_produces_no_issues(self) -> None:
        content = "def add(a, b):\n    return a + b\n"

        issues = performance.detect_performance_issues(content, "test.py")

        assert issues == []


class TestApplyPerformanceOptimizations:
    def test_list_concat_replaced_with_append(self) -> None:
        content = (
            "def build():\n"
            "    results = []\n"
            "    for i in range(10):\n"
            "        results += [i]\n"
            "    return results\n"
        )
        issues = performance.detect_performance_issues(content, "test.py")
        stats = performance.create_optimization_stats()

        optimized = performance.apply_performance_optimizations(content, issues, stats)

        assert "results.append(i)" in optimized
        assert "Performance:" in optimized
        assert stats["list_ops_optimized"] > 0

    def test_string_concat_replaced_with_list_join(self) -> None:
        content = (
            "def build():\n"
            '    result = ""\n'
            "    for i in range(10):\n"
            '        result += str(i) + " "\n'
            "    return result\n"
        )
        issues = performance.detect_performance_issues(content, "test.py")
        stats = performance.create_optimization_stats()

        optimized = performance.apply_performance_optimizations(content, issues, stats)

        assert "result_parts = []" in optimized
        assert "result_parts.append" in optimized
        assert "result = ''.join(result_parts)" in optimized
        assert stats["string_concat_optimized"] > 0

    def test_nested_loop_gets_complexity_comment(self) -> None:
        content = (
            "def nested():\n"
            "    for i in range(100):\n"
            "        for j in range(100):\n"
            "            print(i, j)\n"
        )
        issues = performance.detect_performance_issues(content, "test.py")
        stats = performance.create_optimization_stats()

        optimized = performance.apply_performance_optimizations(content, issues, stats)

        assert "O(n^2)" in optimized
        assert stats["nested_loops_optimized"] > 0

    def test_no_issues_returns_unchanged_content(self) -> None:
        content = "def add(a, b):\n    return a + b\n"
        stats = performance.create_optimization_stats()

        optimized = performance.apply_performance_optimizations(content, [], stats)

        assert optimized == content


class TestGenerateOptimizationSummary:
    def test_no_optimizations(self) -> None:
        stats = performance.create_optimization_stats()

        summary = performance.generate_optimization_summary(stats)

        assert summary == "No optimizations applied in this session"

    def test_with_optimizations(self) -> None:
        stats = performance.create_optimization_stats()
        stats["list_ops_optimized"] = 2
        stats["nested_loops_optimized"] = 1

        summary = performance.generate_optimization_summary(stats)

        assert "Total: 3" in summary
        assert "list_ops_optimized: 2" in summary
        assert "nested_loops_optimized: 1" in summary


class TestValidatePerformanceIssue:
    def test_no_file_path(self) -> None:
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=None,
        )

        result = performance._validate_performance_issue(issue)

        assert result is not None
        assert result.success is False

    def test_file_not_exists(self, tmp_path: Path) -> None:
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=str(tmp_path / "missing.py"),
        )

        result = performance._validate_performance_issue(issue)

        assert result is not None
        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    def test_valid_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "valid.py"
        test_file.write_text("def foo(): pass")

        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=str(test_file),
        )

        result = performance._validate_performance_issue(issue)

        assert result is None


class TestCreateNoOptimizationResult:
    def test_shape(self) -> None:
        result = performance._create_no_optimization_result()

        assert result.success is False
        assert result.confidence == 0.6
        assert len(result.remaining_issues) > 0
        assert "Manual optimization" in result.recommendations[0]


class TestOptimizePerformance:
    async def test_no_file_path(self) -> None:
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=None,
        )

        result = await performance.optimize_performance(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_file_not_found(self, tmp_path: Path) -> None:
        issue = Issue(
            id="perf-002",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=str(tmp_path / "nonexistent.py"),
        )

        result = await performance.optimize_performance(issue)

        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_no_performance_issues_detected(self, tmp_path: Path) -> None:
        test_file = tmp_path / "clean.py"
        test_file.write_text("def add(a, b):\n    return a + b\n")

        issue = Issue(
            id="perf-003",
            type=IssueType.PERFORMANCE,
            severity=Priority.MEDIUM,
            message="Performance issue",
            file_path=str(test_file),
        )

        result = await performance.optimize_performance(issue)

        assert result.success is True
        assert result.confidence == 0.7
        assert "No performance issues" in result.recommendations[0]

    async def test_read_error_returns_error_result(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        issue = Issue(
            id="perf-004",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=str(test_file),
        )

        def boom(_path: object) -> str:
            raise RuntimeError("Read error")

        monkeypatch.setattr(performance, "_read_file", boom)

        result = await performance.optimize_performance(issue)

        assert result.success is False
        assert "Error processing file" in result.remaining_issues[0]

    async def test_detects_and_fixes_nested_loops(self, tmp_path: Path) -> None:
        test_file = tmp_path / "slow.py"
        test_file.write_text(
            "def simple_nested():\n"
            "    for i in range(100):\n"
            "        for j in range(100):\n"
            "            print(i, j)\n",
        )

        issue = Issue(
            id="nested-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Nested loop performance issue",
            file_path=str(test_file),
        )

        result = await performance.optimize_performance(issue)

        assert result.success is True
        assert result.confidence >= 0.8
        assert len(result.fixes_applied) > 0

        optimized_content = test_file.read_text()
        assert "O(n^2)" in optimized_content
        assert "Performance:" in optimized_content

    async def test_fixes_list_concatenation_in_loop(self, tmp_path: Path) -> None:
        test_file = tmp_path / "list_ops.py"
        test_file.write_text(
            "def inefficient_list_building():\n"
            "    results = []\n"
            "    for i in range(1000):\n"
            "        results += [i * 2]\n"
            "    return results\n",
        )

        issue = Issue(
            id="list-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.MEDIUM,
            message="Inefficient list operations",
            file_path=str(test_file),
        )

        result = await performance.optimize_performance(issue)

        assert result.success is True
        optimized_content = test_file.read_text()
        assert "results.append(i * 2)" in optimized_content
        assert "Performance:" in optimized_content

    async def test_fixes_string_concatenation(self, tmp_path: Path) -> None:
        test_file = tmp_path / "strings.py"
        test_file.write_text(
            "def inefficient_string_building():\n"
            '    result = ""\n'
            "    for i in range(1000):\n"
            '        result += str(i) + " "\n'
            "    return result\n",
        )

        issue = Issue(
            id="string-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.MEDIUM,
            message="String concatenation inefficiencies",
            file_path=str(test_file),
        )

        result = await performance.optimize_performance(issue)

        assert result.success is True
        optimized_content = test_file.read_text()
        assert "result_parts = []" in optimized_content
        assert "result_parts.append" in optimized_content
        assert "result = ''.join(result_parts)" in optimized_content

    async def test_multiple_optimization_types_reported_in_summary(
        self,
        tmp_path: Path,
    ) -> None:
        test_file = tmp_path / "multi.py"
        test_file.write_text(
            "def complex_inefficient_function():\n"
            "    results = []\n"
            "    for i in range(100):\n"
            "        for j in range(100):\n"
            "            results += [i * j]\n"
            "    return results\n",
        )

        issue = Issue(
            id="multi-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Multiple performance issues",
            file_path=str(test_file),
        )

        result = await performance.optimize_performance(issue)

        assert result.success is True
        summary = result.fixes_applied[-1]
        assert "Total:" in summary
        assert "nested_loops_optimized" in summary or "list_ops_optimized" in summary

    async def test_recommendations_include_pattern_suggestions(
        self,
        tmp_path: Path,
    ) -> None:
        test_file = tmp_path / "nested_only.py"
        test_file.write_text(
            "def nested():\n"
            "    for i in range(100):\n"
            "        for j in range(100):\n"
            "            print(i, j)\n",
        )

        issue = Issue(
            id="nested-002",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Nested loop performance issue",
            file_path=str(test_file),
        )

        result = await performance.optimize_performance(issue)

        assert result.success is True
        assert "Test performance improvements with benchmarks" in result.recommendations
        recommendations_text = " ".join(result.recommendations).lower()
        assert any(
            keyword in recommendations_text
            for keyword in ("nested", "o(n", "complexity", "loop")
        )
