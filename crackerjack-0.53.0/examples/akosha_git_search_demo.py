#!/usr/bin/env python3
"""Example demonstrating Akosha git semantic search.

This example shows how to:
1. Index a git repository for semantic search
2. Query commits using natural language
3. Get velocity trends with semantic queries

Usage:
    python examples/akosha_git_search_demo.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from crackerjack.integration import create_akosha_git_integration


async def main() -> None:
    """Demonstrate Akosha git semantic search."""

    # Get current repository
    repo_path = Path.cwd()

    print(f"🔍 Setting up Akosha git integration for {repo_path}")
    print()

    # Create integration (auto-detects Akosha availability)
    integration = create_akosha_git_integration(
        repo_path=repo_path,
        backend="auto",
    )

    # Initialize
    await integration.initialize()
    print("✅ Integration initialized")
    print()

    # Index repository history
    print("📊 Indexing repository history (last 30 days)...")
    indexed_count = await integration.index_repository_history(days_back=30)
    print(f"✅ Indexed {indexed_count} commits")
    print()

    # Example 1: Search for feature commits
    print("🔍 Searching for 'feature additions':")
    print("-" * 60)

    results = await integration.search_git_history(
        query="new feature additions",
        limit=5,
    )

    for event in results[:5]:
        print(f"  {event.timestamp.strftime('%Y-%m-%d')}: {event.message[:60]}...")

    if not results:
        print("  No results found (Akosha may not be available)")

    print()

    # Example 2: Search for bug fixes
    print("🔍 Searching for 'bug fixes':")
    print("-" * 60)

    results = await integration.search_git_history(
        query="bug fixes and error handling",
        limit=5,
    )

    for event in results[:5]:
        print(f"  {event.timestamp.strftime('%Y-%m-%d')}: {event.message[:60]}...")

    if not results:
        print("  No results found (Akosha may not be available)")

    print()

    # Example 3: Get velocity trends
    print("📈 Querying velocity trends:")
    print("-" * 60)

    trends = await integration.get_velocity_trends(
        query="repository development velocity",
    )

    for metrics in trends[:3]:
        print(f"  Repository: {metrics.repository_path}")
        print(f"  Velocity: {metrics.avg_commits_per_day:.1f} commits/day")
        print(f"  Compliance: {metrics.conventional_compliance_rate:.1%}")
        print(f"  Conflicts: {metrics.merge_conflict_rate:.1%}")
        print()

    if not trends:
        print("  No trends found (Akosha may not be available)")

    print()
    print("✅ Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
