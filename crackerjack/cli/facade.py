"""CLI Facade for backward compatibility.

This module provides a bridge between the existing CLI interface and the new
workflow orchestrator, ensuring all existing functionality continues to work.
"""

import asyncio
from pathlib import Path

from rich.console import Console

from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.models.protocols import OptionsProtocol


class CrackerjackCLIFacade:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
    ) -> None:
        self.console = console or Console(force_terminal=True)
        self.pkg_path = pkg_path or Path.cwd()
        self.orchestrator = WorkflowOrchestrator(
            console=self.console,
            pkg_path=self.pkg_path,
        )

    def process(self, options: OptionsProtocol) -> None:
        try:
            if self._should_handle_special_mode(options):
                self._handle_special_modes(options)
                return
            success = asyncio.run(self.orchestrator.run_complete_workflow(options))
            if not success:
                self.console.print("[red]❌ Workflow completed with errors[/red]")
            else:
                self.console.print("[green]🎉 Workflow completed successfully![/green]")
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⏹️ Operation cancelled by user[/yellow]")
            raise SystemExit(130)
        except Exception as e:
            self.console.print(f"[red]💥 Unexpected error: {e}[/red]")
            if options.verbose:
                import traceback

                self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
            raise SystemExit(1)

    async def process_async(self, options: OptionsProtocol) -> None:
        await asyncio.to_thread(self.process, options)

    def _should_handle_special_mode(self, options: OptionsProtocol) -> bool:
        return (
            getattr(options, "start_mcp_server", False)
            or getattr(options, "enterprise_batch", False)
            or getattr(options, "monitor_dashboard", False)
        )

    def _handle_special_modes(self, options: OptionsProtocol) -> None:
        if getattr(options, "start_mcp_server", False):
            self._start_mcp_server()
        elif getattr(options, "enterprise_batch", False):
            self._handle_enterprise_batch(options)
        elif getattr(options, "monitor_dashboard", False):
            self._handle_monitor_dashboard(options)

    def _start_mcp_server(self) -> None:
        try:
            from crackerjack.mcp.server import main as start_mcp_main

            self.console.print(
                "[bold cyan]🤖 Starting Crackerjack MCP Server...[/bold cyan]",
            )
            start_mcp_main(str(self.pkg_path))
        except ImportError:
            self.console.print(
                "[red]❌ MCP server requires additional dependencies[/red]",
            )
            self.console.print("[yellow]Install with: uv sync --group mcp[/yellow]")
            raise SystemExit(1)
        except Exception as e:
            self.console.print(f"[red]❌ Failed to start MCP server: {e}[/red]")
            raise SystemExit(1)

    def _handle_enterprise_batch(self, options: OptionsProtocol) -> None:
        self.console.print(
            "[red]❌ Enterprise batch processing is not yet implemented[/red]"
        )
        raise SystemExit(1)

    def _handle_monitor_dashboard(self, options: OptionsProtocol) -> None:
        self.console.print("[red]❌ Monitoring dashboard is not yet implemented[/red]")
        raise SystemExit(1)


def create_crackerjack_runner(
    console: Console | None = None,
    pkg_path: Path | None = None,
) -> CrackerjackCLIFacade:
    return CrackerjackCLIFacade(console=console, pkg_path=pkg_path)


CrackerjackRunner = CrackerjackCLIFacade
