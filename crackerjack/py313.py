import subprocess
import typing
from enum import Enum, auto
from pathlib import Path
from typing import Any, Self, TypedDict


class CommandRunner[TReturn]:
    def run_command(self, cmd: list[str], **kwargs: Any) -> TReturn: ...


class CommandResult(TypedDict):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    command: list[str]
    duration_ms: float


def process_command_output(result: CommandResult) -> tuple[bool, str]:
    match result:
        case {"success": True, "stdout": stdout} if stdout.strip():
            return (True, stdout)
        case {"success": True}:
            return (True, "Command completed successfully with no output")
        case {"success": False, "exit_code": code, "stderr": stderr} if code == 127:
            return (False, f"Command not found: {stderr}")
        case {"success": False, "exit_code": code} if code > 0:
            return (False, f"Command failed with exit code {code}: {result['stderr']}")
        case _:
            pass
    return (False, "Unknown command result pattern")


class HookStatus(Enum):
    SUCCESS = auto()
    FAILURE = auto()
    SKIPPED = auto()
    ERROR = auto()


class HookResult(TypedDict):
    status: HookStatus
    hook_id: str
    output: str
    files: list[str]


def analyze_hook_result(result: HookResult) -> str:
    match result:
        case {"status": HookStatus.SUCCESS, "hook_id": hook_id}:
            return f"✅ Hook {hook_id} passed successfully"
        case {"status": HookStatus.FAILURE, "hook_id": hook_id, "output": output} if (
            "fixable" in output
        ):
            return f"🔧 Hook {hook_id} failed with fixable issues"
        case {"status": HookStatus.FAILURE, "hook_id": hook_id}:
            return f"❌ Hook {hook_id} failed"
        case {"status": HookStatus.SKIPPED, "hook_id": hook_id}:
            return f"⏩ Hook {hook_id} was skipped"
        case {"status": HookStatus.ERROR, "hook_id": hook_id, "output": output}:
            return f"💥 Hook {hook_id} encountered an error: {output}"
        case _:
            pass
    return "Unknown hook result pattern"


class ModernConfigManager:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config: dict[str, Any] = {}

    def load(self) -> Self:
        return self

    def update(self, key: str, value: Any) -> Self:
        self.config[key] = value
        return self

    def save(self) -> Self:
        return self


def categorize_file(file_path: Path) -> str:
    path_str = str(file_path)
    name = file_path
    match path_str:
        case s if name.suffix == ".py" and "/tests/" in s:
            return "Python Test File"
        case s if name.suffix == ".py" and "__init__.py" in name.name:
            return "Python Module Init"
        case s if name.suffix == ".py":
            return "Python Source File"
        case s if name.suffix in {".md", ".rst", ".txt"}:
            return "Documentation File"
        case s if name.stem.startswith(".") or name.name in {
            ".gitignore",
            ".pre-commit-config.yaml",
        }:
            return "Configuration File"
        case _:
            pass
    return "Unknown File Type"


def process_hook_results[T, R](
    results: list[T],
    success_handler: typing.Callable[[T], R],
    failure_handler: typing.Callable[[T], R],
) -> list[R]:
    processed_results = []
    for result in results:
        if isinstance(result, dict) and result.get("status") == HookStatus.SUCCESS:
            processed_results.append(success_handler(result))
        else:
            processed_results.append(failure_handler(result))
    return processed_results


class EnhancedCommandRunner:
    def __init__(self, working_dir: Path | None = None) -> None:
        self.working_dir = working_dir

    def run(self, cmd: list[str], **kwargs: Any) -> CommandResult:
        import time

        start_time = time.time()
        try:
            process = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.working_dir, **kwargs
            )
            duration_ms = (time.time() - start_time) * 1000
            return CommandResult(
                success=process.returncode == 0,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                command=cmd,
                duration_ms=duration_ms,
            )
        except subprocess.SubprocessError as e:
            duration_ms = (time.time() - start_time) * 1000
            return CommandResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                command=cmd,
                duration_ms=duration_ms,
            )

    def handle_result(self, result: CommandResult) -> tuple[bool, str]:
        return process_command_output(result)


def clean_python_code(code: str) -> str:
    lines = code.splitlines()
    cleaned_lines = []
    for line in lines:
        match line.strip():
            case "":
                if not cleaned_lines or cleaned_lines[-1].strip():
                    cleaned_lines.append("")
            case s if s.startswith(("import ", "from ")):
                cleaned_lines.append(line)
            case s if s.startswith("#"):
                continue
            case s if "#" in s and (
                not any(
                    skip in s for skip in ("# noqa", "# type:", "# pragma", "# skip")
                )
            ):
                code_part = line.split("#", 1)[0].rstrip()
                if code_part:
                    cleaned_lines.append(code_part)
            case s if s.startswith('"""') or s.startswith("'''"):
                continue
            case _:
                cleaned_lines.append(line)
    return "\n".join(cleaned_lines)
