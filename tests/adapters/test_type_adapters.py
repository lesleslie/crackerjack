"""Tests for type adapters (ty, pyrefly, zuban)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.type.pyrefly import PyreflyAdapter, PyreflySettings
from crackerjack.adapters.type.ty import TyAdapter, TySettings
from crackerjack.adapters.type.zuban import ZubanAdapter, ZubanSettings


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


class TestZubanAdapter:
    """Test cases for ZubanAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        with patch.object(ZubanAdapter, "validate_tool_available", return_value=True):
            adapter = ZubanAdapter()

            await adapter.init()

            assert adapter.settings is not None
            assert isinstance(adapter.settings, ZubanSettings)
            assert adapter.tool_name == "zuban"
            assert adapter.adapter_name == "Zuban (Type Check)"

    @pytest.mark.asyncio
    async def test_build_command_default(self) -> None:
        with patch.object(ZubanAdapter, "validate_tool_available", return_value=True):
            adapter = ZubanAdapter()
            await adapter.init()

            files = [Path("file1.py"), Path("file2.py")]
            command = adapter.build_command(files)

            expected = [
                "zuban",
                "mypy",
                "--config-file",
                "mypy.ini",
            ]
            expected.extend(str(f) for f in files)

            assert command == expected

    @pytest.mark.asyncio
    async def test_build_command_strict_mode(self) -> None:
        with patch.object(ZubanAdapter, "validate_tool_available", return_value=True):
            settings = ZubanSettings(
                strict_mode=True,
                ignore_missing_imports=True,
            )
            adapter = ZubanAdapter(settings=settings)
            await adapter.init()

            files = [Path("src/")]
            command = adapter.build_command(files)

            assert "--strict" in command
            assert "--ignore-missing-imports" in command
            assert command == [
                "zuban",
                "mypy",
                "--config-file",
                "mypy.ini",
                "--strict",
                "--ignore-missing-imports",
                "src",
            ]

    @pytest.mark.asyncio
    async def test_build_command_with_cache_dir(self) -> None:
        with patch.object(ZubanAdapter, "validate_tool_available", return_value=True):
            settings = ZubanSettings(cache_dir=Path(".cache/zuban"))
            adapter = ZubanAdapter(settings=settings)
            await adapter.init()

            files = [Path("src/")]
            command = adapter.build_command(files)

            assert "--cache-dir" in command
            assert ".cache/zuban" in command
            assert command == [
                "zuban",
                "mypy",
                "--config-file",
                "mypy.ini",
                "--cache-dir",
                ".cache/zuban",
                "src",
            ]

    @pytest.mark.asyncio
    async def test_parse_error_output(self) -> None:
        with patch.object(ZubanAdapter, "validate_tool_available", return_value=True):
            adapter = ZubanAdapter()
            await adapter.init()

            output = (
                'src/module.py:10: error: Incompatible return value type '
                '(got "str", expected "int")  [return-value]\n'
                "src/module.py:15:5: warning: Unused variable 'x'  "
                "[unused-variable]\n"
                "Found 2 errors in 1 file (checked 3 source files)"
            )

            result = self._create_mock_result(output)
            issues = await adapter.parse_output(result)

            assert len(issues) == 2

            error_issue = issues[0]
            assert error_issue.file_path == Path("src/module.py")
            assert error_issue.line_number == 10
            assert error_issue.severity == "error"
            assert error_issue.code == "return-value"
            assert (
                error_issue.message
                == 'Incompatible return value type (got "str", expected "int")'
            )

            warning_issue = issues[1]
            assert warning_issue.file_path == Path("src/module.py")
            assert warning_issue.line_number == 15
            assert warning_issue.severity == "warning"
            assert warning_issue.code == "unused-variable"
            assert warning_issue.message == "warning: Unused variable 'x'"

    @pytest.mark.asyncio
    async def test_parse_empty_output(self) -> None:
        with patch.object(ZubanAdapter, "validate_tool_available", return_value=True):
            adapter = ZubanAdapter()
            await adapter.init()

            result = self._create_mock_result("")
            issues = await adapter.parse_output(result)

            assert issues == []

    @pytest.mark.asyncio
    async def test_parse_multiline_output(self) -> None:
        with patch.object(ZubanAdapter, "validate_tool_available", return_value=True):
            adapter = ZubanAdapter()
            await adapter.init()

            output = (
                "src/core/engine.py:42: error: Argument 1 to "
                '"process" has incompatible type "str"; expected "int"  '
                "[arg-type]\n"
                "src/core/engine.py:88: error: Name 'missing_func' is not "
                'defined  [name-defined]\n'
                "src/utils/helper.py:7: error: Incompatible return value "
                'type (got "None", expected "str")  [return-value]\n'
                "Found 3 errors in 2 files (checked 5 source files)"
            )

            result = self._create_mock_result(output)
            issues = await adapter.parse_output(result)

            assert len(issues) == 3

            assert issues[0].file_path == Path("src/core/engine.py")
            assert issues[0].line_number == 42
            assert issues[0].code == "arg-type"
            assert issues[0].severity == "error"

            assert issues[1].file_path == Path("src/core/engine.py")
            assert issues[1].line_number == 88
            assert issues[1].code == "name-defined"
            assert issues[1].severity == "error"

            assert issues[2].file_path == Path("src/utils/helper.py")
            assert issues[2].line_number == 7
            assert issues[2].code == "return-value"
            assert issues[2].severity == "error"

    def test_get_default_config(self) -> None:
        adapter = ZubanAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "Zuban (Type Check)"
        assert config.enabled is True
        assert config.file_patterns
        assert any(
            pattern.endswith("**/*.py") for pattern in config.file_patterns
        )
        assert config.settings["strict_mode"] is False
        assert config.settings["incremental"] is False
        assert config.settings["follow_imports"] == "normal"
        assert config.settings["warn_unused_ignores"] is False
        assert config.settings["ignore_missing_imports"] is True

    def _create_mock_result(self, output: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            raw_output=output,
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )
