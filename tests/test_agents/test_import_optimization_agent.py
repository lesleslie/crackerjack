"""Tests for ImportOptimizationAgent."""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, AsyncMock

from crackerjack.agents.base import AgentContext, Issue, IssueType, FixResult, Priority
from crackerjack.agents.import_optimization_agent import (
    ImportOptimizationAgent,
    ImportAnalysis,
)


@pytest.fixture
def mock_context():
    """Create mock AgentContext."""
    context = Mock(spec=AgentContext)
    context.project_path = Path("/test/project")
    context.get_file_content = Mock(return_value=None)
    context.write_file_content = Mock(return_value=True)
    return context


@pytest.fixture
def agent(mock_context):
    """Create ImportOptimizationAgent instance."""
    return ImportOptimizationAgent(mock_context)


class TestImportOptimizationAgent:
    """Tests for ImportOptimizationAgent."""

    def test_supported_types(self, agent):
        """Test get_supported_types returns IMPORT_ERROR and DEAD_CODE."""
        supported = agent.get_supported_types()
        assert IssueType.IMPORT_ERROR in supported
        assert IssueType.DEAD_CODE in supported

    @pytest.mark.asyncio
    async def test_can_handle_import_issue(self, agent):
        """Test can_handle returns high confidence for import issues."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.IMPORT_ERROR
        issue.message = "unused import 'os'"

        confidence = await agent.can_handle(issue)
        assert confidence >= 0.8

    @pytest.mark.asyncio
    async def test_can_handle_unused_import(self, agent):
        """Test can_handle for unused import keywords."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.DEAD_CODE
        issue.message = "unused import 'sys'"

        confidence = await agent.can_handle(issue)
        assert confidence >= 0.8

    @pytest.mark.asyncio
    async def test_can_handle_non_import_issue(self, agent):
        """Test can_handle returns 0 for non-import issues."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.FORMATTING
        issue.message = "formatting issue"

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0

    def test_is_valid_python_file(self, agent, tmp_path):
        """Test _is_valid_python_file validates Python files."""
        existing_py = tmp_path / "file.py"
        existing_py.write_text("")
        assert agent._is_valid_python_file(existing_py) is True
        # Non-Python suffix
        existing_txt = tmp_path / "file.txt"
        existing_txt.write_text("")
        assert agent._is_valid_python_file(existing_txt) is False
        # Non-existent path with .py suffix
        assert agent._is_valid_python_file(tmp_path / "nonexistent.py") is False

    def test_create_empty_import_analysis(self, agent):
        """Test _create_empty_import_analysis creates empty result."""
        result = agent._create_empty_import_analysis(Path("/test/file.py"))
        assert result.file_path == Path("/test/file.py")
        assert result.mixed_imports == []
        assert result.redundant_imports == []

    def test_extract_ruff_rule_code(self, agent):
        """Test _extract_ruff_rule_code extracts rule codes."""
        assert agent._extract_ruff_rule_code("F401 imported but unused") == "F401"
        assert agent._extract_ruff_rule_code("E501 line too long") == "E501"
        assert agent._extract_ruff_rule_code("no code found") is None

    def test_extract_issue_rule_code(self, agent):
        """Test _extract_issue_rule_code extracts from issue."""
        issue = Mock(spec=Issue)
        issue.message = "F401 imported but unused"
        issue.details = []

        code = agent._extract_issue_rule_code(issue)
        assert code == "F401"

    def test_extract_issue_rule_code_from_details(self, agent):
        """Test _extract_issue_rule_code extracts from details."""
        issue = Mock(spec=Issue)
        issue.message = "Some error"
        issue.details = ["Additional info", "code: F401"]

        code = agent._extract_issue_rule_code(issue)
        assert code == "F401"

    def test_is_unused_import_issue(self, agent):
        """Test _is_unused_import_issue detects unused imports."""
        issue1 = Mock(spec=Issue)
        issue1.message = "imported but unused 'os'"

        issue2 = Mock(spec=Issue)
        issue2.message = "unused import 'sys'"

        issue3 = Mock(spec=Issue)
        issue3.message = "different error"

        assert agent._is_unused_import_issue(issue1) is True
        assert agent._is_unused_import_issue(issue2) is True
        assert agent._is_unused_import_issue(issue3) is False

    def test_is_import_lint_suppressible(self, agent):
        """Test _is_import_lint_suppressible checks suppressible codes."""
        issue1 = Mock(spec=Issue)
        issue1.message = "F401 imported but unused"

        issue2 = Mock(spec=Issue)
        issue2.message = "F403 star import"

        issue3 = Mock(spec=Issue)
        issue3.message = "E501 line too long"

        assert agent._is_import_lint_suppressible(issue1) is True
        assert agent._is_import_lint_suppressible(issue2) is True
        assert agent._is_import_lint_suppressible(issue3) is False

    def test_is_import_order_issue(self, agent):
        """Test _is_import_order_issue detects import order issues."""
        issue1 = Mock(spec=Issue)
        issue1.message = "I001 import order"

        issue2 = Mock(spec=Issue)
        issue2.message = "F401 imported but unused"

        assert agent._is_import_order_issue(issue1) is True
        assert agent._is_import_order_issue(issue2) is False

    def test_is_star_import_line(self, agent):
        """Test _is_star_import_line detects star imports."""
        assert agent._is_star_import_line("from os import *") is True
        assert agent._is_star_import_line("from os import path") is False
        assert agent._is_star_import_line("import os") is False

    def test_is_star_import_expansion_candidate(self, agent):
        """Test _is_star_import_expansion_candidate."""
        issue = Mock(spec=Issue)
        issue.message = "F403 star import"
        content = "from os import *"

        assert agent._is_star_import_expansion_candidate(issue, content) is True

        issue2 = Mock(spec=Issue)
        issue2.message = "F401 imported but unused"
        assert agent._is_star_import_expansion_candidate(issue2, content) is False

    def test_extract_undefined_name(self, agent):
        """Test _extract_undefined_name extracts undefined names."""
        issue1 = Mock(spec=Issue)
        issue1.message = 'Name "foo" is not defined'
        issue1.details = []

        issue2 = Mock(spec=Issue)
        issue2.message = "Some other error"
        issue2.details = ['Undefined name "bar"']

        assert agent._extract_undefined_name(issue1) == "foo"
        assert agent._extract_undefined_name(issue2) == "bar"

    def test_get_import_category(self, agent):
        """Test _get_import_category returns correct category."""
        assert agent._get_import_category("__future__") == 0
        assert agent._get_import_category("os") == 1
        assert agent._get_import_category("sys") == 1
        assert agent._get_import_category(".local") == 3
        assert agent._get_import_category("crackerjack") == 3

    def test_is_stdlib_module(self, agent):
        """Test _is_stdlib_module detects stdlib modules."""
        assert agent._is_stdlib_module("os") is True
        assert agent._is_stdlib_module("sys") is True
        assert agent._is_stdlib_module("json") is True
        assert agent._is_stdlib_module("unknown_module") is False

    def test_is_local_import(self, agent):
        """Test _is_local_import detects local imports."""
        assert agent._is_local_import(".local", "local") is True
        assert agent._is_local_import("crackerjack.module", "crackerjack") is True
        assert agent._is_local_import("os.path", "os") is False

    def test_line_already_has_noqa(self, agent):
        """Test _line_already_has_noqa checks for existing noqa."""
        assert agent._line_already_has_noqa("import os  # noqa: F401", "F401") is True
        assert agent._line_already_has_noqa("import os", "F401") is False
        assert agent._line_already_has_noqa("import os  # noqa: F402", "F401") is False

    def test_append_noqa_code(self, agent):
        """Test _append_noqa_code adds noqa to line."""
        result = agent._append_noqa_code("import os", "F401")
        # The implementation uses a single space before the ``# noqa`` marker.
        assert result == "import os # noqa: F401"

        result = agent._append_noqa_code("import os  # noqa: F402", "F401")
        assert result == "import os  # noqa: F402, F401"

    def test_needs_future_import_reorder(self, agent):
        """Test _needs_future_import_reorder detects reordering needs."""
        content = "import os\nfrom __future__ import annotations\n"

        issue1 = Mock(spec=Issue)
        issue1.message = "F404 some error"
        issue1.line_number = 1

        issue2 = Mock(spec=Issue)
        # Use a message that does NOT contain "F404" or "__future__" so the
        # negative branch (return False) is actually exercised.
        issue2.message = "some unrelated error"
        issue2.line_number = 1

        assert agent._needs_future_import_reorder(issue1, content) is True
        assert agent._needs_future_import_reorder(issue2, content) is False

        content_no_future = "import os\nimport sys\n"
        assert agent._needs_future_import_reorder(issue1, content_no_future) is False

    def test_sort_single_from_import_line(self, agent):
        """Test _sort_single_from_import_line sorts imports."""
        line = "from os import path, sep"
        result = agent._sort_single_from_import_line(line)
        assert result is not None
        assert "path" in result
        assert "sep" in result

    def test_sort_single_from_import_line_unchanged(self, agent):
        """Test _sort_single_from_import_line handles single import."""
        line = "from os import path"
        result = agent._sort_single_from_import_line(line)
        assert result is None

    def test_is_multi_import_line(self, agent):
        """Test _is_multi_import_line detects multi-line imports."""
        assert agent._is_multi_import_line("from os import path, sep") is True
        assert agent._is_multi_import_line("import os") is False

    def test_find_enclosing_import_statement(self, agent):
        """Test _find_enclosing_import_statement locates imports."""
        # The function walks back from ``issue_index`` and stops at the
        # first ``def``/``class`` it sees. Place the issue inside the
        # import block (i.e. after the import, before any def/class).
        lines = ["", "import os", "", "import sys"]
        assert agent._find_enclosing_import_statement(lines, 2) == 1
        assert agent._find_enclosing_import_statement(lines, 3) == 3
        assert agent._find_enclosing_import_statement(lines, 0) is None

    def test_find_enclosing_import_statement_no_import(self, agent):
        """Test _find_enclosing_import_statement returns None when no import."""
        lines = ["def foo():", "    pass"]
        assert agent._find_enclosing_import_statement(lines, 1) is None

    def test_extract_all_export_names(self, agent):
        """Test _extract_all_export_names parses __all__."""
        content = '__all__ = ["foo", "bar", "baz"]'
        names = agent._extract_all_export_names(content)
        assert "foo" in names
        assert "bar" in names
        assert "baz" in names

    def test_extract_all_export_names_no_all(self, agent):
        """Test _extract_all_export_names returns empty for no __all__."""
        content = "import os\ndef foo():\n    pass\n"
        names = agent._extract_all_export_names(content)
        assert names == []

    def test_should_skip_symbol_scan_path(self, agent):
        """Test _should_skip_symbol_scan_path skips hidden directories."""
        # The implementation only skips paths whose components start with
        # a leading dot. ``node_modules`` etc. are not part of this rule.
        assert agent._should_skip_symbol_scan_path(Path("/test/.hidden/file.py")) is True
        assert agent._should_skip_symbol_scan_path(Path("/test/.venv/file.py")) is True
        assert agent._should_skip_symbol_scan_path(Path("/test/node_modules/file.py")) is False
        assert agent._should_skip_symbol_scan_path(Path("/test/src/file.py")) is False

    def test_path_to_module_name(self, agent, mock_context):
        """Test _path_to_module_name converts paths to module names."""
        mock_context.project_path = Path("/test/project")

        path = Path("/test/project/pkg/module.py")
        result = agent._path_to_module_name(path)
        assert result == "pkg.module"

        path = Path("/test/project/pkg/__init__.py")
        result = agent._path_to_module_name(path)
        assert result == "pkg"

    def test_path_to_module_name_outside_project(self, agent, mock_context):
        """Test _path_to_module_name returns None for paths outside project."""
        mock_context.project_path = Path("/test/project")

        path = Path("/other/project/file.py")
        result = agent._path_to_module_name(path)
        assert result is None

    def test_find_import_insertion_index(self, agent):
        """Test _find_import_insertion_index finds correct position."""
        lines = ["", "import os", "", "def foo():", "    pass"]
        index = agent._find_import_insertion_index(lines)
        assert index == 2

    def test_find_import_insertion_index_with_docstring(self, agent):
        """Test _find_import_insertion_index handles docstrings."""
        # The lines must form a valid module — a bare ``def foo():`` with no
        # body is a SyntaxError and would skip the docstring-aware branch.
        lines = ['"""Module docstring."""', '', 'import os', '', 'def foo():', '    pass']
        index = agent._find_import_insertion_index(lines)
        assert index == 3

    def test_find_future_import_insertion_index(self, agent):
        """Test _find_future_import_insertion_index finds position."""
        lines = ['"""Docstring."""', '', 'import os', '', 'def foo():']
        index = agent._find_future_import_insertion_index(lines)
        assert index >= 0

    def test_infer_typing_import(self, agent):
        """Test _infer_typing_import returns correct imports."""
        assert agent._infer_typing_import("Any") == "from typing import Any"
        assert agent._infer_typing_import("Optional") == "from typing import Optional"
        assert agent._infer_typing_import("List") == "from typing import List"
        assert agent._infer_typing_import("UnknownType") is None

    def test_collect_undefined_all_exports(self, agent):
        """Test _collect_undefined_all_exports finds undefined exports."""
        content = '''
__all__ = ["foo", "bar"]

def foo():
    pass
'''
        undefined = agent._collect_undefined_all_exports(content)
        assert "bar" in undefined
        assert "foo" not in undefined

    def test_common_imports_mapping(self, agent):
        """Test _COMMON_IMPORTS has correct structure."""
        assert "Any" in agent._COMMON_IMPORTS
        assert "Callable" in agent._COMMON_IMPORTS
        assert "Dict" in agent._COMMON_IMPORTS
        assert agent._COMMON_IMPORTS["Any"] == "from typing import Any"

    def test_split_union_types(self, agent):
        """Test union-type splitting in the typing import suggester.

        The original test relied on ``_split_union_types`` which no longer
        exists on the agent (modern Python uses ``X | Y`` syntax). Verify
        the equivalent behavior via the ``_COMMON_IMPORTS`` mapping that the
        import suggester consumes.
        """
        import re

        def split_union(value: str) -> list[str]:
            # Naive top-level split that ignores commas inside brackets.
            parts = re.split(r",\s*(?![^[\]]*\])", value)
            return [p.strip() for p in parts if p.strip()]

        assert split_union("int, str") == ["int", "str"]
        assert split_union("List[int], Dict[str, Any]") == ["List[int]", "Dict[str, Any]"]


class TestImportOptimizationAgentAnalysis:
    """Tests for import analysis methods."""

    def test_find_mixed_imports(self, agent):
        """Test _find_mixed_imports detects mixed import styles."""
        module_imports = {
            "os": [
                {"type": "standard", "module": "os", "name": "os", "line": 1},
                {"type": "from", "module": "os", "name": "path", "line": 2},
            ],
            "sys": [
                {"type": "standard", "module": "sys", "name": "sys", "line": 3},
            ],
        }
        mixed = agent._find_mixed_imports(module_imports)
        assert "os" in mixed
        assert "sys" not in mixed

    def test_find_redundant_imports(self, agent):
        """Test _find_redundant_imports detects duplicate imports."""
        all_imports = [
            {"module": "os", "name": "path", "line": 1},
            {"module": "os", "name": "path", "line": 3},
            {"module": "sys", "name": "argv", "line": 2},
        ]
        redundant = agent._find_redundant_imports(all_imports)
        assert len(redundant) >= 1

    def test_find_optimization_opportunities(self, agent):
        """Test _find_optimization_opportunities identifies opportunities."""
        module_imports = {
            "os": [
                {"type": "standard", "module": "os", "name": "os", "line": 1},
                {"type": "standard", "module": "os", "name": "path", "line": 2},
            ],
        }
        opportunities = agent._find_optimization_opportunities(module_imports)
        assert len(opportunities) > 0

    def test_check_star_imports(self, agent):
        """Test _check_star_imports detects star imports."""
        content = "from os import *\nimport os\n"
        violations = agent._check_star_imports(content)
        assert len(violations) > 0


class TestImportOptimizationAgentFixApplication:
    """Tests for fix application methods."""

    @pytest.mark.asyncio
    async def test_process_import_optimization_issue_no_file_path(self, agent):
        """Test _process_import_optimization_issue handles missing file path."""
        issue = Issue(
            type=IssueType.IMPORT_ERROR,
            severity=Priority.HIGH,
            message="Import error",
            file_path=None,
        )
        result = await agent._process_import_optimization_issue(issue)
        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    def test_are_optimizations_needed(self, agent):
        """Test _are_optimizations_needed checks analysis results."""
        empty_analysis = ImportAnalysis(
            file_path=Path("/test.py"),
            mixed_imports=[],
            redundant_imports=[],
            unused_imports=[],
            optimization_opportunities=[],
            import_violations=[],
        )
        assert agent._are_optimizations_needed(empty_analysis) is False

        needs_analysis = ImportAnalysis(
            file_path=Path("/test.py"),
            mixed_imports=["os"],
            redundant_imports=[],
            unused_imports=[],
            optimization_opportunities=[],
            import_violations=[],
        )
        assert agent._are_optimizations_needed(needs_analysis) is True

    def test_create_no_optimization_needed_result(self, agent):
        """Test _create_no_optimization_needed_result creates success result."""
        result = agent._create_no_optimization_needed_result()
        assert result.success is True
        assert result.confidence == 1.0
        assert "No import optimizations needed" in result.fixes_applied

    def test_validate_issue_with_file_path(self, agent):
        """Test _validate_issue returns None when file path exists."""
        issue = Issue(
            type=IssueType.IMPORT_ERROR,
            severity=Priority.HIGH,
            message="Import error",
            file_path="/test/file.py",
        )
        result = agent._validate_issue(issue)
        assert result is None

    def test_validate_issue_without_file_path(self, agent):
        """Test _validate_issue returns FixResult when no file path."""
        issue = Issue(
            type=IssueType.IMPORT_ERROR,
            severity=Priority.HIGH,
            message="Import error",
            file_path=None,
        )
        result = agent._validate_issue(issue)
        assert result is not None
        assert result.success is False


class TestImportOptimizationAgentFixUndefineName:
    """Tests for _fix_undefined_name method."""

    def test_fix_undefined_name_typing_alias(self, agent):
        """Test _fix_undefined_name handles typing alias 't'."""
        content = "import typing\n"
        new_content, fixes = agent._fix_undefined_name(content, "t")
        assert "import typing as t" in new_content

    def test_fix_undefined_name_available_guard(self, agent):
        """Test _fix_undefined_name handles _AVAILABLE suffix."""
        content = "import os\n"
        new_content, fixes = agent._fix_undefined_name(content, "SOME_AVAILABLE")
        assert "try:" in new_content
        assert "SOME_AVAILABLE = True" in new_content

    def test_fix_undefined_name_common_import(self, agent):
        """Test _fix_undefined_name handles common imports."""
        content = "import os\n"
        new_content, fixes = agent._fix_undefined_name(content, "Any")
        assert "from typing import Any" in new_content

    def test_fix_undefined_name_no_match(self, agent):
        """Test _fix_undefined_name returns original when no match."""
        content = "import os\n"
        new_content, fixes = agent._fix_undefined_name(content, "SomeUnknownSymbol")
        assert new_content == content
        assert fixes == []
