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
            dry_run=False,
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
        try:
            from crackerjack.mcp_enterprise import run_enterprise_batch

            enterprise_batch = options.enterprise_batch
            if not enterprise_batch:
                self.console.print(
                    "[red]❌ No projects specified for batch processing[/red]"
                )
                raise SystemExit(1)

            project_paths: list[str] = [
                path.strip() for path in enterprise_batch.split(",")
            ]
            self.console.print(
                "[bold cyan]🏢 Starting Enterprise Batch Processing...[/bold cyan]",
            )
            self.console.print(f"[dim]Processing {len(project_paths)} projects[/dim]")
            stages: list[str] = ["fast", "comprehensive"]
            if hasattr(options, "test") and options.test:
                stages.insert(1, "tests")
            result = asyncio.run(
                run_enterprise_batch(
                    project_paths,
                    stages=stages,
                    fail_fast=False,
                    create_reports=True,
                ),
            )
            if result.failed_projects == 0:
                self.console.print(
                    "[bold green]🎉 All projects processed successfully![/bold green]",
                )
            else:
                self.console.print(
                    f"[bold yellow]⚠️ {result.failed_projects} projects failed[/bold yellow]",
                )
                raise SystemExit(1)
        except ImportError:
            self.console.print(
                "[red]❌ Enterprise features require additional dependencies[/red]",
            )
            raise SystemExit(1)
        except Exception as e:
            self.console.print(f"[red]❌ Enterprise batch processing failed: {e}[/red]")
            raise SystemExit(1)

    def _handle_monitor_dashboard(self, options: OptionsProtocol) -> None:
        try:
            from crackerjack.mcp_monitor import start_monitoring_dashboard

            monitor_dashboard = options.monitor_dashboard
            if not monitor_dashboard:
                self.console.print("[red]❌ No projects specified for monitoring[/red]")
                raise SystemExit(1)

            project_paths: list[str] = [
                path.strip() for path in monitor_dashboard.split(",")
            ]
            self.console.print(
                "[bold cyan]🖥️ Starting Real-Time Monitoring Dashboard...[/bold cyan]",
            )
            self.console.print(f"[dim]Monitoring {len(project_paths)} projects[/dim]")
            asyncio.run(start_monitoring_dashboard(project_paths))
        except ImportError:
            self.console.print(
                "[red]❌ Monitoring features require additional dependencies[/red]",
            )
            raise SystemExit(1)
        except Exception as e:
            self.console.print(f"[red]❌ Monitoring dashboard failed: {e}[/red]")
            raise SystemExit(1)


def create_crackerjack_runner(
    console: Console | None = None,
    pkg_path: Path | None = None,
) -> CrackerjackCLIFacade:
    return CrackerjackCLIFacade(console=console, pkg_path=pkg_path)


CrackerjackRunner = CrackerjackCLIFacade
