"""CLI handlers for advanced optimization features"""

import typing as t
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends


@depends.inject  # type: ignore[misc]
def handle_advanced_optimizer(
    advanced_optimizer: bool,
    advanced_profile: str | None,
    advanced_report: str | None,
    console: Inject[Console] = None,
) -> bool:
    if not advanced_optimizer:
        return True

    console.print("[cyan]🏢[/cyan] Running advanced-scale optimization analysis...")
    try:
        optimizer = setup_advanced_optimizer(advanced_profile)
        result = run_advanced_optimization(optimizer)
        display_advanced_results(result, advanced_report)
        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Advanced optimizer error: {e}")
        return False


def setup_advanced_optimizer(advanced_profile: str | None) -> t.Any:
    import tempfile

    from crackerjack.services.ai.advanced_optimizer import AdvancedOptimizer

    config_dir = Path.cwd() / ".crackerjack"
    storage_dir = Path(tempfile.gettempdir()) / "crackerjack_storage"
    optimizer = AdvancedOptimizer(config_dir, storage_dir)

    if advanced_profile:
        optimizer.performance_profile.optimization_strategy = advanced_profile

    return optimizer


@depends.inject  # type: ignore[misc]
def run_advanced_optimization(optimizer: t.Any, console: Inject[Console]) -> t.Any:
    import asyncio

    console.print("[blue]📊[/blue] Analyzing system resources and performance...")
    return asyncio.run(optimizer.run_optimization_cycle())


@depends.inject  # type: ignore[misc]
def display_advanced_results(
    result: t.Any, advanced_report: str | None, console: Inject[Console]
) -> None:
    if result["status"] == "success":
        console.print("[green]✅[/green] Advanced optimization completed successfully")
        display_advanced_metrics(result["metrics"])
        display_advanced_recommendations(result["recommendations"])
        save_advanced_report(result, advanced_report)
    else:
        console.print(
            f"[red]❌[/red] Advanced optimization failed: {result.get('message', 'Unknown error')}"
        )


@depends.inject  # type: ignore[misc]
def display_advanced_metrics(metrics: t.Any, console: Inject[Console]) -> None:
    console.print(f"[blue]CPU Usage:[/blue] {metrics['cpu_percent']:.1f}%")
    console.print(f"[blue]Memory Usage:[/blue] {metrics['memory_percent']:.1f}%")
    console.print(f"[blue]Storage Usage:[/blue] {metrics['disk_usage_percent']:.1f}%")


@depends.inject  # type: ignore[misc]
def display_advanced_recommendations(
    recommendations: t.Any, console: Inject[Console]
) -> None:
    if recommendations:
        console.print(
            f"\n[yellow]💡[/yellow] Found {len(recommendations)} optimization recommendations:"
        )
        for rec in recommendations[:3]:
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}[
                rec["priority"]
            ]
            console.print(
                f" [{priority_color}]{rec['priority'].upper()}[/{priority_color}]: {rec['title']}"
            )


@depends.inject  # type: ignore[misc]
def save_advanced_report(
    result: t.Any, advanced_report: str | None, console: Inject[Console]
) -> None:
    if advanced_report:
        import json

        with open(advanced_report, "w") as f:
            json.dump(result, f, indent=2)
        console.print(f"[green]📄[/green] Advanced report saved to: {advanced_report}")
