"""MCP tools for git metrics collection and analysis.

This module provides FastMCP tools for:
- Collecting git metrics from repositories
- Calculating commit velocity
- Analyzing repository health
- Tracking branch and merge patterns
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from mcp.server import FastMCP
from pydantic import Field, validate_call

from crackerjack.memory.git_metrics_collector import GitMetricsCollector

logger = logging.getLogger(__name__)

mcp = FastMCP("crackerjack-git-metrics")


@mcp.tool()
@validate_call
def collect_git_metrics(
    repo_path: str = Field(
        description="Path to git repository",
        examples=["/Users/les/Projects/mahavishnu"],
    ),
    days_back: int = Field(
        default=30,
        description="Number of days to analyze (default: 30)",
        ge=1,
        le=365,
    ),
) -> dict:
    """Collect comprehensive git metrics for a repository.

    Provides a complete dashboard of git activity including:
    - Commit velocity (commits per hour/day/week)
    - Branch activity (switches, creations, deletions)
    - Merge patterns (conflicts, success rate)
    - Conventional commit compliance

    Args:
        repo_path: Absolute path to git repository
        days_back: Number of days to look back for analysis

    Returns:
        Dict with commit, branch, and merge metrics

    Raises:
        ValueError: If repo_path is not a valid git repository
    """
    try:
        repo = Path(repo_path).resolve()

        # Validate repository exists
        if not (repo / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

        logger.info(f"Collecting git metrics for {repo} (last {days_back} days)")

        # Initialize collector
        collector = GitMetricsCollector(repo)

        # Get velocity dashboard
        dashboard = collector.get_velocity_dashboard(days_back=days_back)

        # Format response
        result = {
            "repository": str(repo),
            "period": {
                "start": dashboard.period_start.isoformat(),
                "end": dashboard.period_end.isoformat(),
                "days": days_back,
            },
            "commits": {
                "total": dashboard.commit_metrics.total_commits,
                "per_hour": round(dashboard.commit_metrics.avg_commits_per_hour, 2),
                "per_day": round(dashboard.commit_metrics.avg_commits_per_day, 2),
                "per_week": round(dashboard.commit_metrics.avg_commits_per_week, 2),
                "conventional_rate": round(
                    dashboard.commit_metrics.conventional_compliance_rate * 100, 1
                ),
                "breaking_changes": dashboard.commit_metrics.breaking_changes,
                "most_active_hour": dashboard.commit_metrics.most_active_hour,
                "most_active_day": dashboard.commit_metrics.most_active_day,
            },
            "branches": {
                "total": dashboard.branch_metrics.total_branches,
                "active": dashboard.branch_metrics.active_branches,
                "switches": dashboard.branch_metrics.branch_switches,
                "created": dashboard.branch_metrics.branches_created,
                "deleted": dashboard.branch_metrics.branches_deleted,
                "most_switched": dashboard.branch_metrics.most_switched_branch,
            },
            "merges": {
                "total": dashboard.merge_metrics.total_merges,
                "rebases": dashboard.merge_metrics.total_rebases,
                "conflicts": dashboard.merge_metrics.total_conflicts,
                "conflict_rate": round(dashboard.merge_metrics.conflict_rate * 100, 1),
                "conflict_files_per_merge": round(
                    dashboard.merge_metrics.avg_files_per_conflict, 1
                ),
                "success_rate": round(dashboard.merge_metrics.merge_success_rate * 100, 1),
                "most_conflicted_files": [
                    {"path": f, "count": c}
                    for f, c in dashboard.merge_metrics.most_conflicted_files[:5]
                ],
            },
            "trend": [
                {"date": d.isoformat(), "commits": c}
                for d, c in dashboard.trend_data
            ],
        }

        # Cleanup
        collector.close()

        logger.info(f"Collected metrics: {dashboard.commit_metrics.total_commits} commits")

        return result

    except Exception as e:
        logger.error(f"Failed to collect git metrics: {e}")
        raise


@mcp.tool()
@validate_call
def get_repository_velocity(
    repo_path: str = Field(
        description="Path to git repository",
        examples=["/Users/les/Projects/mahavishnu"],
    ),
    days_back: int = Field(
        default=30,
        description="Number of days to analyze",
        ge=1,
        le=365,
    ),
) -> float:
    """Get commit velocity for a repository.

    Returns the average number of commits per day over the specified time period.

    Args:
        repo_path: Absolute path to git repository
        days_back: Number of days to analyze

    Returns:
        Commits per day (float)

    Raises:
        ValueError: If repo_path is not a valid git repository
    """
    try:
        repo = Path(repo_path).resolve()

        if not (repo / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

        logger.info(f"Calculating velocity for {repo} (last {days_back} days)")

        collector = GitMetricsCollector(repo)
        metrics = collector.collect_commit_metrics(days_back=days_back)
        collector.close()

        velocity = metrics.avg_commits_per_day
        logger.info(f"Repository velocity: {velocity:.2f} commits/day")

        return round(velocity, 2)

    except Exception as e:
        logger.error(f"Failed to calculate velocity: {e}")
        raise


@mcp.tool()
@validate_call
def get_repository_health(
    repo_path: str = Field(
        description="Path to git repository",
        examples=["/Users/les/Projects/mahavishnu"],
    ),
) -> dict:
    """Get repository health indicators.

    Analyzes repository health based on:
    - Active branches (branches with recent activity)
    - Branch switching frequency (context switching overhead)
    - Merge conflict rate (collaboration friction)
    - Merge success rate

    Args:
        repo_path: Absolute path to git repository

    Returns:
        Dict with health metrics and scores

    Raises:
        ValueError: If repo_path is not a valid git repository
    """
    try:
        repo = Path(repo_path).resolve()

        if not (repo / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

        logger.info(f"Analyzing health for {repo}")

        collector = GitMetricsCollector(repo)

        # Collect metrics
        branch_metrics = collector.collect_branch_activity()
        merge_metrics = collector.collect_merge_patterns()

        collector.close()

        # Calculate health score (0-100)
        # Lower conflict rate = better
        conflict_score = max(0, 100 - (merge_metrics.conflict_rate * 100))

        # Higher merge success = better
        merge_score = merge_metrics.merge_success_rate * 100

        # Active branches = good, too many = bad
        branch_score = min(100, branch_metrics.active_branches * 10)

        # Overall health = average of components
        overall_health = (conflict_score + merge_score + branch_score) / 3

        result = {
            "repository": str(repo),
            "health_score": round(overall_health, 1),
            "branches": {
                "total": branch_metrics.total_branches,
                "active": branch_metrics.active_branches,
                "switches": branch_metrics.branch_switches,
                "score": round(branch_score, 1),
            },
            "merges": {
                "total": merge_metrics.total_merges,
                "conflicts": merge_metrics.total_conflicts,
                "conflict_rate": round(merge_metrics.conflict_rate * 100, 1),
                "success_rate": round(merge_metrics.merge_success_rate * 100, 1),
                "score": round(merge_score, 1),
            },
            "recommendations": _generate_health_recommendations(
                branch_metrics, merge_metrics
            ),
        }

        logger.info(f"Repository health score: {overall_health:.1f}/100")

        return result

    except Exception as e:
        logger.error(f"Failed to analyze health: {e}")
        raise


@mcp.tool()
@validate_call
def get_conventional_compliance(
    repo_path: str = Field(
        description="Path to git repository",
        examples=["/Users/les/Projects/mahavishnu"],
    ),
    days_back: int = Field(
        default=30,
        description="Number of days to analyze",
        ge=1,
        le=365,
    ),
) -> dict:
    """Get conventional commit compliance rate.

    Analyzes commit messages for compliance with Conventional Commits specification:
    https://www.conventionalcommits.org/

    Types: feat, fix, docs, style, refactor, test, chore, perf, ci, build, revert

    Args:
        repo_path: Absolute path to git repository
        days_back: Number of days to analyze

    Returns:
        Dict with compliance rate and breakdown by commit type

    Raises:
        ValueError: If repo_path is not a valid git repository
    """
    try:
        repo = Path(repo_path).resolve()

        if not (repo / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

        logger.info(f"Analyzing conventional compliance for {repo}")

        collector = GitMetricsCollector(repo)
        metrics = collector.collect_commit_metrics(days_back=days_back)
        collector.close()

        result = {
            "repository": str(repo),
            "period_days": days_back,
            "total_commits": metrics.total_commits,
            "conventional_commits": metrics.conventional_commits,
            "compliance_rate": round(metrics.conventional_compliance_rate * 100, 1),
            "breaking_changes": metrics.breaking_changes,
        }

        logger.info(
            f"Conventional compliance: {metrics.conventional_compliance_rate * 100:.1f}%"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to analyze compliance: {e}")
        raise


def _generate_health_recommendations(
    branch_metrics: any,
    merge_metrics: any,
) -> list[str]:
    """Generate actionable health recommendations."""
    recommendations = []

    # High conflict rate
    if merge_metrics.conflict_rate > 0.2:
        recommendations.append(
            f"⚠️  High merge conflict rate ({merge_metrics.conflict_rate * 100:.0f}%). "
            "Consider more frequent merges or better code review practices."
        )

    # Low merge success rate
    if merge_metrics.merge_success_rate < 0.8:
        recommendations.append(
            f"⚠️  Low merge success rate ({merge_metrics.merge_success_rate * 100:.0f}%). "
            "Review branch strategy and integration practices."
        )

    # Too many inactive branches
    inactive = branch_metrics.total_branches - branch_metrics.active_branches
    if inactive > 10:
        recommendations.append(
            f"🧹 {inactive} stale branches detected. "
            "Consider cleaning up old branches."
        )

    # High branch switching
    if branch_metrics.branch_switches > 50:
        recommendations.append(
            f"🔄 High branch switching frequency ({branch_metrics.branch_switches}). "
            "Consider consolidating work to reduce context switching."
        )

    if not recommendations:
        recommendations.append("✅ Repository health looks good!")

    return recommendations


# Export MCP server
__all__ = ["mcp"]
