"""Gitleaks adapter for Crackerjack QA framework - secrets and credentials detection.

Gitleaks is a SAST tool for detecting hardcoded secrets like passwords, API keys,
and tokens in git repositories. It scans for:
- API keys (AWS, Google, Azure, etc.)
- Private keys (RSA, SSH, etc.)
- Database credentials
- OAuth tokens
- Generic secrets patterns

Standard Python Patterns:
- MODULE_ID and MODULE_STATUS at module level (static UUID)
- No ACB dependency injection
- Extends BaseToolAdapter for tool execution
- Async execution with JSON output parsing
"""

from __future__ import annotations

import json
import logging
import typing as t
from pathlib import Path
from uuid import UUID

from crackerjack.adapters._tool_adapter_base import (
    BaseToolAdapter,
    ToolAdapterSettings,
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig

# Static UUID from registry (NEVER change once set)
MODULE_ID = UUID("6deed37d-f943-44f5-a188-f2b287f7a17d")
MODULE_STATUS = AdapterStatus.STABLE

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class GitleaksSettings(ToolAdapterSettings):
    """Settings for Gitleaks adapter."""

    tool_name: str = "gitleaks"
    use_json_output: bool = True
    scan_mode: str = "detect"  # "detect" or "protect"
    config_file: Path | None = None
    baseline_file: Path | None = None
    no_git: bool = False  # Scan files without git history
    redact: bool = True  # Redact secrets in output
    verbose: bool = False


class GitleaksAdapter(BaseToolAdapter):
    """Adapter for Gitleaks - secrets and credentials scanner.

    Detects hardcoded secrets and credentials in code:
    - API keys (AWS, GCP, Azure, GitHub, Slack, etc.)
    - Private keys (RSA, SSH, PGP, etc.)
    - Database credentials (MySQL, Postgres, MongoDB, etc.)
    - OAuth tokens and refresh tokens
    - Generic high-entropy strings
    - Custom regex patterns

    Features:
    - JSON output for structured issue reporting
    - Git-aware scanning (detect mode) or file-based (protect mode)
    - Custom configuration support
    - Baseline file for known false positives
    - Secret redaction in output

    Example:
        ```python
        settings = GitleaksSettings(
            scan_mode="protect",  # Scan staged files
            redact=True,
            config_file=Path(".gitleaks.toml"),
        )
        adapter = GitleaksAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: GitleaksSettings | None = None

    def __init__(self, settings: GitleaksSettings | None = None) -> None:
        """Initialize Gitleaks adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)
        logger.debug(
            "GitleaksAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = GitleaksSettings()
            logger.info("Using default GitleaksSettings")
        await super().init()
        logger.debug(
            "GitleaksAdapter initialization complete",
            extra={
                "scan_mode": self.settings.scan_mode,
                "redact": self.settings.redact,
                "no_git": self.settings.no_git,
                "has_config": self.settings.config_file is not None,
            },
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Gitleaks (Secrets)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "gitleaks"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Gitleaks command.

        Args:
            files: Files/directories to scan
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        # Scan mode (detect for git history, protect for current files)
        cmd.append(self.settings.scan_mode)

        # Source path
        if files:
            # For protect mode, scan specific files
            if self.settings.scan_mode == "protect":
                cmd.extend(["--source", str(files[0].parent if files else Path.cwd())])
            else:
                # For detect mode, scan repository
                cmd.extend(["--source", str(Path.cwd())])

        # JSON output
        if self.settings.use_json_output:
            cmd.extend(["--report-format", "json"])
            # Write to stdout
            cmd.extend(["--report-path", "/dev/stdout"])

        # Config file
        if self.settings.config_file and self.settings.config_file.exists():
            cmd.extend(["--config", str(self.settings.config_file)])

        # Baseline file (known false positives)
        if self.settings.baseline_file and self.settings.baseline_file.exists():
            cmd.extend(["--baseline-path", str(self.settings.baseline_file)])

        # No git mode (scan files without git)
        if self.settings.no_git:
            cmd.append("--no-git")

        # Redact secrets in output
        if self.settings.redact:
            cmd.append("--redact")

        # Verbose output
        if self.settings.verbose:
            cmd.append("--verbose")

        logger.info(
            "Built Gitleaks command",
            extra={
                "file_count": len(files),
                "scan_mode": self.settings.scan_mode,
                "redact": self.settings.redact,
                "no_git": self.settings.no_git,
                "has_config": self.settings.config_file is not None,
                "has_baseline": self.settings.baseline_file is not None,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Gitleaks JSON output into standardized issues.

        Args:
            result: Raw execution result from Gitleaks

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            findings = data if isinstance(data, list) else [data]
            logger.debug(
                "Parsed Gitleaks JSON output", extra={"findings_count": len(findings)}
            )
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parse failed",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return []

        issues = []

        # Gitleaks JSON format:
        # [
        #   {
        #     "Description": "AWS Access Key",
        #     "StartLine": 10,
        #     "EndLine": 10,
        #     "StartColumn": 15,
        #     "EndColumn": 35,
        #     "Match": "AKIAIOSFODNN7EXAMPLE",  # Redacted if --redact
        #     "Secret": "AKIAIOSFODNN7EXAMPLE",  # Redacted if --redact
        #     "File": "config/settings.py",
        #     "Commit": "abc123...",
        #     "Entropy": 3.5,
        #     "Author": "user@example.com",
        #     "Date": "2024-01-01",
        #     "Message": "commit message",
        #     "Tags": ["key", "AWS"],
        #     "RuleID": "aws-access-token"
        #   }
        # ]

        for finding in findings:
            file_path = Path(finding.get("File", ""))

            # Build descriptive message
            description = finding.get("Description", "Secret detected")
            rule_id = finding.get("RuleID", "")
            tags = finding.get("Tags", [])

            message_parts = [description]
            if rule_id:
                message_parts.append(f"(Rule: {rule_id})")
            if tags:
                message_parts.append(f"[{', '.join(tags)}]")

            message = " ".join(message_parts)

            # Entropy indicates likelihood of true positive
            entropy = finding.get("Entropy", 0.0)
            severity = "error" if entropy > 4.0 else "warning"

            issue = ToolIssue(
                file_path=file_path,
                line_number=finding.get("StartLine"),
                column_number=finding.get("StartColumn"),
                message=message,
                code=rule_id,
                severity=severity,
                suggestion=f"Review and remove secret. Entropy: {entropy:.2f}",
            )
            issues.append(issue)

        logger.info(
            "Parsed Gitleaks output",
            extra={
                "total_issues": len(issues),
                "high_entropy": sum(1 for i in issues if i.severity == "error"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        """Return security check type."""
        return QACheckType.SECURITY

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Gitleaks adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SECURITY,
            enabled=True,
            file_patterns=["**/*"],  # Scan all files
            exclude_patterns=[
                "**/.git/**",
                "**/node_modules/**",
                "**/.venv/**",
                "**/venv/**",
                "**/__pycache__/**",
            ],
            timeout_seconds=120,
            parallel_safe=True,
            stage="fast",  # Fast secrets scan before commit
            settings={
                "scan_mode": "protect",  # Scan current files
                "redact": True,
                "no_git": False,
            },
        )
