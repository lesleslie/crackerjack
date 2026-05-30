"""Tests for Refurb refactoring adapter.

Refurb is a tool for refactoring Python code. These tests validate
adapter integration and refactoring functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from crackerjack.adapters._tool_adapter_base import (
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.adapters.refactor.refurb import (
    RefurbAdapter,
    RefurbSettings,
    MODULE_ID,
    MODULE_STATUS,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType


class TestRefurbAdapterInitialization:
    """Test Refurb adapter initialization and configuration."""

    def test_module_registration(self) -> None:
        """Test adapter module registration constants."""
        assert str(MODULE_ID) == "0f3546f6-4e29-4d9d-98f8-43c6f3c21a4e"
        assert MODULE_STATUS == AdapterStatus.STABLE

    def test_adapter_initialization_with_defaults(self) -> None:
        """Test adapter initializes with default settings."""
        adapter = RefurbAdapter()
        assert adapter.settings is None
        assert adapter.file_filter is None

    def test_adapter_initialization_with_custom_settings(self) -> None:
        """Test adapter initializes with custom settings."""
        settings = RefurbSettings(
            enable_all=True,
            disable_checks=["FURB101"],
            enable_checks=["FURB102"],
            python_version="3.11",
        )
        adapter = RefurbAdapter(settings=settings)
        assert adapter.settings == settings

    def test_adapter_initialization_with_file_filter(self) -> None:
        """Test adapter initializes with file filter."""
        mock_filter = MagicMock()
        adapter = RefurbAdapter(file_filter=mock_filter)
        assert adapter.file_filter == mock_filter

    @pytest.mark.asyncio
    async def test_adapter_init_creates_default_settings(self) -> None:
        """Test init() creates default settings if none provided."""
        adapter = RefurbAdapter()

        with (
            patch.object(adapter, 'validate_tool_available', return_value=True),
            patch.object(adapter, 'get_tool_version', return_value="1.0.0"),
            patch.object(adapter, '_get_timeout_from_settings', return_value=240),
        ):
            await adapter.init()

        assert adapter.settings is not None
        assert isinstance(adapter.settings, RefurbSettings)
        assert adapter.settings.tool_name == "refurb"

    def test_adapter_name_property(self) -> None:
        """Test adapter_name returns human-readable name."""
        adapter = RefurbAdapter()
        assert adapter.adapter_name == "Refurb (Refactoring)"

    def test_module_id_property(self) -> None:
        """Test module_id property returns MODULE_ID."""
        adapter = RefurbAdapter()
        assert adapter.module_id == MODULE_ID

    def test_tool_name_property(self) -> None:
        """Test tool_name returns CLI command."""
        adapter = RefurbAdapter()
        assert adapter.tool_name == "refurb"


class TestRefurbSettings:
    """Test Refurb settings configuration."""

    def test_default_settings(self) -> None:
        """Test default Refurb settings values."""
        settings = RefurbSettings()

        assert settings.tool_name == "refurb"
        assert settings.use_json_output is False
        assert settings.enable_all is False
        assert settings.disable_checks == []
        assert settings.enable_checks == []
        assert settings.python_version is None
        assert settings.explain is False

    def test_custom_settings(self) -> None:
        """Test custom Refurb settings override defaults."""
        settings = RefurbSettings(
            enable_all=True,
            disable_checks=["FURB101", "FURB102"],
            enable_checks=["FURB103"],
            python_version="3.11",
            explain=True,
        )

        assert settings.enable_all is True
        assert settings.disable_checks == ["FURB101", "FURB102"]
        assert settings.enable_checks == ["FURB103"]
        assert settings.python_version == "3.11"
        assert settings.explain is True


class TestRefurbCommandBuilding:
    """Test Refurb command construction."""

    @pytest.mark.asyncio
    async def test_build_command_with_defaults(self) -> None:
        """Test command building with default settings."""
        adapter = RefurbAdapter()
        await adapter.init()

        files = [Path("src/main.py")]
        cmd = adapter.build_command(files)

        assert cmd[0] == "refurb"
        assert str(files[0]) in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_enable_all(self) -> None:
        """Test command building with enable_all flag."""
        settings = RefurbSettings(enable_all=True)
        adapter = RefurbAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/main.py")])

        assert "--enable-all" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_disable_checks(self) -> None:
        """Test command building with disabled checks."""
        settings = RefurbSettings(disable_checks=["FURB101", "FURB102"])
        adapter = RefurbAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/main.py")])

        assert "--ignore" in cmd
        assert "FURB101" in cmd
        assert "FURB102" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_enable_checks(self) -> None:
        """Test command building with enabled checks."""
        settings = RefurbSettings(enable_checks=["FURB103"])
        adapter = RefurbAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/main.py")])

        assert "--enable" in cmd
        assert "FURB103" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_python_version(self) -> None:
        """Test command building with python version."""
        settings = RefurbSettings(python_version="3.11")
        adapter = RefurbAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/main.py")])

        assert "--python-version" in cmd
        assert "3.11" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_explain(self) -> None:
        """Test command building with explain flag."""
        settings = RefurbSettings(explain=True)
        adapter = RefurbAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/main.py")])

        assert "--explain" in cmd

    @pytest.mark.asyncio
    async def test_build_command_raises_without_init(self) -> None:
        """Test command building raises error if not initialized."""
        adapter = RefurbAdapter()

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([Path("src/main.py")])


class TestRefurbOutputParsing:
    """Test Refurb output parsing."""

    @pytest.mark.asyncio
    async def test_parse_output_with_issues(self) -> None:
        """Test parsing output with refactoring issues."""
        adapter = RefurbAdapter()
        await adapter.init()

        output = """src/main.py:42:10: [FURB101] Use dict comprehension instead of loop
src/utils.py:15:5: [FURB102] Replace lambda with comprehension"""

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=output,
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 2
        assert issues[0].file_path == Path("src/main.py")
        assert issues[0].line_number == 42
        assert "FURB101" in issues[0].code

    @pytest.mark.asyncio
    async def test_parse_output_empty(self) -> None:
        """Test parsing empty output."""
        adapter = RefurbAdapter()
        await adapter.init()

        result = ToolExecutionResult(
            success=True,
            exit_code=0,
            raw_output="",
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_output_no_issues_found(self) -> None:
        """Test parsing output with no FURB issues."""
        adapter = RefurbAdapter()
        await adapter.init()

        output = """src/main.py:42:10: Some other message
src/utils.py:15:5: Another message"""

        result = ToolExecutionResult(
            success=True,
            exit_code=0,
            raw_output=output,
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 0


class TestRefurbLineParsing:
    """Test Refurb line parsing helper methods."""

    def test_parse_refurb_line_valid(self) -> None:
        """Test parsing a valid FURB line."""
        adapter = RefurbAdapter()

        line = "src/main.py:42:10: [FURB101] Use dict comprehension"

        issue = adapter._parse_refurb_line(line)

        assert issue is not None
        assert issue.file_path == Path("src/main.py")
        assert issue.line_number == 42
        assert issue.column_number == 10
        assert "FURB101" in issue.code

    def test_parse_refurb_line_no_column(self) -> None:
        """Test parsing FURB line without column number."""
        adapter = RefurbAdapter()

        line = "src/main.py:42: [FURB101] Use dict comprehension"

        issue = adapter._parse_refurb_line(line)

        assert issue is not None
        assert issue.file_path == Path("src/main.py")
        assert issue.line_number == 42
        assert issue.column_number is None

    def test_parse_refurb_line_invalid_format(self) -> None:
        """Test parsing invalid FURB line format."""
        adapter = RefurbAdapter()

        # No colon separator
        line = "invalid line format"
        assert adapter._parse_refurb_line(line) is None

        # Not enough parts
        line = "src/main.py:42"
        assert adapter._parse_refurb_line(line) is None

    def test_extract_column_number(self) -> None:
        """Test _extract_column_number method."""
        adapter = RefurbAdapter()

        # Valid column number
        assert adapter._extract_column_number("42: Some message") == 42

        # No space (no column)
        assert adapter._extract_column_number("nospace") is None

        # Non-digit
        assert adapter._extract_column_number("abc: message") is None

    def test_extract_message_part(self) -> None:
        """Test _extract_message_part method."""
        adapter = RefurbAdapter()

        # With column
        remaining = "42: [FURB101] Use dict comprehension"
        result = adapter._extract_message_part(remaining, 42)
        assert "FURB101" in result

        # Without column
        remaining = "Some message"
        result = adapter._extract_message_part(remaining, None)
        assert result == "Some message"

    def test_extract_code_and_message(self) -> None:
        """Test _extract_code_and_message method."""
        adapter = RefurbAdapter()

        # With code bracket
        message_part = "[FURB101] Use dict comprehension"
        code, message = adapter._extract_code_and_message(message_part)
        assert code == "FURB101"
        assert "dict comprehension" in message

        # Without code bracket
        message_part = "Just a message"
        code, message = adapter._extract_code_and_message(message_part)
        assert code is None
        assert message == "Just a message"


class TestRefurbDefaultConfiguration:
    """Test Refurb default configuration."""

    def test_get_default_config(self) -> None:
        """Test default configuration values."""
        adapter = RefurbAdapter()
        config = adapter.get_default_config()

        assert config.check_id == MODULE_ID
        assert config.check_name == "Refurb (Refactoring)"
        assert config.check_type == QACheckType.REFACTOR
        assert config.enabled is True
        assert len(config.file_patterns) > 0
        assert "**/test_*.py" in config.exclude_patterns
        assert config.timeout_seconds == 240
        assert config.parallel_safe is True
        assert config.stage == "comprehensive"

    def test_check_type_is_refactor(self) -> None:
        """Test _get_check_type returns REFACTOR."""
        adapter = RefurbAdapter()
        assert adapter._get_check_type() == QACheckType.REFACTOR


class TestDetectPackageDirectory:
    """Test package directory detection."""

    def test_detect_package_directory_with_pyproject(self, tmp_path) -> None:
        """Test detection when pyproject.toml has project name."""
        import os

        adapter = RefurbAdapter()

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-package"\n')

        package_dir = tmp_path / "my_package"
        package_dir.mkdir()
        (package_dir / "__init__.py").touch()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            detected = adapter._detect_package_directory()
            assert detected == "my_package"
        finally:
            os.chdir(original_cwd)

    def test_detect_package_directory_fallback(self, tmp_path) -> None:
        """Test detection falls back to src or current dir name."""
        import os

        adapter = RefurbAdapter()

        # No pyproject, use current dir name
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            detected = adapter._detect_package_directory()
            assert detected in ["src", tmp_path.name]
        finally:
            os.chdir(original_cwd)


class TestRefurbCheck:
    """Test Refurb check method integration."""

    @pytest.mark.asyncio
    async def test_check_with_files(self) -> None:
        """Test check method with target files."""
        adapter = RefurbAdapter()

        mock_result = ToolExecutionResult(
            success=True,
            raw_output="",
            exit_code=0,
        )

        with (
            patch.object(adapter, 'validate_tool_available', return_value=True),
            patch.object(adapter, 'get_tool_version', return_value="1.0.0"),
            patch.object(adapter, '_get_timeout_from_settings', return_value=240),
            patch.object(adapter, '_execute_tool', return_value=mock_result),
        ):
            await adapter.init()

            result = await adapter.check(files=[Path("src/main.py")])

            assert result.status.value in ["success", "skipped", "warning"]
