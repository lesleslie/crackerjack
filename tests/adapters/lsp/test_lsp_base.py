"""Tests for LSP adapter base classes and data classes."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from crackerjack.adapters.lsp._base import (
    BaseRustToolAdapter,
    Issue,
    RustToolAdapter,
    ToolResult,
)


class TestIssueDataclass:
    """Test Issue dataclass."""

    def test_issue_creation(self):
        """Test Issue creation with required fields."""
        issue = Issue(
            file_path=Path("test.py"),
            line_number=10,
            message="Test error",
        )
        assert issue.file_path == Path("test.py")
        assert issue.line_number == 10
        assert issue.message == "Test error"
        assert issue.severity == "error"

    def test_issue_with_all_fields(self):
        """Test Issue creation with all optional fields."""
        issue = Issue(
            file_path=Path("src/main.py"),
            line_number=42,
            message="Type error",
            severity="warning",
        )
        assert issue.severity == "warning"

    def test_issue_to_dict(self):
        """Test Issue.to_dict() method."""
        issue = Issue(
            file_path=Path("test.py"),
            line_number=10,
            message="Test error",
            severity="error",
        )
        d = issue.to_dict()
        assert d["file_path"] == "test.py"
        assert d["line_number"] == 10
        assert d["message"] == "Test error"
        assert d["severity"] == "error"


class TestToolResultDataclass:
    """Test ToolResult dataclass."""

    def test_tool_result_success(self):
        """Test ToolResult with success=True."""
        result = ToolResult(success=True, issues=[])
        assert result.success is True
        assert result.issues == []
        assert result.error is None
        assert result.raw_output == ""

    def test_tool_result_with_issues(self):
        """Test ToolResult with issues."""
        issues = [
            Issue(file_path=Path("a.py"), line_number=1, message="err1"),
            Issue(file_path=Path("b.py"), line_number=2, message="err2"),
        ]
        result = ToolResult(success=False, issues=issues)
        assert len(result.issues) == 2
        assert result.has_errors is True
        assert result.error_count == 2
        assert result.warning_count == 0

    def test_tool_result_error_count(self):
        """Test ToolResult.error_count property."""
        issues = [
            Issue(file_path=Path("a.py"), line_number=1, message="err", severity="error"),
            Issue(file_path=Path("b.py"), line_number=2, message="warn", severity="warning"),
            Issue(file_path=Path("c.py"), line_number=3, message="err2", severity="error"),
        ]
        result = ToolResult(success=False, issues=issues)
        assert result.error_count == 2

    def test_tool_result_warning_count(self):
        """Test ToolResult.warning_count property."""
        issues = [
            Issue(file_path=Path("a.py"), line_number=1, message="err", severity="error"),
            Issue(file_path=Path("b.py"), line_number=2, message="warn", severity="warning"),
            Issue(file_path=Path("c.py"), line_number=3, message="warn2", severity="warning"),
        ]
        result = ToolResult(success=False, issues=issues)
        assert result.warning_count == 2

    def test_tool_result_to_dict(self):
        """Test ToolResult.to_dict() method."""
        issues = [Issue(file_path=Path("test.py"), line_number=1, message="err")]
        result = ToolResult(
            success=False,
            issues=issues,
            error=None,
            raw_output="raw output",
            execution_time=1.5,
            tool_version="1.0.0",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert len(d["issues"]) == 1
        assert d["error_count"] == 1
        assert d["warning_count"] == 0
        assert d["execution_time"] == 1.5
        assert d["tool_version"] == "1.0.0"

    def test_tool_result_execution_mode(self):
        """Test ToolResult._execution_mode attribute."""
        result = ToolResult(success=True)
        result._execution_mode = "lsp"
        assert result._execution_mode == "lsp"


class TestRustToolAdapterProtocol:
    """Test RustToolAdapter Protocol."""

    def test_protocol_exists(self):
        """Test RustToolAdapter Protocol is defined."""
        assert hasattr(RustToolAdapter, "__init__")
        assert hasattr(RustToolAdapter, "get_command_args")
        assert hasattr(RustToolAdapter, "parse_output")
        assert hasattr(RustToolAdapter, "supports_json_output")
        assert hasattr(RustToolAdapter, "get_tool_version")
        assert hasattr(RustToolAdapter, "validate_tool_available")


class ConcreteRustAdapter(BaseRustToolAdapter):
    """Concrete implementation for testing."""

    def get_command_args(self, target_files):
        return ["test_tool"]

    def parse_output(self, output):
        return ToolResult(success=True)

    def supports_json_output(self):
        return False

    def get_tool_name(self):
        return "test_tool"


class TestBaseRustToolAdapter:
    """Test BaseRustToolAdapter abstract class."""

    def test_initialization(self):
        """Test adapter initialization with mock context."""
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        assert adapter.context == mock_context
        assert adapter._tool_version is None

    def test_get_tool_name_abstract(self):
        """Test get_tool_name is abstract method."""
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        assert adapter.get_tool_name() == "test_tool"

    def test_get_tool_version_cached(self):
        """Test get_tool_version returns cached value."""
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        adapter._tool_version = "cached_version"
        assert adapter.get_tool_version() == "cached_version"

    @patch("subprocess.run")
    def test_validate_tool_available_success(self, mock_run):
        """Test validate_tool_available returns True when tool exists."""
        mock_run.return_value.returncode = 0
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        result = adapter.validate_tool_available()
        assert result is True

    @patch("subprocess.run")
    def test_validate_tool_available_failure(self, mock_run):
        """Test validate_tool_available returns False when tool not found."""
        mock_run.return_value.returncode = 1
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        result = adapter.validate_tool_available()
        assert result is False

    @patch("subprocess.run")
    def test_fetch_tool_version(self, mock_run):
        """Test _fetch_tool_version subprocess call."""
        mock_run.return_value.stdout = "version 1.2.3\nsecond line"
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        version = adapter._fetch_tool_version()
        assert version == "version 1.2.3"

    @patch("subprocess.run")
    def test_fetch_tool_version_not_found(self, mock_run):
        """Test _fetch_tool_version returns None on error."""
        mock_run.side_effect = FileNotFoundError()
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        version = adapter._fetch_tool_version()
        assert version is None

    def test_should_use_json_output_ai_agent_mode(self):
        """Test _should_use_json_output when ai_agent_mode is True."""
        mock_context = Mock()
        mock_context.ai_agent_mode = True
        mock_context.ai_debug_mode = False
        adapter = ConcreteRustAdapter(mock_context)
        assert adapter._should_use_json_output() is True

    def test_should_use_json_output_ai_debug_mode(self):
        """Test _should_use_json_output when ai_debug_mode is True."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = True
        adapter = ConcreteRustAdapter(mock_context)
        assert adapter._should_use_json_output() is True

    def test_should_use_json_output_both_false(self):
        """Test _should_use_json_output when both modes are False."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        adapter = ConcreteRustAdapter(mock_context)
        assert adapter._should_use_json_output() is False

    def test_parse_json_output_safe_valid(self):
        """Test _parse_json_output_safe with valid JSON."""
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        result = adapter._parse_json_output_safe('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_output_safe_invalid(self):
        """Test _parse_json_output_safe with invalid JSON."""
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        result = adapter._parse_json_output_safe("not json")
        assert result is None

    def test_create_error_result(self):
        """Test _create_error_result method."""
        mock_context = Mock()
        adapter = ConcreteRustAdapter(mock_context)
        result = adapter._create_error_result("Error message", "raw output")
        assert result.success is False
        assert result.error == "Error message"
        assert result.raw_output == "raw output"