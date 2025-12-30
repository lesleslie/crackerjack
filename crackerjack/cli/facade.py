import asyncio
import shlex
from pathlib import Path

from rich.console import Console

from crackerjack.core.workflow_orchestrator import WorkflowPipeline
from crackerjack.models.protocols import OptionsProtocol

# Valid semantic commands for crackerjack operations
VALID_COMMANDS = {"test", "lint", "check", "format", "security", "complexity", "all"}


def validate_command(
    command: str | None, args: str | None = None
) -> tuple[str, list[str]]:
    """Validate command and detect common misuse patterns.

    Args:
        command: Semantic command name (test, lint, check, etc.)
        args: Additional arguments as a string

    Returns:
        Tuple of (validated_command, cleaned_args_list)

    Raises:
        ValueError: If command is invalid or misused

    Examples:
        >>> validate_command("test", "")
        ("test", [])
        >>> validate_command("check", "--verbose")
        ("check", ["--verbose"])
        >>> validate_command("--ai-fix", "-t")
        Traceback (most recent call last):
        ...
        ValueError: Invalid command: '--ai-fix'...
    """
    # CRITICAL: Check for None command first
    if command is None:
        raise ValueError("Command cannot be None")

    # Detect if user put flags in command parameter
    if command.startswith("--") or command.startswith("-"):
        raise ValueError(
            f"Invalid command: {command!r}\n"
            f"Commands should be semantic (e.g., 'test', 'lint', 'check')\n"
            f"Use ai_agent_mode=True parameter for auto-fix, not --ai-fix in command"
        )

    # Validate against known semantic commands
    if command not in VALID_COMMANDS:
        raise ValueError(
            f"Unknown command: {command!r}\n"
            f"Valid commands: {', '.join(sorted(VALID_COMMANDS))}"
        )

    # Parse args and detect --ai-fix misuse
    # Handle None gracefully by converting to empty string
    args_str = args if args is not None else ""
    # Use shlex.split for proper shell argument parsing (handles quotes)
    parsed_args = shlex.split(args_str) if args_str else []
    if "--ai-fix" in parsed_args:
        raise ValueError(
            "Do not pass --ai-fix in args parameter\n"
            "Use ai_agent_mode=True parameter instead"
        )

    return command, parsed_args


class CrackerjackCLIFacade:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
    ) -> None:
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()
        # CLI facade uses WorkflowPipeline directly for quality workflows
        # MCP server lifecycle handled via MCPServerCLIFactory in __main__.py

    def process(self, options: OptionsProtocol) -> None:
        try:
            if self._should_handle_special_mode(options):
                self._handle_special_modes(options)
                return
            pipeline = WorkflowPipeline(console=self.console, pkg_path=self.pkg_path)
            success = pipeline.run_complete_workflow_sync(options)
            if not success:
                raise SystemExit(1)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⏹️ Operation cancelled by user[/ yellow]")
            raise SystemExit(130)
        except Exception as e:
            self.console.print(f"[red]💥 Unexpected error: {e}[/ red]")
            if options.verbose:
                import traceback

                self.console.print(f"[dim]{traceback.format_exc()}[/ dim]")
            raise SystemExit(1)

    async def process_async(self, options: OptionsProtocol) -> None:
        await asyncio.to_thread(self.process, options)

    def _should_handle_special_mode(self, options: OptionsProtocol) -> bool:
        return (
            getattr(options, "start_mcp_server", False)
            or getattr(options, "advanced_batch", False)
            or getattr(options, "monitor_dashboard", False)
        )

    def _handle_special_modes(self, options: OptionsProtocol) -> None:
        if getattr(options, "start_mcp_server", False):
            self._start_mcp_server()
        elif getattr(options, "advanced_batch", False):
            self._handle_advanced_batch(options)

    def _start_mcp_server(self) -> None:
        try:
            from crackerjack.mcp.server import main as start_mcp_main

            self.console.print(
                "[bold cyan]🤖 Starting Crackerjack MCP Server...[/ bold cyan]",
            )
            start_mcp_main(str(self.pkg_path))
        except ImportError:
            self.console.print(
                "[red]❌ MCP server requires additional dependencies[/ red]",
            )
            self.console.print("[yellow]Install with: uv sync --group mcp[/ yellow]")
            raise SystemExit(1)
        except Exception as e:
            self.console.print(f"[red]❌ Failed to start MCP server: {e}[/ red]")
            raise SystemExit(1)

    def _handle_advanced_batch(self, options: OptionsProtocol) -> None:
        self.console.print(
            "[red]❌ Advanced batch processing is not yet implemented[/ red]"
        )
        raise SystemExit(1)


def create_crackerjack_runner(
    console: Console | None = None,
    pkg_path: Path | None = None,
) -> CrackerjackCLIFacade:
    return CrackerjackCLIFacade(console=console, pkg_path=pkg_path)


CrackerjackRunner = CrackerjackCLIFacade
