"""Skylos adapter for ACB QA framework - dead code detection.

Skylos identifies unused imports, functions, classes, and variables in Python codebases.
It helps maintain clean code by detecting elements that are no longer used.

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Extends BaseToolAdapter for tool execution
- Async execution with output parsing
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
    "01937d86-5f2a-7b3c-9d1e-a2b3c4d5e6f8"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class SkylosSettings(ToolAdapterSettings):
    """Settings for Skylos adapter."""

    tool_name: str = "skylos"
    use_json_output: bool = True  # Skylos supports JSON output
    confidence_threshold: int = 86
    web_dashboard_port: int = 5090


class SkylosAdapter(BaseToolAdapter):
    """Adapter for Skylos - dead code detector.

    Identifies unused imports, functions, classes, variables, and other code elements.
    Helps maintain clean codebases by detecting dead code that can be safely removed.

    Features:
    - Confidence-based detection
    - JSON output for structured analysis
    - Integration with web dashboard
    - Configurable confidence thresholds

    Example:
        ```python
        settings = SkylosSettings(
            confidence_threshold=90,
            web_dashboard_port=5091,
        )
        adapter = SkylosAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: SkylosSettings | None = None

    def __init__(self, settings: SkylosSettings | None = None) -> None:
        """Initialize Skylos adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)
        logger.debug(
            "SkylosAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = SkylosSettings()
            logger.info("Using default SkylosSettings")
        await super().init()
        logger.debug(
            "SkylosAdapter initialization complete",
            extra={"confidence_threshold": self.settings.confidence_threshold},
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Skylos (Dead Code)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "skylos"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Skylos command.

        Args:
            files: Files/directories to scan for dead code
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = ["uv", "run", "skylos"]

        # Add confidence threshold
        cmd.extend(["--confidence", str(self.settings.confidence_threshold)])

        # JSON output for structured parsing
        if self.settings.use_json_output:
            cmd.append("--json")

        # Add targets - use package directory instead of current directory
        # to avoid scanning .venv and other unnecessary locations
        if files:
            cmd.extend([str(f) for f in files])
        else:
            # Determine package name similar to tool_commands.py to target only package
            import tomllib
            from contextlib import suppress

            cwd = Path.cwd()
            package_name = None

            # First try to read from pyproject.toml
            pyproject_path = cwd / "pyproject.toml"
            if pyproject_path.exists():
                with suppress(Exception):
                    with pyproject_path.open("rb") as f:
                        data = tomllib.load(f)
                        project_name = data.get("project", {}).get("name")
                        if project_name:
                            package_name = project_name.replace("-", "_")

            # Fallback: find first directory with __init__.py in project root
            if not package_name:
                for item in cwd.iterdir():
                    if item.is_dir() and (item / "__init__.py").exists():
                        if item.name not in {"tests", "docs", ".venv", "venv", "build", "dist"}:
                            package_name = item.name
                            break

            # Default to 'crackerjack' if nothing found
            if not package_name:
                package_name = "crackerjack"

            cmd.append(f"./{package_name}")

        logger.info(
            "Built Skylos command",
            extra={
                "file_count": len(files) if files else 1,
                "confidence_threshold": self.settings.confidence_threshold,
                "target_directory": cmd[-1],  # Last element should be the target
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Skylos output into standardized issues.

        Args:
            result: Raw execution result from Skylos

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        issues = []

        # Try to parse as JSON first (Skylos JSON output format)
        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed Skylos JSON output",
                extra={"results_count": len(data.get("dead_code", []))},
            )

            for item in data.get("dead_code", []):
                file_path = Path(item.get("file", ""))

                issue = ToolIssue(
                    file_path=file_path,
                    line_number=item.get("line"),
                    message=f"Dead {item.get('type', 'code')}: {item.get('name', '')}",
                    code=item.get("type"),
                    severity="warning",  # Dead code is typically a warning
                    suggestion=f"Confidence: {item.get('confidence', 'unknown')}%",
                )
                issues.append(issue)

        except json.JSONDecodeError:
            # Fallback to text parsing if JSON fails
            logger.warning(
                "JSON parse failed, falling back to text parsing",
                extra={"output_preview": result.raw_output[:200]},
            )
            issues = self._parse_text_output(result.raw_output)

        logger.info(
            "Parsed Skylos output",
            extra={
                "total_issues": len(issues),
                "files_affected": len(set(str(i.file_path) for i in issues)),
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        """Parse Skylos text output (fallback).

        Args:
            output: Text output from Skylos

        Returns:
            List of ToolIssue objects
        """
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or ":" not in line:
                continue

            try:
                # Parse format: "file.py:line: message (confidence: XX%)"
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue

                file_path = Path(parts[0].strip())

                try:
                    line_number = int(parts[1].strip())
                except ValueError:
                    line_number = None

                message_part = parts[2].strip()

                # Extract confidence if present
                confidence = "unknown"
                if "(confidence:" in message_part:
                    conf_start = message_part.find("(confidence:") + len("(confidence:")
                    conf_end = message_part.find(")", conf_start)
                    if conf_end != -1:
                        confidence = message_part[conf_start:conf_end].strip()

                issue = ToolIssue(
                    file_path=file_path,
                    line_number=line_number,
                    message=message_part,
                    severity="warning",
                    suggestion=f"Confidence: {confidence}",
                )
                issues.append(issue)

            except (ValueError, IndexError):
                continue

        logger.info(
            "Parsed Skylos text output (fallback)",
            extra={"total_issues": len(issues)},
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        """Return refactor check type."""
        return QACheckType.REFACTOR

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Skylos adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.REFACTOR,  # Dead code detection is refactoring
            enabled=True,
            file_patterns=["crackerjack/**/*.py"],  # Target package directory
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
            timeout_seconds=300,
            parallel_safe=True,
            stage="comprehensive",  # Dead code detection in comprehensive stage
            settings={
                "confidence_threshold": 86,
                "web_dashboard_port": 5090,
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(SkylosAdapter)
