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

    def test_default_excludes_cover_build_artifacts_and_tool_caches(self) -> None:
        """Default QACheckConfig.exclude_patterns must include build/, dist/, and caches.

        betterleaks scans the filesystem in git mode and finds secrets in
        sdist tarballs (``dist/*.tar.gz!``), build copies
        (``build/lib/...``), and tool caches (``.crackerjack/uv/cache/...``).
        These never hold real source secrets; adding them as default
        excludes silences them for every project.
        """
        from crackerjack.adapters.security.betterleaks import BetterleaksAdapter

        cfg = BetterleaksAdapter().get_default_config()
        excludes = set(cfg.exclude_patterns)

        # Build / sdist
        assert "**/build/**" in excludes
        assert "**/dist/**" in excludes
        assert "**/*.egg-info/**" in excludes
        # Crackerjack / uv cache (the source of the false-positive cluster
        # that prompted this change).
        assert "**/.crackerjack/**" in excludes
        assert "**/__pycache__/**" in excludes
        assert "**/*.pyc" in excludes
        # Other tool caches that frequently show up in scans.
        for cache_dir in (
            "**/.ruff_cache/**",
            "**/.mypy_cache/**",
            "**/.pytest_cache/**",
            "**/.cache/**",
            "**/htmlcov/**",
        ):
            assert cache_dir in excludes, (
                f"{cache_dir} should be in default excludes; "
                "add it to BetterleaksAdapter.get_default_config()"
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
        """Default scan_mode='git' produces 'betterleaks git <git-root>' command."""
        cmd = adapter.build_command(files=[])
        assert "betterleaks" in cmd
        assert "git" in cmd
        assert "--report-format" in cmd
        assert "json" in cmd
        # Scan root is the git toplevel (so .betterleaks.toml can be
        # discovered), not a literal ".". The crackerjack repo itself is
        # inside a git checkout, so this path must be populated.
        assert "." not in cmd[2:4], (
            f"Scan root should be the git toplevel, got {cmd[2]!r}"
        )

    async def test_betterleaks_build_command_dir_mode(self, adapter) -> None:
        """scan_mode='dir' produces 'betterleaks dir <git-root>' command."""
        from crackerjack.adapters.security.betterleaks import BetterleaksSettings

        adapter.settings = BetterleaksSettings(
            timeout_seconds=120, max_workers=4, scan_mode="dir"
        )
        cmd = adapter.build_command(files=[])
        assert "dir" in cmd
        assert "git" not in cmd

    async def test_betterleaks_auto_discovers_betterleaks_toml(
        self, adapter, tmp_path, monkeypatch
    ) -> None:
        """When .betterleaks.toml exists at the git root it is passed via --config.

        Patches ``_find_git_root`` to point at ``tmp_path`` so the test
        doesn't depend on the real git layout of the test runner.
        """
        from crackerjack.adapters.security.betterleaks import BetterleaksAdapter

        config = tmp_path / ".betterleaks.toml"
        config.write_text("[extend]\nuseDefault = true\n")
        monkeypatch.setattr(
            BetterleaksAdapter, "_find_git_root", staticmethod(lambda: tmp_path)
        )
        # Ensure the explicit setting stays None so auto-discovery runs.
        adapter.settings.config_file = None

        cmd = adapter.build_command(files=[])

        assert "--config" in cmd, "expected --config when .betterleaks.toml exists"
        assert str(config) in cmd

    async def test_betterleaks_falls_back_to_gitleaks_toml(
        self, adapter, tmp_path, monkeypatch
    ) -> None:
        """When only .gitleaks.toml exists (no .betterleaks.toml), use it."""
        from crackerjack.adapters.security.betterleaks import BetterleaksAdapter

        gitleaks_cfg = tmp_path / ".gitleaks.toml"
        gitleaks_cfg.write_text("[extend]\nuseDefault = true\n")
        monkeypatch.setattr(
            BetterleaksAdapter, "_find_git_root", staticmethod(lambda: tmp_path)
        )
        adapter.settings.config_file = None

        cmd = adapter.build_command(files=[])

        assert "--config" in cmd
        assert str(gitleaks_cfg) in cmd

    async def test_betterleaks_explicit_config_wins_over_auto_discovery(
        self, adapter, tmp_path, monkeypatch
    ) -> None:
        """An explicit config_file setting overrides .betterleaks.toml auto-discovery."""
        from crackerjack.adapters.security.betterleaks import BetterleaksAdapter

        auto_cfg = tmp_path / ".betterleaks.toml"
        auto_cfg.write_text("[extend]\nuseDefault = true\n")
        explicit_cfg = tmp_path / "explicit.toml"
        explicit_cfg.write_text("[extend]\nuseDefault = false\n")
        monkeypatch.setattr(
            BetterleaksAdapter, "_find_git_root", staticmethod(lambda: tmp_path)
        )
        adapter.settings.config_file = explicit_cfg

        cmd = adapter.build_command(files=[])

        assert "--config" in cmd
        config_idx = cmd.index("--config")
        assert cmd[config_idx + 1] == str(explicit_cfg)
        assert str(auto_cfg) not in cmd

    async def test_betterleaks_omits_config_flag_when_no_config_exists(
        self, adapter, tmp_path, monkeypatch
    ) -> None:
        """No .betterleaks.toml and no explicit config -> no --config flag."""
        from crackerjack.adapters.security.betterleaks import BetterleaksAdapter

        # tmp_path has no .betterleaks.toml or .gitleaks.toml
        monkeypatch.setattr(
            BetterleaksAdapter, "_find_git_root", staticmethod(lambda: tmp_path)
        )
        adapter.settings.config_file = None

        cmd = adapter.build_command(files=[])

        assert "--config" not in cmd

    async def test_find_git_root_returns_none_for_non_git_path(
        self, tmp_path
    ) -> None:
        """``_find_git_root`` silently returns None for non-git directories."""
        from crackerjack.adapters.security.betterleaks import BetterleaksAdapter

        result = BetterleaksAdapter._find_git_root(tmp_path)

        assert result is None, (
            "_find_git_root must not raise on non-git paths; the adapter "
            "falls back to cwd in build_command"
        )


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
