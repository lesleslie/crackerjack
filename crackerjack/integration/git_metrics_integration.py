"""Git metrics integration for session tracking.

This module provides integration between git metrics collection and session
tracking, enabling comprehensive workflow efficiency analysis during development
sessions.

Classes:
    GitMetricsSessionCollector: Collects git metrics for session tracking
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from crackerjack.memory.git_metrics_collector import GitMetricsCollector
from crackerjack.models.protocols import SecureSubprocessExecutorProtocol
from crackerjack.models.session_metrics import SessionMetrics

logger = logging.getLogger(__name__)


class GitMetricsSessionCollector:
    """Collects git metrics during development sessions.

    This class bridges git analytics and session tracking, collecting
    repository metrics and calculating workflow efficiency scores.

    Attributes:
        session_metrics: Session metrics data to update
        project_path: Path to the git repository
        collector: Git metrics collector instance
    """

    def __init__(
        self,
        session_metrics: SessionMetrics,
        project_path: str,
        collector: GitMetricsCollector | None = None,
    ) -> None:
        """Initialize the git metrics session collector.

        Args:
            session_metrics: Session metrics to update with collected data
            project_path: Path to the git repository
            collector: Optional pre-configured collector (auto-created if None)
        """
        self.session_metrics = session_metrics
        self.project_path = project_path
        self._collector = collector

    def _get_collector(
        self, executor: SecureSubprocessExecutorProtocol
    ) -> GitMetricsCollector:
        """Get or create the git metrics collector.

        Args:
            executor: Subprocess executor for git operations

        Returns:
            Configured GitMetricsCollector instance
        """
        if self._collector is None:
            from pathlib import Path

            self._collector = GitMetricsCollector(
                repo_path=Path(self.project_path),
                executor=executor,
            )
            logger.debug(f"Created GitMetricsCollector for {self.project_path}")
        return self._collector

    async def collect_session_metrics(
        self, executor: SecureSubprocessExecutorProtocol
    ) -> SessionMetrics:
        """Collect git metrics and update session metrics.

        This method collects:
        - Commit velocity (commits in last 1 hour)
        - Total branch count
        - Merge statistics (last 30 days)
        - Conventional commit compliance (last 30 days)
        - Workflow efficiency score

        Args:
            executor: Subprocess executor for git operations

        Returns:
            Updated SessionMetrics with git data populated
        """
        try:
            collector = self._get_collector(executor)

            # Collect commit velocity (last 1 hour)
            commit_velocity = await self._collect_commit_velocity(collector)
            self.session_metrics.git_commit_velocity = commit_velocity

            # Collect branch count
            branch_count = await self._collect_branch_count(collector)
            self.session_metrics.git_branch_count = branch_count

            # Collect merge statistics (30 days)
            merge_success = await self._collect_merge_success_rate(collector)
            self.session_metrics.git_merge_success_rate = merge_success

            # Collect conventional compliance (30 days)
            compliance = await self._collect_conventional_compliance(collector)
            self.session_metrics.conventional_commit_compliance = compliance

            # Calculate workflow efficiency score
            efficiency_score = self._calculate_workflow_score(
                commit_velocity=commit_velocity,
                merge_success_rate=merge_success,
                conventional_compliance=compliance,
            )
            self.session_metrics.git_workflow_efficiency_score = efficiency_score

            logger.info(
                f"Collected git metrics for session {self.session_metrics.session_id}: "
                f"velocity={commit_velocity}, branches={branch_count}, "
                f"merge_rate={merge_success:.2%}, compliance={compliance:.2%}, "
                f"efficiency={efficiency_score:.1f}"
            )

        except ValueError as e:
            # Not a git repository or git not available
            logger.warning(f"Git metrics collection failed: {e}")
            self._set_null_metrics()
        except Exception as e:
            logger.error(f"Unexpected error collecting git metrics: {e}", exc_info=True)
            self._set_null_metrics()

        return self.session_metrics

    async def _collect_commit_velocity(self, collector: GitMetricsCollector) -> float:
        """Collect commit velocity (commits per hour).

        Args:
            collector: Git metrics collector instance

        Returns:
            Commits per hour as float
        """
        try:
            since = datetime.now() - timedelta(hours=1)
            metrics = collector.collect_commit_metrics(since=since)

            velocity = metrics.avg_commits_per_hour
            logger.debug(f"Commit velocity: {velocity:.2f} commits/hour")
            return velocity
        except Exception as e:
            logger.warning(f"Failed to collect commit velocity: {e}")
            return 0.0

    async def _collect_branch_count(self, collector: GitMetricsCollector) -> int:
        """Collect total branch count.

        Args:
            collector: Git metrics collector instance

        Returns:
            Total number of branches
        """
        try:
            branch_metrics = collector.collect_branch_activity()
            count = branch_metrics.total_branches
            logger.debug(f"Branch count: {count}")
            return count
        except Exception as e:
            logger.warning(f"Failed to collect branch count: {e}")
            return 0

    async def _collect_merge_success_rate(
        self, collector: GitMetricsCollector
    ) -> float:
        """Collect merge success rate.

        Args:
            collector: Git metrics collector instance

        Returns:
            Merge success rate (0.0 to 1.0)
        """
        try:
            merge_metrics = collector.collect_merge_patterns(
                since=datetime.now() - timedelta(days=30)
            )
            rate = merge_metrics.merge_success_rate
            logger.debug(f"Merge success rate: {rate:.2%}")
            return rate
        except Exception as e:
            logger.warning(f"Failed to collect merge success rate: {e}")
            return 1.0  # Default to 100% if unknown

    async def _collect_conventional_compliance(
        self, collector: GitMetricsCollector
    ) -> float:
        """Collect conventional commit compliance rate.

        Args:
            collector: Git metrics collector instance

        Returns:
            Conventional commit compliance rate (0.0 to 1.0)
        """
        try:
            commit_metrics = collector.collect_commit_metrics(
                since=datetime.now() - timedelta(days=30)
            )
            compliance = commit_metrics.conventional_compliance_rate
            logger.debug(f"Conventional compliance: {compliance:.2%}")
            return compliance
        except Exception as e:
            logger.warning(f"Failed to collect conventional compliance: {e}")
            return 0.0

    def _calculate_workflow_score(
        self,
        commit_velocity: float | None,
        merge_success_rate: float | None,
        conventional_compliance: float | None,
    ) -> float:
        """Calculate workflow efficiency score.

        Weighted formula:
        - 40%: commit velocity (normalized to 0-1)
        - 35%: merge success rate
        - 25%: conventional compliance

        Args:
            commit_velocity: Commits per hour
            merge_success_rate: Merge success rate (0-1)
            conventional_compliance: Conventional commit rate (0-1)

        Returns:
            Workflow efficiency score (0-100)
        """
        # Normalize commit velocity (0-10 commits/hour maps to 0-1)
        normalized_velocity = (
            min(commit_velocity / 10.0, 1.0) if commit_velocity else 0.0
        )

        # Get rates with defaults
        merge_rate = merge_success_rate if merge_success_rate else 1.0
        compliance = conventional_compliance if conventional_compliance else 0.0

        # Weighted calculation
        score = (
            (normalized_velocity * 0.40) + (merge_rate * 0.35) + (compliance * 0.25)
        ) * 100

        logger.debug(
            f"Workflow score calculation: "
            f"velocity={normalized_velocity:.2f} * 0.40 + "
            f"merge={merge_rate:.2f} * 0.35 + "
            f"compliance={compliance:.2f} * 0.25 = {score:.1f}"
        )

        return round(score, 1)

    def _set_null_metrics(self) -> None:
        """Set all git metrics to None/defaults when collection fails."""
        self.session_metrics.git_commit_velocity = None
        self.session_metrics.git_branch_count = None
        self.session_metrics.git_merge_success_rate = None
        self.session_metrics.conventional_commit_compliance = None
        self.session_metrics.git_workflow_efficiency_score = None
        logger.debug("Set null metrics for session")


__all__ = ["GitMetricsSessionCollector"]
