"""Common error handling patterns for crackerjack components."""

import subprocess
import typing as t
from pathlib import Path

from rich.console import Console


class ErrorHandlingMixin:
    """Mixin providing common error handling patterns for crackerjack components."""

    def __init__(self) -> None:
        # These attributes should be provided by the class using the mixin
        self.console: Console
        self.logger: t.Any  # Logger instance

    def handle_subprocess_error(
        self,
        error: Exception,
        command: list[str],
        operation_name: str,
        critical: bool = False,
    ) -> bool:
        """Handle subprocess errors with consistent logging and user feedback.

        Args:
            error: The exception that occurred
            command: The command that failed
            operation_name: Human-readable name of the operation
            critical: Whether this is a critical error that should stop execution

        Returns:
            False to indicate failure
        """
        error_msg = f"{operation_name} failed: {error}"

        # Log the error
        if hasattr(self, "logger") and self.logger:
            self.logger.error(
                error_msg,
                command=" ".join(command),
                error_type=type(error).__name__,
                critical=critical,
            )

        # Display user-friendly error message
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
        """Handle file operation errors with consistent logging and user feedback.

        Args:
            error: The exception that occurred
            file_path: The file that caused the error
            operation: The operation that failed (e.g., "read", "write", "delete")
            critical: Whether this is a critical error that should stop execution

        Returns:
            False to indicate failure
        """
        error_msg = f"Failed to {operation} {file_path}: {error}"

        # Log the error
        if hasattr(self, "logger") and self.logger:
            self.logger.error(
                error_msg,
                file_path=str(file_path),
                operation=operation,
                error_type=type(error).__name__,
                critical=critical,
            )

        # Display user-friendly error message
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
        """Handle timeout errors with consistent logging and user feedback.

        Args:
            operation_name: Human-readable name of the operation
            timeout_seconds: The timeout that was exceeded
            command: Optional command that timed out

        Returns:
            False to indicate failure
        """
        error_msg = f"{operation_name} timed out after {timeout_seconds}s"

        # Log the error
        if hasattr(self, "logger") and self.logger:
            self.logger.warning(
                error_msg,
                timeout=timeout_seconds,
                command=" ".join(command) if command else None,
            )

        # Display user-friendly error message
        self.console.print(f"[yellow]⏰ {error_msg}[/yellow]")

        return False

    def log_operation_success(
        self,
        operation_name: str,
        details: dict[str, t.Any] | None = None,
    ) -> None:
        """Log successful operations with consistent formatting.

        Args:
            operation_name: Human-readable name of the operation
            details: Optional additional details to log
        """
        if hasattr(self, "logger") and self.logger:
            self.logger.info(
                f"{operation_name} completed successfully", **(details or {})
            )

    def validate_required_tools(
        self,
        tools: dict[str, str],
        operation_name: str,
    ) -> bool:
        """Validate that required external tools are available.

        Args:
            tools: Dict mapping tool names to their expected commands
            operation_name: Name of operation requiring the tools

        Returns:
            True if all tools are available, False otherwise
        """
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
        """Safely get an attribute with error handling.

        Args:
            obj: Object to get attribute from
            attribute: Name of attribute to get
            default: Default value if attribute doesn't exist
            operation_name: Name of operation for error logging

        Returns:
            The attribute value or default
        """
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
