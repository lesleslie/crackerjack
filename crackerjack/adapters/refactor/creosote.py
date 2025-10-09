"""Creosote adapter for ACB QA framework - unused dependency detection.

Creosote identifies dependencies listed in project configuration (pyproject.toml,
requirements.txt) that are not actually used in the codebase, helping to:
- Keep dependencies lean
- Reduce security surface area
- Speed up installations
- Maintain clean dependency trees

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Extends BaseToolAdapter for tool execution
- Async execution with output parsing
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


class CreosoteSettings(ToolAdapterSettings):
    """Settings for Creosote adapter."""

    tool_name: str = "creosote"
    use_json_output: bool = False  # Creosote uses simple text output
    config_file: Path | None = None  # pyproject.toml or requirements.txt
    exclude_deps: list[str] = Field(default_factory=list)
    paths: list[Path] = Field(default_factory=list)  # Paths to scan for imports


class CreosoteAdapter(BaseToolAdapter):
    """Adapter for Creosote - unused dependency detector.

    Identifies dependencies that are declared but never imported:
    - Checks pyproject.toml dependencies
    - Checks requirements.txt
    - Scans codebase for actual imports
    - Reports unused dependencies

    Features:
    - Multiple dependency file support
    - Configurable scan paths
    - Dependency exclusion list
    - Helps maintain lean projects

    Example:
        ```python
        settings = CreosoteSettings(
            config_file=Path("pyproject.toml"),
            exclude_deps=["pytest", "black"],  # Build/dev tools
            paths=[Path("src"), Path("tests")],
        )
        adapter = CreosoteAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check()
        ```
    """

    settings: CreosoteSettings | None = None

    def __init__(self, settings: CreosoteSettings | None = None) -> None:
        """Initialize Creosote adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = CreosoteSettings()
        await super().init()

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Creosote (Dependencies)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "creosote"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Creosote command.

        Args:
            files: Not used (Creosote scans whole project)
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        # Config file
        if self.settings.config_file and self.settings.config_file.exists():
            cmd.extend(["--deps-file", str(self.settings.config_file)])

        # Exclude specific dependencies
        if self.settings.exclude_deps:
            for dep in self.settings.exclude_deps:
                cmd.extend(["--exclude", dep])

        # Paths to scan
        if self.settings.paths:
            for path in self.settings.paths:
                cmd.extend(["--paths", str(path)])

        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Creosote text output into standardized issues.

        Args:
            result: Raw execution result from Creosote

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            return []

        issues = []
        lines = result.raw_output.strip().split("\n")

        # Creosote output format:
        # "Found unused dependencies:"
        # "  package-name"
        # "  another-package"

        parsing_unused = False
        config_file = self.settings.config_file if self.settings else Path("pyproject.toml")

        for line in lines:
            line = line.strip()

            # Start of unused dependencies section
            if "unused" in line.lower() and "dependenc" in line.lower():
                parsing_unused = True
                continue

            # Empty line ends section
            if not line:
                parsing_unused = False
                continue

            # Parse dependency names
            if parsing_unused and line:
                # Remove leading dashes or bullets
                dep_name = line.lstrip("- ").strip()

                if dep_name:
                    issue = ToolIssue(
                        file_path=config_file,
                        message=f"Unused dependency: {dep_name}",
                        code="UNUSED_DEP",
                        severity="warning",
                        suggestion=f"Consider removing '{dep_name}' from dependencies if not needed",
                    )
                    issues.append(issue)

        return issues

    def _get_check_type(self) -> QACheckType:
        """Return refactor check type."""
        return QACheckType.REFACTOR

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Creosote adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.REFACTOR,
            enabled=True,
            file_patterns=["pyproject.toml", "requirements*.txt"],
            timeout_seconds=60,
            parallel_safe=True,
            stage="comprehensive",  # Dependency analysis in comprehensive stage
            settings={
                "config_file": "pyproject.toml",
                "exclude_deps": [
                    # Common dev/build tools that may not be directly imported
                    "pytest",
                    "black",
                    "ruff",
                    "mypy",
                    "pre-commit",
                    "sphinx",
                    "tox",
                ],
                "paths": ["src", "tests"],
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(CreosoteAdapter)
