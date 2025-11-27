"""Pyrefly adapter for ACB QA framework - Python type checking tool.

Pyrefly is a Python type checking tool that provides static type analysis
for Python code. It offers:
- Static type checking
- Type inference
- Generic type validation
- Protocol compliance checking

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
    "01937d86-6b2c-7d3e-8f4a-b5c6d7e8f9a2"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "experimental"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class PyreflySettings(ToolAdapterSettings):
    """Settings for Pyrefly adapter."""

    tool_name: str = "pyrefly"
    use_json_output: bool = True
    strict_mode: bool = False
    ignore_missing_imports: bool = False
    follow_imports: str = "normal"  # normal, skip, silent
    incremental: bool = True
    warn_unused_ignores: bool = True


class PyreflyAdapter(BaseToolAdapter):
    """Adapter for Pyrefly - Python type checking tool.

    Performs static type analysis with:
    - Type checking for Python code
    - Type inference and validation
    - Generic type support
    - Protocol compliance checking

    Features:
    - JSON output for structured error reporting
    - Incremental type checking
    - Strict mode for enhanced type safety
    - Import following configuration

    Example:
        ```python
        settings = PyreflySettings(
            strict_mode=True,
            follow_imports="normal",
            incremental=True,
        )
        adapter = PyreflyAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: PyreflySettings | None = None

    def __init__(self, settings: PyreflySettings | None = None) -> None:
        """Initialize Pyrefly adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)
        logger.debug(
            "PyreflyAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = PyreflySettings()
            logger.info("Using default PyreflySettings")
        await super().init()
        logger.debug(
            "PyreflyAdapter initialization complete",
            extra={
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
            },
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Pyrefly (Type Check)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "pyrefly"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Pyrefly command.

        Args:
            files: Files/directories to type check
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

        # Strict mode
        if self.settings.strict_mode:
            cmd.append("--strict")

        # Ignore missing imports
        if self.settings.ignore_missing_imports:
            cmd.append("--ignore-missing-imports")

        # Follow imports
        cmd.extend(["--follow-imports", self.settings.follow_imports])

        # Incremental checking
        if self.settings.incremental:
            cmd.append("--incremental")

        # Warn about unused type: ignore comments
        if self.settings.warn_unused_ignores:
            cmd.append("--warn-unused-ignores")

        # Add targets
        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Pyrefly command",
            extra={
                "file_count": len(files),
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Pyrefly JSON output into standardized issues.

        Args:
            result: Raw execution result from Pyrefly

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed Pyrefly JSON output",
                extra={"files_count": len(data.get("files", []))},
            )
        except json.JSONDecodeError as e:
            logger.debug(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return self._parse_text_output(result.raw_output)

        issues = []

        # Pyrefly JSON format (similar to mypy):
        # {
        #   "files": [
        #     {
        #       "path": "path/to/file.py",
        #       "errors": [
        #         {
        #           "line": 42,
        #           "column": 10,
        #           "message": "Incompatible types...",
        #           "severity": "error",
        #           "code": "assignment"
        #         }
        #       ]
        #     }
        #   ]
        # }

        for file_data in data.get("files", []):
            file_path = Path(file_data.get("path", ""))

            for error in file_data.get("errors", []):
                issue = ToolIssue(
                    file_path=file_path,
                    line_number=error.get("line"),
                    column_number=error.get("column"),
                    message=error.get("message", ""),
                    code=error.get("code"),
                    severity=error.get("severity", "error"),
                )
                issues.append(issue)

        logger.info(
            "Parsed Pyrefly output",
            extra={
                "total_issues": len(issues),
                "errors": sum(1 for i in issues if i.severity == "error"),
                "warnings": sum(1 for i in issues if i.severity == "warning"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        """Parse Pyrefly text output (fallback).

        Args:
            output: Text output from Pyrefly

        Returns:
            List of ToolIssue objects
        """
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            # Pyrefly text format: "file.py:10:5: error: Incompatible types..."
            if ":" not in line:
                continue

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Pyrefly text output (fallback)",
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

            severity = self._parse_severity(severity_and_message)
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

    def _parse_severity(self, severity_and_message: str) -> str:
        """Parse severity from text line.

        Args:
            severity_and_message: Part containing severity

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
        """Return type check type."""
        return QACheckType.TYPE

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Pyrefly adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.TYPE,
            enabled=False,  # Disabled by default as experimental
            file_patterns=["**/*.py"],
            exclude_patterns=[
                "**/.venv/**",
                "**/venv/**",
                "**/build/**",
                "**/dist/**",
            ],
            timeout_seconds=180,  # Type checking can be slower
            parallel_safe=True,
            stage="comprehensive",  # Type checking in comprehensive stage
            settings={
                "strict_mode": False,
                "incremental": True,
                "follow_imports": "normal",
                "warn_unused_ignores": True,
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(PyreflyAdapter)
