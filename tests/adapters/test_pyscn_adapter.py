"""Tests for Pyscn SAST adapter."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from crackerjack.adapters.sast.pyscn import PyscnAdapter, PyscnSettings
from crackerjack.adapters._tool_adapter_base import ToolExecutionResult, ToolIssue


class TestPyscnAdapter:
    """Test cases for PyscnAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """Test basic initialization of PyscnAdapter."""
        with patch.object(PyscnAdapter, 'validate_tool_available', return_value=True):
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
        with patch.object(PyscnAdapter, 'validate_tool_available', return_value=True):
            settings = PyscnSettings()
            adapter = PyscnAdapter(settings=settings)
            await adapter.init()

            files = [Path("file1.py"), Path("file2.py")]
            command = adapter.build_command(files)

            expected = ["pyscn", "--format", "json", "--severity", "low", "--confidence", "low", "--recursive"]
            expected.extend([str(f) for f in files])

            assert command == expected

    @pytest.mark.asyncio
    async def test_build_command_with_options(self) -> None:
        """Test building a pyscn command with various options."""
        with patch.object(PyscnAdapter, 'validate_tool_available', return_value=True):
            settings = PyscnSettings(
                severity_threshold="high",
                confidence_threshold="medium",
                exclude_rules=["SCN001", "SCN002"],
                include_rules=["SCN100"],
                recursive=False,
                max_depth=3,
            )
            adapter = PyscnAdapter(settings=settings)
            await adapter.init()

            files = [Path("src/")]
            command = adapter.build_command(files)

            # Check that the command contains the expected elements
            assert "pyscn" in command
            assert "--format" in command
            assert "json" in command
            assert "--severity" in command
            assert "high" in command
            assert "--confidence" in command
            assert "medium" in command
            assert "--exclude" in command
            assert "SCN001" in command
            assert "SCN002" in command
            assert "--include" in command
            assert "SCN100" in command
            assert "--max-depth" in command
            assert "3" in command
            assert str(files[0]) in command

    @pytest.mark.asyncio
    async def test_parse_json_output(self) -> None:
        """Test parsing JSON output from pyscn."""
        with patch.object(PyscnAdapter, 'validate_tool_available', return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

            # Mock JSON output
            json_output = json.dumps({
                "issues": [
                    {
                        "file": "test.py",
                        "line": 10,
                        "column": 5,
                        "message": "Potential security vulnerability detected",
                        "severity": "high",
                        "confidence": "medium",
                        "rule_id": "SCN123",
                        "rule_name": "insecure_crypto"
                    }
                ]
            })

            result = ToolExecutionResult(
                success=True,
                raw_output=json_output,
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
            assert issue.message == "Potential security vulnerability detected"
            assert issue.code == "SCN123"
            assert issue.severity == "high"

    @pytest.mark.asyncio
    async def test_parse_text_output(self) -> None:
        """Test parsing text output from pyscn."""
        with patch.object(PyscnAdapter, 'validate_tool_available', return_value=True):
            adapter = PyscnAdapter()
            await adapter.init()

        # This tests the fallback method directly
        # Based on the implementation, the text format is:
        # "file.py:10:5: error: Potential security vulnerability detected"
        # But the parsing splits on ":" with maxsplit=4, so parts[3] would be " error"
        # and parts[4] would be " Potential security vulnerability detected"
        text_output = "test.py:10:5: error: Potential security vulnerability detected"
        issues = adapter._parse_text_output(text_output)

        assert len(issues) == 1
        issue = issues[0]
        assert issue.file_path == Path("test.py")
        assert issue.line_number == 10
        assert issue.column_number == 5
        # Based on the implementation, the message should be from parts[4]
        assert issue.message == "Potential security vulnerability detected"
        assert issue.severity == "error"

    @pytest.mark.asyncio
    async def test_parse_empty_output(self) -> None:
        """Test parsing empty output."""
        with patch.object(PyscnAdapter, 'validate_tool_available', return_value=True):
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
