"""Tests for RuffAdapter."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from crackerjack.adapters.format.ruff import (
    RuffAdapter,
    RuffSettings,
    RuffMode,
)
from crackerjack.adapters._tool_adapter_base import (
    ToolIssue,
    ToolExecutionResult,
)
from crackerjack.models.qa_results import QAResultStatus, QACheckType


@pytest.fixture
def ruff_settings():
    """Provide RuffSettings for testing."""
    return RuffSettings(
        timeout_seconds=60,
        max_workers=4,
        mode="check",
        fix_enabled=False,
        unsafe_fixes=False,
        use_json_output=True,
        respect_gitignore=True,
        preview=False,
    )


@pytest.fixture
async def ruff_adapter(ruff_settings):
    """Provide initialized RuffAdapter for testing."""
    adapter = RuffAdapter(settings=ruff_settings)
    # Mock the initialization to avoid tool availability checks
    with patch.object(adapter, 'validate_tool_available', return_value=True), \
         patch.object(adapter, 'get_tool_version', return_value="1.0.0"):
        await adapter.init()
    return adapter


@pytest.fixture
def sample_python_file(tmp_path):
    """Create a sample Python file for testing."""
    test_file = tmp_path / "test.py"
    test_file.write_text("x=1\n")
    return test_file


class TestRuffSettings:
    """Test suite for RuffSettings."""

    def test_default_settings(self):
        """Test RuffSettings default values."""
        settings = RuffSettings()
        assert settings.tool_name == "ruff"
        assert settings.mode == "check"
        assert settings.fix_enabled is False
        assert settings.unsafe_fixes is False
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
            ignore_rules=["E501"],
            line_length=100,
            preview=True,
        )
        assert settings.mode == "format"
        assert settings.fix_enabled is True
        assert settings.unsafe_fixes is True
        assert settings.select_rules == ["E", "F"]
        assert settings.ignore_rules == ["E501"]
        assert settings.line_length == 100
        assert settings.preview is True


class TestRuffAdapterProperties:
    """Test suite for RuffAdapter properties."""

    def test_adapter_name_check_mode(self, ruff_settings):
        """Test adapter_name in check mode."""
        ruff_settings.mode = "check"
        adapter = RuffAdapter(settings=ruff_settings)
        assert adapter.adapter_name == "Ruff (check)"

    def test_adapter_name_format_mode(self):
        """Test adapter_name in format mode."""
        settings = RuffSettings(mode="format")
        adapter = RuffAdapter(settings=settings)
        assert adapter.adapter_name == "Ruff (format)"

    def test_adapter_name_no_settings(self):
        """Test adapter_name when no settings set."""
        adapter = RuffAdapter(settings=None)
        assert adapter.adapter_name == "Ruff"

    def test_module_id(self, ruff_adapter):
        """Test module_id is correct UUID."""
        from crackerjack.adapters.format.ruff import MODULE_ID
        assert ruff_adapter.module_id == MODULE_ID

    def test_tool_name(self, ruff_adapter):
        """Test tool_name property."""
        assert ruff_adapter.tool_name == "ruff"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_check_mode_command(self, ruff_adapter, tmp_path):
        """Test building command in check mode."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        cmd = ruff_adapter.build_command([test_file])

        assert "ruff" in cmd
        assert "check" in cmd
        assert str(test_file) in cmd

    def test_build_format_mode_command(self, tmp_path):
        """Test building command in format mode."""
        settings = RuffSettings(mode="format", fix_enabled=True)
        adapter = RuffAdapter(settings=settings)
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1\n")

        cmd = adapter.build_command([test_file])

        assert "ruff" in cmd
        assert "format" in cmd
        assert str(test_file) in cmd

    def test_check_mode_with_fix(self, tmp_path):
        """Test check mode with fix enabled."""
        settings = RuffSettings(mode="check", fix_enabled=True)
        adapter = RuffAdapter(settings=settings)
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--fix" in cmd

    def test_check_mode_with_unsafe_fixes(self, tmp_path):
        """Test check mode with unsafe fixes enabled."""
        settings = RuffSettings(
            mode="check",
            fix_enabled=True,
            unsafe_fixes=True,
        )
        adapter = RuffAdapter(settings=settings)
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--fix" in cmd
        assert "--unsafe-fixes" in cmd

    def test_check_mode_with_select_rules(self, tmp_path):
        """Test check mode with select rules."""
        settings = RuffSettings(
            mode="check",
            select_rules=["E", "F", "W"],
        )
        adapter = RuffAdapter(settings=settings)
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--select" in cmd
        assert "E, F, W" in " ".join(cmd)

    def test_check_mode_with_ignore_rules(self, tmp_path):
        """Test check mode with ignore rules."""
        settings = RuffSettings(
            mode="check",
            ignore_rules=["E501", "E203"],
        )
        adapter = RuffAdapter(settings=settings)
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--ignore" in cmd
        assert "E501, E203" in " ".join(cmd)

    def test_check_mode_with_preview(self, tmp_path):
        """Test check mode with preview enabled."""
        settings = RuffSettings(mode="check", preview=True)
        adapter = RuffAdapter(settings=settings)
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--preview" in cmd

    def test_format_mode_with_line_length(self, tmp_path):
        """Test format mode with custom line length."""
        settings = RuffSettings(
            mode="format",
            line_length=100,
        )
        adapter = RuffAdapter(settings=settings)
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--line-length" in cmd
        assert "100" in cmd

    def test_format_mode_with_check_flag(self, tmp_path):
        """Test format mode with --check flag."""
        settings = RuffSettings(
            mode="format",
            fix_enabled=False,
        )
        adapter = RuffAdapter(settings=settings)
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--check" in cmd

    def test_respect_gitignore_enabled(self, ruff_adapter, tmp_path):
        """Test --respect-gitignore flag when enabled."""
        test_file = tmp_path / "test.py"
        cmd = ruff_adapter.build_command([test_file])
        assert "--respect-gitignore" in cmd

    def test_respect_gitignore_disabled(self, tmp_path):
        """Test no --respect-gitignore flag when disabled."""
        settings = RuffSettings(respect_gitignore=False)
        adapter = RuffAdapter(settings=settings)
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--respect-gitignore" not in cmd

    def test_build_command_raises_without_settings(self, tmp_path):
        """Test build_command raises RuntimeError without settings."""
        adapter = RuffAdapter(settings=None)
        test_file = tmp_path / "test.py"

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([test_file])


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_check_json_output(self, ruff_adapter):
        """Test parsing JSON output from check mode."""
        json_output = json.dumps([
            {
                "filename": "test.py",
                "location": {"row": 10, "column": 5},
                "message": "Unused variable",
                "code": "F841",
                "fix": {"message": "Remove unused variable"},
            }
        ])

        result = ToolExecutionResult(
            raw_output=json_output,
            exit_code=1,
        )

        issues = await ruff_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 10
        assert issues[0].column_number == 5
        assert issues[0].message == "Unused variable"
        assert issues[0].code == "F841"
        assert issues[0].severity == "warning"
        assert "Remove unused variable" in issues[0].suggestion

    @pytest.mark.asyncio
    async def test_parse_check_json_with_error_code(self, ruff_adapter):
        """Test parsing JSON output with error code."""
        json_output = json.dumps([
            {
                "filename": "test.py",
                "location": {"row": 1, "column": 1},
                "message": "Syntax error",
                "code": "E999",
            }
        ])

        result = ToolExecutionResult(raw_output=json_output)
        issues = await ruff_adapter.parse_output(result)

        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_check_json_empty_array(self, ruff_adapter):
        """Test parsing empty JSON array."""
        result = ToolExecutionResult(raw_output="[]")
        issues = await ruff_adapter.parse_output(result)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_check_json_wildcard(self, ruff_adapter):
        """Test parsing wildcard JSON output."""
        result = ToolExecutionResult(raw_output="[*]")
        issues = await ruff_adapter.parse_output(result)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_check_json_invalid(self, ruff_adapter):
        """Test parsing invalid JSON returns empty list."""
        result = ToolExecutionResult(raw_output="invalid json")
        issues = await ruff_adapter.parse_output(result)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_check_text_output(self, ruff_adapter):
        """Test parsing text output from check mode."""
        text_output = "test.py:10:5: F841 Unused variable\n"

        result = ToolExecutionResult(raw_output=text_output)
        # Switch to text mode
        ruff_adapter.settings.use_json_output = False

        issues = await ruff_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 10
        assert issues[0].column_number == 5
        assert issues[0].message == "Unused variable"
        assert issues[0].code == "F841"

    @pytest.mark.asyncio
    async def test_parse_check_text_without_column(self, ruff_adapter):
        """Test parsing text output without column number."""
        text_output = "test.py:10: F841 Unused variable\n"

        result = ToolExecutionResult(raw_output=text_output)
        ruff_adapter.settings.use_json_output = False

        issues = await ruff_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].line_number == 10
        assert issues[0].column_number is None

    @pytest.mark.asyncio
    async def test_parse_check_text_error_severity(self, ruff_adapter):
        """Test error code severity in text parsing."""
        text_output = "test.py:10:5: E999 Syntax error\n"

        result = ToolExecutionResult(raw_output=text_output)
        ruff_adapter.settings.use_json_output = False

        issues = await ruff_adapter.parse_output(result)

        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_format_output(self, tmp_path):
        """Test parsing format output."""
        settings = RuffSettings(mode="format")
        adapter = RuffAdapter(settings=settings)
        await adapter.init()

        test_file = tmp_path / "test.py"
        text_output = f"Would reformat: {test_file}\n"

        result = ToolExecutionResult(
            raw_output=text_output,
            files_processed=[test_file],
            exit_code=1,
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == test_file
        assert issues[0].message == "File would be reformatted"

    @pytest.mark.asyncio
    async def test_parse_format_output_with_files(self, tmp_path):
        """Test parsing format output with processed files."""
        settings = RuffSettings(mode="format")
        adapter = RuffAdapter(settings=settings)
        await adapter.init()

        test_file = tmp_path / "test.py"
        result = ToolExecutionResult(
            raw_output="",
            files_processed=[test_file],
            exit_code=1,
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == test_file

    @pytest.mark.asyncio
    async def test_parse_output_raises_without_settings(self, tmp_path):
        """Test parse_output raises RuntimeError without settings."""
        adapter = RuffAdapter(settings=None)
        result = ToolExecutionResult(raw_output="output")

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            await adapter.parse_output(result)


class TestCheckMethod:
    """Test suite for check method."""

    @pytest.mark.asyncio
    async def test_check_with_format_fix_enabled(self, tmp_path):
        """Test check method with format mode and fix enabled."""
        settings = RuffSettings(
            mode="format",
            fix_enabled=True,
        )
        adapter = RuffAdapter(settings=settings)

        with patch.object(adapter, 'validate_tool_available', return_value=True), \
             patch.object(adapter, 'get_tool_version', return_value="1.0.0"), \
             patch.object(adapter, '_execute_tool') as mock_exec:

            exec_result = ToolExecutionResult(
                success=True,
                files_processed=[tmp_path / "test.py"],
            )
            mock_exec.return_value = exec_result

            result = await adapter.check([tmp_path / "test.py"])

            assert result.files_modified == result.files_checked
            assert result.issues_fixed == result.issues_found


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config_check_mode(self, ruff_adapter):
        """Test default config for check mode."""
        config = ruff_adapter.get_default_config()

        assert config.check_name == "Ruff (check)"
        assert config.check_type == QACheckType.LINT
        assert config.enabled is True
        assert "**/*.py" in config.file_patterns
        assert config.is_formatter is False

    def test_get_default_config_format_mode(self):
        """Test default config for format mode."""
        settings = RuffSettings(mode="format")
        adapter = RuffAdapter(settings=settings)

        config = adapter.get_default_config()

        assert config.check_name == "Ruff (format)"
        assert config.check_type == QACheckType.FORMAT
        assert config.is_formatter is True


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type_check_mode(self, ruff_adapter):
        """Test check type for check mode."""
        ruff_adapter.settings.mode = "check"
        assert ruff_adapter._get_check_type() == QACheckType.LINT

    def test_get_check_type_format_mode(self):
        """Test check type for format mode."""
        settings = RuffSettings(mode="format")
        adapter = RuffAdapter(settings=settings)
        assert adapter._get_check_type() == QACheckType.FORMAT
