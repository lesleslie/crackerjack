"""Zuban adapter for ACB QA framework - ultra-fast Python type checking.

Zuban is a Rust-based type checker for Python, offering 20-200x faster type checking
compared to traditional tools like pyright or mypy. It provides:
- Static type analysis
- Type inference
- Generic type checking
- Protocol compliance validation

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Extends BaseToolAdapter for tool execution
- Async execution with JSON output parsing
"""

from __future__ import annotations

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
    "01937d86-6b2c-7d3e-8f4a-b5c6d7e8f9a0"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class ZubanSettings(ToolAdapterSettings):
    """Settings for Zuban adapter."""

    tool_name: str = "zuban"
    use_json_output: bool = False  # Zuban doesn't support JSON output
    strict_mode: bool = False
    ignore_missing_imports: bool = False
    follow_imports: str = "normal"  # normal, skip, silent
    cache_dir: Path | None = None
    incremental: bool = True
    warn_unused_ignores: bool = False  # Not supported by zuban directly


class ZubanAdapter(BaseToolAdapter):
    """Adapter for Zuban - ultra-fast Rust-based Python type checker.

    Performs static type analysis with exceptional performance:
    - Type checking 20-200x faster than pyright
    - Type inference and validation
    - Generic type support
    - Protocol compliance checking

    Features:
    - JSON output for structured error reporting
    - Incremental type checking with caching
    - Strict mode for enhanced type safety
    - Import following configuration
    - Parallel execution support

    Example:
        ```python
        settings = ZubanSettings(
            strict_mode=True,
            follow_imports="normal",
            incremental=True,
        )
        adapter = ZubanAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/")])
        ```
    """

    settings: ZubanSettings | None = None

    def __init__(self, settings: ZubanSettings | None = None) -> None:
        """Initialize Zuban adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__(settings=settings)
        logger.debug(
            "ZubanAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        """Initialize adapter with default settings."""
        if not self.settings:
            self.settings = ZubanSettings()
            logger.info("Using default ZubanSettings")
        await super().init()
        logger.debug(
            "ZubanAdapter initialization complete",
            extra={
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
                "has_cache_dir": self.settings.cache_dir is not None,
            },
        )

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Zuban (Type Check)"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        """CLI tool name."""
        return "zuban"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build Zuban command.

        Args:
            files: Files/directories to type check
            config: Optional configuration override

        Returns:
            Command as list of strings
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        # Use mypy-compatible command as it's more likely to have expected behavior
        cmd = [self.tool_name, "mypy", "--config-file", "mypy.ini"]

        # Strict mode
        if self.settings.strict_mode:
            cmd.append("--strict")

        # Ignore missing imports
        if self.settings.ignore_missing_imports:
            cmd.append("--ignore-missing-imports")

        # Follow imports
        if self.settings.follow_imports == "normal":
            pass  # default
        elif self.settings.follow_imports == "skip":
            cmd.append("--follow-untyped-imports")
        elif self.settings.follow_imports == "silent":
            # Doesn't have a direct equivalent, skipping for now
            pass

        # Cache directory
        if self.settings.cache_dir:
            cmd.extend(["--cache-dir", str(self.settings.cache_dir)])

        # NOTE: Zuban doesn't support incremental checking with mypy subcommand
        # Skipping --incremental flag to prevent execution errors
        # if self.settings.incremental:
        #     cmd.append("--incremental")

        # Add targets
        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Zuban command",
            extra={
                "file_count": len(files),
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
                "has_cache_dir": self.settings.cache_dir is not None,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse Zuban text output into standardized issues.

        Args:
            result: Raw execution result from Zuban

        Returns:
            List of parsed issues
        """
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        logger.debug(
            "Parsing Zuban text output",
            extra={"output_length": len(result.raw_output)},
        )

        # Parse text output as zuban doesn't support JSON format
        return self._parse_text_output(result.raw_output)

    def _check_has_column(self, parts: list[str]) -> tuple[bool, int | None]:
        """Check if parts[2] is a column number and return it if so."""
        has_column = parts[2].strip().isdigit()
        column_number = int(parts[2].strip()) if has_column else None
        return has_column, column_number

    def _parse_with_column_format(
        self, file_path_str: str, line_str: str, parts: list[str]
    ) -> tuple[Path, int, int | None, str, str] | None:
        """Parse format: file:line:col: error: message [code]."""
        if not line_str.isdigit():
            return None

        line_number = int(line_str)
        column_number = int(line_str)

        # Third part would be the error type
        severity_and_message = parts[2].strip() if len(parts) > 2 else ""
        message_with_code = parts[3].strip() if len(parts) > 3 else severity_and_message

        # Extract code from message (like [operator])
        message, code = self._extract_message_and_code(message_with_code)

        return (Path(file_path_str), line_number, column_number, message, code)

    def _parse_without_column_format(
        self, file_path_str: str, line_str: str, parts: list[str]
    ) -> tuple[Path, int, int | None, str, str]:
        """Parse format: file:line: error: message [code] (no column)."""
        file_path = Path(file_path_str)
        message_with_code = (
            parts[2].strip() + ":" + parts[3].strip()
            if len(parts) > 3
            else parts[2].strip()
        )
        message, code = self._extract_message_and_code(message_with_code)
        # No column number in this format
        return file_path, int(line_str), None, message, code

    def _parse_standard_format(
        self, file_path_str: str, line_str: str, parts: list[str]
    ) -> tuple[Path, int, int | None, str, str]:
        """Parse standard format: file:line: error: message [code]."""
        file_path = Path(file_path_str)
        line_number = int(line_str)

        # Second part after colon is severity/error type
        severity_and_message = parts[2].strip()
        message_with_code = parts[3].strip() if len(parts) > 3 else severity_and_message

        # Extract message and code
        message, code = self._extract_message_and_code(message_with_code)

        return file_path, line_number, None, message, code

    def _extract_parts_from_line(
        self, line: str
    ) -> tuple[Path, int, int | None, str, str] | None:
        """Extract path, line, column, severity and message from a line."""
        # Handle zuban output: "file:line: error: message  [code]"
        if ":" not in line:
            return None

        # Split at colons, but be careful with colon positions
        # Format: file:line: error: message [code]
        parts = line.split(":", maxsplit=3)
        if len(parts) < 3:
            return None

        try:
            file_path_str = parts[0].strip()
            line_str = parts[1].strip()

            if not line_str:
                # If second part after colon is empty, it might have column info
                # Maybe format is: file:line:col: error: message [code]
                if len(parts) >= 4:
                    line_str = parts[1].strip()
                    int(line_str)

                    # Check if second part is a column number
                    result = self._parse_with_column_format(
                        file_path_str, line_str, parts
                    )
                    if result is not None:
                        return result

                    # Not column format, try without column
                    return self._parse_without_column_format(
                        file_path_str, line_str, parts
                    )
                else:
                    return None
            else:
                # Format: file:line: error: message [code]
                return self._parse_standard_format(file_path_str, line_str, parts)
        except (ValueError, IndexError):
            return None

    def _extract_message_and_code(self, message_and_code_str: str) -> tuple[str, str]:
        """Extract message and code from format like 'error: message [code]'."""
        # Split on first space after "error:" to separate severity from message
        if " error: " in message_and_code_str:
            _, message_part = message_and_code_str.split(" error: ", 1)
        elif " warning: " in message_and_code_str:
            _, message_part = message_and_code_str.split(" warning: ", 1)
        else:
            message_part = message_and_code_str

        # Extract code from [code] brackets
        code = ""
        if " [" in message_part and "]" in message_part:
            start_bracket = message_part.rfind(" [")
            end_bracket = message_part.rfind("]")
            if (
                start_bracket != -1
                and end_bracket != -1
                and end_bracket > start_bracket
            ):
                code = message_part[
                    start_bracket + 2 : end_bracket
                ]  # Extract content between [ and ]
                message_part = message_part[
                    :start_bracket
                ].strip()  # Everything before the bracket

        return message_part.strip(), code

    def _determine_severity_and_message(
        self,
        severity_and_message: str,
        has_column: bool,
        parts: list[str],
        original_message: str,
    ) -> tuple[str, str]:
        """Determine severity and clean up message from the severity_and_message part."""
        # Default to error severity
        severity = "error"
        message = original_message

        if severity_and_message.lower().startswith("warning"):
            severity = "warning"
            message = (
                severity_and_message[len("warning") :].strip()
                if not has_column or len(parts) <= 4
                else original_message
            )
        elif severity_and_message.lower().startswith("error"):
            message = (
                severity_and_message[len("error") :].strip()
                if not has_column or len(parts) <= 4
                else original_message
            )

        return severity, message

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        """Parse Zuban text output.

        Args:
            output: Text output from Zuban

        Returns:
            List of ToolIssue objects
        """
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            # Skip lines that don't contain error information
            if ":" not in line or ("error:" not in line and "warning:" not in line):
                continue

            # Skip summary lines like "Found X error(s) in Y file(s)"
            if (
                "Found" in line
                and ("error" in line or "warning" in line)
                and "file" in line
            ):
                continue

            # Parse error line in format: "file:line: error: message [code]"
            parts_result = self._extract_parts_from_line(line)
            if parts_result is None:
                continue

            (
                file_path,
                line_number,
                column_number,
                message,
                code,
            ) = parts_result

            # Determine severity from message content
            severity = "error" if "error:" in line else "warning"

            issue = ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                code=code,
                severity=severity,
            )
            issues.append(issue)

        logger.info(
            "Parsed Zuban text output",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        """Return type check type."""
        return QACheckType.TYPE

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
        """Get default configuration for Zuban adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        # Dynamically detect package directory
        package_dir = self._detect_package_directory()

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.TYPE,
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
            timeout_seconds=180,  # Type checking can be slower
            parallel_safe=True,
            stage="comprehensive",  # Type checking in comprehensive stage
            settings={
                "strict_mode": False,
                "incremental": False,  # Disable to avoid config cache issues
                "follow_imports": "normal",
                "warn_unused_ignores": False,  # Disable to avoid config issues
                "ignore_missing_imports": True,  # Avoid errors from missing imports
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(ZubanAdapter)
