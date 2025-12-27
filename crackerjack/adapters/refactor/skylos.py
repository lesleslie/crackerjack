"""Skylos adapter for Crackerjack QA framework - dead code detection.

Skylos identifies unused imports, functions, classes, and variables in Python codebases.
It helps maintain clean code by detecting elements that are no longer used.

Standard Python Patterns:
- MODULE_ID and MODULE_STATUS at module level (static UUID)
- No ACB dependency injection
- Extends BaseToolAdapter for tool execution
- Async execution with output parsing
"""

from __future__ import annotations

import json
import logging
import typing as t
from pathlib import Path
from uuid import UUID

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
MODULE_ID = UUID("445401b8-b273-47f1-9015-22e721757d46")
MODULE_STATUS = AdapterStatus.STABLE

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

        # Add targets - use package directory to avoid scanning .venv
        target = self._determine_scan_target(files)
        cmd.append(target)

        logger.info(
            "Built Skylos command",
            extra={
                "file_count": len(files) if files else 1,
                "confidence_threshold": self.settings.confidence_threshold,
                "target_directory": target,
            },
        )
        return cmd

    def _determine_scan_target(self, files: list[Path]) -> str:
        """Determine the target directory or files for scanning.

        Args:
            files: Files specified by user

        Returns:
            Target string for Skylos command
        """
        if files:
            # Join multiple files into a single string
            return " ".join(str(f) for f in files)

        # Auto-detect package directory
        package_name = self._detect_package_name()
        return f"./{package_name}"

    def _detect_package_name(self) -> str:
        """Detect package name from pyproject.toml or directory structure.

        Returns:
            Package name to scan
        """
        cwd = Path.cwd()

        # Try reading from pyproject.toml
        package_name = self._read_package_from_toml(cwd)
        if package_name:
            return package_name

        # Fallback: find first directory with __init__.py
        package_name = self._find_package_directory(cwd)
        if package_name:
            return package_name

        # Default fallback
        return "crackerjack"

    def _read_package_from_toml(self, cwd: Path) -> str | None:
        """Read package name from pyproject.toml.

        Args:
            cwd: Current working directory

        Returns:
            Package name if found, None otherwise
        """
        import tomllib
        from contextlib import suppress

        pyproject_path = cwd / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        with suppress(Exception):
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
                project_name = data.get("project", {}).get("name")
                if project_name:
                    return project_name.replace("-", "_")

        return None

    def _find_package_directory(self, cwd: Path) -> str | None:
        """Find package directory with __init__.py.

        Args:
            cwd: Current working directory

        Returns:
            Package directory name if found, None otherwise
        """
        excluded = {"tests", "docs", ".venv", "venv", "build", "dist"}

        for item in cwd.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                if item.name not in excluded:
                    return item.name

        return None

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

        # Try JSON parsing first, fallback to text parsing
        try:
            issues = self._parse_json_output(result.raw_output)
        except json.JSONDecodeError:
            logger.debug(
                "JSON parse failed, falling back to text parsing",
                extra={"output_preview": result.raw_output[:200]},
            )
            issues = self._parse_text_output(result.raw_output)

        logger.info(
            "Parsed Skylos output",
            extra={
                "total_issues": len(issues),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _parse_json_output(self, output: str) -> list[ToolIssue]:
        """Parse Skylos JSON output.

        Args:
            output: JSON output from Skylos

        Returns:
            List of parsed issues
        """
        data = json.loads(output)
        logger.debug(
            "Parsed Skylos JSON output",
            extra={"results_count": len(data.get("dead_code", []))},
        )

        issues = []
        for item in data.get("dead_code", []):
            issue = self._create_issue_from_json(item)
            issues.append(issue)

        return issues

    def _create_issue_from_json(self, item: dict) -> ToolIssue:
        """Create ToolIssue from JSON item.

        Args:
            item: JSON item representing dead code

        Returns:
            ToolIssue object
        """
        file_path = Path(item.get("file", ""))
        code_type = item.get("type", "code")
        code_name = item.get("name", "")
        confidence = item.get("confidence", "unknown")

        return ToolIssue(
            file_path=file_path,
            line_number=item.get("line"),
            message=f"Dead {code_type}: {code_name}",
            code=code_type,
            severity="warning",  # Dead code is typically a warning
            suggestion=f"Confidence: {confidence}%",
        )

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

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Skylos text output (fallback)",
            extra={"total_issues": len(issues)},
        )
        return issues

    def _parse_text_line(self, line: str) -> ToolIssue | None:
        """Parse a single Skylos text output line.

        Args:
            line: Line of text output

        Returns:
            ToolIssue if parsing successful, None otherwise
        """
        try:
            # Parse format: "file.py:line: message (confidence: XX%)"
            parts = line.split(":", 2)
            if len(parts) < 3:
                return None

            file_path = Path(parts[0].strip())
            line_number = self._parse_line_number(parts[1])
            message_part = parts[2].strip()

            confidence = self._extract_confidence_from_message(message_part)

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                message=message_part,
                severity="warning",
                suggestion=f"Confidence: {confidence}",
            )

        except (ValueError, IndexError):
            return None

    def _parse_line_number(self, line_part: str) -> int | None:
        """Parse line number from text part.

        Args:
            line_part: Part containing line number

        Returns:
            Line number if valid, None otherwise
        """
        try:
            return int(line_part.strip())
        except ValueError:
            return None

    def _extract_confidence_from_message(self, message_part: str) -> str:
        """Extract confidence percentage from message.

        Args:
            message_part: Message containing confidence info

        Returns:
            Confidence value or "unknown"
        """
        if "(confidence:" not in message_part:
            return "unknown"

        conf_start = message_part.find("(confidence:") + len("(confidence:")
        conf_end = message_part.find(")", conf_start)
        if conf_end != -1:
            return message_part[conf_start:conf_end].strip()

        return "unknown"

    def _get_check_type(self) -> QACheckType:
        """Return refactor check type."""
        return QACheckType.REFACTOR

    def _detect_package_directory(self) -> str:
        """Detect the package directory name from pyproject.toml.

        Returns:
            Package directory name (e.g., 'crackerjack', 'session_buddy')
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
        """Get default configuration for Skylos adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        # Dynamically detect package directory
        package_dir = self._detect_package_directory()

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.REFACTOR,  # Dead code detection is refactoring
            enabled=True,
            file_patterns=[
                f"{package_dir}/**/*.py"
            ],  # Dynamically detected package directory
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
