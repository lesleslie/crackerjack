"""Creosote adapter for Crackerjack QA framework - unused dependency detection.

Creosote identifies dependencies listed in project configuration (pyproject.toml,
requirements.txt) that are not actually used in the codebase, helping to:
- Keep dependencies lean
- Reduce security surface area
- Speed up installations
- Maintain clean dependency trees

Standard Python Patterns:
- MODULE_ID and MODULE_STATUS at module level (static UUID)
- No ACB dependency injection
- Extends BaseToolAdapter for tool execution
- Async execution with output parsing
"""

from __future__ import annotations

import logging
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
MODULE_ID = UUID("c4c0c9fc-43d8-4b17-afb5-4febacec2e90")
MODULE_STATUS = AdapterStatus.STABLE

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


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
        logger.debug(
            "CreosoteAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = CreosoteSettings()
            logger.info("Using default CreosoteSettings")
        await super().init()
        logger.debug(
            "CreosoteAdapter initialization complete",
            extra={
                "has_config_file": self.settings.config_file is not None,
                "exclude_deps_count": len(self.settings.exclude_deps),
                "scan_paths_count": len(self.settings.paths),
            },
        )

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

    async def _get_target_files(
        self, files: list[Path] | None, config: QACheckConfig | None
    ) -> list[Path]:
        """Get target files for dependency analysis.

        Creosote scans the entire project based on pyproject.toml,
        so we just return a marker file to trigger execution.

        Args:
            files: Optional explicit file list
            config: Optional configuration

        Returns:
            List containing pyproject.toml to indicate project scan
        """
        if files:
            return files

        # Return pyproject.toml as marker - creosote scans whole project
        pyproject = Path.cwd() / "pyproject.toml"
        return [pyproject] if pyproject.exists() else []

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

        logger.info(
            "Built Creosote command",
            extra={
                "has_config_file": self.settings.config_file is not None,
                "exclude_deps_count": len(self.settings.exclude_deps),
                "scan_paths_count": len(self.settings.paths),
            },
        )
        return cmd

    def _is_unused_deps_section_start(self, line: str) -> bool:
        """Check if the line indicates the start of unused dependencies section."""
        return "unused" in line.lower() and "dependenc" in line.lower()

    def _process_dependency_line(self, line: str) -> str | None:
        """Process a dependency line and return the dependency name if valid."""
        # Remove leading dashes or bullets
        dep_name = line.lstrip("- ").strip()

        if dep_name:
            return dep_name
        return None

    def _create_issue_for_dependency(
        self, dep_name: str, config_file: Path
    ) -> ToolIssue:
        """Create a ToolIssue for an unused dependency."""
        return ToolIssue(
            file_path=config_file,
            message=f"Unused dependency: {dep_name}",
            code="UNUSED_DEP",
            severity="warning",
            suggestion=f"Consider removing '{dep_name}' from dependencies if not needed",
        )

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
            logger.debug("No output to parse")
            return []

        issues = []
        lines = result.raw_output.strip().split("\n")
        logger.debug("Parsing Creosote text output", extra={"line_count": len(lines)})

        # Creosote output format:
        # "Found unused dependencies:"
        # "  package-name"
        # "  another-package"

        parsing_unused = False
        config_file = (
            self.settings.config_file if self.settings else Path("pyproject.toml")
        )

        for line in lines:
            line = line.strip()

            # Start of unused dependencies section
            if self._is_unused_deps_section_start(line):
                parsing_unused = True
                continue

            # Empty line ends section
            if not line:
                parsing_unused = False
                continue

            # Parse dependency names
            if parsing_unused and line:
                dep_name = self._process_dependency_line(line)
                if dep_name:
                    issue = self._create_issue_for_dependency(dep_name, config_file)
                    issues.append(issue)

        logger.info(
            "Parsed Creosote output",
            extra={
                "total_unused": len(issues),
                "config_file": str(config_file),
            },
        )
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
                    "sphinx",
                    "tox",
                ],
                "paths": ["src", "tests"],
            },
        )
