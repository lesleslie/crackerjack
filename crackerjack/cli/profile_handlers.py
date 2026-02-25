import logging
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from crackerjack.config.profile_loader import (
    get_profile_loader,
)

logger = logging.getLogger(__name__)
console = Console()


def list_profiles_command() -> None:
    loader = get_profile_loader()
    profiles = loader.list_profiles()

    if not profiles:
        console.print("[yellow]No profiles found[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Available Profiles")
    table.add_column("Profile", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Execution Time", style="green")
    table.add_column("Default", style="yellow")

    default_profile = loader.get_default_profile()

    for profile_name in profiles:
        try:
            metadata = loader.get_profile_metadata(profile_name)

            is_default = "✓" if profile_name == default_profile else ""
            table.add_row(
                profile_name,
                metadata.description,
                metadata.execution_time,
                is_default,
            )
        except Exception as e:
            logger.warning(f"Failed to load profile {profile_name}: {e}")
            table.add_row(profile_name, "[red]Error loading profile[/red]", "-", "")

    console.print(table)


def show_profile_command(profile_name: str) -> None:
    loader = get_profile_loader()

    if not loader.profile_exists(profile_name):
        console.print(f"[red]Profile not found: {profile_name}[/red]")
        console.print(f"\nAvailable profiles: {', '.join(loader.list_profiles())}")
        raise typer.Exit(1)

    try:
        config = loader.load_profile(profile_name)
        metadata = config.profile

        console.print(f"\n[bold cyan]Profile: {metadata.name}[/bold cyan]")
        console.print(f"[dim]{metadata.description}[/dim]")
        console.print(f"[green]Execution Time: {metadata.execution_time}[/green]")

        console.print("\n[bold]Enabled Checks:[/bold]")
        if config.checks.get("enabled"):
            for check in config.checks["enabled"]:
                console.print(f"  [green]✓[/green] {check}")
        else:
            console.print("  [dim]None[/dim]")

        if config.checks.get("disabled"):
            console.print("\n[bold]Disabled Checks:[/bold]")
            for check in config.checks["disabled"]:
                console.print(f"  [red]✗[/red] {check}")

        console.print("\n[bold]Quality Gates:[/bold]")
        gates = config.quality_gates
        console.print(
            f"  Fail on Ruff errors: [green]{gates.fail_on_ruff_errors}[/green]"
        )
        console.print(
            f"  Fail on test errors: [green]{gates.fail_on_test_errors}[/green]"
        )
        console.print(f"  Fail on coverage: [green]{gates.fail_on_coverage}[/green]")
        if gates.coverage_threshold:
            console.print(
                f"  Coverage threshold: [cyan]{gates.coverage_threshold}%[/cyan]"
            )
        console.print(
            f"  Fail on complexity: [green]{gates.fail_on_complexity}[/green]"
        )

        console.print("\n[bold]Testing:[/bold]")
        console.print(f"  Enabled: [green]{config.testing.enabled}[/green]")
        if config.testing.enabled:
            console.print(f"  Coverage: [green]{config.testing.coverage}[/green]")
            console.print(f"  Parallel: [green]{config.testing.parallel}[/green]")
            console.print(f"  Incremental: [green]{config.testing.incremental}[/green]")
            console.print(f"  Timeout: [cyan]{config.testing.timeout}s[/cyan]")

        console.print("\n[bold]Performance:[/bold]")
        console.print(
            f"  Parallel: [green]{config.performance.parallel_execution}[/green]"
        )
        console.print(f"  Cache: [green]{config.performance.cache_enabled}[/green]")
        console.print(f"  Timeout: [cyan]{config.performance.timeout}s[/cyan]")

    except Exception as e:
        console.print(f"[red]Error loading profile: {e}[/red]")
        raise typer.Exit(1)


def compare_profiles_command(profile1: str, profile2: str) -> None:
    loader = get_profile_loader()

    for profile_name in (profile1, profile2):
        if not loader.profile_exists(profile_name):
            console.print(f"[red]Profile not found: {profile_name}[/red]")
            raise typer.Exit(1)

    try:
        comparison = loader.compare_profiles(profile1, profile2)

        console.print(f"\n[bold]Comparing: {profile1} vs {profile2}[/bold]\n")

        console.print("[bold]Testing:[/bold]")
        for key, values in comparison["testing"].items():
            val1 = values[profile1]
            val2 = values[profile2]
            if val1 != val2:
                console.print(
                    f"  {key}: [cyan]{profile1}={val1}[/cyan] vs [cyan]{profile2}={val2}[/cyan]"
                )

        console.print("\n[bold]Quality Gates:[/bold]")
        for key, values in comparison["quality_gates"].items():
            val1 = values[profile1]
            val2 = values[profile2]
            if val1 != val2:
                console.print(
                    f"  {key}: [cyan]{profile1}={val1}[/cyan] vs [cyan]{profile2}={val2}[/cyan]"
                )

    except Exception as e:
        console.print(f"[red]Error comparing profiles: {e}[/red]")
        raise typer.Exit(1)


def apply_profile_to_options(profile_name: str, options: Any) -> Any:
    loader = get_profile_loader()

    if not loader.profile_exists(profile_name):
        console.print(f"[red]Profile not found: {profile_name}[/red]")
        console.print(f"\nAvailable profiles: {', '.join(loader.list_profiles())}")
        raise typer.Exit(1)

    try:
        config = loader.load_profile(profile_name)

        options.run_tests = config.testing.enabled
        options.coverage = config.testing.coverage
        options.test_timeout = config.testing.timeout
        options.benchmark = config.testing.benchmark

        if config.testing.parallel:
            if config.testing.auto_detect_workers:
                options.test_workers = 0
            else:
                options.test_workers = config.testing.max_workers

        options.incremental_tests = config.testing.incremental

        options.verbose = config.output.verbose
        if options.show_progress is None:
            options.show_progress = config.output.show_progress

        options.cleanup_docs = config.documentation.get("cleanup", False)
        if config.documentation.get("backup_before_cleanup", False):
            pass

        options.commit = config.git.get("commit", False)
        options.create_pr = config.git.get("create_pr", False)

        logger.info(f"Applied profile: {profile_name}")
        if options.verbose:
            console.print(
                f"[dim]Applied profile: {profile_name} ({config.profile.description})[/dim]"
            )

        return options

    except Exception as e:
        console.print(f"[red]Error applying profile: {e}[/red]")
        logger.error(f"Failed to apply profile {profile_name}: {e}")
        raise typer.Exit(1)


def validate_profile_option(profile_name: str | None) -> str | None:
    if profile_name is None:
        return None

    loader = get_profile_loader()

    if not loader.profile_exists(profile_name):
        console.print(f"[red]Invalid profile: {profile_name}[/red]")
        console.print(f"\nAvailable profiles: {', '.join(loader.list_profiles())}")
        console.print("\nUse [cyan]crackerjack profile list[/cyan] to see all profiles")
        raise typer.Exit(1)

    return profile_name


def get_profile_recommendation(
    changed_files: int,
    time_constraint: str | None = None,
    ci_environment: bool = False,
) -> str:

    if time_constraint == "quick":
        return "quick"
    if time_constraint == "standard":
        return "standard"

    if ci_environment:
        return "comprehensive"

    if changed_files < 5:
        return "quick"

    if changed_files < 20:
        return "standard"

    return "comprehensive"


__all__ = [
    "list_profiles_command",
    "show_profile_command",
    "compare_profiles_command",
    "apply_profile_to_options",
    "validate_profile_option",
    "get_profile_recommendation",
]
