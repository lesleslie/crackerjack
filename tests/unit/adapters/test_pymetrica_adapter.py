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
        assert "pymetrica" in names, (
            "pymetrica HookDefinition missing from COMPREHENSIVE_HOOKS"
        )


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
        assert any(
            "alstead" in i.message
            or "HV" in i.message
            or "halstead" in i.message.lower()
            for i in issues
        )

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


@pytest.mark.unit
class TestPymetricaAggregateFormat:
    """PR 1: aggregate metrics emit ONE issue per file with code='pymetrica-aggregate'."""

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

    async def test_aggregate_code_is_pymetrica_aggregate(self, adapter) -> None:
        """Halstead Volume exceeds → code='pymetrica-aggregate' (not per-metric)."""
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

        assert len(issues) == 1, f"expected ONE aggregate issue, got {len(issues)}"
        assert issues[0].code == "pymetrica-aggregate", (
            f"code must be 'pymetrica-aggregate' to be classified NON_FIXABLE; "
            f"got {issues[0].code!r}"
        )

    async def test_aggregate_line_number_is_none(self, adapter) -> None:
        """Aggregate metrics have no line number — they describe whole-file metrics."""
        raw_output = (
            "Metric: Halstead Volume\n"
            "Halstead Volume: 25000.00 (35.00 per LLOC)\n"
            "Halstead Volume per LLOC 35.00 exceeds the fail threshold of 30.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=2.0,
        )
        issues = await adapter.parse_output(result)

        assert issues, "expected at least one aggregate issue"
        assert all(i.line_number is None for i in issues), (
            f"aggregate issues must have line_number=None; got {[i.line_number for i in issues]}"
        )

    async def test_aggregate_message_contains_metric_name(self, adapter) -> None:
        """The message preserves the metric name in '[<metric>] <line>' format."""
        raw_output = (
            "Metric: Halstead Volume\n"
            "Halstead Volume: 25000.00 (35.00 per LLOC)\n"
            "Halstead Volume per LLOC 35.00 exceeds the fail threshold of 30.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=2.0,
        )
        issues = await adapter.parse_output(result)

        assert issues, "expected at least one aggregate issue"
        assert issues[0].message.startswith("[Halstead Volume]"), (
            f"message should start with '[Halstead Volume]'; got {issues[0].message!r}"
        )
        assert "exceeds" in issues[0].message, (
            f"message should preserve the 'exceeds' line text; got {issues[0].message!r}"
        )

    async def test_aggregate_one_issue_per_file_for_repeated_violations(
        self, adapter
    ) -> None:
        """Multiple violations for the same metric collapse into ONE aggregate issue."""
        raw_output = (
            "Metric: Halstead Volume\n"
            "Halstead Volume: 25000.00 (35.00 per LLOC)\n"
            "Halstead Volume per LLOC 35.00 exceeds the fail threshold of 30.\n"
            "Halstead Volume per LLOC 36.00 exceeds the fail threshold of 30.\n"
            "Halstead Volume per LLOC 40.00 exceeds the fail threshold of 30.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=2.0,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) == 1, (
            f"expected ONE aggregate issue per file/metric; got {len(issues)}"
        )
        assert issues[0].code == "pymetrica-aggregate"

    async def test_aggregate_file_path_is_not_directory(self, adapter) -> None:
        """file_path must point at the actual file (or a non-directory path), not '.'."""
        raw_output = (
            "Metric: Primitive Obsession\n"
            "Primitives found are 12.50% of codebase exceeds the fail threshold of 10%.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.5,
        )
        issues = await adapter.parse_output(result)

        assert issues, "expected at least one aggregate issue"
        for issue in issues:
            assert str(issue.file_path) != ".", (
                f"file_path must not be the project directory ('.'); got {issue.file_path!r}"
            )

    async def test_aggregate_extracts_file_path_from_line(self, adapter) -> None:
        """When pymetrica emits '<file>: ...exceeds...' the file_path is extracted."""
        raw_output = (
            "Metric: Halstead Volume\n"
            "crackerjack/adapters/complexity/pymetrica.py:"
            " Halstead Volume per LLOC 35.00 exceeds the fail threshold of 30.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=2.0,
        )
        issues = await adapter.parse_output(result)

        assert issues, "expected at least one aggregate issue"
        assert issues[0].file_path == Path(
            "crackerjack/adapters/complexity/pymetrica.py"
        ), f"file_path should be extracted from the line; got {issues[0].file_path!r}"
        assert issues[0].code == "pymetrica-aggregate"

    async def test_cc_still_excluded_from_aggregate(self, adapter) -> None:
        """CC keyword exclusion still suppresses cyclomatic complexity issues."""
        raw_output = (
            "Metric: Cyclomatic Complexity\n"
            "CC per LLOC 9.50 exceeds the fail threshold of 5.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter.parse_output(result)

        assert issues == [], (
            "CC exclusions must still apply — no aggregate issue for Cyclomatic Complexity"
        )

    async def test_aloc_metric_uses_aggregate_code(self, adapter) -> None:
        """ALOC (Average Line Of Code) is an aggregate metric → pymetrica-aggregate."""
        raw_output = "Metric: ALOC\nALOC 45.00 exceeds the fail threshold of 30.\n"
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter.parse_output(result)

        assert issues, "expected at least one aggregate issue for ALOC"
        assert issues[0].code == "pymetrica-aggregate"

    async def test_maintainability_uses_aggregate_code(self, adapter) -> None:
        """Maintainability is an aggregate metric → pymetrica-aggregate."""
        raw_output = (
            "Metric: Maintainability Index\n"
            "Maintainability Index 42.00 exceeds the fail threshold of 65.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter.parse_output(result)

        assert issues, "expected at least one aggregate issue for Maintainability"
        assert issues[0].code == "pymetrica-aggregate"

    async def test_multiple_metrics_yield_distinct_aggregate_issues(
        self, adapter
    ) -> None:
        """Different metrics each get their own aggregate issue."""
        raw_output = (
            "Metric: Halstead Volume\n"
            "Halstead Volume per LLOC 35.00 exceeds the fail threshold of 30.\n"
            "Metric: Primitive Obsession\n"
            "Primitives found are 12.50% of codebase exceeds the fail threshold of 10%.\n"
            "Metric: ALOC\n"
            "ALOC 45.00 exceeds the fail threshold of 30.\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=2.0,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) == 3, (
            f"expected 3 distinct aggregate issues (HV/PO/ALOC); got {len(issues)}"
        )
        assert all(i.code == "pymetrica-aggregate" for i in issues), (
            f"all aggregate issues must use 'pymetrica-aggregate' code; "
            f"got {[i.code for i in issues]}"
        )
