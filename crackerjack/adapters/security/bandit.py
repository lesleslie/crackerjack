"""Bandit adapter for ACB QA framework - Python security linting.

Bandit is a security linter designed to find common security issues in Python code.
It performs static analysis to identify potential vulnerabilities like:
- SQL injection risks
- Hard-coded passwords/secrets
- Insecure use of eval/exec
- Weak cryptography
- And many more security anti-patterns

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Extends BaseToolAdapter for tool execution
- Async execution with JSON output parsing
"""

from __future__ import annotations

import json
import typing as t
from contextlib import suppress
from pathlib import Path
from uuid import UUID, uuid4

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
MODULE_ID = uuid4()
MODULE_STATUS = "stable"


class BanditSettings(ToolAdapterSettings):
    """Settings for Bandit adapter."""

    tool_name: str = "bandit"
    use_json_output: bool = True
    severity_level: str = "low"  # low, medium, high
    confidence_level: str = "low"  # low, medium, high
    exclude_tests: bool = True
    skip_rules: list[str] = Field(default_factory=list)
    tests_to_run: list[str] = Field(default_factory=list)
    recursive: bool = True


class BanditAdapter(BaseToolAdapter):
    """Adapter for Bandit - Python security linter.

    Performs static security analysis to identify common vulnerabilities:
    - SQL injection
    - Hard-coded credentials
    - Insecure cryptography
    - Command injection
    - Path traversal
    - And 100+ more security checks

    Features:
    - JSON output for structured issue reporting
    - Configurable severity and confidence thresholds
    - Rule selection and exclusion
    - Recursive directory scanning
    - Test file exclusion

    Example:
        ```python
        settings = BanditSettings(
            severity_level="medium",
            confidence_level="medium",
            exclude_tests=True,
            skip_rules=["B101"],  # Skip assert_used check
        )
        adapter = BanditAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: BanditSettings | None = None

    def __init__(self, settings: BanditSettings | None = None) -> None:
        """Initialize Bandit adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = BanditSettings()
        await super().init()

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Bandit (Security)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "bandit"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Bandit command.

        Args:
            files: Files/directories to scan
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        # Recursive scanning
        if self.settings.recursive:
            cmd.append("-r")

        # JSON output
        if self.settings.use_json_output:
            cmd.extend(["-f", "json"])

        # Severity level
        cmd.extend(["-ll", self.settings.severity_level.upper()])

        # Confidence level
        cmd.extend(["-il", self.settings.confidence_level.upper()])

        # Skip specific tests
        if self.settings.skip_rules:
            cmd.extend(["-s", ",".join(self.settings.skip_rules)])

        # Run specific tests only
        if self.settings.tests_to_run:
            cmd.extend(["-t", ",".join(self.settings.tests_to_run)])

        # Exclude test files
        if self.settings.exclude_tests:
            cmd.extend(["--skip-path", "**/test_*.py,**/tests/**"])

        # Add targets
        cmd.extend([str(f) for f in files])

        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Bandit JSON output into standardized issues.

        Args:
            result: Raw execution result from Bandit

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            return []

        try:
            data = json.loads(result.raw_output)
        except json.JSONDecodeError:
            # Fallback to text parsing if JSON fails
            return self._parse_text_output(result.raw_output)

        issues = []

        # Bandit JSON format:
        # {
        #   "results": [
        #     {
        #       "code": "...",
        #       "filename": "path/to/file.py",
        #       "issue_confidence": "HIGH",
        #       "issue_severity": "HIGH",
        #       "issue_text": "...",
        #       "line_number": 42,
        #       "line_range": [42, 43],
        #       "more_info": "https://...",
        #       "test_id": "B201",
        #       "test_name": "flask_debug_true"
        #     }
        #   ],
        #   "metrics": {...}
        # }

        for item in data.get("results", []):
            file_path = Path(item.get("filename", ""))

            # Map Bandit severity to our severity levels
            severity_mapping = {
                "HIGH": "error",
                "MEDIUM": "warning",
                "LOW": "warning",
            }
            bandit_severity = item.get("issue_severity", "MEDIUM")
            severity = severity_mapping.get(bandit_severity.upper(), "warning")

            issue = ToolIssue(
                file_path=file_path,
                line_number=item.get("line_number"),
                message=item.get("issue_text", ""),
                code=item.get("test_id"),
                severity=severity,
                suggestion=f"Confidence: {item.get('issue_confidence', 'UNKNOWN')}, "
                          f"See: {item.get('more_info', '')}",
            )
            issues.append(issue)

        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        """Parse Bandit text output (fallback).

        Args:
            output: Text output from Bandit

        Returns:
            List of ToolIssue objects
        """
        issues = []
        lines = output.strip().split("\n")

        current_file: Path | None = None
        current_line: int | None = None

        for line in lines:
            line = line.strip()

            # Parse file path lines
            if line.startswith(">>"):
                try:
                    file_str = line.split(">>")[1].strip()
                    current_file = Path(file_str)
                except (IndexError, ValueError):
                    continue

            # Parse issue lines
            elif line.startswith("Issue:") and current_file:
                message = line.replace("Issue:", "").strip()
                issue = ToolIssue(
                    file_path=current_file,
                    line_number=current_line,
                    message=message,
                    severity="warning",
                )
                issues.append(issue)

            # Parse line numbers
            elif "Line:" in line:
                try:
                    line_num_str = line.split("Line:")[1].strip()
                    current_line = int(line_num_str)
                except (IndexError, ValueError):
                    pass

        return issues

    def _get_check_type(self) -> QACheckType:
        """Return security check type."""
        return QACheckType.SECURITY

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Bandit adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SECURITY,
            enabled=True,
            file_patterns=["**/*.py"],
            exclude_patterns=["**/test_*.py", "**/tests/**", "**/.venv/**"],
            timeout_seconds=120,
            parallel_safe=True,
            stage="comprehensive",  # Security checks in comprehensive stage
            settings={
                "severity_level": "medium",
                "confidence_level": "medium",
                "exclude_tests": True,
                "skip_rules": [],
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(BanditAdapter)
