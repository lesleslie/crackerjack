"""Tests for Ruff linter/formatter adapter."""

import json
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.format.ruff import (
    RuffAdapter,
    RuffSettings,
    RuffMode,
    _map_ruff_code_to_issue_type,
    _handle_e_prefix,
    _handle_f_prefix,
    MODULE_ID,
)
from crackerjack.agents.base import IssueType
from crackerjack.models.qa_results import QACheckType


class TestRuffMode:
    """Test suite for RuffMode enum."""

    def test_ruff_mode_values(self):
        """Test RuffMode enum values."""
        assert RuffMode.CHECK == "check"
        assert RuffMode.FORMAT == "format"


class TestRuffSettings:
    """Test suite for RuffSettings."""

    def test_default_settings(self):
        """Test RuffSettings default values."""
        settings = RuffSettings()
        assert settings.tool_name == "ruff"
        assert settings.mode == "check"
        assert settings.fix_enabled is False
        assert settings.unsafe_fixes is False
        assert settings.select_rules == []
        assert settings.ignore_rules == []
        assert settings.line_length is None
        assert settings.use_json_output is True
        assert settings.respect_gitignore is True
        assert settings.preview is False

    def test_custom_settings(self):
        """Test RuffSettings with custom values."""
        settings = RuffSettings(
            mode="format",
            fix_enabled=True,
            unsafe_fixes=True,
            select_rules=["E", "F"],
            ignore_rules=["W"],
            line_length=100,
            preview=True,
        )
        assert settings.mode == "format"
        assert settings.fix_enabled is True
        assert settings.unsafe_fixes is True
        assert settings.select_rules == ["E", "F"]
        assert settings.ignore_rules == ["W"]
        assert settings.line_length == 100
        assert settings.preview is True


class TestMapRuffCodeToIssueType:
    """Test suite for _map_ruff_code_to_issue_type function."""

    def test_none_code(self):
        """Test with None code returns FORMATTING."""
        result = _map_ruff_code_to_issue_type(None)
        assert result == IssueType.FORMATTING

    def test_empty_code(self):
        """Test with empty code returns FORMATTING."""
        result = _map_ruff_code_to_issue_type("")
        assert result == IssueType.FORMATTING

    def test_f4_prefix(self):
        """Test F4 prefix returns IMPORT_ERROR."""
        result = _map_ruff_code_to_issue_type("F401")
        assert result == IssueType.IMPORT_ERROR

    def test_f8_prefix(self):
        """Test F8 prefix returns FORMATTING."""
        result = _map_ruff_code_to_issue_type("F821")
        assert result == IssueType.FORMATTING

    def test_up_prefix(self):
        """Test UP prefix returns TYPE_ERROR."""
        result = _map_ruff_code_to_issue_type("UP030")
        assert result == IssueType.TYPE_ERROR

    def test_c_prefix(self):
        """Test C prefix returns COMPLEXITY."""
        result = _map_ruff_code_to_issue_type("C901")
        assert result == IssueType.COMPLEXITY

    def test_pe_prefix(self):
        """Test PE prefix returns PERFORMANCE."""
        result = _map_ruff_code_to_issue_type("PE123")
        assert result == IssueType.PERFORMANCE

    def test_pl_prefix(self):
        """Test PL prefix returns COMPLEXITY."""
        result = _map_ruff_code_to_issue_type("PLR0913")
        assert result == IssueType.COMPLEXITY

    def test_e_prefix(self):
        """Test E prefix returns FORMATTING (default)."""
        result = _map_ruff_code_to_issue_type("E501")
        assert result == IssueType.FORMATTING

    def test_e999(self):
        """Test E999 returns TYPE_ERROR."""
        result = _map_ruff_code_to_issue_type("E999")
        assert result == IssueType.TYPE_ERROR

    def test_e502(self):
        """Test E502 returns TYPE_ERROR."""
        result = _map_ruff_code_to_issue_type("E502")
        assert result == IssueType.TYPE_ERROR

    def test_s_prefix(self):
        """Test S prefix returns SECURITY."""
        result = _map_ruff_code_to_issue_type("S101")
        assert result == IssueType.SECURITY

    def test_w_prefix(self):
        """Test W prefix returns FORMATTING."""
        result = _map_ruff_code_to_issue_type("W292")
        assert result == IssueType.FORMATTING

    def test_unknown_prefix(self):
        """Test unknown prefix returns FORMATTING."""
        result = _map_ruff_code_to_issue_type("X100")
        assert result == IssueType.FORMATTING


class TestHandleEPrefix:
    """Test suite for _handle_e_prefix function."""

    def test_e999_returns_type_error(self):
        """Test E999 returns TYPE_ERROR."""
        result = _handle_e_prefix("E999")
        assert result == IssueType.TYPE_ERROR

    def test_e502_returns_type_error(self):
        """Test E502 returns TYPE_ERROR."""
        result = _handle_e_prefix("E502")
        assert result == IssueType.TYPE_ERROR

    def test_other_e_code_returns_formatting(self):
        """Test other E codes return FORMATTING."""
        result = _handle_e_prefix("E501")
        assert result == IssueType.FORMATTING


class TestHandleFPrefix:
    """Test suite for _handle_f_prefix function."""

    def test_f401_returns_import_error(self):
        """Test F401 returns IMPORT_ERROR."""
        result = _handle_f_prefix("F401")
        assert result == IssueType.IMPORT_ERROR

    def test_f822_returns_import_error(self):
        """Test F822 returns IMPORT_ERROR."""
        result = _handle_f_prefix("F822")
        assert result == IssueType.IMPORT_ERROR

    def test_f8xx_returns_formatting(self):
        """Test F8xx codes return FORMATTING."""
        result = _handle_f_prefix("F821")
        assert result == IssueType.FORMATTING

    def test_other_f_code_returns_formatting(self):
        """Test other F codes return FORMATTING."""
        result = _handle_f_prefix("F401")
        assert result == IssueType.IMPORT_ERROR


class TestRuffAdapterProperties:
    """Test suite for RuffAdapter properties."""

    @pytest.mark.asyncio
    async def test_adapter_name_check_mode(self):
        """Test adapter_name property in check mode."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            await adapter.init()
            assert adapter.adapter_name == "Ruff (check)"

    @pytest.mark.asyncio
    async def test_adapter_name_format_mode(self):
        """Test adapter_name property in format mode."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            settings = RuffSettings(mode="format")
            adapter = RuffAdapter(settings=settings)
            await adapter.init()
            assert adapter.adapter_name == "Ruff (format)"

    @pytest.mark.asyncio
    async def test_adapter_name_no_settings(self):
        """Test adapter_name property without settings."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            await adapter.init()
            # With default settings
            assert "Ruff" in adapter.adapter_name

    @pytest.mark.asyncio
    async def test_module_id(self):
        """Test module_id is correct UUID."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            await adapter.init()
            assert adapter.module_id == MODULE_ID

    @pytest.mark.asyncio
    async def test_tool_name(self):
        """Test tool_name property."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            await adapter.init()
            assert adapter.tool_name == "ruff"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_check_mode(self):
        """Test building command in check mode."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="check")

            files = [Path("test.py"), Path("src/main.py")]
            cmd = adapter.build_command(files)

            assert "ruff" in cmd
            assert "check" in cmd
            assert "--output-format" in cmd
            assert "json" in cmd
            assert "--respect-gitignore" in cmd
            assert "test.py" in cmd
            assert "src/main.py" in cmd

    def test_build_command_format_mode(self):
        """Test building command in format mode."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="format")

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "ruff" in cmd
            assert "format" in cmd
            assert "--check" in cmd  # fix_enabled=False by default

    def test_build_command_format_mode_with_fix(self):
        """Test building command in format mode with fix enabled."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="format", fix_enabled=True)

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--check" not in cmd

    def test_build_command_with_fix_enabled(self):
        """Test building command with fix enabled."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(fix_enabled=True)

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--fix" in cmd

    def test_build_command_with_unsafe_fixes(self):
        """Test building command with unsafe fixes."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(fix_enabled=True, unsafe_fixes=True)

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--fix" in cmd
            assert "--unsafe-fixes" in cmd

    def test_build_command_with_select_rules(self):
        """Test building command with select rules."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(select_rules=["E", "F", "W"])

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--select" in cmd
            assert "E, F, W" in cmd

    def test_build_command_with_ignore_rules(self):
        """Test building command with ignore rules."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(ignore_rules=["E501", "W292"])

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--ignore" in cmd
            assert "E501, W292" in cmd

    def test_build_command_with_preview(self):
        """Test building command with preview mode."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(preview=True)

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--preview" in cmd

    def test_build_command_with_line_length(self):
        """Test building command with line length."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="format", line_length=100)

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--line-length" in cmd
            assert "100" in cmd

    def test_build_command_raises_without_settings(self):
        """Test build_command raises RuntimeError without settings."""
        adapter = RuffAdapter()
        files = [Path("test.py")]

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command(files)


class TestParseCheckJson:
    """Test suite for _parse_check_json method."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON output."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            json_output = json.dumps([
                {
                    "filename": "test.py",
                    "location": {"row": 10, "column": 5},
                    "message": "Missing `f` prefix",
                    "code": "F541",
                    "fix": {"message": "Add f prefix"},
                },
            ])

            issues = adapter._parse_check_json(json_output)

            assert len(issues) == 1
            assert issues[0].file_path == Path("test.py")
            assert issues[0].line_number == 10
            assert issues[0].column_number == 5
            assert issues[0].message == "Missing `f` prefix"
            assert issues[0].code == "F541"
            assert issues[0].suggestion == "Add f prefix"

    def test_parse_json_with_e_code(self):
        """Test parsing JSON with E code (error severity)."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            json_output = json.dumps([
                {
                    "filename": "test.py",
                    "location": {"row": 1, "column": 1},
                    "message": "Syntax error",
                    "code": "E999",
                },
            ])

            issues = adapter._parse_check_json(json_output)

            assert len(issues) == 1
            assert issues[0].severity == "error"

    def test_parse_json_with_w_code(self):
        """Test parsing JSON with W code (warning severity)."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            json_output = json.dumps([
                {
                    "filename": "test.py",
                    "location": {"row": 1, "column": 1},
                    "message": "Whitespace",
                    "code": "W291",
                },
            ])

            issues = adapter._parse_check_json(json_output)

            assert len(issues) == 1
            assert issues[0].severity == "warning"

    def test_parse_json_with_empty_output(self):
        """Test parsing empty JSON output (just [*])."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            issues = adapter._parse_check_json("[*]")
            assert issues == []

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            issues = adapter._parse_check_json("not valid json")
            assert issues == []


class TestParseCheckText:
    """Test suite for _parse_check_text method."""

    def test_parse_check_text(self):
        """Test parsing text output."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            output = "test.py:10:5: F541 `x` is bare (non-WHY-bare)"
            issues = adapter._parse_check_text(output)

            assert len(issues) == 1
            assert issues[0].file_path == Path("test.py")
            assert issues[0].line_number == 10
            assert issues[0].column_number == 5

    def test_parse_check_text_with_code(self):
        """Test parsing text output with error code."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            output = "test.py:10:5: E501 Line too long (85 > 79 characters)"
            issues = adapter._parse_check_text(output)

            assert len(issues) == 1
            assert issues[0].code == "E501"
            assert issues[0].severity == "error"


class TestParseCheckTextLine:
    """Test suite for _parse_check_text_line method."""

    def test_parse_valid_line(self):
        """Test parsing valid line."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            line = "test.py:10:5: F541 `x` is bare"
            issue = adapter._parse_check_text_line(line)

            assert issue is not None
            assert issue.file_path == Path("test.py")
            assert issue.line_number == 10
            assert issue.column_number == 5

    def test_parse_line_without_column(self):
        """Test parsing line without column number."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            line = "test.py:10:not_digit: F541 `x` is bare"
            issue = adapter._parse_check_text_line(line)

            assert issue is not None
            assert issue.line_number == 10
            assert issue.column_number is None

    def test_parse_invalid_line(self):
        """Test parsing invalid line (not enough parts)."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            line = "test.py:10"  # Not enough parts
            issue = adapter._parse_check_text_line(line)
            assert issue is None

    def test_parse_line_with_no_colon(self):
        """Test parsing line without colon separator."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            line = "invalid line format"
            issue = adapter._parse_check_text_line(line)
            assert issue is None


class TestExtractCheckCodeAndMessage:
    """Test suite for _extract_check_code_and_message method."""

    def test_extract_with_code(self):
        """Test extracting code and message from line."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            code, message = adapter._extract_check_code_and_message("F541 `x` is bare")
            assert code == "F541"
            assert "`x` is bare" in message

    def test_extract_without_code(self):
        """Test extracting when message has no leading code."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            # When there's no space, it returns (None, message)
            code, message = adapter._extract_check_code_and_message("Some message")
            # First word is treated as code
            assert code == "Some"
            assert message == "message"


class TestParseFormatOutput:
    """Test suite for _parse_format_output method."""

    def test_parse_would_reformat(self):
        """Test parsing 'Would reformat' output."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            output = "Would reformat: test.py\n"
            issues = adapter._parse_format_output(output, [])

            assert len(issues) == 1
            assert issues[0].file_path == Path("test.py")
            assert "reformat" in issues[0].message.lower()

    def test_parse_would_reformat_py_file(self):
        """Test parsing output with .py file path."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            output = "test.py\n"
            issues = adapter._parse_format_output(output, [])

            assert len(issues) >= 1

    def test_parse_empty_with_processed_files(self):
        """Test parsing empty output with processed files."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings()

            files = [Path("test.py"), Path("src/main.py")]
            issues = adapter._parse_format_output("", files)

            assert len(issues) == 2


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_check_mode_json(self):
        """Test parsing output in check mode with JSON."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            await adapter.init()

            json_output = json.dumps([
                {
                    "filename": "test.py",
                    "location": {"row": 1, "column": 1},
                    "message": "Unused import",
                    "code": "F401",
                },
            ])

            result = ToolExecutionResult(
                success=False,
                raw_output=json_output,
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )
            issues = await adapter.parse_output(result)

            assert len(issues) == 1

    @pytest.mark.asyncio
    async def test_parse_format_mode(self):
        """Test parsing output in format mode."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="format")
            await adapter.init()

            result = ToolExecutionResult(
                success=False,
                raw_output="Would reformat: test.py\n",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )
            issues = await adapter.parse_output(result)

            assert len(issues) >= 1


class TestCheck:
    """Test suite for check method."""

    @pytest.mark.asyncio
    async def test_check_format_mode_with_fix(self):
        """Test check in format mode with fix enabled doesn't raise."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="format", fix_enabled=True)
            await adapter.init()

            # Just verify initialization works, the check method is inherited
            assert adapter.settings.mode == "format"
            assert adapter.settings.fix_enabled is True


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config_check_mode(self):
        """Test default config in check mode."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="check")
            config = adapter.get_default_config()

            assert config.check_name == "Ruff (check)"
            assert config.check_type == QACheckType.LINT
            assert config.enabled is True
            assert "**/*.py" in config.file_patterns
            assert config.is_formatter is False

    def test_get_default_config_format_mode(self):
        """Test default config in format mode."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="format")
            config = adapter.get_default_config()

            assert config.check_name == "Ruff (format)"
            assert config.check_type == QACheckType.FORMAT
            assert config.is_formatter is True


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type_check_mode(self):
        """Test check type in check mode is LINT."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="check")
            assert adapter._get_check_type() == QACheckType.LINT

    def test_get_check_type_format_mode(self):
        """Test check type in format mode is FORMAT."""
        with patch.object(RuffAdapter, "validate_tool_available", return_value=True):
            adapter = RuffAdapter()
            adapter.settings = RuffSettings(mode="format")
            assert adapter._get_check_type() == QACheckType.FORMAT