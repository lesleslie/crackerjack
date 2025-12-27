"""Codespell adapter for Crackerjack QA framework - spelling error detection.

Codespell checks for common spelling errors in code, comments, and documentation.
It helps maintain professional quality by catching:
- Typos in comments and docstrings
- Misspelled variable/function names
- Documentation errors
- Common spelling mistakes

Standard Python Patterns:
- MODULE_ID and MODULE_STATUS at module level (static UUID)
- No ACB dependency injection
- Extends BaseToolAdapter for tool execution
- Async execution with output parsing
"""

from __future__ import annotations

import typing as t
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
from crackerjack.models.qa_results import QACheckType

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig

# Static UUID from registry (NEVER change once set)
MODULE_ID = UUID("b42b5648-52e1-4a89-866f-3f9821087b0b")
MODULE_STATUS = AdapterStatus.STABLE


class CodespellSettings(ToolAdapterSettings):
    """Settings for Codespell adapter."""

    tool_name: str = "codespell"
    use_json_output: bool = False  # Codespell uses text output
    fix_enabled: bool = False  # Auto-fix spelling errors
    skip_hidden: bool = True
    ignore_words: list[str] = Field(default_factory=list)
    ignore_words_file: Path | None = None
    check_filenames: bool = False
    quiet_level: int = 2  # Only show errors


class CodespellAdapter(BaseToolAdapter):
    """Adapter for Codespell - spelling error checker.

    Detects and optionally fixes common spelling mistakes:
    - Comments and docstrings
    - String literals
    - Variable and function names (optional)
    - Documentation files

    Features:
    - Auto-fix support
    - Custom ignore words
    - Configurable scanning scope
    - Multiple file type support

    Example:
        ```python
        settings = CodespellSettings(
            fix_enabled=True,
            ignore_words=["acb", "pydantic"],
            skip_hidden=True,
        )
        adapter = CodespellAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/"), Path("docs/")])
        ```
    """

    settings: CodespellSettings | None = None

    def __init__(self, settings: CodespellSettings | None = None) -> None:
        """Initialize Codespell adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = await CodespellSettings.create_async()
        await super().init()

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Codespell (Spelling)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "codespell"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Codespell command.

        Args:
            files: Files/directories to check
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        # Auto-fix
        if self.settings.fix_enabled:
            cmd.append("--write-changes")

        # Skip hidden files
        if self.settings.skip_hidden:
            cmd.append("--skip=.*")

        # Ignore specific words
        if self.settings.ignore_words:
            cmd.extend(["--ignore-words-list", ",".join(self.settings.ignore_words)])

        # Ignore words file
        if self.settings.ignore_words_file and self.settings.ignore_words_file.exists():
            cmd.extend(["--ignore-words", str(self.settings.ignore_words_file)])

        # Check filenames
        if self.settings.check_filenames:
            cmd.append("--check-filenames")

        # Quiet level
        cmd.extend(["--quiet-level", str(self.settings.quiet_level)])

        # Add targets
        cmd.extend([str(f) for f in files])

        return cmd

    def _parse_codespell_line(
        self, line: str
    ) -> tuple[Path | None, int | None, str, str | None] | None:
        """Parse a single line from codespell output.

        Args:
            line: A line from codespell output

        Returns:
            Tuple of (file_path, line_number, message, suggestion) or None if parsing fails
        """
        # Codespell format: "file.py:10: tyop ==> typo"
        if ":" not in line or "==>" not in line:
            return None

        parts = line.split(":", maxsplit=2)
        if len(parts) < 2:
            return None

        file_path = Path(parts[0].strip())
        line_number = int(parts[1].strip()) if parts[1].strip().isdigit() else None

        # Parse error and suggestion
        error_part = parts[2].strip() if len(parts) > 2 else line
        if "==>" in error_part:
            wrong, correct = error_part.split("==>", maxsplit=1)
            wrong = wrong.strip()
            correct = correct.strip()

            message = f"Spelling: '{wrong}' should be '{correct}'"
            suggestion = f"Replace '{wrong}' with '{correct}'"
        else:
            message = error_part
            suggestion = None

        return file_path, line_number, message, suggestion

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Codespell text output into standardized issues.

        Args:
            result: Raw execution result from Codespell

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            return []

        issues = []
        lines = result.raw_output.strip().split("\n")

        for line in lines:
            parsed_result = self._parse_codespell_line(line)
            if parsed_result is not None:
                file_path, line_number, message, suggestion = parsed_result

                issue = ToolIssue(
                    file_path=file_path,
                    line_number=line_number,
                    message=message,
                    code="SPELLING",
                    severity="warning",
                    suggestion=suggestion,
                )
                issues.append(issue)

        return issues

    def _get_check_type(self) -> QACheckType:
        """Return format check type."""
        return QACheckType.FORMAT

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Codespell adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.FORMAT,
            enabled=True,
            file_patterns=["**/*.py", "**/*.md", "**/*.rst", "**/*.txt"],
            exclude_patterns=[
                "**/.git/**",
                "**/.venv/**",
                "**/node_modules/**",
                "**/__pycache__/**",
            ],
            timeout_seconds=60,
            is_formatter=False,  # Only checks, doesn't format
            parallel_safe=True,
            stage="fast",  # Spelling checks in fast stage
            settings={
                "fix_enabled": False,
                "skip_hidden": True,
                "ignore_words": ["acb", "pydantic", "uuid"],
                "check_filenames": False,
            },
        )
