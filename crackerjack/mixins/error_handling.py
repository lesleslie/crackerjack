import subprocess
import typing as t
from pathlib import Path

from rich.console import Console


class ErrorHandlingMixin:
    def __init__(self) -> None:
        self.console: Console
        self.logger: t.Any

    def handle_subprocess_error(
        self,
        error: Exception,
        command: list[str],
        operation_name: str,
        critical: bool = False,
    ) -> bool:
        error_msg = f"{operation_name} failed: {error}"

        if hasattr(self, "logger") and self.logger:
            self.logger.error(
                error_msg,
                command=" ".join(command),
                error_type=type(error).__name__,
                critical=critical,
            )

        if critical:
            self.console.print(f"[red]🚨 CRITICAL: {error_msg}[/red]")
        else:
            self.console.print(f"[red]❌ {error_msg}[/red]")

        return False

    def handle_file_operation_error(
        self,
        error: Exception,
        file_path: Path,
        operation: str,
        critical: bool = False,
    ) -> bool:
        error_msg = f"Failed to {operation} {file_path}: {error}"

        if hasattr(self, "logger") and self.logger:
            self.logger.error(
                error_msg,
                file_path=str(file_path),
                operation=operation,
                error_type=type(error).__name__,
                critical=critical,
            )

        if critical:
            self.console.print(f"[red]🚨 CRITICAL: {error_msg}[/red]")
        else:
            self.console.print(f"[red]❌ {error_msg}[/red]")

        return False

    def handle_timeout_error(
        self,
        operation_name: str,
        timeout_seconds: float,
        command: list[str] | None = None,
    ) -> bool:
        error_msg = f"{operation_name} timed out after {timeout_seconds}s"

        if hasattr(self, "logger") and self.logger:
            self.logger.warning(
                error_msg,
                timeout=timeout_seconds,
                command=" ".join(command) if command else None,
            )

        self.console.print(f"[yellow]⏰ {error_msg}[/yellow]")

        return False

    def log_operation_success(
        self,
        operation_name: str,
        details: dict[str, t.Any] | None = None,
    ) -> None:
        if hasattr(self, "logger") and self.logger:
            self.logger.info(
                f"{operation_name} completed successfully", **(details or {})
            )

    def validate_required_tools(
        self,
        tools: dict[str, str],
        operation_name: str,
    ) -> bool:
        missing_tools = []

        for tool_name, command in tools.items():
            try:
                subprocess.run(
                    [command, "--version"],
                    capture_output=True,
                    check=True,
                    timeout=5,
                )
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                FileNotFoundError,
            ):
                missing_tools.append(tool_name)

        if missing_tools:
            error_msg = f"Missing required tools for {operation_name}: {', '.join(missing_tools)}"

            if hasattr(self, "logger") and self.logger:
                self.logger.error(
                    error_msg,
                    missing_tools=missing_tools,
                    operation=operation_name,
                )

            self.console.print(f"[red]❌ {error_msg}[/red]")
            return False

        return True

    def safe_get_attribute(
        self,
        obj: t.Any,
        attribute: str,
        default: t.Any = None,
        operation_name: str = "attribute access",
    ) -> t.Any:
        try:
            return getattr(obj, attribute, default)
        except Exception as e:
            if hasattr(self, "logger") and self.logger:
                self.logger.warning(
                    f"Error accessing {attribute} during {operation_name}: {e}",
                    attribute=attribute,
                    operation=operation_name,
                    error_type=type(e).__name__,
                )
            return default
