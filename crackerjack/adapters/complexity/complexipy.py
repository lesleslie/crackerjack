"""Complexipy adapter for ACB QA framework - code complexity analysis.

Complexipy analyzes Python code complexity using multiple metrics:
- Cyclomatic complexity (McCabe)
- Cognitive complexity
- Maintainability index
- Lines of code metrics

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
    "01937d86-9e5f-a6b7-c8d9-e0f1a2b3c4d5"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class ComplexipySettings(ToolAdapterSettings):
    """Settings for Complexipy adapter."""

    tool_name: str = "complexipy"
    use_json_output: bool = True
    max_complexity: int = 15  # crackerjack standard
    include_cognitive: bool = True
    include_maintainability: bool = True
    sort_by: str = "complexity"  # complexity, cognitive, name


class ComplexipyAdapter(BaseToolAdapter):
    """Adapter for Complexipy - code complexity analyzer.

    Analyzes code complexity using multiple metrics:
    - Cyclomatic complexity (control flow branches)
    - Cognitive complexity (how hard code is to understand)
    - Maintainability index (overall code quality score)
    - Lines of code (LOC, SLOC)

    Features:
    - JSON output for structured analysis
    - Configurable complexity thresholds
    - Multiple complexity metrics
    - Sortable results

    Example:
        ```python
        settings = ComplexipySettings(
            max_complexity=15,
            include_cognitive=True,
            include_maintainability=True,
        )
        adapter = ComplexipyAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: ComplexipySettings | None = None

    def __init__(self, settings: ComplexipySettings | None = None) -> None:
        """Initialize Complexipy adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)
        logger.debug(
            "ComplexipyAdapter initialized",
            extra={"has_settings": settings is not None},
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = ComplexipySettings()
            logger.info("Using default ComplexipySettings")
        await super().init()
        logger.debug(
            "ComplexipyAdapter initialization complete",
            extra={
                "max_complexity": self.settings.max_complexity,
                "include_cognitive": self.settings.include_cognitive,
                "include_maintainability": self.settings.include_maintainability,
                "sort_by": self.settings.sort_by,
            },
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Complexipy (Complexity)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "complexipy"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Complexipy command.

        Args:
            files: Files/directories to analyze
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        # JSON output
        if self.settings.use_json_output:
            cmd.append("--json")

        # Max complexity threshold
        cmd.extend(["--max-complexity", str(self.settings.max_complexity)])

        # Include cognitive complexity
        if self.settings.include_cognitive:
            cmd.append("--cognitive")

        # Include maintainability index
        if self.settings.include_maintainability:
            cmd.append("--maintainability")

        # Sort results
        cmd.extend(["--sort", self.settings.sort_by])

        # Add targets
        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Complexipy command",
            extra={
                "file_count": len(files),
                "max_complexity": self.settings.max_complexity,
                "include_cognitive": self.settings.include_cognitive,
                "include_maintainability": self.settings.include_maintainability,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Complexipy JSON output into standardized issues.

        Args:
            result: Raw execution result from Complexipy

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed Complexipy JSON output",
                extra={"files_count": len(data.get("files", []))},
            )
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return self._parse_text_output(result.raw_output)

        issues = []

        # Complexipy JSON format:
        # {
        #   "files": [
        #     {
        #       "path": "file.py",
        #       "functions": [
        #         {
        #           "name": "function_name",
        #           "line": 42,
        #           "complexity": 16,
        #           "cognitive_complexity": 12,
        #           "maintainability": 65.2
        #         }
        #       ]
        #     }
        #   ]
        # }

        for file_data in data.get("files", []):
            file_path = Path(file_data.get("path", ""))

            for func in file_data.get("functions", []):
                complexity = func.get("complexity", 0)
                cognitive = func.get("cognitive_complexity", 0)
                maintainability = func.get("maintainability", 100)

                # Only report if exceeds threshold
                if complexity <= self.settings.max_complexity:
                    continue

                # Build message with all metrics
                message_parts = [f"Complexity: {complexity}"]
                if self.settings.include_cognitive:
                    message_parts.append(f"Cognitive: {cognitive}")
                if self.settings.include_maintainability:
                    message_parts.append(f"Maintainability: {maintainability:.1f}")

                message = f"Function '{func.get('name', 'unknown')}' - " + ", ".join(
                    message_parts
                )

                # Severity based on complexity level
                if complexity > self.settings.max_complexity * 2:
                    severity = "error"
                else:
                    severity = "warning"

                issue = ToolIssue(
                    file_path=file_path,
                    line_number=func.get("line"),
                    message=message,
                    code="COMPLEXITY",
                    severity=severity,
                    suggestion=f"Consider refactoring to reduce complexity below {self.settings.max_complexity}",
                )
                issues.append(issue)

        logger.info(
            "Parsed Complexipy output",
            extra={
                "total_issues": len(issues),
                "high_complexity": sum(1 for i in issues if i.severity == "error"),
                "files_affected": len(set(str(i.file_path) for i in issues)),
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        """Parse Complexipy text output (fallback).

        Args:
            output: Text output from Complexipy

        Returns:
            List of ToolIssue objects
        """
        issues = []
        lines = output.strip().split("\n")

        current_file: Path | None = None

        for line in lines:
            line = line.strip()

            # Parse file headers
            if line.startswith("File:"):
                file_str = line.replace("File:", "").strip()
                current_file = Path(file_str)
                continue

            # Parse complexity lines
            # Format: "  function_name (line 42): complexity 16"
            if "complexity" in line.lower() and current_file:
                try:
                    # Extract function name
                    if "(" in line and ")" in line:
                        func_name = line.split("(")[0].strip()
                        line_part = line.split("(")[1].split(")")[0]
                        line_number = int(line_part.replace("line", "").strip())

                        # Extract complexity
                        complexity_part = line.split("complexity")[1].strip()
                        complexity = int(complexity_part.split()[0])

                        if complexity > self.settings.max_complexity:
                            issue = ToolIssue(
                                file_path=current_file,
                                line_number=line_number,
                                message=f"Function '{func_name}' has complexity {complexity}",
                                code="COMPLEXITY",
                                severity="warning"
                                if complexity <= self.settings.max_complexity * 2
                                else "error",
                            )
                            issues.append(issue)

                except (ValueError, IndexError):
                    continue

        logger.info(
            "Parsed Complexipy text output (fallback)",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len(set(str(i.file_path) for i in issues)),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        """Return complexity check type."""
        return QACheckType.COMPLEXITY

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Complexipy adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.COMPLEXITY,
            enabled=True,
            file_patterns=["**/*.py"],
            exclude_patterns=["**/.venv/**", "**/venv/**", "**/tests/**"],
            timeout_seconds=90,
            parallel_safe=True,
            stage="comprehensive",  # Complexity analysis in comprehensive stage
            settings={
                "max_complexity": 15,
                "include_cognitive": True,
                "include_maintainability": True,
                "sort_by": "complexity",
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(ComplexipyAdapter)
