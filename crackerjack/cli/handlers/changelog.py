"""CLI handlers for changelog generation and version analysis.

This module contains handlers for:
- Changelog generation from git commits
- Changelog dry-run previews
- Automated version analysis and recommendations
- Debug/verbose flag setup
"""

import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from crackerjack.services.changelog_automation import ChangelogGenerator
    from crackerjack.services.git import GitService


def setup_changelog_services() -> dict[str, t.Any]:
    """Set up changelog generation services (git, generator, path)."""
    from crackerjack.services.changelog_automation import ChangelogGenerator
    from crackerjack.services.git import GitService

    pkg_path = Path()
    git_service = GitService()
    changelog_generator = ChangelogGenerator()

    return {
        "pkg_path": pkg_path,
        "git_service": git_service,
        "generator": changelog_generator,
    }


def handle_changelog_dry_run(
    generator: "ChangelogGenerator",
    changelog_since: str | None,
    options: t.Any,
) -> bool:
    """Handle changelog dry-run (preview without writing)."""
    console.print("🔍 [bold blue]Previewing changelog generation...[/bold blue]")
    entries = generator.generate_changelog_entries(changelog_since)
    if entries:
        generator._display_changelog_preview(entries)
        console.print("✅ [bold green]Changelog preview completed![/bold green]")
    else:
        console.print("⚠️ No new changelog entries to generate")

    return should_continue_after_changelog(options)


def handle_changelog_generation(
    services: dict[str, t.Any],
    changelog_path: Path,
    changelog_version: str | None,
    changelog_since: str | None,
    options: t.Any,
) -> bool:
    """Handle changelog generation and write to file."""
    console.print("📝 [bold blue]Generating changelog...[/bold blue]")

    version = determine_changelog_version(
        services["git_service"], changelog_version, changelog_since, options
    )

    success = services["generator"].generate_changelog_from_commits(
        changelog_path=changelog_path,
        version=version,
        since_version=changelog_since,
    )

    if success:
        console.print(
            f"✅ [bold green]Changelog updated for version {version}![/bold green]"
        )
        return should_continue_after_changelog(options)
    console.print("❌ [bold red]Changelog generation failed![/bold red]")
    return False


def determine_changelog_version(
    git_service: "GitService",
    changelog_version: str | None,
    changelog_since: str | None,
    options: t.Any,
) -> str:
    """Determine changelog version (auto-detect via AI or use provided version)."""
    if getattr(options, "auto_version", False) and not changelog_version:
        try:
            import asyncio

            from crackerjack.services.version_analyzer import VersionAnalyzer

            version_analyzer = VersionAnalyzer(git_service)
            console.print(
                "[cyan]🔍[/cyan] Analyzing version changes for intelligent changelog..."
            )

            recommendation = asyncio.run(
                version_analyzer.recommend_version_bump(changelog_since)
            )
            version = recommendation.recommended_version
            console.print(f"[green]✨[/green] Using AI-recommended version: {version}")
            return version
        except Exception as e:
            console.print(f"[yellow]⚠️[/yellow] Version analysis failed: {e}")
            return changelog_version or "Unreleased"

    return changelog_version or "Unreleased"


def should_continue_after_changelog(options: t.Any) -> bool:
    """Check if workflow should continue after changelog commands."""
    return any(
        [
            options.run_tests,
            options.strip_code,
            options.all,
            options.publish,
            options.comp,
        ]
    )


def handle_changelog_commands(
    generate_changelog: bool,
    changelog_dry_run: bool,
    changelog_version: str | None,
    changelog_since: str | None,
    options: t.Any,
) -> bool:
    """Handle all changelog-related commands (generation, dry-run, versioning).

    Args:
        generate_changelog: Whether to generate changelog
        changelog_dry_run: Whether to preview changelog without writing
        changelog_version: Explicit version to use (or None for auto/unreleased)
        changelog_since: Git reference to generate changelog since
        options: CLI options object

    Returns:
        True if execution should continue to other workflows
    """
    if not (generate_changelog or changelog_dry_run):
        return True

    services = setup_changelog_services()
    changelog_path = services["pkg_path"] / "CHANGELOG.md"

    if changelog_dry_run:
        return handle_changelog_dry_run(services["generator"], changelog_since, options)

    if generate_changelog:
        return handle_changelog_generation(
            services, changelog_path, changelog_version, changelog_since, options
        )

    return should_continue_after_changelog(options)


# === Version Analysis Handler ===
def handle_version_analysis(
    auto_version: bool,
    version_since: str | None,
    accept_version: bool,
    options: t.Any,
) -> bool:
    """Handle automated version analysis and recommendations.

    Args:
        auto_version: Whether to perform automated version analysis
        version_since: Git reference to analyze changes since
        accept_version: Whether to auto-accept the recommendation
        options: CLI options object
        console: Rich console for output

    Returns:
        True if execution should continue to other workflows
    """
    if not auto_version:
        return True

    from rich.prompt import Confirm

    from crackerjack.services.git import GitService
    from crackerjack.services.version_analyzer import VersionAnalyzer

    Path()
    git_service = GitService()
    version_analyzer = VersionAnalyzer(git_service)

    try:
        import asyncio

        recommendation = asyncio.run(
            version_analyzer.recommend_version_bump(version_since)
        )
        version_analyzer.display_recommendation(recommendation)

        if accept_version or Confirm.ask(
            f"\nAccept recommendation ({recommendation.bump_type.value})",
            default=True,
        ):
            console.print(
                f"[green]✅ Version bump accepted: {recommendation.current_version} → {recommendation.recommended_version}[/green]"
            )

        else:
            console.print("[yellow]❌ Version bump declined[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Version analysis failed: {e}[/red]")

    return any(
        [
            options.run_tests,
            options.strip_code,
            options.all,
            options.publish,
            options.comp,
        ]
    )


# === Debug/Verbose Setup ===


def setup_debug_and_verbose_flags(
    ai_fix: bool, ai_debug: bool, debug: bool, verbose: bool, options: t.Any
) -> tuple[bool, bool]:
    """Set up debug and verbose flags for AI and general operations.

    Args:
        ai_fix: Whether AI fixing is enabled
        ai_debug: Whether AI debug mode is enabled
        debug: Whether general debug mode is enabled
        verbose: Whether verbose output is enabled
        options: CLI options object to update

    Returns:
        Tuple of (ai_fix, verbose) flags after processing
    """
    if ai_debug:
        ai_fix = True
        verbose = True
        options.verbose = True
        options.ai_debug = True  # Set ai_debug on options for downstream checks

    if debug:
        verbose = True
        options.verbose = True

    # Set up structured logging for AI-related operations if needed
    if ai_fix or ai_debug:
        from crackerjack.services.logging import setup_structured_logging

        setup_structured_logging(level="DEBUG", json_output=True)

    return ai_fix, verbose
