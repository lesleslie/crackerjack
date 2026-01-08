from pathlib import Path

from rich.console import Console
from rich.panel import Panel


class ToolExecutionError(Exception):
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
        self.tool = tool
        self.exit_code = exit_code
        self.stdout = stdout.strip()
        self.stderr = stderr.strip()
        self.command = command
        self.cwd = cwd
        self.duration = duration

        message = f"Tool '{tool}' failed with exit code {exit_code}"
        if duration is not None:
            message += f" after {duration:.1f}s"

        super().__init__(message)

    def format_rich(self, console: Console | None = None) -> Panel:
        content_parts = []

        content_parts.extend(
            (
                f"[bold red]Tool:[/bold red] {self.tool}",
                f"[bold red]Exit Code:[/bold red] {self.exit_code}",
            )
        )

        if self.duration is not None:
            content_parts.append(
                f"[bold yellow]Duration:[/bold yellow] {self.duration:.2f}s"
            )

        if self.cwd:
            content_parts.append(f"[bold cyan]Directory:[/bold cyan] {self.cwd}")

        if self.command:
            cmd_str = " ".join(self.command)

            if len(cmd_str) > 100:
                cmd_str = cmd_str[:97] + "..."
            content_parts.append(f"[bold cyan]Command:[/bold cyan] {cmd_str}")

        if self.stderr:
            content_parts.append("\n[bold yellow]Error Output:[/bold yellow]")

            stderr_lines = self.stderr.split("\n")
            if len(stderr_lines) > 20:
                content_parts.append("[dim]...(truncated)[/dim]")
                stderr_lines = stderr_lines[-20:]
            content_parts.append(self._format_output(stderr_lines))

        elif self.stdout:
            content_parts.append("\n[bold yellow]Output:[/bold yellow]")
            stdout_lines = self.stdout.split("\n")
            if len(stdout_lines) > 20:
                content_parts.append("[dim]...(truncated)[/dim]")
                stdout_lines = stdout_lines[-20:]
            content_parts.append(self._format_output(stdout_lines))

        else:
            content_parts.append("\n[dim]No error output available[/dim]")

        content = "\n".join(content_parts)

        return Panel(
            content,
            title=f"❌ Tool Execution Failed: {self.tool}",
            border_style="red",
            expand=False,
        )

    def _format_output(self, lines: list[str]) -> str:
        import re

        ansi_escape = re.compile(r"\x1b\[[0-9;]*m")

        formatted_lines = []
        for line in lines:
            clean_line = ansi_escape.sub("", line)

            if clean_line.strip():
                formatted_lines.append(f" {clean_line}")

        return "\n".join(formatted_lines) if formatted_lines else "[dim] (empty)[/dim]"

    def _get_error_suggestion(self, combined_output: str) -> str | None:
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
        messages = [f"Tool '{self.tool}' failed with exit code {self.exit_code}"]

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
        return (
            f"ToolExecutionError(tool={self.tool!r}, "
            f"exit_code={self.exit_code}, "
            f"duration={self.duration})"
        )
