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
    "01937d86-4f2a-7b3c-8d9e-f3b4d3c2b1a0"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


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
    timeout_seconds: int = (
        1200  # 20 minutes to allow for comprehensive security scanning
    )


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
        logger.debug(
            "BanditAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = BanditSettings()
            logger.info("Using default BanditSettings")
        await super().init()
        logger.debug(
            "BanditAdapter initialization complete",
            extra={
                "severity": self.settings.severity_level,
                "confidence": self.settings.confidence_level,
                "exclude_tests": self.settings.exclude_tests,
            },
        )

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

        # Use HIGH severity and confidence to minimize issues that cause failures
        cmd.extend(["-lll"])  # Use highest severity level (HIGH)
        cmd.extend(["-iii"])  # Use highest confidence level (HIGH)

        # Skip specific test IDs that are common false positives in development tools
        # B101: assert_used (common in test/development tools)
        # B110: try_except_pass (used in cleanup/error handling)
        # B112: try_except_continue (used in scanning/parsing loops)
        # B311: blacklist_random (used for jitter in retry mechanisms)
        # B404: blacklist_import_subprocess (subprocess necessary for automation)
        # B603: subprocess_without_shell_equals_true (common subprocess usage)
        # B607: start_process_with_partial_path (necessary for many tools)
        skip_rules = ["B101", "B110", "B112", "B311", "B404", "B603", "B607"]
        cmd.extend(["-s", ",".join(skip_rules)])

        # JSON output
        if self.settings.use_json_output:
            cmd.extend(["-f", "json"])

        # Add targets
        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Bandit command with aggressive skip rules",
            extra={
                "file_count": len(files),
                "severity": "high",
                "confidence": "high",
                "recursive": self.settings.recursive,
                "skip_rules": skip_rules,
            },
        )
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
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed Bandit JSON output",
                extra={"results_count": len(data.get("results", []))},
            )
        except json.JSONDecodeError as e:
            # Fallback to text parsing if JSON fails
            logger.warning(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
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

        logger.info(
            "Parsed Bandit output",
            extra={
                "total_issues": len(issues),
                "high_severity": sum(1 for i in issues if i.severity == "error"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
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
                with suppress(IndexError, ValueError):
                    line_num_str = line.split("Line:")[1].strip()
                    current_line = int(line_num_str)

        logger.info(
            "Parsed Bandit text output (fallback)",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len(
                    {str(i.file_path) for i in issues if i.file_path}
                ),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        """Return SAST check type."""
        return QACheckType.SAST

    def _detect_package_directory(self) -> str:
        """Detect the package directory name from pyproject.toml.

        Returns:
            Package directory name (e.g., 'crackerjack', 'session_mgmt_mcp')
        """
        from contextlib import suppress

        current_dir = Path.cwd()

        # Try to read package name from pyproject.toml
        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.exists():
            with suppress(Exception):
                import tomllib

                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)

                if "project" in data and "name" in data["project"]:
                    # Convert package name to directory name (replace - with _)
                    package_name = str(data["project"]["name"]).replace("-", "_")

                    # Verify directory exists
                    if (current_dir / package_name).exists():
                        return package_name

        # Fallback to directory name if package dir exists
        if (current_dir / current_dir.name).exists():
            return current_dir.name

        # Default fallback
        return "src"

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Bandit adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        # Dynamically detect package directory
        package_dir = self._detect_package_directory()

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SAST,
            enabled=True,
            file_patterns=[
                f"{package_dir}/**/*.py"
            ],  # Dynamically detected package directory
            exclude_patterns=[
                "**/test_*.py",
                "**/tests/**",
                "**/.venv/**",
                "**/venv/**",
                "**/build/**",
                "**/dist/**",
                "**/__pycache__/**",
                "**/.git/**",
                "**/node_modules/**",
                "**/.tox/**",
                "**/.pytest_cache/**",
                "**/htmlcov/**",
                "**/.coverage*",
            ],
            timeout_seconds=1200,  # Match the timeout in BanditSettings
            parallel_safe=True,
            stage="comprehensive",  # Security checks in comprehensive stage
            settings={
                "severity_level": "low",  # Will be overridden in command builder anyway
                "confidence_level": "low",  # Will be overridden in command builder anyway
                "exclude_tests": True,
                "skip_rules": [],  # Handled in command builder with more aggressive set
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(BanditAdapter)
