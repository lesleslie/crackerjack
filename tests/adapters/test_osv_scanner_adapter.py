"""Tests for osv-scanner dependency scanner adapter (smoke-level coverage)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.dependency.pip_audit import (
    OsvScannerAdapter,
    OsvScannerSettings,
)


def _osv_payload(vuln_id: str = "PYSEC-2024-1") -> dict[str, object]:
    return {
        "results": [
            {
                "source": {"path": "uv.lock", "type": "lockfile"},
                "packages": [
                    {
                        "package": {
                            "name": "requests",
                            "version": "2.25.0",
                            "ecosystem": "PyPI",
                        },
                        "vulnerabilities": [
                            {
                                "id": vuln_id,
                                "aliases": ["CVE-2024-1"],
                                "summary": "demo",
                            },
                        ],
                    },
                ],
            },
        ],
    }


class TestOsvScannerAdapter:
    """Smoke tests for OsvScannerAdapter."""

    @pytest.mark.asyncio
    async def test_init_default(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            assert isinstance(adapter.settings, OsvScannerSettings)
            assert adapter.tool_name == "osv-scanner"
            assert adapter.adapter_name == "osv-scanner (Dependency Vulnerabilities)"

    @pytest.mark.asyncio
    async def test_build_command_minimal(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            cmd = adapter.build_command([Path("uv.lock")])
            assert cmd[0] == "osv-scanner"
            assert "--format" in cmd and "json" in cmd
            assert "--lockfile" in cmd and "uv.lock" in cmd

    @pytest.mark.asyncio
    async def test_parse_json_with_vulnerabilities(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            result = ToolExecutionResult(
                success=True,
                raw_output=json.dumps(_osv_payload()),
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            issues = await adapter.parse_output(result)
            assert len(issues) == 1
            assert issues[0].code == "PYSEC-2024-1"

    @pytest.mark.asyncio
    async def test_parse_no_vulnerabilities(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            result = ToolExecutionResult(
                success=True,
                raw_output=json.dumps({"results": []}),
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            assert await adapter.parse_output(result) == []

    @pytest.mark.asyncio
    async def test_parse_empty_output(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            result = ToolExecutionResult(
                success=True,
                raw_output="",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            assert await adapter.parse_output(result) == []

    @pytest.mark.asyncio
    async def test_get_default_config(self) -> None:
        adapter = OsvScannerAdapter()
        config = adapter.get_default_config()
        assert config.check_name == "osv-scanner (Dependency Vulnerabilities)"
        assert config.stage == "fast"

    @pytest.mark.asyncio
    async def test_count_affected_packages(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            data = _osv_payload()
            assert adapter._count_affected_packages(data) == 1
