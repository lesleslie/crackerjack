"""Tests for Creosote dependency checker adapter.

Creosote detects unused/bloat dependencies in Python projects.
These tests validate adapter integration and dependency checking functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from crackerjack.adapters._tool_adapter_base import (
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.adapters.refactor.creosote import (
    CreosoteAdapter,
    CreosoteSettings,
    MODULE_ID,
    MODULE_STATUS,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType


class TestCreosoteAdapterInitialization:
    """Test Creosote adapter initialization and configuration."""

    def test_module_registration(self) -> None:
        """Test adapter module registration constants."""
        assert str(MODULE_ID) == "c4c0c9fc-43d8-4b17-afb5-4febacec2e90"
        assert MODULE_STATUS == AdapterStatus.STABLE

    def test_adapter_initialization_with_defaults(self) -> None:
        """Test adapter initializes with default settings."""
        adapter = CreosoteAdapter()
        assert adapter.settings is None

    def test_adapter_initialization_with_custom_settings(self) -> None:
        """Test adapter initializes with custom settings."""
        settings = CreosoteSettings(
            output_format="json",
            exclude_deps=["pytest"],
            config_file=Path("pyproject.toml"),
        )
        adapter = CreosoteAdapter(settings=settings)
        assert adapter.settings == settings

    @pytest.mark.asyncio
    async def test_adapter_init_creates_default_settings(self) -> None:
        """Test init() creates default settings if none provided."""
        adapter = CreosoteAdapter()

        with (
            patch.object(adapter, 'validate_tool_available', return_value=True),
            patch.object(adapter, 'get_tool_version', return_value="1.0.0"),
            patch.object(adapter, '_get_timeout_from_settings', return_value=60),
        ):
            await adapter.init()

        assert adapter.settings is not None
        assert isinstance(adapter.settings, CreosoteSettings)
        assert adapter.settings.tool_name == "creosote"
        assert adapter.settings.timeout_seconds == 60

    def test_adapter_name_property(self) -> None:
        """Test adapter_name returns human-readable name."""
        adapter = CreosoteAdapter()
        assert adapter.adapter_name == "Creosote (Dependencies)"

    def test_module_id_property(self) -> None:
        """Test module_id property returns MODULE_ID."""
        adapter = CreosoteAdapter()
        assert adapter.module_id == MODULE_ID

    def test_tool_name_property(self) -> None:
        """Test tool_name returns CLI command."""
        adapter = CreosoteAdapter()
        assert adapter.tool_name == "creosote"


class TestCreosoteSettings:
    """Test Creosote settings configuration."""

    def test_default_settings(self) -> None:
        """Test default Creosote settings values."""
        settings = CreosoteSettings()

        assert settings.tool_name == "creosote"
        assert settings.use_json_output is False
        assert settings.config_file is None
        assert settings.exclude_deps == []
        assert settings.paths == []
        assert settings.output_format == "porcelain"
        assert settings.include_deferred is False

    def test_custom_settings(self) -> None:
        """Test custom Creosote settings override defaults."""
        config_file = Path("/tmp/pyproject.toml")
        settings = CreosoteSettings(
            output_format="json",
            config_file=config_file,
            exclude_deps=["pytest", "black"],
            paths=[Path("src"), Path("tests")],
            include_deferred=True,
        )

        assert settings.output_format == "json"
        assert settings.config_file == config_file
        assert settings.exclude_deps == ["pytest", "black"]
        assert settings.paths == [Path("src"), Path("tests")]
        assert settings.include_deferred is True


class TestCreosoteCommandBuilding:
    """Test Creosote command construction."""

    @pytest.mark.asyncio
    async def test_build_command_with_defaults(self) -> None:
        """Test command building with default settings."""
        adapter = CreosoteAdapter()
        await adapter.init()

        files = [Path("pyproject.toml")]
        cmd = adapter.build_command(files)

        assert cmd[0] == "creosote"
        assert "--format" in cmd
        assert "porcelain" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_config_file(self) -> None:
        """Test command building with config file."""
        config_file = Path("pyproject.toml")
        settings = CreosoteSettings(config_file=config_file)
        adapter = CreosoteAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("pyproject.toml")])

        assert "--deps-file" in cmd
        assert str(config_file) in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_exclude_deps(self) -> None:
        """Test command building with excluded dependencies."""
        settings = CreosoteSettings(exclude_deps=["pytest", "black"])
        adapter = CreosoteAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("pyproject.toml")])

        assert "--exclude-dep" in cmd
        assert "pytest" in cmd
        assert "black" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_include_deferred(self) -> None:
        """Test command building with include_deferred flag."""
        settings = CreosoteSettings(include_deferred=True)
        adapter = CreosoteAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("pyproject.toml")])

        assert "--include-deferred" in cmd

    @pytest.mark.asyncio
    async def test_build_command_raises_without_init(self) -> None:
        """Test command building raises error if not initialized."""
        adapter = CreosoteAdapter()

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([Path("pyproject.toml")])


class TestCreosoteOutputParsing:
    """Test Creosote output parsing."""

    @pytest.mark.asyncio
    async def test_parse_output_with_unused_deps(self) -> None:
        """Test parsing output with unused dependencies."""
        adapter = CreosoteAdapter()
        await adapter.init()

        output = """pytest
black
ruff
mypy"""

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=output,
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 4
        assert all(issue.code == "UNUSED_DEP" for issue in issues)
        assert all(issue.severity == "warning" for issue in issues)

    @pytest.mark.asyncio
    async def test_parse_output_filters_bloat_messages(self) -> None:
        """Test parsing output filters out 'bloat' messages."""
        adapter = CreosoteAdapter()
        await adapter.init()

        output = """Found 3 unused dependencies
pytest
bloat-package
black"""

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=output,
        )

        issues = await adapter.parse_output(result)

        # Should filter out "bloat-package"
        dep_names = [issue.message.split(": ")[1] if ": " in issue.message else issue.message for issue in issues]
        assert "bloat-package" not in dep_names

    @pytest.mark.asyncio
    async def test_parse_output_empty_output(self) -> None:
        """Test parsing empty output."""
        adapter = CreosoteAdapter()
        await adapter.init()

        result = ToolExecutionResult(
            success=True,
            exit_code=0,
            raw_output="",
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_output_no_output(self) -> None:
        """Test parsing with no raw_output."""
        adapter = CreosoteAdapter()
        await adapter.init()

        result = ToolExecutionResult(
            success=True,
            exit_code=0,
            raw_output="",
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 0


class TestCreosoteHelperMethods:
    """Test Creosote adapter helper methods."""

    def test_is_unused_deps_section_start(self) -> None:
        """Test _is_unused_deps_section_start detection."""
        adapter = CreosoteAdapter()

        assert adapter._is_unused_deps_section_start("Unused dependencies:")
        assert adapter._is_unused_deps_section_start("Found unused dependency in")
        assert not adapter._is_unused_deps_section_start("Some other text")

    def test_process_dependency_line(self) -> None:
        """Test _process_dependency_line extraction."""
        adapter = CreosoteAdapter()

        assert adapter._process_dependency_line("- pytest") == "pytest"
        assert adapter._process_dependency_line("  black  ") == "black"
        assert adapter._process_dependency_line("") is None
        assert adapter._process_dependency_line("   ") is None

    def test_create_issue_for_dependency(self) -> None:
        """Test _create_issue_for_dependency creation."""
        adapter = CreosoteAdapter()
        config_file = Path("pyproject.toml")

        issue = adapter._create_issue_for_dependency("pytest", config_file)

        assert issue.file_path == config_file
        assert "pytest" in issue.message
        assert issue.code == "UNUSED_DEP"
        assert issue.severity == "warning"
        assert "consider removing" in issue.suggestion.lower()


class TestCreosoteDefaultConfiguration:
    """Test Creosote default configuration."""

    def test_get_default_config(self) -> None:
        """Test default configuration values."""
        adapter = CreosoteAdapter()
        config = adapter.get_default_config()

        assert config.check_id == MODULE_ID
        assert config.check_name == "Creosote (Dependencies)"
        assert config.check_type == QACheckType.REFACTOR
        assert config.enabled is True
        assert "pyproject.toml" in config.file_patterns
        assert "pytest" in config.settings["exclude_deps"]
        assert config.timeout_seconds == 60
        assert config.parallel_safe is True
        assert config.stage == "comprehensive"

    def test_check_type_is_refactor(self) -> None:
        """Test _get_check_type returns REFACTOR."""
        adapter = CreosoteAdapter()
        assert adapter._get_check_type() == QACheckType.REFACTOR


class TestCreosoteCheck:
    """Test Creosote check method integration."""

    @pytest.mark.asyncio
    async def test_check_with_files(self) -> None:
        """Test check method with target files."""
        adapter = CreosoteAdapter()

        mock_result = ToolExecutionResult(
            success=True,
            raw_output="",
            exit_code=0,
        )

        with (
            patch.object(adapter, 'validate_tool_available', return_value=True),
            patch.object(adapter, 'get_tool_version', return_value="1.0.0"),
            patch.object(adapter, '_get_timeout_from_settings', return_value=60),
            patch.object(adapter, '_execute_tool', return_value=mock_result),
        ):
            await adapter.init()

            result = await adapter.check(files=[Path("pyproject.toml")])

            assert result.status.value in ["success", "skipped", "warning"]

    @pytest.mark.asyncio
    async def test_check_with_no_files_returns_skipped(self) -> None:
        """Test check method with no target files returns skipped."""
        adapter = CreosoteAdapter()

        with (
            patch.object(adapter, 'validate_tool_available', return_value=True),
            patch.object(adapter, 'get_tool_version', return_value="1.0.0"),
            patch.object(adapter, '_get_timeout_from_settings', return_value=60),
        ):
            await adapter.init()

            # Mock _get_target_files to return empty
            with patch.object(adapter, '_get_target_files', return_value=[]):
                result = await adapter.check(files=[])

            assert result.status.value == "skipped"
