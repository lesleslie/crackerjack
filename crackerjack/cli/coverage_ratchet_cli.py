from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from crackerjack.services.coverage_ratchet import CoverageRatchetService

app = typer.Typer(
    name="coverage-ratchet",
    help=(
        "Coverage ratchet commands: initialize, status, lower. "
        "See CoverageRatchetService for underlying state."
    ),
    no_args_is_help=True,
)
console = Console()


@app.command()
def init(
    pkg_path: Path = typer.Option(
        Path(),
        "--pkg-path",
        help="Project root containing coverage.json and pyproject.toml.",
    ),
    reinit: bool = typer.Option(
        False,
        "--reinit",
        help="Overwrite an existing .coverage-ratchet.json.",
    ),
) -> None:
    """Initialize the coverage ratchet at current coverage."""
    svc = CoverageRatchetService(pkg_path=pkg_path)
    if svc.ratchet_file.exists() and not reinit:
        console.print(
            f"[red]Ratchet already exists at {pkg_path / '.coverage-ratchet.json'}[/red]"
        )
        console.print("[dim]Use --reinit to overwrite.[/dim]")
        raise typer.Exit(1)
    coverage_file = pkg_path / "coverage.json"
    if not coverage_file.exists():
        console.print(
            "[red]coverage.json not found.[/red] Run pytest with coverage first."
        )
        raise typer.Exit(1)
    data = json.loads(coverage_file.read_text())
    coverage = float(data.get("totals", {}).get("percent_covered", 0.0))
    svc.initialize_baseline(coverage)
    try:
        svc.mirror_to_pyproject(coverage)
    except FileNotFoundError:
        console.print(
            "[yellow]⚠️  pyproject.toml not found; skipped mirroring.[/yellow]"
        )
    console.print(f"[green]✅ Ratchet initialized at {coverage:.2f}%[/green]")


@app.command()
def status(
    pkg_path: Path = typer.Option(
        Path(),
        "--pkg-path",
        help="Project root to read ratchet state from.",
    ),
) -> None:
    """Show ratchet state."""
    svc = CoverageRatchetService(pkg_path=pkg_path)
    console.print(svc.report_status())


@app.command()
def lower(
    to_coverage: float = typer.Option(
        ...,
        "--to",
        help="New lower-bound coverage percentage (operator ack of regression).",
    ),
    reason: str = typer.Option(
        ...,
        "--reason",
        help="Non-empty justification for lowering the ratchet.",
    ),
    pkg_path: Path = typer.Option(
        Path(),
        "--pkg-path",
        help="Project root containing the ratchet file.",
    ),
) -> None:
    """Explicitly lower the ratchet (operator ack of regression)."""
    svc = CoverageRatchetService(pkg_path=pkg_path)
    try:
        svc.lower_baseline(to_coverage, reason=reason)
    except ValueError as exc:
        console.print(f"[red]❌ {exc}[/red]")
        raise typer.Exit(1) from exc
    try:
        svc.mirror_to_pyproject(to_coverage)
    except FileNotFoundError:
        console.print(
            "[yellow]⚠️  pyproject.toml not found; skipped mirroring.[/yellow]"
        )
    console.print(
        f"[green]✅ Ratchet lowered to {to_coverage:.2f}% (reason: {reason})[/green]"
    )


__all__ = ["app", "console"]
