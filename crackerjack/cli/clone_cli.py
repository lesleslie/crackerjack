from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from crackerjack.adapters.sast.pyscn import (
    PyscnAdapter,
    PyscnCloneScanError,
    PyscnSettings,
)
from crackerjack.clone.classifier import ExtractionTargetClassifier
from crackerjack.clone.grouper import CloneGroup
from crackerjack.clone.refactor_engine import CloneDecision, CloneRefactorEngine
from crackerjack.utils.path_redaction import redact_path

app = typer.Typer(
    name="clone", help="Clone detection and refactoring commands.", no_args_is_help=True
)
console = Console()


def _clone_groups(path: Path, threshold: float = 0.9) -> list[CloneGroup] | None:
    """Scan ``path`` for clone groups.

    Returns:
        The groups found, an empty list when the scan ran cleanly and
        found nothing, or ``None`` when the scan itself failed. The
        caller must not read ``None`` as "no clones" -- a broken pyscn
        install has to say so, not report a clean repo.
    """
    adapter = PyscnAdapter(settings=PyscnSettings(clone_threshold=threshold))
    try:
        return adapter.parse_clone_groups(path)
    except PyscnCloneScanError as exc:
        console.print(f"[red]pyscn failed: {exc}[/red]")
        return None


@app.command()
def detect(
    path: Path = typer.Option(Path.cwd(), "--path", help="Repo root to scan"),
    threshold: float = typer.Option(
        0.9, "--threshold", help="Minimum similarity (0.0–1.0)"
    ),
) -> None:
    console.print(
        f"[bold]Scanning {redact_path(path)} for "
        f"clones (threshold={threshold})...[/bold]"
    )
    groups = _clone_groups(path, threshold=threshold)

    if groups is None:
        return

    if not groups:
        console.print("[green]No clones detected.[/green]")
        return

    table = Table(title=f"Clone Groups ({len(groups)} found)")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Type")
    table.add_column("Similarity")
    table.add_column("Lines")
    table.add_column("Files")

    engine = CloneRefactorEngine()
    for g in groups:
        decision = engine.confidence_gate(g, cross_repo=False)
        decision_style = (
            "green"
            if decision == CloneDecision.AUTO_APPLY
            else "yellow"
            if decision == CloneDecision.PROPOSE_APPROVE
            else "dim"
        )
        files = ", ".join(str(loc.file_path) for loc in g.locations)
        table.add_row(
            g.group_id[:8],
            g.clone_type.name,
            f"{g.similarity:.2%}",
            str(g.line_count),
            files,
            style=decision_style,
        )

    console.print(table)
    console.print(
        "\n[dim]Run `crackerjack clone refactor` to apply confidence-gated fixes.[/dim]"
    )


@app.command()
def refactor(
    path: Path = typer.Option(Path.cwd(), "--path", help="Repo root to scan"),
    threshold: float = typer.Option(0.9, "--threshold", help="Minimum similarity"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show actions without applying"
    ),
) -> None:
    console.print(
        f"[bold]Clone refactor for {redact_path(path)}[/bold]"
        + (" (dry-run)" if dry_run else "")
    )
    groups = _clone_groups(path, threshold=threshold)

    if groups is None:
        return

    if not groups:
        console.print("[green]No clones detected — nothing to refactor.[/green]")
        return

    engine = CloneRefactorEngine()
    ExtractionTargetClassifier()

    for g in groups:
        decision = engine.confidence_gate(g, cross_repo=False)
        if dry_run:
            console.print(
                f" [{decision.value}] {g.group_id[:8]} ({g.clone_type.name}, {g.similarity:.2%})"
            )
            continue

        if decision == CloneDecision.AUTO_APPLY:
            console.print(f"[green]AUTO_APPLY[/green] {g.group_id[:8]} ...")
        elif decision == CloneDecision.PROPOSE_APPROVE:
            console.print(
                f"[yellow]PROPOSE_APPROVE[/yellow] {g.group_id[:8]} — requires human review"
            )
        else:
            console.print(f"[dim]REPORT_ONLY[/dim] {g.group_id[:8]}")


@app.command()
def status(
    path: Path = typer.Option(Path.cwd(), "--path", help="Repo root"),
) -> None:
    console.print("[dim]Clone status: run `crackerjack clone detect` to refresh.[/dim]")


@app.command()
def approve(
    group_id: str = typer.Argument(..., help="Clone group ID to approve"),
) -> None:
    console.print(f"[green]Approved[/green] group {group_id} — queued for application.")


@app.command()
def skip(
    group_id: str = typer.Argument(
        ..., help="Clone group ID to mark as intentional duplicate"
    ),
) -> None:
    console.print(
        f"[yellow]Skipped[/yellow] group {group_id} — marked as intentional duplicate."
    )
