"""Tests for DeadCodeRemovalAgent."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, AsyncMock

from crackerjack.agents.base import AgentContext, Issue, IssueType, FixResult, Priority
from crackerjack.agents.dead_code_removal_agent import DeadCodeRemovalAgent, DeadCodeInfo


@pytest.fixture
def mock_context():
    """Create mock AgentContext."""
    context = Mock(spec=AgentContext)
    context.project_path = Path("/test/project")
    context.get_file_content = Mock()
    context.write_file_content = Mock(return_value=True)
    return context


@pytest.fixture
def agent(mock_context):
    """Create DeadCodeRemovalAgent instance."""
    return DeadCodeRemovalAgent(mock_context)


class TestDeadCodeRemovalAgent:
    """Tests for DeadCodeRemovalAgent."""

    def test_supported_types(self, agent):
        """Test get_supported_types returns DEAD_CODE."""
        assert agent.get_supported_types() == {IssueType.DEAD_CODE}

    @pytest.mark.asyncio
    async def test_can_handle_dead_code_issue(self, agent):
        """Test can_handle returns high confidence for dead code issues."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.DEAD_CODE
        issue.message = "Unused function 'foo' at line 10 (80% confidence)"
        issue.line_number = 10

        confidence = await agent.can_handle(issue)
        assert confidence >= 0.7

    @pytest.mark.asyncio
    async def test_can_handle_non_dead_code_issue(self, agent):
        """Test can_handle returns 0 for non-dead code issues."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.TYPE_ERROR
        issue.message = "Some type error"
        issue.line_number = None

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_can_handle_no_message(self, agent):
        """Test can_handle returns 0 for issue with no message."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.DEAD_CODE
        issue.message = ""
        issue.line_number = 1

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0

    def test_extract_confidence_from_message(self, agent):
        """Test _extract_confidence extracts percentage confidence."""
        assert agent._extract_confidence("80% confidence") == 0.80
        assert agent._extract_confidence("90% confidence") == 0.90

    def test_extract_confidence_certainty_words(self, agent):
        """Test _extract_confidence uses certainty words."""
        assert agent._extract_confidence("definitely unused") == 0.95
        assert agent._extract_confidence("certainly dead") == 0.95
        assert agent._extract_confidence("likely unused") == 0.75
        assert agent._extract_confidence("probably dead") == 0.75
        assert agent._extract_confidence("possibly unused") == 0.50
        assert agent._extract_confidence("might be dead") == 0.50

    def test_is_test_file(self, agent):
        """Test _is_test_file detects test files."""
        assert agent._is_test_file(Path("tests/test_foo.py")) is True
        assert agent._is_test_file(Path("test_foo.py")) is True
        assert agent._is_test_file(Path("foo_test.py")) is True
        assert agent._is_test_file(Path("conftest.py")) is True
        assert agent._is_test_file(Path("src/foo.py")) is False
        assert agent._is_test_file(Path("lib/bar.py")) is False

    def test_parse_dead_code_issue_skylos_format(self, agent):
        """Test _parse_dead_code_issue_enhanced handles skylos format."""
        issue = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused function 'foo' at line 10",
            line_number=10,
        )
        content = "def foo():\n    pass\n"

        result = agent._parse_dead_code_issue_enhanced(issue, content)
        assert result is not None
        assert result.code_type == "function"
        assert result.name == "foo"
        assert result.line_number == 10

    def test_parse_dead_code_issue_vulture_format(self, agent):
        """Test _parse_dead_code_issue_enhanced handles vulture format."""
        issue = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused function 'bar' at line 5",
            line_number=5,
        )
        content = "def bar():\n    pass\n"

        result = agent._parse_dead_code_issue_enhanced(issue, content)
        assert result is not None
        assert result.code_type == "function"
        assert result.name == "bar"
        assert result.line_number == 5

    def test_find_block_end_function(self, agent):
        """Test _find_block_end locates function boundaries."""
        content = """
def foo():
    x = 1
    y = 2
    return x + y

def bar():
    pass
"""
        lines = content.split("\n")
        result = agent._find_block_end(lines, 2, "function")
        assert result == 5

    def test_find_block_end_class(self, agent):
        """Test _find_block_end locates class boundaries."""
        content = """
class Foo:
    def __init__(self):
        pass

    def method(self):
        pass
"""
        lines = content.split("\n")
        result = agent._find_block_end(lines, 2, "class")
        assert result is not None

    def test_get_decorators(self, agent):
        """Test _get_decorators extracts decorators above a line."""
        content = """
@property
@pytest.fixture
def foo():
    pass
"""
        decorators = agent._get_decorators(content, 4)
        assert "@property" in decorators
        assert "@pytest.fixture" in decorators

    def test_has_docstring(self, agent):
        """Test _has_docstring detects docstrings."""
        content = '''
def foo():
    """This is a docstring."""
    pass
'''
        assert agent._has_docstring(content, 1) is True

    def test_has_docstring_no_docstring(self, agent):
        """Test _has_docstring returns False when no docstring."""
        content = """
def foo():
    pass
"""
        assert agent._has_docstring(content, 1) is False

    def test_is_exported_in_all(self, agent):
        """Test _is_exported detects __all__ exports."""
        content = '''
__all__ = ["foo", "bar"]
'''
        assert agent._is_exported(content, "foo") is True
        assert agent._is_exported(content, "baz") is False

    def test_analyze_usage_dynamic_usage(self, agent):
        """Test _analyze_usage detects dynamic usage patterns."""
        content = """
class Foo:
    pass

getattr(sys, "Foo")
"""
        dead_code = DeadCodeInfo(
            code_type="class",
            name="Foo",
            line_number=1,
            confidence=0.8,
        )
        result = agent._analyze_usage(content, dead_code)
        assert result["has_dynamic_usage"] is True

    def test_perform_safety_checks_protected_decorator(self, agent):
        """Test _perform_safety_checks_enhanced blocks protected decorators."""
        dead_code = DeadCodeInfo(
            code_type="function",
            name="foo",
            line_number=1,
            confidence=0.8,
            decorators=["@property"],
        )
        content = """
@property
def foo():
    pass
"""
        result = agent._perform_safety_checks_enhanced(content, dead_code)
        assert result["safe_to_remove"] is False
        assert "Has protected decorator: @property" in result["reasons"]

    def test_perform_safety_checks_exported(self, agent):
        """Test _perform_safety_checks_enhanced blocks exported items."""
        dead_code = DeadCodeInfo(
            code_type="function",
            name="foo",
            line_number=1,
            confidence=0.8,
        )
        content = '''
__all__ = ["foo"]

def foo():
    pass
'''
        result = agent._perform_safety_checks_enhanced(content, dead_code)
        assert result["safe_to_remove"] is False
        assert any("exported in __all__" in r for r in result["reasons"])

    def test_remove_import_line_enhanced(self, agent):
        """Test _remove_import_line_enhanced handles import removal."""
        lines = ["import os", "import sys", "from foo import bar"]
        new_lines, fix = agent._remove_import_line_enhanced(lines, "os", 1)
        assert "import os" not in new_lines
        assert fix == "Removed import: os"

    def test_remove_function_enhanced(self, agent):
        """Test _remove_function_enhanced removes function with decorators."""
        lines = [
            "@property",
            "def foo():",
            "    pass",
            "",
            "def bar():",
            "    pass",
        ]
        new_lines, fix = agent._remove_function_enhanced(lines, 2, 3, ["@property"])
        assert "def foo" not in "\n".join(new_lines)
        assert "def bar" in "\n".join(new_lines)

    def test_remove_class_enhanced(self, agent):
        """Test _remove_class_enhanced removes class."""
        lines = [
            "class Foo:",
            "    def __init__(self):",
            "        pass",
            "",
            "def bar():",
            "    pass",
        ]
        new_lines, fix = agent._remove_class_enhanced(lines, 1, 3, None)
        assert "class Foo" not in "\n".join(new_lines)

    def test_remove_variable_enhanced(self, agent):
        """Test _remove_variable_enhanced removes variable."""
        lines = ["x = 1", "y = 2", "z = 3"]
        new_lines, fix = agent._remove_variable_enhanced(lines, 1, "x")
        assert len(new_lines) == 2
        assert "x = 1" not in new_lines

    def test_extract_undefined_export_names(self, agent):
        """Test _extract_undefined_export_names parses __all__ issues."""
        message = 'Undefined name "foo" in __all__'
        names = agent._extract_undefined_export_names(message)
        assert "foo" in names

    def test_remove_undefined_exports(self, agent):
        """Test _remove_undefined_exports removes from __all__."""
        content = '__all__ = ["foo", "bar", "baz"]'
        updated_content, removed = agent._remove_undefined_exports(content, ["foo", "bar"])
        assert "foo" not in updated_content
        assert "bar" not in updated_content
        assert "baz" in updated_content
        assert "foo" in removed
        assert "bar" in removed

    def test_should_fix_export_list(self, agent):
        """Test _should_fix_export_list detects __all__ issues."""
        issue_with_all = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message='Undefined name "foo" in __all__',
        )
        issue_with_undefined = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="undefined name 'bar'",
        )
        assert agent._should_fix_export_list(issue_with_all) is True
        assert agent._should_fix_export_list(issue_with_undefined) is True

    def test_high_confidence_types(self, agent):
        """Test high confidence types get boosted."""
        dead_code = DeadCodeInfo(
            code_type="import",
            name="os",
            line_number=1,
            confidence=0.7,
        )
        content = "import os\n"
        result = agent._perform_safety_checks_enhanced(content, dead_code)
        assert result["confidence"] >= 0.85


class TestDeadCodeInfo:
    """Tests for DeadCodeInfo dataclass."""

    def test_dead_code_info_creation(self):
        """Test DeadCodeInfo can be created with required fields."""
        info = DeadCodeInfo(
            code_type="function",
            name="foo",
            line_number=10,
            confidence=0.8,
        )
        assert info.code_type == "function"
        assert info.name == "foo"
        assert info.line_number == 10
        assert info.confidence == 0.8
        assert info.end_line is None
        assert info.decorators is None

    def test_dead_code_info_full(self):
        """Test DeadCodeInfo with all fields."""
        info = DeadCodeInfo(
            code_type="class",
            name="Foo",
            line_number=5,
            confidence=0.9,
            end_line=10,
            decorators=["@property", "@staticmethod"],
        )
        assert info.end_line == 10
        assert len(info.decorators) == 2