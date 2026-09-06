"""Tests for ``crackerjack.mcp.tools.mahavishnu_tools``.

Covers the four FastMCP tool functions and the aggregator singleton. The
``MahavishnuAggregator`` itself is a stub that raises ``NotImplementedError``,
so each tool's success path is tested via a mock aggregator injected into
the module-level ``_aggregator`` global.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import crackerjack.mcp.tools.mahavishnu_tools as mod
from crackerjack.mcp.tools.mahavishnu_tools import (
    _get_aggregator,
    get_cross_project_git_dashboard,
    get_cross_project_patterns,
    get_repository_health,
    get_velocity_comparison,
)


@pytest.fixture(autouse=True)
def _reset_aggregator_singleton() -> None:
    """Reset the module-level aggregator between tests for isolation."""
    saved = mod._aggregator
    mod._aggregator = None
    yield
    mod._aggregator = saved


def _make_dashboard(
    *,
    total_repositories: int = 2,
    period_days: int = 30,
    repositories: list[Any] | None = None,
    top_performers: list[str] | None = None,
    needs_attention: list[str] | None = None,
    cross_project_patterns: list[Any] | None = None,
    aggregate_metrics: dict[str, Any] | None = None,
) -> Any:
    """Build a SimpleNamespace matching the PortfolioDashboard shape."""
    return SimpleNamespace(
        total_repositories=total_repositories,
        period_days=period_days,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        aggregate_metrics=aggregate_metrics
        or {
            "total_commits": 100,
            "avg_commits_per_day": 5.0,
            "avg_health_score": 85.5,
            "total_conflicts": 3,
        },
        repositories=repositories or [],
        top_performers=top_performers or [],
        needs_attention=needs_attention or [],
        cross_project_patterns=cross_project_patterns or [],
    )


def _make_repository_velocity(
    name: str = "repo-a", commits: int = 10, breaking: int = 0
) -> Any:
    return SimpleNamespace(
        repository_name=name,
        repository_path=f"/tmp/{name}",
        total_commits=commits,
        avg_commits_per_day=1.0,
        avg_commits_per_week=7.0,
        conventional_compliance_rate=0.85,
        breaking_changes=breaking,
        merge_conflict_rate=0.05,
        health_score=80.0,
        trend_direction="stable",
    )


def _make_repository_health(score: float = 80.0) -> Any:
    return SimpleNamespace(
        repository_name="repo-a",
        health_score=score,
        risk_level="low",
        stale_branches=[],
        unmerged_prs=0,
        large_files=[],
        last_activity=datetime(2026, 1, 1, tzinfo=UTC),
        recommendations=[],
    )


def _make_pattern() -> Any:
    return SimpleNamespace(
        pattern_type="test-flake",
        severity="warning",
        description="Flaky tests in 3 repos",
        metric_value=0.42,
        affected_repositories=["/tmp/a", "/tmp/b"],
        recommendation="Pin timeouts",
        detected_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_module_exports_mcp_server() -> None:
    from fastmcp import FastMCP

    assert isinstance(mod.mcp, FastMCP)


def test_get_aggregator_creates_default_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """First call to ``_get_aggregator`` builds a default aggregator."""
    from crackerjack.integration.mahavishnu_integration import MahavishnuAggregator

    aggregator = _get_aggregator()
    assert isinstance(aggregator, MahavishnuAggregator)
    # Second call returns the same instance.
    assert _get_aggregator() is aggregator


def test_get_cross_project_git_dashboard_basic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_repository_velocity()
    dashboard = _make_dashboard(repositories=[repo])

    async def _fake_dashboard(paths, days):
        return dashboard

    fake_agg = SimpleNamespace(get_cross_project_git_dashboard=_fake_dashboard)
    monkeypatch.setattr(mod, "_aggregator", fake_agg)

    result = get_cross_project_git_dashboard(
        project_paths=["/tmp/a", "/tmp/b"], days_back=7
    )

    assert result["summary"]["total_repositories"] == 2
    assert result["summary"]["period_days"] == 30
    assert result["aggregate_metrics"]["total_commits"] == 100
    assert result["aggregate_metrics"]["avg_health_score"] == 85.5
    assert result["repositories"][0]["name"] == "repo-a"


def test_get_cross_project_git_dashboard_with_patterns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pattern = _make_pattern()
    dashboard = _make_dashboard(cross_project_patterns=[pattern])

    async def _fake_dashboard(paths, days):
        return dashboard

    fake_agg = SimpleNamespace(get_cross_project_git_dashboard=_fake_dashboard)
    monkeypatch.setattr(mod, "_aggregator", fake_agg)

    result = get_cross_project_git_dashboard(project_paths=["/tmp/a"], days_back=30)
    assert len(result["patterns"]) == 1
    assert result["patterns"][0]["type"] == "test-flake"


def test_get_cross_project_git_dashboard_top_performers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = _make_dashboard(top_performers=["/tmp/a", "/tmp/b"])

    async def _fake_dashboard(paths, days):
        return dashboard

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(get_cross_project_git_dashboard=_fake_dashboard),
    )

    result = get_cross_project_git_dashboard(project_paths=["/tmp/a"], days_back=30)
    assert result["top_performers"][0]["name"] == "a"
    assert result["top_performers"][0]["path"] == "/tmp/a"


def test_get_cross_project_git_dashboard_needs_attention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = _make_dashboard(needs_attention=["/tmp/stale"])

    async def _fake_dashboard(paths, days):
        return dashboard

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(get_cross_project_git_dashboard=_fake_dashboard),
    )

    result = get_cross_project_git_dashboard(project_paths=["/tmp/stale"], days_back=30)
    assert result["needs_attention"][0]["name"] == "stale"


def test_get_cross_project_git_dashboard_raises_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(paths, days):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(get_cross_project_git_dashboard=_boom),
    )

    with pytest.raises(RuntimeError, match="kaboom"):
        get_cross_project_git_dashboard(project_paths=["/tmp/a"], days_back=30)


def test_get_repository_health_rejects_non_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory without ``.git`` raises ValueError."""
    fake_agg = SimpleNamespace()  # shouldn't be called
    monkeypatch.setattr(mod, "_aggregator", fake_agg)

    with pytest.raises(ValueError, match="Not a git repository"):
        get_repository_health(repo_path=str(tmp_path))


def test_get_repository_health_basic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    health = _make_repository_health(score=92.5)

    async def _fake_health(repo):
        return health

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(get_repository_health=_fake_health),
    )

    result = get_repository_health(repo_path=str(tmp_path))
    assert result["health_score"] == 92.5
    assert result["risk_level"] == "low"
    assert result["indicators"]["stale_branches"] == 0


def test_get_repository_health_with_recommendations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    health = SimpleNamespace(
        repository_name="repo-x",
        health_score=70.0,
        risk_level="medium",
        stale_branches=["feature/old"],
        unmerged_prs=2,
        large_files=["big.bin"],
        last_activity=datetime(2026, 1, 1, tzinfo=UTC),
        recommendations=["drop stale branch"],
    )

    async def _fake_health(repo):
        return health

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(get_repository_health=_fake_health),
    )

    result = get_repository_health(repo_path=str(tmp_path))
    assert "drop stale branch" in result["recommendations"]
    assert result["indicators"]["unmerged_prs"] == 2


def test_get_repository_health_no_last_activity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    health = SimpleNamespace(
        repository_name="r",
        health_score=80.0,
        risk_level="low",
        stale_branches=[],
        unmerged_prs=0,
        large_files=[],
        last_activity=None,
        recommendations=[],
    )

    async def _fake_health(repo):
        return health

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(get_repository_health=_fake_health),
    )

    result = get_repository_health(repo_path=str(tmp_path))
    assert result["indicators"]["last_activity"] is None


def test_get_cross_project_patterns_basic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pattern = _make_pattern()

    async def _fake_patterns(paths, days):
        return [pattern]

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(get_cross_project_patterns=_fake_patterns),
    )

    result = get_cross_project_patterns(
        project_paths=["/tmp/a", "/tmp/b"], days_back=90
    )
    assert result["summary"]["total_patterns"] == 1
    assert result["summary"]["period_days"] == 90
    assert result["summary"]["repositories_analyzed"] == 2
    assert result["patterns"][0]["type"] == "test-flake"


def test_get_cross_project_patterns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _empty(paths, days):
        return []

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(get_cross_project_patterns=_empty),
    )

    result = get_cross_project_patterns(project_paths=["/tmp/a"], days_back=30)
    assert result["summary"]["total_patterns"] == 0
    assert result["patterns"] == []


def test_get_cross_project_patterns_raises_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(paths, days):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(get_cross_project_patterns=_boom),
    )

    with pytest.raises(RuntimeError, match="kaboom"):
        get_cross_project_patterns(project_paths=["/tmp/a"], days_back=30)


@pytest.mark.parametrize(
    ("current_per_day", "prev_per_day", "expected_trend"),
    [
        (5.0, 1.0, "increasing"),  # +4.0 commits/day
        (1.0, 5.0, "decreasing"),  # -4.0 commits/day
        (3.0, 3.0, "stable"),     # 0.0 commits/day (within ±0.5)
    ],
)
def test_get_velocity_comparison_trend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    current_per_day: float,
    prev_per_day: float,
    expected_trend: str,
) -> None:
    (tmp_path / ".git").mkdir()

    async def _fake_collect(repo, period_start, period_end):
        # First call returns current, second call returns previous.
        if not getattr(_fake_collect, "called", False):
            _fake_collect.called = True
            commits = 30 if expected_trend != "decreasing" else 10
            return SimpleNamespace(
                repository_name="r",
                total_commits=commits,
                avg_commits_per_day=current_per_day,
                avg_commits_per_week=current_per_day * 7,
            )
        commits = 10 if expected_trend != "decreasing" else 30
        return SimpleNamespace(
            repository_name="r",
            total_commits=commits,
            avg_commits_per_day=prev_per_day,
            avg_commits_per_week=prev_per_day * 7,
        )

    _fake_collect.called = False
    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(_collect_repository_velocity=_fake_collect),
    )

    result = get_velocity_comparison(repo_path=str(tmp_path), compare_period_days=30)
    assert result["trend"] == expected_trend


def test_get_velocity_comparison_handles_zero_previous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When previous period has 0 commits, percent change is 0 (no div-by-zero)."""
    (tmp_path / ".git").mkdir()

    call_count = {"n": 0}

    async def _fake_collect(repo, period_start, period_end):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return SimpleNamespace(
                repository_name="r",
                total_commits=10,
                avg_commits_per_day=1.0,
                avg_commits_per_week=7.0,
            )
        # Second call: zero commits in previous period.
        return SimpleNamespace(
            repository_name="r",
            total_commits=0,
            avg_commits_per_day=0.0,
            avg_commits_per_week=0.0,
        )

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(_collect_repository_velocity=_fake_collect),
    )

    result = get_velocity_comparison(repo_path=str(tmp_path), compare_period_days=30)
    assert result["change"]["commits_percent"] == 0
    assert result["change"]["velocity_percent"] == 0


def test_get_velocity_comparison_rejects_non_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "_aggregator", SimpleNamespace())
    with pytest.raises(ValueError, match="Not a git repository"):
        get_velocity_comparison(repo_path=str(tmp_path), compare_period_days=30)


def test_get_velocity_comparison_returns_full_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()

    async def _fake_collect(repo, period_start, period_end):
        return SimpleNamespace(
            repository_name="r",
            total_commits=5,
            avg_commits_per_day=1.0,
            avg_commits_per_week=7.0,
        )

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(_collect_repository_velocity=_fake_collect),
    )

    result = get_velocity_comparison(repo_path=str(tmp_path), compare_period_days=30)
    assert "current_period" in result
    assert "previous_period" in result
    assert "change" in result
    assert "trend" in result
    assert result["period_days"] == 30


def test_get_velocity_comparison_raises_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()

    async def _boom(repo, period_start, period_end):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(
        mod,
        "_aggregator",
        SimpleNamespace(_collect_repository_velocity=_boom),
    )

    with pytest.raises(RuntimeError, match="kaboom"):
        get_velocity_comparison(repo_path=str(tmp_path), compare_period_days=30)


def test_module_has_all_four_tools() -> None:
    """The four FastMCP tools are exposed as decorated functions on the module."""
    assert callable(get_cross_project_git_dashboard)
    assert callable(get_repository_health)
    assert callable(get_cross_project_patterns)
    assert callable(get_velocity_comparison)
