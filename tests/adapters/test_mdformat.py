"""Tests for Mdformat markdown formatter adapter."""

from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.format.mdformat import (
    MdformatAdapter,
    MdformatSettings,
    MODULE_ID,
)
from crackerjack.models.qa_results import QACheckType


class TestMdformatSettings:
    """Test suite for MdformatSettings."""

    def test_default_settings(self):
        """Test MdformatSettings default values."""
        settings = MdformatSettings()
        assert settings.tool_name == "mdformat"
        assert settings.use_json_output is False
        assert settings.fix_enabled is True
        assert settings.line_length == 88
        assert settings.check_only is False
        assert settings.wrap_mode == "keep"
        assert settings.timeout_seconds == 300
        assert settings.max_workers == 4

    def test_custom_settings(self):
        """Test MdformatSettings with custom values."""
        settings = MdformatSettings(
            fix_enabled=False,
            line_length=100,
            check_only=True,
            wrap_mode="no",
            timeout_seconds=600,
        )
        assert settings.fix_enabled is False
        assert settings.line_length == 100
        assert settings.check_only is True
        assert settings.wrap_mode == "no"
        assert settings.timeout_seconds == 600


class TestMdformatAdapterProperties:
    """Test suite for MdformatAdapter properties."""

    @pytest.mark.asyncio
    async def test_adapter_name(self):
        """Test adapter_name property."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            await adapter.init()
            assert adapter.adapter_name == "Mdformat (Markdown)"

    @pytest.mark.asyncio
    async def test_module_id(self):
        """Test module_id is correct UUID."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            await adapter.init()
            assert adapter.module_id == MODULE_ID

    @pytest.mark.asyncio
    async def test_tool_name(self):
        """Test tool_name property."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            await adapter.init()
            assert adapter.tool_name == "mdformat"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_basic(self):
        """Test building basic command."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()

            files = [Path("README.md"), Path("docs/guide.md")]
            cmd = adapter.build_command(files)

            assert "mdformat" in cmd
            assert "README.md" in cmd
            assert "docs/guide.md" in cmd

    def test_build_command_fix_enabled(self):
        """Test building command with fix enabled (default)."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings(fix_enabled=True)

            files = [Path("README.md")]
            cmd = adapter.build_command(files)

            # --check should NOT be present when fix_enabled=True
            assert "--check" not in cmd

    def test_build_command_fix_disabled(self):
        """Test building command with fix disabled."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings(fix_enabled=False)

            files = [Path("README.md")]
            cmd = adapter.build_command(files)

            assert "--check" in cmd

    def test_build_command_with_wrap_mode_keep(self):
        """Test building command with wrap_mode=keep."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings(wrap_mode="keep")

            files = [Path("README.md")]
            cmd = adapter.build_command(files)

            assert "--wrap" in cmd
            assert "keep" in cmd

    def test_build_command_with_wrap_mode_no(self):
        """Test building command with wrap_mode=no."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings(wrap_mode="no")

            files = [Path("README.md")]
            cmd = adapter.build_command(files)

            assert "--wrap" in cmd
            assert "no" in cmd

    def test_build_command_with_wrap_mode_digit(self):
        """Test building command with wrap_mode as digit string."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings(wrap_mode="80")

            files = [Path("README.md")]
            cmd = adapter.build_command(files)

            assert "--wrap" in cmd
            assert "80" in cmd

    def test_build_command_with_line_length(self):
        """Test building command uses line_length when wrap_mode is digit string."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            # wrap_mode="80" isdigit() returns True, so --wrap 80 is used
            adapter.settings = MdformatSettings(line_length=100, wrap_mode="80")

            files = [Path("README.md")]
            cmd = adapter.build_command(files)

            assert "--wrap" in cmd
            assert "80" in cmd  # wrap_mode as digit string is used, not line_length

    def test_build_command_raises_without_settings(self):
        """Test build_command raises RuntimeError without settings."""
        adapter = MdformatAdapter()
        files = [Path("README.md")]

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command(files)


class TestParseOutputLines:
    """Test suite for _parse_output_lines method."""

    def test_parse_output_lines_with_md_files(self, tmp_path):
        """Test parsing output lines with markdown files."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()

            # Create a real markdown file
            md_file = tmp_path / "README.md"
            md_file.write_text("# Hello")

            output = str(md_file)
            issues = adapter._parse_output_lines(output)

            assert len(issues) == 1
            assert issues[0].file_path == md_file
            assert issues[0].code == "MDFORMAT"
            assert issues[0].severity == "warning"

    def test_parse_output_lines_empty(self):
        """Test parsing empty output lines."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()

            issues = adapter._parse_output_lines("")
            assert issues == []

    def test_parse_output_lines_non_md_files(self, tmp_path):
        """Test parsing output with non-markdown files (should be ignored)."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()

            # Create a non-markdown file
            py_file = tmp_path / "test.py"
            py_file.write_text("print('hello')")

            output = str(py_file)
            issues = adapter._parse_output_lines(output)

            assert issues == []


class TestCreateIssueFromLine:
    """Test suite for _create_issue_from_line method."""

    def test_create_issue_from_line_nonexistent_file(self):
        """Test creating issue from nonexistent file returns None."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()

            issue = adapter._create_issue_from_line("/nonexistent/path.md")
            # File doesn't exist, so returns None
            assert issue is None

    def test_create_issue_from_line_md_file(self, tmp_path):
        """Test creating issue from existing markdown file."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()

            md_file = tmp_path / "README.md"
            md_file.write_text("# Hello")

            issue = adapter._create_issue_from_line(str(md_file))

            assert issue is not None
            assert issue.file_path == md_file
            assert "Markdown formatting" in issue.message
            assert issue.code == "MDFORMAT"
            assert issue.severity == "warning"
            assert issue.suggestion == "Run mdformat to format this file"

    def test_create_issue_from_line_markdown_file(self, tmp_path):
        """Test creating issue from existing .markdown file."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()

            md_file = tmp_path / "guide.markdown"
            md_file.write_text("# Hello")

            issue = adapter._create_issue_from_line(str(md_file))

            assert issue is not None
            assert issue.file_path == md_file


class TestCreateIssuesFromProcessedFiles:
    """Test suite for _create_issues_from_processed_files method."""

    def test_create_issues_from_md_files(self, tmp_path):
        """Test creating issues from processed markdown files."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()

            md_file = tmp_path / "README.md"
            md_file.touch()
            mdpy_file = tmp_path / "guide.markdown"
            mdpy_file.touch()
            py_file = tmp_path / "test.py"
            py_file.touch()

            processed_files = [md_file, mdpy_file, py_file]
            issues = adapter._create_issues_from_processed_files(processed_files)

            # Only markdown files should create issues
            assert len(issues) == 2
            assert all(i.code == "MDFORMAT" for i in issues)
            assert all(i.severity == "warning" for i in issues)


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_output_success(self):
        """Test parsing output with exit_code 0 (success)."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
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
    async def test_parse_output_with_issues(self, tmp_path):
        """Test parsing output with formatting issues."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            await adapter.init()

            md_file = tmp_path / "README.md"
            md_file.write_text("# Hello")

            result = ToolExecutionResult(
                success=False,
                raw_output=str(md_file),
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
                files_processed=[md_file],
            )
            issues = await adapter.parse_output(result)

            assert len(issues) >= 1

    @pytest.mark.asyncio
    async def test_parse_output_no_issues_but_processed_files(self, tmp_path):
        """Test parsing when no issues found but processed files exist."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            await adapter.init()

            md_file = tmp_path / "README.md"
            md_file.touch()

            result = ToolExecutionResult(
                success=False,
                raw_output="",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
                files_processed=[md_file],
            )
            issues = await adapter.parse_output(result)

            # Should create issues from processed files
            assert len(issues) >= 1


class TestGetTargetFiles:
    """Test suite for _get_target_files method."""

    @pytest.mark.asyncio
    async def test_get_target_files_with_provided_files(self):
        """Test _get_target_files returns provided files."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            await adapter.init()

            files = [Path("README.md"), Path("docs/guide.md")]
            result = await adapter._get_target_files(files, None)

            assert result == files

    @pytest.mark.asyncio
    async def test_get_target_files_without_files(self):
        """Test _get_target_files gets files from git."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            with patch(
                "crackerjack.tools._git_utils.get_git_tracked_files"
            ) as mock_get_files:
                mock_get_files.side_effect = [
                    [Path("README.md")],
                    [Path("docs/guide.md")],
                ]

                adapter = MdformatAdapter()
                await adapter.init()

                result = await adapter._get_target_files(None, None)

                assert Path("README.md") in result
                assert Path("docs/guide.md") in result


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self):
        """Test default configuration."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()
            config = adapter.get_default_config()

            assert config.check_name == "Mdformat (Markdown)"
            assert config.check_type == QACheckType.FORMAT
            assert config.enabled is True
            assert "**/*.md" in config.file_patterns
            assert "**/*.markdown" in config.file_patterns
            assert config.is_formatter is True
            assert config.stage == "fast"
            assert config.timeout_seconds == 300


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self):
        """Test check type is FORMAT."""
        with patch.object(MdformatAdapter, "validate_tool_available", return_value=True):
            adapter = MdformatAdapter()
            adapter.settings = MdformatSettings()
            assert adapter._get_check_type() == QACheckType.FORMAT