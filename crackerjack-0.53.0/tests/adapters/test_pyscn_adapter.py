"""Tests for Pyscn SAST adapter."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult, ToolIssue
from crackerjack.adapters.sast.pyscn import PyscnAdapter, PyscnSettings


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
                max_complexity=20,
            )
            adapter = PyscnAdapter(settings=settings)
            await adapter.init()

            files = [Path("src/")]
            command = adapter.build_command(files)

            # Check that the command contains the expected elements
            assert "pyscn" in command
            assert "check" in command
            assert "--max-complexity" in command
            assert "20" in command
            assert str(files[0]) in command

    @pytest.mark.asyncio
    async def test_parse_json_output(self) -> None:
        """Test parsing output from pyscn (text format only)."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

            # Mock text output (pyscn only outputs text, not JSON)
            text_output = "test.py:10:5: error: Function 'test_func' is too complex (complexity 25)"

            result = ToolExecutionResult(
                success=True,
                raw_output=text_output,
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            issues = await adapter.parse_output(result)

            assert len(issues) == 1
            issue = issues[0]
            assert issue.file_path == Path("test.py")
            assert issue.line_number == 10
            assert issue.column_number == 5
            assert "complex" in issue.message.lower()

    @pytest.mark.asyncio
    async def test_parse_text_output(self) -> None:
        """Test parsing text output from pyscn."""
        with patch.object(PyscnAdapter, "validate_tool_available", return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

        # Test the actual format: "file.py:10:5: error: Function 'test_func' is too complex"
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
    async def test_parse_empty_output(self) -> None:
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

    def test_get_default_config(self) -> None:
        """Test getting default configuration."""
        adapter = PyscnAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "Pyscn (Security Analysis)"
        assert config.enabled is False  # Experimental, so disabled by default
        assert config.file_patterns == ["**/*.py"]
        assert config.stage == "comprehensive"  # Security checks in comprehensive stage
