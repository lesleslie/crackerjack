from __future__ import annotations

import ast
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext
from crackerjack.agents.helpers.refactoring.dead_code_detector import (
    DeadCodeDetector,
    EnhancedUsageAnalyzer,
    UsageDataCollector,
)


@pytest.fixture
def context(tmp_path: Path) -> AgentContext:
    return AgentContext(project_path=tmp_path)


@pytest.fixture
def detector(context: AgentContext) -> DeadCodeDetector:
    return DeadCodeDetector(context)


# ---------------------------------------------------------------------------
# UsageDataCollector + EnhancedUsageAnalyzer


class TestEnhancedUsageAnalyzer:
    def test_visit_import_records_name(self) -> None:
        src = "import os\nimport sys"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        names = [row[1] for row in collector.import_lines]
        assert "os" in names
        assert "sys" in names

    def test_visit_import_from_records_name(self) -> None:
        src = "from pathlib import Path"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        names = [row[1] for row in collector.import_lines]
        assert "Path" in names

    def test_import_alias_uses_asname(self) -> None:
        src = "import numpy as np"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        names = [row[1] for row in collector.import_lines]
        assert "np" in names

    def test_visit_function_def_records_and_marks_used(self) -> None:
        src = "def foo(): pass"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        func_names = [f["name"] for f in collector.functions]
        assert "foo" in func_names
        assert "foo" in analyzer.used_names

    def test_visit_class_def_records_and_marks_used(self) -> None:
        src = "class MyClass: pass"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        class_names = [c["name"] for c in collector.classes]
        assert "MyClass" in class_names
        assert "MyClass" in analyzer.used_names

    def test_visit_name_adds_to_used(self) -> None:
        src = "x = foo_func()"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        assert "foo_func" in analyzer.used_names

    def test_visit_attribute_adds_attr_to_used(self) -> None:
        src = "obj.method()"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        assert "method" in analyzer.used_names

    def test_get_results_structure(self) -> None:
        src = "import os\ndef bar(): pass"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        results = collector.get_results(analyzer)
        assert "import_lines" in results
        assert "used_names" in results
        assert "unused_functions" in results
        assert "unused_classes" in results


# ---------------------------------------------------------------------------
# DeadCodeDetector._collect_usage_data


class TestCollectUsageData:
    def test_returns_expected_keys(self, detector: DeadCodeDetector) -> None:
        src = "import os\ndef foo(): pass"
        tree = ast.parse(src)
        result = detector._collect_usage_data(tree)
        assert "import_lines" in result
        assert "used_names" in result
        assert "unused_functions" in result

    def test_collects_imports_and_functions(self, detector: DeadCodeDetector) -> None:
        src = "import re\ndef helper(): pass"
        tree = ast.parse(src)
        result = detector._collect_usage_data(tree)
        import_names = [row[1] for row in result["import_lines"]]
        assert "re" in import_names
        func_names = [f["name"] for f in result["unused_functions"]]
        assert "helper" in func_names


# ---------------------------------------------------------------------------
# DeadCodeDetector._process_unused_imports


class TestProcessUnusedImports:
    def test_marks_truly_unused_import(self) -> None:
        src = "import os"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        analyzer.used_names.discard("os")
        result = collector.get_results(analyzer)
        analysis: dict = {"unused_imports": [], "removable_items": []}
        DeadCodeDetector._process_unused_imports(analysis, result)
        assert any(i["name"] == "os" for i in analysis["unused_imports"])
        assert any("os" in item for item in analysis["removable_items"])

    def test_does_not_mark_used_import(self) -> None:
        src = "import os\npath = os.path.join('a', 'b')"
        tree = ast.parse(src)
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        result = collector.get_results(analyzer)
        analysis: dict = {"unused_imports": [], "removable_items": []}
        DeadCodeDetector._process_unused_imports(analysis, result)
        assert not any(i["name"] == "os" for i in analysis["unused_imports"])


# ---------------------------------------------------------------------------
# DeadCodeDetector._process_unused_functions


class TestProcessUnusedFunctions:
    def test_marks_function_not_in_used_names(self) -> None:
        collector = UsageDataCollector()
        collector.functions = [{"name": "orphan", "line": 5}]
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.used_names = set()
        result = collector.get_results(analyzer)
        analysis: dict = {"unused_functions": [], "removable_items": []}
        DeadCodeDetector._process_unused_functions(analysis, result)
        assert any(f["name"] == "orphan" for f in analysis["unused_functions"])

    def test_skips_function_in_used_names(self) -> None:
        collector = UsageDataCollector()
        collector.functions = [{"name": "active_func", "line": 1}]
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.used_names = {"active_func"}
        result = collector.get_results(analyzer)
        analysis: dict = {"unused_functions": [], "removable_items": []}
        DeadCodeDetector._process_unused_functions(analysis, result)
        assert not analysis["unused_functions"]


# ---------------------------------------------------------------------------
# DeadCodeDetector._process_unused_classes


class TestProcessUnusedClasses:
    def test_marks_class_not_in_used_names(self) -> None:
        collector = UsageDataCollector()
        collector.classes = [{"name": "Orphan", "line": 3}]
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.used_names = set()
        result = collector.get_results(analyzer)
        result["unused_classes"] = collector.classes
        analysis: dict = {"unused_classes": [], "removable_items": []}
        DeadCodeDetector._process_unused_classes(analysis, result)
        assert any(c["name"] == "Orphan" for c in analysis["unused_classes"])

    def test_skips_when_no_unused_classes_key(self) -> None:
        analysis: dict = {"unused_classes": [], "removable_items": []}
        DeadCodeDetector._process_unused_classes(analysis, {})
        assert not analysis["unused_classes"]

    def test_skips_class_in_used_names(self) -> None:
        collector = UsageDataCollector()
        collector.classes = [{"name": "Active", "line": 1}]
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.used_names = {"Active"}
        result = collector.get_results(analyzer)
        result["unused_classes"] = collector.classes
        analysis: dict = {"unused_classes": [], "removable_items": []}
        DeadCodeDetector._process_unused_classes(analysis, result)
        assert not analysis["unused_classes"]


# ---------------------------------------------------------------------------
# DeadCodeDetector._detect_unreachable_code


class TestDetectUnreachableCode:
    def test_detects_code_after_return(self) -> None:
        src = """
def foo():
    return 1
    x = 2
"""
        tree = ast.parse(src)
        analysis: dict = {"unreachable_code": [], "removable_items": []}
        DeadCodeDetector._detect_unreachable_code(analysis, tree, src)
        assert len(analysis["unreachable_code"]) == 1
        assert analysis["unreachable_code"][0]["function"] == "foo"

    def test_detects_code_after_raise(self) -> None:
        src = """
def bar():
    raise ValueError("oops")
    return None
"""
        tree = ast.parse(src)
        analysis: dict = {"unreachable_code": [], "removable_items": []}
        DeadCodeDetector._detect_unreachable_code(analysis, tree, src)
        assert len(analysis["unreachable_code"]) == 1
        assert "unreachable code" in analysis["removable_items"][0]

    def test_no_unreachable_code_in_clean_function(self) -> None:
        src = """
def baz(x):
    if x:
        return x
    return 0
"""
        tree = ast.parse(src)
        analysis: dict = {"unreachable_code": [], "removable_items": []}
        DeadCodeDetector._detect_unreachable_code(analysis, tree, src)
        assert not analysis["unreachable_code"]

    def test_detects_unreachable_in_async_function(self) -> None:
        src = """
async def async_foo():
    return 42
    print("never")
"""
        tree = ast.parse(src)
        analysis: dict = {"unreachable_code": [], "removable_items": []}
        DeadCodeDetector._detect_unreachable_code(analysis, tree, src)
        assert len(analysis["unreachable_code"]) == 1
        assert analysis["unreachable_code"][0]["function"] == "async_foo"


# ---------------------------------------------------------------------------
# DeadCodeDetector._detect_redundant_code


class TestDetectRedundantCode:
    def test_detects_empty_except_block(self) -> None:
        src = """
try:
    pass
except:
    pass
"""
        tree = ast.parse(src)
        analysis: dict = {"removable_items": []}
        DeadCodeDetector._detect_redundant_code(analysis, tree, src)
        assert any("empty_except" in item for item in analysis["removable_items"])

    def test_detects_if_true(self) -> None:
        src = "if True:\n    x = 1\n"
        tree = ast.parse(src)
        analysis: dict = {"removable_items": []}
        DeadCodeDetector._detect_redundant_code(analysis, tree, src)
        assert any("if_true" in item for item in analysis["removable_items"])

    def test_detects_if_false(self) -> None:
        src = "if False:\n    x = 1\n"
        tree = ast.parse(src)
        analysis: dict = {"removable_items": []}
        DeadCodeDetector._detect_redundant_code(analysis, tree, src)
        assert any("if_false" in item for item in analysis["removable_items"])

    def test_detects_duplicate_lines(self) -> None:
        src = "x = 1\nx = 1\n"
        tree = ast.parse(src)
        analysis: dict = {"removable_items": []}
        DeadCodeDetector._detect_redundant_code(analysis, tree, src)
        assert any("duplicate" in item for item in analysis["removable_items"])

    def test_no_false_positive_on_clean_code(self) -> None:
        src = "x = 1\ny = 2\n"
        tree = ast.parse(src)
        analysis: dict = {"removable_items": []}
        DeadCodeDetector._detect_redundant_code(analysis, tree, src)
        assert not analysis["removable_items"]


# ---------------------------------------------------------------------------
# DeadCodeDetector.analyze_dead_code (integration)


class TestAnalyzeDeadCode:
    def test_full_analysis_with_unused_import(self, detector: DeadCodeDetector) -> None:
        src = "import os\n\nx = 1\n"
        tree = ast.parse(src)
        result = detector.analyze_dead_code(tree, src)
        assert "unused_imports" in result
        assert "unused_variables" in result
        assert "unused_functions" in result
        assert "unused_classes" in result
        assert "unreachable_code" in result
        assert "removable_items" in result

    def test_detects_unused_import_in_full_analysis(
        self, detector: DeadCodeDetector
    ) -> None:
        src = "import re\n\nx = 42\n"
        tree = ast.parse(src)
        result = detector.analyze_dead_code(tree, src)
        unused_import_names = [i["name"] for i in result["unused_imports"]]
        assert "re" in unused_import_names

    def test_clean_code_has_no_removable_items(
        self, detector: DeadCodeDetector
    ) -> None:
        src = "import os\n\npath = os.path.join('a', 'b')\n"
        tree = ast.parse(src)
        result = detector.analyze_dead_code(tree, src)
        assert result["unreachable_code"] == []


# ---------------------------------------------------------------------------
# DeadCodeDetector.find_lines_to_remove


class TestFindLinesToRemove:
    def test_returns_index_of_unused_import_line(
        self, detector: DeadCodeDetector
    ) -> None:
        lines = ["import os", "x = 1"]
        analysis = {
            "unused_imports": [{"name": "os", "line": 1, "type": "import"}],
        }
        result = detector.find_lines_to_remove(lines, analysis)
        assert 0 in result

    def test_ignores_out_of_range_line_index(
        self, detector: DeadCodeDetector
    ) -> None:
        lines = ["x = 1"]
        analysis = {
            "unused_imports": [{"name": "os", "line": 99, "type": "import"}],
        }
        result = detector.find_lines_to_remove(lines, analysis)
        assert not result


# ---------------------------------------------------------------------------
# DeadCodeDetector._should_remove_import_line


class TestShouldRemoveImportLine:
    def test_plain_import_match(self) -> None:
        assert DeadCodeDetector._should_remove_import_line(
            "import os", {"name": "os", "type": "import"}
        )

    def test_plain_import_no_match(self) -> None:
        assert not DeadCodeDetector._should_remove_import_line(
            "import sys", {"name": "os", "type": "import"}
        )

    def test_from_import_match(self) -> None:
        assert DeadCodeDetector._should_remove_import_line(
            "from pathlib import Path", {"name": "Path", "type": "from_import"}
        )

    def test_from_import_middle_no_match(self) -> None:
        # "Path" appears mid-line; line does NOT end with "Path"
        assert not DeadCodeDetector._should_remove_import_line(
            "from pathlib import Path, PurePath, os",
            {"name": "Path", "type": "from_import"},
        )

    def test_unknown_type_returns_false(self) -> None:
        assert not DeadCodeDetector._should_remove_import_line(
            "import os", {"name": "os", "type": "unknown"}
        )


# ---------------------------------------------------------------------------
# DeadCodeDetector._find_unreachable_lines


class TestFindUnreachableLines:
    def test_returns_index_for_unreachable_line(self) -> None:
        lines = ["def f():", "    return 1", "    x = 2"]
        analysis = {"unreachable_code": [{"line": 3}]}
        result = DeadCodeDetector._find_unreachable_lines(lines, analysis)
        assert 2 in result

    def test_skips_missing_line_key(self) -> None:
        lines = ["x = 1"]
        analysis = {"unreachable_code": [{}]}
        result = DeadCodeDetector._find_unreachable_lines(lines, analysis)
        assert not result

    def test_empty_unreachable_code(self) -> None:
        lines = ["x = 1"]
        analysis = {"unreachable_code": []}
        result = DeadCodeDetector._find_unreachable_lines(lines, analysis)
        assert not result


# ---------------------------------------------------------------------------
# DeadCodeDetector._find_redundant_lines


class TestFindRedundantLines:
    def test_finds_empty_pass_after_except(self) -> None:
        lines = ["try:", "    pass", "except:", "    pass"]
        analysis: dict = {}
        result = DeadCodeDetector._find_redundant_lines(lines, analysis)
        assert 3 in result

    def test_no_redundant_lines_in_clean_code(self) -> None:
        lines = ["x = 1", "y = 2"]
        analysis: dict = {}
        result = DeadCodeDetector._find_redundant_lines(lines, analysis)
        assert not result


# ---------------------------------------------------------------------------
# DeadCodeDetector._is_empty_except_block


class TestIsEmptyExceptBlock:
    def test_bare_except(self) -> None:
        lines = ["except:"]
        assert DeadCodeDetector._is_empty_except_block(lines, 0)

    def test_typed_except(self) -> None:
        lines = ["except ValueError:"]
        assert DeadCodeDetector._is_empty_except_block(lines, 0)

    def test_non_except_line(self) -> None:
        lines = ["x = 1"]
        assert not DeadCodeDetector._is_empty_except_block(lines, 0)


# ---------------------------------------------------------------------------
# DeadCodeDetector._find_empty_pass_line


class TestFindEmptyPassLine:
    def test_finds_pass_immediately_after_except(self) -> None:
        lines = ["except:", "    pass"]
        result = DeadCodeDetector._find_empty_pass_line(lines, 0)
        assert result == 1

    def test_skips_blank_lines_to_find_pass(self) -> None:
        lines = ["except:", "", "    pass"]
        result = DeadCodeDetector._find_empty_pass_line(lines, 0)
        assert result == 2

    def test_returns_none_when_no_pass(self) -> None:
        lines = ["except:", "    raise ValueError()"]
        result = DeadCodeDetector._find_empty_pass_line(lines, 0)
        assert result is None

    def test_returns_none_at_end_of_file(self) -> None:
        lines = ["except:"]
        result = DeadCodeDetector._find_empty_pass_line(lines, 0)
        assert result is None
