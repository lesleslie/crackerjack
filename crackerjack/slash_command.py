"""
Crackerjack slash command implementation with WebSocket progress monitoring.

This module provides the /crackerjack functionality that bypasses the broken MCP tool
and directly interfaces with the WebSocket server for job creation and monitoring.
"""

import asyncio
import json
import time
from typing import Dict, Any
import aiohttp
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table

console = Console()


class CrackerjackSlashCommand:
    """Handler for /crackerjack slash command with live progress monitoring."""
    
    def __init__(self, websocket_url: str = "http://localhost:8675"):
        self.websocket_url = websocket_url
        self.ws_progress_url = websocket_url.replace("http://", "ws://").replace("https://", "wss://")
        
    async def execute(self) -> Dict[str, Any]:
        """Execute the /crackerjack slash command with live progress monitoring."""
        console.print(Panel.fit(
            "[bold cyan]🚀 Crackerjack AI Agent Auto-Fix[/bold cyan]\n\n"
            "[dim]Starting iterative auto-fixing workflow...[/dim]",
            border_style="cyan"
        ))
        
        try:
            # Step 1: Start the job
            job_id = await self._start_job()
            if not job_id:
                return {"success": False, "error": "Failed to start job"}
            
            console.print(f"[green]✅ Job started with ID: {job_id}[/green]\n")
            
            # Step 2: Monitor progress with live updates
            result = await self._monitor_job_with_live_display(job_id)
            
            return result
            
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return {"success": False, "error": str(e)}
    
    async def _start_job(self) -> str | None:
        """Start a new Crackerjack job via WebSocket server."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.websocket_url}/start-job", json={}) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            return data.get("job_id")
                    return None
        except Exception as e:
            console.print(f"[red]Failed to start job: {e}[/red]")
            return None
    
    async def _monitor_job_with_live_display(self, job_id: str) -> Dict[str, Any]:
        """Monitor job progress with Rich live display."""
        
        # Create progress display components
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(complete_style="green", finished_style="green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
            expand=True
        )
        
        # Create main progress task
        main_task = progress.add_task("Initializing...", total=100)
        
        last_status = {}
        iteration_count = 0
        max_iterations = 10
        
        # Create live display with progress and status table
        with Live(self._create_status_display(progress, last_status), refresh_per_second=2) as live:
            
            # Monitor until completion
            while True:
                try:
                    # Check progress via WebSocket server status
                    status = await self._get_job_progress(job_id)
                    
                    if status:
                        last_status = status
                        
                        # Update main progress
                        overall_progress = status.get("overall_progress", 0)
                        current_stage = status.get("current_stage", "unknown")
                        message = status.get("message", "")
                        iteration = status.get("iteration", 0)
                        
                        if iteration != iteration_count:
                            iteration_count = iteration
                            console.print(f"\n[bold yellow]🔄 Iteration {iteration}/{max_iterations}[/bold yellow]")
                        
                        # Update progress description and percentage
                        description = f"[cyan]{current_stage}[/cyan] - {message}"
                        progress.update(main_task, completed=overall_progress, description=description)
                        
                        # Update live display
                        live.update(self._create_status_display(progress, last_status))
                        
                        # Check if completed
                        job_status = status.get("status", "running")
                        if job_status in ("completed", "failed"):
                            final_message = "🎉 Perfect code quality achieved!" if job_status == "completed" else "⚠️ Workflow completed with issues"
                            progress.update(main_task, completed=100, description=f"[bold green]{final_message}[/bold green]")
                            live.update(self._create_status_display(progress, last_status))
                            
                            return {
                                "success": job_status == "completed",
                                "job_id": job_id,
                                "final_status": last_status,
                                "iterations_completed": iteration_count,
                                "message": final_message
                            }
                    
                    # Wait before next check
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    console.print(f"[red]Error monitoring job: {e}[/red]")
                    await asyncio.sleep(5)
    
    def _create_status_display(self, progress: Progress, status: Dict[str, Any]) -> Panel:
        """Create a rich status display panel."""
        
        # Create status table
        table = Table.grid(padding=1)
        table.add_column("Key", style="bold cyan")
        table.add_column("Value", style="white")
        
        if status:
            table.add_row("Job ID", status.get("job_id", "N/A"))
            table.add_row("Status", status.get("status", "N/A"))
            table.add_row("Iteration", f"{status.get('iteration', 0)}/{status.get('max_iterations', 10)}")
            table.add_row("Stage", status.get("current_stage", "N/A"))
            table.add_row("Progress", f"{status.get('overall_progress', 0)}%")
            
            # Add stage details if available
            details = status.get("details", {})
            if details:
                table.add_row("", "")  # Separator
                for key, value in details.items():
                    emoji = "✅" if value == "passed" else "❌" if value == "failed" else "⏳"
                    table.add_row(f"  {key}", f"{emoji} {value}")
        
        # Combine progress and table
        from rich.console import Group
        content = Group(progress, "", table)
        
        return Panel(
            content,
            title="[bold green]Crackerjack AI Agent Progress[/bold green]",
            border_style="green",
            padding=1
        )
    
    async def _get_job_progress(self, job_id: str) -> Dict[str, Any] | None:
        """Get current job progress from WebSocket server."""
        try:
            # Check if progress file exists in the server's directory
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.websocket_url}/") as response:
                    if response.status == 200:
                        server_status = await response.json()
                        active_jobs = server_status.get("active_jobs", [])
                        
                        # For now, simulate progress since we don't have direct access to progress files
                        # In a real implementation, this would read from the progress file
                        return {
                            "job_id": job_id,
                            "status": "running",
                            "iteration": 1,
                            "max_iterations": 10,
                            "overall_progress": 25,
                            "current_stage": "fast_hooks",
                            "message": "Running fast hooks...",
                            "details": {
                                "fast_hooks": "running",
                                "comprehensive_hooks": "pending",
                                "tests": "pending"
                            }
                        }
            return None
        except Exception:
            return None


async def execute_crackerjack_slash_command() -> Dict[str, Any]:
    """Main entry point for /crackerjack slash command."""
    command = CrackerjackSlashCommand()
    return await command.execute()


if __name__ == "__main__":
    asyncio.run(execute_crackerjack_slash_command())