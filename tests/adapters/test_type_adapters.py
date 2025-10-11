"""Tests for type adapters (ty, pyrefly)."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from crackerjack.adapters.type.ty import TyAdapter, TySettings
from crackerjack.adapters.type.pyrefly import PyreflyAdapter, PyreflySettings
from crackerjack.adapters._tool_adapter_base import ToolExecutionResult, ToolIssue


class TestTyAdapter:
    """Test cases for TyAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """Test basic initialization of TyAdapter."""
        with patch.object(TyAdapter, 'validate_tool_available', return_value=True):
            adapter = TyAdapter()
            assert adapter.settings is None

            await adapter.init()
            assert adapter.settings is not None
            assert isinstance(adapter.settings, TySettings)
            assert adapter.tool_name == "ty"
            assert adapter.adapter_name == "Ty (Type Verification)"

    @pytest.mark.asyncio
    async def test_build_command_basic(self) -> None:
        """Test building a basic ty command."""
        with patch.object(TyAdapter, 'validate_tool_available', return_value=True):
            settings = TySettings(use_json_output=True, strict_mode=False,
                                ignore_missing_imports=False, follow_imports="normal",
                                incremental=True, warn_unused_ignores=True)
            adapter = TyAdapter(settings=settings)
            await adapter.init()

            files = [Path("file1.py"), Path("file2.py")]
            command = adapter.build_command(files)

            expected = ["ty", "--format", "json", "--follow-imports", "normal", "--incremental", "--warn-unused-ignores"]
            expected.extend([str(f) for f in files])

            assert command == expected

    @pytest.mark.asyncio
    async def test_build_command_with_options(self) -> None:
        """Test building a ty command with various options."""
        with patch.object(TyAdapter, 'validate_tool_available', return_value=True):
            settings = TySettings(
                strict_mode=True,
                ignore_missing_imports=True,
                follow_imports="silent",
                incremental=False,
                warn_unused_ignores=False,
            )
            adapter = TyAdapter(settings=settings)
            await adapter.init()

            files = [Path("src/")]
            command = adapter.build_command(files)

            expected = [
                "ty",
                "--format", "json",
                "--strict",
                "--ignore-missing-imports",
                "--follow-imports", "silent",
            ]
            expected.extend([str(f) for f in files])

            assert command == expected

    async def _create_mock_result(self, output: str) -> ToolExecutionResult:
        """Helper to create a mock execution result."""
        return ToolExecutionResult(
            success=True,
            raw_output=output,
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )

    @pytest.mark.asyncio
    async def test_parse_json_output(self) -> None:
        """Test parsing JSON output from ty."""
        with patch.object(TyAdapter, 'validate_tool_available', return_value=True):
            adapter = TyAdapter()
            await adapter.init()

            # Mock JSON output
            json_output = json.dumps({
                "files": [
                    {
                        "path": "test.py",
                        "errors": [
                            {
                                "line": 10,
                                "column": 5,
                                "message": "Incompatible types",
                                "severity": "error",
                                "code": "assignment"
                            }
                        ]
                    }
                ]
            })

            result = await self._create_mock_result(json_output)
            issues = await adapter.parse_output(result)

            assert len(issues) == 1
            issue = issues[0]
            assert issue.file_path == Path("test.py")
            assert issue.line_number == 10
            assert issue.column_number == 5
            assert issue.message == "Incompatible types"
            assert issue.code == "assignment"
            assert issue.severity == "error"

    @pytest.mark.asyncio
    async def test_parse_text_output(self) -> None:
        """Test parsing text output from ty."""
        with patch.object(TyAdapter, 'validate_tool_available', return_value=True):
            adapter = TyAdapter()
            await adapter.init()

        # This tests the fallback method directly
        text_output = "test.py:10:5: error: Incompatible types in assignment"
        issues = adapter._parse_text_output(text_output)

        assert len(issues) == 1
        issue = issues[0]
        assert issue.file_path == Path("test.py")
        assert issue.line_number == 10
        assert issue.column_number == 5
        # The text parsing may extract the message differently depending on implementation
        # Check that a message was extracted
        assert issue.message != ""
        assert "Incompatible types" in issue.message or "assignment" in issue.message
        assert issue.severity == "error"

    @pytest.mark.asyncio
    async def test_parse_empty_output(self) -> None:
        """Test parsing empty output."""
        with patch.object(TyAdapter, 'validate_tool_available', return_value=True):
            adapter = TyAdapter()
            await adapter.init()

            result = await self._create_mock_result("")
            issues = await adapter.parse_output(result)

            assert issues == []

    def test_get_default_config(self) -> None:
        """Test getting default configuration."""
        adapter = TyAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "Ty (Type Verification)"
        assert config.enabled is False  # Experimental, so disabled by default
        assert config.file_patterns == ["**/*.py"]


class TestPyreflyAdapter:
    """Test cases for PyreflyAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """Test basic initialization of PyreflyAdapter."""
        with patch.object(PyreflyAdapter, 'validate_tool_available', return_value=True):
            adapter = PyreflyAdapter()
            assert adapter.settings is None

            await adapter.init()
            assert adapter.settings is not None
            assert isinstance(adapter.settings, PyreflySettings)
            assert adapter.tool_name == "pyrefly"
            assert adapter.adapter_name == "Pyrefly (Type Check)"

    @pytest.mark.asyncio
    async def test_build_command_basic(self) -> None:
        """Test building a basic pyrefly command."""
        with patch.object(PyreflyAdapter, 'validate_tool_available', return_value=True):
            settings = PyreflySettings(use_json_output=True, strict_mode=False,
                                     ignore_missing_imports=False, follow_imports="normal",
                                     incremental=True, warn_unused_ignores=True)
            adapter = PyreflyAdapter(settings=settings)
            await adapter.init()

            files = [Path("file1.py"), Path("file2.py")]
            command = adapter.build_command(files)

            expected = ["pyrefly", "--format", "json", "--follow-imports", "normal", "--incremental", "--warn-unused-ignores"]
            expected.extend([str(f) for f in files])

            assert command == expected

    @pytest.mark.asyncio
    async def test_build_command_with_options(self) -> None:
        """Test building a pyrefly command with various options."""
        with patch.object(PyreflyAdapter, 'validate_tool_available', return_value=True):
            settings = PyreflySettings(
                strict_mode=True,
                ignore_missing_imports=True,
                follow_imports="silent",
                incremental=False,
                warn_unused_ignores=False,
            )
            adapter = PyreflyAdapter(settings=settings)
            await adapter.init()

            files = [Path("src/")]
            command = adapter.build_command(files)

            expected = [
                "pyrefly",
                "--format", "json",
                "--strict",
                "--ignore-missing-imports",
                "--follow-imports", "silent",
            ]
            expected.extend([str(f) for f in files])

            assert command == expected

    @pytest.mark.asyncio
    async def test_parse_json_output(self) -> None:
        """Test parsing JSON output from pyrefly."""
        with patch.object(PyreflyAdapter, 'validate_tool_available', return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()

            # Mock JSON output
            json_output = json.dumps({
                "files": [
                    {
                        "path": "test.py",
                        "errors": [
                            {
                                "line": 15,
                                "column": 3,
                                "message": "Undefined variable 'x'",
                                "severity": "error",
                                "code": "name-defined"
                            }
                        ]
                    }
                ]
            })

            result = self._create_mock_result(json_output)
            issues = await adapter.parse_output(result)

            assert len(issues) == 1
            issue = issues[0]
            assert issue.file_path == Path("test.py")
            assert issue.line_number == 15
            assert issue.column_number == 3
            assert issue.message == "Undefined variable 'x'"
            assert issue.code == "name-defined"
            assert issue.severity == "error"

    def _create_mock_result(self, output: str) -> ToolExecutionResult:
        """Helper to create a mock execution result."""
        return ToolExecutionResult(
            success=True,
            raw_output=output,
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )

    @pytest.mark.asyncio
    async def test_parse_text_output(self) -> None:
        """Test parsing text output from pyrefly."""
        with patch.object(PyreflyAdapter, 'validate_tool_available', return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()

        # This tests the fallback method directly
        text_output = "test.py:15:3: error: Undefined variable 'x'"
        issues = adapter._parse_text_output(text_output)

        assert len(issues) == 1
        issue = issues[0]
        assert issue.file_path == Path("test.py")
        assert issue.line_number == 15
        assert issue.column_number == 3
        # The text parsing may extract the message differently depending on implementation
        # Check that a message was extracted
        assert issue.message != ""
        assert "Undefined variable" in issue.message or "x" in issue.message
        assert issue.severity == "error"

    @pytest.mark.asyncio
    async def test_parse_empty_output(self) -> None:
        """Test parsing empty output."""
        with patch.object(PyreflyAdapter, 'validate_tool_available', return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()

            result = self._create_mock_result("")
            issues = await adapter.parse_output(result)

            assert issues == []

    def test_get_default_config(self) -> None:
        """Test getting default configuration."""
        adapter = PyreflyAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "Pyrefly (Type Check)"
        assert config.enabled is False  # Experimental, so disabled by default
        assert config.file_patterns == ["**/*.py"]
