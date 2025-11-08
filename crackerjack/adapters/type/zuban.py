"""Zuban adapter for ACB QA framework - ultra-fast Python type checking.

Zuban is a Rust-based type checker for Python, offering 20-200x faster type checking
compared to traditional tools like pyright or mypy. It provides:
- Static type analysis
- Type inference
- Generic type checking
- Protocol compliance validation

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
    "01937d86-6b2c-7d3e-8f4a-b5c6d7e8f9a0"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class ZubanSettings(ToolAdapterSettings):
    """Settings for Zuban adapter."""

    tool_name: str = "zuban"
    use_json_output: bool = True
    strict_mode: bool = False
    ignore_missing_imports: bool = False
    follow_imports: str = "normal"  # normal, skip, silent
    cache_dir: Path | None = None
    incremental: bool = True
    warn_unused_ignores: bool = True


class ZubanAdapter(BaseToolAdapter):
    """Adapter for Zuban - ultra-fast Rust-based Python type checker.

    Performs static type analysis with exceptional performance:
    - Type checking 20-200x faster than pyright
    - Type inference and validation
    - Generic type support
    - Protocol compliance checking

    Features:
    - JSON output for structured error reporting
    - Incremental type checking with caching
    - Strict mode for enhanced type safety
    - Import following configuration
    - Parallel execution support

    Example:
        ```python
        settings = ZubanSettings(
            strict_mode=True,
            follow_imports="normal",
            incremental=True,
        )
        adapter = ZubanAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: ZubanSettings | None = None

    def __init__(self, settings: ZubanSettings | None = None) -> None:
        """Initialize Zuban adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)
        logger.debug(
            "ZubanAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = ZubanSettings()
            logger.info("Using default ZubanSettings")
        await super().init()
        logger.debug(
            "ZubanAdapter initialization complete",
            extra={
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
                "has_cache_dir": self.settings.cache_dir is not None,
            },
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Zuban (Type Check)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "zuban"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Zuban command.

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

        # Cache directory
        if self.settings.cache_dir:
            cmd.extend(["--cache-dir", str(self.settings.cache_dir)])

        # Incremental checking
        if self.settings.incremental:
            cmd.append("--incremental")

        # Warn about unused type: ignore comments
        # IMPORTANT: Skip this option if it causes config parsing errors
        # if self.settings.warn_unused_ignores:
        #     cmd.append("--warn-unused-ignores")

        # Add targets
        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Zuban command",
            extra={
                "file_count": len(files),
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
                "has_cache_dir": self.settings.cache_dir is not None,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Zuban JSON output into standardized issues.

        Args:
            result: Raw execution result from Zuban

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed Zuban JSON output",
                extra={"files_count": len(data.get("files", []))},
            )
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return self._parse_text_output(result.raw_output)

        issues = []

        # Zuban JSON format (similar to mypy):
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
            "Parsed Zuban output",
            extra={
                "total_issues": len(issues),
                "errors": sum(1 for i in issues if i.severity == "error"),
                "warnings": sum(1 for i in issues if i.severity == "warning"),
                "files_affected": len(set(str(i.file_path) for i in issues)),
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        """Parse Zuban text output (fallback).

        Args:
            output: Text output from Zuban

        Returns:
            List of ToolIssue objects
        """
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            # Zuban text format: "file.py:10:5: error: Incompatible types..."
            if ":" not in line:
                continue

            parts = line.split(":", maxsplit=4)
            if len(parts) < 4:
                continue

            try:
                file_path = Path(parts[0].strip())
                line_number = int(parts[1].strip())
                column_number = (
                    int(parts[2].strip()) if parts[2].strip().isdigit() else None
                )

                # Parse severity and message
                severity_and_message = parts[3].strip() if len(parts) > 3 else ""
                message = parts[4].strip() if len(parts) > 4 else severity_and_message

                # Default to error severity
                severity = "error"
                if severity_and_message.lower().startswith("warning"):
                    severity = "warning"
                    message = severity_and_message[len("warning") :].strip()
                elif severity_and_message.lower().startswith("error"):
                    message = severity_and_message[len("error") :].strip()

                issue = ToolIssue(
                    file_path=file_path,
                    line_number=line_number,
                    column_number=column_number,
                    message=message,
                    severity=severity,
                )
                issues.append(issue)

            except (ValueError, IndexError):
                continue

        logger.info(
            "Parsed Zuban text output (fallback)",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len(set(str(i.file_path) for i in issues)),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        """Return type check type."""
        return QACheckType.TYPE

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Zuban adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.TYPE,
            enabled=True,
            file_patterns=["crackerjack/**/*.py"],  # Only target package directory
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
            timeout_seconds=180,  # Type checking can be slower
            parallel_safe=True,
            stage="comprehensive",  # Type checking in comprehensive stage
            settings={
                "strict_mode": False,
                "incremental": False,  # Disable to avoid config cache issues
                "follow_imports": "normal",
                "warn_unused_ignores": False,  # Disable to avoid config issues
                "ignore_missing_imports": True,  # Avoid errors from missing imports
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(ZubanAdapter)
