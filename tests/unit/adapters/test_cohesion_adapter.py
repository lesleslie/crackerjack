"""Tests for CohesionAdapter — class cohesion measurement via cohesion CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult


@pytest.mark.unit
class TestCohesionBuildCommand:
    """CohesionAdapter.build_command produces correct CLI invocation."""

    @pytest.fixture
    async def adapter(self):
        from crackerjack.adapters.refactor.cohesion import (
            CohesionAdapter,
            CohesionSettings,
        )

        settings = CohesionSettings(timeout_seconds=300, max_workers=4)
        adapter = CohesionAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="1.2.0"),
        ):
            await adapter.init()
        return adapter

    async def test_cohesion_build_command_uses_below_flag(self, adapter) -> None:
        """`-b` (below threshold) flag must be present in command."""
        cmd = adapter.build_command(files=[])
        assert "-b" in cmd, "cohesion build_command must use -b to filter below threshold"

    async def test_cohesion_build_command_uses_directory_flag(self, adapter) -> None:
        """`-d` (directory) flag must be present."""
        cmd = adapter.build_command(files=[])
        assert "-d" in cmd

    async def test_cohesion_build_command_includes_threshold(self, adapter) -> None:
        """Threshold value (70 for default 0.70) must appear in command."""
        cmd = adapter.build_command(files=[])
        assert "70" in cmd


@pytest.mark.unit
class TestCohesionParseOutput:
    """CohesionAdapter.parse_output extracts low-cohesion classes as issues."""

    @pytest.fixture
    async def adapter(self):
        from crackerjack.adapters.refactor.cohesion import (
            CohesionAdapter,
            CohesionSettings,
        )

        settings = CohesionSettings(timeout_seconds=300, max_workers=4)
        adapter = CohesionAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="1.2.0"),
        ):
            await adapter.init()
        return adapter

    async def test_cohesion_parse_below_threshold(self, adapter) -> None:
        """Class at 65% with default threshold 70% → severity == 'error'."""
        raw_output = (
            "File: src/module.py\n"
            "  Class: LowCohesionClass (5:0)\n"
            "    Function: method1 0/3 0.00%\n"
            "    Total: 65.0%\n"
        )
        result = ToolExecutionResult(
            exit_code=0,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.2,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) >= 1
        assert any(i.severity == "error" for i in issues)
        assert any("LowCohesionClass" in i.message for i in issues)

    async def test_cohesion_parse_above_threshold(self, adapter) -> None:
        """Class at 80% with default threshold 70% → no issues emitted."""
        raw_output = (
            "File: src/module.py\n"
            "  Class: HighCohesionClass (5:0)\n"
            "    Function: method1 3/3 100.0%\n"
            "    Total: 80.0%\n"
        )
        result = ToolExecutionResult(
            exit_code=0,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=0.8,
        )
        issues = await adapter.parse_output(result)
        assert issues == []

    async def test_cohesion_parse_empty_output(self, adapter) -> None:
        """Empty output → empty issues list (no crash)."""
        result = ToolExecutionResult(
            exit_code=0,
            raw_output="",
            error_output="",
            execution_time_ms=0.5,
        )
        issues = await adapter.parse_output(result)
        assert issues == []

    async def test_cohesion_parse_file_header_only(self, adapter) -> None:
        """File headers without class entries → no issues."""
        raw_output = "File: src/module.py\n"
        result = ToolExecutionResult(
            exit_code=0,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=0.5,
        )
        issues = await adapter.parse_output(result)
        assert issues == []

    async def test_cohesion_parse_multiple_classes(self, adapter) -> None:
        """Multiple classes: only those below threshold emit issues."""
        raw_output = (
            "File: src/module.py\n"
            "  Class: GoodClass (3:0)\n"
            "    Total: 85.0%\n"
            "  Class: BadClass (20:0)\n"
            "    Total: 40.0%\n"
        )
        result = ToolExecutionResult(
            exit_code=0,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) == 1
        assert "BadClass" in issues[0].message
        assert issues[0].severity == "error"
