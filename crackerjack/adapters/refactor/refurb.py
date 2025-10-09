"""Refurb adapter for ACB QA framework - Python refactoring suggestions.

Refurb is a tool for refactoring Python code, suggesting modern Python idioms
and best practices. It identifies:
- Outdated syntax patterns
- Inefficient constructs
- Opportunities to use modern Python features
- Code that can be simplified

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Extends BaseToolAdapter for tool execution
- Async execution with output parsing
"""

from __future__ import annotations

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
    "01937d86-7c3d-8e4f-9a5b-c6d7e8f9a0b1"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class RefurbSettings(ToolAdapterSettings):
    """Settings for Refurb adapter."""

    tool_name: str = "refurb"
    use_json_output: bool = False  # Refurb doesn't support JSON output
    enable_all: bool = False  # Enable all checks
    disable_checks: list[str] = Field(default_factory=list)
    enable_checks: list[str] = Field(default_factory=list)
    python_version: str | None = None  # e.g., "3.13"
    explain: bool = False  # Show detailed explanations


class RefurbAdapter(BaseToolAdapter):
    """Adapter for Refurb - Python refactoring suggestions.

    Suggests modern Python idioms and refactoring opportunities:
    - Replace outdated constructs with modern equivalents
    - Simplify complex expressions
    - Use built-in functions more effectively
    - Apply Python best practices

    Features:
    - Configurable check selection
    - Python version-specific suggestions
    - Detailed explanations for suggestions
    - Non-destructive analysis only

    Example:
        ```python
        settings = RefurbSettings(
            enable_all=False,
            enable_checks=["FURB101", "FURB109"],
            python_version="3.13",
        )
        adapter = RefurbAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: RefurbSettings | None = None

    def __init__(self, settings: RefurbSettings | None = None) -> None:
        """Initialize Refurb adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)
        logger.debug(
            "RefurbAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = RefurbSettings()
            logger.info("Using default RefurbSettings")
        await super().init()
        logger.debug(
            "RefurbAdapter initialization complete",
            extra={
                "enable_all": self.settings.enable_all,
                "enable_checks_count": len(self.settings.enable_checks),
                "disable_checks_count": len(self.settings.disable_checks),
                "has_python_version": self.settings.python_version is not None,
            },
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Refurb (Refactoring)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "refurb"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Refurb command.

        Args:
            files: Files/directories to analyze
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        # Enable all checks
        if self.settings.enable_all:
            cmd.append("--enable-all")

        # Disable specific checks
        if self.settings.disable_checks:
            for check in self.settings.disable_checks:
                cmd.extend(["--ignore", check])

        # Enable specific checks
        if self.settings.enable_checks:
            for check in self.settings.enable_checks:
                cmd.extend(["--enable", check])

        # Python version
        if self.settings.python_version:
            cmd.extend(["--python-version", self.settings.python_version])

        # Show explanations
        if self.settings.explain:
            cmd.append("--explain")

        # Add targets
        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Refurb command",
            extra={
                "file_count": len(files),
                "enable_all": self.settings.enable_all,
                "enable_checks_count": len(self.settings.enable_checks),
                "disable_checks_count": len(self.settings.disable_checks),
                "explain": self.settings.explain,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Refurb text output into standardized issues.

        Args:
            result: Raw execution result from Refurb

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        issues = []
        lines = result.raw_output.strip().split("\n")
        logger.debug("Parsing Refurb text output", extra={"line_count": len(lines)})

        for line in lines:
            # Refurb format: "file.py:10:5 [FURB101]: Use dict comprehension..."
            if "[FURB" not in line:
                continue

            try:
                # Split on first colon to get file path
                if ":" not in line:
                    continue

                parts = line.split(":", maxsplit=3)
                if len(parts) < 3:
                    continue

                file_path = Path(parts[0].strip())
                line_number = int(parts[1].strip())

                # Parse column and message
                remaining = parts[2].strip()
                column_number = None
                message_part = remaining

                # Try to extract column number
                if " " in remaining:
                    first_part = remaining.split()[0]
                    if first_part.isdigit():
                        column_number = int(first_part)
                        message_part = remaining[len(first_part) :].strip()

                # Extract code and message
                if "[" in message_part and "]" in message_part:
                    code_start = message_part.index("[")
                    code_end = message_part.index("]")
                    code = message_part[code_start + 1 : code_end]
                    message = message_part[code_end + 1 :].strip()
                    if message.startswith(":"):
                        message = message[1:].strip()
                else:
                    code = None
                    message = message_part

                issue = ToolIssue(
                    file_path=file_path,
                    line_number=line_number,
                    column_number=column_number,
                    message=message,
                    code=code,
                    severity="warning",  # Refurb suggestions are warnings
                )
                issues.append(issue)

            except (ValueError, IndexError):
                continue

        logger.info(
            "Parsed Refurb output",
            extra={
                "total_issues": len(issues),
                "files_affected": len(set(str(i.file_path) for i in issues)),
                "unique_codes": len(set(i.code for i in issues if i.code)),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        """Return refactor check type."""
        return QACheckType.REFACTOR

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Refurb adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.REFACTOR,
            enabled=True,
            file_patterns=["**/*.py"],
            exclude_patterns=["**/.venv/**", "**/venv/**"],
            timeout_seconds=90,
            parallel_safe=True,
            stage="comprehensive",  # Refactoring suggestions in comprehensive stage
            settings={
                "enable_all": False,
                "disable_checks": [],
                "enable_checks": [],
                "explain": False,
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(RefurbAdapter)
