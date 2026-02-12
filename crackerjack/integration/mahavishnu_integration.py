from __future__ import annotations

import asyncio
import logging
import typing as t
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepositoryVelocity:
    repository_path: str
    repository_name: str
    period_start: datetime
    period_end: datetime
    total_commits: int
    avg_commits_per_day: float
    avg_commits_per_week: float
    conventional_compliance_rate: float
    breaking_changes: int
    merge_conflict_rate: float
    health_score: float
    trend_direction: t.Literal["increasing", "stable", "decreasing"]


@dataclass(frozen=True)
class RepositoryHealth:
    repository_path: str
    repository_name: str
    stale_branches: list[str]
    unmerged_prs: int
    large_files: list[str]
    last_activity: datetime | None
    health_score: float
    risk_level: t.Literal["low", "medium", "high", "critical"]
    recommendations: list[str]


@dataclass(frozen=True)
class CrossProjectPattern:
    pattern_type: str
    affected_repositories: list[str]
    severity: t.Literal["info", "warning", "critical"]
    description: str
    metric_value: float
    recommendation: str
    detected_at: datetime


@dataclass(frozen=True)
class CrossProjectDashboard:
    generated_at: datetime
    total_repositories: int
    period_days: int
    repositories: list[RepositoryVelocity]
    aggregate_metrics: dict[str, t.Any]
    top_performers: list[str]
    needs_attention: list[str]
    cross_project_patterns: list[CrossProjectPattern]


@dataclass
class PortfolioVelocityDashboard:
    generated_at: datetime
    total_repositories: int
    period_days: int
    portfolio_velocity: float
    total_commits: int
    avg_health_score: float
    velocity_distribution: dict[str, int]
    repositories: list[RepositoryVelocity]
    top_performers: list[str]
    needs_attention: list[str]
    cross_project_patterns: list[CrossProjectPattern]


@dataclass
class MergePatternAnalysis:
    generated_at: datetime
    repositories_analyzed: int
    period_days: int
    total_merges: int
    total_rebases: int
    total_conflicts: int
    portfolio_conflict_rate: float
    rebase_ratio: float
    merge_vs_rebase_bias: t.Literal["merge", "rebase"]
    most_conflicted_files: list[tuple[str, int]]
    recommendations: list[str]


@dataclass
class BestPracticePropagation:
    generated_at: datetime
    repositories_analyzed: int
    top_performers_count: int
    best_practices: list[dict[str, t.Any]]
    propagation_targets: list[dict[str, t.Any]]
    recommendations: list[str]


@dataclass
class MahavishnuConfig:
    db_path: Path = field(default_factory=lambda: Path(".crackerjack/mahavishnu.db"))
    websocket_enabled: bool = False
    websocket_host: str = "127.0.0.1"
    websocket_port: int = 8686
    cache_ttl_seconds: int = 300
    git_metrics_enabled: bool = True
    git_metrics_db_path: Path = field(
        default_factory=lambda: Path(".crackerjack/git_metrics.db")
    )
    portfolio_repos: list[str] = field(default_factory=list)
    dashboard_refresh_interval: int = 300


@dataclass
class NoOpWebSocketBroadcaster:
    config: MahavishnuConfig

    async def broadcast_dashboard_update(
        self, dashboard: CrossProjectDashboard | PortfolioVelocityDashboard
    ) -> None:
        logger.debug("WebSocket broadcaster disabled, skipping dashboard update")

    async def broadcast_health_alert(
        self, repo_path: str, health: RepositoryHealth
    ) -> None:
        logger.debug("WebSocket broadcaster disabled, skipping health alert")

    async def broadcast_pattern_detected(self, pattern: CrossProjectPattern) -> None:
        logger.debug("WebSocket broadcaster disabled, skipping pattern detection")

    async def broadcast_merge_analysis(self, analysis: MergePatternAnalysis) -> None:
        logger.debug("WebSocket broadcaster disabled, skipping merge analysis")

    async def broadcast_best_practices(
        self, practices: BestPracticePropagation
    ) -> None:
        logger.debug("WebSocket broadcaster disabled, skipping best practices")


@dataclass
class MahavishnuWebSocketBroadcaster:
    config: MahavishnuConfig
    _server: t.Any = field(init=False, default=None)
    _initialized: bool = field(init=False, default=False)

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            from crackerjack.qc import QualityControlManager
            from crackerjack.websocket.server import CrackerjackWebSocketServer

            qc_manager = QualityControlManager()

            self._server = CrackerjackWebSocketServer(
                qc_manager=qc_manager,
                host=self.config.websocket_host,
                port=self.config.websocket_port,
            )

            asyncio.create_task(self._server.start())
            self._initialized = True
            logger.info(
                f"Mahavishnu WebSocket broadcaster initialized: "
                f"{self.config.websocket_host}:{self.config.websocket_port}"
            )

        except ImportError as e:
            logger.debug(f"WebSocket server not available: {e}")
            self._initialized = False

        except Exception as e:
            logger.error(f"Failed to initialize WebSocket broadcaster: {e}")
            self._initialized = False

    async def broadcast_dashboard_update(
        self, dashboard: CrossProjectDashboard | PortfolioVelocityDashboard
    ) -> None:
        if not self._initialized or not self._server:
            return

        try:
            from mcp_common.websocket import EventTypes, WebSocketProtocol

            message = WebSocketProtocol.create_event(
                200,
                EventTypes.CUSTOM,
                {
                    "event_type": "dashboard_update",
                    "dashboard": {
                        "generated_at": dashboard.generated_at.isoformat(),
                        "total_repositories": dashboard.total_repositories,
                        "period_days": dashboard.period_days,
                        "top_performers": dashboard.top_performers,
                        "needs_attention": dashboard.needs_attention,
                    },
                },
            )

            await self._server.broadcast("mahavishnu: global", message)
            logger.debug("Broadcast dashboard update")

        except Exception as e:
            logger.error(f"Failed to broadcast dashboard update: {e}")

    async def broadcast_health_alert(
        self, repo_path: str, health: RepositoryHealth
    ) -> None:
        if not self._initialized or not self._server:
            return

        try:
            from mcp_common.websocket import EventTypes, WebSocketProtocol

            if health.risk_level not in ("medium", "high", "critical"):
                return

            message = WebSocketProtocol.create_event(
                200,
                EventTypes.CUSTOM,
                {
                    "event_type": "health_alert",
                    "repository": repo_path,
                    "repository_name": health.repository_name,
                    "risk_level": health.risk_level,
                    "health_score": health.health_score,
                    "recommendations": health.recommendations,
                },
            )

            channel = f"mahavishnu: repo:{Path(repo_path).name}"
            await self._server.broadcast(channel, message)
            await self._server.broadcast("mahavishnu: global", message)
            logger.debug(f"Broadcast health alert for {repo_path}")

        except Exception as e:
            logger.error(f"Failed to broadcast health alert: {e}")

    async def broadcast_pattern_detected(self, pattern: CrossProjectPattern) -> None:
        if not self._initialized or not self._server:
            return

        try:
            from mcp_common.websocket import EventTypes, WebSocketProtocol

            message = WebSocketProtocol.create_event(
                200,
                EventTypes.CUSTOM,
                {
                    "event_type": "pattern_detected",
                    "pattern_type": pattern.pattern_type,
                    "severity": pattern.severity,
                    "description": pattern.description,
                    "affected_repositories": pattern.affected_repositories,
                    "recommendation": pattern.recommendation,
                },
            )

            await self._server.broadcast("mahavishnu: global", message)
            logger.debug(f"Broadcast pattern detection: {pattern.pattern_type}")

        except Exception as e:
            logger.error(f"Failed to broadcast pattern detection: {e}")

    async def broadcast_merge_analysis(self, analysis: MergePatternAnalysis) -> None:
        if not self._initialized or not self._server:
            return

        try:
            from mcp_common.websocket import EventTypes, WebSocketProtocol

            message = WebSocketProtocol.create_event(
                200,
                EventTypes.CUSTOM,
                {
                    "event_type": "merge_analysis",
                    "repositories_analyzed": analysis.repositories_analyzed,
                    "period_days": analysis.period_days,
                    "total_merges": analysis.total_merges,
                    "portfolio_conflict_rate": analysis.portfolio_conflict_rate,
                    "merge_vs_rebase_bias": analysis.merge_vs_rebase_bias,
                    "recommendations": analysis.recommendations,
                },
            )

            await self._server.broadcast("mahavishnu: global", message)
            logger.debug("Broadcast merge analysis")

        except Exception as e:
            logger.error(f"Failed to broadcast merge analysis: {e}")

    async def broadcast_best_practices(
        self, practices: BestPracticePropagation
    ) -> None:
        if not self._initialized or not self._server:
            return

        try:
            from mcp_common.websocket import EventTypes, WebSocketProtocol

            message = WebSocketProtocol.create_event(
                200,
                EventTypes.CUSTOM,
                {
                    "event_type": "best_practices",
                    "repositories_analyzed": practices.repositories_analyzed,
                    "best_practices_found": len(practices.best_practices),
                    "propagation_targets": len(practices.propagation_targets),
                    "recommendations": practices.recommendations,
                },
            )

            await self._server.broadcast("mahavishnu: global", message)
            logger.debug("Broadcast best practices")

        except Exception as e:
            logger.error(f"Failed to broadcast best practices: {e}")


class MahavishnuAggregator:
    def __init__(
        self,
        config: MahavishnuConfig | None = None,
    ) -> None:
        self.config = config or MahavishnuConfig()
        self.broadcaster: t.Any
        self._cache: dict[str, tuple[t.Any, datetime]] = {}
        self._initialized = False

        if self.config.websocket_enabled:
            self.broadcaster = MahavishnuWebSocketBroadcaster(self.config)
        else:
            self.broadcaster = NoOpWebSocketBroadcaster(self.config)

    async def initialize(self) -> None:
        if self._initialized:
            return

        if self.config.websocket_enabled:
            await self.broadcaster.initialize()

        try:
            import sqlite3

            db_path = (
                self.config.db_path
                if isinstance(self.config.db_path, Path)
                else Path(self.config.db_path)
            )

            db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mahavishnu_cache (
                    key TEXT PRIMARY KEY,
                    data TEXT,
                    timestamp TEXT
                )
                """
            )
            conn.commit()
            conn.close()

            logger.info(f"Mahavishnu aggregator initialized: {db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize Mahavishnu aggregator: {e}")
            raise

        self._initialized = True

    async def get_cross_project_git_dashboard(
        self,
        project_paths: list[str] | list[Path],
        days_back: int = 30,
    ) -> CrossProjectDashboard:

        project_paths = [str(p) for p in project_paths]

        logger.info(
            f"Generating cross-project dashboard for {len(project_paths)} repositories"
        )

        repositories = []
        period_start = datetime.now() - timedelta(days=days_back)
        period_end = datetime.now()

        total_commits = 0
        total_conflicts = 0
        health_scores = []

        for repo_path in project_paths:
            try:
                velocity = await self._collect_repository_velocity(
                    repo_path, period_start, period_end
                )
                repositories.append(velocity)
                total_commits += velocity.total_commits
                total_conflicts += velocity.merge_conflict_rate
                health_scores.append(velocity.health_score)

            except Exception as e:
                logger.warning(f"Failed to collect metrics from {repo_path}: {e}")
                continue

        avg_health_score = (
            sum(health_scores) / len(health_scores) if health_scores else 0.0
        )
        avg_commits_per_day = (
            sum(r.avg_commits_per_day for r in repositories) / len(repositories)
            if repositories
            else 0.0
        )

        sorted_by_health = sorted(
            repositories, key=lambda r: r.health_score, reverse=True
        )
        top_performers = [r.repository_path for r in sorted_by_health[:3]]
        needs_attention = [
            r.repository_path for r in sorted_by_health[-3:] if r.health_score < 50
        ]

        patterns = await self._detect_cross_project_patterns(repositories, days_back)

        dashboard = CrossProjectDashboard(
            generated_at=datetime.now(),
            total_repositories=len(repositories),
            period_days=days_back,
            repositories=repositories,
            aggregate_metrics={
                "total_commits": total_commits,
                "avg_commits_per_day": avg_commits_per_day,
                "avg_health_score": avg_health_score,
                "total_conflicts": total_conflicts,
            },
            top_performers=top_performers,
            needs_attention=needs_attention,
            cross_project_patterns=patterns,
        )

        await self.broadcaster.broadcast_dashboard_update(dashboard)

        return dashboard

    async def get_portfolio_velocity_dashboard(
        self,
        project_paths: list[str] | list[Path],
        days_back: int = 30,
    ) -> PortfolioVelocityDashboard:
        project_paths = [str(p) for p in project_paths]

        logger.info(
            f"Generating portfolio dashboard for {len(project_paths)} repositories"
        )

        period_start = datetime.now() - timedelta(days=days_back)
        period_end = datetime.now()

        repositories = []
        total_commits = 0
        health_scores = []

        for repo_path in project_paths:
            try:
                velocity = await self._collect_repository_velocity(
                    repo_path, period_start, period_end
                )
                repositories.append(velocity)
                total_commits += velocity.total_commits
                health_scores.append(velocity.health_score)
            except Exception as e:
                logger.warning(f"Failed to collect metrics from {repo_path}: {e}")
                continue

        portfolio_velocity = (
            sum(r.avg_commits_per_day for r in repositories) if repositories else 0.0
        )
        avg_health_score = (
            sum(health_scores) / len(health_scores) if health_scores else 0.0
        )

        velocity_distribution = {
            "high_performers": len([r for r in repositories if r.health_score >= 80]),
            "healthy": len([r for r in repositories if 50 <= r.health_score < 80]),
            "needs_attention": len([r for r in repositories if r.health_score < 50]),
            "critical": len([r for r in repositories if r.health_score < 40]),
        }

        sorted_by_health = sorted(
            repositories, key=lambda r: r.health_score, reverse=True
        )
        top_performers = [r.repository_path for r in sorted_by_health[:3]]
        needs_attention = [
            r.repository_path for r in sorted_by_health[-3:] if r.health_score < 50
        ]

        patterns = await self._detect_cross_project_patterns(repositories, days_back)

        dashboard = PortfolioVelocityDashboard(
            generated_at=datetime.now(),
            total_repositories=len(repositories),
            period_days=days_back,
            portfolio_velocity=portfolio_velocity,
            total_commits=total_commits,
            avg_health_score=avg_health_score,
            velocity_distribution=velocity_distribution,
            repositories=repositories,
            top_performers=top_performers,
            needs_attention=needs_attention,
            cross_project_patterns=patterns,
        )

        await self.broadcaster.broadcast_dashboard_update(dashboard)

        return dashboard

    async def analyze_merge_patterns(
        self,
        project_paths: list[str] | list[Path],
        days_back: int = 90,
    ) -> MergePatternAnalysis:
        project_paths = [str(p) for p in project_paths]

        logger.info(
            f"Analyzing merge patterns for {len(project_paths)} repositories "
            f"(last {days_back} days)"
        )

        from crackerjack.memory.git_metrics_collector import GitMetricsCollector

        period_end = datetime.now()
        period_start = period_end - timedelta(days=days_back)

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
                collector = GitMetricsCollector(repo_path)
                merge_metrics = collector.collect_merge_patterns(
                    since=period_start, until=period_end
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

        merge_vs_rebase_bias: t.Literal["merge", "rebase"] = (
            "rebase" if rebase_ratio > 0.5 else "merge"
        )

        analysis = MergePatternAnalysis(
            generated_at=datetime.now(),
            repositories_analyzed=len(project_paths),
            period_days=days_back,
            total_merges=total_merges,
            total_rebases=total_rebases,
            total_conflicts=total_conflicts,
            portfolio_conflict_rate=portfolio_conflict_rate,
            rebase_ratio=rebase_ratio,
            merge_vs_rebase_bias=merge_vs_rebase_bias,
            most_conflicted_files=all_conflicted_files.most_common(20),
            recommendations=self._generate_merge_recommendations(
                portfolio_conflict_rate,
                rebase_ratio,
                all_conflicted_files.most_common(10),
            ),
        )

        await self.broadcaster.broadcast_merge_analysis(analysis)

        return analysis

    async def propagate_best_practices(
        self,
        project_paths: list[str] | list[Path],
        days_back: int = 60,
    ) -> BestPracticePropagation:
        project_paths = [str(p) for p in project_paths]

        logger.info(
            f"Analyzing best practices for {len(project_paths)} repositories "
            f"(last {days_back} days)"
        )

        period_end = datetime.now()
        period_start = period_end - timedelta(days=days_back)

        repos_data = []
        for repo_path_str in project_paths:
            try:
                velocity = await self._collect_repository_velocity(
                    repo_path_str, period_start, period_end
                )
                repos_data.append(velocity)
            except Exception as e:
                logger.warning(f"Failed to collect metrics from {repo_path_str}: {e}")
                continue

        if not repos_data:
            return BestPracticePropagation(
                generated_at=datetime.now(),
                repositories_analyzed=0,
                top_performers_count=0,
                best_practices=[],
                propagation_targets=[],
                recommendations=["No valid repositories found"],
            )

        sorted_by_health = sorted(
            repos_data, key=lambda r: r.health_score, reverse=True
        )
        top_performers = sorted_by_health[:3]
        low_performers = [r for r in sorted_by_health if r.health_score < 60]

        best_practices = self._extract_best_practices(top_performers)
        propagation_targets = self._identify_propagation_targets(
            low_performers, best_practices
        )

        propagation = BestPracticePropagation(
            generated_at=datetime.now(),
            repositories_analyzed=len(repos_data),
            top_performers_count=len(top_performers),
            best_practices=best_practices,
            propagation_targets=propagation_targets,
            recommendations=self._generate_best_practice_recommendations(
                top_performers, low_performers
            ),
        )

        await self.broadcaster.broadcast_best_practices(propagation)

        return propagation

    async def get_repository_health(self, repo_path: str | Path) -> RepositoryHealth:
        repo_path = str(repo_path)
        repo_name = Path(repo_path).name

        logger.debug(f"Collecting health metrics for {repo_name}")

        try:
            from crackerjack.memory.git_metrics_storage import GitMetricsStorage

            storage = GitMetricsStorage(db_path=Path(".crackerjack/git_metrics.db"))

            health_data = storage.get_repository_health(repo_path)

            health_score = health_data.get("health_score", 50)
            health_score = max(0, min(100, health_score))

            if health_score >= 80:
                risk_level = "low"
            elif health_score >= 60:
                risk_level = "medium"
            elif health_score >= 40:
                risk_level = "high"
            else:
                risk_level = "critical"

            recommendations = self._generate_health_recommendations(health_data)

            health = RepositoryHealth(
                repository_path=repo_path,
                repository_name=repo_name,
                stale_branches=health_data.get("stale_branches", []),
                unmerged_prs=health_data.get("unmerged_prs", 0),
                large_files=health_data.get("large_files", []),
                last_activity=datetime.fromisoformat(
                    health_data["last_activity_timestamp"]
                )
                if health_data.get("last_activity_timestamp")
                else None,
                health_score=health_score,
                risk_level=risk_level,
                recommendations=recommendations,
            )

            await self.broadcaster.broadcast_health_alert(repo_path, health)

            return health

        except Exception as e:
            logger.error(f"Failed to get repository health for {repo_path}: {e}")

            return RepositoryHealth(
                repository_path=repo_path,
                repository_name=repo_name,
                stale_branches=[],
                unmerged_prs=0,
                large_files=[],
                last_activity=None,
                health_score=0.0,
                risk_level="critical",
                recommendations=["Unable to collect health metrics"],
            )

    async def get_cross_project_patterns(
        self,
        project_paths: list[str] | list[Path] | None = None,
        days_back: int = 90,
    ) -> list[CrossProjectPattern]:
        if project_paths is None:
            project_paths = list(self._cache.keys())

        project_paths = [str(p) for p in project_paths]

        period_start = datetime.now() - timedelta(days=days_back)
        period_end = datetime.now()

        repositories = []
        for repo_path in project_paths:
            try:
                velocity = await self._collect_repository_velocity(
                    repo_path, period_start, period_end
                )
                repositories.append(velocity)
            except Exception as e:
                logger.warning(f"Failed to collect metrics from {repo_path}: {e}")
                continue

        return await self._detect_cross_project_patterns(repositories, days_back)

    async def _collect_repository_velocity(
        self,
        repo_path: str,
        period_start: datetime,
        period_end: datetime,
    ) -> RepositoryVelocity:
        from crackerjack.memory.git_metrics_storage import GitMetricsStorage

        storage = GitMetricsStorage(db_path=Path(".crackerjack/git_metrics.db"))
        repo_name = Path(repo_path).name

        metrics = storage.get_metrics(
            repository_path=repo_path,
            since=period_start,
            until=period_end,
        )

        total_commits = 0
        conventional_commits = 0
        breaking_changes = 0
        conflicts = 0

        for metric in metrics:
            if metric.metric_type == "commit_velocity":
                total_commits += int(metric.value)
            elif metric.metric_type == "conventional_commits":
                conventional_commits += int(metric.value)
            elif metric.metric_type == "breaking_changes":
                breaking_changes += int(metric.value)
            elif metric.metric_type == "merge_conflicts":
                conflicts += int(metric.value)

        days_period = (period_end - period_start).days
        avg_commits_per_day = total_commits / max(days_period, 1)
        avg_commits_per_week = avg_commits_per_day * 7
        conventional_compliance_rate = (
            conventional_commits / total_commits if total_commits > 0 else 0.0
        )
        merge_conflict_rate = conflicts / max(total_commits, 1)

        trend_direction: t.Literal["increasing", "stable", "decreasing"] = "stable"
        if avg_commits_per_day > 5.0:
            trend_direction = "increasing"
        elif avg_commits_per_day < 1.0:
            trend_direction = "decreasing"

        health_score = (
            (conventional_compliance_rate * 30)
            + (min(avg_commits_per_day, 10) / 10 * 30)
            + (max(0, 100 - merge_conflict_rate * 100) * 20)
            + (0 if breaking_changes == 0 else -breaking_changes * 5)
        )
        health_score = max(0, min(100, health_score))

        return RepositoryVelocity(
            repository_path=repo_path,
            repository_name=repo_name,
            period_start=period_start,
            period_end=period_end,
            total_commits=total_commits,
            avg_commits_per_day=avg_commits_per_day,
            avg_commits_per_week=avg_commits_per_week,
            conventional_compliance_rate=conventional_compliance_rate,
            breaking_changes=breaking_changes,
            merge_conflict_rate=merge_conflict_rate,
            health_score=health_score,
            trend_direction=trend_direction,
        )

    async def _detect_cross_project_patterns(
        self,
        repositories: list[RepositoryVelocity],
        days_back: int,
    ) -> list[CrossProjectPattern]:
        patterns = []

        declining = [
            r.repository_path
            for r in repositories
            if r.trend_direction == "decreasing" and r.avg_commits_per_day < 1.0
        ]
        if len(declining) >= 2:
            patterns.append(
                CrossProjectPattern(
                    pattern_type="declining_velocity",
                    affected_repositories=declining,
                    severity="warning",
                    description=f"{len(declining)} repositories show declining commit velocity",
                    metric_value=sum(
                        r.avg_commits_per_day
                        for r in repositories
                        if r.trend_direction == "decreasing"
                    ),
                    recommendation="Review team allocation and project priorities for declining repositories",
                    detected_at=datetime.now(),
                )
            )

        high_conflicts = [
            r.repository_path for r in repositories if r.merge_conflict_rate > 0.1
        ]
        if len(high_conflicts) >= 2:
            patterns.append(
                CrossProjectPattern(
                    pattern_type="high_conflicts",
                    affected_repositories=high_conflicts,
                    severity="warning",
                    description=f"{len(high_conflicts)} repositories have high merge conflict rates",
                    metric_value=sum(
                        r.merge_conflict_rate
                        for r in repositories
                        if r.merge_conflict_rate > 0.1
                    ),
                    recommendation="Implement better branch management and code review practices",
                    detected_at=datetime.now(),
                )
            )

        poor_compliance = [
            r.repository_path
            for r in repositories
            if r.conventional_compliance_rate < 0.5
        ]
        if len(poor_compliance) >= 2:
            patterns.append(
                CrossProjectPattern(
                    pattern_type="poor_compliance",
                    affected_repositories=poor_compliance,
                    severity="info",
                    description=f"{len(poor_compliance)} repositories have low conventional commit compliance",
                    metric_value=sum(
                        r.conventional_compliance_rate
                        for r in repositories
                        if r.conventional_compliance_rate < 0.5
                    ),
                    recommendation="Consider implementing commit linting tools and guidelines",
                    detected_at=datetime.now(),
                )
            )

        for pattern in patterns:
            await self.broadcaster.broadcast_pattern_detected(pattern)

        return patterns

    def _generate_health_recommendations(
        self, health_data: dict[str, t.Any]
    ) -> list[str]:
        recommendations = []

        stale_branches = health_data.get("stale_branches", [])
        if len(stale_branches) > 5:
            recommendations.append(f"Clean up {len(stale_branches)} stale branches")

        recent_activity = health_data.get("recent_activity_count", 0)
        if recent_activity == 0:
            recommendations.append(
                "No recent git activity detected - project may be abandoned"
            )

        health_score = health_data.get("health_score", 50)
        if health_score < 50:
            recommendations.append("Health score is low - review quality metrics")

        if not recommendations:
            recommendations.append("Repository health looks good")

        return recommendations

    def _generate_merge_recommendations(
        self,
        conflict_rate: float,
        rebase_ratio: float,
        conflicted_files: list[tuple[str, int]],
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
            top_file, count = conflicted_files[0]
            if count > 5:
                recommendations.append(
                    f"File '{top_file}' has {count} conflicts: "
                    "Consider splitting or redesigning to reduce conflicts"
                )

        if not recommendations:
            recommendations.append(
                "Merge patterns look healthy - no major issues detected"
            )

        return recommendations

    def _extract_best_practices(
        self, top_performers: list[RepositoryVelocity]
    ) -> list[dict[str, t.Any]]:
        practices = []

        if not top_performers:
            return practices

        avg_compliance = sum(
            r.conventional_compliance_rate for r in top_performers
        ) / len(top_performers)

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

        avg_velocity = sum(r.avg_commits_per_day for r in top_performers) / len(
            top_performers
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
        self,
        low_performers: list[RepositoryVelocity],
        best_practices: list[dict[str, t.Any]],
    ) -> list[dict[str, t.Any]]:
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
        self,
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


def create_mahavishnu_aggregator(
    config: MahavishnuConfig | None = None,
) -> MahavishnuAggregator:
    aggregator = MahavishnuAggregator(config=config)

    return aggregator
