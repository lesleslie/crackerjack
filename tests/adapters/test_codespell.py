"""Tests for Codespell spelling checker adapter."""

from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.lint.codespell import (
    CodespellAdapter,
    CodespellSettings,
    MODULE_ID,
)
from crackerjack.models.qa_results import QACheckType


class TestCodespellSettings:
    """Test suite for CodespellSettings."""

    def test_default_settings(self):
        """Test CodespellSettings default values."""
        settings = CodespellSettings()
        assert settings.tool_name == "codespell"
        assert settings.use_json_output is False
        assert settings.fix_enabled is True
        assert settings.skip_hidden is True
        assert settings.ignore_words == []
        assert settings.ignore_words_file is None
        assert settings.check_filenames is False
        assert settings.quiet_level == 2
        assert settings.timeout_seconds == 60
        assert settings.max_workers == 4

    def test_custom_settings(self):
        """Test CodespellSettings with custom values."""
        settings = CodespellSettings(
            fix_enabled=False,
            skip_hidden=False,
            ignore_words=["foo", "bar"],
            check_filenames=True,
            quiet_level=0,
            timeout_seconds=120,
        )
        assert settings.fix_enabled is False
        assert settings.skip_hidden is False
        assert settings.ignore_words == ["foo", "bar"]
        assert settings.check_filenames is True
        assert settings.quiet_level == 0
        assert settings.timeout_seconds == 120


class TestCodespellAdapterProperties:
    """Test suite for CodespellAdapter properties."""

    @pytest.mark.asyncio
    async def test_adapter_name(self):
        """Test adapter_name property."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            await adapter.init()
            assert adapter.adapter_name == "Codespell (Spelling)"

    @pytest.mark.asyncio
    async def test_module_id(self):
        """Test module_id is correct UUID."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            await adapter.init()
            assert adapter.module_id == MODULE_ID

    @pytest.mark.asyncio
    async def test_tool_name(self):
        """Test tool_name property."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            await adapter.init()
            assert adapter.tool_name == "codespell"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_basic(self):
        """Test building basic command."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            adapter.settings = CodespellSettings()

            files = [Path("test.py"), Path("README.md")]
            cmd = adapter.build_command(files)

            assert "codespell" in cmd
            assert "--write-changes" in cmd  # fix_enabled=True
            assert "--skip=.*" in cmd  # skip_hidden=True
            assert "--quiet-level" in cmd
            assert "2" in cmd
            assert "test.py" in cmd
            assert "README.md" in cmd

    def test_build_command_fix_disabled(self):
        """Test building command with fix disabled."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            settings = CodespellSettings(fix_enabled=False)
            adapter = CodespellAdapter(settings=settings)
            adapter.settings = settings

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--write-changes" not in cmd

    def test_build_command_skip_hidden_disabled(self):
        """Test building command with skip_hidden disabled."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            settings = CodespellSettings(skip_hidden=False)
            adapter = CodespellAdapter(settings=settings)
            adapter.settings = settings

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--skip=.*" not in cmd

    def test_build_command_with_ignore_words(self):
        """Test building command with ignore words list."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            settings = CodespellSettings(ignore_words=["pydantic", "uuid"])
            adapter = CodespellAdapter(settings=settings)
            adapter.settings = settings

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--ignore-words-list" in cmd
            assert "pydantic, uuid" in cmd

    def test_build_command_with_ignore_words_file(self, tmp_path):
        """Test building command with ignore words file."""
        ignore_file = tmp_path / "ignore.txt"
        ignore_file.write_text("foo\nbar\n")

        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            settings = CodespellSettings(ignore_words_file=ignore_file)
            adapter = CodespellAdapter(settings=settings)
            adapter.settings = settings

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--ignore-words" in cmd
            assert str(ignore_file) in cmd

    def test_build_command_with_ignore_words_file_not_exists(self, tmp_path):
        """Test building command skips ignore words file if it doesn't exist."""
        ignore_file = tmp_path / "nonexistent.txt"

        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            settings = CodespellSettings(ignore_words_file=ignore_file)
            adapter = CodespellAdapter(settings=settings)
            adapter.settings = settings

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--ignore-words" not in cmd

    def test_build_command_with_check_filenames(self):
        """Test building command with check_filenames enabled."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            settings = CodespellSettings(check_filenames=True)
            adapter = CodespellAdapter(settings=settings)
            adapter.settings = settings

            files = [Path("test.py")]
            cmd = adapter.build_command(files)

            assert "--check-filenames" in cmd

    def test_build_command_raises_without_settings(self):
        """Test build_command raises RuntimeError without settings."""
        adapter = CodespellAdapter()
        files = [Path("test.py")]

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command(files)


class TestParseCodespellLine:
    """Test suite for _parse_codespell_line method."""

    def test_parse_standard_format(self):
        """Test parsing standard codespell output format."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            adapter.settings = CodespellSettings()

            # Note: codespell output format is "file:line: ==> wrong => correct"
            line = "test_file.py:10:==> 'teh' should be 'the'"
            result = adapter._parse_codespell_line(line)

            assert result is not None
            file_path, line_number, message, suggestion = result
            assert file_path == Path("test_file.py")
            assert line_number == 10
            assert "'teh' should be 'the'" in message
            assert suggestion is not None

    def test_parse_without_line_number(self):
        """Test parsing codespell output without line number."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            adapter.settings = CodespellSettings()

            line = "test_file.py: ==> 'teh' should be 'the'"
            result = adapter._parse_codespell_line(line)

            assert result is not None
            file_path, line_number, message, suggestion = result
            assert file_path == Path("test_file.py")
            assert line_number is None

    def test_parse_invalid_format(self):
        """Test parsing invalid codespell output."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            adapter.settings = CodespellSettings()

            # No ":" or "==>"
            line = "invalid output format"
            result = adapter._parse_codespell_line(line)
            assert result is None

    def test_parse_without_arrow(self):
        """Test parsing codespell output without ==> returns None."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            adapter.settings = CodespellSettings()

            # Without ==>, the function returns None because of the early check
            line = "test_file.py:15: Some spelling error"
            result = adapter._parse_codespell_line(line)

            # Function returns None when no "==>" is present
            assert result is None


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_output_with_results(self):
        """Test parsing output with spelling issues."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            await adapter.init()

            raw_output = """test_file.py:10: ==> 'teh' should be 'the'
README.md:5: ==> 'accomodate' should be 'accommodate'
"""
            result = ToolExecutionResult(
                success=True,
                raw_output=raw_output,
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            issues = await adapter.parse_output(result)

            assert len(issues) == 2
            assert issues[0].file_path == Path("test_file.py")
            assert issues[0].line_number == 10
            assert issues[0].code == "SPELLING"
            assert issues[0].severity == "warning"
            assert "'teh' should be 'the'" in issues[0].message

    @pytest.mark.asyncio
    async def test_parse_empty_output(self):
        """Test parsing empty output."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
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
    async def test_parse_none_output(self):
        """Test parsing None output."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            await adapter.init()

            result = ToolExecutionResult(
                success=True,
                raw_output=None,
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            issues = await adapter.parse_output(result)

            assert issues == []


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self):
        """Test default configuration."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            adapter.settings = CodespellSettings()
            config = adapter.get_default_config()

            assert config.check_name == "Codespell (Spelling)"
            assert config.check_type == QACheckType.FORMAT
            assert config.enabled is True
            assert "**/*.py" in config.file_patterns
            assert "**/*.md" in config.file_patterns
            assert config.is_formatter is True
            assert config.stage == "fast"
            assert config.timeout_seconds == 60


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self):
        """Test check type is FORMAT."""
        with patch.object(CodespellAdapter, "validate_tool_available", return_value=True):
            adapter = CodespellAdapter()
            adapter.settings = CodespellSettings()
            assert adapter._get_check_type() == QACheckType.FORMAT