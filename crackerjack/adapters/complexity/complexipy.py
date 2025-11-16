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
    sort_by: str = (
        "desc"  # Valid options: asc, desc, name (sorts by complexity descending)
    )


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
            # Load max_complexity from pyproject.toml and use it to initialize settings
            config_data = self._load_config_from_pyproject()
            max_complexity = config_data.get("max_complexity", 15)
            self.settings = ComplexipySettings(max_complexity=max_complexity)
            logger.info(
                "Using default ComplexipySettings",
                extra={"max_complexity": max_complexity},
            )
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

        # JSON output (correct flag: --output-json, not --json)
        if self.settings.use_json_output:
            cmd.append("--output-json")

        # Max complexity threshold (correct flag: --max-complexity-allowed, not --max-complexity)
        # Load max_complexity from pyproject.toml configuration instead of settings
        config_data = self._load_config_from_pyproject()
        max_complexity = config_data.get("max_complexity", self.settings.max_complexity)
        cmd.extend(["--max-complexity-allowed", str(max_complexity)])

        # NOTE: --cognitive and --maintainability flags don't exist in complexipy
        # Complexity tool only reports cyclomatic complexity, not cognitive/maintainability
        # These settings are kept in ComplexipySettings for backwards compatibility but ignored

        # Sort results
        cmd.extend(["--sort", self.settings.sort_by])

        # Add targets - files are already filtered by _get_target_files based on config
        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Complexipy command",
            extra={
                "file_count": len(files),
                "max_complexity": max_complexity,
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

        Complexipy with --output-json saves JSON to a file and outputs a pretty table
        to stdout. We need to read the JSON file, not parse stdout.

        Args:
            result: Raw execution result from Complexipy

        Returns:
            List of parsed issues
        """
        # Complexipy saves JSON to complexipy.json in the working directory
        json_file = Path.cwd() / "complexipy.json"

        if self.settings.use_json_output and json_file.exists():
            try:
                with json_file.open() as f:
                    data = json.load(f)
                logger.debug(
                    "Read Complexipy JSON file",
                    extra={
                        "file": str(json_file),
                        "entries": len(data) if isinstance(data, list) else "N/A",
                    },
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(
                    "Failed to read JSON file, falling back to stdout parsing",
                    extra={"error": str(e), "file": str(json_file)},
                )
                return self._parse_text_output(result.raw_output)
        else:
            # Fall back to parsing stdout (legacy mode or if JSON file not found)
            if not result.raw_output:
                logger.debug("No output to parse")
                return []

            try:
                data = json.loads(result.raw_output)
                logger.debug(
                    "Parsed Complexipy JSON from stdout",
                    extra={"entries": len(data) if isinstance(data, list) else "N/A"},
                )
            except json.JSONDecodeError as e:
                logger.warning(
                    "JSON parse failed, falling back to text parsing",
                    extra={"error": str(e), "output_preview": result.raw_output[:200]},
                )
                return self._parse_text_output(result.raw_output)

        issues = self._process_complexipy_data(data)

        logger.info(
            "Parsed Complexipy output",
            extra={
                "total_issues": len(issues),
                "high_complexity": sum(1 for i in issues if i.severity == "error"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _process_complexipy_data(self, data: list | dict) -> list[ToolIssue]:
        """Process the complexipy JSON data to extract issues.

        Args:
            data: Parsed JSON data from complexipy (flat list or legacy nested dict)

        Returns:
            List of ToolIssue objects
        """
        issues = []

        # Handle flat list structure (current complexipy format)
        if isinstance(data, list):
            for func in data:
                complexity = func.get("complexity", 0)
                if complexity <= self.settings.max_complexity:
                    continue

                file_path = Path(func.get("path", ""))
                function_name = func.get("function_name", "unknown")
                severity = (
                    "error"
                    if complexity > self.settings.max_complexity * 2
                    else "warning"
                )

                issue = ToolIssue(
                    file_path=file_path,
                    line_number=None,  # complexipy JSON doesn't include line numbers
                    message=f"Function '{function_name}' - Complexity: {complexity}",
                    code="COMPLEXITY",
                    severity=severity,
                    suggestion=f"Consider refactoring to reduce complexity below {self.settings.max_complexity}",
                )
                issues.append(issue)
            return issues

        # Handle legacy nested structure (backwards compatibility)
        for file_data in data.get("files", []):
            file_path = Path(file_data.get("path", ""))
            issues.extend(
                self._process_file_data(file_path, file_data.get("functions", []))
            )
        return issues

    def _process_file_data(
        self, file_path: Path, functions: list[dict]
    ) -> list[ToolIssue]:
        """Process function data for a specific file.

        Args:
            file_path: Path of the file being analyzed
            functions: List of function data from complexipy

        Returns:
            List of ToolIssue objects for this file
        """
        issues = []
        for func in functions:
            issue = self._create_issue_if_needed(file_path, func)
            if issue:
                issues.append(issue)
        return issues

    def _create_issue_if_needed(self, file_path: Path, func: dict) -> ToolIssue | None:
        """Create an issue if complexity exceeds threshold.

        Args:
            file_path: Path of the file containing the function
            func: Function data from complexipy

        Returns:
            ToolIssue if needed, otherwise None
        """
        complexity = func.get("complexity", 0)

        # Only report if exceeds threshold
        if complexity <= self.settings.max_complexity:
            return None

        message = self._build_issue_message(func, complexity)
        severity = self._determine_issue_severity(complexity)

        return ToolIssue(
            file_path=file_path,
            line_number=func.get("line"),
            message=message,
            code="COMPLEXITY",
            severity=severity,
            suggestion=f"Consider refactoring to reduce complexity below {self.settings.max_complexity}",
        )

    def _build_issue_message(self, func: dict, complexity: int) -> str:
        """Build the message for a complexity issue.

        Args:
            func: Function data from complexipy
            complexity: Complexity value

        Returns:
            Formatted message string
        """
        message_parts = [f"Complexity: {complexity}"]

        if self.settings.include_cognitive:
            cognitive = func.get("cognitive_complexity", 0)
            message_parts.append(f"Cognitive: {cognitive}")

        if self.settings.include_maintainability:
            maintainability = func.get("maintainability", 100)
            message_parts.append(f"Maintainability: {maintainability:.1f}")

        return f"Function '{func.get('name', 'unknown')}' - " + ", ".join(message_parts)

    def _determine_issue_severity(self, complexity: int) -> str:
        """Determine the severity of the issue based on complexity.

        Args:
            complexity: Complexity value

        Returns:
            "error" or "warning" based on threshold
        """
        if complexity > self.settings.max_complexity * 2:
            return "error"
        return "warning"

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
            current_file = self._update_current_file(line, current_file)
            if "complexity" in line.lower() and current_file:
                issue = self._parse_complexity_line(line, current_file)
                if issue:
                    issues.append(issue)

        logger.info(
            "Parsed Complexipy text output (fallback)",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _update_current_file(self, line: str, current_file: Path | None) -> Path | None:
        """Update current file based on line content.

        Args:
            line: Current line from output
            current_file: Current file path

        Returns:
            Updated file path
        """
        if line.strip().startswith("File:"):
            file_str = line.strip().replace("File:", "").strip()
            return Path(file_str)
        return current_file

    def _parse_complexity_line(self, line: str, current_file: Path) -> ToolIssue | None:
        """Parse a line containing complexity information.

        Args:
            line: Line from text output
            current_file: Current file path

        Returns:
            ToolIssue if valid complexity data found, otherwise None
        """
        with suppress(ValueError, IndexError):
            func_data = self._extract_function_data(line)
            if func_data:
                func_name, line_number, complexity = func_data
                if complexity > self.settings.max_complexity:
                    severity = (
                        "error"
                        if complexity > self.settings.max_complexity * 2
                        else "warning"
                    )
                    return ToolIssue(
                        file_path=current_file,
                        line_number=line_number,
                        message=f"Function '{func_name}' has complexity {complexity}",
                        code="COMPLEXITY",
                        severity=severity,
                    )

        return None

    def _extract_function_data(self, line: str) -> tuple[str, int, int] | None:
        """Extract function name, line number, and complexity from a line.

        Args:
            line: Line from text output

        Returns:
            Tuple of (function name, line number, complexity) or None
        """
        line = line.strip()
        if "(" in line and ")" in line and "complexity" in line.lower():
            func_name = line.split("(")[0].strip()
            line_part = line.split("(")[1].split(")")[0]
            line_number = int(line_part.replace("line", "").strip())
            complexity_part = line.split("complexity")[1].strip()
            complexity = int(complexity_part.split()[0])
            return func_name, line_number, complexity

        return None

    def _get_check_type(self) -> QACheckType:
        """Return complexity check type."""
        return QACheckType.COMPLEXITY

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for Complexipy adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        # Load configuration from pyproject.toml to get actual exclude patterns and max_complexity
        config_data = self._load_config_from_pyproject()
        exclude_patterns = config_data.get(
            "exclude_patterns", ["**/.venv/**", "**/venv/**", "**/tests/**"]
        )
        max_complexity = config_data.get("max_complexity", 15)

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.COMPLEXITY,
            enabled=True,
            file_patterns=["**/*.py"],
            exclude_patterns=exclude_patterns,
            timeout_seconds=90,
            parallel_safe=True,
            stage="comprehensive",  # Complexity analysis in comprehensive stage
            settings={
                "max_complexity": max_complexity,
                "include_cognitive": True,
                "include_maintainability": True,
                "sort_by": "complexity",
            },
        )

    def _load_config_from_pyproject(self) -> dict:
        """Load complexipy configuration from pyproject.toml.

        Returns:
            Dictionary with complexipy configuration or defaults
        """
        import tomllib
        from pathlib import Path

        pyproject_path = Path.cwd() / "pyproject.toml"
        config = {
            "exclude_patterns": ["**/.venv/**", "**/venv/**", "**/tests/**"],
            "max_complexity": 15,
        }

        if pyproject_path.exists():
            try:
                with pyproject_path.open("rb") as f:
                    toml_config = tomllib.load(f)
                complexipy_config = toml_config.get("tool", {}).get("complexipy", {})

                # Load exclude patterns if specified
                exclude_patterns = complexipy_config.get("exclude_patterns")
                if exclude_patterns:
                    config["exclude_patterns"] = exclude_patterns
                    logger.info(
                        "Loaded exclude patterns from pyproject.toml",
                        extra={"exclude_patterns": exclude_patterns},
                    )

                # Load max complexity if specified
                max_complexity = complexipy_config.get("max_complexity")
                if max_complexity is not None:
                    config["max_complexity"] = max_complexity
                    logger.info(
                        "Loaded max_complexity from pyproject.toml",
                        extra={"max_complexity": max_complexity},
                    )
            except (tomllib.TOMLDecodeError, OSError) as e:
                logger.warning(
                    "Failed to load complexipy config from pyproject.toml, using defaults",
                    extra={"error": str(e)},
                )

        return config

    def _load_exclude_patterns_from_config(self) -> list[str]:
        """Load exclude patterns from pyproject.toml configuration.

        Returns:
            List of exclude patterns from pyproject.toml or defaults
        """
        config = self._load_config_from_pyproject()
        return config.get(
            "exclude_patterns", ["**/.venv/**", "**/venv/**", "**/tests/**"]
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(ComplexipyAdapter)
