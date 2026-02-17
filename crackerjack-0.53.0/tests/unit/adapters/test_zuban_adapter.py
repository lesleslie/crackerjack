"""Tests for ZubanAdapter."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from crackerjack.adapters.lsp.zuban import ZubanAdapter, TypeIssue


@pytest.fixture
def mock_execution_context():
    """Provide mock ExecutionContext for testing."""
    context = MagicMock()
    context.root_path = Path("/test/path")
    context.settings = MagicMock()
    return context


@pytest.fixture
def zuban_adapter(mock_execution_context):
    """Provide ZubanAdapter for testing."""
    adapter = ZubanAdapter(
        context=mock_execution_context,
        strict_mode=True,
        mypy_compatibility=True,
        use_lsp=False,  # Disable LSP for unit tests
    )
    return adapter


class TestZubanAdapterProperties:
    """Test suite for ZubanAdapter properties."""

    def test_get_tool_name(self, zuban_adapter):
        """Test get_tool_name method."""
        assert zuban_adapter.get_tool_name() == "zuban"

    def test_initialization(self, mock_execution_context):
        """Test adapter initialization."""
        adapter = ZubanAdapter(
            context=mock_execution_context,
            strict_mode=True,
            mypy_compatibility=True,
            use_lsp=True,
        )

        assert adapter.strict_mode is True
        assert adapter.mypy_compatibility is True
        assert adapter.use_lsp is True
        assert adapter._lsp_client is None
        assert adapter._lsp_wrapper is None


class TestCheckToolHealth:
    """Test suite for check_tool_health method."""

    def test_check_tool_health_success(self, zuban_adapter):
        """Test tool health check when tool is available."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0

            result = zuban_adapter.check_tool_health()
            assert result is True

    def test_check_tool_health_version_fails(self, zuban_adapter):
        """Test tool health check when --version fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # --help
                MagicMock(returncode=1),  # --version
            ]

            result = zuban_adapter.check_tool_health()
            assert result is False

    def test_check_tool_health_not_available(self, zuban_adapter):
        """Test tool health check when tool is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1

            result = zuban_adapter.check_tool_health()
            assert result is False


class TestSupportsJsonOutput:
    """Test suite for supports_json_output method."""

    def test_supports_json_output(self, zuban_adapter):
        """Test that Zuban doesn't support JSON output."""
        assert zuban_adapter.supports_json_output() is False


class TestGetCommandArgs:
    """Test suite for get_command_args method."""

    def test_get_command_args_mypy_compat(self, zuban_adapter, tmp_path):
        """Test command args with mypy compatibility."""
        test_file = tmp_path / "test.py"

        args = zuban_adapter.get_command_args([test_file])

        assert "uv" in args
        assert "run" in args
        assert "zuban" in args
        assert "mypy" in args
        assert "--strict" in args
        assert "--show-error-codes" in args
        assert str(test_file) in args

    def test_get_command_args_no_mypy_compat(self, mock_execution_context):
        """Test command args without mypy compatibility."""
        adapter = ZubanAdapter(
            context=mock_execution_context,
            mypy_compatibility=False,
        )

        args = adapter.get_command_args([])

        assert "mypy" not in args
        assert "check" in args

    def test_get_command_args_no_strict_mode(self, mock_execution_context):
        """Test command args without strict mode."""
        adapter = ZubanAdapter(
            context=mock_execution_context,
            strict_mode=False,
        )

        args = adapter.get_command_args([])

        assert "--strict" not in args

    def test_get_command_args_no_files(self, zuban_adapter):
        """Test command args with no files uses current directory."""
        args = zuban_adapter.get_command_args([])

        assert "." in args


class TestParseOutput:
    """Test suite for parse_output method."""

    def test_parse_text_output_empty(self, zuban_adapter):
        """Test parsing empty output."""
        result = zuban_adapter.parse_output("")
        assert result.success is True
        assert len(result.issues) == 0

    def test_parse_text_line(self, zuban_adapter):
        """Test parsing a single text line."""
        line = "test.py:10:5: error: Name 'undefined' is not defined  [name-defined]"

        issue = zuban_adapter._parse_text_line(line)

        assert issue is not None
        assert issue.file_path == Path("test.py")
        assert issue.line_number == 10
        assert issue.column == 5
        assert "not defined" in issue.message
        assert issue.severity == "error"
        assert issue.error_code == "name-defined"

    def test_parse_text_line_without_column(self, zuban_adapter):
        """Test parsing line without column number."""
        line = "test.py:10: error: Name 'undefined' not defined"

        issue = zuban_adapter._parse_text_line(line)

        assert issue is not None
        assert issue.line_number == 10
        assert issue.column == 1

    def test_extract_line_components(self, zuban_adapter):
        """Test extracting line components."""
        line = "test.py:10:5: error: message"

        result = zuban_adapter._extract_line_components(line)

        assert result is not None
        file_path, line_number, message_part = result
        assert file_path == Path("test.py")
        assert line_number == 10
        assert "error: message" in message_part

    def test_extract_line_components_invalid(self, zuban_adapter):
        """Test extracting from invalid line."""
        result = zuban_adapter._extract_line_components("invalid line")
        assert result is None

    def test_extract_column_number(self, zuban_adapter):
        """Test extracting column number."""
        result = zuban_adapter._extract_column_number("5: error: message")
        assert result == 5

    def test_extract_column_number_not_a_number(self, zuban_adapter):
        """Test column number extraction when not numeric."""
        result = zuban_adapter._extract_column_number("error: message")
        assert result == 1

    def test_extract_severity_and_message(self, zuban_adapter):
        """Test extracting severity and message."""
        test_cases = [
            ("error: something went wrong", ("error", "something went wrong")),
            ("warning: be careful", ("warning", "be careful")),
            ("note: additional info", ("note", "additional info")),
            ("info: for your information", ("info", "for your information")),
            ("plain message", ("error", "plain message")),
        ]

        for input_msg, expected in test_cases:
            result = zuban_adapter._extract_severity_and_message(input_msg)
            assert result == expected

    def test_extract_error_code(self, zuban_adapter):
        """Test extracting error code."""
        result = zuban_adapter._extract_error_code("message [error-code]")
        assert result == "error-code"

    def test_extract_error_code_none(self, zuban_adapter):
        """Test error code extraction when none present."""
        result = zuban_adapter._extract_error_code("just a message")
        assert result is None

    def test_normalize_severity(self, zuban_adapter):
        """Test severity normalization."""
        assert zuban_adapter._normalize_severity("error") == "error"
        assert zuban_adapter._normalize_severity("warning") == "warning"
        assert zuban_adapter._normalize_severity("note") == "info"
        assert zuban_adapter._normalize_severity("info") == "info"
        assert zuban_adapter._normalize_severity("unknown") == "error"


class TestCheckWithLspOrFallback:
    """Test suite for check_with_lsp_or_fallback method."""

    @pytest.mark.asyncio
    async def test_check_tool_not_healthy(self, zuban_adapter):
        """Test when tool health check fails."""
        with patch.object(zuban_adapter, 'check_tool_health', return_value=False):
            result = await zuban_adapter.check_with_lsp_or_fallback([Path("test.py")])
            assert result.success is False
            assert "not functional" in result.raw_output

    @pytest.mark.asyncio
    async def test_check_with_cli_fallback(self, zuban_adapter):
        """Test CLI fallback when LSP disabled."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            result = await zuban_adapter.check_with_lsp_or_fallback([Path("test.py")])

            assert result is not None
            assert hasattr(result, '_execution_mode')
            assert result._execution_mode == "cli"


class TestMapLspSeverity:
    """Test suite for _map_lsp_severity method."""

    def test_map_lsp_severity(self, zuban_adapter):
        """Test LSP severity mapping."""
        assert zuban_adapter._map_lsp_severity(1) == "error"
        assert zuban_adapter._map_lsp_severity(2) == "warning"
        assert zuban_adapter._map_lsp_severity(3) == "info"
        assert zuban_adapter._map_lsp_severity(4) == "info"
        assert zuban_adapter._map_lsp_severity(99) == "error"


class TestTypeIssue:
    """Test suite for TypeIssue dataclass."""

    def test_type_issue_creation(self):
        """Test creating TypeIssue."""
        issue = TypeIssue(
            file_path=Path("test.py"),
            line_number=10,
            column=5,
            message="Type error",
            severity="error",
            error_code="E001",
        )

        assert issue.file_path == Path("test.py")
        assert issue.line_number == 10
        assert issue.column == 5
        assert issue.message == "Type error"
        assert issue.severity == "error"
        assert issue.error_code == "E001"

    def test_type_issue_to_dict(self):
        """Test TypeIssue to_dict method."""
        issue = TypeIssue(
            file_path=Path("test.py"),
            line_number=10,
            column=5,
            message="Type error",
            severity="error",
            error_code="E001",
        )

        result = issue.to_dict()

        assert result["file_path"] == "test.py"
        assert result["line_number"] == 10
        assert result["column"] == 5
        assert result["message"] == "Type error"
        assert result["severity"] == "error"
        assert result["error_code"] == "E001"
