"""Tests for ``crackerjack.memory.git_metrics_collector``.

The module is a typed stub mirroring ``crackerjack.integration.git_metrics_integration``:
the runtime bodies raise ``NotImplementedError`` and production callers should
use the ``get_repository_health_dashboard`` MCP tool instead. These tests
pin the contract so the stub stays distinguishable from a fully-implemented
collector.
"""

from __future__ import annotations

import typing
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from crackerjack.memory.git_metrics_collector import (
    BranchMetrics,
    CommitMetrics,
    GitMetricsCollector,
    MergeMetrics,
)


def test_module_exports_expected_names() -> None:
    from crackerjack.memory import git_metrics_collector

    assert git_metrics_collector.__all__ == [
        "BranchMetrics",
        "CommitMetrics",
        "GitMetricsCollector",
        "MergeMetrics",
    ]


def test_commit_metrics_defaults() -> None:
    m = CommitMetrics()
    assert m.total_commits == 0
    assert m.avg_commits_per_day == 0.0
    assert m.conventional_compliance_rate == 0.0
    assert m.breaking_changes == 0


def test_commit_metrics_field_count() -> None:
    """Pin the dataclass schema so callers can rely on these fields."""
    assert len(fields(CommitMetrics)) == 4


def test_branch_metrics_defaults() -> None:
    m = BranchMetrics()
    assert m.total_branches == 0
    assert m.active_branches == 0
    assert m.branches_created == 0
    assert m.branches_deleted == 0
    assert m.avg_branch_lifetime_hours == 0.0
    assert m.branch_switches == 0


def test_branch_metrics_field_count() -> None:
    assert len(fields(BranchMetrics)) == 6


def test_merge_metrics_defaults() -> None:
    m = MergeMetrics()
    assert m.total_merges == 0
    assert m.total_rebases == 0
    assert m.total_conflicts == 0
    assert m.conflict_rate == 0.0
    assert m.merge_success_rate == 1.0
    assert m.avg_files_per_conflict == 0.0
    assert m.most_conflicted_files == []


def test_merge_metrics_most_conflicted_files_default_is_list_per_instance() -> None:
    """Each instance should get its own list (mutable default factory)."""
    m1 = MergeMetrics()
    m2 = MergeMetrics()
    m1.most_conflicted_files.append(("a.py", 3))
    assert m2.most_conflicted_files == []


def test_merge_metrics_accepts_most_conflicted_files() -> None:
    m = MergeMetrics(most_conflicted_files=[("hot.py", 9)])
    assert m.most_conflicted_files == [("hot.py", 9)]


def test_collector_stores_pkg_path_and_executor(tmp_path: Path) -> None:
    collector = GitMetricsCollector(pkg_path=tmp_path)
    assert collector.pkg_path is tmp_path
    assert collector.executor is None


def test_collector_accepts_optional_executor(tmp_path: Path) -> None:
    fake_executor: Any = object()  # never invoked by the stub
    collector = GitMetricsCollector(pkg_path=tmp_path, executor=fake_executor)
    assert collector.executor is fake_executor


def test_collect_commit_metrics_raises_not_implemented(tmp_path: Path) -> None:
    collector = GitMetricsCollector(pkg_path=tmp_path)
    with pytest.raises(NotImplementedError, match="collect_commit_metrics"):
        collector.collect_commit_metrics(
            since=datetime(2026, 1, 1, tzinfo=UTC),
            until=datetime(2026, 1, 2, tzinfo=UTC),
        )


def test_collect_branch_activity_raises_not_implemented(tmp_path: Path) -> None:
    collector = GitMetricsCollector(pkg_path=tmp_path)
    with pytest.raises(NotImplementedError, match="collect_branch_activity"):
        collector.collect_branch_activity(since=datetime(2026, 1, 1, tzinfo=UTC))


def test_collect_merge_patterns_raises_not_implemented(tmp_path: Path) -> None:
    collector = GitMetricsCollector(pkg_path=tmp_path)
    with pytest.raises(NotImplementedError, match="collect_merge_patterns"):
        collector.collect_merge_patterns(
            since=datetime(2026, 1, 1, tzinfo=UTC),
            until=datetime(2026, 1, 2, tzinfo=UTC),
        )


def test_typed_signature_uses_optional_secure_subprocess() -> None:
    """The constructor's ``executor`` parameter references SecureSubprocessExecutor."""
    import inspect

    from crackerjack.memory import git_metrics_collector

    sig = inspect.signature(git_metrics_collector.GitMetricsCollector.__init__)
    executor_param = sig.parameters["executor"]
    # Annotation is forward-ref string (PEP 563); check raw string form.
    annotation = str(executor_param.annotation)
    assert "SecureSubprocessExecutor" in annotation
    assert "None" in annotation
