"""Tests for Pyscn SAST adapter."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult, ToolIssue
from crackerjack.adapters.sast.pyscn import PyscnAdapter, PyscnSettings
from crackerjack.models.qa_results import QACheckType


class TestPyscnAdapter:
    """Test cases for PyscnAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """Test basic initialization of PyscnAdapter."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            assert adapter.settings is None

            await adapter.init()
            assert adapter.settings is not None
            assert isinstance(adapter.settings, PyscnSettings)
            assert adapter.tool_name == "pyscn"
            assert adapter.adapter_name == "Pyscn (Security Analysis)"

    @pytest.mark.asyncio
    async def test_initialization_with_custom_settings(self) -> None:
        """Test initialization with custom settings."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            settings = PyscnSettings(
                max_complexity=20,
                severity_threshold="medium",
                confidence_threshold="medium",
            )
            adapter = PyscnAdapter(settings=settings)
            await adapter.init()

            assert adapter.settings.max_complexity == 20
            assert adapter.settings.severity_threshold == "medium"
            assert adapter.settings.confidence_threshold == "medium"

    @pytest.mark.asyncio
    async def test_build_command_basic(self) -> None:
        """Test building a basic pyscn command."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            settings = PyscnSettings()
            adapter = PyscnAdapter(settings=settings)
            await adapter.init()

            files = [Path("file1.py"), Path("file2.py")]
            command = adapter.build_command(files)

            expected = ["pyscn", "check", "--max-complexity", "15"]
            expected.extend([str(f) for f in files])

            assert command == expected

    @pytest.mark.asyncio
    async def test_build_command_with_options(self) -> None:
        """Test building a pyscn command with various options."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            settings = PyscnSettings(
                max_complexity=25,
            )
            adapter = PyscnAdapter(settings=settings)
            await adapter.init()

            files = [Path("src/")]
            command = adapter.build_command(files)

            assert "pyscn" in command
            assert "check" in command
            assert "--max-complexity" in command
            assert "25" in command
            assert str(files[0]) in command

    @pytest.mark.asyncio
    async def test_build_command_raises_without_settings(self) -> None:
        """Test build_command raises RuntimeError without settings."""
        adapter = PyscnAdapter()
        # No init called, settings is None
        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([Path("file.py")])

    @pytest.mark.asyncio
    async def test_parse_text_output_single_issue(self) -> None:
        """Test parsing a single issue from text output."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

        text_output = "test.py:10:5: error: Function 'test_func' is too complex (complexity 25)"
        issues = adapter._parse_text_output(text_output)

        assert len(issues) == 1
        issue = issues[0]
        assert issue.file_path == Path("test.py")
        assert issue.line_number == 10
        assert issue.column_number == 5
        assert "complex" in issue.message.lower()
        assert issue.severity == "error"

    @pytest.mark.asyncio
    async def test_parse_text_output_multiple_issues(self) -> None:
        """Test parsing multiple issues from text output."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

        text_output = """test1.py:10:5: error: Function 'func1' is too complex (complexity 20)
test2.py:20:3: warning: Function 'func2' is too complex (complexity 16)
test3.py:30:1: error: Function 'func3' is too complex (complexity 25)"""

        issues = adapter._parse_text_output(text_output)

        assert len(issues) == 3
        assert issues[0].file_path == Path("test1.py")
        assert issues[0].line_number == 10
        assert issues[0].column_number == 5
        assert issues[0].severity == "error"

        assert issues[1].file_path == Path("test2.py")
        assert issues[1].line_number == 20
        assert issues[1].column_number == 3
        assert issues[1].severity == "warning"

    @pytest.mark.asyncio
    async def test_parse_text_output_ignores_clone_warnings(self) -> None:
        """Test that clone warnings are ignored."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

        text_output = """test.py:10:5: error: Function 'func' is too complex
test.py:15:3: warning: clone of 'func' detected
⚠️ Some other warning
test.py:20:1: error: Another complex function"""

        issues = adapter._parse_text_output(text_output)

        # Should only get the complex function issues, not the clone or emoji warnings
        assert all("clone" not in issue.message.lower() for issue in issues)
        assert all("⚠️" not in issue.message for issue in issues)

    @pytest.mark.asyncio
    async def test_parse_text_output_invalid_lines(self) -> None:
        """Test parsing with invalid line formats."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

        text_output = """not a valid line
also not valid
test.py:10:5: error: Function 'func' is too complex
"""

        issues = adapter._parse_text_output(text_output)

        assert len(issues) == 1

    @pytest.mark.asyncio
    async def test_parse_output_empty(self) -> None:
        """Test parsing empty output."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

        result = ToolExecutionResult(
            success=True,
            raw_output="",
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )
        issues = await adapter.parse_output(result)

        assert issues == []

    @pytest.mark.asyncio
    async def test_parse_output_with_text(self) -> None:
        """Test parse_output with text output."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

        text_output = "test.py:10:5: error: Function 'func' is too complex (complexity 25)"

        result = ToolExecutionResult(
            success=True,
            raw_output=text_output,
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")

    def test_get_check_type(self) -> None:
        """Test _get_check_type returns SAST."""
        adapter = PyscnAdapter()
        assert adapter._get_check_type() == QACheckType.SAST

    def test_get_default_config(self) -> None:
        """Test getting default configuration."""
        adapter = PyscnAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "Pyscn (Security Analysis)"
        assert config.check_type == QACheckType.SAST
        assert config.enabled is False  # Disabled by default
        assert config.file_patterns == ["**/*.py"]
        assert "**/.venv/**" in config.exclude_patterns
        assert "**/tests/**" in config.exclude_patterns
        assert config.stage == "comprehensive"
        assert config.timeout_seconds == 120

    def test_module_id_matches_constant(self) -> None:
        """Test module_id is correct UUID."""
        from crackerjack.adapters.sast.pyscn import MODULE_ID

        adapter = PyscnAdapter()
        assert adapter.module_id == MODULE_ID


class TestPyscnSettings:
    """Test suite for PyscnSettings."""

    def test_default_settings(self) -> None:
        """Test PyscnSettings default values."""
        settings = PyscnSettings()
        assert settings.tool_name == "pyscn"
        assert settings.use_json_output is False
        assert settings.severity_threshold == "low"
        assert settings.confidence_threshold == "low"
        assert settings.max_complexity == 15
        assert settings.exclude_rules == []
        assert settings.include_rules == []
        assert settings.recursive is True
        assert settings.max_depth is None

    def test_custom_settings(self) -> None:
        """Test PyscnSettings with custom values."""
        settings = PyscnSettings(
            severity_threshold="medium",
            confidence_threshold="high",
            max_complexity=20,
            exclude_rules=["B101"],
            include_rules=["B102"],
            recursive=False,
            max_depth=10,
        )
        assert settings.severity_threshold == "medium"
        assert settings.confidence_threshold == "high"
        assert settings.max_complexity == 20
        assert settings.exclude_rules == ["B101"]
        assert settings.include_rules == ["B102"]
        assert settings.recursive is False
        assert settings.max_depth == 10

    def test_exclude_rules_default_list(self) -> None:
        """Test exclude_rules default is a list."""
        settings = PyscnSettings()
        assert isinstance(settings.exclude_rules, list)
        assert len(settings.exclude_rules) == 0

    def test_include_rules_default_list(self) -> None:
        """Test include_rules default is a list."""
        settings = PyscnSettings()
        assert isinstance(settings.include_rules, list)
        assert len(settings.include_rules) == 0


class TestPyscnAdapterProtocol:
    """Test SASTAdapter protocol compliance."""

    @pytest.mark.asyncio
    async def test_adapter_implements_protocol(self) -> None:
        """Test that PyscnAdapter implements SASTAdapterProtocol."""
        from crackerjack.adapters.sast._base import SASTAdapterProtocol

        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

        # Protocol checks
        assert hasattr(adapter, "adapter_name")
        assert hasattr(adapter, "module_id")
        assert hasattr(adapter, "tool_name")
        assert hasattr(adapter, "init")
        assert hasattr(adapter, "build_command")
        assert hasattr(adapter, "check")
        assert hasattr(adapter, "parse_output")
        assert hasattr(adapter, "_get_check_type")
        assert hasattr(adapter, "get_default_config")


class TestPyscnTextParsing:
    """Test suite for text parsing helpers."""

    def test_parse_text_line_valid(self) -> None:
        """Test _parse_text_line with valid input."""
        adapter = PyscnAdapter()

        line = "test.py:10:5: error: Function 'test_func' is too complex"
        issue = adapter._parse_text_line(line)

        assert issue is not None
        assert issue.file_path == Path("test.py")
        assert issue.line_number == 10
        assert issue.column_number == 5
        assert issue.severity == "error"

    def test_parse_text_line_warning(self) -> None:
        """Test _parse_text_line with warning severity."""
        adapter = PyscnAdapter()

        line = "test.py:10:5: warning: Some warning message"
        issue = adapter._parse_text_line(line)

        assert issue is not None
        assert issue.severity == "warning"

    def test_parse_text_line_invalid(self) -> None:
        """Test _parse_text_line with invalid input."""
        adapter = PyscnAdapter()

        # Too few parts
        line = "invalid:line"
        issue = adapter._parse_text_line(line)

        assert issue is None

    def test_parse_text_line_no_colon(self) -> None:
        """Test _parse_text_line with no colon separator."""
        adapter = PyscnAdapter()

        line = "no colon in this line"
        issue = adapter._parse_text_line(line)

        assert issue is None

    def test_parse_severity_error(self) -> None:
        """Test _parse_severity returns error for non-warning."""
        adapter = PyscnAdapter()

        severity = adapter._parse_severity("error: some message", "some message")
        assert severity == "error"

    def test_parse_severity_warning(self) -> None:
        """Test _parse_severity returns warning for warning prefix."""
        adapter = PyscnAdapter()

        severity = adapter._parse_severity("warning: some message", "some message")
        assert severity == "warning"

    def test_extract_message_with_message(self) -> None:
        """Test _extract_message uses message when provided."""
        adapter = PyscnAdapter()

        message = adapter._extract_message("error: prefix", "actual message", "error")
        assert message == "actual message"

    def test_extract_message_without_message(self) -> None:
        """Test _extract_message extracts from severity string when no message."""
        adapter = PyscnAdapter()

        # severity_and_message doesn't start with severity, so it returns as-is
        message = adapter._extract_message("prefix", "", "error")
        assert message == "prefix"

    def test_extract_message_empty_both(self) -> None:
        """Test _extract_message returns severity string when both empty."""
        adapter = PyscnAdapter()

        # severity_and_message doesn't start with severity, returns as-is
        message = adapter._extract_message("some text", "", "error")
        assert message == "some text"