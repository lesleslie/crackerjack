#!/usr/bin/env python3
"""Demo script for GitMetricsCollector functionality.

This script demonstrates:
- Parsing git log output
- Detecting conventional commits
- Calculating commit velocity
- Tracking branch activity
- Merge conflict detection
"""

from pathlib import Path
from datetime import datetime, timedelta

from crackerjack.memory import GitMetricsCollector


def main():
    """Run git metrics collection demo."""
    # Get repository path (current directory or specified)
    import sys

    if len(sys.argv) > 1:
        repo_path = Path(sys.argv[1])
    else:
        repo_path = Path.cwd()

    print(f"📊 Collecting Git metrics from: {repo_path}")
    print()

    try:
        # Initialize collector
        collector = GitMetricsCollector(repo_path)

        # Collect commit metrics (last 30 days)
        print("🔍 Collecting commit metrics...")
        commit_metrics = collector.collect_commit_metrics()

        print(f"  Total commits: {commit_metrics.total_commits}")
        print(f"  Conventional commits: {commit_metrics.conventional_commits}")
        print(f"  Conventional compliance: {commit_metrics.conventional_compliance_rate:.1%}")
        print(f"  Breaking changes: {commit_metrics.breaking_changes}")
        print(f"  Commits per day: {commit_metrics.avg_commits_per_day:.1f}")
        print(f"  Most active hour: {commit_metrics.most_active_hour}:00")
        print()

        # Collect branch metrics (last 7 days)
        print("🌿 Collecting branch metrics...")
        branch_metrics = collector.collect_branch_activity()

        print(f"  Total branches: {branch_metrics.total_branches}")
        print(f"  Active branches: {branch_metrics.active_branches}")
        print(f"  Branch switches: {branch_metrics.branch_switches}")
        print(f"  Most switched branch: {branch_metrics.most_switched_branch or 'N/A'}")
        print()

        # Collect merge metrics (last 30 days)
        print("🔄 Collecting merge metrics...")
        merge_metrics = collector.collect_merge_patterns()

        print(f"  Total merges: {merge_metrics.total_merges}")
        print(f"  Total rebases: {merge_metrics.total_rebases}")
        print(f"  Total conflicts: {merge_metrics.total_conflicts}")
        print(f"  Conflict rate: {merge_metrics.conflict_rate:.1%}")
        print(f"  Merge success rate: {merge_metrics.merge_success_rate:.1%}")

        if merge_metrics.most_conflicted_files:
            print(f"  Most conflicted files:")
            for file_path, count in merge_metrics.most_conflicted_files[:5]:
                print(f"    - {file_path}: {count} conflicts")
        print()

        # Get velocity dashboard
        print("📈 Velocity dashboard (last 30 days)...")
        dashboard = collector.get_velocity_dashboard(days_back=30)

        print(f"  Period: {dashboard.period_start.date()} to {dashboard.period_end.date()}")
        print(f"  Trend data points: {len(dashboard.trend_data)}")

        if dashboard.trend_data:
            # Show last 7 days
            print(f"  Last 7 days activity:")
            for date, count in dashboard.trend_data[-7:]:
                print(f"    {date.date()}: {count} commits")
        print()

        # Test conventional commit parser
        print("🔤 Testing conventional commit parser...")
        from crackerjack.memory.git_metrics_collector import _ConventionalCommitParser

        test_messages = [
            "feat: add new feature",
            "fix(auth): resolve login issue",
            "feat(api)!: breaking API change",
            "random non-conventional message",
        ]

        for msg in test_messages:
            is_conv, type_, scope, breaking = _ConventionalCommitParser.parse(msg)
            status = "✅" if is_conv else "❌"
            print(f"  {status} '{msg}'")
            if is_conv:
                print(f"     Type: {type_}, Scope: {scope or 'N/A'}, Breaking: {breaking}")
        print()

        # Close storage
        collector.close()
        print("✅ Demo complete!")

    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Make sure you're running this from a git repository.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
