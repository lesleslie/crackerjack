#!/usr/bin/env python3
"""Test script for version analyzer CLI functionality."""

import asyncio
import sys
from pathlib import Path

# Add the project to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.prompt import Confirm

from crackerjack.services.git import GitService
from crackerjack.services.version_analyzer import VersionAnalyzer


async def main() -> None:
    """Test version analyzer with CLI-like interface."""
    console = Console()

    console.print("[bold blue]🔍 Version Bump Analyzer Test[/bold blue]\n")

    # Initialize services
    pkg_path = Path(".")
    git_service = GitService(console, pkg_path)
    version_analyzer = VersionAnalyzer(console, git_service)

    # Test different scenarios
    test_cases = [
        ("v0.31.8", "Since v0.31.8 (recent changes)"),
        ("v0.31.0", "Since v0.31.0 (more changes)"),
        (None, "Since last tag (default)"),
    ]

    for since_version, description in test_cases:
        console.print(f"[cyan]📋 Test Case: {description}[/cyan]")

        try:
            recommendation = await version_analyzer.recommend_version_bump(
                since_version
            )
            version_analyzer.display_recommendation(recommendation)

            # Simulate interactive confirmation
            if not Confirm.ask(
                f"\nAccept recommendation ({recommendation.bump_type.value})",
                default=True,
            ):
                console.print("[yellow]❌ Version bump declined[/yellow]")
            else:
                console.print(
                    f"[green]✅ Version bump accepted: {recommendation.current_version} → {recommendation.recommended_version}[/green]"
                )

        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")

        console.print("\n" + "─" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
