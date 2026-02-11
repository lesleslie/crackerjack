#!/usr/bin/env python3

import asyncio
from pathlib import Path

from crackerjack.integration.mahavishnu_integration import (
    create_mahavishnu_aggregator,
    MahavishnuConfig,
)


async def main():
    print("=" * 60)
    print("Mahavishnu Cross-Project Git Analytics Demo")
    print("=" * 60)


    config = MahavishnuConfig(
        db_path=Path(".crackerjack/mahavishnu.db"),
        websocket_enabled=False,
    )

    aggregator = create_mahavishnu_aggregator(config=config)
    await aggregator.initialize()

    print("\n✅ Mahavishnu aggregator initialized")


    print("\n" + "-" * 60)
    print("Repository Health Analysis")
    print("-" * 60)

    repo_path = Path.cwd()
    print(f"\nAnalyzing: {repo_path}")

    health = await aggregator.get_repository_health(repo_path)

    print(f"\n📊 Repository: {health.repository_name}")
    print(f"   Health Score: {health.health_score:.1f}/100")
    print(f"   Risk Level: {health.risk_level}")
    print(f"   Stale Branches: {len(health.stale_branches)}")
    print(f"   Unmerged PRs: {health.unmerged_prs}")
    print(f"   Large Files: {len(health.large_files)}")
    print(f"   Last Activity: {health.last_activity}")

    print("\n💡 Recommendations:")
    for i, rec in enumerate(health.recommendations, 1):
        print(f"   {i}. {rec}")


    print("\n" + "-" * 60)
    print("Cross-Project Pattern Analysis")
    print("-" * 60)

    patterns = await aggregator.get_cross_project_patterns(
        project_paths=[repo_path],
        days_back=90,
    )

    print(f"\n🔍 Detected {len(patterns)} patterns:")

    for i, pattern in enumerate(patterns, 1):
        print(f"\n   Pattern {i}: {pattern.pattern_type}")
        print(f"   Severity: {pattern.severity}")
        print(f"   Description: {pattern.description}")
        print(f"   Recommendation: {pattern.recommendation}")


    print("\n" + "-" * 60)
    print("Cross-Project Dashboard")
    print("-" * 60)

    dashboard = await aggregator.get_cross_project_git_dashboard(
        project_paths=[repo_path],
        days_back=30,
    )

    print(f"\n📈 Dashboard Summary:")
    print(f"   Total Repositories: {dashboard.total_repositories}")
    print(f"   Period: {dashboard.period_days} days")
    print(f"   Generated: {dashboard.generated_at}")

    print(f"\n📊 Aggregate Metrics:")
    print(f"   Total Commits: {dashboard.aggregate_metrics['total_commits']}")
    print(f"   Avg Commits/Day: {dashboard.aggregate_metrics['avg_commits_per_day']:.2f}")
    print(f"   Avg Health Score: {dashboard.aggregate_metrics['avg_health_score']:.1f}")

    print(f"\n🏆 Top Performers:")
    for performer in dashboard.top_performers:
        print(f"   - {Path(performer).name}")

    print(f"\n⚠️  Needs Attention:")
    for attention in dashboard.needs_attention:
        print(f"   - {Path(attention).name}")

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
