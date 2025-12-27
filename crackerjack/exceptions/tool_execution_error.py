"""Enhanced tool execution error with rich formatting.

Provides context-rich error reporting for failed tool executions.
Part of Phase 10.2.3: Development Velocity Improvements.
"""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel


class ToolExecutionError(Exception):
    """Enhanced error with context for tool execution failures.

    Provides detailed information about what went wrong during tool execution,
    including exit code, stdout, stderr, and rich formatting for better UX.
    """

    def __init__(
        self,
        tool: str,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
        command: list[str] | None = None,
        cwd: Path | None = None,
        duration: float | None = None,
    ):
        """Initialize tool execution error.

        Args:
            tool: Tool name that failed
            exit_code: Process exit code
            stdout: Standard output from tool
            stderr: Standard error from tool
            command: Full command that was executed (optional)
            cwd: Working directory where command was run (optional)
            duration: Execution duration in seconds (optional)
        """
        self.tool = tool
        self.exit_code = exit_code
        self.stdout = stdout.strip()
        self.stderr = stderr.strip()
        self.command = command
        self.cwd = cwd
        self.duration = duration

        # Create base exception message
        message = f"Tool '{tool}' failed with exit code {exit_code}"
        if duration is not None:
            message += f" after {duration:.1f}s"

        super().__init__(message)

    def format_rich(self, console: Console | None = None) -> Panel:
        """Format error for rich console display with syntax highlighting.

        Args:
            console: Optional console for width detection

        Returns:
            Formatted rich Panel with error details
        """
        # Build error content with sections
        content_parts = []

        # Tool and exit code
        content_parts.extend(
            (
                f"[bold red]Tool:[/bold red] {self.tool}",
                f"[bold red]Exit Code:[/bold red] {self.exit_code}",
            )
        )

        # Duration if available
        if self.duration is not None:
            content_parts.append(
                f"[bold yellow]Duration:[/bold yellow] {self.duration:.2f}s"
            )

        # Working directory if available
        if self.cwd:
            content_parts.append(f"[bold cyan]Directory:[/bold cyan] {self.cwd}")

        # Command if available
        if self.command:
            cmd_str = " ".join(self.command)
            # Truncate very long commands
            if len(cmd_str) > 100:
                cmd_str = cmd_str[:97] + "..."
            content_parts.append(f"[bold cyan]Command:[/bold cyan] {cmd_str}")

        # Standard error (most important)
        if self.stderr:
            content_parts.append("\n[bold yellow]Error Output:[/bold yellow]")
            # Limit error output to last 20 lines for readability
            stderr_lines = self.stderr.split("\n")
            if len(stderr_lines) > 20:
                content_parts.append("[dim]...(truncated)[/dim]")
                stderr_lines = stderr_lines[-20:]
            content_parts.append(self._format_output(stderr_lines))

        # Standard output (if present and stderr is empty)
        elif self.stdout:
            content_parts.append("\n[bold yellow]Output:[/bold yellow]")
            stdout_lines = self.stdout.split("\n")
            if len(stdout_lines) > 20:
                content_parts.append("[dim]...(truncated)[/dim]")
                stdout_lines = stdout_lines[-20:]
            content_parts.append(self._format_output(stdout_lines))

        # No output available
        else:
            content_parts.append("\n[dim]No error output available[/dim]")

        # Combine all parts
        content = "\n".join(content_parts)

        return Panel(
            content,
            title=f"❌ Tool Execution Failed: {self.tool}",
            border_style="red",
            expand=False,
        )

    def _format_output(self, lines: list[str]) -> str:
        """Format output lines with proper indentation and markup.

        Args:
            lines: Output lines to format

        Returns:
            Formatted output string
        """
        # Remove ANSI color codes for cleaner display
        import re

        # Standard ANSI escape sequence pattern (not security-critical, safe to use directly)
        ansi_escape = re.compile(r"\x1b\[[0-9;]*m")

        formatted_lines = []
        for line in lines:
            # Strip ANSI codes
            clean_line = ansi_escape.sub("", line)
            # Indent for readability
            if clean_line.strip():
                formatted_lines.append(f"  {clean_line}")

        return "\n".join(formatted_lines) if formatted_lines else "[dim]  (empty)[/dim]"

    def _get_error_suggestion(self, combined_output: str) -> str | None:
        """Get specific suggestion based on error patterns in output.

        Args:
            combined_output: Combined stderr and stdout in lowercase

        Returns:
            Suggestion string, or None if no pattern matched
        """
        error_patterns = {
            "permission denied": "→ Check file permissions or run with appropriate access",
            (
                "command not found",
                "no such file",
            ): f"→ Ensure '{self.tool}' is installed and in PATH",
            (
                "timeout",
                "timed out",
            ): "→ Tool execution timed out - consider increasing timeout",
            (
                "syntaxerror",
                "syntax error",
            ): "→ Check code syntax in files being analyzed",
            (
                "importerror",
                "modulenotfounderror",
            ): "→ Check Python dependencies are installed (try: uv sync)",
            ("typeerror", "type error"): "→ Fix type annotation errors in your code",
            "out of memory": "→ Reduce batch size or increase available memory",
        }

        for patterns, suggestion in error_patterns.items():
            patterns_list = patterns if isinstance(patterns, tuple) else (patterns,)
            if any(pattern in combined_output for pattern in patterns_list):
                return suggestion

        return None

    def get_actionable_message(self) -> str:
        """Get actionable error message for developers.

        Returns:
            Human-readable error message with suggestions
        """
        messages = [f"Tool '{self.tool}' failed with exit code {self.exit_code}"]

        # Add common error patterns and suggestions
        combined_output = f"{self.stderr} {self.stdout}".lower()
        suggestion = self._get_error_suggestion(combined_output)

        if suggestion:
            messages.append(suggestion)
        elif self.stderr:
            messages.append("→ Check error output above for details")
        else:
            messages.append(f"→ Run '{self.tool}' manually for more details")

        return "\n".join(messages)

    def __str__(self) -> str:
        """String representation for logging and debugging.

        Returns:
            Detailed string representation
        """
        parts = [
            f"ToolExecutionError: {self.tool}",
            f"Exit Code: {self.exit_code}",
        ]

        if self.duration is not None:
            parts.append(f"Duration: {self.duration:.2f}s")

        if self.command:
            parts.append(f"Command: {' '.join(self.command)}")

        if self.stderr:
            parts.append(f"Stderr: {self.stderr[:200]}...")
        elif self.stdout:
            parts.append(f"Stdout: {self.stdout[:200]}...")

        return " | ".join(parts)

    def __repr__(self) -> str:
        """Developer representation.

        Returns:
            Repr string
        """
        return (
            f"ToolExecutionError(tool={self.tool!r}, "
            f"exit_code={self.exit_code}, "
            f"duration={self.duration})"
        )
