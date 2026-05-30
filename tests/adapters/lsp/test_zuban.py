"""Tests for ZubanAdapter type checking."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from crackerjack.adapters.lsp.zuban import (
    TypeIssue,
    ZubanAdapter,
)


class TestTypeIssue:
    """Test TypeIssue dataclass."""

    def test_type_issue_creation(self):
        """Test TypeIssue creation."""
        issue = TypeIssue(
            file_path=Path("test.py"),
            line_number=10,
            message="Type error",
        )
        assert issue.severity == "error"
        assert issue.column == 1
        assert issue.error_code is None

    def test_type_issue_with_all_fields(self):
        """Test TypeIssue with all fields."""
        issue = TypeIssue(
            file_path=Path("main.py"),
            line_number=42,
            message="Incompatible types",
            severity="warning",
            column=5,
            error_code="assignment",
        )
        assert issue.severity == "warning"
        assert issue.column == 5
        assert issue.error_code == "assignment"

    def test_type_issue_to_dict(self):
        """Test TypeIssue.to_dict() method."""
        issue = TypeIssue(
            file_path=Path("test.py"),
            line_number=10,
            message="Type error",
            column=8,
            error_code="type-error",
        )
        d = issue.to_dict()
        assert d["file_path"] == "test.py"
        assert d["column"] == 8
        assert d["error_code"] == "type-error"


class TestZubanAdapter:
    """Test ZubanAdapter."""

    def test_initialization_defaults(self):
        """Test adapter initialization with defaults."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        assert adapter.get_tool_name() == "zuban"
        assert adapter.strict_mode is True
        assert adapter.mypy_compatibility is True
        assert adapter.use_lsp is True
        assert adapter._lsp_client is None
        assert adapter._lsp_available is False

    def test_initialization_custom(self):
        """Test adapter initialization with custom values."""
        mock_context = Mock()
        adapter = ZubanAdapter(
            context=mock_context,
            strict_mode=False,
            mypy_compatibility=False,
            use_lsp=False,
        )

        assert adapter.strict_mode is False
        assert adapter.mypy_compatibility is False
        assert adapter.use_lsp is False

    def test_supports_json_output(self):
        """Test supports_json_output returns False."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)
        assert adapter.supports_json_output() is False

    def test_check_tool_health_success(self):
        """Test check_tool_health returns True when tool works."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = adapter.check_tool_health()
            assert result is True

    def test_check_tool_health_failure(self):
        """Test check_tool_health returns False when tool fails."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            result = adapter.check_tool_health()
            assert result is False

    def test_check_tool_health_exception(self):
        """Test check_tool_health returns False on exception."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Tool not found")
            result = adapter.check_tool_health()
            assert result is False

    def test_ensure_lsp_client_no_lsp(self):
        """Test _ensure_lsp_client when LSP disabled."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context, use_lsp=False)

        adapter._ensure_lsp_client()

        assert adapter._lsp_client is None

    def test_ensure_lsp_client_import_error(self):
        """Test _ensure_lsp_client handles ImportError."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context, use_lsp=True)

        with patch.dict("sys.modules", {"crackerjack.services.lsp_client": None}):
            with patch("builtins.__import__", side_effect=ImportError()):
                adapter._ensure_lsp_client()

        assert adapter._lsp_available is False

    @pytest.mark.asyncio
    async def test_get_lsp_diagnostics_no_client(self):
        """Test get_lsp_diagnostics when client not available."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context, use_lsp=False)

        result = await adapter.get_lsp_diagnostics([Path("test.py")])

        assert result == []

    @pytest.mark.asyncio
    async def test_get_lsp_diagnostics_with_client(self):
        """Test get_lsp_diagnostics with LSP client."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context, use_lsp=True)

        mock_lsp_client = Mock()
        mock_lsp_client.is_server_running.return_value = True
        mock_lsp_client.check_project_with_feedback.return_value = (
            {
                "test.py": [
                    {"line": 10, "column": 5, "message": "Type error", "severity": "error", "code": "E001"}
                ]
            },
            {},
        )
        adapter._lsp_client = mock_lsp_client
        adapter._lsp_available = True

        result = await adapter.get_lsp_diagnostics([Path("test.py")])

        assert len(result) == 1
        assert result[0].message == "Type error"

    @pytest.mark.asyncio
    async def test_get_lsp_diagnostics_exception_handling(self):
        """Test get_lsp_diagnostics handles exceptions."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context, use_lsp=True)

        mock_lsp_client = Mock()
        mock_lsp_client.is_server_running.return_value = True
        mock_lsp_client.check_project_with_feedback.side_effect = Exception("LSP error")
        adapter._lsp_client = mock_lsp_client
        adapter._lsp_available = True

        result = await adapter.get_lsp_diagnostics([Path("test.py")])

        assert result == []
        assert adapter._lsp_available is False

    def test_get_command_args_mypy_mode(self):
        """Test get_command_args in mypy compatibility mode."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = ZubanAdapter(mock_context, mypy_compatibility=True)

        args = adapter.get_command_args([Path("src/main.py")])

        assert "uv" in args
        assert "run" in args
        assert "zuban" in args
        assert "mypy" in args
        assert "--strict" in args
        assert "--show-error-codes" in args
        assert "src/main.py" in args

    def test_get_command_args_check_mode(self):
        """Test get_command_args in check mode."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = ZubanAdapter(mock_context, mypy_compatibility=False)

        args = adapter.get_command_args([Path("src/main.py")])

        assert "check" in args
        assert "--strict" not in args

    def test_get_command_args_no_files(self):
        """Test get_command_args with no target files."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = ZubanAdapter(mock_context)

        args = adapter.get_command_args([])

        assert "." in args

    def test_map_lsp_severity(self):
        """Test _map_lsp_severity maps correctly."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        assert adapter._map_lsp_severity(1) == "error"
        assert adapter._map_lsp_severity(2) == "warning"
        assert adapter._map_lsp_severity(3) == "info"
        assert adapter._map_lsp_severity(4) == "info"
        assert adapter._map_lsp_severity(99) == "error"

    def test_create_type_issue_from_diagnostic(self):
        """Test _create_type_issue_from_diagnostic."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        diag = {
            "uri": "file:///src/main.py",
            "range": {"start": {"line": 9, "character": 4}},
            "message": "Type error",
            "severity": 1,
            "code": "E001",
        }

        issue = adapter._create_type_issue_from_diagnostic(diag, Path("src/main.py"))

        assert issue.file_path == Path("src/main.py")
        assert issue.line_number == 10
        assert issue.column == 5
        assert issue.message == "Type error"
        assert issue.severity == "error"
        assert issue.error_code == "E001"

    @pytest.mark.asyncio
    async def test_check_with_lsp_or_fallback_health_check_fails(self):
        """Test check_with_lsp_or_fallback when health check fails."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        with patch.object(adapter, "check_tool_health", return_value=False):
            result = await adapter.check_with_lsp_or_fallback([Path("test.py")])

            assert result.success is False
            assert "TOML parsing bug" in result.raw_output

    @pytest.mark.asyncio
    async def test_run_cli_fallback(self):
        """Test _run_cli_fallback executes subprocess."""
        mock_context = Mock()
        mock_context.root_path = "/test"
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        adapter = ZubanAdapter(mock_context)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""

            with patch.object(adapter, "parse_output") as mock_parse:
                mock_parse.return_value = Mock()
                result = await adapter._run_cli_fallback([Path("test.py")])

                mock_parse.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_cli_fallback_timeout(self):
        """Test _run_cli_fallback handles timeout."""
        mock_context = Mock()
        mock_context.root_path = "/test"
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        adapter = ZubanAdapter(mock_context)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = TimeoutError()

            result = await adapter._run_cli_fallback([Path("test.py")])

            assert result.success is False
            assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_run_cli_fallback_exception(self):
        """Test _run_cli_fallback handles exceptions."""
        mock_context = Mock()
        mock_context.root_path = "/test"
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        adapter = ZubanAdapter(mock_context)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Unknown error")

            result = await adapter._run_cli_fallback([Path("test.py")])

            assert result.success is False
            assert "failed" in result.error

    def test_parse_output_text_mode(self):
        """Test parse_output falls back to text mode."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        adapter = ZubanAdapter(mock_context)

        with patch.object(adapter, "_should_use_json_output", return_value=False):
            with patch.object(adapter, "_parse_text_output") as mock_text:
                mock_text.return_value = Mock()
                adapter.parse_output("some output")
                mock_text.assert_called_once_with("some output")

    def test_parse_json_output_valid(self):
        """Test _parse_json_output with valid JSON."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        adapter = ZubanAdapter(mock_context)

        json_data = {
            "diagnostics": [
                {"file": "src/main.py", "line": 10, "column": 5, "message": "Type error", "severity": "error", "code": "E001"}
            ]
        }
        output = json.dumps(json_data)

        result = adapter._parse_json_output(output)

        assert result.success is False
        assert len(result.issues) == 1

    def test_parse_json_output_invalid(self):
        """Test _parse_json_output with invalid JSON."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        adapter = ZubanAdapter(mock_context)

        result = adapter._parse_json_output("not valid json")

        assert result.success is False
        assert result.error is not None

    def test_parse_text_output_empty(self):
        """Test _parse_text_output with empty output."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        adapter = ZubanAdapter(mock_context)

        result = adapter._parse_text_output("")

        assert result.success is True
        assert len(result.issues) == 0

    def test_parse_text_line_valid(self):
        """Test _parse_text_line with valid line."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        adapter = ZubanAdapter(mock_context)

        line = "src/main.py:10:5: error: Type error [E001]"
        issue = adapter._parse_text_line(line)

        assert issue is not None
        assert issue.file_path == Path("src/main.py")
        assert issue.line_number == 10

    def test_parse_text_line_invalid(self):
        """Test _parse_text_line with invalid line."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        adapter = ZubanAdapter(mock_context)

        issue = adapter._parse_text_line("invalid line")
        assert issue is None

    def test_extract_line_components_valid(self):
        """Test _extract_line_components with valid line."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        result = adapter._extract_line_components("src/main.py:10:5: error: message")
        assert result is not None
        assert result[0] == Path("src/main.py")
        assert result[1] == 10

    def test_extract_line_components_no_colon(self):
        """Test _extract_line_components with no colon."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        result = adapter._extract_line_components("invalid line")
        assert result is None

    def test_extract_column_number(self):
        """Test _extract_column_number."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        column = adapter._extract_column_number("5: error message")
        assert column == 5

    def test_extract_column_number_invalid(self):
        """Test _extract_column_number with invalid format."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        column = adapter._extract_column_number("invalid")
        assert column == 1

    def test_parse_message_content_with_code(self):
        """Test _parse_message_content extracts error code."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        result = adapter._parse_message_content("5: error: Type error [E001]")

        assert result["severity"] == "error"
        assert result["error_code"] == "E001"

    def test_parse_message_content_with_severity_indicator(self):
        """Test _parse_message_content with severity indicator."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        result = adapter._parse_message_content("warning: Missing return statement")

        assert result["severity"] == "warning"

    def test_extract_severity_and_message_error(self):
        """Test _extract_severity_and_message with error."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        severity, message = adapter._extract_severity_and_message("error: Something went wrong")

        assert severity == "error"
        assert message == "Something went wrong"

    def test_extract_severity_and_message_warning(self):
        """Test _extract_severity_and_message with warning."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        severity, message = adapter._extract_severity_and_message("warning: Be careful")

        assert severity == "warning"
        assert message == "Be careful"

    def test_extract_severity_and_message_no_indicator(self):
        """Test _extract_severity_and_message with no indicator."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        severity, message = adapter._extract_severity_and_message("Just a message")

        assert severity == "error"
        assert message == "Just a message"

    def test_extract_error_code_valid(self):
        """Test _extract_error_code with valid code."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        code = adapter._extract_error_code("Type error [E001]")
        assert code == "E001"

    def test_extract_error_code_invalid(self):
        """Test _extract_error_code with invalid format."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        code = adapter._extract_error_code("No code here")
        assert code is None

    def test_normalize_severity_error(self):
        """Test _normalize_severity converts to error."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        assert adapter._normalize_severity("error") == "error"
        assert adapter._normalize_severity("ERR") == "error"
        assert adapter._normalize_severity("invalid") == "error"

    def test_normalize_severity_warning(self):
        """Test _normalize_severity keeps warning."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        assert adapter._normalize_severity("warning") == "warning"

    def test_normalize_severity_info(self):
        """Test _normalize_severity converts note/info to info."""
        mock_context = Mock()
        adapter = ZubanAdapter(mock_context)

        assert adapter._normalize_severity("note") == "info"
        assert adapter._normalize_severity("info") == "info"
