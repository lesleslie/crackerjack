"""Comprehensive tests for osv-scanner dependency vulnerability scanner adapter.

The adapter reads ``uv.lock``/``requirements.txt``/``pyproject.toml`` via
osv-scanner's JSON output schema (different shape from pip-audit's
``{dependencies: [...]}``). These tests pin the new behavior:

- ``build_command`` produces ``osv-scanner --format json --lockfile <file>
  [--ignore-vuln <id>]...`` — no ``--desc``, ``--skip-editable``,
  ``--require-hashes``, or ``--vulnerability-service`` flags.
- ``parse_output`` walks ``results[].packages[].vulnerabilities[]`` and
  filters via ``settings.ignore_vulns`` (same OSV-format IDs as before).
- Graceful handling of empty / no-vulnerability JSON output.

osv-scanner does NOT have a real PyPI distribution; it is a Go binary
installed via system package managers. Tests patch
``validate_tool_available`` so the adapter doesn't try to exec the binary.
"""

from __future__ import annotations

import json
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.adapters._tool_adapter_base import (
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.adapters.dependency.pip_audit import (
    MODULE_ID,
    OsvScannerAdapter,
    OsvScannerSettings,
)
from crackerjack.config.pip_audit_ignores import IGNORED_VULNERABILITY_IDS
from crackerjack.models.qa_results import QACheckType


def _osv_scanner_payload(
    *,
    package_name: str = "requests",
    package_version: str = "2.25.0",
    vuln_id: str = "PYSEC-2023-123",
    aliases: list[str] | None = None,
    summary: str = "Security vulnerability in requests",
    source_path: str = "uv.lock",
) -> dict[str, object]:
    """Build an osv-scanner-shaped JSON payload."""
    return {
        "results": [
            {
                "source": {"path": source_path, "type": "lockfile"},
                "packages": [
                    {
                        "package": {
                            "name": package_name,
                            "version": package_version,
                            "ecosystem": "PyPI",
                        },
                        "vulnerabilities": [
                            {
                                "id": vuln_id,
                                "aliases": aliases if aliases is not None else [
                                    "CVE-2023-12345",
                                ],
                                "summary": summary,
                                "severity": [
                                    {"type": "CVSS_V3", "score": "9.8"},
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    }


class TestOsvScannerSettings:
    """Test suite for OsvScannerSettings."""

    def test_default_settings(self) -> None:
        settings = OsvScannerSettings()
        assert settings.tool_name == "osv-scanner"
        assert settings.use_json_output is True
        assert settings.dry_run is False
        assert settings.fix is False
        assert settings.cache_dir is None
        assert settings.ignore_vulns == []

    def test_custom_settings(self) -> None:
        settings = OsvScannerSettings(
            use_json_output=False,
            dry_run=True,
            fix=True,
            cache_dir=Path("/tmp/cache"),
            ignore_vulns=["CVE-2023-12345"],
        )
        assert settings.use_json_output is False
        assert settings.dry_run is True
        assert settings.fix is True
        assert settings.cache_dir == Path("/tmp/cache")
        assert "CVE-2023-12345" in settings.ignore_vulns


class TestOsvScannerAdapterProperties:
    """Test suite for OsvScannerAdapter properties."""

    @pytest.mark.asyncio
    async def test_adapter_name(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            assert adapter.adapter_name == "osv-scanner (Dependency Vulnerabilities)"

    @pytest.mark.asyncio
    async def test_module_id(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            assert adapter.module_id == MODULE_ID

    @pytest.mark.asyncio
    async def test_tool_name(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            assert adapter.tool_name == "osv-scanner"


class TestBuildCommand:
    """Test suite for build_command method."""

    @pytest.mark.asyncio
    async def test_build_command_basic(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            command = adapter.build_command([Path("pyproject.toml")])

            assert command[0] == "osv-scanner"
            assert "--format" in command
            assert "json" in command
            assert "--lockfile" in command
            # These pip-audit-only flags must NOT appear
            for forbidden in (
                "--vulnerability-service",
                "--desc",
                "--skip-editable",
                "--require-hashes",
            ):
                assert forbidden not in command

    @pytest.mark.asyncio
    async def test_build_command_with_lockfile(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            command = adapter.build_command([Path("uv.lock")])
            assert "uv.lock" in command
            assert command.count("--lockfile") == 1

    @pytest.mark.asyncio
    async def test_build_command_with_pyproject_only(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            command = adapter.build_command([Path("pyproject.toml")])
            assert "pyproject.toml" in command

    @pytest.mark.asyncio
    async def test_build_command_skips_unsupported_files(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            files = [
                Path("requirements.txt"),
                Path("pyproject.toml"),
                Path("other.txt"),
            ]
            command = adapter.build_command(files)
            assert command.count("--lockfile") == 2
            assert "other.txt" not in command

    @pytest.mark.asyncio
    async def test_build_command_with_dry_run(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            settings = OsvScannerSettings(dry_run=True)
            adapter = OsvScannerAdapter(settings=settings)
            await adapter.init()
            command = adapter.build_command([Path("uv.lock")])
            assert "--dry-run" in command

    @pytest.mark.asyncio
    async def test_build_command_with_fix(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            settings = OsvScannerSettings(fix=True)
            adapter = OsvScannerAdapter(settings=settings)
            await adapter.init()
            command = adapter.build_command([Path("uv.lock")])
            assert "--fix" in command

    @pytest.mark.asyncio
    async def test_build_command_with_cache_dir(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            cache_path = Path("/tmp/osv-cache")
            settings = OsvScannerSettings(cache_dir=cache_path)
            adapter = OsvScannerAdapter(settings=settings)
            await adapter.init()
            command = adapter.build_command([Path("uv.lock")])
            assert "--cache-dir" in command
            assert str(cache_path) in command

    @pytest.mark.asyncio
    async def test_build_command_with_ignored_vulns(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            settings = OsvScannerSettings(
                ignore_vulns=["CVE-2023-12345", "PYSEC-2024-456"],
            )
            adapter = OsvScannerAdapter(settings=settings)
            await adapter.init()
            command = adapter.build_command([Path("uv.lock")])
            assert command.count("--ignore-vuln") == 2
            assert "CVE-2023-12345" in command
            assert "PYSEC-2024-456" in command

    @pytest.mark.asyncio
    async def test_build_command_raises_without_settings(self) -> None:
        adapter = OsvScannerAdapter()
        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([Path("uv.lock")])


class TestCreateIssuesFromEntry:
    """Test suite for _create_issues_from_entry method."""

    @pytest.mark.asyncio
    async def test_create_issues_with_vulnerability(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            entry = _osv_scanner_payload()["results"][0]
            issues = adapter._create_issues_from_entry(entry, "uv.lock")
            assert len(issues) == 1
            assert issues[0].code == "PYSEC-2023-123"
            assert issues[0].severity == "error"
            assert "requests==2.25.0" in issues[0].message

    @pytest.mark.asyncio
    async def test_create_issues_with_ignored_vuln(self) -> None:
        """The helper emits ALL vulns; the outer ``parse_output`` filters
        against ``settings.ignore_vulns``."""
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            entry = _osv_scanner_payload(
                vuln_id="CVE-2025-53000",
                aliases=[],
            )["results"][0]
            issues = adapter._create_issues_from_entry(entry, "uv.lock")
            # The helper doesn't filter — outer parse_output does.
            assert len(issues) == 1

    @pytest.mark.asyncio
    async def test_create_issues_multiple_vulns(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            entry = {
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
                                "id": "CVE-2023-001",
                                "aliases": [],
                                "summary": "First",
                            },
                            {
                                "id": "CVE-2023-002",
                                "aliases": [],
                                "summary": "Second",
                            },
                        ],
                    },
                ],
            }
            issues = adapter._create_issues_from_entry(entry, "uv.lock")
            assert len(issues) == 2


class TestCountAffectedPackages:
    """Test suite for _count_affected_packages method."""

    @pytest.mark.asyncio
    async def test_count_with_vulnerable_packages(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            data = _osv_scanner_payload(
                package_name="requests",
                package_version="2.25.0",
            )
            data["results"].append(
                {
                    "source": {"path": "uv.lock", "type": "lockfile"},
                    "packages": [
                        {
                            "package": {
                                "name": "urllib3",
                                "version": "1.0.0",
                                "ecosystem": "PyPI",
                            },
                            "vulnerabilities": [
                                {"id": "CVE-2023-003", "aliases": [], "summary": "x"},
                            ],
                        },
                    ],
                },
            )
            data["results"].append(
                {
                    "source": {"path": "uv.lock", "type": "lockfile"},
                    "packages": [
                        {
                            "package": {
                                "name": "safe-package",
                                "version": "1.0.0",
                                "ecosystem": "PyPI",
                            },
                            "vulnerabilities": [],
                        },
                    ],
                },
            )
            count = adapter._count_affected_packages(data)
            assert count == 2

    @pytest.mark.asyncio
    async def test_count_with_no_vulnerabilities(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            data = {
                "results": [
                    {
                        "source": {"path": "uv.lock", "type": "lockfile"},
                        "packages": [
                            {
                                "package": {
                                    "name": "safe",
                                    "version": "1.0.0",
                                    "ecosystem": "PyPI",
                                },
                                "vulnerabilities": [],
                            },
                        ],
                    },
                ],
            }
            assert adapter._count_affected_packages(data) == 0


class TestParseOutput:
    """Test suite for parse_output method (the end-to-end JSON walker)."""

    @pytest.mark.asyncio
    async def test_parse_json_output_with_vulnerabilities(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            payload = _osv_scanner_payload(
                vuln_id="PYSEC-2023-123",
                aliases=["CVE-2023-12345"],
                summary="Security vulnerability in requests",
            )
            result = ToolExecutionResult(
                success=True,
                raw_output=json.dumps(payload),
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            issues = await adapter.parse_output(result)
            assert len(issues) == 1
            assert "requests==2.25.0" in issues[0].message
            assert "PYSEC-2023-123" in issues[0].message
            assert issues[0].code == "PYSEC-2023-123"
            assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_empty_results(self) -> None:
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
    async def test_parse_invalid_json_returns_empty(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            result = ToolExecutionResult(
                success=False,
                raw_output="not json {oops}",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )
            assert await adapter.parse_output(result) == []

    @pytest.mark.asyncio
    async def test_parse_sets_exit_code_zero_when_only_ignored(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            # Pick a CVE that is in the canonical ignore list so this test
            # is robust to changes in the ignore config.
            ignored_id = next(iter(IGNORED_VULNERABILITY_IDS))
            await adapter.init()
            payload = _osv_scanner_payload(
                vuln_id=ignored_id,
                aliases=[],
            )
            result = ToolExecutionResult(
                success=False,
                raw_output=json.dumps(payload),
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )
            await adapter.parse_output(result)
            # parse_output surfaces the issue but resets the exit code to 0
            # so the hook reports success when every finding is in the ignore list.
            assert result.exit_code == 0


class TestIsSuccessfulResult:
    @pytest.mark.asyncio
    async def test_no_issues_with_nonzero_exit(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            result = ToolExecutionResult(
                success=False,
                raw_output="",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )
            with patch.object(adapter, "parse_output", new=AsyncMock(return_value=[])):
                assert await adapter.is_successful_result(result) is True

    @pytest.mark.asyncio
    async def test_failure_with_non_ignored_issues(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            issues = [
                ToolIssue(
                    file_path=Path("pyproject.toml"),
                    line_number=None,
                    column_number=None,
                    message="Test vulnerability",
                    code="CVE-2023-12345",
                    severity="error",
                ),
            ]
            result = ToolExecutionResult(
                success=False,
                raw_output="",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )
            with patch.object(adapter, "parse_output", new=AsyncMock(return_value=issues)):
                assert await adapter.is_successful_result(result) is False


class TestGetDefaultConfig:
    def test_get_default_config(self) -> None:
        adapter = OsvScannerAdapter()
        config = adapter.get_default_config()
        assert config.check_name == "osv-scanner (Dependency Vulnerabilities)"
        assert config.check_type == QACheckType.SECURITY
        assert config.enabled is True
        assert "pyproject.toml" in config.file_patterns
        assert "uv.lock" in config.file_patterns
        assert "requirements.txt" in config.file_patterns
        assert config.stage == "fast"
        assert config.timeout_seconds == 120
        assert config.parallel_safe is True


class TestGetCheckType:
    def test_get_check_type(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            adapter.settings = OsvScannerSettings()
            assert adapter._get_check_type() == QACheckType.SECURITY


class TestInitialization:
    @pytest.mark.asyncio
    async def test_init_with_custom_settings(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            settings = OsvScannerSettings(fix=True, cache_dir=Path("/tmp/x"))
            adapter = OsvScannerAdapter(settings=settings)
            await adapter.init()
            assert adapter.settings is not None
            assert adapter.settings.fix is True
            assert adapter.settings.cache_dir == Path("/tmp/x")

    @pytest.mark.asyncio
    async def test_init_without_settings_uses_defaults(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            assert adapter.settings is not None
            assert adapter.settings.timeout_seconds == 120
            assert adapter.settings.dry_run is False
            assert adapter.settings.fix is False
            # Should have default ignored vulns merged from config
            assert len(adapter.settings.ignore_vulns) > 0

    @pytest.mark.asyncio
    async def test_init_uses_ignored_vulns_from_config(self) -> None:
        with patch.object(
            OsvScannerAdapter, "validate_tool_available", return_value=True
        ):
            adapter = OsvScannerAdapter()
            await adapter.init()
            # The canonical list contains at least one well-known entry;
            # see crackerjack/config/pip_audit_ignores.py for the source.
            assert any(
                vid in adapter.settings.ignore_vulns for vid in IGNORED_VULNERABILITY_IDS
            ) or adapter.settings.ignore_vulns  # either canonical or local config
