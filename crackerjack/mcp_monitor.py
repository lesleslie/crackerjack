"""
Real-Time MCP Monitoring Dashboard for Crackerjack

This module provides a real-time monitoring dashboard for tracking code quality
across multiple projects and development teams.
"""

import asyncio
import json
import time
import typing as t
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.progress import Progress, SpinnerColumn, TextColumn

    MONITOR_DEPS_AVAILABLE = True
except ImportError:
    MONITOR_DEPS_AVAILABLE = False


class QualityMetrics:
    def __init__(self) -> None:
        self.metrics = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "total_fixes_applied": 0,
            "avg_response_time": 0.0,
            "last_check": None,
            "uptime_start": datetime.now(timezone.utc),
        }

    def update(self, success: bool, fixes_applied: int, response_time: float) -> None:
        self.metrics["total_checks"] += 1
        if success:
            self.metrics["successful_checks"] += 1
        else:
            self.metrics["failed_checks"] += 1
        self.metrics["total_fixes_applied"] += fixes_applied
        self.metrics["last_check"] = datetime.now(timezone.utc).isoformat()
        current_avg = self.metrics["avg_response_time"]
        total_checks = self.metrics["total_checks"]
        self.metrics["avg_response_time"] = (
            (current_avg * (total_checks - 1)) + response_time
        ) / total_checks

    @property
    def success_rate(self) -> float:
        if self.metrics["total_checks"] == 0:
            return 0.0
        return (self.metrics["successful_checks"] / self.metrics["total_checks"]) * 100

    @property
    def uptime(self) -> str:
        delta = datetime.now(timezone.utc) - self.metrics["uptime_start"]
        hours, remainder = divmod(delta.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"


class CrackerjackMonitor:
    def __init__(
        self, server_url: str = "http://localhost:8000", update_interval: int = 30
    ) -> None:
        if not MONITOR_DEPS_AVAILABLE:
            raise ImportError(
                "Monitor dependencies not available. Install with: pip install httpx rich"
            )
        self.server_url = server_url
        self.update_interval = update_interval
        self.console = Console()
        self.client = httpx.AsyncClient(timeout=60.0)
        self.projects: dict[str, QualityMetrics] = {}
        self.global_metrics = QualityMetrics()
        self.running = False
        self.last_update = None

    async def add_project(self, project_path: str) -> None:
        if project_path not in self.projects:
            self.projects[project_path] = QualityMetrics()
            self.console.print(
                f"[green]➕ Added project to monitoring: {project_path}[/green]"
            )

    async def remove_project(self, project_path: str) -> None:
        if project_path in self.projects:
            del self.projects[project_path]
            self.console.print(
                f"[yellow]➖ Removed project from monitoring: {project_path}[/yellow]"
            )

    async def start_monitoring(self, projects: list[str]) -> None:
        self.console.print(
            "[bold cyan]🖥️ Starting Crackerjack Real-Time Monitor[/bold cyan]"
        )
        self.console.print(
            f"[dim]Monitoring {len(projects)} projects every {self.update_interval}s[/dim]\n"
        )
        for project in projects:
            await self.add_project(project)
        self.running = True
        with Live(
            self._create_dashboard(), refresh_per_second=1, console=self.console
        ) as live:
            try:
                while self.running:
                    await self._update_all_projects()
                    live.update(self._create_dashboard())
                    await asyncio.sleep(self.update_interval)
            except KeyboardInterrupt:
                self.running = False
                self.console.print("\n[yellow]🛑 Monitoring stopped by user[/yellow]")

    async def _update_all_projects(self) -> None:
        self.last_update = datetime.now(timezone.utc)
        tasks = [
            self._check_project_quality(project) for project in self.projects.keys()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_project_quality(self, project_path: str) -> None:
        start_time = time.time()
        try:
            result = await self._run_quality_check(project_path)
            response_time = time.time() - start_time
            success = result.get("success", False)
            fixes_applied = len(result.get("fixes_applied", []))
            self.projects[project_path].update(success, fixes_applied, response_time)
            self.global_metrics.update(success, fixes_applied, response_time)
        except Exception as e:
            response_time = time.time() - start_time
            self.projects[project_path].update(False, 0, response_time)
            self.global_metrics.update(False, 0, response_time)

    async def _run_quality_check(self, project_path: str) -> dict[str, t.Any]:
        try:
            payload = {
                "tool": "run_crackerjack_stage",
                "arguments": {
                    "stage": "fast",
                    "max_retries": 1,
                    "project_path": project_path,
                },
            }
            response = await self.client.post(
                f"{self.server_url}/execute", json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e), "fixes_applied": []}

    def _create_dashboard(self) -> Panel:
        global_table = Table(title="🌍 Global Quality Metrics", show_header=True)
        global_table.add_column("Metric", style="cyan")
        global_table.add_column("Value", style="green")
        global_table.add_row(
            "Total Checks", str(self.global_metrics.metrics["total_checks"])
        )
        global_table.add_row("Success Rate", f"{self.global_metrics.success_rate:.1f}%")
        global_table.add_row(
            "Total Fixes Applied",
            str(self.global_metrics.metrics["total_fixes_applied"]),
        )
        global_table.add_row(
            "Avg Response Time",
            f"{self.global_metrics.metrics['avg_response_time']:.2f}s",
        )
        global_table.add_row("Monitor Uptime", self.global_metrics.uptime)
        global_table.add_row(
            "Last Update",
            self.last_update.strftime("%H:%M:%S") if self.last_update else "Never",
        )
        project_table = Table(title="📂 Project Status", show_header=True)
        project_table.add_column("Project", style="cyan")
        project_table.add_column("Status", style="green")
        project_table.add_column("Checks", justify="right")
        project_table.add_column("Success Rate", justify="right")
        project_table.add_column("Fixes Applied", justify="right")
        project_table.add_column("Avg Response", justify="right")
        for project_path, metrics in self.projects.items():
            status = (
                "🟢 Healthy"
                if metrics.success_rate >= 80
                else "🟡 Warning"
                if metrics.success_rate >= 50
                else "🔴 Critical"
            )
            project_table.add_row(
                project_path,
                status,
                str(metrics.metrics["total_checks"]),
                f"{metrics.success_rate:.1f}%",
                str(metrics.metrics["total_fixes_applied"]),
                f"{metrics.metrics['avg_response_time']:.2f}s",
            )
        dashboard = Panel(
            Columns([global_table, project_table]),
            title="🤖 Crackerjack Real-Time Quality Monitor",
            subtitle=f"Monitoring {len(self.projects)} projects • Updates every {self.update_interval}s",
        )

        return dashboard

    async def generate_report(self, output_file: str = None) -> dict[str, t.Any]:
        if output_file is None:
            output_file = (
                f"crackerjack-monitor-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            )
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "monitoring_duration": self.global_metrics.uptime,
            "global_metrics": self.global_metrics.metrics,
            "project_metrics": {
                project: metrics.metrics for project, metrics in self.projects.items()
            },
        }
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)
        self.console.print(f"[green]📊 Monitoring report saved: {output_file}[/green]")
        return report

    async def close(self) -> None:
        self.running = False
        await self.client.aclose()


async def start_monitoring_dashboard(
    projects: list[str], update_interval: int = 30
) -> None:
    monitor = CrackerjackMonitor(update_interval=update_interval)
    try:
        await monitor.start_monitoring(projects)
    finally:
        await monitor.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m crackerjack.mcp_monitor <project1> <project2> ...")
        sys.exit(1)

    projects = sys.argv[1:]
    asyncio.run(start_monitoring_dashboard(projects))
