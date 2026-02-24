from __future__ import annotations

import logging
import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from mcp.server import FastMCP
from pydantic import Field, validate_call

from crackerjack.integration.mahavishnu_integration import (
    MahavishnuAggregator,
    MahavishnuConfig,
    RepositoryVelocity,
)

logger = logging.getLogger(__name__)

mcp = FastMCP("crackerjack-mahavishnu-git-analytics")

_aggregator: MahavishnuAggregator | None = None


def _get_aggregator() -> MahavishnuAggregator:
    global _aggregator
    if _aggregator is None:
        config = MahavishnuConfig(
            db_path=Path(".crackerjack/mahavishnu.db"),
            websocket_enabled=False,
        )
        _aggregator = MahavishnuAggregator(config=config)
    return _aggregator


@mcp.tool()
@validate_call
def get_portfolio_velocity_dashboard(
    project_paths: list[str] = Field(
        description="List of absolute paths to git repositories for portfolio analysis",
        examples=[
            [
                "/Users/les/Projects/crackerjack",
                "/Users/les/Projects/mcp-common",
                "/Users/les/Projects/session-buddy",
            ]
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
            f"Generating portfolio dashboard for {len(project_paths)} repositories "
            f"(last {days_back} days)"
        )

        project_paths_str = [str(p) for p in project_paths]

        import asyncio

        dashboard = asyncio.run(
            aggregator.get_cross_project_git_dashboard(project_paths_str, days_back)
        )

        portfolio_velocity = sum(r.avg_commits_per_day for r in dashboard.repositories)
        total_commits = sum(r.total_commits for r in dashboard.repositories)
        avg_health = (
            sum(r.health_score for r in dashboard.repositories)
            / len(dashboard.repositories)
            if dashboard.repositories
            else 0.0
        )

        high_performers = [r for r in dashboard.repositories if r.health_score >= 80]
        needs_attention = [r for r in dashboard.repositories if r.health_score < 50]

        result = {
            "portfolio": {
                "total_repositories": dashboard.total_repositories,
                "period_days": dashboard.period_days,
                "generated_at": dashboard.generated_at.isoformat(),
                "portfolio_velocity": round(portfolio_velocity, 2),
                "total_commits": total_commits,
                "avg_health_score": round(avg_health, 1),
            },
            "velocity_distribution": {
                "high_performers": len(high_performers),
                "healthy": len(
                    [r for r in dashboard.repositories if 50 <= r.health_score < 80]
                ),
                "needs_attention": len(needs_attention),
                "critical": len(
                    [r for r in dashboard.repositories if r.health_score < 40]
                ),
            },
            "repositories": [
                {
                    "name"  # type: ignore[untyped]: repo.repository_name,
                    "path": repo.repository_path,
                    "commits": repo.total_commits,
                    "commits_per_day": round(repo.avg_commits_per_day, 2),
                    "health_score": round(repo.health_score, 1),
                    "trend": repo.trend_direction,
                    "conventional_compliance": round(
                        repo.conventional_compliance_rate * 100, 1
                    ),
                }
                for repo in sorted(
                    dashboard.repositories, key=lambda r: r.health_score, reverse=True
                )
            ],
            "top_performers": [
                {"name": Path(p).name, "path": p} for p in dashboard.top_performers
            ],
            "needs_attention": [
                {"name": Path(p).name, "path": p} for p in dashboard.needs_attention
            ],
            "cross_project_patterns": [
                {
                    "type": pattern.pattern_type,
                    "severity": pattern.severity,
                    "description": pattern.description,
                    "affected_count": len(pattern.affected_repositories),
                    "recommendation": pattern.recommendation,
                }
                for pattern in dashboard.cross_project_patterns
            ],
        }

        logger.info(
            f"Portfolio dashboard: {total_commits} commits, "
            f"{portfolio_velocity:.2f} avg commits/day, "
            f"{avg_health:.1f} avg health score"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to generate portfolio dashboard: {e}")
        raise


@mcp.tool()
@validate_call
def analyze_merge_patterns(
    project_paths: list[str] = Field(
        description="List of absolute paths to git repositories",
        examples=[
            [
                "/Users/les/Projects/crackerjack",
                "/Users/les/Projects/mcp-common",
            ]
        ],
    ),
    days_back: int = Field(
        default=90,
        description="Number of days to analyze for merge patterns",
        ge=1,
        le=365,
    ),
) -> dict:
    try:
        logger.info(
            f"Analyzing merge patterns for {len(project_paths)} repositories "
            f"(last {days_back} days)"
        )

        from crackerjack.memory.git_metrics_collector import (
            GitMetricsCollector,
        )

        period_end = datetime.now()
        period_start = period_end - timedelta(days=days_back)

        repos_data = []
        total_merges = 0
        total_rebases = 0
        total_conflicts = 0
        all_conflicted_files: Counter = Counter()

        for repo_path_str in project_paths:
            repo_path = Path(repo_path_str).resolve()

            if not (repo_path / ".git").exists():
                logger.warning(f"Not a git repository: {repo_path}")
                continue

            try:
                collector = GitMetricsCollector(repo_path)  # type: ignore[untyped]
                merge_metrics = collector.collect_merge_patterns(
                    since=period_start, until=period_end
                )

                repos_data.append(
                    {
                        "name"  # type: ignore[untyped]: repo_path.name,
                        "path": str(repo_path),
                        "total_merges": merge_metrics.total_merges,
                        "total_rebases": merge_metrics.total_rebases,
                        "total_conflicts": merge_metrics.total_conflicts,
                        "conflict_rate": round(merge_metrics.conflict_rate * 100, 2),
                        "merge_success_rate": round(
                            merge_metrics.merge_success_rate * 100, 1
                        ),
                        "avg_files_per_conflict": round(
                            merge_metrics.avg_files_per_conflict, 1
                        ),
                    }
                )

                total_merges += merge_metrics.total_merges
                total_rebases += merge_metrics.total_rebases
                total_conflicts += merge_metrics.total_conflicts

                for file_path, count in merge_metrics.most_conflicted_files:
                    all_conflicted_files[file_path] += count

            except Exception as e:
                logger.error(f"Failed to analyze {repo_path}: {e}")
                continue

        portfolio_conflict_rate = (
            total_conflicts / total_merges if total_merges > 0 else 0.0
        )
        rebase_ratio = total_rebases / total_merges if total_merges > 0 else 0.0

        merge_vs_rebase_bias = "rebase" if rebase_ratio > 0.5 else "merge"

        top_conflicted_files = [
            {"path": path, "conflicts": count}
            for path, count in all_conflicted_files.most_common(20)
        ]

        result = {
            "summary": {
                "repositories_analyzed": len(repos_data),
                "period_days": days_back,
                "total_merges": total_merges,
                "total_rebases": total_rebases,
                "total_conflicts": total_conflicts,
                "portfolio_conflict_rate": round(portfolio_conflict_rate * 100, 2),
                "merge_vs_rebase_bias": merge_vs_rebase_bias,
                "rebase_ratio": round(rebase_ratio * 100, 1),
            },
            "portfolio_metrics": {
                "avg_conflicts_per_repo": round(total_conflicts / len(repos_data), 1)
                if repos_data
                else 0,
                "avg_conflict_rate": round(
                    sum(r["conflict_rate"] for r in repos_data) / len(repos_data), 2
                )
                if repos_data
                else 0,
                "merge_success_rate": round(
                    sum(r["merge_success_rate"] for r in repos_data) / len(repos_data),
                    1,
                )
                if repos_data
                else 0,
            },
            "repositories": repos_data,
            "most_conflicted_files": top_conflicted_files,
            "recommendations": _generate_merge_recommendations(
                portfolio_conflict_rate, rebase_ratio, top_conflicted_files
            ),
        }

        logger.info(
            f"Merge analysis: {total_merges} merges, "
            f"{rebase_ratio * 100:.1f}% rebase, "
            f"{portfolio_conflict_rate * 100:.2f}% conflict rate"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to analyze merge patterns: {e}")
        raise


@mcp.tool()
@validate_call
def get_best_practices_propagation(
    project_paths: list[str] = Field(
        description="List of absolute paths to git repositories",
        examples=[
            [
                "/Users/les/Projects/crackerjack",
                "/Users/les/Projects/mcp-common",
            ]
        ],
    ),
    days_back: int = Field(
        default=60,
        description="Number of days to analyze for best practices",
        ge=1,
        le=365,
    ),
) -> dict:
    try:
        aggregator = _get_aggregator()

        logger.info(
            f"Analyzing best practices for {len(project_paths)} repositories "
            f"(last {days_back} days)"
        )

        project_paths_str = [str(p) for p in project_paths]

        import asyncio

        period_end = datetime.now()
        period_start = period_end - timedelta(days=days_back)

        repos_data = []
        for repo_path_str in project_paths_str:
            try:
                velocity = asyncio.run(
                    aggregator._collect_repository_velocity(
                        365, repo_path_str, period_start, period_end
                    )
                )
                repos_data.append(velocity)
            except Exception as e:
                logger.warning(f"Failed to collect metrics from {repo_path_str}: {e}")
                continue

        if not repos_data:
            return {"error": "No valid repositories found"}

        sorted_by_health = sorted(
            repos_data, key=lambda r: r.health_score, reverse=True
        )
        top_performers = sorted_by_health[:3]
        low_performers = [r for r in sorted_by_health if r.health_score < 60]

        best_practices = _extract_best_practices(top_performers)
        propagation_targets = _identify_propagation_targets(
            low_performers, best_practices
        )

        result = {
            "summary": {
                "repositories_analyzed": len(repos_data),
                "top_performers_count": len(top_performers),
                "best_practices_found": len(best_practices),
                "propagation_targets": len(propagation_targets),
            },
            "top_performers": [
                {
                    "name"  # type: ignore[untyped]: r.repository_name,
                    "path": r.repository_path,
                    "health_score": round(r.health_score, 1),
                    "commits_per_day": round(r.avg_commits_per_day, 2),
                    "conventional_compliance": round(
                        r.conventional_compliance_rate * 100, 1
                    ),
                }
                for r in top_performers
            ],
            "best_practices": best_practices,
            "propagation_targets": propagation_targets,
            "recommendations": _generate_best_practice_recommendations(
                top_performers, low_performers
            ),
        }

        logger.info(
            f"Best practices: {len(best_practices)} practices found, "
            f"{len(propagation_targets)} propagation targets"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to analyze best practices: {e}")
        raise


@mcp.tool()
@validate_call
def get_repository_comparison(
    repo_paths: list[str] = Field(
        description="List of 2-5 absolute paths to git repositories for comparison",
        examples=[
            [
                "/Users/les/Projects/crackerjack",
                "/Users/les/Projects/mcp-common",
            ]
        ],
    ),
    days_back: int = Field(
        default=30,
        description="Number of days to analyze for comparison",
        ge=1,
        le=365,
    ),
) -> dict:
    try:
        if len(repo_paths) < 2 or len(repo_paths) > 5:
            raise ValueError("repo_paths must contain 2-5 repositories")

        aggregator = _get_aggregator()

        logger.info(f"Comparing {len(repo_paths)} repositories (last {days_back} days)")

        import asyncio

        period_end = datetime.now()
        period_start = period_end - timedelta(days=days_back)

        comparison_data = []
        for repo_path_str in repo_paths:
            try:
                repo_path = Path(repo_path_str).resolve()
                velocity = asyncio.run(
                    aggregator._collect_repository_velocity(
                        str(repo_path), period_start, period_end
                    )
                )
                comparison_data.append(
                    {
                        "name"  # type: ignore[untyped]: velocity.repository_name,
                        "path": velocity.repository_path,
                        "total_commits": velocity.total_commits,
                        "commits_per_day": round(velocity.avg_commits_per_day, 2),
                        "commits_per_week": round(velocity.avg_commits_per_week, 1),
                        "conventional_compliance": round(
                            velocity.conventional_compliance_rate * 100, 1
                        ),
                        "breaking_changes": velocity.breaking_changes,
                        "conflict_rate": round(velocity.merge_conflict_rate * 100, 2),
                        "health_score": round(velocity.health_score, 1),
                        "trend": velocity.trend_direction,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to analyze {repo_path_str}: {e}")
                continue

        if not comparison_data:
            return {"error": "No valid repositories found for comparison"}

        max_commits_day = max(r["commits_per_day"] for r in comparison_data)
        max_health = max(r["health_score"] for r in comparison_data)
        max_compliance = max(r["conventional_compliance"] for r in comparison_data)

        for repo in comparison_data:
            repo["relative_velocity"] = (
                round(repo["commits_per_day"] / max_commits_day * 100, 1)
                if max_commits_day > 0
                else 0
            )
            repo["relative_health"] = (
                round(repo["health_score"] / max_health * 100, 1)  # type: ignore[untyped]
                if max_health > 0  # type: ignore[untyped]
                else 0
            )
            repo["relative_compliance"] = (
                round(repo["conventional_compliance"] / max_compliance * 100, 1)
                if max_compliance > 0
                else 0
            )

        comparison_data.sort(key=lambda r: r["health_score"], reverse=True)  # type: ignore[untyped]

        result = {
            "summary": {
                "repositories_compared": len(comparison_data),
                "period_days": days_back,
                "leader_velocity": comparison_data[0]["name"]
                if comparison_data
                else None,
                "leader_health": max(comparison_data, key=lambda r: r["health_score"])[  # type: ignore[untyped]
                    :  # type: ignore[comment]
                    :  # type: ignore[comment]
                    "name"  # type: ignore[untyped]
                ]
                if comparison_data
                else None,
            },
            "comparison": comparison_data,
            "insights": _generate_comparison_insights(comparison_data),
        }

        logger.info(
            f"Comparison complete: {len(comparison_data)} repos, "
            f"leader: {comparison_data[0]['name']}"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to compare repositories: {e}")
        raise


@mcp.tool()
@validate_call
def get_cross_project_conflicts(
    project_paths: list[str] = Field(
        description="List of absolute paths to git repositories",
        examples=[
            [
                "/Users/les/Projects/crackerjack",
                "/Users/les/Projects/mcp-common",
            ]
        ],
    ),
    days_back: int = Field(
        default=90,
        description="Number of days to analyze for conflict patterns",
        ge=1,
        le=365,
    ),
) -> dict:
    try:
        _get_aggregator()

        logger.info(
            f"Analyzing cross-project conflicts for {len(project_paths)} repositories "
            f"(last {days_back} days)"
        )

        from crackerjack.memory.git_metrics_collector import GitMetricsCollector

        period_end = datetime.now()
        period_start = period_end - timedelta(days=days_back)

        all_conflicts: list[dict] = []
        file_conflicts: Counter = Counter()
        directory_conflicts: Counter = Counter()
        file_type_conflicts: Counter = Counter()
        repo_conflict_counts: dict[str, int] = {}
        total_merges = 0
        total_merges_with_conflicts = 0

        for repo_path_str in project_paths:
            repo_path = Path(repo_path_str).resolve()

            if not (repo_path / ".git").exists():
                logger.warning(f"Not a git repository: {repo_path}")
                continue

            try:
                collector = GitMetricsCollector(repo_path)  # type: ignore[untyped]
                merge_metrics = collector.collect_merge_patterns(
                    since=period_start, until=period_end
                )

                repo_conflict_counts[repo_path.name] = merge_metrics.total_conflicts
                total_merges += merge_metrics.total_merges

                if merge_metrics.total_conflicts > 0:
                    total_merges_with_conflicts += (
                        merge_metrics.total_merges_with_conflicts  # type: ignore[untyped]
                    )

                for file_path, count in merge_metrics.most_conflicted_files:
                    file_conflicts[file_path] += count

                    path_obj = Path(file_path)
                    directory = str(path_obj.parent) if path_obj.parent else "."
                    file_ext = path_obj.suffix.lower() or "(no extension)"

                    directory_conflicts[directory] += count
                    file_type_conflicts[file_ext] += count

                    file_full_path = repo_path / file_path
                    file_size = 0
                    line_count = 0
                    language = "unknown"

                    if file_full_path.exists():
                        file_size = file_full_path.stat().st_size
                        try:
                            with open(
                                file_full_path, encoding="utf-8", errors="ignore"
                            ) as f:
                                line_count = sum(1 for _ in f)
                        except Exception:
                            pass

                        language = _detect_language(file_ext)

                    all_conflicts.append(
                        {
                            "repository": repo_path.name,
                            "file": file_path,
                            "directory": directory,
                            "conflicts": count,
                            "file_size": file_size,
                            "line_count": line_count,
                            "language": language,
                            "file_type": file_ext,
                        }
                    )

            except Exception as e:
                logger.error(f"Failed to analyze conflicts for {repo_path}: {e}")
                continue

        if not all_conflicts:
            return {
                "summary": {
                    "repositories_analyzed": 0,
                    "total_conflict_files": 0,
                    "total_conflicts": 0,
                    "period_days": days_back,
                },
                "conflict_patterns": [],
                "hotspot_files": [],
                "recommendations": [],
            }

        merge_threshold = max(1, int(total_merges * 0.10))
        hotspot_files = [
            {
                "path": file_path,
                "conflicts": count,
                "conflict_rate": round(
                    (count / total_merges * 100) if total_merges > 0 else 0, 2
                ),
                "threshold_exceeded": count >= merge_threshold,
            }
            for file_path, count in file_conflicts.most_common(50)
        ]

        conflict_patterns = _analyze_conflict_patterns(
            all_conflicts,
            file_conflicts,
            directory_conflicts,
            file_type_conflicts,
            total_merges,
        )

        recommendations = _generate_conflict_prevention_recommendations(
            hotspot_files,
            conflict_patterns,
            file_conflicts,
            total_merges,
        )

        result = {
            "summary": {
                "repositories_analyzed": len(repo_conflict_counts),
                "total_conflict_files": len(file_conflicts),
                "total_conflicts": sum(file_conflicts.values()),
                "total_merges": total_merges,
                "merges_with_conflicts": total_merges_with_conflicts,
                "conflict_rate": round(
                    (total_merges_with_conflicts / total_merges * 100)
                    if total_merges > 0
                    else 0,
                    2,
                ),
                "period_days": days_back,
            },
            "conflict_patterns": conflict_patterns,
            "hotspot_files": [
                {
                    **hotspot,
                    **next(
                        (
                            {
                                "directory": c["directory"],
                                "language": c["language"],
                                "file_size": c["file_size"],
                                "line_count": c["line_count"],
                            }
                            for c in all_conflicts
                            if c["file"] == hotspot["path"]
                        ),
                        {},
                    ),
                }
                for hotspot in hotspot_files[:20]
            ],
            "directory_hotspots": [
                {
                    "directory": dir_path,
                    "conflicts": count,
                    "conflict_rate": round(
                        (count / total_merges * 100) if total_merges > 0 else 0, 2
                    ),
                }
                for dir_path, count in directory_conflicts.most_common(10)
            ],
            "file_type_analysis": [
                {
                    "file_type": ext,
                    "conflicts": count,
                    "percentage": round(
                        (count / sum(file_type_conflicts.values()) * 100)
                        if file_type_conflicts
                        else 0,
                        1,
                    ),
                }
                for ext, count in file_type_conflicts.most_common(10)
            ],
            "recommendations": recommendations,
        }

        logger.info(
            f"Cross-project conflicts: {len(file_conflicts)} files, "
            f"{sum(file_conflicts.values())} total conflicts, "
            f"{len(hotspot_files)} hotspot files identified"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to analyze cross-project conflicts: {e}")
        raise


def _detect_language(file_ext: str) -> str:
    language_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "JavaScript (React)",
        ".tsx": "TypeScript (React)",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".c": "C",
        ".cpp": "C++",
        ".cc": "C++",
        ".cxx": "C++",
        ".h": "C/C++ Header",
        ".hpp": "C++ Header",
        ".rb": "Ruby",
        ".php": "PHP",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".scala": "Scala",
        ".sh": "Shell",
        ".bash": "Bash",
        ".zsh": "Zsh",
        ".fish": "Fish",
        ".ps1": "PowerShell",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".toml": "TOML",
        ".xml": "XML",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".sass": "Sass",
        ".md": "Markdown",
        ".rst": "reStructuredText",
        ".txt": "Plain Text",
        ".sql": "SQL",
        ".dockerfile": "Docker",
        ".dockerignore": "Docker",
        ".gitignore": "Git",
        ".env": "Environment",
    }
    return language_map.get(file_ext.lower(), "unknown")


def _analyze_conflict_patterns(
    all_conflicts: list[dict],
    file_conflicts: Counter,
    directory_conflicts: Counter,
    file_type_conflicts: Counter,
    total_merges: int,
) -> list[dict]:
    patterns = []

    config_extensions = {".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".conf"}
    config_conflicts = sum(
        count for ext, count in file_type_conflicts.items() if ext in config_extensions
    )
    if config_conflicts > 0:
        patterns.append(
            {
                "pattern_type": "configuration_files",
                "description": "Frequent conflicts in configuration files",
                "count": config_conflicts,
                "percentage": round(
                    (config_conflicts / sum(file_type_conflicts.values()) * 100)
                    if file_type_conflicts
                    else 0,
                    1,
                ),
                "severity": "medium"
                if config_conflicts < sum(file_type_conflicts.values()) * 0.2
                else "high",
                "recommendation": "Use environment-specific configuration files and config management tools",
            }
        )

    lock_files = sum(
        count
        for file_path, count in file_conflicts.items()
        if "lock" in file_path.lower()
    )
    if lock_files > 0:
        patterns.append(
            {
                "pattern_type": "lock_files",
                "description": "Dependency lock file conflicts",
                "count": lock_files,
                "percentage": round(
                    (lock_files / sum(file_conflicts.values()) * 100)
                    if file_conflicts
                    else 0,
                    1,
                ),
                "severity": "low",
                "recommendation": "Implement automated dependency update workflows to reduce concurrent lock changes",
            }
        )

    large_files = [
        c
        for c in all_conflicts
        if c.get("line_count", 0) > 500 or c.get("file_size", 0) > 50000
    ]
    if large_files:
        large_file_conflicts = sum(c["conflicts"] for c in large_files)
        patterns.append(
            {
                "pattern_type": "large_files",
                "description": "Conflicts in large files (>500 lines or 50KB)",
                "count": large_file_conflicts,
                "percentage": round(
                    (large_file_conflicts / sum(file_conflicts.values()) * 100)
                    if file_conflicts
                    else 0,
                    1,
                ),
                "severity": "high",
                "recommendation": "Refactor large files into smaller modules to reduce conflict surface area",
            }
        )

    if directory_conflicts:
        top_dir = directory_conflicts.most_common(1)[0]
        patterns.append(
            {
                "pattern_type": "directory_hotspot",
                "description": f"Directory '{top_dir[0]}' has highest conflict concentration",
                "count": top_dir[1],
                "percentage": round(
                    (top_dir[1] / sum(directory_conflicts.values()) * 100)
                    if directory_conflicts
                    else 0,
                    1,
                ),
                "severity": "medium",
                "recommendation": f"Review ownership and modification patterns in '{top_dir[0]}' directory",
            }
        )

    if file_type_conflicts:
        top_type = file_type_conflicts.most_common(1)[0]
        if top_type[0] != "(no extension)":
            language = _detect_language(top_type[0])
            patterns.append(
                {
                    "pattern_type": "language_specific",
                    "description": f"High conflict rate in {language} files",
                    "count": top_type[1],
                    "percentage": round(
                        (top_type[1] / sum(file_type_conflicts.values()) * 100)
                        if file_type_conflicts
                        else 0,
                        1,
                    ),
                    "severity": "low",
                    "recommendation": f"Review {language} code organization and team coordination practices",
                }
            )

    return patterns


def _generate_conflict_prevention_recommendations(
    hotspot_files: list[dict],
    conflict_patterns: list[dict],
    file_conflicts: Counter,
    total_merges: int,
) -> list[dict]:
    recommendations = []

    critical_hotspots = [f for f in hotspot_files if f.get("threshold_exceeded", False)]
    if critical_hotspots:
        total_hotspot_conflicts = sum(f["conflicts"] for f in critical_hotspots)
        expected_reduction = round(
            (total_hotspot_conflicts / sum(file_conflicts.values()) * 100)
            if file_conflicts
            else 0,
            1,
        )
        recommendations.append(
            {
                "priority": "high",
                "action": "refactor_hotspots",
                "title": "Refactor Critical Hotspot Files",
                "description": f"Break down {len(critical_hotspots)} files that exceed 10% merge conflict threshold",
                "affected_files": [f["path"] for f in critical_hotspots[:5]],
                "expected_impact": f"{expected_reduction}% reduction in conflicts",
                "effort": "high",
                "implementation": "Split large files, extract modules, reduce coupling",
            }
        )

    config_pattern = next(
        (p for p in conflict_patterns if p["pattern_type"] == "configuration_files"),
        None,
    )
    if config_pattern and config_pattern["severity"] == "high":
        recommendations.append(
            {
                "priority": "medium",
                "action": "config_management",
                "title": "Implement Configuration Management",
                "description": "Use environment-specific configs and schema validation",
                "expected_impact": f"{config_pattern['percentage']}% reduction in config conflicts",
                "effort": "medium",
                "implementation": "Adopt config-as-pattern, use .env files, implement config validation",
            }
        )

    lock_pattern = next(
        (p for p in conflict_patterns if p["pattern_type"] == "lock_files"), None
    )
    if lock_pattern:
        recommendations.append(
            {
                "priority": "low",
                "action": "dependency_automation",
                "title": "Automate Dependency Updates",
                "description": "Schedule automated dependency updates to reduce concurrent lock changes",
                "expected_impact": f"{lock_pattern['percentage']}% reduction in lock file conflicts",
                "effort": "low",
                "implementation": "Use Dependabot, Renovate, or similar tools",
            }
        )

    large_pattern = next(
        (p for p in conflict_patterns if p["pattern_type"] == "large_files"), None
    )
    if large_pattern:
        recommendations.append(
            {
                "priority": "high",
                "action": "large_file_refactoring",
                "title": "Refactor Large Files",
                "description": "Split files >500 lines into smaller, focused modules",
                "expected_impact": f"{large_pattern['percentage']}% reduction in conflicts",
                "effort": "high",
                "implementation": "Apply Single Responsibility Principle, extract classes/functions",
            }
        )

    if total_merges > 0:
        overall_conflict_rate = (
            sum(f["conflicts"] for f in hotspot_files) / total_merges
            if total_merges > 0
            else 0
        )
        if overall_conflict_rate > 0.2:
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "branch_strategy_review",
                    "title": "Review Branch Management Strategy",
                    "description": "High overall conflict rate indicates need for better branch coordination",
                    "expected_impact": "10-20% reduction through shorter-lived branches",
                    "effort": "medium",
                    "implementation": "Use trunk-based development, reduce branch lifetime, improve feature flags",
                }
            )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(
        key=lambda r: (
            priority_order.get(r["priority"], 3),  # type: ignore[untyped]
            -r.get("expected_impact", 0),  # type: ignore[untyped]
        )
    )

    return recommendations


def _generate_merge_recommendations(
    conflict_rate: float, rebase_ratio: float, conflicted_files: list[dict]
) -> list[str]:
    recommendations = []

    if conflict_rate > 0.15:
        recommendations.append(
            f"High conflict rate ({conflict_rate * 100:.1f}%): "
            "Consider implementing feature flags to reduce merge conflicts"
        )

    if rebase_ratio < 0.2:
        recommendations.append(
            f"Low rebase usage ({rebase_ratio * 100:.1f}%): "
            "Consider using rebase for linear history on long-running branches"
        )
    elif rebase_ratio > 0.8:
        recommendations.append(
            f"Very high rebase usage ({rebase_ratio * 100:.1f}%): "
            "Ensure team is trained on rebase conflict resolution"
        )

    if conflicted_files:
        top_file = conflicted_files[0]
        if top_file["conflicts"] > 5:
            recommendations.append(
                f"File '{top_file['path']}' has {top_file['conflicts']} conflicts: "
                "Consider splitting or redesigning to reduce conflicts"
            )

    if not recommendations:
        recommendations.append("Merge patterns look healthy - no major issues detected")

    return recommendations


def _extract_best_practices(top_performers: list[RepositoryVelocity]) -> list[dict]:
    practices = []

    avg_compliance = (
        sum(r.conventional_compliance_rate for r in top_performers)
        / len(top_performers)
        if top_performers
        else 0
    )

    if avg_compliance > 0.8:
        practices.append(
            {
                "practice": "Conventional Commits",
                "description": "High compliance with conventional commit format",
                "avg_compliance": round(avg_compliance * 100, 1),
                "adoption_rate": 100,
                "benefit": "Improved changelog generation and commit clarity",
            }
        )

    avg_velocity = (
        sum(r.avg_commits_per_day for r in top_performers) / len(top_performers)
        if top_performers
        else 0
    )

    if avg_velocity > 3.0:
        practices.append(
            {
                "practice": "High Velocity Workflow",
                "description": "Consistent daily commit cadence",
                "avg_commits_per_day": round(avg_velocity, 1),
                "adoption_rate": 100,
                "benefit": "Faster iteration and feedback cycles",
            }
        )

    low_conflict = [r for r in top_performers if r.merge_conflict_rate < 0.05]
    if len(low_conflict) >= len(top_performers) * 0.7:
        practices.append(
            {
                "practice": "Low Conflict Merging",
                "description": "Effective branch management reducing conflicts",
                "success_rate": 95,
                "adoption_rate": len(low_conflict) / len(top_performers) * 100,
                "benefit": "Reduced merge time and smoother integrations",
            }
        )

    return practices


def _identify_propagation_targets(
    low_performers: list[RepositoryVelocity], best_practices: list[dict]
) -> list[dict]:
    targets = []

    for repo in low_performers:
        missing_practices = []

        if repo.conventional_compliance_rate < 0.7:
            missing_practices.append("Conventional Commits")

        if repo.avg_commits_per_day < 1.0:
            missing_practices.append("Increased Commit Frequency")

        if repo.merge_conflict_rate > 0.1:
            missing_practices.append("Better Branch Management")

        if missing_practices:
            targets.append(
                {
                    "repository": repo.repository_name,
                    "path": repo.repository_path,
                    "health_score": round(repo.health_score, 1),
                    "missing_practices": missing_practices,
                    "potential_improvement": round(100 - repo.health_score, 1),
                }
            )

    return targets


def _generate_best_practice_recommendations(
    top_performers: list[RepositoryVelocity],
    low_performers: list[RepositoryVelocity],
) -> list[str]:
    recommendations = []

    if top_performers and low_performers:
        top_compliance = sum(
            r.conventional_compliance_rate for r in top_performers
        ) / len(top_performers)
        low_compliance = sum(
            r.conventional_compliance_rate for r in low_performers
        ) / len(low_performers)

        if top_compliance > low_compliance + 0.3:
            recommendations.append(
                f"Top performers have {top_compliance * 100:.1f}% conventional compliance "
                f"vs {low_compliance * 100:.1f}% for low performers - "
                "consider implementing commit linting"
            )

        top_velocity = sum(r.avg_commits_per_day for r in top_performers) / len(
            top_performers
        )
        low_velocity = sum(r.avg_commits_per_day for r in low_performers) / len(
            low_performers
        )

        if top_velocity > low_velocity * 2:
            recommendations.append(
                f"Top performers commit {top_velocity / low_velocity:.1f}x more frequently - "
                "review CI/CD bottlenecks in low performers"
            )

    if not recommendations:
        recommendations.append("All repositories show similar performance patterns")

    return recommendations


def _generate_comparison_insights(comparison_data: list[dict]) -> list[str]:
    insights = []

    if len(comparison_data) < 2:
        return insights

    max_velocity = max(r["commits_per_day"] for r in comparison_data)
    min_velocity = min(r["commits_per_day"] for r in comparison_data)

    if max_velocity > min_velocity * 3:
        velocity_leader = max(comparison_data, key=lambda r: r["commits_per_day"])
        insights.append(
            f"{velocity_leader['name']} has {max_velocity / min_velocity:.1f}x higher velocity "
            f"than the slowest repository"
        )

    max_health = max(r["health_score"] for r in comparison_data)
    min_health = min(r["health_score"] for r in comparison_data)

    if max_health - min_health > 30:
        health_leader = max(comparison_data, key=lambda r: r["health_score"])
        insights.append(
            f"Health score variance is {max_health - min_health:.1f} points - "
            f"{health_leader['name']} leads with {health_leader['health_score']:.1f}"
        )

    high_conflict = [r for r in comparison_data if r["conflict_rate"] > 10]
    if len(high_conflict) >= len(comparison_data) * 0.5:
        insights.append(
            f"{len(high_conflict)} repositories have high conflict rates - "
            "consider portfolio-wide branch management review"
        )

    if not insights:
        insights.append("Repositories show consistent performance across metrics")

    return insights


@mcp.tool()
@validate_call
def get_active_branches_analysis(
    project_paths: list[str] = Field(
        description="List of absolute paths to git repositories for branch analysis",
        examples=[
            [
                "/Users/les/Projects/crackerjack",
                "/Users/les/Projects/mcp-common",
                "/Users/les/Projects/session-buddy",
            ]
        ],
    ),
    stale_threshold_days: int = Field(
        default=90,
        description="Days without commits before a branch is considered stale",
        ge=7,
        le=365,
    ),
) -> dict:
    try:
        logger.info(
            f"Analyzing active branches for {len(project_paths)} repositories "
            f"(stale threshold: {stale_threshold_days} days)"
        )

        period_end = datetime.now()
        stale_threshold = timedelta(days=stale_threshold_days)

        repos_data = []
        portfolio_branches: list[dict] = []
        all_branch_names: list[str] = []
        abandoned_branches: list[dict] = []
        all_naming_patterns: Counter = Counter()

        for repo_path_str in project_paths:
            repo_path = Path(repo_path_str).resolve()

            if not (repo_path / ".git").exists():
                logger.warning(f"Not a git repository: {repo_path}")
                continue

            try:
                repo_branches = _collect_branch_data(
                    repo_path, period_end, stale_threshold
                )

                if not repo_branches:
                    continue

                branch_metrics = _calculate_branch_metrics(repo_branches)
                naming_analysis = _analyze_naming_conventions(repo_branches)
                hygiene_score = _calculate_branch_hygiene_score(
                    branch_metrics, naming_analysis
                )

                repos_data.append(
                    {
                        "name"  # type: ignore[untyped]: repo_path.name,
                        "path": str(repo_path),
                        "total_branches": branch_metrics["total_branches"],
                        "active_branches": branch_metrics["active_branches"],
                        "abandoned_branches": branch_metrics["abandoned_branches"],
                        "avg_branch_age_days": round(
                            branch_metrics["avg_branch_age_days"], 1
                        ),
                        "stale_branch_ratio": round(
                            branch_metrics["stale_branch_ratio"] * 100, 1
                        ),
                        "naming_compliance": round(
                            naming_analysis["compliance_rate"] * 100, 1
                        ),
                        "hygiene_score": round(hygiene_score, 1),
                        "most_common_prefix": naming_analysis.get("most_common_prefix"),
                    }
                )

                portfolio_branches.extend(repo_branches)
                all_branch_names.extend(b["name"] for b in repo_branches)
                abandoned_branches.extend(
                    [
                        {**b, "repository": repo_path.name, "path": str(repo_path)}
                        for b in repo_branches
                        if b["is_abandoned"]
                    ]
                )

                for pattern in naming_analysis.get("patterns", []):
                    all_naming_patterns[pattern["prefix"]] += pattern["count"]

            except Exception as e:
                logger.error(f"Failed to analyze branches for {repo_path}: {e}")
                continue

        if not repos_data:
            return {"error": "No valid repositories found for branch analysis"}

        portfolio_metrics = _calculate_portfolio_branch_metrics(
            repos_data, portfolio_branches, abandoned_branches
        )

        lifecycle_analysis = _analyze_branch_lifecycle(portfolio_branches, period_end)

        naming_summary = _summarize_naming_patterns(all_naming_patterns)

        recommendations = _generate_branch_hygiene_recommendations(
            portfolio_metrics, naming_summary, lifecycle_analysis
        )

        result = {
            "summary": {
                "repositories_analyzed": len(repos_data),
                "total_branches": portfolio_metrics["total_branches"],
                "active_branches": portfolio_metrics["active_branches"],
                "abandoned_branches": portfolio_metrics["abandoned_branches"],
                "avg_branch_age_days": round(
                    portfolio_metrics["avg_branch_age_days"], 1
                ),
                "stale_branch_ratio": round(
                    portfolio_metrics["stale_branch_ratio"] * 100, 1
                ),
                "portfolio_hygiene_score": round(portfolio_metrics["hygiene_score"], 1),
            },
            "branch_metrics": {
                "total_branches": portfolio_metrics["total_branches"],
                "active_branches": portfolio_metrics["active_branches"],
                "abandoned_branches": portfolio_metrics["abandoned_branches"],
                "avg_branch_age_days": round(
                    portfolio_metrics["avg_branch_age_days"], 1
                ),
                "stale_branch_ratio": round(
                    portfolio_metrics["stale_branch_ratio"] * 100, 1
                ),
                "branches_needing_cleanup": portfolio_metrics[
                    "branches_needing_cleanup"
                ],
            },
            "lifecycle_analysis": lifecycle_analysis,
            "naming_conventions": naming_summary,
            "hygiene_score": {
                "score": round(portfolio_metrics["hygiene_score"], 1),
                "grade": _get_hygiene_grade(portfolio_metrics["hygiene_score"]),
                "factors": portfolio_metrics["hygiene_factors"],
            },
            "repositories": repos_data,
            "abandoned_branches": abandoned_branches[:50],
            "recommendations": recommendations,
        }

        logger.info(
            f"Branch analysis: {portfolio_metrics['total_branches']} branches, "
            f"{portfolio_metrics['abandoned_branches']} abandoned, "
            f"hygiene score: {portfolio_metrics['hygiene_score']:.1f}/100"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to analyze active branches: {e}")
        raise


def _collect_branch_data(
    repo_path: Path, period_end: datetime, stale_threshold: timedelta
) -> list[dict]:
    branches = []

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "for-each-ref",
                "--format=%(refname: short)%00%(committerdate: iso8601)",
                "refs/heads/",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.warning(f"Failed to get branches for {repo_path}")
            return []

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("\x00")
            if len(parts) != 2:
                continue

            branch_name, commit_date_str = parts

            try:
                commit_date = datetime.fromisoformat(commit_date_str)
                age_days = (period_end - commit_date).total_seconds() / 86400
                is_abandoned = (period_end - commit_date) > stale_threshold

                branches.append(
                    {
                        "name"  # type: ignore[untyped]: branch_name,
                        "last_commit_date": commit_date.isoformat(),
                        "age_days": round(age_days, 1),
                        "is_abandoned": is_abandoned,
                    }
                )

            except ValueError:
                logger.debug(f"Failed to parse date for branch {branch_name}")
                continue

    except subprocess.TimeoutExpired:
        logger.error(f"Git command timed out for {repo_path}")
    except Exception as e:
        logger.error(f"Failed to collect branch data from {repo_path}: {e}")

    return branches


def _calculate_branch_metrics(branches: list[dict]) -> dict:
    if not branches:
        return {
            "total_branches": 0,
            "active_branches": 0,
            "abandoned_branches": 0,
            "avg_branch_age_days": 0.0,
            "stale_branch_ratio": 0.0,
        }

    total_branches = len(branches)
    active_branches = sum(1 for b in branches if not b["is_abandoned"])
    abandoned_branches = total_branches - active_branches
    avg_age = sum(b["age_days"] for b in branches) / total_branches
    stale_ratio = abandoned_branches / total_branches if total_branches > 0 else 0.0

    return {
        "total_branches": total_branches,
        "active_branches": active_branches,
        "abandoned_branches": abandoned_branches,
        "avg_branch_age_days": avg_age,
        "stale_branch_ratio": stale_ratio,
    }


def _analyze_naming_conventions(branches: list[dict]) -> dict:
    if not branches:
        return {"compliance_rate": 0.0, "patterns": [], "most_common_prefix": None}

    naming_patterns = {
        "feature/": r"^feature/",
        "feat/": r"^feat/",
        "bugfix/": r"^bugfix/",
        "fix/": r"^fix/",
        "hotfix/": r"^hotfix/",
        "release/": r"^release/",
        "chore/": r"^chore/",
        "docs/": r"^docs/",
        "test/": r"^test/",
        "refactor/": r"^refactor/",
        "perf/": r"^perf/",
    }

    pattern_counts: Counter = Counter()
    compliant_count = 0

    for branch in branches:
        branch_name = branch["name"]
        matched = False

        for prefix, pattern in naming_patterns.items():
            if re.match(pattern, branch_name):
                pattern_counts[prefix] += 1
                compliant_count += 1
                matched = True
                break

        if not matched and re.match(r"^[A-Z]+-\d+", branch_name):
            pattern_counts["ticket-id"] += 1
            compliant_count += 1
            matched = True

    compliance_rate = compliant_count / len(branches) if branches else 0.0

    patterns = [
        {
            "prefix": prefix,
            "count": count,
            "percentage": round(count / len(branches) * 100, 1),
        }
        for prefix, count in pattern_counts.most_common()
    ]

    most_common = pattern_counts.most_common(1)[0] if pattern_counts else None

    return {
        "compliance_rate": compliance_rate,
        "patterns": patterns,
        "most_common_prefix": most_common[0] if most_common else None,
    }


def _calculate_branch_hygiene_score(
    branch_metrics: dict, naming_analysis: dict
) -> float:
    score = 100.0

    stale_ratio = branch_metrics["stale_branch_ratio"]
    if stale_ratio > 0.5:
        score -= 40
    elif stale_ratio > 0.3:
        score -= 25
    elif stale_ratio > 0.1:
        score -= 10

    compliance = naming_analysis["compliance_rate"]
    if compliance < 0.5:
        score -= 30
    elif compliance < 0.7:
        score -= 15
    elif compliance < 0.9:
        score -= 5

    total_branches = branch_metrics["total_branches"]
    if total_branches > 50:
        score -= 20
    elif total_branches > 30:
        score -= 10
    elif total_branches > 20:
        score -= 5

    avg_age = branch_metrics["avg_branch_age_days"]
    if avg_age > 180:
        score -= 10
    elif avg_age > 90:
        score -= 5

    return max(score, 0.0)


def _calculate_portfolio_branch_metrics(
    repos_data: list[dict], all_branches: list[dict], abandoned_branches: list[dict]
) -> dict:
    if not repos_data:
        return {
            "total_branches": 0,
            "active_branches": 0,
            "abandoned_branches": 0,
            "avg_branch_age_days": 0.0,
            "stale_branch_ratio": 0.0,
            "branches_needing_cleanup": 0,
            "hygiene_score": 0.0,
            "hygiene_factors": {},
        }

    total_branches = sum(r["total_branches"] for r in repos_data)
    active_branches = sum(r["active_branches"] for r in repos_data)
    abandoned_branches_count = len(abandoned_branches)
    avg_age = (
        sum(r["avg_branch_age_days"] for r in repos_data) / len(repos_data)
        if repos_data
        else 0.0
    )
    stale_ratio = (
        abandoned_branches_count / total_branches if total_branches > 0 else 0.0
    )

    hygiene_scores = [r["hygiene_score"] for r in repos_data]
    avg_hygiene = sum(hygiene_scores) / len(hygiene_scores) if hygiene_scores else 0.0

    hygiene_factors = {
        "stale_branch_penalty": max(0, 40 * (1 if stale_ratio > 0.5 else 0)),
        "naming_compliance_bonus": sum(r["naming_compliance"] for r in repos_data)
        / len(repos_data),
        "excessive_branches_penalty": sum(
            1 for r in repos_data if r["total_branches"] > 30
        ),
    }

    return {
        "total_branches": total_branches,
        "active_branches": active_branches,
        "abandoned_branches": abandoned_branches_count,
        "avg_branch_age_days": avg_age,
        "stale_branch_ratio": stale_ratio,
        "branches_needing_cleanup": abandoned_branches_count,
        "hygiene_score": avg_hygiene,
        "hygiene_factors": hygiene_factors,
    }


def _analyze_branch_lifecycle(branches: list[dict], period_end: datetime) -> dict:
    if not branches:
        return {
            "age_distribution": {"young": 0, "mature": 0, "old": 0},
            "avg_lifespan_days": 0.0,
        }

    young = sum(1 for b in branches if b["age_days"] < 7)
    mature = sum(1 for b in branches if 7 <= b["age_days"] < 30)
    old = sum(1 for b in branches if b["age_days"] >= 30)

    avg_lifespan = sum(b["age_days"] for b in branches) / len(branches)

    return {
        "age_distribution": {
            "young": young,
            "mature": mature,
            "old": old,
            "young_pct": round(young / len(branches) * 100, 1),
            "mature_pct": round(mature / len(branches) * 100, 1),
            "old_pct": round(old / len(branches) * 100, 1),
        },
        "avg_lifespan_days": round(avg_lifespan, 1),
    }


def _summarize_naming_patterns(patterns: Counter) -> dict:
    if not patterns:
        return {"total_patterns": 0, "top_patterns": [], "compliance_rate": 0.0}

    total_branches = sum(patterns.values())
    top_patterns = [
        {
            "prefix": prefix,
            "count": count,
            "percentage": round(count / total_branches * 100, 1),
        }
        for prefix, count in patterns.most_common(10)
    ]

    return {
        "total_patterns": len(patterns),
        "top_patterns": top_patterns,
        "compliance_rate": round(
            sum(count for prefix, count in patterns.items() if prefix != "other")
            / total_branches
            * 100,
            1,
        )
        if total_branches > 0
        else 0.0,
    }


def _generate_branch_hygiene_recommendations(
    metrics: dict, naming: dict, lifecycle: dict
) -> list[dict]:
    recommendations = []

    stale_ratio = metrics["stale_branch_ratio"]
    if stale_ratio > 0.3:
        priority = "high" if stale_ratio > 0.5 else "medium"
        recommendations.append(
            {
                "priority": priority,
                "issue": "High stale branch ratio",
                "impact": f"{stale_ratio * 100:.1f}% of branches are abandoned",
                "recommendation": "Implement automated branch cleanup policies "
                "for branches older than 90 days",
                "expected_improvement": f"Reduce stale ratio by {min(stale_ratio * 0.7, 0.4):.1%}",
            }
        )

    hygiene_score = metrics["hygiene_score"]
    if hygiene_score < 60:
        recommendations.append(
            {
                "priority": "high",
                "issue": "Poor branch hygiene score",
                "impact": f"Current score: {hygiene_score:.1f}/100",
                "recommendation": "Establish branch naming conventions "
                "and implement pre-commit hooks for enforcement",
                "expected_improvement": "+20-30 points in hygiene score",
            }
        )

    if metrics["total_branches"] > 50:
        recommendations.append(
            {
                "priority": "medium",
                "issue": "Excessive branch count",
                "impact": f"{metrics['total_branches']} total branches detected",
                "recommendation": "Implement aggressive branch cleanup "
                "and reduce long-lived feature branches",
                "expected_improvement": "Reduce total branches by 40-60%",
            }
        )

    compliance = naming.get("compliance_rate", 0)
    if compliance < 70:
        recommendations.append(
            {
                "priority": "medium",
                "issue": "Low naming convention compliance",
                "impact": f"Only {compliance:.1f}% of branches follow conventions",
                "recommendation": "Adopt conventional branch naming (feature/, fix/, hotfix/) "
                "and add validation to PR templates",
                "expected_improvement": "Improve compliance to 90%+ within 2 weeks",
            }
        )

    old_pct = lifecycle["age_distribution"].get("old_pct", 0)
    if old_pct > 40:
        recommendations.append(
            {
                "priority": "medium",
                "issue": "Many long-lived branches",
                "impact": f"{old_pct:.1f}% of branches are older than 30 days",
                "recommendation": "Review branch lifecycle and consider "
                "shortening feature branch duration",
                "expected_improvement": "Reduce average branch lifespan by 50%",
            }
        )

    if not recommendations:
        recommendations.append(
            {
                "priority": "low",
                "issue": "Branch management looks healthy",
                "impact": "No major issues detected",
                "recommendation": "Continue current practices and "
                "monitor metrics monthly",
                "expected_improvement": "Maintain current hygiene standards",
            }
        )

    return recommendations


def _get_hygiene_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


"""
New implementation of get_repository_health_dashboard() for git_analytics.py

This should be inserted after line 727 (after get_cross_project_conflicts ends)
"""


@mcp.tool()
@validate_call
def get_repository_health_dashboard(
    repository_paths: list[str] = Field(
        description="List of absolute paths to git repositories for health analysis",
        examples=[
            [
                "/Users/les/Projects/crackerjack",
                "/Users/les/Projects/mcp-common",
                "/Users/les/Projects/session-buddy",
            ]
        ],
    ),
    days_back: int = Field(
        default=90,
        description="Number of days to analyze for health metrics",
        ge=1,
        le=365,
    ),
) -> dict:
    try:
        logger.info(
            f"Generating health dashboard for {len(repository_paths)} repositories "
            f"(last {days_back} days)"
        )

        from crackerjack.memory.git_metrics_collector import GitMetricsCollector
        from crackerjack.services.secure_subprocess import SecureSubprocessExecutor

        period_end = datetime.now()
        period_start = period_end - timedelta(days=days_back)

        all_health_data: list[dict] = []
        portfolio_warnings: list[dict] = []
        all_large_files: list[dict] = []
        all_stale_branches: list[dict] = []

        for repo_path_str in repository_paths:
            repo_path = Path(repo_path_str).resolve()

            if not (repo_path / ".git").exists():
                logger.warning(f"Not a git repository: {repo_path}")
                continue

            try:
                executor = SecureSubprocessExecutor()  # type: ignore
                collector = GitMetricsCollector(repo_path, executor)

                commit_metrics = collector.collect_commit_metrics(
                    since=period_start, until=period_end
                )
                branch_metrics = collector.collect_branch_activity(since=period_start)
                merge_metrics = collector.collect_merge_patterns(
                    since=period_start, until=period_end
                )

                activity_score = _calculate_activity_health_score(
                    commit_metrics, days_back
                )
                quality_score = _calculate_quality_health_score(commit_metrics)
                workflow_score = _calculate_workflow_health_score(merge_metrics)
                hygiene_score = _calculate_hygiene_health_score(branch_metrics)

                overall_health = (
                    activity_score * 0.30
                    + quality_score * 0.30
                    + workflow_score * 0.25
                    + hygiene_score * 0.15
                )

                warnings = _detect_health_warnings(  # type: ignore[untyped]
                    repo_path.name,
                    commit_metrics,
                    branch_metrics,
                    merge_metrics,
                )
                portfolio_warnings.extend(warnings)

                large_files = _scan_large_files(repo_path)
                all_large_files.extend(large_files)

                stale_branches = _scan_stale_branches(repo_path)
                all_stale_branches.extend(stale_branches)

                previous_start = period_start - timedelta(days=days_back)
                previous_end = period_start

                try:
                    previous_commit_metrics = collector.collect_commit_metrics(
                        since=previous_start, until=previous_end
                    )
                    trend = _calculate_health_trend(
                        commit_metrics, previous_commit_metrics
                    )
                except Exception as e:
                    logger.debug(f"Could not calculate trend for {repo_path}: {e}")
                    trend = "unknown"

                all_health_data.append(
                    {
                        "repository": repo_path.name,
                        "path": str(repo_path),
                        "overall_health": round(overall_health, 1),
                        "component_scores": {
                            "activity": round(activity_score, 1),
                            "quality": round(quality_score, 1),
                            "workflow": round(workflow_score, 1),
                            "hygiene": round(hygiene_score, 1),
                        },
                        "metrics": {
                            "commits": {
                                "total": commit_metrics.total_commits,
                                "per_day": round(commit_metrics.avg_commits_per_day, 2),
                                "conventional_rate": round(
                                    commit_metrics.conventional_compliance_rate * 100,
                                    1,
                                ),
                                "breaking_changes": commit_metrics.breaking_changes,
                            },
                            "branches": {
                                "total": branch_metrics.total_branches,
                                "active": branch_metrics.active_branches,
                                "switches": branch_metrics.branch_switches,
                                "created": branch_metrics.branches_created,
                                "deleted": branch_metrics.branches_deleted,
                            },
                            "merges": {
                                "total": merge_metrics.total_merges,
                                "conflicts": merge_metrics.total_conflicts,
                                "conflict_rate": round(
                                    merge_metrics.conflict_rate * 100, 2
                                ),
                                "success_rate": round(
                                    merge_metrics.merge_success_rate * 100, 1
                                ),
                            },
                        },
                        "trend": trend,
                        "warnings": [w["message"] for w in warnings],
                        "grade": _health_score_to_grade(overall_health),
                    }
                )

            except Exception as e:
                logger.error(f"Failed to analyze {repo_path}: {e}")
                continue

        if not all_health_data:
            return {"error": "No valid repositories found for health analysis"}

        portfolio_health = _aggregate_portfolio_health(all_health_data)
        portfolio_trends = _analyze_portfolio_trends(all_health_data)

        recommendations = _create_health_recommendations(
            all_health_data, portfolio_warnings, all_large_files, all_stale_branches
        )

        result = {
            "summary": {
                "repositories_analyzed": len(all_health_data),
                "period_days": days_back,
                "generated_at": period_end.isoformat(),
                "overall_health_score": portfolio_health["overall_score"],
                "health_grade": _health_score_to_grade(
                    portfolio_health["overall_score"]
                ),
            },
            "health_scores": {
                "overall": portfolio_health["overall_score"],
                "activity": portfolio_health["avg_activity"],
                "quality": portfolio_health["avg_quality"],
                "workflow": portfolio_health["avg_workflow"],
                "hygiene": portfolio_health["avg_hygiene"],
                "grade_distribution": portfolio_health["grade_distribution"],
            },
            "trends": portfolio_trends,
            "warnings": {
                "total": len(portfolio_warnings),
                "critical": len(
                    [w for w in portfolio_warnings if w["severity"] == "critical"]
                ),
                "warnings_by_type": _categorize_warnings(portfolio_warnings),
                "top_warnings": sorted(
                    portfolio_warnings,
                    key=lambda w: (
                        w["severity"] == "critical",
                        w["severity"] == "warning",
                    ),
                    reverse=True,
                )[:20],
            },
            "component_breakdown": {
                "activity": _build_activity_breakdown(all_health_data),
                "quality": _build_quality_breakdown(all_health_data),
                "workflow": _build_workflow_breakdown(all_health_data),
                "hygiene": _build_hygiene_breakdown(all_health_data),
            },
            "repositories": sorted(
                all_health_data, key=lambda r: r["overall_health"], reverse=True
            ),
            "recommendations": recommendations,
        }

        logger.info(
            f"Health dashboard: {len(all_health_data)} repos, "
            f"portfolio health {portfolio_health['overall_score']:.1f}, "
            f"{len(portfolio_warnings)} warnings"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to generate health dashboard: {e}")
        raise


@mcp.tool()
@validate_call
def get_workflow_recommendations(
    project_paths: list[str] = Field(
        description="List of absolute paths to git repositories for workflow analysis",
        examples=[
            [
                "/Users/les/Projects/crackerjack",
                "/Users/les/Projects/mcp-common",
                "/Users/les/Projects/session-buddy",
            ]
        ],
    ),
    days_back: int = Field(
        default=60,
        description="Number of days to analyze for workflow patterns",
        ge=1,
        le=365,
    ),
    quality_correlation: bool = Field(
        default=True,
        description="Whether to correlate workflow patterns with quality metrics",
    ),
) -> dict:
    try:
        aggregator = _get_aggregator()

        logger.info(
            f"Generating workflow recommendations for {len(project_paths)} repositories "
            f"(last {days_back} days, quality_correlation={quality_correlation})"
        )

        project_paths_str = [str(p) for p in project_paths]

        import asyncio

        period_end = datetime.now()
        period_start = period_end - timedelta(days=days_back)

        repos_data = []
        for repo_path_str in project_paths_str:
            try:
                velocity = asyncio.run(
                    aggregator._collect_repository_velocity(
                        str(repo_path_str), period_start, period_end
                    )
                )
                repos_data.append(velocity)
            except Exception as e:
                logger.warning(f"Failed to collect metrics from {repo_path_str}: {e}")
                continue

        if not repos_data:
            return {"error": "No valid repositories found for analysis"}

        from crackerjack.memory.git_metrics_collector import GitMetricsCollector

        repo_workflow_data: list[dict] = []

        for repo_velocity in repos_data:
            repo_path = Path(repo_velocity.repository_path)
            try:
                collector = GitMetricsCollector(repo_path)  # type: ignore[untyped]
                commit_metrics = collector.collect_commit_metrics(
                    since=period_start, until=period_end
                )
                branch_metrics = collector.collect_branch_metrics(  # type: ignore[untyped]
                    since=period_start, until=period_end
                )
                merge_metrics = collector.collect_merge_patterns(
                    since=period_start, until=period_end
                )

                repo_workflow_data.append(
                    {
                        "velocity": repo_velocity,
                        "commit_metrics": commit_metrics,
                        "branch_metrics": branch_metrics,
                        "merge_metrics": merge_metrics,
                    }
                )

            except Exception as e:
                logger.warning(
                    f"Failed to collect detailed metrics for {repo_path}: {e}"
                )

        workflow_analysis = _analyze_workflow_patterns(repo_workflow_data)
        bottlenecks = _identify_workflow_bottlenecks(repo_workflow_data)
        quality_correlation_data = (
            _correlate_quality_metrics(repo_workflow_data)
            if quality_correlation
            else None
        )
        recommendations = _generate_workflow_recommendations(
            workflow_analysis, bottlenecks, quality_correlation_data
        )

        result = {
            "summary": {
                "repositories_analyzed": len(repo_workflow_data),
                "period_days": days_back,
                "analysis_timestamp": datetime.now().isoformat(),
                "overall_health": round(
                    sum(r["velocity"].health_score for r in repo_workflow_data)
                    / len(repo_workflow_data),
                    1,
                )
                if repo_workflow_data
                else 0.0,
            },
            "workflow_analysis": workflow_analysis,
            "bottlenecks": bottlenecks,
            "quality_correlation": quality_correlation_data or {},
            "recommendations": recommendations,
        }

        logger.info(
            f"Workflow recommendations: {len(recommendations)} recommendations generated, "
            f"{len(bottlenecks)} bottlenecks identified"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to generate workflow recommendations: {e}")
        raise


def _calculate_activity_health_score(commit_metrics: Any, days_back: int) -> float:  # type: ignore[untyped]
    score = 100.0

    commits_per_day = commit_metrics.avg_commits_per_day
    total_commits = commit_metrics.total_commits
    compliance_rate = commit_metrics.conventional_compliance_rate

    if commits_per_day < 0.5:
        score -= 40
    elif commits_per_day < 1.0:
        score -= 25
    elif commits_per_day < 2.0:
        score -= 10

    if compliance_rate < 0.5:
        score -= 30
    elif compliance_rate < 0.7:
        score -= 15
    elif compliance_rate < 0.9:
        score -= 5

    breaking_ratio = (
        commit_metrics.breaking_changes / total_commits if total_commits > 0 else 0
    )
    if breaking_ratio > 0.1:
        score -= 30
    elif breaking_ratio > 0.05:
        score -= 15
    elif breaking_ratio > 0.02:
        score -= 5

    return max(score, 0.0)


def _calculate_quality_health_score(commit_metrics: Any) -> float:  # type: ignore[untyped]
    score = 100.0

    compliance_rate = commit_metrics.conventional_compliance_rate
    breaking_changes = commit_metrics.breaking_changes
    total_commits = commit_metrics.total_commits

    if compliance_rate >= 0.95:
        score = min(score + 30, 100.0)
    elif compliance_rate >= 0.9:
        score += 20
    elif compliance_rate >= 0.8:
        score += 10

    breaking_ratio = breaking_changes / total_commits if total_commits > 0 else 0
    if breaking_ratio > 0.15:
        score -= 40
    elif breaking_ratio > 0.1:
        score -= 25
    elif breaking_ratio > 0.05:
        score -= 10

    if total_commits < 10:
        score -= 30
    elif total_commits < 20:
        score -= 15
    elif total_commits < 50:
        score -= 5

    return max(score, 0.0)


def _calculate_workflow_health_score(merge_metrics: Any) -> float:  # type: ignore[untyped]
    score = 100.0

    total_merges = merge_metrics.total_merges
    conflict_rate = merge_metrics.conflict_rate
    success_rate = merge_metrics.merge_success_rate

    if total_merges < 5:
        score -= 30
    elif total_merges < 10:
        score -= 15
    elif total_merges < 20:
        score -= 5

    if conflict_rate > 0.2:
        score -= 40
    elif conflict_rate > 0.15:
        score -= 25
    elif conflict_rate > 0.1:
        score -= 10

    if success_rate < 0.7:
        score -= 30
    elif success_rate < 0.85:
        score -= 15
    elif success_rate < 0.95:
        score -= 5

    return max(score, 0.0)


def _calculate_hygiene_health_score(branch_metrics: Any) -> float:  # type: ignore[untyped]
    score = 100.0

    total_branches = branch_metrics.total_branches
    active_branches = branch_metrics.active_branches
    created = branch_metrics.branches_created
    deleted = branch_metrics.branches_deleted

    if total_branches > 50:
        score -= 30
    elif total_branches > 30:
        score -= 15
    elif total_branches > 20:
        score -= 5

    if created > 0:
        cleanup_ratio = deleted / created if created > 0 else 0
        if cleanup_ratio < 0.5:
            score -= 40
        elif cleanup_ratio < 0.7:
            score -= 20
        elif cleanup_ratio < 0.9:
            score -= 5

    if total_branches > 0:
        active_ratio = active_branches / total_branches
        if active_ratio < 0.3:
            score -= 30
        elif active_ratio < 0.5:
            score -= 15
        elif active_ratio < 0.7:
            score -= 5

    return max(score, 0.0)


def _detect_health_warnings(
    repo_name: str,
    commit_metrics: Any,
    branch_metrics: Any,
) -> list[dict]:
    warnings = []

    if commit_metrics.avg_commits_per_day < 0.5:
        warnings.append(
            {
                "repository": repo_name,
                "type": "low_activity",
                "severity": "warning",
                "message": f"Very low commit activity "
                f"({commit_metrics.avg_commits_per_day:.2f} commits/day)",
            }
        )

    if commit_metrics.conventional_compliance_rate < 0.7:
        warnings.append(
            {
                "repository": repo_name,
                "type": "low_compliance",
                "severity": "warning",
                "message": f"Low conventional compliance "
                f"({commit_metrics.conventional_compliance_rate * 100:.1f}%)",
            }
        )

    if merge_metrics.conflict_rate > 0.15:  # type: ignore[untyped]
        warnings.append(
            {
                "repository": repo_name,
                "type": "high_conflicts",
                "severity": "critical",
                "message": f"High merge conflict rate "
                f"({merge_metrics.conflict_rate * 100:.1f}%)",  # type: ignore[untyped]
            }
        )

    if branch_metrics.total_branches > 30:
        warnings.append(
            {
                "repository": repo_name,
                "type": "too_many_branches",
                "severity": "warning",
                "message": f"Excessive branch count "
                f"({branch_metrics.total_branches} branches)",
            }
        )

    if (
        branch_metrics.branches_created > 0
        and branch_metrics.branches_deleted < branch_metrics.branches_created * 0.5
    ):
        warnings.append(
            {
                "repository": repo_name,
                "type": "poor_cleanup",
                "severity": "warning",
                "message": "Poor branch cleanup (many created but few deleted)",
            }
        )

    return warnings


def _scan_large_files(repo_path: Path, size_threshold_mb: float = 1.0) -> list[dict]:
    large_files = []
    threshold_bytes = size_threshold_mb * 1024 * 1024

    try:
        executor = SecureSubprocessExecutor()  # type: ignore
        result = executor.execute_secure(
            command=["git", "ls-files"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        for file_path in result.stdout.strip().split("\n"):
            if not file_path:
                continue

            full_path = repo_path / file_path
            if full_path.is_file():
                try:
                    size = full_path.stat().st_size
                    if size >= threshold_bytes:
                        large_files.append(
                            {
                                "repository": repo_path.name,
                                "path": file_path,
                                "size_mb": round(size / (1024 * 1024), 2),
                                "severity": "critical"
                                if size > 5 * threshold_bytes
                                else "warning",
                            }
                        )
                except Exception:
                    continue

    except Exception as e:
        logger.debug(f"Could not detect large files for {repo_path}: {e}")

    return large_files[:20]


def _scan_stale_branches(repo_path: Path) -> list[dict]:
    stale_branches = []

    try:
        executor = SecureSubprocessExecutor()  # type: ignore
        result = executor.execute_secure(
            command=[
                "git",
                "branch",
                "-v",
                "--format=%(refname: short)%09%(committerdate: iso8601)",
            ],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        period_end = datetime.now()
        stale_threshold_days = 90

        for line in result.stdout.strip().split("\n"):
            if not line or "\t" not in line:
                continue

            branch_name, date_str = line.split("\t", 1)
            if branch_name == "*" or not branch_name.strip():
                continue

            try:
                commit_date = datetime.fromisoformat(date_str.split("+")[0].strip())
                days_since = (period_end - commit_date).days

                if days_since > stale_threshold_days:
                    stale_branches.append(
                        {
                            "repository": repo_path.name,
                            "branch": branch_name.strip(),
                            "age_days": days_since,
                            "last_commit_date": date_str,
                            "severity": "critical" if days_since > 180 else "warning",
                        }
                    )
            except (ValueError, IndexError):
                continue

    except Exception as e:
        logger.debug(f"Could not detect stale branches for {repo_path}: {e}")

    return stale_branches[:20]


def _calculate_health_trend(current_metrics: Any, previous_metrics: Any) -> str:  # type: ignore
    current_commits = current_metrics.total_commits
    previous_commits = previous_metrics.total_commits

    current_compliance = current_metrics.conventional_compliance_rate
    previous_compliance = previous_metrics.conventional_compliance_rate

    commit_change = (
        (current_commits - previous_commits) / previous_commits
        if previous_commits > 0
        else 0
    )
    compliance_change = current_compliance - previous_compliance

    if commit_change > 0.2 and compliance_change > 0.1:
        return "improving"
    elif commit_change < -0.2 or compliance_change < -0.1:
        return "declining"
    else:
        return "stable"


def _aggregate_portfolio_health(health_data: list[dict]) -> dict:
    if not health_data:
        return {
            "overall_score": 0.0,
            "avg_activity": 0.0,
            "avg_quality": 0.0,
            "avg_workflow": 0.0,
            "avg_hygiene": 0.0,
            "grade_distribution": {},
        }

    overall_scores = [r["overall_health"] for r in health_data]
    activity_scores = [r["component_scores"]["activity"] for r in health_data]
    quality_scores = [r["component_scores"]["quality"] for r in health_data]
    workflow_scores = [r["component_scores"]["workflow"] for r in health_data]
    hygiene_scores = [r["component_scores"]["hygiene"] for r in health_data]

    grade_counts: dict[str, int] = {}
    for r in health_data:
        grade = r["grade"]
        grade_counts[grade] = grade_counts.get(grade, 0) + 1

    return {
        "overall_score": round(sum(overall_scores) / len(overall_scores), 1),
        "avg_activity": round(sum(activity_scores) / len(activity_scores), 1),
        "avg_quality": round(sum(quality_scores) / len(quality_scores), 1),
        "avg_workflow": round(sum(workflow_scores) / len(workflow_scores), 1),
        "avg_hygiene": round(sum(hygiene_scores) / len(hygiene_scores), 1),
        "grade_distribution": grade_counts,
    }


def _analyze_portfolio_trends(health_data: list[dict]) -> dict:
    if not health_data:
        return {"improving": 0, "stable": 0, "declining": 0, "unknown": 0}

    trend_counts = {"improving": 0, "stable": 0, "declining": 0, "unknown": 0}

    for repo in health_data:
        trend = repo["trend"]
        trend_counts[trend] = trend_counts.get(trend, 0) + 1

    return trend_counts


def _categorize_warnings(warnings: list[dict]) -> dict:
    grouped: dict[str, int] = {}
    for warning in warnings:
        warning_type = warning["type"]
        grouped[warning_type] = grouped.get(warning_type, 0) + 1
    return grouped


def _build_activity_breakdown(health_data: list[dict]) -> dict:
    return {
        "high_performers": len(
            [r for r in health_data if r["component_scores"]["activity"] >= 80]
        ),
        "healthy": len(
            [r for r in health_data if 60 <= r["component_scores"]["activity"] < 80]
        ),
        "needs_attention": len(
            [r for r in health_data if r["component_scores"]["activity"] < 60]
        ),
        "average_activity": round(
            sum(r["component_scores"]["activity"] for r in health_data)
            / len(health_data),
            1,
        )
        if health_data
        else 0.0,
    }


def _build_quality_breakdown(health_data: list[dict]) -> dict:
    return {
        "high_performers": len(
            [r for r in health_data if r["component_scores"]["quality"] >= 80]
        ),
        "healthy": len(
            [r for r in health_data if 60 <= r["component_scores"]["quality"] < 80]
        ),
        "needs_attention": len(
            [r for r in health_data if r["component_scores"]["quality"] < 60]
        ),
        "average_quality": round(
            sum(r["component_scores"]["quality"] for r in health_data)
            / len(health_data),
            1,
        )
        if health_data
        else 0.0,
    }


def _build_workflow_breakdown(health_data: list[dict]) -> dict:
    return {
        "high_performers": len(
            [r for r in health_data if r["component_scores"]["workflow"] >= 80]
        ),
        "healthy": len(
            [r for r in health_data if 60 <= r["component_scores"]["workflow"] < 80]
        ),
        "needs_attention": len(
            [r for r in health_data if r["component_scores"]["workflow"] < 60]
        ),
        "average_workflow": round(
            sum(r["component_scores"]["workflow"] for r in health_data)
            / len(health_data),
            1,
        )
        if health_data
        else 0.0,
    }


def _build_hygiene_breakdown(health_data: list[dict]) -> dict:
    return {
        "high_performers": len(
            [r for r in health_data if r["component_scores"]["hygiene"] >= 80]
        ),
        "healthy": len(
            [r for r in health_data if 60 <= r["component_scores"]["hygiene"] < 80]
        ),
        "needs_attention": len(
            [r for r in health_data if r["component_scores"]["hygiene"] < 60]
        ),
        "average_hygiene": round(
            sum(r["component_scores"]["hygiene"] for r in health_data)
            / len(health_data),
            1,
        )
        if health_data
        else 0.0,
    }


def _health_score_to_grade(score: float) -> str:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def _create_health_recommendations(
    health_data: list[dict],
    warnings: list[dict],
    large_files: list[dict],
    stale_branches: list[dict],
) -> list[dict]:
    recommendations = []

    low_activity_count = len(
        [r for r in health_data if r["component_scores"]["activity"] < 60]
    )
    if low_activity_count > 0:
        recommendations.append(
            {
                "category": "activity",
                "priority": "high"
                if low_activity_count > len(health_data) * 0.5
                else "medium",
                "recommendation": f"{low_activity_count} repositories have low activity - "
                f"review CI/CD bottlenecks",
                "expected_impact": "Improved velocity and developer engagement",
                "affected_repositories": low_activity_count,
            }
        )

    low_compliance_count = len(
        [r for r in health_data if r["metrics"]["commits"]["conventional_rate"] < 70]
    )
    if low_compliance_count > 0:
        recommendations.append(
            {
                "category": "quality",
                "priority": "high",
                "recommendation": f"{low_compliance_count} repositories have low "
                f"conventional compliance - implement commit linting",
                "expected_impact": "Better changelogs and commit clarity",
                "affected_repositories": low_compliance_count,
            }
        )

    high_conflict_repos = [
        r for r in health_data if r["metrics"]["merges"]["conflict_rate"] > 15
    ]
    if high_conflict_repos:
        recommendations.append(
            {
                "category": "workflow",
                "priority": "critical",
                "recommendation": f"{len(high_conflict_repos)} repositories have high "
                f"conflict rates - consider feature flags",
                "expected_impact": "Reduced merge time and conflicts",
                "affected_repositories": len(high_conflict_repos),
            }
        )

    if stale_branches:
        critical_stale = len([b for b in stale_branches if b["severity"] == "critical"])
        recommendations.append(
            {
                "category": "hygiene",
                "priority": "high" if critical_stale > 0 else "medium",
                "recommendation": f"{len(stale_branches)} stale branches detected "
                f"({critical_stale} critical) - implement branch cleanup policy",
                "expected_impact": "Cleaner repository and reduced confusion",
                "affected_repositories": len(
                    set(b["repository"] for b in stale_branches)
                ),
            }
        )

    if large_files:
        critical_large = len([f for f in large_files if f["severity"] == "critical"])
        recommendations.append(
            {
                "category": "code_quality",
                "priority": "high" if critical_large > 0 else "low",
                "recommendation": f"{len(large_files)} large files detected - "
                f"consider Git LFS or refactoring",
                "expected_impact": "Smaller repository size and faster clones",
                "affected_repositories": len(set(f["repository"] for f in large_files)),
            }
        )

    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 4))  # type: ignore

    return recommendations[:15]


__all__ = ["mcp"]


def _analyze_workflow_patterns(repo_workflow_data: list[dict]) -> dict:
    if not repo_workflow_data:
        return {}

    velocity_data = [r["velocity"] for r in repo_workflow_data]

    avg_velocity = sum(r.avg_commits_per_day for r in velocity_data) / len(
        velocity_data
    )
    avg_compliance = sum(r.conventional_compliance_rate for r in velocity_data) / len(
        velocity_data
    )
    avg_conflict_rate = sum(r.merge_conflict_rate for r in velocity_data) / len(
        velocity_data
    )

    velocity_variance = max(r.avg_commits_per_day for r in velocity_data) - min(
        r.avg_commits_per_day for r in velocity_data
    )

    high_velocity_repos = [
        r for r in velocity_data if r.avg_commits_per_day > avg_velocity
    ]
    low_velocity_repos = [
        r for r in velocity_data if r.avg_commits_per_day < avg_velocity * 0.5
    ]
    high_conflict_repos = [r for r in velocity_data if r.merge_conflict_rate > 0.15]

    branch_metrics_data = [
        r["branch_metrics"]
        for r in repo_workflow_data
        if r.get("branch_metrics") is not None
    ]

    if branch_metrics_data:
        avg_branch_lifetime = sum(
            bm.avg_branch_lifetime_hours for bm in branch_metrics_data
        ) / len(branch_metrics_data)
        active_branches_ratio = (
            sum(bm.active_branches for bm in branch_metrics_data)
            / sum(bm.total_branches for bm in branch_metrics_data)
            if sum(bm.total_branches for bm in branch_metrics_data) > 0
            else 0
        )
    else:
        avg_branch_lifetime = 0.0
        active_branches_ratio = 0.0

    merge_metrics_data = [
        r["merge_metrics"]
        for r in repo_workflow_data
        if r.get("merge_metrics") is not None
    ]

    if merge_metrics_data:
        rebase_ratio = (
            sum(mm.total_rebases for mm in merge_metrics_data)
            / sum(mm.total_merges + mm.total_rebases for mm in merge_metrics_data)
            if merge_metrics_data
            else 0.0
        )
        merge_success_rate = sum(
            mm.merge_success_rate for mm in merge_metrics_data
        ) / len(merge_metrics_data)
    else:
        rebase_ratio = 0.0
        merge_success_rate = 1.0

    return {
        "velocity_patterns": {
            "portfolio_avg_velocity": round(avg_velocity, 2),
            "velocity_variance": round(velocity_variance, 2),
            "high_velocity_count": len(high_velocity_repos),
            "low_velocity_count": len(low_velocity_repos),
            "velocity_distribution": "balanced"
            if velocity_variance < avg_velocity
            else "high_variance",
        },
        "quality_patterns": {
            "conventional_compliance_rate": round(avg_compliance * 100, 1),
            "merge_conflict_rate": round(avg_conflict_rate * 100, 2),
            "high_conflict_count": len(high_conflict_repos),
        },
        "branch_patterns": {
            "avg_branch_lifetime_hours": round(avg_branch_lifetime, 1),
            "active_branches_ratio": round(active_branches_ratio * 100, 1),
            "long_lived_branches": avg_branch_lifetime > 168,
        },
        "merge_patterns": {
            "rebase_ratio": round(rebase_ratio * 100, 1),
            "merge_success_rate": round(merge_success_rate * 100, 1),
            "merge_strategy": "rebase_heavy" if rebase_ratio > 0.6 else "merge_heavy",
        },
    }


def _identify_workflow_bottlenecks(repo_workflow_data: list[dict]) -> list[dict]:
    bottlenecks = []

    for repo_data in repo_workflow_data:
        velocity = repo_data["velocity"]
        merge_metrics = repo_data.get("merge_metrics")
        branch_metrics = repo_data.get("branch_metrics")

        repo_bottlenecks = []

        if merge_metrics and merge_metrics.merge_success_rate < 0.85:
            repo_bottlenecks.append(
                {
                    "type": "low_merge_success_rate",
                    "severity": "high"
                    if merge_metrics.merge_success_rate < 0.7
                    else "medium",
                    "value": round(merge_metrics.merge_success_rate * 100, 1),
                    "description": "Low merge success rate indicates frequent conflicts",
                }
            )

        if merge_metrics and merge_metrics.conflict_rate > 0.15:
            repo_bottlenecks.append(
                {
                    "type": "high_conflict_rate",
                    "severity": "high"
                    if merge_metrics.conflict_rate > 0.25
                    else "medium",
                    "value": round(merge_metrics.conflict_rate * 100, 1),
                    "description": "High conflict rate slowing integration",
                }
            )

        if branch_metrics and branch_metrics.avg_branch_lifetime_hours > 168:
            repo_bottlenecks.append(
                {
                    "type": "long_lived_branches",
                    "severity": "medium",
                    "value": round(branch_metrics.avg_branch_lifetime_hours, 1),
                    "description": "Branches living >1 week indicate delayed integration",
                }
            )

        if velocity.avg_commits_per_day < 1.0:
            repo_bottlenecks.append(
                {
                    "type": "low_velocity",
                    "severity": "medium",
                    "value": round(velocity.avg_commits_per_day, 2),
                    "description": "Low commit velocity indicates workflow bottlenecks",
                }
            )

        if velocity.conventional_compliance_rate < 0.5:
            repo_bottlenecks.append(
                {
                    "type": "poor_commit_discipline",
                    "severity": "low",
                    "value": round(velocity.conventional_compliance_rate * 100, 1),
                    "description": "Low conventional compliance reduces traceability",
                }
            )

        if repo_bottlenecks:
            bottlenecks.append(
                {
                    "repository": velocity.repository_name,
                    "path": velocity.repository_path,
                    "health_score": round(velocity.health_score, 1),
                    "bottlenecks": repo_bottlenecks,
                }
            )

    return bottlenecks


def _correlate_quality_metrics(repo_workflow_data: list[dict]) -> dict:
    if not repo_workflow_data:
        return {}

    correlations = []

    for repo_data in repo_workflow_data:
        velocity = repo_data["velocity"]
        merge_metrics = repo_data.get("merge_metrics")

        correlation_item = {
            "repository": velocity.repository_name,
            "health_score": velocity.health_score,
            "velocity": velocity.avg_commits_per_day,
            "compliance": velocity.conventional_compliance_rate,
            "conflict_rate": velocity.merge_conflict_rate,
        }

        if merge_metrics:
            correlation_item["merge_success_rate"] = merge_metrics.merge_success_rate
            correlation_item["conflict_files_count"] = len(
                merge_metrics.most_conflicted_files
            )

        correlations.append(correlation_item)

    high_health = [c for c in correlations if c["health_score"] >= 70]
    low_health = [c for c in correlations if c["health_score"] < 50]

    if high_health and low_health:
        avg_velocity_high = sum(c["velocity"] for c in high_health) / len(high_health)
        avg_velocity_low = sum(c["velocity"] for c in low_health) / len(low_health)

        avg_conflict_high = sum(c["conflict_rate"] for c in high_health) / len(
            high_health
        )
        avg_conflict_low = sum(c["conflict_rate"] for c in low_health) / len(low_health)

        insights = []
        if avg_velocity_high > avg_velocity_low * 1.5:
            insights.append(
                f"High-health repos have {avg_velocity_high / avg_velocity_low:.1f}x higher velocity"
            )

        if avg_conflict_high < avg_conflict_low * 0.7:
            insights.append(
                f"High-health repos have {avg_conflict_low / avg_conflict_high:.1f}x lower conflict rate"
            )
    else:
        insights = ["Insufficient data for correlation analysis"]

    return {
        "correlations": correlations,
        "insights": insights,
        "summary": {
            "high_health_count": len(high_health),
            "low_health_count": len(low_health),
            "avg_health_score": round(
                sum(c["health_score"] for c in correlations) / len(correlations), 1
            )
            if correlations
            else 0.0,
        },
    }


def _generate_workflow_recommendations(
    workflow_analysis: dict,
    bottlenecks: list[dict],
    quality_correlation: dict | None,
) -> list[dict]:
    recommendations = []

    velocity_patterns = workflow_analysis.get("velocity_patterns", {})
    quality_patterns = workflow_analysis.get("quality_patterns", {})
    branch_patterns = workflow_analysis.get("branch_patterns", {})
    merge_patterns = workflow_analysis.get("merge_patterns", {})

    if velocity_patterns.get("low_velocity_count", 0) > 0:
        low_velocity_count = velocity_patterns["low_velocity_count"]
        recommendations.append(
            {
                "category": "velocity_improvement",
                "title": "Address Low-Velocity Repositories",
                "description": f"{low_velocity_count} repos show low commit velocity",
                "actions": [
                    "Review CI/CD pipeline bottlenecks",
                    "Implement automated testing to reduce manual QA delays",
                    "Consider smaller, more frequent PRs",
                    "Establish code review SLAs",
                ],
                "expected_impact": {
                    "velocity_improvement": "+40%",
                    "quality_improvement": "+10%",
                    "implementation_effort": "medium",
                    "priority_score": 85,
                },
                "affected_repositories": low_velocity_count,
            }
        )

    if quality_patterns.get("high_conflict_count", 0) > 0:
        high_conflict_count = quality_patterns["high_conflict_count"]
        recommendations.append(
            {
                "category": "conflict_reduction",
                "title": "Reduce Merge Conflicts",
                "description": f"{high_conflict_count} repos experience high conflict rates",
                "actions": [
                    "Implement feature flagging for parallel development",
                    "Adapt trunk-based development for reduced branch lifetime",
                    "Establish clear ownership boundaries",
                    "Increase communication on upcoming changes",
                ],
                "expected_impact": {
                    "velocity_improvement": "+25%",
                    "quality_improvement": "+15%",
                    "implementation_effort": "high",
                    "priority_score": 80,
                },
                "affected_repositories": high_conflict_count,
            }
        )

    if branch_patterns.get("long_lived_branches", False):
        recommendations.append(
            {
                "category": "branch_management",
                "title": "Implement Short-Lived Branch Strategy",
                "description": "Branches exceed 1 week lifetime on average",
                "actions": [
                    "Set branch lifetime limits (e.g., 7 days max)",
                    "Automate stale branch notifications",
                    "Encourage trunk-based development",
                    "Implement feature flags instead of long branches",
                ],
                "expected_impact": {
                    "velocity_improvement": "+35%",
                    "quality_improvement": "+20%",
                    "implementation_effort": "medium",
                    "priority_score": 90,
                },
                "affected_repositories": "all",
            }
        )

    if quality_patterns.get("conventional_compliance_rate", 0) < 70:
        compliance_rate = quality_patterns["conventional_compliance_rate"]
        recommendations.append(
            {
                "category": "commit_discipline",
                "title": "Enforce Conventional Commits",
                "description": f"Portfolio compliance at {compliance_rate}% below target",
                "actions": [
                    "Install commitlint hooks",
                    "Add commit message validation to CI/CD",
                    "Train team on conventional commit format",
                    "Provide commit message templates",
                ],
                "expected_impact": {
                    "velocity_improvement": "+10%",
                    "quality_improvement": "+25%",
                    "implementation_effort": "low",
                    "priority_score": 75,
                },
                "affected_repositories": "all",
            }
        )

    if merge_patterns.get("rebase_ratio", 0) < 0.3:
        recommendations.append(
            {
                "category": "merge_strategy",
                "title": "Consider Rebase Workflow",
                "description": "Low rebase usage may contribute to merge complexity",
                "actions": [
                    "Evaluate rebase vs. merge trade-offs",
                    "Train team on rebase conflict resolution",
                    "Enable rebase by default for feature branches",
                    "Document rebase workflow guidelines",
                ],
                "expected_impact": {
                    "velocity_improvement": "+15%",
                    "quality_improvement": "+10%",
                    "implementation_effort": "low",
                    "priority_score": 65,
                },
                "affected_repositories": "all",
            }
        )

    if velocity_patterns.get("velocity_distribution") == "high_variance":
        recommendations.append(
            {
                "category": "standardization",
                "title": "Standardize Workflow Across Repositories",
                "description": "High velocity variance indicates inconsistent workflows",
                "actions": [
                    "Document target workflow patterns",
                    "Share CI/CD templates across repos",
                    "Establish portfolio-wide branch policies",
                    "Create workflow adoption checklist",
                ],
                "expected_impact": {
                    "velocity_improvement": "+20%",
                    "quality_improvement": "+15%",
                    "implementation_effort": "high",
                    "priority_score": 70,
                },
                "affected_repositories": "all",
            }
        )

    for bottleneck_group in bottlenecks:
        repo_name = bottleneck_group["repository"]
        for bottleneck in bottleneck_group["bottlenecks"]:
            if bottleneck["type"] == "low_merge_success_rate":
                recommendations.append(
                    {
                        "category": "merge_optimization",
                        "title": f"Improve Merge Success: {repo_name}",
                        "description": bottleneck["description"],
                        "actions": [
                            "Increase test coverage to catch integration issues early",
                            "Implement pre-merge validation checks",
                            "Schedule regular integration sessions",
                            "Use pull request templates for clarity",
                        ],
                        "expected_impact": {
                            "velocity_improvement": "+30%",
                            "quality_improvement": "+20%",
                            "implementation_effort": "medium",
                            "priority_score": 82,
                        },
                        "affected_repositories": repo_name,
                    }
                )

    if quality_correlation and quality_correlation.get("insights"):
        for insight in quality_correlation["insights"]:
            if "velocity" in insight.lower() and "health" in insight.lower():
                recommendations.append(
                    {
                        "category": "health_improvement",
                        "title": "Leverage Velocity-Health Correlation",
                        "description": insight,
                        "actions": [
                            "Analyze high-velocity repos for best practices",
                            "Adopt successful workflow patterns",
                            "Monitor health scores as leading indicators",
                            "Set velocity targets aligned with health goals",
                        ],
                        "expected_impact": {
                            "velocity_improvement": "+20%",
                            "quality_improvement": "+25%",
                            "implementation_effort": "medium",
                            "priority_score": 78,
                        },
                        "affected_repositories": "low_health",
                    }
                )
                break

    recommendations.sort(
        key=lambda r: r["expected_impact"]["priority_score"], reverse=True
    )

    for i, rec in enumerate(recommendations, 1):
        rec["rank"] = i
        rec["expected_impact"]["priority_level"] = (
            "critical"
            if rec["expected_impact"]["priority_score"] >= 85
            else "high"
            if rec["expected_impact"]["priority_score"] >= 75
            else "medium"
        )

    return recommendations
