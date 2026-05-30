"""Tests for Vulture dead code detector adapter.

Vulture detects unused code (dead code) in Python projects.
These tests validate adapter integration and dead code detection functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from crackerjack.adapters._tool_adapter_base import (
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.adapters.refactor.vulture import (
    VultureAdapter,
    VultureSettings,
    MODULE_ID,
    MODULE_STATUS,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType


class TestVultureAdapterInitialization:
    """Test Vulture adapter initialization and configuration."""

    def test_module_registration(self) -> None:
        """Test adapter module registration constants."""
        assert str(MODULE_ID) == "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"
        assert MODULE_STATUS == AdapterStatus.BETA

    def test_adapter_initialization_with_defaults(self) -> None:
        """Test adapter initializes with default settings."""
        adapter = VultureAdapter()
        assert adapter.settings is None

    def test_adapter_initialization_with_custom_settings(self) -> None:
        """Test adapter initializes with custom settings."""
        settings = VultureSettings(
            min_confidence=80,
            exclude_patterns=["tests/**", "docs/**"],
            ignore_decorators=["@app.route"],
            ignore_names=["unused_*"],
        )
        adapter = VultureAdapter(settings=settings)
        assert adapter.settings == settings

    @pytest.mark.asyncio
    async def test_adapter_init_creates_default_settings(self) -> None:
        """Test init() creates default settings if none provided."""
        adapter = VultureAdapter()

        with (
            patch.object(adapter, 'validate_tool_available', return_value=True),
            patch.object(adapter, 'get_tool_version', return_value="2.0.0"),
            patch.object(adapter, '_get_timeout_from_settings', return_value=30),
        ):
            await adapter.init()

        assert adapter.settings is not None
        assert isinstance(adapter.settings, VultureSettings)
        assert adapter.settings.tool_name == "vulture"
        assert adapter.settings.min_confidence == 60

    def test_adapter_name_property(self) -> None:
        """Test adapter_name returns human-readable name."""
        adapter = VultureAdapter()
        assert adapter.adapter_name == "Vulture (Dead Code)"

    def test_module_id_property(self) -> None:
        """Test module_id property returns MODULE_ID."""
        adapter = VultureAdapter()
        assert adapter.module_id == MODULE_ID

    def test_tool_name_property(self) -> None:
        """Test tool_name returns CLI command."""
        adapter = VultureAdapter()
        assert adapter.tool_name == "vulture"


class TestVultureSettings:
    """Test Vulture settings configuration."""

    def test_default_settings(self) -> None:
        """Test default Vulture settings values."""
        settings = VultureSettings()

        assert settings.tool_name == "vulture"
        assert settings.min_confidence == 60
        assert settings.exclude_patterns == []
        assert settings.ignore_decorators == []
        assert settings.ignore_names == []
        assert settings.sort_by_size is False
        assert settings.make_whitelist is False

    def test_custom_settings(self) -> None:
        """Test custom Vulture settings override defaults."""
        settings = VultureSettings(
            min_confidence=80,
            exclude_patterns=["tests/**"],
            ignore_decorators=["@property"],
            ignore_names=["unused_*", "dead_*"],
            sort_by_size=True,
            make_whitelist=True,
        )

        assert settings.min_confidence == 80
        assert settings.exclude_patterns == ["tests/**"]
        assert settings.ignore_decorators == ["@property"]
        assert settings.ignore_names == ["unused_*", "dead_*"]
        assert settings.sort_by_size is True
        assert settings.make_whitelist is True


class TestVultureCommandBuilding:
    """Test Vulture command construction."""

    @pytest.mark.asyncio
    async def test_build_command_with_defaults(self) -> None:
        """Test command building with default settings."""
        adapter = VultureAdapter()
        await adapter.init()

        files = [Path("src/")]
        cmd = adapter.build_command(files)

        assert cmd[0] == "vulture"
        assert "--min-confidence" in cmd
        assert "60" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_custom_min_confidence(self) -> None:
        """Test command building with custom min confidence."""
        settings = VultureSettings(min_confidence=80)
        adapter = VultureAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/")])

        assert "--min-confidence" in cmd
        assert "80" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_exclude_patterns(self) -> None:
        """Test command building with exclude patterns."""
        settings = VultureSettings(exclude_patterns=["tests/**", "docs/**"])
        adapter = VultureAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/")])

        assert "--exclude" in cmd
        # Patterns are joined with ", "
        exclude_str = " ".join(cmd[cmd.index("--exclude") + 1:])
        assert "tests/**" in exclude_str
        assert "docs/**" in exclude_str

    @pytest.mark.asyncio
    async def test_build_command_with_ignore_decorators(self) -> None:
        """Test command building with ignore decorators."""
        settings = VultureSettings(ignore_decorators=["@property", "@staticmethod"])
        adapter = VultureAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/")])

        assert "--ignore-decorators" in cmd
        # Decorators are joined with ", "
        decorators_str = " ".join(cmd[cmd.index("--ignore-decorators") + 1:])
        assert "@property" in decorators_str

    @pytest.mark.asyncio
    async def test_build_command_with_ignore_names(self) -> None:
        """Test command building with ignore names."""
        settings = VultureSettings(ignore_names=["unused_*"])
        adapter = VultureAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/")])

        assert "--ignore-names" in cmd
        assert "unused_*" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_sort_by_size(self) -> None:
        """Test command building with sort by size flag."""
        settings = VultureSettings(sort_by_size=True)
        adapter = VultureAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/")])

        assert "--sort-by-size" in cmd

    @pytest.mark.asyncio
    async def test_build_command_raises_without_init(self) -> None:
        """Test command building raises error if not initialized."""
        adapter = VultureAdapter()

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([Path("src/")])


class TestVultureOutputParsing:
    """Test Vulture output parsing."""

    @pytest.mark.asyncio
    async def test_parse_output_with_dead_code(self) -> None:
        """Test parsing output with dead code issues."""
        adapter = VultureAdapter()
        await adapter.init()

        output = """src/main.py:42: unused_function - unused function (80% confidence)
src/utils.py:15: unused_class - unused class (90% confidence)
src/helpers.py:100: unused_variable - unused variable (70% confidence)"""

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=output,
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 3
        assert issues[0].file_path == Path("src/main.py")
        assert issues[0].line_number == 42
        assert "80% confidence" in issues[0].message
        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_output_high_confidence_error(self) -> None:
        """Test that high confidence issues are marked as errors."""
        adapter = VultureAdapter()
        await adapter.init()

        output = """src/main.py:42: unused_func - unused function (90% confidence)"""

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=output,
        )

        issues = await adapter.parse_output(result)

        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_output_low_confidence_warning(self) -> None:
        """Test that low confidence issues are marked as warnings."""
        adapter = VultureAdapter()
        await adapter.init()

        output = """src/main.py:42: unused_func - unused function (60% confidence)"""

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=output,
        )

        issues = await adapter.parse_output(result)

        assert issues[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_parse_output_empty(self) -> None:
        """Test parsing empty output."""
        adapter = VultureAdapter()
        await adapter.init()

        result = ToolExecutionResult(
            success=True,
            exit_code=0,
            raw_output="",
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_output_filters_unused_attribute(self) -> None:
        """Test parsing filters out 'unused attribute' lines."""
        adapter = VultureAdapter()
        await adapter.init()

        output = """src/main.py:42: some_func - some function (80% confidence)
unused attribute found in class
src/utils.py:15: another_func - another function (75% confidence)"""

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=output,
        )

        issues = await adapter.parse_output(result)

        # Should only have 2 issues, "unused attribute" line filtered
        assert len(issues) == 2


class TestVultureLineParsing:
    """Test Vulture line parsing helper methods."""

    def test_parse_line_valid(self) -> None:
        """Test parsing a valid Vulture line."""
        adapter = VultureAdapter()

        line = "src/main.py:42: unused_function - unused function (80% confidence)"

        issue = adapter._parse_line(line)

        assert issue is not None
        assert issue.file_path == Path("src/main.py")
        assert issue.line_number == 42
        assert issue.code == "vulture_unused_function"

    def test_parse_line_invalid_format(self) -> None:
        """Test parsing invalid Vulture line format."""
        adapter = VultureAdapter()

        # Invalid format (missing confidence)
        line = "src/main.py:42: unused_function"
        assert adapter._parse_line(line) is None

        # Empty line
        assert adapter._parse_line("") is None

    def test_parse_line_confidence_threshold(self) -> None:
        """Test confidence affects severity."""
        adapter = VultureAdapter()

        # High confidence (>=80) -> error
        high_line = "src/main.py:42: unused_func - function (80% confidence)"
        high_issue = adapter._parse_line(high_line)
        assert high_issue is not None
        assert high_issue.severity == "error"

        # Low confidence (<80) -> warning
        low_line = "src/main.py:42: unused_func - function (70% confidence)"
        low_issue = adapter._parse_line(low_line)
        assert low_issue is not None
        assert low_issue.severity == "warning"


class TestVultureDefaultConfiguration:
    """Test Vulture default configuration."""

    def test_get_default_config(self) -> None:
        """Test default configuration values."""
        adapter = VultureAdapter()
        config = adapter.get_default_config()

        assert config.check_id == MODULE_ID
        assert config.check_name == "Vulture (Dead Code)"
        assert config.check_type == QACheckType.COMPLEXITY
        assert config.enabled is True
        assert len(config.file_patterns) > 0
        assert "**/test_*.py" in config.exclude_patterns
        assert config.timeout_seconds == 30
        assert config.parallel_safe is True
        assert config.stage == "fast"

    def test_check_type_is_complexity(self) -> None:
        """Test _get_check_type returns COMPLEXITY."""
        adapter = VultureAdapter()
        assert adapter._get_check_type() == QACheckType.COMPLEXITY


class TestVultureCheck:
    """Test Vulture check method integration."""

    @pytest.mark.asyncio
    async def test_check_with_files(self) -> None:
        """Test check method with target files."""
        adapter = VultureAdapter()

        mock_result = ToolExecutionResult(
            success=True,
            raw_output="",
            exit_code=0,
        )

        with (
            patch.object(adapter, 'validate_tool_available', return_value=True),
            patch.object(adapter, 'get_tool_version', return_value="2.0.0"),
            patch.object(adapter, '_get_timeout_from_settings', return_value=30),
            patch.object(adapter, '_execute_tool', return_value=mock_result),
        ):
            await adapter.init()

            result = await adapter.check(files=[Path("src/")])

            assert result.status.value in ["success", "skipped", "warning"]

    @pytest.mark.asyncio
    async def test_check_with_no_files(self) -> None:
        """Test check method with no target files uses package dir."""
        adapter = VultureAdapter()

        mock_result = ToolExecutionResult(
            success=True,
            raw_output="",
            exit_code=0,
        )

        with (
            patch.object(adapter, 'validate_tool_available', return_value=True),
            patch.object(adapter, 'get_tool_version', return_value="2.0.0"),
            patch.object(adapter, '_get_timeout_from_settings', return_value=30),
            patch.object(adapter, '_execute_tool', return_value=mock_result),
        ):
            await adapter.init()

            # With empty file list, should still work (uses package dir)
            result = await adapter.check(files=[])

            # Status depends on whether files were found
            assert result.status.value in ["success", "skipped"]
