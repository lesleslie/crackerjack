"""CLI handlers for test coverage reporting and status"""

import typing as t
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends


@depends.inject  # type: ignore[misc]
def display_coverage_info(
    coverage_info: dict[str, t.Any], console: Inject[Console]
) -> None:
    coverage_percent = coverage_info.get("coverage_percent", 0.0)
    coverage_source = coverage_info.get("source", "unknown")

    if coverage_percent > 0:
        console.print(
            f"[green]Current Coverage:[/green] {coverage_percent:.2f}% (from {coverage_source})"
        )
    else:
        console.print("[yellow]Current Coverage:[/yellow] No coverage data available")

    status_message = coverage_info.get("message")
    if status_message:
        console.print(f"[dim]{status_message}[/dim]")


@depends.inject  # type: ignore[misc]
def display_coverage_report(test_manager: t.Any, console: Inject[Console]) -> None:
    coverage_report = test_manager.get_coverage_report()
    if coverage_report:
        console.print(f"[cyan]Details:[/cyan] {coverage_report}")


@depends.inject  # type: ignore[misc]
def display_ratchet_status(test_manager: t.Any, console: Inject[Console]) -> None:
    from contextlib import suppress

    with suppress(Exception):
        ratchet_status = test_manager.get_coverage_ratchet_status()
        if ratchet_status:
            next_milestone = ratchet_status.get("next_milestone")
            if next_milestone:
                console.print(f"[cyan]Next Milestone:[/cyan] {next_milestone:.0f}%")

            milestones = ratchet_status.get("milestones_achieved", [])
            if milestones:
                console.print(f"[green]Milestones Achieved:[/green] {len(milestones)}")


@depends.inject  # type: ignore[misc]
def handle_coverage_status(
    coverage_status: bool, options: t.Any, console: Inject[Console]
) -> bool:
    if not coverage_status:
        return True

    try:
        from crackerjack.managers.test_manager import TestManager

        pkg_path = Path.cwd()

        test_manager = TestManager(pkg_path)

        console.print("[cyan]📊[/cyan] Coverage Status Report")
        console.print("=" * 50)

        coverage_info = test_manager.get_coverage()
        display_coverage_info(coverage_info)

        display_coverage_report(test_manager)

        display_ratchet_status(test_manager)

        console.print()
        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Failed to get coverage status: {e}")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False
