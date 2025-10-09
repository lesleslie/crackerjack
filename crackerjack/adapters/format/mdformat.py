"""Mdformat adapter for ACB QA framework - Markdown formatting.

Mdformat is an opinionated Markdown formatter that enforces consistent styling:
- Consistent heading styles
- Standardized list formatting
- Proper code block formatting
- Link and image formatting
- Table alignment

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Extends BaseToolAdapter for tool execution
- Async execution with output parsing
"""

from __future__ import annotations

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


class MdformatSettings(ToolAdapterSettings):
    """Settings for Mdformat adapter."""

    tool_name: str = "mdformat"
    use_json_output: bool = False  # Mdformat doesn't support JSON
    fix_enabled: bool = False  # Auto-format files
    line_length: int = 88  # Match Python formatting
    check_only: bool = True  # Check without modifying
    wrap_mode: str = "keep"  # keep, no, or number


class MdformatAdapter(BaseToolAdapter):
    """Adapter for Mdformat - Markdown formatter.

    Enforces consistent Markdown formatting:
    - Heading styles (ATX vs Setext)
    - List formatting and indentation
    - Code block styles
    - Link reference styles
    - Table formatting

    Features:
    - Check-only or auto-fix mode
    - Configurable line length
    - Text wrapping options
    - Plugin support

    Example:
        ```python
        settings = MdformatSettings(
            fix_enabled=True,
            line_length=88,
            wrap_mode="keep",
        )
        adapter = MdformatAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("README.md"), Path("docs/")])
        ```
    """

    settings: MdformatSettings | None = None

    def __init__(self, settings: MdformatSettings | None = None) -> None:
        """Initialize Mdformat adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = MdformatSettings()
        await super().init()

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Mdformat (Markdown)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "mdformat"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Mdformat command.

        Args:
            files: Files/directories to format
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        # Check-only mode (don't modify files)
        if not self.settings.fix_enabled:
            cmd.append("--check")

        # Line length
        if self.settings.line_length:
            cmd.extend(["--wrap", str(self.settings.line_length)])

        # Wrap mode
        if self.settings.wrap_mode:
            if self.settings.wrap_mode == "keep":
                cmd.append("--wrap=keep")
            elif self.settings.wrap_mode == "no":
                cmd.append("--wrap=no")
            elif self.settings.wrap_mode.isdigit():
                cmd.extend(["--wrap", self.settings.wrap_mode])

        # Add targets
        cmd.extend([str(f) for f in files])

        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Mdformat output into standardized issues.

        Args:
            result: Raw execution result from Mdformat

        Returns:
            List of parsed issues
        """
        issues = []

        # Mdformat in check mode returns non-zero if files would be reformatted
        # and lists files that need formatting in stdout
        if result.exit_code != 0:
            # Parse files that would be reformatted
            lines = result.raw_output.strip().split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Mdformat outputs file paths that would be reformatted
                try:
                    file_path = Path(line)
                    if file_path.exists() and file_path.suffix in (".md", ".markdown"):
                        issue = ToolIssue(
                            file_path=file_path,
                            message="File needs Markdown formatting",
                            code="MDFORMAT",
                            severity="warning",
                            suggestion="Run mdformat to format this file",
                        )
                        issues.append(issue)
                except Exception:
                    continue

            # If no files parsed from output but exit code != 0,
            # report all checked files
            if not issues and result.files_processed:
                for file_path in result.files_processed:
                    if file_path.suffix in (".md", ".markdown"):
                        issue = ToolIssue(
                            file_path=file_path,
                            message="File needs Markdown formatting",
                            code="MDFORMAT",
                            severity="warning",
                        )
                        issues.append(issue)

        return issues

    def _get_check_type(self) -> QACheckType:
        """Return format check type."""
        return QACheckType.FORMAT

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Mdformat adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.FORMAT,
            enabled=True,
            file_patterns=["**/*.md", "**/*.markdown"],
            exclude_patterns=[
                "**/.git/**",
                "**/.venv/**",
                "**/node_modules/**",
            ],
            timeout_seconds=60,
            is_formatter=True,  # Can modify files
            parallel_safe=True,
            stage="fast",  # Markdown formatting in fast stage
            settings={
                "fix_enabled": False,
                "line_length": 88,
                "check_only": True,
                "wrap_mode": "keep",
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(MdformatAdapter)
