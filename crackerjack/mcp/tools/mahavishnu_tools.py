from __future__ import annotations

import logging
from pathlib import Path

from mcp.server import FastMCP
from pydantic import Field, validate_call

from crackerjack.integration.mahavishnu_integration import create_mahavishnu_aggregator

logger = logging.getLogger(__name__)

mcp = FastMCP("crackerjack-mahavishnu")


_aggregator = None


def _get_aggregator():
    global _aggregator
    if _aggregator is None:
        from crackerjack.integration.mahavishnu_integration import MahavishnuConfig

        config = MahavishnuConfig(
            db_path=Path(".crackerjack/mahavishnu.db"),
            websocket_enabled=False,
        )
        _aggregator = create_mahavishnu_aggregator(config=config)
    return _aggregator


@mcp.tool()
@validate_call
def get_cross_project_git_dashboard(
    project_paths: list[str] = Field(
        description="List of absolute paths to git repositories",
        examples=[
            ["/Users/les/Projects/crackerjack", "/Users/les/Projects/mcp-common"],
        ],
    ),
    days_back: int = Field(
        default=30,
        description="Number of days to analyze for velocity metrics",
        ge=1,
        le=365,
    ),
) -> dict:
    try:
        aggregator = _get_aggregator()

        logger.info(
            f"Generating cross-project dashboard for {len(project_paths)} repositories "
            f"(last {days_back} days)"
        )

        project_paths_str = [p for p in project_paths]

        import asyncio

        dashboard = asyncio.run(
            aggregator.get_cross_project_git_dashboard(project_paths_str, days_back)
        )

        result = {
            "summary": {
                "total_repositories": dashboard.total_repositories,
                "period_days": dashboard.period_days,
                "generated_at": dashboard.generated_at.isoformat(),
            },
            "aggregate_metrics": {
                "total_commits": dashboard.aggregate_metrics["total_commits"],
                "avg_commits_per_day": round(
                    dashboard.aggregate_metrics["avg_commits_per_day"], 2
                ),
                "avg_health_score": round(
                    dashboard.aggregate_metrics["avg_health_score"], 1
                ),
                "total_conflicts": dashboard.aggregate_metrics["total_conflicts"],
            },
            "repositories": [
                {
                    "name": repo.repository_name,
                    "path": repo.repository_path,
                    "commits": repo.total_commits,
                    "commits_per_day": round(repo.avg_commits_per_day, 2),
                    "commits_per_week": round(repo.avg_commits_per_week, 1),
                    "conventional_compliance": round(
                        repo.conventional_compliance_rate * 100, 1
                    ),
                    "breaking_changes": repo.breaking_changes,
                    "conflict_rate": round(repo.merge_conflict_rate * 100, 2),
                    "health_score": round(repo.health_score, 1),
                    "trend": repo.trend_direction,
                }
                for repo in dashboard.repositories
            ],
            "top_performers": [
                {"path": path, "name": Path(path).name}
                for path in dashboard.top_performers
            ],
            "needs_attention": [
                {"path": path, "name": Path(path).name}
                for path in dashboard.needs_attention
            ],
            "patterns": [
                {
                    "type": pattern.pattern_type,
                    "severity": pattern.severity,
                    "description": pattern.description,
                    "affected_repositories": [
                        {"path": p, "name": Path(p).name}
                        for p in pattern.affected_repositories
                    ],
                    "recommendation": pattern.recommendation,
                }
                for pattern in dashboard.cross_project_patterns
            ],
        }

        logger.info(
            f"Dashboard generated: {dashboard.total_repositories} repos, "
            f"{len(dashboard.cross_project_patterns)} patterns detected"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to generate cross-project dashboard: {e}")
        raise


@mcp.tool()
@validate_call
def get_repository_health(
    repo_path: str = Field(
        description="Absolute path to git repository",
        examples=["/Users/les/Projects/crackerjack"],
    ),
) -> dict:
    try:
        repo = Path(repo_path).resolve()

        if not (repo / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

        aggregator = _get_aggregator()

        logger.info(f"Analyzing repository health for {repo}")

        import asyncio

        health = asyncio.run(aggregator.get_repository_health(repo))

        result = {
            "repository": str(repo),
            "repository_name": health.repository_name,
            "health_score": round(health.health_score, 1),
            "risk_level": health.risk_level,
            "indicators": {
                "stale_branches": len(health.stale_branches),
                "unmerged_prs": health.unmerged_prs,
                "large_files": len(health.large_files),
                "last_activity": health.last_activity.isoformat()
                if health.last_activity
                else None,
            },
            "details": {
                "stale_branches": health.stale_branches[:10],
                "large_files": health.large_files[:10],
            },
            "recommendations": health.recommendations,
        }

        logger.info(
            f"Repository health: {health.health_score:.1f}/100 (risk: {health.risk_level})"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to analyze repository health: {e}")
        raise


@mcp.tool()
@validate_call
def get_cross_project_patterns(
    project_paths: list[str] = Field(
        description="List of absolute paths to git repositories",
        examples=[
            ["/Users/les/Projects/crackerjack", "/Users/les/Projects/mcp-common"],
        ],
    ),
    days_back: int = Field(
        default=90,
        description="Number of days to analyze for pattern detection",
        ge=1,
        le=365,
    ),
) -> dict:
    try:
        aggregator = _get_aggregator()

        logger.info(
            f"Analyzing cross-project patterns for {len(project_paths)} repositories "
            f"(last {days_back} days)"
        )

        project_paths_str = [p for p in project_paths]

        import asyncio

        patterns = asyncio.run(
            aggregator.get_cross_project_patterns(project_paths_str, days_back)
        )

        result = {
            "summary": {
                "total_patterns": len(patterns),
                "period_days": days_back,
                "repositories_analyzed": len(project_paths),
            },
            "patterns": [
                {
                    "type": pattern.pattern_type,
                    "severity": pattern.severity,
                    "description": pattern.description,
                    "metric_value": round(pattern.metric_value, 2),
                    "affected_repositories": [
                        {"path": p, "name": Path(p).name}
                        for p in pattern.affected_repositories
                    ],
                    "recommendation": pattern.recommendation,
                    "detected_at": pattern.detected_at.isoformat(),
                }
                for pattern in patterns
            ],
        }

        logger.info(f"Detected {len(patterns)} cross-project patterns")

        return result

    except Exception as e:
        logger.error(f"Failed to detect cross-project patterns: {e}")
        raise


@mcp.tool()
@validate_call
def get_velocity_comparison(
    repo_path: str = Field(
        description="Absolute path to git repository",
        examples=["/Users/les/Projects/crackerjack"],
    ),
    compare_period_days: int = Field(
        default=30,
        description="Period in days to compare against previous period",
        ge=1,
        le=365,
    ),
) -> dict:
    try:
        repo = Path(repo_path).resolve()

        if not (repo / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

        aggregator = _get_aggregator()

        logger.info(
            f"Comparing velocity for {repo} ({compare_period_days} day periods)"
        )

        import asyncio
        from datetime import datetime, timedelta

        period_end = datetime.now()
        period_start = datetime.now() - timedelta(days=compare_period_days)

        current_velocity = asyncio.run(
            aggregator._collect_repository_velocity(str(repo), period_start, period_end)
        )

        prev_end = period_start
        prev_start = period_start - timedelta(days=compare_period_days)

        previous_velocity = asyncio.run(
            aggregator._collect_repository_velocity(str(repo), prev_start, prev_end)
        )

        commits_change = (
            current_velocity.total_commits - previous_velocity.total_commits
        )
        commits_change_pct = (
            (commits_change / previous_velocity.total_commits * 100)
            if previous_velocity.total_commits > 0
            else 0
        )

        velocity_change = (
            current_velocity.avg_commits_per_day - previous_velocity.avg_commits_per_day
        )
        velocity_change_pct = (
            (velocity_change / previous_velocity.avg_commits_per_day * 100)
            if previous_velocity.avg_commits_per_day > 0
            else 0
        )

        if velocity_change > 0.5:
            trend = "increasing"
        elif velocity_change < -0.5:
            trend = "decreasing"
        else:
            trend = "stable"

        result = {
            "repository": str(repo),
            "repository_name": current_velocity.repository_name,
            "period_days": compare_period_days,
            "current_period": {
                "commits": current_velocity.total_commits,
                "commits_per_day": round(current_velocity.avg_commits_per_day, 2),
                "commits_per_week": round(current_velocity.avg_commits_per_week, 1),
            },
            "previous_period": {
                "commits": previous_velocity.total_commits,
                "commits_per_day": round(previous_velocity.avg_commits_per_day, 2),
                "commits_per_week": round(previous_velocity.avg_commits_per_week, 1),
            },
            "change": {
                "commits": commits_change,
                "commits_percent": round(commits_change_pct, 1),
                "velocity": round(velocity_change, 2),
                "velocity_percent": round(velocity_change_pct, 1),
            },
            "trend": trend,
        }

        logger.info(f"Velocity trend: {trend} ({velocity_change:+.2f} commits/day)")

        return result

    except Exception as e:
        logger.error(f"Failed to compare velocity: {e}")
        raise


__all__ = ["mcp"]
