"""Tests for ``crackerjack.mcp.tools.mahavishnu_tools``.

The module exposes four MCP tool wrappers around the Mahavishnu aggregator.
We mock the aggregator at the module boundary (the module-level cache is
reset between tests) and exercise the result-shaping logic, validation,
and error paths.
"""

from __future__ import annotations

import typing as t
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.integration.mahavishnu_integration import (
    CrossProjectDashboard,
    CrossProjectPattern,
    RepositoryHealth,
    RepositoryVelocity,
)
from crackerjack.mcp.tools import mahavishnu_tools
from crackerjack.mcp.tools.mahavishnu_tools import (
    get_cross_project_git_dashboard,
    get_cross_project_patterns,
    get_repository_health,
    get_velocity_comparison,
)


# ─── helpers ─────────────────────────────────────────────────────────────────


def _velocity(
    name: str = "crackerjack",
    path: str = "/Users/les/Projects/crackerjack",
    total_commits: int = 50,
    avg_per_day: float = 2.5,
    avg_per_week: float = 17.5,
    compliance: float = 0.8,
    breaking: int = 1,
    conflict_rate: float = 0.05,
    health: float = 70.0,
    trend: t.Literal["increasing", "stable", "decreasing"] = "stable",
) -> RepositoryVelocity:
    now = datetime.now()
    return RepositoryVelocity(
        repository_path=path,
        repository_name=name,
        period_start=now,
        period_end=now,
        total_commits=total_commits,
        avg_commits_per_day=avg_per_day,
        avg_commits_per_week=avg_per_week,
        conventional_compliance_rate=compliance,
        breaking_changes=breaking,
        merge_conflict_rate=conflict_rate,
        health_score=health,
        trend_direction=trend,
    )


def _pattern(
    pattern_type: str = "declining_velocity",
    severity: t.Literal["info", "warning", "critical"] = "warning",
    description: str = "desc",
    metric_value: float = 1.5,
    affected: list[str] | None = None,
    recommendation: str = "rec",
) -> CrossProjectPattern:
    return CrossProjectPattern(
        pattern_type=pattern_type,
        affected_repositories=affected or ["/path/a", "/path/b"],
        severity=severity,
        description=description,
        metric_value=metric_value,
        recommendation=recommendation,
        detected_at=datetime.now(),
    )


def _dashboard(
    repos: list[RepositoryVelocity] | None = None,
    patterns: list[CrossProjectPattern] | None = None,
    top: list[str] | None = None,
    needs: list[str] | None = None,
    period_days: int = 30,
) -> CrossProjectDashboard:
    repos = repos if repos is not None else [_velocity()]
    return CrossProjectDashboard(
        generated_at=datetime.now(),
        total_repositories=len(repos),
        period_days=period_days,
        repositories=repos,
        aggregate_metrics={
            "total_commits": 100,
            "avg_commits_per_day": 3.3,
            "avg_health_score": 80.0,
            "total_conflicts": 0.15,
        },
        top_performers=(
            top
            if top is not None
            else ["/Users/les/Projects/crackerjack"]
        ),
        needs_attention=needs if needs is not None else [],
        cross_project_patterns=patterns if patterns is not None else [],
    )


def _health(
    repo_path: str = "/tmp/repo",
    health_score: float = 85.0,
    risk: t.Literal["low", "medium", "high", "critical"] = "low",
    stale: list[str] | None = None,
    unmerged: int = 0,
    large_files: list[str] | None = None,
    last_activity: datetime | None = None,
    recommendations: list[str] | None = None,
) -> RepositoryHealth:
    return RepositoryHealth(
        repository_path=repo_path,
        repository_name=Path(repo_path).name,
        stale_branches=stale or [],
        unmerged_prs=unmerged,
        large_files=large_files or [],
        last_activity=last_activity,
        health_score=health_score,
        risk_level=risk,
        recommendations=recommendations or ["ok"],
    )


@pytest.fixture(autouse=True)
def _reset_aggregator_cache() -> t.Generator[None, None, None]:
    """Reset the module-level aggregator cache so each test gets a fresh one."""
    saved = mahavishnu_tools._aggregator
    mahavishnu_tools._aggregator = None
    try:
        yield
    finally:
        mahavishnu_tools._aggregator = saved


# ─── get_cross_project_git_dashboard ────────────────────────────────────────


@pytest.mark.unit
class TestGetCrossProjectGitDashboard:
    def test_returns_summary_aggregate_and_repositories(self) -> None:
        repos = [
            _velocity(name="a", path="/p/a", total_commits=10),
            _velocity(name="b", path="/p/b", total_commits=20, health=40.0),
        ]
        dashboard = _dashboard(
            repos=repos,
            patterns=[_pattern()],
            top=["/p/a"],
            needs=["/p/b"],
        )
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_cross_project_git_dashboard = AsyncMock(
                return_value=dashboard
            )
            result = get_cross_project_git_dashboard(
                project_paths=["/p/a", "/p/b"],
                days_back=7,
            )

        assert result["summary"]["total_repositories"] == 2
        # dashboard.period_days is what the tool returns; the input days_back
        # is forwarded to the aggregator (the dashboard carries its own value)
        assert result["summary"]["period_days"] == 30
        assert result["aggregate_metrics"]["total_commits"] == 100
        assert isinstance(result["aggregate_metrics"]["avg_commits_per_day"], float)
        assert len(result["repositories"]) == 2
        repo0 = result["repositories"][0]
        assert repo0["name"] == "a"
        assert repo0["path"] == "/p/a"
        assert repo0["commits"] == 10
        assert isinstance(repo0["conventional_compliance"], float)
        assert isinstance(repo0["health_score"], float)
        assert repo0["trend"] == "stable"

    def test_top_performers_and_needs_attention_use_path_basename(self) -> None:
        dashboard = _dashboard(
            repos=[_velocity()],
            top=["/Users/les/Projects/crackerjack"],
            needs=["/Users/les/Projects/mahavishnu"],
        )
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_cross_project_git_dashboard = AsyncMock(
                return_value=dashboard
            )
            result = get_cross_project_git_dashboard(project_paths=["/p/a"])

        assert result["top_performers"][0] == {
            "path": "/Users/les/Projects/crackerjack",
            "name": "crackerjack",
        }
        assert result["needs_attention"][0]["name"] == "mahavishnu"

    def test_patterns_are_serialized_with_affected_paths(self) -> None:
        pattern = _pattern(
            pattern_type="high_conflicts",
            severity="critical",
            affected=["/p/x", "/p/y"],
            description="lots of conflicts",
        )
        dashboard = _dashboard(repos=[_velocity()], patterns=[pattern])
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_cross_project_git_dashboard = AsyncMock(
                return_value=dashboard
            )
            result = get_cross_project_git_dashboard(project_paths=["/p/x"])

        assert len(result["patterns"]) == 1
        pat = result["patterns"][0]
        assert pat["type"] == "high_conflicts"
        assert pat["severity"] == "critical"
        assert pat["description"] == "lots of conflicts"
        assert "recommendation" in pat
        assert pat["affected_repositories"][0]["name"] == "x"

    def test_empty_repos_returns_zero_totals(self) -> None:
        dashboard = _dashboard(repos=[], patterns=[], top=[], needs=[])
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_cross_project_git_dashboard = AsyncMock(
                return_value=dashboard
            )
            result = get_cross_project_git_dashboard(project_paths=[])

        assert result["summary"]["total_repositories"] == 0
        assert result["repositories"] == []
        assert result["top_performers"] == []
        assert result["patterns"] == []

    def test_aggregator_error_propagates(self) -> None:
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_cross_project_git_dashboard = AsyncMock(
                side_effect=RuntimeError("db down")
            )
            with pytest.raises(RuntimeError, match="db down"):
                get_cross_project_git_dashboard(project_paths=["/p/a"])

    def test_days_back_validation_rejects_zero(self) -> None:
        with pytest.raises(Exception):
            # pydantic ValidationError from validate_call on ge=1
            get_cross_project_git_dashboard(project_paths=["/p/a"], days_back=0)


# ─── get_repository_health ──────────────────────────────────────────────────


@pytest.mark.unit
class TestGetRepositoryHealth:
    def test_returns_health_payload(self, tmp_path: Path) -> None:
        repo = tmp_path
        (repo / ".git").mkdir()
        health = _health(
            repo_path=str(repo),
            health_score=88.0,
            risk="low",
            stale=["feature/old"],
            unmerged=2,
            large_files=["big.bin"],
            last_activity=datetime(2026, 1, 1, 12, 0, 0),
            recommendations=["merge stale PRs"],
        )
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_repository_health = AsyncMock(
                return_value=health
            )
            result = get_repository_health(repo_path=str(repo))

        assert result["repository_name"] == repo.name
        assert result["health_score"] == 88.0
        assert result["risk_level"] == "low"
        assert result["indicators"]["stale_branches"] == 1
        assert result["indicators"]["unmerged_prs"] == 2
        assert result["indicators"]["large_files"] == 1
        assert result["indicators"]["last_activity"] == "2026-01-01T12:00:00"
        assert result["details"]["stale_branches"] == ["feature/old"]
        assert result["recommendations"] == ["merge stale PRs"]

    def test_last_activity_none_when_missing(self, tmp_path: Path) -> None:
        repo = tmp_path
        (repo / ".git").mkdir()
        health = _health(repo_path=str(repo), last_activity=None)
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_repository_health = AsyncMock(
                return_value=health
            )
            result = get_repository_health(repo_path=str(repo))

        assert result["indicators"]["last_activity"] is None

    def test_non_git_repository_raises_value_error(
        self, tmp_path: Path
    ) -> None:
        # tmp_path has no .git directory
        with pytest.raises(ValueError, match="Not a git repository"):
            get_repository_health(repo_path=str(tmp_path))

    def test_aggregator_error_propagates(self, tmp_path: Path) -> None:
        repo = tmp_path
        (repo / ".git").mkdir()
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_repository_health = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            with pytest.raises(RuntimeError, match="boom"):
                get_repository_health(repo_path=str(repo))


# ─── get_cross_project_patterns ─────────────────────────────────────────────


@pytest.mark.unit
class TestGetCrossProjectPatterns:
    def test_returns_patterns_payload(self) -> None:
        patterns = [
            _pattern(pattern_type="declining_velocity", severity="warning"),
            _pattern(
                pattern_type="poor_compliance",
                severity="info",
                affected=["/p/c"],
                metric_value=0.42,
            ),
        ]
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_cross_project_patterns = AsyncMock(
                return_value=patterns
            )
            result = get_cross_project_patterns(
                project_paths=["/p/a", "/p/b", "/p/c"],
                days_back=14,
            )

        assert result["summary"]["total_patterns"] == 2
        assert result["summary"]["period_days"] == 14
        assert result["summary"]["repositories_analyzed"] == 3
        assert result["patterns"][0]["type"] == "declining_velocity"
        assert result["patterns"][0]["affected_repositories"][0]["name"] == "a"
        assert isinstance(result["patterns"][1]["metric_value"], float)
        assert "detected_at" in result["patterns"][0]

    def test_empty_patterns(self) -> None:
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_cross_project_patterns = AsyncMock(
                return_value=[]
            )
            result = get_cross_project_patterns(project_paths=["/p/a"])

        assert result["summary"]["total_patterns"] == 0
        assert result["patterns"] == []

    def test_aggregator_error_propagates(self) -> None:
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value.get_cross_project_patterns = AsyncMock(
                side_effect=ValueError("invalid input")
            )
            with pytest.raises(ValueError, match="invalid input"):
                get_cross_project_patterns(project_paths=["/p/a"])

    def test_days_back_validation_rejects_too_large(self) -> None:
        with pytest.raises(Exception):
            get_cross_project_patterns(project_paths=["/p/a"], days_back=400)


# ─── get_velocity_comparison ────────────────────────────────────────────────


@pytest.mark.unit
class TestGetVelocityComparison:
    def test_increasing_trend(self, tmp_path: Path) -> None:
        repo = tmp_path
        (repo / ".git").mkdir()
        current = _velocity(total_commits=80, avg_per_day=4.0, avg_per_week=28.0)
        previous = _velocity(total_commits=20, avg_per_day=1.0, avg_per_week=7.0)
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value._collect_repository_velocity = AsyncMock(
                side_effect=[current, previous]
            )
            result = get_velocity_comparison(
                repo_path=str(repo), compare_period_days=30
            )

        assert result["trend"] == "increasing"
        assert result["current_period"]["commits"] == 80
        assert result["previous_period"]["commits"] == 20
        assert result["change"]["commits"] == 60
        assert isinstance(result["change"]["commits_percent"], float)
        assert isinstance(result["change"]["velocity"], float)
        assert isinstance(result["change"]["velocity_percent"], float)
        assert result["period_days"] == 30

    def test_decreasing_trend(self, tmp_path: Path) -> None:
        repo = tmp_path
        (repo / ".git").mkdir()
        current = _velocity(total_commits=5, avg_per_day=0.1, avg_per_week=0.7)
        previous = _velocity(total_commits=80, avg_per_day=4.0, avg_per_week=28.0)
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value._collect_repository_velocity = AsyncMock(
                side_effect=[current, previous]
            )
            result = get_velocity_comparison(
                repo_path=str(repo), compare_period_days=30
            )

        assert result["trend"] == "decreasing"

    def test_stable_trend_when_difference_small(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path
        (repo / ".git").mkdir()
        current = _velocity(total_commits=30, avg_per_day=1.0, avg_per_week=7.0)
        previous = _velocity(total_commits=29, avg_per_day=0.95, avg_per_week=6.65)
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value._collect_repository_velocity = AsyncMock(
                side_effect=[current, previous]
            )
            result = get_velocity_comparison(
                repo_path=str(repo), compare_period_days=30
            )

        assert result["trend"] == "stable"

    def test_zero_previous_commits_yields_zero_percent(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path
        (repo / ".git").mkdir()
        current = _velocity(total_commits=10, avg_per_day=0.5, avg_per_week=3.5)
        previous = _velocity(total_commits=0, avg_per_day=0.0, avg_per_week=0.0)
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value._collect_repository_velocity = AsyncMock(
                side_effect=[current, previous]
            )
            result = get_velocity_comparison(
                repo_path=str(repo), compare_period_days=30
            )

        assert result["change"]["commits_percent"] == 0
        assert result["change"]["velocity_percent"] == 0

    def test_non_git_repository_raises_value_error(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="Not a git repository"):
            get_velocity_comparison(
                repo_path=str(tmp_path), compare_period_days=30
            )

    def test_aggregator_error_propagates(self, tmp_path: Path) -> None:
        repo = tmp_path
        (repo / ".git").mkdir()
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools._get_aggregator"
        ) as mock_get:
            mock_get.return_value._collect_repository_velocity = AsyncMock(
                side_effect=RuntimeError("metrics offline")
            )
            with pytest.raises(RuntimeError, match="metrics offline"):
                get_velocity_comparison(
                    repo_path=str(repo), compare_period_days=30
                )

    def test_compare_period_days_validation(self) -> None:
        with pytest.raises(Exception):
            # pydantic ValidationError from validate_call on ge=1
            get_velocity_comparison(
                repo_path="/tmp/nope", compare_period_days=0
            )


# ─── module surface ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestModuleSurface:
    def test_mcp_server_is_registered(self) -> None:
        from mcp.server import FastMCP

        assert isinstance(mahavishnu_tools.mcp, FastMCP)

    def test_get_aggregator_caches_after_first_call(
        self, tmp_path: Path
    ) -> None:
        # Reset cache, then call _get_aggregator and verify caching.
        mahavishnu_tools._aggregator = None
        with patch(
            "crackerjack.mcp.tools.mahavishnu_tools.create_mahavishnu_aggregator"
        ) as mock_create:
            instance = MagicMock(name="aggregator")
            mock_create.return_value = instance
            a = mahavishnu_tools._get_aggregator()
            b = mahavishnu_tools._get_aggregator()
        assert a is b
        # create is only called once thanks to caching
        assert mock_create.call_count == 1
