"""Base adapter for external tool integration in ACB QA framework.

Provides shared functionality for adapters that wrap external CLI tools
like Ruff, Zuban, Bandit, Gitleaks, etc.

ACB Patterns:
- Extends QAAdapterBase for ACB compliance
- Async subprocess execution with timeout/cancellation
- Standardized output parsing and error handling
- Tool availability validation
- Version detection and caching
"""

from __future__ import annotations

import asyncio
import shutil
import typing as t
from abc import abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from crackerjack.adapters._qa_adapter_base import QAAdapterBase, QABaseSettings
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig


@dataclass
class ToolIssue:
    """Represents a single issue found by a tool.

    Standardized format for all tool outputs.
    """

    file_path: Path
    line_number: int | None = None
    column_number: int | None = None
    message: str = ""
    code: str | None = None
    severity: str = "error"
    suggestion: str | None = None

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for serialization."""
        return {
            "file_path": str(self.file_path),
            "line_number": self.line_number,
            "column_number": self.column_number,
            "message": self.message,
            "code": self.code,
            "severity": self.severity,
            "suggestion": self.suggestion,
        }


@dataclass
class ToolExecutionResult:
    """Result of tool execution with standardized format."""

    success: bool
    issues: list[ToolIssue] = field(default_factory=list)
    error_message: str | None = None
    raw_output: str = ""
    raw_stderr: str = ""
    execution_time_ms: float = 0.0
    exit_code: int = 0
    tool_version: str | None = None
    files_processed: list[Path] = field(default_factory=list)
    files_modified: list[Path] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if result contains error-level issues."""
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return len([i for i in self.issues if i.severity == "error"])

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return len([i for i in self.issues if i.severity == "warning"])

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "issues": [issue.to_dict() for issue in self.issues],
            "error_message": self.error_message,
            "raw_output": self.raw_output[:500],  # Truncate for logs
            "execution_time_ms": self.execution_time_ms,
            "exit_code": self.exit_code,
            "tool_version": self.tool_version,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "files_processed": [str(f) for f in self.files_processed],
            "files_modified": [str(f) for f in self.files_modified],
        }


class ToolAdapterSettings(QABaseSettings):
    """Settings for tool-based adapters.

    Extends QABaseSettings with tool-specific configuration.
    """

    tool_name: str = ""
    tool_args: list[str] = field(default_factory=list)
    use_json_output: bool = False
    fix_enabled: bool = False
    include_warnings: bool = True


from acb.adapters import AdapterMetadata


class BaseToolAdapter(QAAdapterBase):
    """Base adapter for external CLI tools in QA framework.

    Provides shared implementation for tools like Ruff, Zuban, Bandit, etc.
    Subclasses implement tool-specific command building and output parsing.

    Example:
        ```python
        import uuid
        from contextlib import suppress
        from acb.depends import depends

        MODULE_ID = uuid.uuid7()
        MODULE_STATUS = "stable"


        class RuffAdapter(BaseToolAdapter):
            settings: RuffSettings | None = None

            @property
            def module_id(self) -> uuid.UUID:
                return MODULE_ID

            @property
            def tool_name(self) -> str:
                return "ruff"

            def build_command(self, files: list[Path]) -> list[str]:
                cmd = [self.tool_name, "check"]
                if self.settings and self.settings.fix_enabled:
                    cmd.append("--fix")
                cmd.extend([str(f) for f in files])
                return cmd

            async def parse_output(
                self, result: ToolExecutionResult
            ) -> list[ToolIssue]:
                # Parse ruff JSON output
                if not result.raw_output:
                    return []
                data = json.loads(result.raw_output)
                return [self._parse_ruff_issue(issue) for issue in data]


        with suppress(Exception):
            depends.set(RuffAdapter)
        ```
    """

    settings: ToolAdapterSettings | None = None
    metadata: AdapterMetadata | None = None

    def __init__(self, settings: ToolAdapterSettings | None = None) -> None:
        """Initialize tool adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__()
        if settings:
            self.settings = settings
        self._tool_version: str | None = None
        self._tool_available: bool | None = None

    async def init(self) -> None:
        """Initialize adapter with tool validation."""
        if not self.settings:
            self.settings = ToolAdapterSettings(tool_name=self.tool_name)

        # Validate tool is available
        available = await self.validate_tool_available()
        if not available:
            raise RuntimeError(
                f"Tool '{self.tool_name}' not found in PATH. "
                f"Please install it before using this adapter."
            )

        # Cache tool version
        self._tool_version = await self.get_tool_version()

        await super().init()

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Get the CLI tool name (e.g., 'ruff', 'bandit', 'zuban').

        Must be implemented by subclasses.
        """
        ...

    @abstractmethod
    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        """Build the command to execute for this tool.

        Args:
            files: Files to check
            config: Optional configuration override

        Returns:
            Command as list of strings (for subprocess)

        Must be implemented by subclasses.
        """
        ...

    @abstractmethod
    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        """Parse tool output into standardized issues.

        Args:
            result: Raw execution result from tool

        Returns:
            List of parsed issues

        Must be implemented by subclasses.
        """
        ...

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        """Execute tool check on files.

        Args:
            files: List of files to check (None = check all matching patterns)
            config: Optional configuration override

        Returns:
            QAResult with check execution results
        """
        if not self._initialized:
            await self.init()

        start_time = asyncio.get_event_loop().time()

        # Determine files to check
        target_files = await self._get_target_files(files, config)

        if not target_files:
            return self._create_result(
                status=QAResultStatus.SKIPPED,
                message="No files to check",
                start_time=start_time,
            )

        # Build and execute command
        command = self.build_command(target_files, config)

        try:
            exec_result = await self._execute_tool(command, target_files, start_time)
        except TimeoutError:
            # At this point, settings should be initialized by the init() method
            assert self.settings is not None, "Settings should be initialized"
            return self._create_result(
                status=QAResultStatus.ERROR,
                message=f"Tool execution timed out after {self.settings.timeout_seconds}s",
                start_time=start_time,
            )
        except Exception as e:
            return self._create_result(
                status=QAResultStatus.ERROR,
                message=f"Tool execution failed: {e}",
                start_time=start_time,
            )

        # Parse output into issues
        issues = await self.parse_output(exec_result)

        # Convert to QAResult
        return self._convert_to_qa_result(
            exec_result=exec_result,
            issues=issues,
            target_files=target_files,
            start_time=start_time,
        )

    async def _get_target_files(
        self, files: list[Path] | None, config: QACheckConfig | None
    ) -> list[Path]:
        """Collect target files based on provided list or config patterns.

        If explicit files are provided, return them. Otherwise, scan the project
        root for files matching include patterns and not matching exclude patterns.
        """
        if files:
            return files

        # Fallback to default configuration if none provided
        cfg = config or self.get_default_config()

        root = Path.cwd() / "crackerjack"
        if not root.exists():
            root = Path.cwd()

        candidates = [p for p in root.rglob("*.py")]
        result: list[Path] = []
        for path in candidates:
            # Include if matches include patterns
            include = any(path.match(pattern) for pattern in cfg.file_patterns)
            if not include:
                continue
            # Exclude if matches any exclude pattern
            if any(path.match(pattern) for pattern in cfg.exclude_patterns):
                continue
            result.append(path)

        return result

    async def _execute_tool(
        self,
        command: list[str],
        target_files: list[Path],
        start_time: float,
    ) -> ToolExecutionResult:
        """Execute tool command asynchronously.

        Args:
            command: Command to execute
            target_files: Files being processed
            start_time: Start time for duration calculation

        Returns:
            ToolExecutionResult with execution details

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout
            Exception: For other execution failures
        """
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd(),
            )

            # At this point, settings should be initialized by the init() method
            assert self.settings is not None, "Settings should be initialized"
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.timeout_seconds,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            # Non-zero exit code doesn't always mean failure
            # Some tools return 1 when they find issues
            success = process.returncode == 0 or (
                process.returncode == 1 and bool(stdout)
            )

            return ToolExecutionResult(
                success=success,
                raw_output=stdout,
                raw_stderr=stderr,
                exit_code=process.returncode or 0,
                execution_time_ms=elapsed_ms,
                tool_version=self._tool_version,
                files_processed=target_files,
            )

        except TimeoutError:
            # Kill the process if it times out
            if process:
                from contextlib import suppress

                with suppress(Exception):
                    process.kill()
                    await process.wait()
            raise

    async def validate_tool_available(self) -> bool:
        """Check if tool is available in PATH.

        Returns:
            True if tool is available, False otherwise
        """
        if self._tool_available is not None:
            return self._tool_available

        tool_path = shutil.which(self.tool_name)
        self._tool_available = tool_path is not None
        return self._tool_available

    async def get_tool_version(self) -> str | None:
        """Get tool version asynchronously.

        Returns:
            Version string or None if unavailable
        """
        if self._tool_version is not None:
            return self._tool_version

        try:
            process = await asyncio.create_subprocess_exec(
                self.tool_name,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=10,
            )

            version_output = stdout_bytes.decode("utf-8", errors="replace")
            # Return first line of version output
            return version_output.strip().split("\n")[0]

        except (TimeoutError, FileNotFoundError, Exception):
            return None

    async def health_check(self) -> dict[str, t.Any]:
        """Check adapter and tool health.

        Returns:
            Dictionary with health status and metadata
        """
        base_health = await super().health_check()

        tool_available = await self.validate_tool_available()
        tool_version = await self.get_tool_version() if tool_available else None

        return base_health | {
            "tool_name": self.tool_name,
            "tool_available": tool_available,
            "tool_version": tool_version,
            "metadata": self.metadata.dict() if self.metadata else None,
        }

    def _convert_to_qa_result(
        self,
        exec_result: ToolExecutionResult,
        issues: list[ToolIssue],
        target_files: list[Path],
        start_time: float,
    ) -> QAResult:
        """Convert tool execution result to QAResult.

        Args:
            exec_result: Raw execution result
            issues: Parsed issues
            target_files: Files that were checked
            start_time: Start time for duration

        Returns:
            QAResult
        """
        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        # Determine status based on issues and exit code
        if exec_result.error_message:
            status = QAResultStatus.ERROR
            message = exec_result.error_message
        elif not exec_result.success and exec_result.exit_code != 1:
            # Exit code 1 with output is typically "issues found"
            status = QAResultStatus.ERROR
            message = f"Tool exited with code {exec_result.exit_code}"
        elif not issues:
            status = QAResultStatus.SUCCESS
            message = "No issues found"
        else:
            error_count = sum(1 for i in issues if i.severity == "error")
            warning_count = sum(1 for i in issues if i.severity == "warning")

            if error_count > 0:
                status = QAResultStatus.FAILURE
                message = f"Found {error_count} errors"
                if warning_count > 0:
                    message += f" and {warning_count} warnings"
            else:
                status = QAResultStatus.WARNING
                message = f"Found {warning_count} warnings"

        # Build details from issues
        details_lines = []
        for issue in issues[:10]:  # Limit to first 10 for readability
            loc = str(issue.file_path)
            if issue.line_number:
                loc += f":{issue.line_number}"
            if issue.column_number:
                loc += f":{issue.column_number}"
            details_lines.append(f"{loc}: {issue.message}")

        if len(issues) > 10:
            details_lines.append(f"... and {len(issues) - 10} more issues")

        return QAResult(
            check_id=self.module_id,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            status=status,
            message=message,
            details="\n".join(details_lines),
            files_checked=target_files,
            files_modified=exec_result.files_modified,
            issues_found=len(issues),
            issues_fixed=len(exec_result.files_modified),
            execution_time_ms=elapsed_ms,
            metadata={
                "tool_version": exec_result.tool_version,
                "exit_code": exec_result.exit_code,
                "error_count": exec_result.error_count,
                "warning_count": exec_result.warning_count,
            },
        )

    def _create_result(
        self,
        status: QAResultStatus,
        message: str,
        start_time: float,
        files: list[Path] | None = None,
    ) -> QAResult:
        """Create a QAResult with standard fields.

        Args:
            status: Result status
            message: Result message
            start_time: Start time for duration
            files: Optional files list

        Returns:
            QAResult
        """
        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        return QAResult(
            check_id=self.module_id,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            status=status,
            message=message,
            files_checked=files or [],
            execution_time_ms=elapsed_ms,
            metadata={"tool_version": self._tool_version},
        )

    def _get_check_type(self) -> QACheckType:
        """Determine QACheckType based on tool name.

        Subclasses can override for more specific typing.

        Returns:
            QACheckType
        """
        # Default mapping based on tool name patterns
        tool_lower = self.tool_name.lower()

        if "format" in tool_lower or "fmt" in tool_lower:
            return QACheckType.FORMAT
        if any(x in tool_lower for x in ("type", "pyright", "mypy", "zuban")):
            return QACheckType.TYPE
        if any(x in tool_lower for x in ("bandit", "safety", "gitleaks", "semgrep")):
            return QACheckType.SECURITY
        if any(x in tool_lower for x in ("test", "pytest", "unittest")):
            return QACheckType.TEST
        if any(x in tool_lower for x in ("refactor", "refurb", "complex")):
            return QACheckType.REFACTOR
        return QACheckType.LINT

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for tool adapter.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=self.module_id,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            enabled=True,
            file_patterns=["**/*.py"],
            timeout_seconds=60,
            parallel_safe=True,
            stage="fast",
            settings={
                "tool_name": self.tool_name,
                "fix_enabled": False,
            },
        )
