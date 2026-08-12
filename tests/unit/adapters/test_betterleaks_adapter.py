"""Tests for BetterleaksAdapter — Go-binary secrets gate replacing gitleaks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult


@pytest.mark.unit
class TestBetterleaksHooksRegistration:
    """betterleaks must be in COMPREHENSIVE_HOOKS; gitleaks must be disabled."""

    def test_betterleaks_in_comprehensive_hooks(self) -> None:
        from crackerjack.config.hooks import COMPREHENSIVE_HOOKS

        names = [h.name for h in COMPREHENSIVE_HOOKS]
        assert "betterleaks" in names, (
            "betterleaks HookDefinition missing from COMPREHENSIVE_HOOKS"
        )

    def test_gitleaks_disabled_in_hooks(self) -> None:
        from crackerjack.config.hooks import COMPREHENSIVE_HOOKS

        gitleaks = next((h for h in COMPREHENSIVE_HOOKS if h.name == "gitleaks"), None)
        assert gitleaks is not None, "gitleaks entry missing from COMPREHENSIVE_HOOKS"
        assert gitleaks.disabled is True, (
            "gitleaks must be disabled=True now that betterleaks is the primary gate"
        )


@pytest.mark.unit
class TestBetterleaksBuildCommand:
    """BetterleaksAdapter.build_command produces correct CLI invocation."""

    @pytest.fixture
    async def adapter(self):
        from crackerjack.adapters.security.betterleaks import (
            BetterleaksAdapter,
            BetterleaksSettings,
        )

        settings = BetterleaksSettings(timeout_seconds=120, max_workers=4)
        adapter = BetterleaksAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="0.1.0"),
        ):
            await adapter.init()
        return adapter

    async def test_betterleaks_build_command_git_mode(self, adapter) -> None:
        """Default scan_mode='git' produces 'betterleaks git .' command."""
        cmd = adapter.build_command(files=[])
        assert "betterleaks" in cmd
        assert "git" in cmd
        assert "--report-format" in cmd
        assert "json" in cmd

    async def test_betterleaks_build_command_dir_mode(self, adapter) -> None:
        """scan_mode='dir' produces 'betterleaks dir .' command."""
        from crackerjack.adapters.security.betterleaks import BetterleaksSettings

        adapter.settings = BetterleaksSettings(
            timeout_seconds=120, max_workers=4, scan_mode="dir"
        )
        cmd = adapter.build_command(files=[])
        assert "dir" in cmd
        assert "git" not in cmd


@pytest.mark.unit
class TestBetterleaksParseOutput:
    """BetterleaksAdapter.parse_output reads JSON report and maps findings."""

    @pytest.fixture
    async def adapter(self):
        from crackerjack.adapters.security.betterleaks import (
            BetterleaksAdapter,
            BetterleaksSettings,
        )

        settings = BetterleaksSettings(timeout_seconds=120, max_workers=4)
        adapter = BetterleaksAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="0.1.0"),
        ):
            await adapter.init()
        return adapter

    async def test_betterleaks_parse_json_high_entropy(
        self, adapter, tmp_path
    ) -> None:
        """Finding with entropy > 4.0 maps to severity='error'."""
        report = tmp_path / "betterleaks-report.json"
        report.write_text(
            json.dumps(
                [
                    {
                        "Description": "AWS access key",
                        "File": "config.py",
                        "StartLine": 10,
                        "StartColumn": 5,
                        "RuleID": "aws-access-key",
                        "Tags": ["aws"],
                        "Entropy": 5.2,
                        "Secret": "[REDACTED]",
                    }
                ]
            )
        )
        adapter.settings.report_path = report

        result = ToolExecutionResult(
            exit_code=1,
            raw_output="",
            error_output="",
            execution_time_ms=0.5,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "AWS access key" in issues[0].message

    async def test_betterleaks_parse_json_low_entropy(
        self, adapter, tmp_path
    ) -> None:
        """Finding with entropy <= 4.0 maps to severity='warning'."""
        report = tmp_path / "betterleaks-report.json"
        report.write_text(
            json.dumps(
                [
                    {
                        "Description": "Low-entropy placeholder",
                        "File": "config.py",
                        "StartLine": 5,
                        "StartColumn": 1,
                        "RuleID": "generic-api-key",
                        "Tags": [],
                        "Entropy": 3.1,
                        "Secret": "[REDACTED]",
                    }
                ]
            )
        )
        adapter.settings.report_path = report

        result = ToolExecutionResult(
            exit_code=1,
            raw_output="",
            error_output="",
            execution_time_ms=0.5,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].severity == "warning"

    async def test_betterleaks_parse_json_empty_list(self, adapter, tmp_path) -> None:
        """Empty findings list → empty issues (clean scan)."""
        report = tmp_path / "betterleaks-report.json"
        report.write_text(json.dumps([]))
        adapter.settings.report_path = report

        result = ToolExecutionResult(
            exit_code=0,
            raw_output="",
            error_output="",
            execution_time_ms=0.5,
        )
        issues = await adapter.parse_output(result)
        assert issues == []

    async def test_betterleaks_parse_json_missing_report_emits_error(
        self, adapter, tmp_path
    ) -> None:
        """Missing report file after non-zero exit → fail-closed: emit error issue."""
        adapter.settings.report_path = tmp_path / "nonexistent-report.json"

        result = ToolExecutionResult(
            exit_code=1,  # non-zero = tool failed or found secrets
            raw_output="",
            error_output="betterleaks: command not found",
            execution_time_ms=0.0,
        )
        issues = await adapter.parse_output(result)

        # Must NOT return [] — that would silently disable the secrets gate
        assert len(issues) >= 1
        assert any(i.severity == "error" for i in issues)
        assert any("betterleaks" in i.message.lower() for i in issues)

    async def test_betterleaks_missing_report_on_zero_exit_is_clean(
        self, adapter, tmp_path
    ) -> None:
        """Missing report on exit code 0 (no findings, tool ran OK) → [] is safe."""
        adapter.settings.report_path = tmp_path / "nonexistent-report.json"

        result = ToolExecutionResult(
            exit_code=0,
            raw_output="No leaks found",
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter.parse_output(result)
        # exit 0 + no report = no secrets found (betterleaks may skip empty report)
        assert issues == []

    async def test_betterleaks_panic_with_stale_report_does_not_invent_issues(
        self, adapter, tmp_path
    ) -> None:
        """Panic (exit 2) with a stale report on disk → gate-failure, NOT 10 issues.

        Regression for the case where betterleaks 1.7.4 panics on a malformed
        .gz file inside a vendored test fixture (e.g. joblib's pickle gz). If a
        previous successful run left a report file behind, the parser must NOT
        parse it as the current run's findings — it must surface the panic as
        a single gate-failure and discard the stale file.
        """
        report = tmp_path / "betterleaks-report.json"
        # Stale findings from a previous successful run
        report.write_text(
            json.dumps(
                [
                    {
                        "Description": f"Stale finding {i}",
                        "File": f"src/secret{i}.py",
                        "StartLine": i + 1,
                        "StartColumn": 1,
                        "RuleID": "stale-rule",
                        "Tags": ["stale"],
                        "Entropy": 5.0,
                        "Secret": "[REDACTED]",
                    }
                    for i in range(10)
                ]
            )
        )
        adapter.settings.report_path = report

        result = ToolExecutionResult(
            exit_code=2,  # Go runtime panic
            raw_output="",
            error_output=(
                "panic: runtime error: invalid memory address or nil pointer "
                "dereference\ngoroutine ...\ngithub.com/klauspost/compress/gzip..."
            ),
            execution_time_ms=0.5,
        )
        issues = await adapter.parse_output(result)

        # Must surface the panic as a gate failure — never as 10 fabricated issues
        assert len(issues) == 1, (
            f"Expected exactly 1 gate-failure ToolIssue, got {len(issues)}. "
            "Stale report must NOT be parsed as current-run findings."
        )
        assert issues[0].code == "betterleaks-gate-failure"
        assert issues[0].severity == "error"
        assert "2" in issues[0].message  # exit code surfaced for diagnosis
        assert not report.exists(), (
            "Stale report must be deleted so subsequent runs start clean"
        )

    async def test_betterleaks_build_command_clears_stale_report(
        self, adapter, tmp_path
    ) -> None:
        """build_command deletes any existing report so panic'd runs don't inherit it."""
        report = tmp_path / "betterleaks-report.json"
        report.write_text("[{\"File\": \"stale.py\", \"StartLine\": 1}]")
        assert report.exists()

        adapter.settings.report_path = report
        _ = adapter.build_command(files=[])

        assert not report.exists(), (
            "build_command must unlink any stale report before invoking "
            "betterleaks so a panic in the new run cannot be confused with "
            "a successful previous run."
        )
