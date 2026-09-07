"""Gitignore conformance CLI for Bodai fleet repos.

Subcommands:
  - check: report whether the canonical snippet is installed in the
    repo at --pkg-path. Exits 1 when the snippet is missing or drifted.
  - sync: install (or refresh) the canonical snippet in the repo,
    backing up the existing .gitignore first.

Both subcommands refuse to operate on non-Bodai repos (silently
return success, no mutation) so crackerjack stays usable outside the
fleet.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from crackerjack.checks.gitignore_conformance import (
    check_repo_gitignore,
    sync_repo_gitignore,
)

app = typer.Typer(
    name="gitignore",
    help=(
        "Bodai `.gitignore` snippet conformance: `check` reports drift, "
        "`sync` installs or refreshes the canonical block. Non-Bodai "
        "repos are skipped silently."
    ),
    no_args_is_help=True,
)
console = Console()


@app.command()
def check(
    pkg_path: Path = typer.Option(
        Path(),
        "--pkg-path",
        help="Project root containing .gitignore (defaults to CWD).",
    ),
) -> None:
    """Check whether the canonical Bodai `.gitignore` snippet is installed."""
    result = check_repo_gitignore(pkg_path)
    if not result.is_fleet_member:
        console.print(f"[dim]Skipped (non-Bodai): {result.repo_path}[/dim]")
        raise typer.Exit(0)

    if result.snippet_present and not result.missing_patterns:
        console.print(
            f"[green]OK[/green] Bodai `.gitignore` snippet is present in "
            f"{result.repo_path}"
        )
        raise typer.Exit(0)

    if not result.snippet_present:
        console.print(
            f"[red]MISSING[/red] Bodai `.gitignore` snippet is not present "
            f"in {result.repo_path}. Run `crackerjack gitignore sync` to install."
        )
        raise typer.Exit(1)

    console.print(
        f"[red]DRIFT[/red] Bodai `.gitignore` snippet is present but "
        f"missing {len(result.missing_patterns)} pattern(s) in {result.repo_path}:"
    )
    for pattern in result.missing_patterns:
        console.print(f"  - {pattern}")
    raise typer.Exit(1)


@app.command()
def sync(
    pkg_path: Path = typer.Option(
        Path(),
        "--pkg-path",
        help="Project root whose .gitignore should be updated.",
    ),
    no_backup: bool = typer.Option(
        False,
        "--no-backup",
        help="Skip writing a timestamped .gitignore backup before overwriting.",
    ),
) -> None:
    """Install or refresh the canonical Bodai `.gitignore` snippet."""
    result = sync_repo_gitignore(pkg_path, backup=not no_backup)

    if not result.is_fleet_member:
        console.print(f"[dim]Skipped (non-Bodai): {result.repo_path}[/dim]")
        raise typer.Exit(0)

    console.print(
        f"[green]Synced[/green] Bodai `.gitignore` snippet in {result.repo_path}"
    )
    if result.backup_path:
        console.print(f"  Backup: {result.backup_path}")
    raise typer.Exit(0)
