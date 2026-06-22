"""Tests for PymetricaAdapter — Halstead Volume, Primitive Obsession, Instability metrics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult


@pytest.mark.unit
class TestPymetricaHooksRegistration:
    def test_pymetrica_in_comprehensive_hooks(self) -> None:
        from crackerjack.config.hooks import COMPREHENSIVE_HOOKS

        names = [h.name for h in COMPREHENSIVE_HOOKS]
        assert "pymetrica" in names, "pymetrica HookDefinition missing from COMPREHENSIVE_HOOKS"


@pytest.mark.unit
class TestPymetricaSettings:
    def test_pymetrica_cc_threshold_is_zero(self) -> None:
        from crackerjack.adapters.complexity.pymetrica import PymetricaSettings

        settings = PymetricaSettings(timeout_seconds=300, max_workers=4)
        assert settings.cc_fail_threshold == 0, (
            "cc_fail_threshold must be 0 to disable CC checks (ruff C901 covers CC)"
        )


@pytest.mark.unit
class TestPymetricaBuildCommand:
    @pytest.fixture
    async def adapter(self):
        from crackerjack.adapters.complexity.pymetrica import (
            PymetricaAdapter,
            PymetricaSettings,
        )

        settings = PymetricaSettings(timeout_seconds=300, max_workers=4)
        adapter = PymetricaAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="1.5.6"),
        ):
            await adapter.init()
        return adapter

    async def test_pymetrica_build_command_uses_run_all(self, adapter) -> None:
        cmd = adapter.build_command(files=[])
        assert "run-all" in cmd

    async def test_pymetrica_build_command_includes_audit_flag(self, adapter) -> None:
        cmd = adapter.build_command(files=[])
        assert "-a" in cmd or "--audit" in cmd


@pytest.mark.unit
class TestPymetricaParseOutput:
    @pytest.fixture
    async def adapter(self):
        from crackerjack.adapters.complexity.pymetrica import (
            PymetricaAdapter,
            PymetricaSettings,
        )

        settings = PymetricaSettings(timeout_seconds=300, max_workers=4)
        adapter = PymetricaAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="1.5.6"),
        ):
            await adapter.init()
        return adapter

    async def test_pymetrica_hv_above_threshold(self, adapter) -> None:
        """HV per LLOC exceeding threshold → severity error."""
        raw_output = (
            "Metric: Halstead Volume\n"
            "Halstead Volume: 25000.00 (35.00 per LLOC)\n"
            "Halstead Volume per LLOC 35.00 exceeds the fail threshold of 30."
            " Reduce the number of unique operators and operands.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=2.0,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) >= 1
        assert any(i.severity == "error" for i in issues)
        assert any("alstead" in i.message or "HV" in i.message or "halstead" in i.message.lower() for i in issues)

    async def test_pymetrica_po_above_threshold(self, adapter) -> None:
        """PO primitives % exceeding threshold → severity error."""
        raw_output = (
            "Metric: Primitive Obsession\n"
            "Primitives found are 12.50% of codebase exceeds the fail threshold of 10%."
            " Consider using type aliases or other data structures.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.5,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) >= 1
        assert any(i.severity == "error" for i in issues)

    async def test_pymetrica_li_above_threshold(self, adapter) -> None:
        """LI instability exceeding threshold → severity error."""
        raw_output = (
            "Metric: Instability\n"
            "Instability 0.85 exceeds the fail threshold of 0.70."
            " Consider adding more stable dependencies.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) >= 1
        assert any(i.severity == "error" for i in issues)

    async def test_pymetrica_cc_never_fails(self, adapter) -> None:
        """CC 'exceeds' messages must NOT produce issues (ruff covers CC)."""
        raw_output = (
            "Metric: Cyclomatic Complexity\n"
            "CC per LLOC 9.50 exceeds the fail threshold of 5."
            " Consider breaking down complex functions.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter.parse_output(result)

        assert issues == [], (
            "Cyclomatic Complexity issues must be suppressed "
            "(ruff C901 already covers this in fast stage)"
        )

    async def test_pymetrica_parse_empty_output(self, adapter) -> None:
        result = ToolExecutionResult(
            exit_code=0,
            raw_output="",
            error_output="",
            execution_time_ms=0.5,
        )
        issues = await adapter.parse_output(result)
        assert issues == []

    async def test_pymetrica_parse_clean_run(self, adapter) -> None:
        """No 'exceeds' messages → empty issues (all metrics within thresholds)."""
        raw_output = (
            "Metric: Halstead Volume\n"
            "Halstead Volume: 1000.00 (18.00 per LLOC)\n"
            "Metric: Primitive Obsession\n"
            "Total codebase primitives: 30 (3.00%)\n"
        )
        result = ToolExecutionResult(
            exit_code=0,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter.parse_output(result)
        assert issues == []
