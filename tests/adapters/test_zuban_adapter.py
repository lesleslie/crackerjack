"""Tests for Zuban type checking adapter.

Zuban is a Rust-based ultra-fast Python type checker (20-200x faster than pyright).
These tests validate the ACB adapter integration and type checking functionality.
"""

import json
from pathlib import Path
from uuid import UUID

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult, ToolIssue
from crackerjack.adapters.type.zuban import (
    MODULE_ID,
    MODULE_STATUS,
    ZubanAdapter,
    ZubanSettings,
)
from crackerjack.models.qa_results import QACheckType


class TestZubanAdapterInitialization:
    """Test Zuban adapter initialization and configuration."""

    def test_module_registration(self) -> None:
        """Test ACB module registration constants."""
        assert MODULE_ID == UUID("01937d86-6b2c-7d3e-8f4a-b5c6d7e8f9a0")
        assert MODULE_STATUS == "stable"

    def test_adapter_initialization_with_defaults(self) -> None:
        """Test adapter initializes with default settings."""
        adapter = ZubanAdapter()
        assert adapter.settings is None  # Not initialized until init()

    def test_adapter_initialization_with_custom_settings(self) -> None:
        """Test adapter initializes with custom settings."""
        settings = ZubanSettings(
            strict_mode=True,
            incremental=False,
            follow_imports="skip",
        )
        adapter = ZubanAdapter(settings=settings)
        assert adapter.settings == settings
        assert adapter.settings.strict_mode is True
        assert adapter.settings.incremental is False

    @pytest.mark.asyncio
    async def test_adapter_init_creates_default_settings(self) -> None:
        """Test init() creates default settings if none provided."""
        adapter = ZubanAdapter()
        await adapter.init()

        assert adapter.settings is not None
        assert isinstance(adapter.settings, ZubanSettings)
        assert adapter.settings.tool_name == "zuban"
        assert adapter.settings.use_json_output is True

    def test_adapter_name_property(self) -> None:
        """Test adapter_name returns human-readable name."""
        adapter = ZubanAdapter()
        assert adapter.adapter_name == "Zuban (Type Check)"

    def test_module_id_property(self) -> None:
        """Test module_id property returns MODULE_ID."""
        adapter = ZubanAdapter()
        assert adapter.module_id == MODULE_ID

    def test_tool_name_property(self) -> None:
        """Test tool_name returns CLI command."""
        adapter = ZubanAdapter()
        assert adapter.tool_name == "zuban"


class TestZubanSettings:
    """Test Zuban settings configuration."""

    def test_default_settings(self) -> None:
        """Test default Zuban settings values."""
        settings = ZubanSettings()

        assert settings.tool_name == "zuban"
        assert settings.use_json_output is True
        assert settings.strict_mode is False
        assert settings.ignore_missing_imports is False
        assert settings.follow_imports == "normal"
        assert settings.cache_dir is None
        assert settings.incremental is True
        assert settings.warn_unused_ignores is True

    def test_custom_settings(self) -> None:
        """Test custom Zuban settings override defaults."""
        cache_dir = Path("/tmp/zuban-cache")
        settings = ZubanSettings(
            strict_mode=True,
            ignore_missing_imports=True,
            follow_imports="silent",
            cache_dir=cache_dir,
            incremental=False,
            warn_unused_ignores=False,
        )

        assert settings.strict_mode is True
        assert settings.ignore_missing_imports is True
        assert settings.follow_imports == "silent"
        assert settings.cache_dir == cache_dir
        assert settings.incremental is False
        assert settings.warn_unused_ignores is False


class TestZubanCommandBuilding:
    """Test Zuban command construction."""

    @pytest.mark.asyncio
    async def test_build_command_with_defaults(self) -> None:
        """Test command building with default settings."""
        adapter = ZubanAdapter()
        await adapter.init()

        files = [Path("src/"), Path("tests/")]
        cmd = adapter.build_command(files)

        assert cmd[0] == "zuban"
        assert "--format" in cmd
        assert "json" in cmd
        assert "--follow-imports" in cmd
        assert "normal" in cmd
        assert "--incremental" in cmd
        assert "--warn-unused-ignores" in cmd
        assert "src" in cmd
        assert "tests" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_strict_mode(self) -> None:
        """Test command building with strict mode enabled."""
        settings = ZubanSettings(strict_mode=True)
        adapter = ZubanAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/")])

        assert "--strict" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_cache_dir(self) -> None:
        """Test command building with cache directory."""
        cache_dir = Path("/tmp/zuban-cache")
        settings = ZubanSettings(cache_dir=cache_dir)
        adapter = ZubanAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/")])

        assert "--cache-dir" in cmd
        assert str(cache_dir) in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_ignore_missing_imports(self) -> None:
        """Test command building with ignore missing imports."""
        settings = ZubanSettings(ignore_missing_imports=True)
        adapter = ZubanAdapter(settings=settings)
        await adapter.init()

        cmd = adapter.build_command([Path("src/")])

        assert "--ignore-missing-imports" in cmd

    @pytest.mark.asyncio
    async def test_build_command_raises_without_init(self) -> None:
        """Test command building raises error if not initialized."""
        adapter = ZubanAdapter()

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([Path("src/")])


class TestZubanOutputParsing:
    """Test Zuban output parsing (JSON and text formats)."""

    @pytest.mark.asyncio
    async def test_parse_json_output_success(self) -> None:
        """Test parsing valid JSON output from Zuban."""
        adapter = ZubanAdapter()
        await adapter.init()

        # Sample Zuban JSON output
        json_output = json.dumps({
            "files": [
                {
                    "path": "src/main.py",
                    "errors": [
                        {
                            "line": 42,
                            "column": 10,
                            "message": "Incompatible types in assignment",
                            "severity": "error",
                            "code": "assignment",
                        },
                        {
                            "line": 50,
                            "column": 5,
                            "message": "Missing return statement",
                            "severity": "warning",
                            "code": "return",
                        },
                    ],
                },
                {
                    "path": "src/utils.py",
                    "errors": [
                        {
                            "line": 15,
                            "column": 8,
                            "message": "Undefined name 'Optional'",
                            "severity": "error",
                            "code": "name-error",
                        },
                    ],
                },
            ],
        })

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=json_output,
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 3

        # First issue
        assert issues[0].file_path == Path("src/main.py")
        assert issues[0].line_number == 42
        assert issues[0].column_number == 10
        assert "Incompatible types" in issues[0].message
        assert issues[0].severity == "error"
        assert issues[0].code == "assignment"

        # Second issue
        assert issues[1].file_path == Path("src/main.py")
        assert issues[1].line_number == 50
        assert issues[1].severity == "warning"

        # Third issue
        assert issues[2].file_path == Path("src/utils.py")
        assert issues[2].line_number == 15

    @pytest.mark.asyncio
    async def test_parse_empty_json_output(self) -> None:
        """Test parsing empty JSON output (no errors)."""
        adapter = ZubanAdapter()
        await adapter.init()

        json_output = json.dumps({"files": []})
        result = ToolExecutionResult(
            success=True,
            exit_code=0,
            raw_output=json_output,
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_text_output_fallback(self) -> None:
        """Test fallback text parsing when JSON parsing fails."""
        adapter = ZubanAdapter()
        await adapter.init()

        # Non-JSON text output
        text_output = """src/main.py:42:10: error: Incompatible types in assignment
src/main.py:50:5: warning: Missing return statement
src/utils.py:15:8: error: Undefined name 'Optional'"""

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=text_output,
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 3
        assert issues[0].file_path == Path("src/main.py")
        assert issues[0].line_number == 42
        assert issues[0].column_number == 10
        assert issues[0].severity == "error"
        assert issues[1].severity == "warning"

    @pytest.mark.asyncio
    async def test_parse_output_no_output(self) -> None:
        """Test parsing with no output."""
        adapter = ZubanAdapter()
        await adapter.init()

        result = ToolExecutionResult(
            success=True,
            exit_code=0,
            raw_output="",
        )

        issues = await adapter.parse_output(result)

        assert len(issues) == 0


class TestZubanDefaultConfiguration:
    """Test Zuban default configuration."""

    def test_get_default_config(self) -> None:
        """Test default configuration values."""
        adapter = ZubanAdapter()
        config = adapter.get_default_config()

        assert config.check_id == MODULE_ID
        assert config.check_name == "Zuban (Type Check)"
        assert config.check_type == QACheckType.TYPE
        assert config.enabled is True
        assert config.file_patterns == ["**/*.py"]
        assert "**/.venv/**" in config.exclude_patterns
        assert "**/build/**" in config.exclude_patterns
        assert config.timeout_seconds == 180
        assert config.parallel_safe is True
        assert config.stage == "comprehensive"

    def test_get_default_config_settings(self) -> None:
        """Test default configuration settings dict."""
        adapter = ZubanAdapter()
        config = adapter.get_default_config()

        assert config.settings["strict_mode"] is False
        assert config.settings["incremental"] is True
        assert config.settings["follow_imports"] == "normal"
        assert config.settings["warn_unused_ignores"] is True

    def test_check_type_is_type(self) -> None:
        """Test _get_check_type returns TYPE."""
        adapter = ZubanAdapter()
        assert adapter._get_check_type() == QACheckType.TYPE


class TestZubanEdgeCases:
    """Test Zuban adapter edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_parse_malformed_json(self) -> None:
        """Test parsing malformed JSON falls back to text parsing."""
        adapter = ZubanAdapter()
        await adapter.init()

        malformed_json = '{"files": [{'  # Incomplete JSON
        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=malformed_json,
        )

        issues = await adapter.parse_output(result)

        # Should fall back to text parsing (which won't find valid lines)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_text_with_invalid_line_numbers(self) -> None:
        """Test text parsing skips lines with invalid line numbers."""
        adapter = ZubanAdapter()
        await adapter.init()

        text_output = """src/main.py:invalid:10: error: Some error
src/main.py:42:10: error: Valid error"""

        result = ToolExecutionResult(
            success=False,
            exit_code=1,
            raw_output=text_output,
        )

        issues = await adapter.parse_output(result)

        # Should only parse the valid line
        assert len(issues) == 1
        assert issues[0].line_number == 42

    def test_multiple_files_in_command(self) -> None:
        """Test command building with multiple target files."""
        settings = ZubanSettings()
        adapter = ZubanAdapter(settings=settings)
        adapter.settings = settings  # Manual init for test

        files = [Path("src/main.py"), Path("src/utils.py"), Path("tests/")]
        cmd = adapter.build_command(files)

        assert "src/main.py" in cmd
        assert "src/utils.py" in cmd
        assert "tests" in cmd


# Integration test placeholder (requires actual Zuban installation)
@pytest.mark.skip(reason="Requires Zuban installation - enable for integration testing")
class TestZubanIntegration:
    """Integration tests for Zuban adapter (requires Zuban installed)."""

    @pytest.mark.asyncio
    async def test_real_type_check(self, tmp_path: Path) -> None:
        """Test real type checking on sample Python file."""
        # Create sample file with type error
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def add_numbers(a: int, b: int) -> int:
    return a + b

result: str = add_numbers(1, 2)  # Type error: int assigned to str
""")

        adapter = ZubanAdapter()
        await adapter.init()

        result = await adapter.check(files=[test_file])

        assert not result.success
        assert len(result.issues) > 0
        assert any("incompatible" in issue.message.lower() for issue in result.issues)
