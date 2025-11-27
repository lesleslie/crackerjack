"""Pyscn adapter for ACB QA framework - Python security static analysis.

Pyscn is a Python static code analyzer for security that detects:
- Security vulnerabilities in Python code
- Common security anti-patterns
- Potential injection attacks
- Insecure cryptography usage
- Authentication and authorization issues

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
from pydantic import Field

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
    "01937d86-6b2c-7d3e-8f4a-b5c6d7e8f9a3"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "experimental"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class PyscnSettings(ToolAdapterSettings):
    """Settings for Pyscn adapter."""

    tool_name: str = "pyscn"
    use_json_output: bool = True
    severity_threshold: str = "low"  # low, medium, high, critical
    confidence_threshold: str = "low"  # low, medium, high
    exclude_rules: list[str] = Field(default_factory=list)
    include_rules: list[str] = Field(default_factory=list)
    recursive: bool = True
    max_depth: int | None = None


class PyscnAdapter(BaseToolAdapter):
    """Adapter for Pyscn - Python security static analyzer.

    Performs static security analysis to detect vulnerabilities in Python code:
    - Security anti-patterns and insecure practices
    - Potential injection vulnerabilities
    - Weak cryptography implementations
    - Authentication/authorization flaws
    - Privilege escalation risks
    - Data exposure issues

    Features:
    - JSON output for structured issue reporting
    - Configurable severity and confidence thresholds
    - Rule inclusion/exclusion filtering
    - Recursive directory scanning with depth control

    Example:
        ```python
        settings = PyscnSettings(
            severity_threshold="medium",
            confidence_threshold="medium",
            exclude_rules=["SCN001"],
            recursive=True,
        )
        adapter = PyscnAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: PyscnSettings | None = None

    def __init__(self, settings: PyscnSettings | None = None) -> None:
        """Initialize Pyscn adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)
        logger.debug(
            "PyscnAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = PyscnSettings()
            logger.info("Using default PyscnSettings")
        await super().init()
        logger.debug(
            "PyscnAdapter initialization complete",
            extra={
                "severity_threshold": self.settings.severity_threshold,
                "confidence_threshold": self.settings.confidence_threshold,
                "recursive": self.settings.recursive,
            },
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Pyscn (Security Analysis)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "pyscn"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Pyscn command.

        Args:
            files: Files/directories to scan
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

        # Severity threshold
        cmd.extend(["--severity", self.settings.severity_threshold])

        # Confidence threshold
        cmd.extend(["--confidence", self.settings.confidence_threshold])

        # Exclude rules
        for rule in self.settings.exclude_rules:
            cmd.extend(["--exclude", rule])

        # Include rules
        for rule in self.settings.include_rules:
            cmd.extend(["--include", rule])

        # Recursive scanning
        if self.settings.recursive:
            cmd.append("--recursive")

        # Max depth
        if self.settings.max_depth is not None:
            cmd.extend(["--max-depth", str(self.settings.max_depth)])

        # Add targets
        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Pyscn command",
            extra={
                "file_count": len(files),
                "severity_threshold": self.settings.severity_threshold,
                "confidence_threshold": self.settings.confidence_threshold,
                "recursive": self.settings.recursive,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Pyscn JSON output into standardized issues.

        Args:
            result: Raw execution result from Pyscn

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed Pyscn JSON output",
                extra={"issues_count": len(data.get("issues", []))},
            )
        except json.JSONDecodeError as e:
            logger.debug(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return self._parse_text_output(result.raw_output)

        issues = []

        # Pyscn JSON format:
        # {
        #   "issues": [
        #     {
        #       "file": "path/to/file.py",
        #       "line": 42,
        #       "column": 10,
        #       "message": "Potential security vulnerability...",
        #       "severity": "high",
        #       "confidence": "medium",
        #       "rule_id": "SCN123",
        #       "rule_name": "insecure_crypto"
        #     }
        #   ]
        # }

        for issue_data in data.get("issues", []):
            issue = ToolIssue(
                file_path=Path(issue_data.get("file", "")),
                line_number=issue_data.get("line"),
                column_number=issue_data.get("column"),
                message=issue_data.get("message", ""),
                code=issue_data.get("rule_id"),
                severity=issue_data.get("severity", "error"),
            )
            issues.append(issue)

        logger.info(
            "Parsed Pyscn output",
            extra={
                "total_issues": len(issues),
                "errors": sum(1 for i in issues if i.severity == "error"),
                "warnings": sum(1 for i in issues if i.severity == "warning"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        """Parse Pyscn text output (fallback).

        Args:
            output: Text output from Pyscn

        Returns:
            List of ToolIssue objects
        """
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            # Pyscn text format: "file.py:10:5: error: Potential security vulnerability..."
            if ":" not in line:
                continue

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Pyscn text output (fallback)",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len({str(i.file_path) for i in issues}),
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
        parts = line.split(":", maxsplit=4)
        if len(parts) < 4:
            return None

        try:
            file_path = Path(parts[0].strip())
            line_number = int(parts[1].strip())
            column_number = (
                int(parts[2].strip()) if parts[2].strip().isdigit() else None
            )

            severity_and_message = parts[3].strip() if len(parts) > 3 else ""
            message = parts[4].strip() if len(parts) > 4 else ""

            severity = self._parse_severity(severity_and_message, message)
            message = self._extract_message(severity_and_message, message, severity)

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                severity=severity,
            )

        except (ValueError, IndexError):
            return None

    def _parse_severity(self, severity_and_message: str, message: str) -> str:
        """Parse severity from text line.

        Args:
            severity_and_message: Part containing severity
            message: Explicit message if present

        Returns:
            Severity level (error or warning)
        """
        if severity_and_message.lower().startswith("warning"):
            return "warning"
        return "error"

    def _extract_message(
        self, severity_and_message: str, message: str, severity: str
    ) -> str:
        """Extract message from text line.

        Args:
            severity_and_message: Part containing severity and possibly message
            message: Explicit message if present
            severity: Parsed severity level

        Returns:
            Extracted message
        """
        if message:
            return message

        # Extract from severity_and_message
        if severity_and_message.lower().startswith(severity):
            return severity_and_message[len(severity) :].strip()

        return severity_and_message

    def _get_check_type(self) -> QACheckType:
        """Return SAST check type."""
        return QACheckType.SAST

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Pyscn adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SAST,
            enabled=False,  # Disabled by default as experimental
            file_patterns=["**/*.py"],
            exclude_patterns=[
                "**/.venv/**",
                "**/venv/**",
                "**/build/**",
                "**/dist/**",
            ],
            timeout_seconds=120,  # Security scanning can be slower
            parallel_safe=True,
            stage="comprehensive",  # Security checks in comprehensive stage
            settings={
                "severity_threshold": "medium",
                "confidence_threshold": "medium",
                "recursive": True,
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(PyscnAdapter)
