"""Tests for ``crackerjack.mcp.tools.git_metrics_tools``.

The four MCP tool entry points (`collect_git_metrics`,
`get_repository_velocity`, `get_repository_health`,
`get_conventional_compliance`) plus the private
`_generate_health_recommendations` helper are exercised by mocking
``GitMetricsCollector`` and ``SecureSubprocessExecutor`` at the
import boundary. The tools run synchronously and are decorated by
``FastMCP.tool`` and ``pydantic.validate_call``; to bypass pydantic
we invoke the underlying function via ``raw_function`` (matching the
pattern used in the sibling ``test_mcp_git_analytics.py``).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.mcp.tools import git_metrics_tools as gmt


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _commit_metrics(
    total: int = 100,
    conventional: int = 80,
    compliance: float = 0.8,
    breaking: int = 1,
    per_hour: float = 0.5,
    per_day: float = 4.0,
    per_week: float = 28.0,
    active_hour: int = 14,
    active_day: int = 2,
) -> SimpleNamespace:
    return SimpleNamespace(
        total_commits=total,
        conventional_commits=conventional,
        conventional_compliance_rate=compliance,
        breaking_changes=breaking,
        avg_commits_per_hour=per_hour,
        avg_commits_per_day=per_day,
        avg_commits_per_week=per_week,
        most_active_hour=active_hour,
        most_active_day=active_day,
        time_period=timedelta(days=30),
    )


def _branch_metrics(
    total: int = 10,
    active: int = 5,
    switches: int = 5,
    created: int = 4,
    deleted: int = 3,
    most_switched: str | None = "feature/x",
) -> SimpleNamespace:
    return SimpleNamespace(
        total_branches=total,
        active_branches=active,
        branch_switches=switches,
        branches_created=created,
        branches_deleted=deleted,
        avg_branch_lifetime_hours=12.0,
        most_switched_branch=most_switched,
    )


def _merge_metrics(
    total: int = 20,
    rebases: int = 5,
    conflicts: int = 2,
    conflict_rate: float = 0.1,
    avg_files: float = 1.5,
    success_rate: float = 0.9,
    conflicted_files: list[tuple[str, int]] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        total_merges=total,
        total_rebases=rebases,
        total_conflicts=conflicts,
        conflict_rate=conflict_rate,
        avg_files_per_conflict=avg_files,
        most_conflicted_files=conflicted_files or [],
        merge_success_rate=success_rate,
    )


def _velocity_dashboard(
    commits: SimpleNamespace | None = None,
    branches: SimpleNamespace | None = None,
    merges: SimpleNamespace | None = None,
    trend: list[tuple[datetime, int]] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        period_start=datetime(2026, 5, 1),
        period_end=datetime(2026, 5, 31),
        commit_metrics=commits or _commit_metrics(),
        branch_metrics=branches or _branch_metrics(),
        merge_metrics=merges or _merge_metrics(),
        trend_data=trend if trend is not None else [
            (datetime(2026, 5, 1), 5),
            (datetime(2026, 5, 2), 7),
        ],
    )


@pytest.fixture
def fake_repo(tmp_path):
    """Create a temporary directory that contains a ``.git`` subdir."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


@pytest.fixture
def non_repo(tmp_path):
    """A path that does not contain a ``.git`` directory."""
    path = tmp_path / "not_a_repo"
    path.mkdir()
    return path


@pytest.fixture
def patched_collector(fake_repo):
    """Patch ``_create_collector`` to return a configured MagicMock."""
    with patch.object(gmt, "_create_collector") as patched:
        collector = MagicMock()
        patched.return_value = collector
        yield collector, patched


# ---------------------------------------------------------------------------
# collect_git_metrics
# ---------------------------------------------------------------------------


class TestCollectGitMetrics:
    def test_returns_full_dashboard(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.get_velocity_dashboard.return_value = _velocity_dashboard()

        result = gmt.collect_git_metrics.raw_function(str(fake_repo), 30)

        assert result["repository"] == str(fake_repo.resolve())
        assert result["period"]["days"] == 30
        assert result["commits"]["total"] == 100
        assert result["commits"]["per_day"] == 4.0
        assert result["commits"]["conventional_rate"] == 80.0
        assert result["branches"]["total"] == 10
        assert result["merges"]["conflict_rate"] == 10.0
        assert len(result["trend"]) == 2
        collector.get_velocity_dashboard.assert_called_once_with(days_back=30)
        collector.close.assert_called_once()

    def test_empty_repo_returns_zero_metrics(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        empty_commits = _commit_metrics(
            total=0, conventional=0, compliance=0.0, breaking=0,
            per_hour=0.0, per_day=0.0, per_week=0.0,
        )
        empty_branches = _branch_metrics(
            total=0, active=0, switches=0, created=0, deleted=0, most_switched=None,
        )
        empty_merges = _merge_metrics(
            total=0, rebases=0, conflicts=0, conflict_rate=0.0, success_rate=1.0,
            conflicted_files=[],
        )
        collector.get_velocity_dashboard.return_value = _velocity_dashboard(
            commits=empty_commits,
            branches=empty_branches,
            merges=empty_merges,
            trend=[],
        )

        result = gmt.collect_git_metrics.raw_function(str(fake_repo), 7)

        assert result["commits"]["total"] == 0
        assert result["branches"]["most_switched"] is None
        assert result["merges"]["most_conflicted_files"] == []
        assert result["trend"] == []
        assert result["period"]["days"] == 7

    def test_clamps_most_conflicted_files_to_five(
        self, fake_repo, patched_collector,
    ):
        collector, _ = patched_collector
        files = [(f"src/file_{i}.py", i + 1) for i in range(8)]
        collector.get_velocity_dashboard.return_value = _velocity_dashboard(
            merges=_merge_metrics(conflicted_files=files),
        )

        result = gmt.collect_git_metrics.raw_function(str(fake_repo), 30)

        assert len(result["merges"]["most_conflicted_files"]) == 5
        assert result["merges"]["most_conflicted_files"][0]["path"] == "src/file_0.py"

    def test_missing_git_directory_raises(self, non_repo):
        with pytest.raises(ValueError, match="Not a git repository"):
            gmt.collect_git_metrics.raw_function(str(non_repo), 30)

    def test_collector_exception_is_reraised(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.get_velocity_dashboard.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            gmt.collect_git_metrics.raw_function(str(fake_repo), 30)

    def test_path_trailing_slash_is_resolved(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.get_velocity_dashboard.return_value = _velocity_dashboard()

        result = gmt.collect_git_metrics.raw_function(str(fake_repo) + "/", 14)

        assert result["repository"] == str(fake_repo.resolve())


# ---------------------------------------------------------------------------
# get_repository_velocity
# ---------------------------------------------------------------------------


class TestGetRepositoryVelocity:
    def test_returns_rounded_per_day(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.collect_commit_metrics.return_value = _commit_metrics(per_day=3.4567)

        velocity = gmt.get_repository_velocity.raw_function(str(fake_repo), 30)

        assert velocity == 3.46
        collector.collect_commit_metrics.assert_called_once()
        collector.close.assert_called_once()

    def test_zero_velocity(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.collect_commit_metrics.return_value = _commit_metrics(per_day=0.0)

        velocity = gmt.get_repository_velocity.raw_function(str(fake_repo), 7)

        assert velocity == 0.0

    def test_missing_git_directory_raises(self, non_repo):
        with pytest.raises(ValueError, match="Not a git repository"):
            gmt.get_repository_velocity.raw_function(str(non_repo), 30)

    def test_collector_exception_propagates(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.collect_commit_metrics.side_effect = OSError("git error")

        with pytest.raises(OSError, match="git error"):
            gmt.get_repository_velocity.raw_function(str(fake_repo), 30)


# ---------------------------------------------------------------------------
# get_repository_health
# ---------------------------------------------------------------------------


class TestGetRepositoryHealth:
    def test_returns_health_score_and_components(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.collect_branch_activity.return_value = _branch_metrics(
            total=5, active=4, switches=10,
        )
        collector.collect_merge_patterns.return_value = _merge_metrics(
            total=10, conflicts=1, conflict_rate=0.1, success_rate=0.9,
        )

        result = gmt.get_repository_health.raw_function(str(fake_repo))

        # branch_score = min(100, 4*10) = 40
        # merge_score = 0.9 * 100 = 90
        # conflict_score = max(0, 100 - 10) = 90
        # overall = (40 + 90 + 90) / 3 = 73.333... -> 73.3
        assert result["health_score"] == 73.3
        assert result["branches"]["score"] == 40.0
        assert result["merges"]["score"] == 90.0
        assert result["repository"] == str(fake_repo.resolve())
        # No recommendations triggered for clean defaults
        assert result["recommendations"] == ["✅ Repository health looks good!"]
        collector.close.assert_called_once()

    def test_branch_score_caps_at_100(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.collect_branch_activity.return_value = _branch_metrics(
            total=20, active=15, switches=0,
        )
        collector.collect_merge_patterns.return_value = _merge_metrics(
            total=0, conflicts=0, conflict_rate=0.0, success_rate=1.0,
        )

        result = gmt.get_repository_health.raw_function(str(fake_repo))

        # branch_score should be capped at 100 (15*10 = 150 -> 100)
        assert result["branches"]["score"] == 100.0

    def test_conflict_score_floors_at_zero(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.collect_branch_activity.return_value = _branch_metrics(
            total=3, active=3, switches=0,
        )
        # conflict_rate > 1 should still produce conflict_score = 0
        collector.collect_merge_patterns.return_value = _merge_metrics(
            total=5, conflicts=10, conflict_rate=1.5, success_rate=0.5,
        )

        result = gmt.get_repository_health.raw_function(str(fake_repo))

        assert result["merges"]["score"] == 50.0
        # conflict_score = max(0, 100 - 150) = 0
        # overall = (30 + 50 + 0) / 3 = 26.666... -> 26.7
        assert result["health_score"] == 26.7

    def test_recommendations_appear_for_poor_health(
        self, fake_repo, patched_collector,
    ):
        collector, _ = patched_collector
        collector.collect_branch_activity.return_value = _branch_metrics(
            total=20, active=2, switches=80,
        )
        collector.collect_merge_patterns.return_value = _merge_metrics(
            total=5, conflicts=4, conflict_rate=0.4, success_rate=0.6,
        )

        result = gmt.get_repository_health.raw_function(str(fake_repo))

        recs = result["recommendations"]
        # Conflict rate 0.4 > 0.2
        assert any("High merge conflict rate" in r for r in recs)
        # Success 0.6 < 0.8
        assert any("Low merge success rate" in r for r in recs)
        # 18 inactive branches > 10
        assert any("stale branches" in r for r in recs)
        # 80 switches > 50
        assert any("High branch switching" in r for r in recs)

    def test_missing_git_directory_raises(self, non_repo):
        with pytest.raises(ValueError, match="Not a git repository"):
            gmt.get_repository_health.raw_function(str(non_repo))

    def test_branch_collection_failure_propagates(
        self, fake_repo, patched_collector,
    ):
        collector, _ = patched_collector
        collector.collect_branch_activity.side_effect = RuntimeError("branches broken")

        with pytest.raises(RuntimeError, match="branches broken"):
            gmt.get_repository_health.raw_function(str(fake_repo))


# ---------------------------------------------------------------------------
# get_conventional_compliance
# ---------------------------------------------------------------------------


class TestGetConventionalCompliance:
    def test_returns_compliance_summary(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.collect_commit_metrics.return_value = _commit_metrics(
            total=50, conventional=45, compliance=0.9, breaking=2,
        )

        result = gmt.get_conventional_compliance.raw_function(
            str(fake_repo), 14,
        )

        assert result == {
            "repository": str(fake_repo.resolve()),
            "period_days": 14,
            "total_commits": 50,
            "conventional_commits": 45,
            "compliance_rate": 90.0,
            "breaking_changes": 2,
        }
        collector.collect_commit_metrics.assert_called_once()
        collector.close.assert_called_once()

    def test_zero_compliance(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.collect_commit_metrics.return_value = _commit_metrics(
            total=10, conventional=0, compliance=0.0, breaking=0,
        )

        result = gmt.get_conventional_compliance.raw_function(
            str(fake_repo), 30,
        )

        assert result["conventional_commits"] == 0
        assert result["compliance_rate"] == 0.0

    def test_missing_git_directory_raises(self, non_repo):
        with pytest.raises(ValueError, match="Not a git repository"):
            gmt.get_conventional_compliance.raw_function(str(non_repo), 30)

    def test_collector_exception_propagates(self, fake_repo, patched_collector):
        collector, _ = patched_collector
        collector.collect_commit_metrics.side_effect = ValueError("no commits")

        with pytest.raises(ValueError, match="no commits"):
            gmt.get_conventional_compliance.raw_function(str(fake_repo), 30)


# ---------------------------------------------------------------------------
# _create_collector
# ---------------------------------------------------------------------------


class TestCreateCollector:
    def test_wires_executor_into_collector(self, fake_repo):
        with patch(
            "crackerjack.mcp.tools.git_metrics_tools.GitMetricsCollector",
        ) as mock_cls, \
             patch(
                 "crackerjack.mcp.tools.git_metrics_tools.SecureSubprocessExecutor",
             ) as mock_exec_cls:
            mock_exec_cls.return_value = MagicMock(name="executor")

            gmt._create_collector(fake_repo)

            mock_exec_cls.assert_called_once_with()
            mock_cls.assert_called_once_with(
                repo_path=fake_repo, executor=mock_exec_cls.return_value,
            )


# ---------------------------------------------------------------------------
# _generate_health_recommendations (private helper)
# ---------------------------------------------------------------------------


class TestGenerateHealthRecommendations:
    def test_no_recommendations_returns_healthy_message(self):
        branches = _branch_metrics(total=5, active=5, switches=10)
        merges = _merge_metrics(conflict_rate=0.05, success_rate=0.95)

        recs = gmt._generate_health_recommendations(branches, merges)

        assert recs == ["✅ Repository health looks good!"]

    def test_high_conflict_rate_triggers_warning(self):
        branches = _branch_metrics(total=5, active=5, switches=10)
        merges = _merge_metrics(conflict_rate=0.5, success_rate=0.95)

        recs = gmt._generate_health_recommendations(branches, merges)

        assert len(recs) == 1
        assert "High merge conflict rate" in recs[0]
        assert "50%" in recs[0]

    def test_low_success_rate_triggers_warning(self):
        branches = _branch_metrics(total=5, active=5, switches=10)
        merges = _merge_metrics(conflict_rate=0.1, success_rate=0.5)

        recs = gmt._generate_health_recommendations(branches, merges)

        assert any("Low merge success rate" in r for r in recs)
        assert any("50%" in r for r in recs)

    def test_many_inactive_branches_triggers_cleanup(self):
        branches = _branch_metrics(total=25, active=5, switches=10)
        merges = _merge_metrics(conflict_rate=0.05, success_rate=0.95)

        recs = gmt._generate_health_recommendations(branches, merges)

        # 20 inactive branches
        assert any("20 stale branches" in r for r in recs)

    def test_many_branch_switches_triggers_consolidation(self):
        branches = _branch_metrics(total=5, active=5, switches=100)
        merges = _merge_metrics(conflict_rate=0.05, success_rate=0.95)

        recs = gmt._generate_health_recommendations(branches, merges)

        assert any("High branch switching" in r for r in recs)
        assert any("100" in r for r in recs)

    def test_exact_thresholds_do_not_trigger(self):
        # conflict_rate exactly 0.2 should NOT trigger (> 0.2 required)
        # success_rate exactly 0.8 should NOT trigger (< 0.8 required)
        # inactive = 10 should NOT trigger (> 10 required)
        # switches = 50 should NOT trigger (> 50 required)
        branches = _branch_metrics(total=12, active=2, switches=50)
        merges = _merge_metrics(conflict_rate=0.2, success_rate=0.8)

        recs = gmt._generate_health_recommendations(branches, merges)

        assert recs == ["✅ Repository health looks good!"]

    def test_combined_recommendations(self):
        # All four warning conditions active simultaneously
        branches = _branch_metrics(total=30, active=2, switches=200)
        merges = _merge_metrics(conflict_rate=0.6, success_rate=0.3)

        recs = gmt._generate_health_recommendations(branches, merges)

        # 4 separate recommendations, in declaration order
        assert len(recs) == 4
        assert "High merge conflict rate" in recs[0]
        assert "Low merge success rate" in recs[1]
        assert "stale branches" in recs[2]
        assert "High branch switching" in recs[3]
