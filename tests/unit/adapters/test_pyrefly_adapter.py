from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.type.pyrefly import PyreflyAdapter, PyreflySettings
from crackerjack.adapters.type.ty import TyAdapter


def _make_result(output: str) -> ToolExecutionResult:
    return ToolExecutionResult(
        success=True,
        raw_output=output,
        raw_stderr="",
        execution_time_ms=0.0,
        exit_code=0,
    )


class TestPyreflyModuleId:
    @pytest.mark.unit
    def test_pyrefly_module_id_differs_from_ty(self) -> None:
        assert PyreflyAdapter().module_id != TyAdapter().module_id

    @pytest.mark.unit
    def test_all_type_adapter_module_ids_are_unique(self) -> None:
        from crackerjack.adapters.type.zuban import ZubanAdapter

        ids = [
            TyAdapter().module_id,
            PyreflyAdapter().module_id,
            ZubanAdapter().module_id,
        ]
        assert len(ids) == len(set(ids)), f"Duplicate MODULE_IDs detected: {ids}"


class TestPyreflyDefaultConfig:
    @pytest.mark.unit
    def test_pyrefly_default_config_is_disabled(self) -> None:
        config = PyreflyAdapter().get_default_config()
        assert config.enabled is False

    @pytest.mark.unit
    def test_pyrefly_default_output_format_is_json(self) -> None:
        config = PyreflyAdapter().get_default_config()
        assert config.settings["output_format"] == "json"


class TestPyreflyBuildCommand:
    @pytest.mark.unit
    async def test_pyrefly_build_command_uses_json_format(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()
            cmd = adapter.build_command([Path("module.py")])
        assert "--output-format" in cmd
        assert "json" in cmd

    @pytest.mark.unit
    async def test_pyrefly_build_command_includes_tool_name(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()
            cmd = adapter.build_command([Path("src/")])
        assert cmd[0] == "pyrefly"
        assert "check" in cmd


class TestPyreflyParseOutput:
    @pytest.mark.unit
    async def test_pyrefly_parse_json_output_errors_key(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()
            payload = json.dumps({
                "errors": [
                    {
                        "path": "/tmp/a.py",
                        "line": 5,
                        "column": 10,
                        "name": "bad-return",
                        "concise_description": "Return type mismatch",
                        "severity": "error",
                    }
                ]
            })
            issues = await adapter.parse_output(_make_result(payload))
        assert len(issues) == 1
        assert issues[0].code == "bad-return"
        assert issues[0].severity == "error"

    @pytest.mark.unit
    async def test_pyrefly_parse_json_output_files_key(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()
            payload = json.dumps({
                "files": [
                    {
                        "path": "/tmp/b.py",
                        "errors": [
                            {
                                "line": 1,
                                "column": 1,
                                "name": "missing-type",
                                "description": "Missing type annotation",
                                "severity": "error",
                            }
                        ],
                    }
                ]
            })
            issues = await adapter.parse_output(_make_result(payload))
        assert len(issues) == 1
        assert issues[0].file_path == Path("/tmp/b.py")

    @pytest.mark.unit
    async def test_pyrefly_parse_text_fallback(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()
            issues = await adapter.parse_output(_make_result("not json at all"))
        assert isinstance(issues, list)

    @pytest.mark.unit
    async def test_pyrefly_parse_output_empty(self) -> None:
        with patch.object(PyreflyAdapter, "validate_tool_available", return_value=True):
            adapter = PyreflyAdapter()
            await adapter.init()
            issues = await adapter.parse_output(_make_result(""))
        assert issues == []
