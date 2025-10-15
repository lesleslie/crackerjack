"""Enhanced Quality Baseline Service with trending, alerts, and export capabilities."""

import json
import typing as t
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.quality.quality_baseline import (
    QualityBaselineService,
    QualityMetrics,
)


class TrendDirection(str, Enum):
    """Quality trend direction."""

    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    VOLATILE = "volatile"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class QualityTrend:
    """Quality trend analysis over time."""

    direction: TrendDirection
    change_rate: float  # Points per day
    confidence: float  # 0.0 to 1.0
    period_days: int
    recent_scores: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class QualityAlert:
    """Quality alert for significant changes."""

    severity: AlertSeverity
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    triggered_at: datetime
    git_hash: str | None = None

    def to_dict(self) -> dict[str, t.Any]:
        data = asdict(self)
        data["triggered_at"] = self.triggered_at.isoformat()
        return data


@dataclass
class UnifiedMetrics:
    """Unified metrics for real-time monitoring dashboard."""

    timestamp: datetime
    quality_score: int
    test_coverage: float
    hook_duration: float
    active_jobs: int
    error_count: int
    trend_direction: TrendDirection
    predictions: dict[str, t.Any] = field(default_factory=dict[str, t.Any])

    def to_dict(self) -> dict[str, t.Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class SystemHealthStatus:
    """System health status for monitoring."""

    overall_status: str  # "healthy", "warning", "critical"
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    service_status: dict[str, str] = field(default_factory=dict[str, t.Any])

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class DashboardState:
    """Complete dashboard state for real-time monitoring."""

    current_metrics: UnifiedMetrics
    historical_data: list[UnifiedMetrics]
    active_alerts: list[QualityAlert]
    system_health: SystemHealthStatus
    recommendations: list[str]
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "current_metrics": self.current_metrics.to_dict(),
            "historical_data": [metrics.to_dict() for metrics in self.historical_data],
            "active_alerts": [alert.to_dict() for alert in self.active_alerts],
            "system_health": self.system_health.to_dict(),
            "recommendations": self.recommendations,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class QualityReport:
    """Comprehensive quality report."""

    current_metrics: QualityMetrics | None
    trend: QualityTrend | None
    alerts: list[QualityAlert]
    historical_data: list[QualityMetrics]
    recommendations: list[str]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "current_metrics": self.current_metrics.to_dict()
            if self.current_metrics
            else None,
            "trend": self.trend.to_dict() if self.trend else None,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "historical_data": [metrics.to_dict() for metrics in self.historical_data],
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
        }


class EnhancedQualityBaselineService(QualityBaselineService):
    """Enhanced quality baseline service with advanced analytics."""

    def __init__(
        self,
        cache: CrackerjackCache | None = None,
        alert_thresholds: dict[str, float] | None = None,
    ) -> None:
        super().__init__(cache)
        self.alert_thresholds = alert_thresholds or {
            "quality_score_drop": 10.0,  # Alert if score drops by 10+ points
            "coverage_drop": 5.0,  # Alert if coverage drops by 5%+
            "test_pass_rate_drop": 10.0,  # Alert if pass rate drops by 10%+
            "security_issues_increase": 1,  # Alert on any security issue increase
            "type_errors_threshold": 10,  # Alert if type errors exceed 10
        }

    def analyze_quality_trend(
        self, days: int = 30, min_data_points: int = 5
    ) -> QualityTrend | None:
        """Analyze quality trend over specified period."""
        baselines = self.get_recent_baselines(
            limit=days * 2
        )  # Get more data for analysis

        if len(baselines) < min_data_points:
            return None

        # Filter to specified period
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_baselines = [b for b in baselines if b.timestamp >= cutoff_date]

        if len(recent_baselines) < min_data_points:
            return None

        # Calculate trend
        scores = [b.quality_score for b in recent_baselines]
        timestamps = [
            (b.timestamp - cutoff_date).total_seconds() / 86400
            for b in recent_baselines
        ]

        # Simple linear regression for trend
        n = len(scores)
        sum_x = sum(timestamps)
        sum_y = sum(scores)
        sum_xy = sum(x * y for x, y in zip(timestamps, scores))
        sum_x2 = sum(x * x for x in timestamps)

        if n * sum_x2 - sum_x * sum_x == 0:
            slope: float = 0.0
        else:
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        # Determine direction and confidence
        abs_slope = abs(slope)

        if abs_slope < 0.1:
            direction = TrendDirection.STABLE
        elif slope > 0:
            direction = TrendDirection.IMPROVING
        else:
            direction = TrendDirection.DECLINING

        # Calculate volatility (standard deviation of scores)
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        volatility = variance**0.5

        if volatility > 15:  # High volatility threshold
            direction = TrendDirection.VOLATILE

        # Confidence based on data consistency and amount
        confidence = min(1.0, (len(scores) / 10) * (1 / (volatility + 1)))

        return QualityTrend(
            direction=direction,
            change_rate=slope,
            confidence=confidence,
            period_days=days,
            recent_scores=scores[-10:],  # Last 10 scores
        )

    def check_quality_alerts(
        self, current_metrics: dict[str, t.Any], baseline_git_hash: str | None = None
    ) -> list[QualityAlert]:
        """Check for quality alerts based on thresholds."""
        alerts: list[QualityAlert] = []
        baseline = self.get_baseline(baseline_git_hash)

        if not baseline:
            return alerts

        # Filter metrics to only include parameters that calculate_quality_score accepts
        score_metrics = {
            k: v
            for k, v in current_metrics.items()
            if k
            in (
                "coverage_percent",
                "test_pass_rate",
                "hook_failures",
                "complexity_violations",
                "security_issues",
                "type_errors",
                "linting_issues",
            )
        }
        current_score = self.calculate_quality_score(**score_metrics)
        git_hash = self.get_current_git_hash()

        # Quality score drop alert
        score_drop = baseline.quality_score - current_score
        if score_drop >= self.alert_thresholds["quality_score_drop"]:
            alerts.append(
                QualityAlert(
                    severity=AlertSeverity.CRITICAL
                    if score_drop >= 20
                    else AlertSeverity.WARNING,
                    message=f"Quality score dropped by {score_drop:.1f} points (from {baseline.quality_score} to {current_score})",
                    metric_name="quality_score",
                    current_value=current_score,
                    threshold_value=baseline.quality_score
                    - self.alert_thresholds["quality_score_drop"],
                    triggered_at=datetime.now(),
                    git_hash=git_hash,
                )
            )

        # Coverage drop alert
        coverage_drop = baseline.coverage_percent - current_metrics.get(
            "coverage_percent", 0
        )
        if coverage_drop >= self.alert_thresholds["coverage_drop"]:
            alerts.append(
                QualityAlert(
                    severity=AlertSeverity.WARNING,
                    message=f"Test coverage dropped by {coverage_drop:.1f}% (from {baseline.coverage_percent:.1f}% to {current_metrics.get('coverage_percent', 0):.1f}%)",
                    metric_name="coverage_percent",
                    current_value=current_metrics.get("coverage_percent", 0),
                    threshold_value=baseline.coverage_percent
                    - self.alert_thresholds["coverage_drop"],
                    triggered_at=datetime.now(),
                    git_hash=git_hash,
                )
            )

        # Security issues increase alert
        security_increase = (
            current_metrics.get("security_issues", 0) - baseline.security_issues
        )
        if security_increase >= self.alert_thresholds["security_issues_increase"]:
            alerts.append(
                QualityAlert(
                    severity=AlertSeverity.CRITICAL,
                    message=f"Security issues increased by {security_increase} (from {baseline.security_issues} to {current_metrics.get('security_issues', 0)})",
                    metric_name="security_issues",
                    current_value=current_metrics.get("security_issues", 0),
                    threshold_value=baseline.security_issues
                    + self.alert_thresholds["security_issues_increase"]
                    - 1,
                    triggered_at=datetime.now(),
                    git_hash=git_hash,
                )
            )

        # Type errors threshold alert
        type_errors = current_metrics.get("type_errors", 0)
        if type_errors >= self.alert_thresholds["type_errors_threshold"]:
            alerts.append(
                QualityAlert(
                    severity=AlertSeverity.WARNING,
                    message=f"Type errors ({type_errors}) exceed threshold ({self.alert_thresholds['type_errors_threshold']})",
                    metric_name="type_errors",
                    current_value=type_errors,
                    threshold_value=self.alert_thresholds["type_errors_threshold"],
                    triggered_at=datetime.now(),
                    git_hash=git_hash,
                )
            )

        return alerts

    def generate_recommendations(
        self,
        current_metrics: dict[str, t.Any],
        trend: QualityTrend | None,
        alerts: list[QualityAlert],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations: list[str] = []

        # Generate different types of recommendations
        self._add_coverage_recommendations(current_metrics, recommendations)
        self._add_error_recommendations(current_metrics, recommendations)
        self._add_trend_recommendations(trend, recommendations)
        self._add_alert_recommendations(alerts, recommendations)
        self._add_general_recommendations(current_metrics, recommendations)

        return recommendations

    def _add_coverage_recommendations(
        self, metrics: dict[str, t.Any], recommendations: list[str]
    ) -> None:
        """Add coverage-based recommendations."""
        coverage = metrics.get("coverage_percent", 0)
        if coverage < 80:
            recommendations.append(
                f"📊 Increase test coverage from {coverage:.1f}% to 80%+ by adding tests for uncovered code paths"
            )
        elif coverage < 95:
            recommendations.append(
                f"🎯 Consider targeting 95%+ coverage (currently {coverage:.1f}%) for better code quality"
            )

    def _add_error_recommendations(
        self, metrics: dict[str, t.Any], recommendations: list[str]
    ) -> None:
        """Add error-based recommendations."""
        type_errors = metrics.get("type_errors", 0)
        if type_errors > 0:
            recommendations.append(
                f"🔧 Fix {type_errors} type errors to improve code reliability"
            )

        security_issues = metrics.get("security_issues", 0)
        if security_issues > 0:
            recommendations.append(
                f"🔒 Address {security_issues} security issues immediately"
            )

    def _add_trend_recommendations(
        self, trend: QualityTrend | None, recommendations: list[str]
    ) -> None:
        """Add trend-based recommendations."""
        if not trend:
            return

        trend_messages = {
            TrendDirection.DECLINING: "📉 Quality trend is declining - consider code review process improvements",
            TrendDirection.VOLATILE: "⚠️ Quality is volatile - implement more consistent testing practices",
            TrendDirection.IMPROVING: "📈 Great job! Quality is improving - maintain current practices",
        }

        message = trend_messages.get(trend.direction)
        if message:
            recommendations.append(message)

    def _add_alert_recommendations(
        self, alerts: list[QualityAlert], recommendations: list[str]
    ) -> None:
        """Add alert-based recommendations."""
        critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        if critical_alerts:
            recommendations.append(
                f"🚨 Address {len(critical_alerts)} critical quality issues before proceeding"
            )

    def _add_general_recommendations(
        self, metrics: dict[str, t.Any], recommendations: list[str]
    ) -> None:
        """Add general recommendations."""
        hook_failures = metrics.get("hook_failures", 0)
        if hook_failures > 0:
            recommendations.append(
                f"⚙️ Fix {hook_failures} pre-commit hook failures to streamline development"
            )

    def generate_comprehensive_report(
        self, current_metrics: dict[str, t.Any] | None = None, days: int = 30
    ) -> QualityReport:
        """Generate comprehensive quality report."""
        # Get current metrics or create from latest baseline
        current_baseline = None
        if current_metrics:
            git_hash = self.get_current_git_hash()
            if git_hash:
                # Filter metrics to only include parameters that calculate_quality_score accepts
                score_metrics = {
                    k: v
                    for k, v in current_metrics.items()
                    if k
                    in (
                        "coverage_percent",
                        "test_pass_rate",
                        "hook_failures",
                        "complexity_violations",
                        "security_issues",
                        "type_errors",
                        "linting_issues",
                    )
                }
                quality_score = self.calculate_quality_score(**score_metrics)
                current_baseline = QualityMetrics(
                    git_hash=git_hash,
                    timestamp=datetime.now(),
                    coverage_percent=current_metrics.get("coverage_percent", 0.0),
                    test_count=current_metrics.get("test_count", 0),
                    test_pass_rate=current_metrics.get("test_pass_rate", 0.0),
                    hook_failures=current_metrics.get("hook_failures", 0),
                    complexity_violations=current_metrics.get(
                        "complexity_violations", 0
                    ),
                    security_issues=current_metrics.get("security_issues", 0),
                    type_errors=current_metrics.get("type_errors", 0),
                    linting_issues=current_metrics.get("linting_issues", 0),
                    quality_score=quality_score,
                )
        else:
            current_baseline = self.get_baseline()

        # Analyze trend
        trend = self.analyze_quality_trend(days=days)

        # Check alerts
        alerts = []
        if current_metrics:
            alerts = self.check_quality_alerts(current_metrics)

        # Get historical data
        historical_data = self.get_recent_baselines(limit=days)

        # Generate recommendations
        metrics_dict = current_metrics or (
            {
                "coverage_percent": current_baseline.coverage_percent,
                "test_count": current_baseline.test_count,
                "test_pass_rate": current_baseline.test_pass_rate,
                "hook_failures": current_baseline.hook_failures,
                "complexity_violations": current_baseline.complexity_violations,
                "security_issues": current_baseline.security_issues,
                "type_errors": current_baseline.type_errors,
                "linting_issues": current_baseline.linting_issues,
            }
            if current_baseline
            else {}
        )

        recommendations = self.generate_recommendations(metrics_dict, trend, alerts)

        return QualityReport(
            current_metrics=current_baseline,
            trend=trend,
            alerts=alerts,
            historical_data=historical_data,
            recommendations=recommendations,
        )

    def export_report(
        self, report: QualityReport, output_path: Path, format: str = "json"
    ) -> None:
        """Export quality report to file."""
        if format.lower() == "json":
            with output_path.open("w") as f:
                json.dump(report.to_dict(), f, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def set_alert_threshold(self, metric: str, threshold: float) -> None:
        """Update alert threshold for specific metric."""
        self.alert_thresholds[metric] = threshold

    def get_alert_thresholds(self) -> dict[str, float]:
        """Get current alert thresholds."""
        return self.alert_thresholds.copy()

    def create_unified_metrics(
        self, current_metrics: dict[str, t.Any], active_job_count: int = 0
    ) -> UnifiedMetrics:
        """Create UnifiedMetrics from current quality data."""
        # Calculate quality score
        score_metrics = {
            k: v
            for k, v in current_metrics.items()
            if k
            in (
                "coverage_percent",
                "test_pass_rate",
                "hook_failures",
                "complexity_violations",
                "security_issues",
                "type_errors",
                "linting_issues",
            )
        }
        quality_score = self.calculate_quality_score(**score_metrics)

        # Get trend direction
        trend = self.analyze_quality_trend(days=7)
        trend_direction = trend.direction if trend else TrendDirection.STABLE

        # Calculate error count
        error_count = (
            current_metrics.get("hook_failures", 0)
            + current_metrics.get("security_issues", 0)
            + current_metrics.get("type_errors", 0)
            + current_metrics.get("linting_issues", 0)
        )

        # Create predictions based on trend
        predictions = {}
        if trend and trend.confidence > 0.5:
            days_ahead = 7
            predicted_score = quality_score + (trend.change_rate * days_ahead)
            predictions["quality_score_7_days"] = max(0.0, min(100.0, predicted_score))

        return UnifiedMetrics(
            timestamp=datetime.now(),
            quality_score=quality_score,
            test_coverage=current_metrics.get("coverage_percent", 0.0),
            hook_duration=current_metrics.get("hook_duration", 0.0),
            active_jobs=active_job_count,
            error_count=error_count,
            trend_direction=trend_direction,
            predictions=predictions,
        )

    def get_system_health(self) -> SystemHealthStatus:
        """Get current system health status."""
        import psutil

        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            # Determine overall status
            if cpu_percent > 90 or memory.percent > 90 or disk.percent > 95:
                overall_status = "critical"
            elif cpu_percent > 70 or memory.percent > 80 or disk.percent > 85:
                overall_status = "warning"
            else:
                overall_status = "healthy"

            service_status = {
                "quality_baseline": "healthy",
                "git": "healthy" if self.get_current_git_hash() else "warning",
                "cache": "healthy" if self.cache else "warning",
            }

            return SystemHealthStatus(
                overall_status=overall_status,
                cpu_usage=cpu_percent,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                service_status=service_status,
            )
        except ImportError:
            # psutil not available, return basic status
            return SystemHealthStatus(
                overall_status="healthy",
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                service_status={"quality_baseline": "healthy"},
            )

    def create_dashboard_state(
        self,
        current_metrics: dict[str, t.Any],
        active_job_count: int = 0,
        historical_days: int = 30,
    ) -> DashboardState:
        """Create complete dashboard state for monitoring."""
        # Create current unified metrics
        unified_metrics = self.create_unified_metrics(current_metrics, active_job_count)

        # Get historical data and convert to UnifiedMetrics
        historical_baselines = self.get_recent_baselines(limit=historical_days)
        historical_unified = [
            UnifiedMetrics(
                timestamp=baseline.timestamp,
                quality_score=baseline.quality_score,
                test_coverage=baseline.coverage_percent,
                hook_duration=0.0,  # Not tracked in baseline
                active_jobs=0,  # Historical data
                error_count=(
                    baseline.hook_failures
                    + baseline.security_issues
                    + baseline.type_errors
                    + baseline.linting_issues
                ),
                trend_direction=TrendDirection.STABLE,  # Calculate per point if needed
                predictions={},
            )
            for baseline in historical_baselines[-10:]  # Last 10 data points
        ]

        # Get active alerts
        alerts = self.check_quality_alerts(current_metrics)

        # Get system health
        system_health = self.get_system_health()

        # Generate recommendations
        trend = self.analyze_quality_trend(days=7)
        recommendations = self.generate_recommendations(current_metrics, trend, alerts)

        return DashboardState(
            current_metrics=unified_metrics,
            historical_data=historical_unified,
            active_alerts=alerts,
            system_health=system_health,
            recommendations=recommendations,
        )
