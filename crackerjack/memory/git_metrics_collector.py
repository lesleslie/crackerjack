"""Typed stub for the git-metrics collector module.

The full git-metrics collector previously lived in ``crackerjack.memory``
alongside other AI-fix / memory subsystems that were removed when the
AI-fix stage was deleted (see ``crackerjack/core/autofix_coordinator.py``
for the dead-code note). This module exists so the type checker can
resolve ``crackerjack.memory.git_metrics_collector`` and so the four
call sites in ``crackerjack/mahavishnu/mcp/tools/git_analytics.py``
(lines 180, 586, 1868, 2113) have the surface they need at
static-analysis time.

The runtime bodies raise ``NotImplementedError``; production deployments
should rely on the real ``get_repository_health_dashboard`` MCP tool
exposed via the ``crackerjack-mahavishnu-git-analytics`` FastMCP server
in ``crackerjack/mahavishnu/mcp/tools/git_analytics.py`` rather than
importing this stub.

TODO(mcpretentious-removed): restore full module once vishnu MCP wire-up is verified
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.services.secure_subprocess import SecureSubprocessExecutor

__all__ = [
    "BranchMetrics",
    "CommitMetrics",
    "GitMetricsCollector",
    "MergeMetrics",
]


@dataclass
class CommitMetrics:
    total_commits: int = 0
    avg_commits_per_day: float = 0.0
    conventional_compliance_rate: float = 0.0
    breaking_changes: int = 0


@dataclass
class BranchMetrics:
    total_branches: int = 0
    active_branches: int = 0
    branches_created: int = 0
    branches_deleted: int = 0
    avg_branch_lifetime_hours: float = 0.0
    branch_switches: int = 0


@dataclass
class MergeMetrics:
    total_merges: int = 0
    total_rebases: int = 0
    total_conflicts: int = 0
    conflict_rate: float = 0.0
    merge_success_rate: float = 1.0
    avg_files_per_conflict: float = 0.0
    most_conflicted_files: list[tuple[str, int]] = field(default_factory=list)


class GitMetricsCollector:
    def __init__(
        self,
        pkg_path: Path,
        executor: SecureSubprocessExecutor | None = None,
    ) -> None:
        self.pkg_path = pkg_path
        self.executor = executor

    def collect_commit_metrics(
        self,
        since: datetime,
        until: datetime,
    ) -> CommitMetrics:
        """Collect per-commit metrics for ``since..until``.

        Stub: production callers should invoke the
        ``get_repository_health_dashboard`` MCP tool on the
        ``crackerjack-mahavishnu-git-analytics`` FastMCP server instead.
        """
        raise NotImplementedError(
            "GitMetricsCollector.collect_commit_metrics is a stub. "
            "Use the get_repository_health_dashboard MCP tool instead.",
        )

    def collect_branch_activity(self, since: datetime) -> BranchMetrics:
        """Collect branch activity metrics since ``since``.

        Stub: production callers should invoke the
        ``get_repository_health_dashboard`` MCP tool on the
        ``crackerjack-mahavishnu-git-analytics`` FastMCP server instead.
        """
        raise NotImplementedError(
            "GitMetricsCollector.collect_branch_activity is a stub. "
            "Use the get_repository_health_dashboard MCP tool instead.",
        )

    def collect_merge_patterns(
        self,
        since: datetime,
        until: datetime,
    ) -> MergeMetrics:
        """Collect merge-pattern metrics for ``since..until``.

        Stub: production callers should invoke the
        ``get_repository_health_dashboard`` MCP tool on the
        ``crackerjack-mahavishnu-git-analytics`` FastMCP server instead.
        """
        raise NotImplementedError(
            "GitMetricsCollector.collect_merge_patterns is a stub. "
            "Use the get_repository_health_dashboard MCP tool instead.",
        )
