from __future__ import annotations

import asyncio
import logging
import shutil
import typing as t
from abc import abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from crackerjack.adapters._qa_adapter_base import QAAdapterBase, QABaseSettings
from crackerjack.models.adapter_metadata import AdapterMetadata
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig


logger = logging.getLogger(__name__)


@dataclass
class ToolIssue:
    file_path: Path
    line_number: int | None = None
    column_number: int | None = None
    message: str = ""
    code: str | None = None
    severity: str = "error"
    suggestion: str | None = None

    def to_dict(self) -> dict[str, t.Any]:
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
    success: bool | None = None
    issues: list[ToolIssue] = field(default_factory=list)
    error_message: str | None = None
    raw_output: str = ""
    raw_stderr: str = ""
    error_output: str = ""
    execution_time_ms: float = 0.0
    exit_code: int = 0
    tool_version: str | None = None
    files_processed: list[Path] = field(default_factory=list)
    files_modified: list[Path] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.error_output and not self.raw_stderr:
            self.raw_stderr = self.error_output
        if self.success is None:
            self.success = self.exit_code == 0

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == "error"])

    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == "warning"])

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "success": self.success,
            "issues": [issue.to_dict() for issue in self.issues],
            "error_message": self.error_message,
            "raw_output": self.raw_output[:500],
            "execution_time_ms": self.execution_time_ms,
            "exit_code": self.exit_code,
            "tool_version": self.tool_version,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "files_processed": [str(f) for f in self.files_processed],
            "files_modified": [str(f) for f in self.files_modified],
        }


class ToolAdapterSettings(QABaseSettings):
    tool_name: str = ""
    tool_args: list[str] = field(default_factory=list)
    use_json_output: bool = False
    fix_enabled: bool = False
    include_warnings: bool = True


class BaseToolAdapter(QAAdapterBase):
    settings: ToolAdapterSettings | None = None
    metadata: AdapterMetadata | None = None

    def __init__(self, settings: ToolAdapterSettings | None = None) -> None:
        super().__init__()
        if settings:
            self.settings = settings
        self._tool_version: str | None = None
        self._tool_available: bool | None = None

    async def init(self) -> None:
        if not self.settings:
            timeout_seconds = self._get_timeout_from_settings()

            self.settings = ToolAdapterSettings(
                tool_name=self.tool_name,
                timeout_seconds=timeout_seconds,
                max_workers=4,
            )

        available = await self.validate_tool_available()
        if not available:
            raise RuntimeError(
                f"Tool '{self.tool_name}' not found in PATH. "
                f"Please install it before using this adapter."
            )

        self._tool_version = await self.get_tool_version()

        await super().init()

    def _get_timeout_from_settings(self) -> int:
        try:
            from crackerjack.config import CrackerjackSettings
            from crackerjack.config.loader import load_settings

            settings = load_settings(CrackerjackSettings)

            adapter_name = self.tool_name.lower()

            adapter_timeouts = settings.adapter_timeouts
            if adapter_timeouts and hasattr(
                adapter_timeouts, f"{adapter_name}_timeout"
            ):
                timeout = getattr(adapter_timeouts, f"{adapter_name}_timeout")
                logger.debug(
                    f"Using configured timeout for {self.tool_name}: {timeout}s",
                )
                return timeout
        except Exception as e:
            logger.debug(f"Could not load timeout from settings: {e}")

        default_timeout = 300
        logger.debug(
            f"Using default timeout for {self.tool_name}: {default_timeout}s",
        )
        return default_timeout

    @property
    @abstractmethod
    def tool_name(self) -> str: ...

    @abstractmethod
    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]: ...

    @abstractmethod
    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]: ...

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        if not self._initialized:
            await self.init()

        start_time = asyncio.get_event_loop().time()

        target_files = await self._get_target_files(files, config)

        if not target_files:
            return self._create_result(
                status=QAResultStatus.SKIPPED,
                message="No files to check",
                start_time=start_time,
            )

        command = self.build_command(target_files, config)

        try:
            exec_result = await self._execute_tool(command, target_files, start_time)
        except TimeoutError:
            assert self.settings is not None, "Settings should be initialized"
            timeout_msg = (
                f"Tool execution timed out after {self.settings.timeout_seconds}s"
            )
            return self._create_result(
                status=QAResultStatus.ERROR,
                message=timeout_msg,
                details=timeout_msg,
                start_time=start_time,
            )
        except Exception as e:
            error_msg = f"Tool execution failed: {e}"

            import traceback

            error_details = f"{error_msg}\n\nFull traceback:\n{traceback.format_exc()}"
            return self._create_result(
                status=QAResultStatus.ERROR,
                message=error_msg,
                details=error_details,
                start_time=start_time,
            )

        issues = await self.parse_output(exec_result)

        return self._convert_to_qa_result(
            exec_result=exec_result,
            issues=issues,
            target_files=target_files,
            start_time=start_time,
        )

    async def _get_target_files(
        self, files: list[Path] | None, config: QACheckConfig | None
    ) -> list[Path]:
        if files:
            return files

        cfg = config or self.get_default_config()

        root = Path.cwd() / "crackerjack"
        if not root.exists():
            root = Path.cwd()

        standard_excludes = {
            ".venv",
            "venv",
            ".env",
            "env",
            ".tox",
            ".nox",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".git",
            ".hg",
            ".svn",
            "node_modules",
            ".uv",
            "dist",
            "build",
            "*.egg-info",
        }

        if (
            cfg
            and hasattr(cfg, "is_comprehensive_stage")
            and cfg.is_comprehensive_stage
        ):
            standard_excludes.add("tests")

        candidates = [p for p in root.rglob("*.py")]
        result: list[Path] = []
        for path in candidates:
            if any(excluded in path.parts for excluded in standard_excludes):
                continue

            include = any(path.match(pattern) for pattern in cfg.file_patterns)
            if not include:
                continue

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
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd(),
            )

            assert self.settings is not None, "Settings should be initialized"
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.timeout_seconds,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

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
            if process:
                from contextlib import suppress

                with suppress(Exception):
                    process.kill()
                    await process.wait()
            raise

    async def validate_tool_available(self) -> bool:
        if self._tool_available is not None:
            return self._tool_available

        tool_path = shutil.which(self.tool_name)
        self._tool_available = tool_path is not None
        return self._tool_available

    async def get_tool_version(self) -> str | None:
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

            return version_output.strip().split("\n")[0]

        except (TimeoutError, FileNotFoundError, Exception):
            return None

    async def health_check(self) -> dict[str, t.Any]:
        base_health = await super().health_check()

        tool_available = await self.validate_tool_available()
        tool_version = await self.get_tool_version() if tool_available else None

        return base_health | {
            "tool_name": self.tool_name,
            "tool_available": tool_available,
            "tool_version": tool_version,
            "metadata": self.metadata.dict() if self.metadata else None,
        }

    def _count_issues_by_severity(self, issues: list[ToolIssue]) -> tuple[int, int]:
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        return error_count, warning_count

    def _determine_qa_status_and_message(
        self, exec_result: ToolExecutionResult, issues: list[ToolIssue]
    ) -> tuple[QAResultStatus, str]:
        if exec_result.error_message:
            return QAResultStatus.ERROR, exec_result.error_message

        if not exec_result.success and exec_result.exit_code != 1:
            return (
                QAResultStatus.ERROR,
                f"Tool exited with code {exec_result.exit_code}",
            )

        if not issues:
            return QAResultStatus.SUCCESS, "No issues found"

        error_count, warning_count = self._count_issues_by_severity(issues)

        if error_count > 0:
            message = f"Found {error_count} errors"
            if warning_count > 0:
                message += f" and {warning_count} warnings"
            return QAResultStatus.FAILURE, message

        return QAResultStatus.WARNING, f"Found {warning_count} warnings"

    def _build_details_from_issues(self, issues: list[ToolIssue]) -> str:
        details_lines = []
        for issue in issues[:10]:
            loc = str(issue.file_path)
            if issue.line_number:
                loc += f":{issue.line_number}"
            if issue.column_number:
                loc += f":{issue.column_number}"
            details_lines.append(f"{loc}: {issue.message}")

        if len(issues) > 10:
            details_lines.append(f"... and {len(issues) - 10} more issues")

        return "\n".join(details_lines)

    def _convert_to_qa_result(
        self,
        exec_result: ToolExecutionResult,
        issues: list[ToolIssue],
        target_files: list[Path],
        start_time: float,
    ) -> QAResult:
        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        status, message = self._determine_qa_status_and_message(exec_result, issues)
        details = self._build_details_from_issues(issues)

        return QAResult(
            check_id=self.module_id,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            status=status,
            message=message,
            details=details,
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
        details: str | None = None,
    ) -> QAResult:
        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        return QAResult(
            check_id=self.module_id,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            status=status,
            message=message,
            details=details or "",
            files_checked=files or [],
            execution_time_ms=elapsed_ms,
            metadata={"tool_version": self._tool_version},
        )

    def _get_check_type(self) -> QACheckType:
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
