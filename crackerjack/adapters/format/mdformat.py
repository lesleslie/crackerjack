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
    fix_enabled: bool = True  # Auto-format files (changed to match fast hooks behavior)
    line_length: int = 88  # Match Python formatting
    check_only: bool = False  # Auto-fix mode, not check-only
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
            self.settings = await MdformatSettings.create_async()
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

    async def _get_target_files(
        self, files: list[Path] | None, config: QACheckConfig | None
    ) -> list[Path]:
        """Get target markdown files using git-aware discovery.

        Args:
            files: Optional explicit file list
            config: Optional configuration

        Returns:
            List of markdown files to check
        """
        if files:
            return files

        # Use git-aware discovery for markdown files
        from crackerjack.tools._git_utils import get_git_tracked_files

        md_files = get_git_tracked_files("*.md")
        markdown_files = get_git_tracked_files("*.markdown")
        return md_files + markdown_files

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
        else:
            # When fix is enabled, run in fix mode to automatically format
            pass

        # Wrap handling: mdformat supports exactly one --wrap option
        # Prefer explicit wrap_mode (keep/no/number). If not provided, fall back to line_length.
        wrap_mode = getattr(self.settings, "wrap_mode", None)
        if wrap_mode:
            if wrap_mode in {"keep", "no"}:
                cmd.extend(["--wrap", wrap_mode])
            elif isinstance(wrap_mode, str) and wrap_mode.isdigit():
                cmd.extend(["--wrap", wrap_mode])
            else:
                # Unknown wrap_mode; ignore and fall back to line_length if available
                if self.settings.line_length:
                    cmd.extend(["--wrap", str(self.settings.line_length)])
        else:
            if self.settings.line_length:
                cmd.extend(["--wrap", str(self.settings.line_length)])

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
        if result.exit_code == 0:
            return []

        # Parse files that would be reformatted
        issues = self._parse_output_lines(result.raw_output)

        # Fallback: if no files parsed but exit code != 0, use processed files
        if not issues and result.files_processed:
            issues = self._create_issues_from_processed_files(result.files_processed)

        return issues

    def _parse_output_lines(self, output: str) -> list[ToolIssue]:
        """Parse output lines to extract files needing formatting.

        Args:
            output: Raw output from Mdformat

        Returns:
            List of issues for files needing formatting
        """
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            issue = self._create_issue_from_line(line)
            if issue:
                issues.append(issue)

        return issues

    def _create_issue_from_line(self, line: str) -> ToolIssue | None:
        """Create issue from output line if it's a valid markdown file.

        Args:
            line: Output line potentially containing file path

        Returns:
            ToolIssue if valid markdown file, None otherwise
        """
        with suppress(Exception):
            file_path = Path(line)
            if file_path.exists() and file_path.suffix in (".md", ".markdown"):
                return ToolIssue(
                    file_path=file_path,
                    message="File needs Markdown formatting",
                    code="MDFORMAT",
                    severity="warning",
                    suggestion="Run mdformat to format this file",
                )

        return None

    def _create_issues_from_processed_files(
        self, processed_files: list[Path]
    ) -> list[ToolIssue]:
        """Create issues from processed markdown files.

        Args:
            processed_files: Files that were processed by Mdformat

        Returns:
            List of issues for markdown files
        """
        issues = []
        for file_path in processed_files:
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
            timeout_seconds=300,  # Increased from 60 to 300 seconds (5 minutes) to handle larger markdown files
            is_formatter=True,  # Can modify files
            parallel_safe=True,
            stage="fast",  # Markdown formatting in fast stage
            settings={
                "fix_enabled": True,  # Enable auto-fix by default
                "line_length": 88,
                "check_only": False,  # Use fix mode as default
                "wrap_mode": "keep",
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(MdformatAdapter)
