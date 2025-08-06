"""
Enterprise MCP Client for Crackerjack - Autonomous Code Quality at Scale

This module provides enterprise-grade MCP client functionality for managing
code quality across multiple projects, teams, and deployment pipelines.
"""

import asyncio
import json
import time
import typing as t
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
    )

    ENTERPRISE_DEPS_AVAILABLE = True
except ImportError:
    ENTERPRISE_DEPS_AVAILABLE = False
    Console = None
    Table = None
    Live = None
    Progress = None


@dataclass
class ProjectResult:
    project_path: str
    success: bool
    stages_completed: list[str] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class BatchResult:
    total_projects: int
    successful_projects: int
    failed_projects: int
    total_fixes_applied: int
    total_duration: float
    project_results: list[ProjectResult] = field(default_factory=list)
    start_time: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    end_time: str = ""


class EnterpriseMCPClient:
    def __init__(
        self, server_url: str = "http://localhost:8000", max_concurrent: int = 5
    ) -> None:
        if not ENTERPRISE_DEPS_AVAILABLE:
            raise ImportError(
                "Enterprise dependencies not available. Install with: pip install httpx rich"
            )
        self.server_url = server_url
        self.max_concurrent = max_concurrent
        self.console = Console()
        self.client = httpx.AsyncClient(timeout=300.0)

    async def run_enterprise_workflow(
        self,
        projects: list[str | Path],
        stages: list[str] = None,
        fail_fast: bool = False,
        create_reports: bool = True,
        report_dir: str = "crackerjack-reports",
    ) -> BatchResult:
        if stages is None:
            stages = ["fast", "tests", "comprehensive"]

        self.console.print(
            f"\n[bold cyan]🚀 Enterprise Crackerjack Auto-Fix Workflow[/bold cyan]"
        )
        self.console.print(
            f"[dim]Processing {len(projects)} projects with stages: {', '.join(stages)}[/dim]\n"
        )

        batch_result = BatchResult(
            total_projects=len(projects),
            successful_projects=0,
            failed_projects=0,
            total_fixes_applied=0,
            total_duration=0.0,
        )
        start_time = time.time()

        semaphore = asyncio.Semaphore(self.max_concurrent)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(
                f"Processing {len(projects)} projects...", total=len(projects)
            )

            tasks = [
                self._process_project_with_semaphore(
                    semaphore, project, stages, progress, task
                )
                for project in projects
            ]

            project_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in project_results:
                if isinstance(result, Exception):
                    self.console.print(
                        f"[red]❌ Error processing project: {result}[/red]"
                    )
                    batch_result.failed_projects += 1
                elif isinstance(result, ProjectResult):
                    batch_result.project_results.append(result)
                    if result.success:
                        batch_result.successful_projects += 1
                    else:
                        batch_result.failed_projects += 1
                        if fail_fast:
                            self.console.print(
                                "[red]💥 Fail-fast enabled, stopping on first failure[/red]"
                            )
                            break

                    batch_result.total_fixes_applied += len(result.fixes_applied)
                    batch_result.total_duration += result.duration

        batch_result.end_time = datetime.now(timezone.utc).isoformat()
        batch_result.total_duration = time.time() - start_time

        self._display_batch_results(batch_result)

        if create_reports:
            await self._create_enterprise_reports(batch_result, report_dir)

        return batch_result

    async def _process_project_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        project_path: str | Path,
        stages: list[str],
        progress: Progress,
        task_id: t.Any,
    ) -> ProjectResult:
        async with semaphore:
            result = await self._process_single_project(project_path, stages)
            progress.advance(task_id)
            return result

    async def _process_single_project(
        self, project_path: str | Path, stages: list[str]
    ) -> ProjectResult:
        project_path = str(project_path)
        result = ProjectResult(project_path=project_path, success=True)
        start_time = time.time()
        try:
            for stage in stages:
                self.console.print(
                    f"[dim]  📂 {project_path}: Running {stage} stage...[/dim]"
                )
                stage_result = await self._run_stage(stage, project_path)
                if stage_result.get("success", False):
                    result.stages_completed.append(stage)
                    fixes = stage_result.get("fixes_applied", [])
                    result.fixes_applied.extend(fixes)
                else:
                    result.success = False
                    error_msg = stage_result.get("error", f"{stage} stage failed")
                    result.errors.append(error_msg)
                    self.console.print(
                        f"[yellow]  ⚠️ {project_path}: {stage} stage failed - {error_msg}[/yellow]"
                    )
                    break
            if result.success:
                self.console.print(
                    f"[green]  ✅ {project_path}: All stages completed successfully[/green]"
                )
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            self.console.print(
                f"[red]  ❌ {project_path}: Unexpected error - {e}[/red]"
            )
        result.duration = time.time() - start_time
        return result

    async def _run_stage(self, stage: str, project_path: str = ".") -> dict[str, t.Any]:
        try:
            payload = {
                "tool": "run_crackerjack_stage",
                "arguments": {
                    "stage": stage,
                    "max_retries": 2,
                    "project_path": project_path,
                },
            }
            response = await self.client.post(
                f"{self.server_url}/execute", json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e), "stage": stage}

    def _display_batch_results(self, batch_result: BatchResult) -> None:
        self.console.print("\n" + "=" * 80)
        self.console.print(f"[bold cyan]🏆 Enterprise Auto-Fix Results[/bold cyan]")
        self.console.print("=" * 80)
        table = Table(title="Batch Processing Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Total Projects", str(batch_result.total_projects))
        table.add_row("Successful", str(batch_result.successful_projects))
        table.add_row("Failed", str(batch_result.failed_projects))
        table.add_row(
            "Success Rate",
            f"{(batch_result.successful_projects / batch_result.total_projects * 100):.1f}%",
        )
        table.add_row("Total Fixes Applied", str(batch_result.total_fixes_applied))
        table.add_row("Total Duration", f"{batch_result.total_duration:.2f}s")
        table.add_row(
            "Avg Duration/Project",
            f"{batch_result.total_duration / batch_result.total_projects:.2f}s",
        )
        self.console.print(table)
        if batch_result.failed_projects > 0:
            self.console.print(
                f"\n[red]Failed Projects ({batch_result.failed_projects}):[/red]"
            )
            for result in batch_result.project_results:
                if not result.success:
                    self.console.print(
                        f"  [red]❌ {result.project_path}[/red] - {', '.join(result.errors)}"
                    )
        self.console.print(
            f"\n[green]✨ Enterprise auto-fix completed! {batch_result.total_fixes_applied} total fixes applied.[/green]"
        )

    async def _create_enterprise_reports(
        self, batch_result: BatchResult, report_dir: str
    ) -> None:
        report_path = Path(report_dir)
        report_path.mkdir(exist_ok=True)
        json_report = (
            report_path
            / f"crackerjack-batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
        with open(json_report, "w") as f:
            json.dump(
                {
                    "batch_summary": {
                        "total_projects": batch_result.total_projects,
                        "successful_projects": batch_result.successful_projects,
                        "failed_projects": batch_result.failed_projects,
                        "success_rate": batch_result.successful_projects
                        / batch_result.total_projects
                        * 100,
                        "total_fixes_applied": batch_result.total_fixes_applied,
                        "total_duration": batch_result.total_duration,
                        "start_time": batch_result.start_time,
                        "end_time": batch_result.end_time,
                    },
                    "project_results": [
                        {
                            "project_path": r.project_path,
                            "success": r.success,
                            "stages_completed": r.stages_completed,
                            "fixes_applied": r.fixes_applied,
                            "errors": r.errors,
                            "duration": r.duration,
                            "timestamp": r.timestamp,
                        }
                        for r in batch_result.project_results
                    ],
                },
                f,
                indent=2,
            )
        md_report = (
            report_path
            / f"crackerjack-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        )
        with open(md_report, "w") as f:
            f.write(f"# Crackerjack Enterprise Auto-Fix Report\n\n")
            f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
            f.write(f"## Summary\n\n")
            f.write(f"- **Total Projects**: {batch_result.total_projects}\n")
            f.write(f"- **Successful**: {batch_result.successful_projects}\n")
            f.write(f"- **Failed**: {batch_result.failed_projects}\n")
            f.write(
                f"- **Success Rate**: {(batch_result.successful_projects / batch_result.total_projects * 100):.1f}%\n"
            )
            f.write(f"- **Total Fixes Applied**: {batch_result.total_fixes_applied}\n")
            f.write(f"- **Total Duration**: {batch_result.total_duration:.2f}s\n\n")
            f.write(f"## Project Results\n\n")
            f.write(f"| Project | Status | Stages | Fixes | Duration | Errors |\n")
            f.write(f"|---------|--------|--------|-------|----------|--------|\n")
            for result in batch_result.project_results:
                status = "✅" if result.success else "❌"
                stages = ", ".join(result.stages_completed)
                fixes = len(result.fixes_applied)
                errors = "; ".join(result.errors) if result.errors else "None"
                f.write(
                    f"| {result.project_path} | {status} | {stages} | {fixes} | {result.duration:.2f}s | {errors} |\n"
                )
        self.console.print(f"\n[cyan]📊 Enterprise reports created:[/cyan]")
        self.console.print(f"  [dim]📄 JSON: {json_report}[/dim]")
        self.console.print(f"  [dim]📝 Markdown: {md_report}[/dim]")

    async def monitor_real_time(self, projects: list[str], interval: int = 60) -> None:
        self.console.print(f"[bold cyan]👀 Real-time Quality Monitoring[/bold cyan]")
        self.console.print(
            f"[dim]Monitoring {len(projects)} projects every {interval}s[/dim]\n"
        )
        try:
            while True:
                self.console.print(
                    f"[dim]{datetime.now().strftime('%H:%M:%S')} - Running quality checks...[/dim]"
                )
                for project in projects:
                    try:
                        result = await self._run_stage("fast", str(project))
                        if result.get("success", False):
                            self.console.print(
                                f"  [green]✅ {project}: Quality checks passed[/green]"
                            )
                        else:
                            self.console.print(
                                f"  [yellow]⚠️ {project}: Issues detected[/yellow]"
                            )
                    except Exception as e:
                        self.console.print(
                            f"  [red]❌ {project}: Monitor error - {e}[/red]"
                        )
                await asyncio.sleep(interval)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]🛑 Monitoring stopped by user[/yellow]")

    async def close(self) -> None:
        await self.client.aclose()


async def run_enterprise_batch(projects: list[str], **kwargs) -> BatchResult:
    client = EnterpriseMCPClient()
    try:
        return await client.run_enterprise_workflow(projects, **kwargs)
    finally:
        await client.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m crackerjack.mcp_enterprise <project1> <project2> ...")
        sys.exit(1)

    projects = sys.argv[1:]
    result = asyncio.run(run_enterprise_batch(projects))

    if result.failed_projects > 0:
        sys.exit(1)
