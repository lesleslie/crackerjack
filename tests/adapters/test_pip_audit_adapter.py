"""Tests for PipAudit dependency scanner adapter."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.dependency.pip_audit import PipAuditAdapter, PipAuditSettings


class TestPipAuditAdapter:
    """Test cases for PipAuditAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """Test basic initialization of PipAuditAdapter."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            assert adapter.settings is None

            await adapter.init()
            assert adapter.settings is not None
            assert isinstance(adapter.settings, PipAuditSettings)
            assert adapter.tool_name == "pip-audit"
            assert adapter.adapter_name == "pip-audit (Dependency Vulnerabilities)"

    @pytest.mark.asyncio
    async def test_build_command_basic(self) -> None:
        """Test building a basic pip-audit command."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings()
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path(".")]
            command = adapter.build_command(files)

            # Basic command structure
            assert "pip-audit" in command
            assert "--format" in command
            assert "json" in command
            assert "--vulnerability-service" in command
            assert "osv" in command
            assert "--desc" in command
            assert "--skip-editable" in command

    @pytest.mark.asyncio
    async def test_build_command_with_requirements(self) -> None:
        """Test building pip-audit command with requirements file."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings()
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path("requirements.txt")]
            command = adapter.build_command(files)

            # Should include -r flag for requirements file
            assert "-r" in command
            assert "requirements.txt" in command

    @pytest.mark.asyncio
    async def test_build_command_with_options(self) -> None:
        """Test building pip-audit command with various options."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            settings = PipAuditSettings(
                vulnerability_service="pypi",
                require_hashes=True,
                skip_editable=False,
                fix=True,
            )
            adapter = PipAuditAdapter(settings=settings)
            await adapter.init()

            files = [Path(".")]
            command = adapter.build_command(files)

            assert "--vulnerability-service" in command
            assert "pypi" in command
            assert "--require-hashes" in command
            assert "--fix" in command
            assert "--skip-editable" not in command

    @pytest.mark.asyncio
    async def test_parse_json_output(self) -> None:
        """Test parsing JSON output from pip-audit."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            # Mock JSON output with vulnerability
            json_output = json.dumps(
                {
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
                                }
                            ],
                        }
                    ]
                }
            )

            result = ToolExecutionResult(
                success=True,
                raw_output=json_output,
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            issues = await adapter.parse_output(result)

            assert len(issues) == 1
            issue = issues[0]
            assert issue.file_path == Path("pyproject.toml")
            assert issue.line_number is None  # No line numbers for dependency issues
            assert "requests==2.25.0" in issue.message
            assert "PYSEC-2023-123" in issue.message
            assert "CVE-2023-12345" in issue.message
            assert "Fix available" in issue.message
            assert issue.code == "PYSEC-2023-123"
            assert issue.severity == "error"

    @pytest.mark.asyncio
    async def test_parse_json_output_no_vulnerabilities(self) -> None:
        """Test parsing JSON output with no vulnerabilities."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            # Mock JSON output without vulnerabilities
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
    async def test_parse_text_output_fallback(self) -> None:
        """Test parsing text output as fallback."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            text_output = "requests 2.25.0 vulnerability CVE-2023-12345 detected"

            result = ToolExecutionResult(
                success=True,
                raw_output=text_output,
                raw_stderr="",
                execution_time_ms=0.0,
                exit_code=0,
            )
            issues = await adapter.parse_output(result)

            assert len(issues) == 1
            issue = issues[0]
            assert issue.file_path == Path("pyproject.toml")
            assert issue.severity == "error"
            assert "CVE-2023-12345" in issue.message

    @pytest.mark.asyncio
    async def test_parse_empty_output(self) -> None:
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

    def test_get_default_config(self) -> None:
        """Test getting default configuration."""
        adapter = PipAuditAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "pip-audit (Dependency Vulnerabilities)"
        assert config.enabled is True  # Stable, so enabled by default
        assert "pyproject.toml" in config.file_patterns
        assert "requirements.txt" in config.file_patterns
        assert config.stage == "comprehensive"
        assert config.timeout_seconds == 120

    @pytest.mark.asyncio
    async def test_build_vulnerability_message(self) -> None:
        """Test building vulnerability message with all components."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            message = adapter._build_vulnerability_message(
                package_name="requests",
                package_version="2.25.0",
                vuln_id="PYSEC-2023-123",
                description="A security vulnerability was found in the requests library",
                fix_versions=["2.31.0", "2.32.0"],
                aliases=["CVE-2023-12345", "GHSA-abcd-1234"],
            )

            assert "requests==2.25.0" in message
            assert "PYSEC-2023-123" in message
            assert "CVE-2023-12345" in message
            assert "Fix available: 2.31.0, 2.32.0" in message
            assert "A security vulnerability was found" in message

    @pytest.mark.asyncio
    async def test_count_affected_packages(self) -> None:
        """Test counting affected packages."""
        with patch.object(PipAuditAdapter, "validate_tool_available", return_value=True):
            adapter = PipAuditAdapter()
            await adapter.init()

            data = {
                "dependencies": [
                    {"name": "requests", "version": "2.25.0", "vulns": [{"id": "1"}]},
                    {"name": "urllib3", "version": "1.0.0", "vulns": [{"id": "2"}]},
                    {"name": "safe-pkg", "version": "1.0.0", "vulns": []},
                ]
            }

            count = adapter._count_affected_packages(data)
            assert count == 2  # Only requests and urllib3 have vulnerabilities
