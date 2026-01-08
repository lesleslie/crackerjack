import json
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

if t.TYPE_CHECKING:
    from crackerjack.orchestration.execution_strategies import ExecutionContext


@dataclass
class Issue:
    file_path: Path
    line_number: int
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "file_path": str(self.file_path),
            "line_number": self.line_number,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class ToolResult:
    success: bool
    issues: list[Issue] = field(default_factory=list)
    error: str | None = None
    raw_output: str = ""
    execution_time: float = 0.0
    tool_version: str | None = None
    _execution_mode: str | None = None

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
            "error": self.error,
            "raw_output": self.raw_output,
            "execution_time": self.execution_time,
            "tool_version": self.tool_version,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


class RustToolAdapter(Protocol):
    def __init__(self, context: "ExecutionContext") -> None: ...

    def get_command_args(self, target_files: list[Path]) -> list[str]: ...

    def parse_output(self, output: str) -> ToolResult: ...

    def supports_json_output(self) -> bool: ...

    def get_tool_version(self) -> str | None: ...

    def validate_tool_available(self) -> bool: ...


class BaseRustToolAdapter(ABC):
    def __init__(self, context: "ExecutionContext") -> None:
        self.context = context
        self._tool_version: str | None = None

    @abstractmethod
    def get_command_args(self, target_files: list[Path]) -> list[str]:
        pass

    @abstractmethod
    def parse_output(self, output: str) -> ToolResult:
        pass

    @abstractmethod
    def supports_json_output(self) -> bool:
        pass

    @abstractmethod
    def get_tool_name(self) -> str:
        pass

    def get_tool_version(self) -> str | None:
        if self._tool_version is None:
            self._tool_version = self._fetch_tool_version()
        return self._tool_version

    def validate_tool_available(self) -> bool:
        import subprocess

        tool_name = self.get_tool_name()
        try:
            result = subprocess.run(
                ["which", tool_name], capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _fetch_tool_version(self) -> str | None:
        import subprocess

        tool_name = self.get_tool_name()
        try:
            result = subprocess.run(
                [tool_name, "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            return result.stdout.strip().split("\\n")[0]
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            return None

    def _should_use_json_output(self) -> bool:
        return self.supports_json_output() and (
            self.context.ai_agent_mode or self.context.ai_debug_mode
        )

    def _parse_json_output_safe(self, output: str) -> dict[str, t.Any] | None:
        try:
            json_result = json.loads(output)
            return t.cast(dict[str, t.Any] | None, json_result)
        except json.JSONDecodeError:
            return None

    def _create_error_result(
        self, error_message: str, raw_output: str = ""
    ) -> ToolResult:
        return ToolResult(
            success=False,
            error=error_message,
            raw_output=raw_output,
            tool_version=self.get_tool_version(),
        )
