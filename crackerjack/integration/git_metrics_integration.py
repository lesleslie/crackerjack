from __future__ import annotations

import logging
from datetime import datetime, timedelta

from crackerjack.memory.git_metrics_collector import GitMetricsCollector
from crackerjack.models.protocols import SecureSubprocessExecutorProtocol
from crackerjack.models.session_metrics import SessionMetrics

logger = logging.getLogger(__name__)


class GitMetricsSessionCollector:
    def __init__(
        self,
        session_metrics: SessionMetrics,
        project_path: str,
        collector: GitMetricsCollector | None = None,
    ) -> None:
        self.session_metrics = session_metrics
        self.project_path = project_path
        self._collector = collector

    def _get_collector(
        self, executor: SecureSubprocessExecutorProtocol
    ) -> GitMetricsCollector:
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
        try:
            collector = self._get_collector(executor)

            commit_velocity = await self._collect_commit_velocity(collector)
            self.session_metrics.git_commit_velocity = commit_velocity

            branch_count = await self._collect_branch_count(collector)
            self.session_metrics.git_branch_count = branch_count

            merge_success = await self._collect_merge_success_rate(collector)
            self.session_metrics.git_merge_success_rate = merge_success

            compliance = await self._collect_conventional_compliance(collector)
            self.session_metrics.conventional_commit_compliance = compliance

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
            logger.warning(f"Git metrics collection failed: {e}")
            self._set_null_metrics()
        except Exception as e:
            logger.error(f"Unexpected error collecting git metrics: {e}", exc_info=True)
            self._set_null_metrics()

        return self.session_metrics

    async def _collect_commit_velocity(self, collector: GitMetricsCollector) -> float:
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
        try:
            merge_metrics = collector.collect_merge_patterns(
                since=datetime.now() - timedelta(days=30)
            )
            rate = merge_metrics.merge_success_rate
            logger.debug(f"Merge success rate: {rate:.2%}")
            return rate
        except Exception as e:
            logger.warning(f"Failed to collect merge success rate: {e}")
            return 1.0

    async def _collect_conventional_compliance(
        self, collector: GitMetricsCollector
    ) -> float:
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

        normalized_velocity = (
            min(commit_velocity / 10.0, 1.0) if commit_velocity else 0.0
        )

        merge_rate = merge_success_rate or 1.0
        compliance = conventional_compliance or 0.0

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
        self.session_metrics.git_commit_velocity = None
        self.session_metrics.git_branch_count = None
        self.session_metrics.git_merge_success_rate = None
        self.session_metrics.conventional_commit_compliance = None
        self.session_metrics.git_workflow_efficiency_score = None
        logger.debug("Set null metrics for session")


__all__ = ["GitMetricsSessionCollector"]
