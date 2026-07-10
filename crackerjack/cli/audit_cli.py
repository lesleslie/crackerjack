from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(
    name="audit",
    help=(
        "Orphan-detection audit. Wraps the project's "
        "scripts/audit_orphans.py. Reports recently-added Python "
        "symbols with zero callers ('built but not wired')."
    ),
    no_args_is_help=True,
)
console = Console()


def _find_audit_script(path: Path) -> Path | None:
    canonical = path / "scripts" / "audit_orphans.py"
    if canonical.exists():
        return canonical
    for candidate in path.glob("audit_orphans.py"):
        rel = candidate.relative_to(path)
        if len(rel.parts) <= 3:
            return candidate
    for candidate in path.rglob("audit_orphans.py"):
        rel = candidate.relative_to(path)
        if len(rel.parts) <= 3 and "node_modules" not in rel.parts:
            return candidate
    return None


@app.command()
def orphans(
    path: Path = typer.Option(
        Path.cwd(),
        "--path",
        "-p",
        help="Project root to audit (default: current directory).",
    ),
    days: int = typer.Option(
        30,
        "--days",
        "-d",
        help="Lookback window in days (default: 30).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of the Markdown report.",
    ),
    fail_on_orphans: bool = typer.Option(
        False,
        "--fail",
        help="Exit with non-zero status when orphans are found. Use in CI to gate.",
    ),
    include_stub_check: bool = typer.Option(
        False,
        "--include-stub-check",
        help="Best-effort: also exclude Pydantic discriminated-union members.",
    ),
    include_tests: bool = typer.Option(
        False,
        "--include-tests",
        help="Include symbols defined in tests/ (off by default).",
    ),
) -> None:
    audit_script = _find_audit_script(path)
    if audit_script is None:
        expected = path / "scripts" / "audit_orphans.py"
        console.print(
            f"[red]audit_orphans.py not found under {path}[/red]\n"
            f"[dim]Expected: {expected}[/dim]\n"
            f"[dim]See: https://github.com/lesleslie/mahavishnu "
            f"for the canonical script.[/dim]"
        )
        raise typer.Exit(2)

    cmd: list[str] = [
        sys.executable,
        str(audit_script),
        "--days",
        str(days),
        "--root",
        str(path),
    ]
    if json_output:
        cmd.append("--json")
    if include_stub_check:
        cmd.append("--include-stub-check")
    if include_tests:
        cmd.append("--include-tests")

    console.print(f"[dim]Running[/dim] [cyan]{' '.join(cmd[1:])}[/cyan]")
    result = subprocess.run(cmd, cwd=path, check=False)

    if result.returncode not in (0, 1):
        console.print(
            f"[red]audit_orphans.py exited with code {result.returncode}[/red]"
        )
        raise typer.Exit(2)

    if result.returncode == 1 and fail_on_orphans:
        raise typer.Exit(1)


@app.command()
def locate(
    path: Path = typer.Option(
        Path.cwd(),
        "--path",
        "-p",
        help="Project root to search.",
    ),
) -> None:
    audit_script = _find_audit_script(path)
    if audit_script is None:
        console.print(f"[red]audit_orphans.py not found under {path}[/red]")
        raise typer.Exit(2)
    sys.stdout.write(str(audit_script))
    sys.stdout.write("\n")


def _self_test() -> None:
    here = Path(__file__).resolve()
    expected = here.parent.parent / "scripts" / "audit_orphans.py"
    if not expected.exists():
        pass


if __name__ == "__main__":
    app()
