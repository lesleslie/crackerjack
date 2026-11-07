"""``crackerjack run-state`` - query recorded per-test run results.

The run-state store records what every test run observed, keyed by
``(repo, commit_sha, worktree)``. This command surfaces it:

- ``run-state show`` prints the per-test status recorded for a commit.
- ``run-state diff`` prints the tests whose status differs between two
  commits - the "did my change break anything" question, answered without
  running anything.

Both commands say so plainly when a commit has no recorded run. An empty
table that reads like a clean result is worse than no output at all.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape as escape_markup

from crackerjack.config.settings import RunStateSettings
from crackerjack.services.testing.run_state_store import RunStateStore

app = typer.Typer(
    name="run-state",
    help=(
        "Query recorded per-test run results: show the status recorded for "
        "a commit, or diff two commits."
    ),
    no_args_is_help=True,
)
console = Console()


def _safe(value: object) -> str:
    """Render a repository-controlled value for terminal output.

    Node ids come from the repository's own file names and the package
    name from its ``pyproject.toml``, so neither is trusted. Rich reads
    a bracketed sequence as a style tag, and a raw escape sequence would
    be handed straight to the terminal. Control characters are dropped
    and the markup is escaped, so the value is printed as text.
    """
    text = "".join(character for character in str(value) if character.isprintable())
    return escape_markup(text)


def _resolve_db_path(db_path: Path | None) -> Path:
    if db_path is not None:
        return Path(db_path)
    return RunStateSettings().storage_path


def _detect_head(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _detect_project_name(cwd: Path) -> str:
    from crackerjack.managers.test_command_builder import TestCommandBuilder

    return TestCommandBuilder(pkg_path=cwd).get_project_name()


def _find_run(
    store: RunStateStore,
    repo: str,
    commit_sha: str,
    worktree: str,
) -> dict[str, object] | None:
    run = store.get_run(repo=repo, commit_sha=commit_sha, worktree=worktree)
    if run is None:
        run = store.get_run(repo=repo, commit_sha=commit_sha)
    return run


def _format_duration(duration: object) -> str:
    if isinstance(duration, (int, float)):
        return f"{float(duration):.3f}s"
    return "-"


@app.command()
def show(
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Project name (default: the current project's package name).",
    ),
    commit: str | None = typer.Option(
        None,
        "--commit",
        help="Commit to query (default: HEAD).",
    ),
    worktree: str | None = typer.Option(
        None,
        "--worktree",
        help="Worktree path (default: the current directory).",
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db-path",
        help="Run-state database (default: crackerjack's XDG data directory).",
    ),
) -> None:
    """Show the per-test status recorded for a commit."""
    cwd = Path.cwd()
    store = RunStateStore(_resolve_db_path(db_path))
    repo_name = repo or _detect_project_name(cwd)
    commit_sha = commit or _detect_head(cwd)
    worktree_path = str(worktree) if worktree is not None else str(cwd)

    run = _find_run(store, repo_name, commit_sha, worktree_path)
    if run is None:
        console.print(
            f"[yellow]No recorded run for {_safe(repo_name)}@{_safe(commit_sha)}[/yellow]"
        )
        return

    console.print(
        f"[bold]{_safe(repo_name)}[/bold] @ [cyan]{_safe(commit_sha)}[/cyan] "
        f"(worktree {_safe(run['worktree'])})",
        soft_wrap=True,
    )
    console.print(
        f"{run['passed']} passed, {run['failed']} failed, "
        f"{run['skipped']} skipped of {run['total']} tests "
        f"({_safe(run['selection_mode'])} selection)",
        soft_wrap=True,
    )
    for result in store.get_test_results(str(run["id"])):
        console.print(
            f"  {_safe(result['node_id'])}  {_safe(result['status'])}  "
            f"{_format_duration(result.get('duration'))}",
            soft_wrap=True,
        )


@app.command()
def stats(
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Project name (default: every project).",
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db-path",
        help="Run-state database (default: crackerjack's XDG data directory).",
    ),
) -> None:
    """Show how the recorded runs were selected.

    Every run records the selection mode it used, so this answers "how
    often was the incremental path taken?" The coverage ratchet skips
    exactly when a run was incremental, so the incremental count is also
    the number of times the ratchet was skipped.
    """
    store = RunStateStore(_resolve_db_path(db_path))

    summary = store.summarize(repo=repo)

    if summary["runs"] == 0:
        console.print("[yellow]No recorded runs[/yellow]")
        return

    scope = _safe(repo) if repo else "every project"
    console.print(
        f"[bold]{summary['runs']}[/bold] recorded runs for {scope}",
        soft_wrap=True,
    )
    console.print(
        f"  incremental: {summary['incremental']}  "
        f"(the coverage ratchet was skipped this many times)",
        soft_wrap=True,
    )
    console.print(f"  full: {summary['full']}", soft_wrap=True)
    if summary["other"]:
        console.print(f"  other: {summary['other']}", soft_wrap=True)
    console.print(
        f"  passed: {summary['passed_runs']}  failed: {summary['failed_runs']}",
        soft_wrap=True,
    )


@app.command()
def diff(
    base: str = typer.Option(
        ...,
        "--base",
        help="Base commit to compare against.",
    ),
    commit: str | None = typer.Option(
        None,
        "--commit",
        help="Commit to compare (default: HEAD).",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Project name (default: the current project's package name).",
    ),
    worktree: str | None = typer.Option(
        None,
        "--worktree",
        help="Worktree path (default: the current directory).",
    ),
    db_path: Path | None = typer.Option(
        None,
        "--db-path",
        help="Run-state database (default: crackerjack's XDG data directory).",
    ),
) -> None:
    """Show tests whose status differs between two commits."""
    cwd = Path.cwd()
    store = RunStateStore(_resolve_db_path(db_path))
    repo_name = repo or _detect_project_name(cwd)
    commit_sha = commit or _detect_head(cwd)
    worktree_path = str(worktree) if worktree is not None else str(cwd)

    base_run = _find_run(store, repo_name, base, worktree_path)
    if base_run is None:
        console.print(
            f"[yellow]No recorded run for {_safe(repo_name)}@{_safe(base)}[/yellow]"
        )
        return

    head_run = _find_run(store, repo_name, commit_sha, worktree_path)
    if head_run is None:
        console.print(
            f"[yellow]No recorded run for {_safe(repo_name)}@{_safe(commit_sha)}[/yellow]"
        )
        return

    base_status = store.get_status_map(str(base_run["id"]))
    head_status = store.get_status_map(str(head_run["id"]))

    changes: list[tuple[str, str, str]] = []
    for node_id in sorted(set(base_status) | set(head_status)):
        before = base_status.get(node_id, "absent")
        after = head_status.get(node_id, "absent")
        if before != after:
            changes.append((node_id, before, after))

    if not changes:
        console.print(
            f"No status changes between {_safe(base)} and {_safe(commit_sha)}."
        )
        return

    console.print(
        f"Status changes between {_safe(base)} and {_safe(commit_sha)}:", soft_wrap=True
    )
    for node_id, before, after in changes:
        console.print(
            f"  {_safe(node_id)}  {_safe(before)} -> {_safe(after)}", soft_wrap=True
        )
