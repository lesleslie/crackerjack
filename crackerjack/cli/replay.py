from __future__ import annotations

import argparse
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from crackerjack.core.ai_fix_events import (
    AgentDispatched,
    AIFixEvent,
    FixSessionFinished,
    FixSessionStarted,
    IssueFailed,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    RunFinished,
    RunStarted,
)
from crackerjack.core.ai_fix_sinks import JsonlSink

if TYPE_CHECKING:
    pass


def _format_event(event: AIFixEvent) -> str:
    if isinstance(event, RunStarted):
        return (
            f"[bold cyan]RUN STARTED[/] stage={event.stage} "
            f"issues={event.initial_issue_count}"
        )
    if isinstance(event, IterationStarted):
        return (
            f"[magenta]↻ iteration {event.iteration}[/] "
            f"strategy={event.strategy or '-'} issues={event.issue_count}"
        )
    if isinstance(event, IterationFinished):
        return (
            f"[magenta]✓ iteration {event.iteration} finished[/] "
            f"resolved={event.resolved} ok={event.success}"
        )
    if isinstance(event, RunFinished):
        return (
            f"[bold {'green' if event.success else 'red'}]"
            f"RUN FINISHED[/] success={event.success} "
            f"iterations={event.total_iterations}"
        )
    if isinstance(event, AgentDispatched):
        return (
            f" → [yellow]{event.agent}[/] {event.action} "
            f"on {event.file} ({event.issue_type})"
        )
    if isinstance(event, IssueResolved):
        return (
            f" [green]✓ resolved[/] {event.agent} "
            f"{event.file} ({event.duration_s:.1f}s)"
        )
    if isinstance(event, IssueFailed):
        return f" [red]✗ failed[/] {event.agent} {event.file}: {event.reason}"
    if isinstance(event, FixSessionStarted):
        return f" [dim]fix-session start[/] {event.issue_type} in {event.file}"
    if isinstance(event, FixSessionFinished):
        outcome = "[green]resolved[/]" if event.success else "[red]failed[/]"
        return (
            f" {outcome} [dim]fix-session end[/] {event.file} "
            f"(tier={event.final_tier}, no-ops={event.no_op_count}, "
            f"{event.total_duration_s:.1f}s)"
        )
    if _is_tier_transitioned(event):
        return (
            f" [dim]tier {event.from_tier}→{event.to_tier}[/] "
            f"{event.file} ({event.reason})"  # type: ignore[attr-defined]
        )
    return f" [dim]{type(event).__name__}[/]"


def _is_tier_transitioned(event: AIFixEvent) -> bool:

    from crackerjack.core.ai_fix_events import TierTransitioned

    return isinstance(event, TierTransitioned)


def _summary(events: list[AIFixEvent]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for e in events:
        kind = type(e).__name__
        summary[kind] = summary.get(kind, 0) + 1
    return summary


def render_replay(
    run_id: str,
    *,
    base_dir: Path | None = None,
    console: Console | None = None,
) -> int:
    console = console or Console()
    events: Iterator[AIFixEvent] = JsonlSink.restore_run(run_id, base_dir=base_dir)
    events_list = list(events)
    if not events_list:
        console.print(
            f"[red]No events.jsonl found for run_id={run_id!r}[/red]\n"
            f"Checked: {(base_dir or Path.cwd()) / '.crackerjack' / 'runs' / run_id / 'events.jsonl'}"  # noqa: E501
        )
        return 1

    console.print(f"[bold]crackerjack replay[/bold] — run_id={run_id}")
    console.print(f" events: {len(events_list)}")
    summary = _summary(events_list)
    console.print(
        " summary: "
        + ", ".join(f"{kind}={count}" for kind, count in sorted(summary.items()))
    )
    console.print()

    for event in events_list:
        console.print(_format_event(event))

    table = Table(title="Run summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    resolved = sum(1 for e in events_list if isinstance(e, IssueResolved))
    failed = sum(1 for e in events_list if isinstance(e, IssueFailed))
    dispatched = sum(1 for e in events_list if isinstance(e, AgentDispatched))
    sessions_started = sum(1 for e in events_list if isinstance(e, FixSessionStarted))
    sessions_finished = sum(1 for e in events_list if isinstance(e, FixSessionFinished))
    no_ops = sum(
        e.no_op_count for e in events_list if isinstance(e, FixSessionFinished)
    )
    iterations = sum(1 for e in events_list if isinstance(e, IterationStarted))
    run_finished = next((e for e in events_list if isinstance(e, RunFinished)), None)
    table.add_row("iterations started", str(iterations))
    table.add_row("agents dispatched", str(dispatched))
    table.add_row("issues resolved", str(resolved))
    table.add_row("issues failed", str(failed))
    table.add_row("fix sessions", f"{sessions_finished}/{sessions_started}")
    table.add_row("total no-op fixes", str(no_ops))
    if run_finished is not None:
        table.add_row("run success", str(run_finished.success))
    console.print()
    console.print(table)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crackerjack replay",
        description="Re-render an AI-fix run from its JSONL event log.",
    )
    parser.add_argument("run_id", help="Run identifier (timestamp-uuid prefix).")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Project base directory (defaults to cwd).",
    )
    args = parser.parse_args(argv)
    return render_replay(args.run_id, base_dir=args.base_dir)


if __name__ == "__main__":
    raise SystemExit(main())
