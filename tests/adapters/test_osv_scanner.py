"""Comprehensive tests for PipAudit dependency vulnerability scanner adapter."""

import json
import logging
import typing as t
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.dependency.pip_audit import (
    PipAuditAdapter,
    PipAuditSettings,
    MODULE_ID,
)
from crackerjack.config.pip_audit_ignores import IGNORED_VULNERABILITY_IDS
from crackerjack.models.qa_results import QACheckType


class TestPipAuditSettings:
    """Test suite for PipAuditSettings."""

    def test_default_settings(self):
        """Test PipAuditSettings default values."""
        settings = PipAuditSettings()
        assert settings.tool_name == "pip-audit"
        assert settings.use_json_output is True
        assert settings.require_hashes is False
        assert settings.vulnerability_service == "osv"
        assert settings.skip_editable is True
        assert settings.dry_run is False
        assert settings.fix is False
        assert settings.output_desc is True
        assert settings.cache_dir is None
        assert settings.ignore_vulns == []

    def test_custom_settings(self):
        """Test PipAuditSettings with custom values."""
        settings = PipAuditSettings(
            require_hashes=True,
            vulnerability_service="pypi",
            skip_editable=False,
            fix=True,
            cache_dir=Path("/tmp/cache"),
            ignore_vulns=["CVE-2023-12345"],
        )
        assert settings.require_hashes is True
        assert settings.vulnerability_service == "pypi"
        assert settings.skip_editable is False
        assert settings.fix is True
        assert settings.cache_dir == Path("/tmp/cache")
        assert "CVE-2023-12345" in settings.ignore_vulns


class TestPipAuditAdapterProperties:
    """Test suite for PipAuditAdapter properties."""

    @pytest.mark.asyncio
    async def test_adapter_name(self):
        """Test adapter_name property."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()
            assert adapter.adapter_name == "pip-audit (Dependency Vulnerabilities)"

    @pytest.mark.asyncio
    async def test_module_id(self):
        """Test module_id is correct UUID."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()
            assert adapter.module_id == MODULE_ID

    @pytest.mark.asyncio
    async def test_tool_name(self):
        """Test tool_name property."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()
            assert adapter.tool_name == "pip-audit"


class TestBuildCommand:
    """Test suite for build_command method."""

    @pytest.mark.asyncio
    async def test_build_command_basic(self):
        """Test building a basic pip-audit command."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            files = [Path("pyproject.toml")]
            command = adapter.build_command(files)

            assert "pip-audit" in command
            assert "--format" in command
            assert "json" in command
            assert "--vulnerability-service" in command
            assert "osv" in command
            assert "--desc" in command
            assert "--skip-editable" in command

    @pytest.mark.asyncio
    async def test_build_command_with_requirements_file(self):
        """Test building command with requirements.txt."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            files = [Path("requirements.txt")]
            command = adapter.build_command(files)

            assert "-r" in command
            assert "requirements.txt" in command

    @pytest.mark.asyncio
    async def test_build_command_with_pyproject_toml(self):
        """Test building command with pyproject.toml."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            files = [Path("pyproject.toml")]
            command = adapter.build_command(files)

            assert "-r" in command
            assert "pyproject.toml" in command

    @pytest.mark.asyncio
    async def test_build_command_with_multiple_files(self):
        """Test building command with multiple dependency files."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            files = [Path("requirements.txt"), Path("pyproject.toml"), Path("other.txt")]
            command = adapter.build_command(files)

            # Only requirements.txt and pyproject.toml should get -r flag
            assert command.count("-r") == 2

    @pytest.mark.asyncio
    async def test_build_command_with_pypi_service(self):
        """Test building command with pypi vulnerability service."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings(vulnerability_service="pypi")
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path("pyproject.toml")]
            command = adapter.build_command(files)

            assert "--vulnerability-service" in command
            assert "pypi" in command

    @pytest.mark.asyncio
    async def test_build_command_with_require_hashes(self):
        """Test building command with require_hashes."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings(require_hashes=True)
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path("pyproject.toml")]
            command = adapter.build_command(files)

            assert "--require-hashes" in command

    @pytest.mark.asyncio
    async def test_build_command_skip_editable_false(self):
        """Test building command with skip_editable disabled."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings(skip_editable=False)
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path("pyproject.toml")]
            command = adapter.build_command(files)

            assert "--skip-editable" not in command

    @pytest.mark.asyncio
    async def test_build_command_with_dry_run(self):
        """Test building command with dry_run enabled."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings(dry_run=True)
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path("pyproject.toml")]
            command = adapter.build_command(files)

            assert "--dry-run" in command

    @pytest.mark.asyncio
    async def test_build_command_with_fix(self):
        """Test building command with fix enabled."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings(fix=True)
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path("pyproject.toml")]
            command = adapter.build_command(files)

            assert "--fix" in command

    @pytest.mark.asyncio
    async def test_build_command_with_cache_dir(self):
        """Test building command with cache_dir."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            cache_path = Path("/tmp/pip-audit-cache")
            settings = PipAuditSettings(cache_dir=cache_path)
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path("pyproject.toml")]
            command = adapter.build_command(files)

            assert "--cache-dir" in command
            assert str(cache_path) in command

    @pytest.mark.asyncio
    async def test_build_command_with_ignored_vulns(self):
        """Test building command with ignored vulnerabilities."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings(ignore_vulns=["CVE-2023-12345", "PYSEC-2024-456"])
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path("pyproject.toml")]
            command = adapter.build_command(files)

            assert "--ignore-vuln" in command
            assert "CVE-2023-12345" in command
            assert "PYSEC-2024-456" in command

    @pytest.mark.asyncio
    async def test_build_command_raises_without_settings(self):
        """Test build_command raises RuntimeError without settings."""
        adapter = PipAuditAdapter()
        files = [Path("pyproject.toml")]

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command(files)


class TestAddCommandOptions:
    """Test suite for _add_* command option methods."""

    @pytest.mark.asyncio
    async def test_add_format_options(self):
        """Test _add_format_options adds correct flags."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            cmd = []
            adapter._add_format_options(cmd, t.cast(PipAuditSettings, adapter.settings))
            assert "--format" in cmd
            assert "json" in cmd

    @pytest.mark.asyncio
    async def test_add_vulnerability_service(self):
        """Test _add_vulnerability_service adds correct flag."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            adapter.settings = PipAuditSettings(vulnerability_service="pypi")
            await adapter.init()

            cmd = []
            adapter._add_vulnerability_service(cmd, adapter.settings)
            assert "--vulnerability-service" in cmd
            assert "pypi" in cmd

    @pytest.mark.asyncio
    async def test_add_output_options(self):
        """Test _add_output_options adds --desc when enabled."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            adapter.settings = PipAuditSettings(output_desc=True)
            await adapter.init()

            cmd = []
            adapter._add_output_options(cmd, adapter.settings)
            assert "--desc" in cmd

    @pytest.mark.asyncio
    async def test_add_output_options_disabled(self):
        """Test _add_output_options doesn't add --desc when disabled."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            adapter.settings = PipAuditSettings(output_desc=False)
            await adapter.init()

            cmd = []
            adapter._add_output_options(cmd, adapter.settings)
            assert "--desc" not in cmd

    @pytest.mark.asyncio
    async def test_add_skippable_options(self):
        """Test _add_skippable_options adds correct flags."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            adapter.settings = PipAuditSettings(skip_editable=True, require_hashes=True)
            await adapter.init()

            cmd = []
            adapter._add_skippable_options(cmd, adapter.settings)
            assert "--skip-editable" in cmd
            assert "--require-hashes" in cmd

    @pytest.mark.asyncio
    async def test_add_fix_options(self):
        """Test _add_fix_options adds correct flags."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            adapter.settings = PipAuditSettings(dry_run=True, fix=True)
            await adapter.init()

            cmd = []
            adapter._add_fix_options(cmd, adapter.settings)
            assert "--dry-run" in cmd
            assert "--fix" in cmd

    @pytest.mark.asyncio
    async def test_add_cache_dir(self):
        """Test _add_cache_dir adds correct flags."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            cache_path = Path("/tmp/cache")
            adapter.settings = PipAuditSettings(cache_dir=cache_path)
            await adapter.init()

            cmd = []
            adapter._add_cache_dir(cmd, adapter.settings)
            assert "--cache-dir" in cmd
            assert str(cache_path) in cmd

    @pytest.mark.asyncio
    async def test_add_ignored_vulns(self):
        """Test _add_ignored_vulns adds correct flags."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            adapter.settings = PipAuditSettings(ignore_vulns=["CVE-2023-1", "CVE-2023-2"])
            await adapter.init()

            cmd = []
            adapter._add_ignored_vulns(cmd, adapter.settings)
            assert "--ignore-vuln" in cmd
            assert "CVE-2023-1" in cmd
            assert "CVE-2023-2" in cmd


class TestBuildVulnerabilityMessage:
    """Test suite for _build_vulnerability_message method."""

    @pytest.mark.asyncio
    async def test_build_message_with_all_components(self):
        """Test building message with all components."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            message = adapter._build_vulnerability_message(
                package_name="requests",
                package_version="2.25.0",
                vuln_id="PYSEC-2023-123",
                description="A security vulnerability was found",
                fix_versions=["2.31.0", "2.32.0", "2.33.0"],
                aliases=["CVE-2023-12345", "GHSA-abcd"],
            )

            assert "requests==2.25.0" in message
            assert "PYSEC-2023-123" in message
            assert "CVE-2023-12345" in message
            assert "Fix available: 2.31.0, 2.32.0, 2.33.0" in message

    @pytest.mark.asyncio
    async def test_build_message_with_long_description(self):
        """Test building message truncates long descriptions."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            long_desc = "A" * 150  # More than 100 chars
            message = adapter._build_vulnerability_message(
                package_name="requests",
                package_version="2.25.0",
                vuln_id="PYSEC-2023-123",
                description=long_desc,
                fix_versions=["2.31.0"],
                aliases=["CVE-2023-12345"],
            )

            assert "..." in message
            assert len(message) < len(long_desc) + 100

    @pytest.mark.asyncio
    async def test_build_message_without_cve(self):
        """Test building message without CVE in aliases."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            # Only CVE aliases are included in the message
            message = adapter._build_vulnerability_message(
                package_name="requests",
                package_version="2.25.0",
                vuln_id="PYSEC-2023-123",
                description="Security issue",
                fix_versions=["2.31.0"],
                aliases=["GHSA-abcd", "VENDOR-123"],  # No CVE
            )

            # GHSA and VENDOR are not CVE, so they shouldn't be in message
            assert "GHSA-abcd" not in message
            assert "VENDOR-123" not in message
            assert "requests==2.25.0" in message

    @pytest.mark.asyncio
    async def test_build_message_without_fix_versions(self):
        """Test building message without fix versions."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            message = adapter._build_vulnerability_message(
                package_name="requests",
                package_version="2.25.0",
                vuln_id="PYSEC-2023-123",
                description="Security issue",
                fix_versions=[],
                aliases=[],
            )

            assert "Fix available" not in message


class TestCreateIssuesFromDependencies:
    """Test suite for _create_issues_from_dependencies method."""

    @pytest.mark.asyncio
    async def test_create_issues_with_vulnerabilities(self):
        """Test creating issues from dependencies with vulnerabilities."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            data = {
                "dependencies": [
                    {
                        "name": "requests",
                        "version": "2.25.0",
                        "vulns": [
                            {
                                "id": "CVE-2023-12345",
                                "description": "Security vulnerability",
                                "fix_versions": ["2.31.0"],
                                "aliases": ["CVE-2023-12345"],
                            }
                        ],
                    }
                ]
            }

            issues = adapter._create_issues_from_dependencies(data)

            assert len(issues) == 1
            assert issues[0].file_path == Path("pyproject.toml")
            assert issues[0].code == "CVE-2023-12345"
            assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_create_issues_with_ignored_vulns(self):
        """Test that ignored vulnerabilities are not created as issues."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            # Use a CVE that is in IGNORED_VULNERABILITY_IDS
            adapter = PipAuditAdapter()
            await adapter.init()

            data = {
                "dependencies": [
                    {
                        "name": "some-package",
                        "version": "1.0.0",
                        "vulns": [
                            {
                                "id": "CVE-2025-53000",  # In ignored list
                                "description": "Ignored vulnerability",
                                "fix_versions": [],
                                "aliases": [],
                            }
                        ],
                    }
                ]
            }

            issues = adapter._create_issues_from_dependencies(data)

            # CVE-2025-53000 is in IGNORED_VULNERABILITY_IDS, should be skipped
            assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_create_issues_multiple_deps(self):
        """Test creating issues from multiple dependencies."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            data = {
                "dependencies": [
                    {
                        "name": "requests",
                        "version": "2.25.0",
                        "vulns": [
                            {"id": "CVE-2023-001", "description": "Vuln 1", "fix_versions": [], "aliases": []},
                            {"id": "CVE-2023-002", "description": "Vuln 2", "fix_versions": [], "aliases": []},
                        ],
                    },
                    {
                        "name": "urllib3",
                        "version": "1.0.0",
                        "vulns": [
                            {"id": "CVE-2023-003", "description": "Vuln 3", "fix_versions": [], "aliases": []},
                        ],
                    },
                ]
            }

            issues = adapter._create_issues_from_dependencies(data)

            # 3 total vulnerabilities
            assert len(issues) == 3


class TestCountAffectedPackages:
    """Test suite for _count_affected_packages method."""

    @pytest.mark.asyncio
    async def test_count_with_vulnerable_packages(self):
        """Test counting packages with vulnerabilities."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            data = {
                "dependencies": [
                    {"name": "requests", "version": "2.25.0", "vulns": [{"id": "1"}]},
                    {"name": "urllib3", "version": "1.0.0", "vulns": [{"id": "2"}]},
                    {"name": "safe-package", "version": "1.0.0", "vulns": []},
                ]
            }

            count = adapter._count_affected_packages(data)
            assert count == 2

    @pytest.mark.asyncio
    async def test_count_with_no_vulnerable_packages(self):
        """Test counting with no vulnerable packages."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            data = {
                "dependencies": [
                    {"name": "safe1", "version": "1.0.0", "vulns": []},
                    {"name": "safe2", "version": "2.0.0", "vulns": []},
                ]
            }

            count = adapter._count_affected_packages(data)
            assert count == 0


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_json_output_with_vulnerabilities(self):
        """Test parsing JSON output with vulnerabilities."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            json_output = json.dumps({
                "dependencies": [
                    {
                        "name": "requests",
                        "version": "2.25.0",
                        "vulns": [
                            {
                                "id": "PYSEC-2023-123",
                                "description": "Security vulnerability in requests",
                                "fix_versions": ["2.31.0", "2.32.0"],
                                "aliases": ["CVE-2023-12345", "GHSA-abcd-1234"],
                            },
                        ],
                    },
                ],
            })

            result = ToolExecutionResult(
                success=True,
                raw_output=json_output,
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
    async def test_parse_json_output_no_vulnerabilities(self):
        """Test parsing JSON output with no vulnerabilities."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            json_output = json.dumps({"dependencies": []})

            result = ToolExecutionResult(
                success=True,
                raw_output=json_output,
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            issues = await adapter.parse_output(result)

            assert issues == []

    @pytest.mark.asyncio
    async def test_parse_empty_output(self):
        """Test parsing empty output."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            result = ToolExecutionResult(
                success=True,
                raw_output="",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            issues = await adapter.parse_output(result)

            assert issues == []

    @pytest.mark.asyncio
    async def test_parse_json_with_preamble(self):
        """Test parsing JSON output with text preamble."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            # pip-audit sometimes outputs text before the JSON
            output = """Processing: pyproject.toml
Found vulnerabilities in 1 package:
{"dependencies": [{"name": "requests", "version": "2.25.0", "vulns": [{"id": "CVE-2023-001", "description": "Test", "fix_versions": [], "aliases": []}]}]}"""

            result = ToolExecutionResult(
                success=True,
                raw_output=output,
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )
            issues = await adapter.parse_output(result)

            assert len(issues) == 1

    @pytest.mark.asyncio
    async def test_parse_invalid_json_fallback_to_text(self):
        """Test parsing invalid JSON falls back to text parsing."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            text_output = "requests 2.25.0 vulnerability CVE-2023-12345 detected"

            result = ToolExecutionResult(
                success=True,
                raw_output=text_output,
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )
            issues = await adapter.parse_output(result)

            assert len(issues) >= 1


class TestParseTextOutput:
    """Test suite for _parse_text_output method."""

    @pytest.mark.asyncio
    async def test_parse_text_with_cve(self):
        """Test parsing text output with CVE."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            output = "requests 2.25.0 vulnerability CVE-2023-12345 detected"
            issues = adapter._parse_text_output(output)

            assert len(issues) == 1
            assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_text_with_pyssec(self):
        """Test parsing text output with PYSEC."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            output = "urllib3 1.0.0 vulnerability PYSEC-2024-789 detected"
            issues = adapter._parse_text_output(output)

            assert len(issues) == 1

    @pytest.mark.asyncio
    async def test_parse_text_with_vulnerability_keyword(self):
        """Test parsing text output with 'vulnerability' keyword."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            output = "package 1.0.0 has a vulnerability that needs fixing"
            issues = adapter._parse_text_output(output)

            assert len(issues) == 1


class TestParseTextLine:
    """Test suite for _parse_text_line method."""

    def test_parse_valid_line(self):
        """Test parsing valid text line."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            adapter.settings = PipAuditSettings()
            # We need settings to be initialized
            import asyncio
            asyncio.get_event_loop().run_until_complete(adapter.init())

            line = "requests 2.25.0 vulnerability CVE-2023-12345"
            issue = adapter._parse_text_line(line)

            assert issue is not None
            assert issue.file_path == Path("pyproject.toml")
            assert issue.severity == "error"


class TestIsSuccessfulResult:
    """Test suite for is_successful_result method."""

    @pytest.mark.asyncio
    async def test_no_issues_with_nonzero_exit(self):
        """Test success when no issues but non-zero exit code."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            result = ToolExecutionResult(
                success=False,
                raw_output="",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )

            # Mock parse_output to return empty
            with patch.object(adapter, "parse_output", return_value=[]):
                is_success = await adapter.is_successful_result(result)
                assert is_success is True

    @pytest.mark.asyncio
    async def test_no_issues_with_zero_exit(self):
        """Test success when no issues and zero exit code."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            result = ToolExecutionResult(
                success=True,
                raw_output="",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )

            with patch.object(adapter, "parse_output", return_value=[]):
                is_success = await adapter.is_successful_result(result)
                assert is_success is True

    @pytest.mark.asyncio
    async def test_failure_with_non_ignored_issues(self):
        """Test failure when there are non-ignored issues."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            issues = [
                ToolIssue(
                    file_path=Path("pyproject.toml"),
                    line_number=None,
                    column_number=None,
                    message="Test vulnerability",
                    code="CVE-2023-12345",  # Not in ignore list
                    severity="error",
                )
            ]

            result = ToolExecutionResult(
                success=False,
                raw_output="",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )

            with patch.object(adapter, "parse_output", return_value=issues):
                is_success = await adapter.is_successful_result(result)
                assert is_success is False

    @pytest.mark.asyncio
    async def test_success_when_all_issues_ignored(self):
        """Test success when all issues are in ignore list."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            # Use an ignored CVE
            issues = [
                ToolIssue(
                    file_path=Path("pyproject.toml"),
                    line_number=None,
                    column_number=None,
                    message="Test vulnerability",
                    code="CVE-2025-53000",  # In IGNORED_VULNERABILITY_IDS
                    severity="error",
                )
            ]

            result = ToolExecutionResult(
                success=False,
                raw_output="",
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=1,
            )

            with patch.object(adapter, "parse_output", return_value=issues):
                is_success = await adapter.is_successful_result(result)
                assert is_success is True


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self):
        """Test default configuration."""
        adapter = PipAuditAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "pip-audit (Dependency Vulnerabilities)"
        assert config.check_type == QACheckType.SECURITY
        assert config.enabled is True
        assert "pyproject.toml" in config.file_patterns
        assert "requirements.txt" in config.file_patterns
        assert config.stage == "fast"
        assert config.timeout_seconds == 120
        assert config.parallel_safe is True


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self):
        """Test check type is SECURITY."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            adapter.settings = PipAuditSettings()
            assert adapter._get_check_type() == QACheckType.SECURITY


class TestInitialization:
    """Test suite for adapter initialization."""

    @pytest.mark.asyncio
    async def test_init_with_custom_settings(self):
        """Test initialization with custom settings."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings(vulnerability_service="pypi")
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            assert adapter.settings is not None
            assert adapter.settings.vulnerability_service == "pypi"

    @pytest.mark.asyncio
    async def test_init_without_settings_uses_defaults(self):
        """Test initialization without settings uses defaults."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            assert adapter.settings is not None
            assert adapter.settings.timeout_seconds == 120
            assert adapter.settings.vulnerability_service == "osv"
            # Should have default ignored vulns
            assert len(adapter.settings.ignore_vulns) > 0

    @pytest.mark.asyncio
    async def test_init_uses_ignored_vulns_from_config(self):
        """Test initialization includes IGNORED_VULNERABILITY_IDS."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            # CVE-2025-53000 should be in the default ignore list
            assert "CVE-2025-53000" in adapter.settings.ignore_vulns


# Import ToolIssue for use in tests
from crackerjack.adapters._tool_adapter_base import ToolIssue
