"""PipAudit adapter for ACB QA framework - Python dependency vulnerability scanner.

pip-audit is a tool from the Python Packaging Authority (PyPA) that scans Python
dependencies for known security vulnerabilities using the OSV database. It provides:
- CVE detection in installed packages
- SBOM (Software Bill of Materials) generation
- PyPI vulnerability database integration
- Fix version recommendations

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Extends BaseToolAdapter for tool execution
- Async execution with JSON output parsing
"""

from __future__ import annotations

import json
import logging
import typing as t
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from acb.depends import depends

from crackerjack.adapters._tool_adapter_base import (
    BaseToolAdapter,
    ToolAdapterSettings,
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.models.qa_results import QACheckType

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig

# ACB Module Registration (REQUIRED)
MODULE_ID = UUID(
    "01937d86-7a2b-7c3d-8e4f-b5c6d7e8f9a0"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class PipAuditSettings(ToolAdapterSettings):
    """Settings for PipAudit adapter."""

    tool_name: str = "pip-audit"
    use_json_output: bool = True
    require_hashes: bool = False  # Require hashes for all packages
    vulnerability_service: str = "osv"  # osv or pypi
    skip_editable: bool = True  # Skip editable packages in development
    dry_run: bool = False  # Report vulnerabilities without fixing
    fix: bool = False  # Attempt to fix vulnerabilities automatically
    output_desc: bool = True  # Include vulnerability descriptions
    cache_dir: Path | None = None  # Custom cache directory for vulnerability data


class PipAuditAdapter(BaseToolAdapter):
    """Adapter for pip-audit - Python dependency vulnerability scanner.

    Performs Software Composition Analysis (SCA) with:
    - CVE detection in Python dependencies
    - OSV database integration for vulnerability data
    - SBOM generation capabilities
    - Automatic fix suggestions with version recommendations
    - Support for requirements.txt and pyproject.toml

    Features:
    - JSON output for structured vulnerability reporting
    - Multiple vulnerability databases (OSV, PyPI)
    - Hash verification for package integrity
    - Editable package handling
    - Fix suggestions with version constraints

    Example:
        ```python
        settings = PipAuditSettings(
            vulnerability_service="osv",
            output_desc=True,
            skip_editable=True,
        )
        adapter = PipAuditAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path(".")])
        ```
    """

    settings: PipAuditSettings | None = None

    def __init__(self, settings: PipAuditSettings | None = None) -> None:
        """Initialize PipAudit adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)
        logger.debug(
            "PipAuditAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = PipAuditSettings()
            logger.info("Using default PipAuditSettings")
        await super().init()
        logger.debug(
            "PipAuditAdapter initialization complete",
            extra={
                "vulnerability_service": self.settings.vulnerability_service,
                "skip_editable": self.settings.skip_editable,
                "fix_enabled": self.settings.fix,
            },
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "pip-audit (Dependency Vulnerabilities)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "pip-audit"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build pip-audit command.

        Args:
            files: Files/directories to scan (typically project root or requirements.txt)
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        # JSON output
        if self.settings.use_json_output:
            cmd.extend(["--format", "json"])

        # Vulnerability service selection
        cmd.extend(["--vulnerability-service", self.settings.vulnerability_service])

        # Include vulnerability descriptions
        if self.settings.output_desc:
            cmd.append("--desc")

        # Skip editable packages
        if self.settings.skip_editable:
            cmd.append("--skip-editable")

        # Require hashes
        if self.settings.require_hashes:
            cmd.append("--require-hashes")

        # Dry run mode
        if self.settings.dry_run:
            cmd.append("--dry-run")

        # Fix vulnerabilities automatically
        if self.settings.fix:
            cmd.append("--fix")

        # Custom cache directory
        if self.settings.cache_dir:
            cmd.extend(["--cache-dir", str(self.settings.cache_dir)])

        # Scan targets
        # If files contains a requirements file, use it directly
        # Otherwise scan the current environment
        for file_path in files:
            if file_path.name in ("requirements.txt", "pyproject.toml"):
                cmd.extend(["-r", str(file_path)])
            elif file_path.is_dir():
                # Scan installed packages in current environment
                # pip-audit will automatically detect packages
                pass

        logger.info(
            "Built pip-audit command",
            extra={
                "file_count": len(files),
                "vulnerability_service": self.settings.vulnerability_service,
                "fix_mode": self.settings.fix,
                "skip_editable": self.settings.skip_editable,
            },
        )
        return cmd

    def _build_vulnerability_message(
        self,
        package_name: str,
        package_version: str,
        vuln_id: str,
        description: str,
        fix_versions: list[str],
        aliases: list[str],
    ) -> str:
        """Build a comprehensive message for a vulnerability."""
        message_parts = [
            f"{package_name}=={package_version}",
            f"vulnerability {vuln_id}",
        ]

        # Add CVE aliases if present
        cve_aliases = [a for a in aliases if a.startswith("CVE-")]
        if cve_aliases:
            message_parts.append(f"({', '.join(cve_aliases)})")

        # Add description
        if description:
            # Truncate long descriptions
            desc_preview = (
                description[:100] + "..." if len(description) > 100 else description
            )
            message_parts.append(f"- {desc_preview}")

        # Add fix versions
        if fix_versions:
            message_parts.append(f"Fix available: {', '.join(fix_versions[:3])}")

        return " ".join(message_parts)

    def _create_issues_from_dependencies(self, data: dict) -> list[ToolIssue]:
        """Create ToolIssues from parsed dependencies data."""
        issues = []

        for dependency in data.get("dependencies", []):
            package_name = dependency.get("name", "unknown")
            package_version = dependency.get("version", "unknown")

            for vuln in dependency.get("vulns", []):
                vuln_id = vuln.get("id", "unknown")
                description = vuln.get("description", "")
                fix_versions = vuln.get("fix_versions", [])
                aliases = vuln.get("aliases", [])

                message = self._build_vulnerability_message(
                    package_name,
                    package_version,
                    vuln_id,
                    description,
                    fix_versions,
                    aliases,
                )

                issue = ToolIssue(
                    file_path=Path("pyproject.toml"),  # Dependencies are in pyproject
                    line_number=None,  # No line number for dependency issues
                    column_number=None,
                    message=message,
                    code=vuln_id,
                    severity="error",  # All vulnerabilities are errors
                )
                issues.append(issue)

        return issues

    def _count_affected_packages(self, data: dict) -> int:
        """Count the number of affected packages."""
        return len(
            {
                dep.get("name")
                for dep in data.get("dependencies", [])
                if dep.get("vulns")
            }
        )

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse pip-audit JSON output into standardized issues.

        Args:
            result: Raw execution result from pip-audit

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed pip-audit JSON output",
                extra={"dependencies_count": len(data.get("dependencies", []))},
            )
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return self._parse_text_output(result.raw_output)

        issues = self._create_issues_from_dependencies(data)

        logger.info(
            "Parsed pip-audit output",
            extra={
                "total_vulnerabilities": len(issues),
                "affected_packages": self._count_affected_packages(data),
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        """Parse pip-audit text output (fallback).

        Args:
            output: Text output from pip-audit

        Returns:
            List of ToolIssue objects
        """
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            # pip-audit text format varies, but typically includes package name and CVE
            if "PYSEC-" in line or "CVE-" in line or "vulnerability" in line.lower():
                issue = self._parse_text_line(line)
                if issue:
                    issues.append(issue)

        logger.info(
            "Parsed pip-audit text output (fallback)",
            extra={
                "total_issues": len(issues),
            },
        )
        return issues

    def _parse_text_line(self, line: str) -> ToolIssue | None:
        """Parse a single text output line.

        Args:
            line: Line of text output

        Returns:
            ToolIssue if parsing successful, None otherwise
        """
        # Basic text parsing - extract package name and vulnerability info
        # This is a fallback, JSON is preferred
        try:
            return ToolIssue(
                file_path=Path("pyproject.toml"),
                line_number=None,
                column_number=None,
                message=line.strip(),
                severity="error",
            )
        except Exception:
            return None

    def _get_check_type(self) -> QACheckType:
        """Return dependency security check type."""
        return QACheckType.SECURITY

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for PipAudit adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SECURITY,
            enabled=True,
            file_patterns=[
                "pyproject.toml",
                "requirements.txt",
                "requirements-*.txt",
            ],
            exclude_patterns=[
                "**/.venv/**",
                "**/venv/**",
                "**/build/**",
                "**/dist/**",
            ],
            timeout_seconds=120,  # Dependency scanning can take time
            parallel_safe=True,
            stage="comprehensive",  # Run in comprehensive stage (not fast hooks)
            settings={
                "vulnerability_service": "osv",
                "skip_editable": True,
                "output_desc": True,
                "fix": False,  # Don't auto-fix by default
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(PipAuditAdapter)
