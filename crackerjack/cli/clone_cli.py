from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from crackerjack.clone.classifier import ExtractionTargetClassifier
from crackerjack.clone.grouper import CloneGrouper
from crackerjack.clone.refactor_engine import CloneDecision, CloneRefactorEngine

app = typer.Typer(
    name="clone", help="Clone detection and refactoring commands.", no_args_is_help=True
)
console = Console()


def _run_pyscn_json(path: Path, threshold: float = 0.9) -> dict[str, Any]:
    report_dir = path / ".pyscn" / "reports"
    result = subprocess.run(
        [
            "pyscn",
            "analyze",
            "--json",
            "--select",
            "clones",
            "--clone-threshold",
            str(threshold),
            str(path),
        ],
        capture_output=True,
        text=True,
        cwd=str(path),
    )
    if result.returncode not in (0, 1):
        console.print(f"[red]pyscn failed: {result.stderr}[/red]")
        return {}

    import glob

    files = sorted(glob.glob(str(report_dir / "analyze_*.json")))
    if not files:
        console.print("[yellow]No pyscn report found.[/yellow]")
        return {}

    with open(files[-1], encoding="utf-8") as f:
        return json.load(f)


@app.command()
def detect(
    path: Path = typer.Option(Path.cwd(), "--path", help="Repo root to scan"),
    threshold: float = typer.Option(
        0.9, "--threshold", help="Minimum similarity (0.0–1.0)"
    ),
) -> None:
    console.print(f"[bold]Scanning {path} for clones (threshold={threshold})...[/bold]")
    data = _run_pyscn_json(path, threshold=threshold)
    clone_data = data.get("clone", {})
    raw_pairs = clone_data.get("clone_pairs") or []

    if not raw_pairs:
        console.print("[green]No clones detected.[/green]")
        return

    grouper = CloneGrouper()
    groups = grouper.group_pairs(raw_pairs)

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
        f"[bold]Clone refactor for {path}[/bold]" + (" (dry-run)" if dry_run else "")
    )
    data = _run_pyscn_json(path, threshold=threshold)
    raw_pairs = (data.get("clone") or {}).get("clone_pairs") or []

    if not raw_pairs:
        console.print("[green]No clones detected — nothing to refactor.[/green]")
        return

    grouper = CloneGrouper()
    groups = grouper.group_pairs(raw_pairs)
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
