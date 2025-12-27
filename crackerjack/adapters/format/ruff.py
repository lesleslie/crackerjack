"""Ruff adapter for Crackerjack QA framework - unified lint and format checking.

Ruff is a fast Python linter and formatter that combines the functionality
of multiple tools (Flake8, isort, Black, etc.) into a single executable.

This adapter handles both lint checking and formatting.

Standard Python Patterns:
- MODULE_ID and MODULE_STATUS at module level (static UUID)
- No ACB dependency injection
- Extends BaseToolAdapter for tool execution
- Async execution with JSON output parsing
"""

from __future__ import annotations

import json
import typing as t
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from pydantic import Field

from crackerjack.adapters._tool_adapter_base import (
    BaseToolAdapter,
    ToolAdapterSettings,
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig

# Static UUID from registry (NEVER change once set)
MODULE_ID = UUID("c38609f7-f4a4-43ac-a7af-c55ef522c615")
MODULE_STATUS = AdapterStatus.STABLE


class RuffMode(StrEnum):
    """Ruff execution modes."""

    CHECK = "check"
    FORMAT = "format"


class RuffSettings(ToolAdapterSettings):
    """Settings for Ruff adapter.

    Extends ToolAdapterSettings with Ruff-specific configuration.
    """

    tool_name: str = "ruff"
    mode: str = "check"  # "check" or "format"
    fix_enabled: bool = False
    unsafe_fixes: bool = False  # Enable unsafe auto-fixes for ruff check
    select_rules: list[str] = Field(default_factory=list)
    ignore_rules: list[str] = Field(default_factory=list)
    line_length: int | None = None
    use_json_output: bool = True  # Ruff supports JSON output
    respect_gitignore: bool = True
    preview: bool = False  # Enable preview rules


class RuffAdapter(BaseToolAdapter):
    """Adapter for Ruff - fast Python linter and formatter.

    Handles both linting and formatting operations:
    - Lint mode: Checks code quality, style, and complexity
    - Format mode: Reformats code to match style guidelines

    Features:
    - JSON output parsing for structured error reporting
    - Auto-fix support for lint issues
    - Configurable rule selection and line length
    - Respects .gitignore by default
    - Fast parallel execution

    Example:
        ```python
        # Lint mode with auto-fix
        settings = RuffSettings(
            mode="check",
            fix_enabled=True,
            select_rules=["E", "F", "I"],
            ignore_rules=["E501"],
        )
        adapter = RuffAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/file.py")])

        # Format mode
        settings = RuffSettings(mode="format")
        adapter = RuffAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/file.py")])
        ```
    """

    settings: RuffSettings | None = None

    def __init__(self, settings: RuffSettings | None = None) -> None:
        """Initialize Ruff adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = RuffSettings()
        await super().init()

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        if self.settings:
            mode = self.settings.mode
            return f"Ruff ({mode})"
        return "Ruff"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "ruff"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Ruff command based on mode and settings.

        Args:
            files: Files to check/format
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name, self.settings.mode]

        # Add mode-specific options
        if self.settings.mode == "check":
            self._add_check_mode_options(cmd)
        elif self.settings.mode == "format":
            self._add_format_mode_options(cmd)

        # Add files
        cmd.extend([str(f) for f in files])

        # Respect gitignore
        if self.settings.respect_gitignore:
            cmd.append("--respect-gitignore")

        return cmd

    def _add_check_mode_options(self, cmd: list[str]) -> None:
        """Add lint mode specific options to command.

        Args:
            cmd: Command list to append options to
        """
        if not self.settings:
            return

        if self.settings.fix_enabled:
            cmd.append("--fix")

            # Add unsafe-fixes flag when enabled (requires --fix)
            if self.settings.unsafe_fixes:
                cmd.append("--unsafe-fixes")

        if self.settings.use_json_output:
            cmd.extend(["--output-format", "json"])

        if self.settings.select_rules:
            cmd.extend(["--select", ",".join(self.settings.select_rules)])

        if self.settings.ignore_rules:
            cmd.extend(["--ignore", ",".join(self.settings.ignore_rules)])

        if self.settings.preview:
            cmd.append("--preview")

    def _add_format_mode_options(self, cmd: list[str]) -> None:
        """Add format mode specific options to command.

        Args:
            cmd: Command list to append options to
        """
        if not self.settings:
            return

        if self.settings.line_length:
            cmd.extend(["--line-length", str(self.settings.line_length)])

        if self.settings.preview:
            cmd.append("--preview")

        # Format mode doesn't support JSON output
        # But we can use --check to see what would be formatted
        if not self.settings.fix_enabled:
            cmd.append("--check")  # Only check, don't modify

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Ruff output into standardized issues.

        Args:
            result: Raw execution result from Ruff

        Returns:
            List of parsed issues
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        issues: list[ToolIssue] = []

        # Parse based on mode
        if self.settings.mode == "check":
            # Lint mode - parse JSON output
            if self.settings.use_json_output and result.raw_output:
                issues = self._parse_check_json(result.raw_output)
            else:
                # Fallback to text parsing if JSON not available
                issues = self._parse_check_text(result.raw_output)

        elif self.settings.mode == "format":
            # Format mode - parse modified files from output
            if result.exit_code != 0:
                # Files would be modified (or were modified if fix_enabled)
                issues = self._parse_format_output(
                    result.raw_output,
                    result.files_processed,
                )

        return issues

    def _parse_check_json(self, output: str) -> list[ToolIssue]:
        """Parse Ruff check JSON output.

        Args:
            output: JSON output from ruff check

        Returns:
            List of ToolIssue objects
        """
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []

        issues = []
        for item in data:
            # Ruff JSON format:
            # {
            #   "code": "F401",
            #   "message": "'os' imported but unused",
            #   "location": {
            #     "row": 1,
            #     "column": 8
            #   },
            #   "filename": "example.py",
            #   "url": "https://...",
            #   "fix": {...} (optional)
            # }

            location = item.get("location", {})
            file_path = Path(item.get("filename", ""))

            issue = ToolIssue(
                file_path=file_path,
                line_number=location.get("row"),
                column_number=location.get("column"),
                message=item.get("message", ""),
                code=item.get("code"),
                severity="error" if item.get("code", "").startswith("E") else "warning",
                suggestion=item.get("fix", {}).get("message")
                if item.get("fix")
                else None,
            )
            issues.append(issue)

        return issues

    def _parse_check_text(self, output: str) -> list[ToolIssue]:
        """Parse Ruff check text output (fallback).

        Args:
            output: Text output from ruff check

        Returns:
            List of ToolIssue objects
        """
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            # Ruff text format: "path/to/file.py:10:5: F401 'os' imported but unused"
            if ":" not in line:
                continue

            issue = self._parse_check_text_line(line)
            if issue:
                issues.append(issue)

        return issues

    def _parse_check_text_line(self, line: str) -> ToolIssue | None:
        """Parse a single Ruff check text line.

        Args:
            line: Line of text output

        Returns:
            ToolIssue if parsing successful, None otherwise
        """
        parts = line.split(":", maxsplit=3)
        if len(parts) < 4:
            return None

        try:
            file_path = Path(parts[0].strip())
            line_number = int(parts[1].strip())
            column_number = (
                int(parts[2].strip()) if parts[2].strip().isdigit() else None
            )

            # Parse code and message
            message_part = parts[3].strip()
            code, message = self._extract_check_code_and_message(message_part)

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                code=code,
                severity="error" if code and code.startswith("E") else "warning",
            )

        except (ValueError, IndexError):
            return None

    def _extract_check_code_and_message(
        self, message_part: str
    ) -> tuple[str | None, str]:
        """Extract code and message from Ruff check output.

        Args:
            message_part: Part containing code and message

        Returns:
            Tuple of (code, message)
        """
        if " " not in message_part:
            return None, message_part

        code_candidate = message_part.split()[0]
        if code_candidate.strip():
            code = code_candidate
            message = message_part[len(code) :].strip()
            return code, message

        return None, message_part

    def _parse_format_output(
        self,
        output: str,
        processed_files: list[Path],
    ) -> list[ToolIssue]:
        """Parse Ruff format output.

        Args:
            output: Text output from ruff format
            processed_files: Files that were processed

        Returns:
            List of ToolIssue objects (files needing formatting)
        """
        issues = []

        # Ruff format --check outputs files that would be reformatted
        lines = output.strip().split("\n")

        for line in lines:
            if line.startswith("Would reformat:") or line.strip().endswith(".py"):
                # Extract file path
                file_str = line.replace("Would reformat:", "").strip()
                if file_str:
                    try:
                        file_path = Path(file_str)
                        issue = ToolIssue(
                            file_path=file_path,
                            message="File would be reformatted",
                            severity="warning",
                        )
                        issues.append(issue)
                    except Exception:
                        continue

        # If no specific files mentioned but exit code != 0, all files need formatting
        if not issues and processed_files:
            for file_path in processed_files:
                issue = ToolIssue(
                    file_path=file_path,
                    message="File needs formatting",
                    severity="warning",
                )
                issues.append(issue)

        return issues

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        """Execute Ruff check/format on files.

        Overrides parent to handle format mode's file modifications.

        Args:
            files: List of files to check (None = check all matching patterns)
            config: Optional configuration override

        Returns:
            QAResult with check execution results
        """
        # Call parent check implementation
        result = await super().check(files=files, config=config)

        # If format mode with fix enabled, mark files as modified
        if (
            self.settings
            and self.settings.mode == "format"
            and self.settings.fix_enabled
            and result.status in (QAResultStatus.SUCCESS, QAResultStatus.WARNING)
        ):
            # Files were formatted - mark as modified
            result.files_modified = result.files_checked.copy()
            result.issues_fixed = result.issues_found

        return result

    def _get_check_type(self) -> QACheckType:
        """Determine check type based on mode.

        Returns:
            QACheckType.FORMAT for format mode, QACheckType.LINT for check mode
        """
        if self.settings and self.settings.mode == "format":
            return QACheckType.FORMAT
        return QACheckType.LINT

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Ruff adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        # Determine if this is a format mode adapter from settings or default to check mode
        is_format_mode = False
        if self.settings:
            is_format_mode = self.settings.mode == "format"
        else:
            is_format_mode = False  # Default to check mode

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            enabled=True,
            file_patterns=["**/*.py"],
            exclude_patterns=[
                "**/.*",
                "**/__pycache__/**",
                "**/build/**",
                "**/dist/**",
            ],
            timeout_seconds=60,
            is_formatter=is_format_mode,
            parallel_safe=True,
            stage="fast",
            settings={
                "mode": "check",
                "fix_enabled": True,  # Enable auto-fix by default for fast hooks
                "select_rules": [],
                "ignore_rules": [],
                "preview": False,
            },
        )
