from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from crackerjack.documentation.docstring_enricher import (
    DocstringEnricher,
    check_docs_quality,
)

app = typer.Typer(
    name="docs", help="Documentation management commands.", no_args_is_help=True
)
console = Console()

_ZENSICAL_TOML_TEMPLATE = """\
[project]
site_name = "{name}"
site_description = "Documentation for {name}"
site_author = ""

[[project.nav]]
Home = "index.md"

[[project.nav]]
"API Reference" = "api/"
"""


def _project_name(path: Path) -> str:
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        import tomllib
        from contextlib import suppress

        with suppress(Exception):
            with pyproject.open("rb") as f:
                return tomllib.load(f).get("project", {}).get("name", path.name)
    return path.name


@app.command()
def init(
    path: Path = typer.Option(Path.cwd(), "--path", help="Repo root to scaffold"),
) -> None:
    toml_path = path / "zensical.toml"
    if toml_path.exists():
        console.print(f"[yellow]zensical.toml already exists at {toml_path}[/yellow]")
        raise typer.Exit(0)
    name = _project_name(path)
    toml_path.write_text(_ZENSICAL_TOML_TEMPLATE.format(name=name), encoding="utf-8")
    console.print(f"[green]Created[/green] {toml_path}")


@app.command()
def build(
    path: Path = typer.Option(
        Path.cwd(), "--path", help="Repo root with zensical.toml"
    ),
) -> None:
    result = subprocess.run(
        ["zensical", "build"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        console.print(f"[red]zensical build failed:[/red]\n{result.stderr}")
        raise typer.Exit(1)
    console.print("[green]Documentation built successfully.[/green]")


@app.command()
def serve(
    path: Path = typer.Option(
        Path.cwd(), "--path", help="Repo root with zensical.toml"
    ),
) -> None:
    result = subprocess.run(
        ["zensical", "serve"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        console.print(f"[red]zensical serve failed:[/red]\n{result.stderr}")
        raise typer.Exit(1)
    console.print("[green]Documentation server stopped.[/green]")


@app.command()
def deploy(
    path: Path = typer.Option(
        Path.cwd(), "--path", help="Repo root with zensical.toml"
    ),
) -> None:
    result = subprocess.run(
        ["zensical", "deploy"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        console.print(f"[red]zensical deploy failed:[/red]\n{result.stderr}")
        raise typer.Exit(1)
    console.print("[green]Documentation deployed.[/green]")


@app.command()
def check(
    path: Path = typer.Option(Path.cwd(), "--path", help="Repo root to check"),
) -> None:
    result = check_docs_quality(path)
    pct = result.coverage_pct * 100
    console.print(
        f"Docstring coverage: {result.documented_apis}/{result.total_public_apis} "
        f"({pct:.1f}%)"
    )
    if not result.zensical_toml_present:
        console.print("[red]zensical.toml not found — run: crackerjack docs init[/red]")
        raise typer.Exit(1)
    console.print("[green]Docs check passed.[/green]")


@app.command(name="ai-fix")
def ai_fix(
    path: Path = typer.Option(Path.cwd(), "--path", help="Repo root to enrich"),
) -> None:
    enricher = DocstringEnricher()
    py_files = [f for f in path.rglob("*.py") if "__pycache__" not in str(f)]

    total_enriched = 0
    report_only: list[str] = []

    async def run() -> None:
        nonlocal total_enriched
        for py_file in py_files:
            result = await enricher.enrich(py_file)
            total_enriched += result.enriched
            report_only.extend(result.report_only)

    asyncio.run(run())

    console.print(f"[green]Enriched {total_enriched} docstrings.[/green]")
    if report_only:
        console.print(
            f"[yellow]Low-confidence (report only): {', '.join(report_only)}[/yellow]"
        )
