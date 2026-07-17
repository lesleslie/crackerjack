from __future__ import annotations

import asyncio
import json
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


from crackerjack.services.frontmatter_validator import (
    FrontmatterValidator,
    FrontmatterValidationError,
)


@app.command()
def validate(
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors."),
    store: str | None = typer.Option(
        None, "--store", help="Limit scan to a single store (e.g. docs/plans/)."
    ),
    validate_links: bool = typer.Option(
        False, "--validate-links", help="Also check cross-references."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of human-readable."),
    pkg_path: Path = typer.Option(Path.cwd(), "--path", help="Repo root."),
) -> None:
    """Validate YAML frontmatter on docs/, .claude/decisions/, etc."""
    validator = FrontmatterValidator(pkg_path=pkg_path)
    try:
        result = validator.validate(
            strict=strict,
            allow_nonstandard=True,
            validate_links=validate_links,
            store=store,
        )
    except FrontmatterValidationError as exc:
        if json_output:
            payload = exc.result.__dict__ if exc.result is not None else {
                "success": False, "reason": exc.reason,
            }
            console.print(json.dumps(payload, indent=2))
        else:
            console.print(f"[red]validator failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    if json_output:
        payload = {
            "success": result.success,
            "files_scanned": result.files_scanned,
            "errors": [e.__dict__ for e in result.errors],
            "warnings": [w.__dict__ for w in result.warnings],
            "duration_ms": result.duration_ms,
        }
        console.print(json.dumps(payload, indent=2))
    else:
        status = "[green]OK[/green]" if result.success else "[yellow]WARN[/yellow]"
        console.print(
            f"{status} {result.files_scanned} files scanned: "
            f"{result.error_count} errors, {result.warning_count} warnings "
            f"({result.duration_ms} ms)"
        )
        for issue in result.errors:
            console.print(f"  [red]ERROR[/red] {issue.file}:{issue.line} {issue.code}: {issue.message}")
        for issue in result.warnings:
            console.print(f"  [yellow]WARN[/yellow] {issue.file}:{issue.line} {issue.code}: {issue.message}")

    if not result.success or (strict and result.warning_count > 0):
        raise typer.Exit(1)
