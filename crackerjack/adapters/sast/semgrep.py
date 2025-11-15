"""Semgrep adapter for ACB QA framework - Modern security scanning.

Semgrep is a fast, open-source, static analysis tool for finding bugs,
enforcing code standards, and finding security vulnerabilities.

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
    "01937d86-4f2a-7b3c-8d9e-f3b4d3c2b1a1"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class SemgrepSettings(ToolAdapterSettings):
    """Settings for Semgrep adapter."""

    tool_name: str = "semgrep"
    use_json_output: bool = True
    config: str = "p/python"  # Default ruleset
    exclude_tests: bool = True
    timeout_seconds: int = 1200


class SemgrepAdapter(BaseToolAdapter):
    """Adapter for Semgrep - Modern static analysis."""

    settings: SemgrepSettings | None = None

    def __init__(self, settings: SemgrepSettings | None = None) -> None:
        """Initialize Semgrep adapter."""
        super().__init__(settings=settings)
        logger.debug(
            "SemgrepAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = SemgrepSettings()
            logger.info("Using default SemgrepSettings")
        await super().init()
        logger.debug(
            "SemgrepAdapter initialization complete",
            extra={
                "config": self.settings.config,
                "exclude_tests": self.settings.exclude_tests,
            },
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Semgrep (Security)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "semgrep"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Semgrep command."""
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name, "scan"]

        # JSON output
        if self.settings.use_json_output:
            cmd.append("--json")

        # Config
        cmd.extend(["--config", self.settings.config])

        # Add targets
        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Semgrep command",
            extra={
                "file_count": len(files),
                "config": self.settings.config,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Semgrep JSON output into standardized issues."""
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed Semgrep JSON output",
                extra={"results_count": len(data.get("results", []))},
            )
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return []  # No text parsing for semgrep for now

        issues = []
        for item in data.get("results", []):
            file_path = Path(item.get("path", ""))
            start_line = item.get("start", {}).get("line")
            message = item.get("extra", {}).get("message", "")
            code = item.get("check_id")
            severity = item.get("extra", {}).get("severity", "WARNING").lower()

            issue = ToolIssue(
                file_path=file_path,
                line_number=start_line,
                message=message,
                code=code,
                severity=severity,
            )
            issues.append(issue)

        logger.info(
            "Parsed Semgrep output",
            extra={
                "total_issues": len(issues),
                "files_affected": len({str(i.file_path) for i in issues}),
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
        """Get default configuration for Semgrep adapter."""
        from crackerjack.models.qa_config import QACheckConfig

        # Dynamically detect package directory
        package_dir = self._detect_package_directory()

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SAST,
            enabled=True,
            file_patterns=[f"{package_dir}/**/*.py"],
            exclude_patterns=[
                "**/test_*.py",
                "**/tests/**",
            ],
            timeout_seconds=1200,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "config": "p/python",
                "exclude_tests": True,
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(SemgrepAdapter)
