"""Tests for type adapters (ty, pyrefly)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.type.pyrefly import PyreflyAdapter, PyreflySettings
from crackerjack.adapters.type.ty import TyAdapter, TySettings


class TestTyAdapter:
    """Test cases for TyAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        with patch.object(TyAdapter, "validate_tool_available", return_value=True):
            adapter = TyAdapter()

            await adapter.init()

            assert adapter.settings is not None
            assert isinstance(adapter.settings, TySettings)
            assert adapter.tool_name == "ty"
            assert adapter.adapter_name == "Ty (Type Check)"

    @pytest.mark.asyncio
    async def test_build_command_default(self) -> None:
        with patch.object(TyAdapter, "validate_tool_available", return_value=True):
            adapter = TyAdapter()
            await adapter.init()

            files = [Path("file1.py"), Path("file2.py")]
            command = adapter.build_command(files)

            expected = [
                "ty",
                "check",
                "--output-format",
                "concise",
                "--no-progress",
            ]
            expected.extend(str(f) for f in files)

            assert command == expected

    @pytest.mark.asyncio
    async def test_build_command_with_fix_and_suppress(self) -> None:
        with patch.object(TyAdapter, "validate_tool_available", return_value=True):
            settings = TySettings(
                output_format="github",
                fix_enabled=True,
                add_ignore_enabled=True,
                no_progress=False,
            )
            adapter = TyAdapter(settings=settings)
            await adapter.init()

            files = [Path("src/")]
            command = adapter.build_command(files)

            assert command == [
                "ty",
                "check",
                "--output-format",
                "github",
                "--fix",
                "--add-ignore",
                "src",
            ]

    @pytest.mark.asyncio
    async def test_parse_concise_output(self) -> None:
        with patch.object(TyAdapter, "validate_tool_available", return_value=True):
            adapter = TyAdapter()
            await adapter.init()

            output = (
                "/tmp/project/a.py:1:10: error[invalid-assignment] "
                'Object of type `Literal["a"]` is not assignable to `int`\n'
                "Found 1 diagnostic"
            )

            result = self._create_mock_result(output)
            issues = await adapter.parse_output(result)

            assert len(issues) == 1
            issue = issues[0]
            assert issue.file_path == Path("/tmp/project/a.py")
            assert issue.line_number == 1
            assert issue.column_number == 10
            assert issue.code == "invalid-assignment"
            assert (
                issue.message
                == 'Object of type `Literal["a"]` is not assignable to `int`'
            )
            assert issue.severity == "error"

    @pytest.mark.asyncio
    async def test_parse_empty_output(self) -> None:
        with patch.object(TyAdapter, "validate_tool_available", return_value=True):
            adapter = TyAdapter()
            await adapter.init()

            result = self._create_mock_result("")
            issues = await adapter.parse_output(result)

            assert issues == []

    def test_capabilities(self) -> None:
        adapter = TyAdapter()

        assert adapter.supports_fix() is True
        assert adapter.supports_suppress() is True
        assert adapter.supports_baseline() is False
        assert adapter.supports_json_output() is False

    def test_get_default_config(self) -> None:
        adapter = TyAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "Ty (Type Check)"
        assert config.enabled is False
        assert config.file_patterns
        assert any(pattern.endswith("**/*.py") for pattern in config.file_patterns)
        assert config.settings["output_format"] == "concise"
        assert config.settings["fix_enabled"] is False
        assert config.settings["add_ignore_enabled"] is False
        assert config.settings["no_progress"] is True

    def _create_mock_result(self, output: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            raw_output=output,
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )


class TestPyreflyAdapter:
    """Test cases for PyreflyAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()

            await adapter.init()

            assert adapter.settings is not None
            assert isinstance(adapter.settings, PyreflySettings)
            assert adapter.tool_name == "pyrefly"
            assert adapter.adapter_name == "Pyrefly (Type Check)"

    @pytest.mark.asyncio
    async def test_build_command_default(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()

            files = [Path("file1.py"), Path("file2.py")]
            command = adapter.build_command(files)

            expected = [
                "pyrefly",
                "check",
                "--output-format",
                "json",
                "--summary",
                "none",
                "--no-progress-bar",
            ]
            expected.extend(str(f) for f in files)

            assert command == expected

    @pytest.mark.asyncio
    async def test_build_command_with_baseline_and_suppression(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            settings = PyreflySettings(
                baseline_file=Path(".cache/pyrefly.baseline.json"),
                update_baseline=True,
                suppress_errors=True,
                remove_unused_ignores=True,
            )
            adapter = PyreflyAdapter(settings=settings)
            await adapter.init()

            command = adapter.build_command([Path("src/")])

            assert command == [
                "pyrefly",
                "check",
                "--output-format",
                "json",
                "--summary",
                "none",
                "--no-progress-bar",
                "--baseline",
                ".cache/pyrefly.baseline.json",
                "--update-baseline",
                "--suppress-errors",
                "--remove-unused-ignores",
                "src",
            ]

    @pytest.mark.asyncio
    async def test_parse_json_output(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()

            output = json.dumps(
                {
                    "errors": [
                        {
                            "line": 1,
                            "column": 10,
                            "stop_line": 1,
                            "stop_column": 13,
                            "path": "/tmp/project/a.py",
                            "code": -2,
                            "name": "bad-assignment",
                            "description": "`Literal['a']` is not assignable to `int`",
                            "concise_description": "`Literal['a']` is not assignable to `int`",
                            "severity": "error",
                        },
                    ],
                },
            )

            result = self._create_mock_result(output)
            issues = await adapter.parse_output(result)

            assert len(issues) == 1
            issue = issues[0]
            assert issue.file_path == Path("/tmp/project/a.py")
            assert issue.line_number == 1
            assert issue.column_number == 10
            assert issue.code == "bad-assignment"
            assert issue.message == "`Literal['a']` is not assignable to `int`"
            assert issue.severity == "error"

    @pytest.mark.asyncio
    async def test_parse_empty_output(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()

            result = self._create_mock_result("")
            issues = await adapter.parse_output(result)

            assert issues == []

    def test_capabilities(self) -> None:
        adapter = PyreflyAdapter()

        assert adapter.supports_fix() is False
        assert adapter.supports_suppress() is True
        assert adapter.supports_baseline() is True
        assert adapter.supports_json_output() is True

    def test_get_default_config(self) -> None:
        adapter = PyreflyAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "Pyrefly (Type Check)"
        assert config.enabled is False
        assert config.settings["output_format"] == "json"
        assert config.settings["summary"] == "none"
        assert config.settings["no_progress_bar"] is True
        assert config.settings["baseline_file"] is None
        assert config.settings["update_baseline"] is False
        assert config.settings["suppress_errors"] is False
        assert config.settings["remove_unused_ignores"] is False

    def _create_mock_result(self, output: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            raw_output=output,
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )


