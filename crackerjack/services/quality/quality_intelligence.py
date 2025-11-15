"""Advanced ML-based quality intelligence with anomaly detection and predictive analytics."""

import json
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

import numpy as np
from scipy import stats

from crackerjack.models.protocols import QualityIntelligenceProtocol

from .quality_baseline_enhanced import (
    AlertSeverity,
    EnhancedQualityBaselineService,
    TrendDirection,
)


class AnomalyType(str, Enum):
    """Types of anomalies that can be detected."""

    SPIKE = "spike"  # Sudden increase in metrics
    DROP = "drop"  # Sudden decrease in metrics
    DRIFT = "drift"  # Gradual change over time
    OSCILLATION = "oscillation"  # Unusual fluctuation patterns
    OUTLIER = "outlier"  # Statistical outlier


class PatternType(str, Enum):
    """Types of patterns that can be identified."""

    CYCLIC = "cyclic"  # Regular recurring patterns
    SEASONAL = "seasonal"  # Time-based patterns
    CORRELATION = "correlation"  # Metric correlation patterns
    REGRESSION = "regression"  # Quality regression patterns
    IMPROVEMENT = "improvement"  # Quality improvement patterns


@dataclass
class QualityAnomaly:
    """Detected quality anomaly with ML confidence."""

    anomaly_type: AnomalyType
    metric_name: str
    detected_at: datetime
    confidence: float  # 0.0 to 1.0
    severity: AlertSeverity
    description: str
    actual_value: float
    expected_value: float
    deviation_sigma: float  # Standard deviations from normal
    context: dict[str, t.Any] = field(default_factory=dict[str, t.Any])

    def to_dict(self) -> dict[str, t.Any]:
        data = {
            "anomaly_type": self.anomaly_type,
            "metric_name": self.metric_name,
            "detected_at": self.detected_at.isoformat(),
            "confidence": self.confidence,
            "severity": self.severity,
            "description": self.description,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "deviation_sigma": self.deviation_sigma,
            "context": self.context,
        }
        return data


@dataclass
class QualityPattern:
    """Identified quality pattern with statistical analysis."""

    pattern_type: PatternType
    metric_names: list[str]
    detected_at: datetime
    confidence: float
    description: str
    period_days: int
    correlation_strength: float  # For correlation patterns
    trend_direction: TrendDirection
    statistical_significance: float  # p-value
    context: dict[str, t.Any] = field(default_factory=dict[str, t.Any])

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "pattern_type": self.pattern_type,
            "metric_names": self.metric_names,
            "detected_at": self.detected_at.isoformat(),
            "confidence": self.confidence,
            "description": self.description,
            "period_days": self.period_days,
            "correlation_strength": self.correlation_strength,
            "trend_direction": self.trend_direction,
            "statistical_significance": self.statistical_significance,
            "context": self.context,
        }


@dataclass
class QualityPrediction:
    """Advanced quality prediction with confidence intervals."""

    metric_name: str
    predicted_value: float
    confidence_lower: float
    confidence_upper: float
    confidence_level: float  # e.g., 0.95 for 95% confidence
    prediction_horizon_days: int
    prediction_method: str
    created_at: datetime
    factors: list[str] = field(default_factory=list)
    risk_assessment: str = "low"  # low, medium, high

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "metric_name": self.metric_name,
            "predicted_value": self.predicted_value,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
            "confidence_level": self.confidence_level,
            "prediction_horizon_days": self.prediction_horizon_days,
            "prediction_method": self.prediction_method,
            "created_at": self.created_at.isoformat(),
            "factors": self.factors,
            "risk_assessment": self.risk_assessment,
        }


@dataclass
class QualityInsights:
    """Comprehensive quality insights with ML analysis."""

    anomalies: list[QualityAnomaly]
    patterns: list[QualityPattern]
    predictions: list[QualityPrediction]
    recommendations: list[str]
    overall_health_score: float  # 0.0 to 1.0
    risk_level: str  # low, medium, high, critical
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "anomalies": [a.to_dict() for a in self.anomalies],
            "patterns": [p.to_dict() for p in self.patterns],
            "predictions": [p.to_dict() for p in self.predictions],
            "recommendations": self.recommendations,
            "overall_health_score": self.overall_health_score,
            "risk_level": self.risk_level,
            "generated_at": self.generated_at.isoformat(),
        }


class QualityIntelligenceService(QualityIntelligenceProtocol):
    """Advanced ML-based quality intelligence service."""

    def __init__(
        self,
        quality_service: EnhancedQualityBaselineService,
        anomaly_sensitivity: float = 2.0,  # Standard deviations for anomaly detection
        min_data_points: int = 10,
    ) -> None:
        self.quality_service = quality_service
        self.anomaly_sensitivity = anomaly_sensitivity
        self.min_data_points = min_data_points

    def detect_anomalies(
        self, days: int = 30, metrics: list[str] | None = None
    ) -> list[QualityAnomaly]:
        """Detect anomalies in quality metrics using statistical analysis (sync version)."""
        metrics = self._get_default_metrics() if metrics is None else metrics

        baselines = self.quality_service.get_recent_baselines(limit=days * 2)
        if len(baselines) < self.min_data_points:
            return []

        anomalies = []
        for metric_name in metrics:
            metric_anomalies = self._detect_metric_anomalies(metric_name, baselines)
            anomalies.extend(metric_anomalies)

        return anomalies

    async def detect_anomalies_async(
        self, days: int = 30, metrics: list[str] | None = None
    ) -> list[QualityAnomaly]:
        """Detect anomalies in quality metrics using statistical analysis (async version)."""
        metrics = self._get_default_metrics() if metrics is None else metrics

        baselines = await self.quality_service.aget_recent_baselines(limit=days * 2)
        if len(baselines) < self.min_data_points:
            return []

        anomalies = []
        for metric_name in metrics:
            metric_anomalies = self._detect_metric_anomalies(metric_name, baselines)
            anomalies.extend(metric_anomalies)

        return anomalies

    def _get_default_metrics(self) -> list[str]:
        """Get default metrics list[t.Any] for anomaly detection."""
        return [
            "quality_score",
            "coverage_percent",
            "hook_failures",
            "security_issues",
            "type_errors",
            "linting_issues",
        ]

    def _detect_metric_anomalies(
        self, metric_name: str, baselines: list[t.Any]
    ) -> list[QualityAnomaly]:
        """Detect anomalies for a specific metric."""
        values, timestamps = self._extract_metric_values(metric_name, baselines)

        if len(values) < self.min_data_points:
            return []

        stats_data = self._calculate_statistical_metrics(values)
        if stats_data is None:  # No variation
            return []

        return self._identify_outlier_anomalies(
            metric_name, values, timestamps, stats_data
        )

    def _extract_metric_values(
        self, metric_name: str, baselines: list[t.Any]
    ) -> tuple[list[float], list[t.Any]]:
        """Extract metric values and timestamps from baselines."""
        values = []
        timestamps = []

        for baseline in baselines:
            metric_value = self._get_baseline_metric_value(baseline, metric_name)
            if metric_value is not None:
                values.append(metric_value)
                timestamps.append(baseline.timestamp)

        return values, timestamps

    def _get_baseline_metric_value(
        self, baseline: t.Any, metric_name: str
    ) -> float | None:
        """Get metric value from baseline object."""
        metric_mapping = {
            "quality_score": baseline.quality_score,
            "coverage_percent": baseline.coverage_percent,
            "hook_failures": baseline.hook_failures,
            "security_issues": baseline.security_issues,
            "type_errors": baseline.type_errors,
            "linting_issues": baseline.linting_issues,
        }
        return metric_mapping.get(metric_name)

    def _calculate_statistical_metrics(
        self, values: list[float]
    ) -> dict[str, float] | None:
        """Calculate statistical metrics for anomaly detection."""
        values_array = np.array(values)
        mean_val = np.mean(values_array)
        std_val = np.std(values_array)

        if std_val == 0:
            return None  # No variation to detect anomalies

        z_scores = np.abs((values_array - mean_val) / std_val)

        return {
            "mean": mean_val,
            "std": std_val,
            "z_scores": z_scores,
            "values_array": values_array,
        }

    def _identify_outlier_anomalies(
        self,
        metric_name: str,
        values: list[float],
        timestamps: list[t.Any],
        stats_data: dict[str, t.Any],
    ) -> list[QualityAnomaly]:
        """Identify outlier anomalies based on z-scores."""
        anomalies = []
        z_scores = stats_data["z_scores"]
        mean_val = stats_data["mean"]
        std_val = stats_data["std"]

        for i, (value, timestamp, z_score) in enumerate(
            zip(values, timestamps, z_scores)
        ):
            if z_score > self.anomaly_sensitivity:
                anomaly = self._create_anomaly_object(
                    metric_name,
                    value,
                    timestamp,
                    z_score,
                    mean_val,
                    std_val,
                    i,
                    len(values),
                )
                anomalies.append(anomaly)

        return anomalies

    def _create_anomaly_object(
        self,
        metric_name: str,
        value: float,
        timestamp: t.Any,
        z_score: float,
        mean_val: float,
        std_val: float,
        position: int,
        data_points: int,
    ) -> QualityAnomaly:
        """Create QualityAnomaly object from detected outlier."""
        anomaly_type, severity = self._determine_anomaly_type_and_severity(
            value, mean_val, z_score
        )
        confidence = min(1.0, z_score / 4.0)  # Scale to 0-1

        return QualityAnomaly(
            anomaly_type=anomaly_type,
            metric_name=metric_name,
            detected_at=timestamp,
            confidence=confidence,
            severity=severity,
            description=f"{metric_name} {anomaly_type} detected: {value:.2f} (expected ~{mean_val:.2f})",
            actual_value=value,
            expected_value=mean_val,
            deviation_sigma=z_score,
            context={
                "metric_mean": mean_val,
                "metric_std": std_val,
                "data_points": data_points,
                "position_in_series": position,
            },
        )

    def _determine_anomaly_type_and_severity(
        self, value: float, mean_val: float, z_score: float
    ) -> tuple[AnomalyType, AlertSeverity]:
        """Determine anomaly type and severity based on value and z-score."""
        if value > mean_val:
            anomaly_type = AnomalyType.SPIKE
        else:
            anomaly_type = AnomalyType.DROP

        severity = AlertSeverity.CRITICAL if z_score > 3.0 else AlertSeverity.WARNING

        return anomaly_type, severity

    def identify_patterns(self, days: int = 60) -> list[QualityPattern]:
        """Identify patterns in quality metrics using correlation and trend analysis (sync version)."""
        baselines = self.quality_service.get_recent_baselines(limit=days * 2)
        if len(baselines) < self.min_data_points:
            return []

        metrics_data = self._extract_metrics_data(baselines)
        return self._find_correlation_patterns(metrics_data, days)

    async def identify_patterns_async(self, days: int = 60) -> list[QualityPattern]:
        """Identify patterns in quality metrics using correlation and trend analysis (async version)."""
        baselines = await self.quality_service.aget_recent_baselines(limit=days * 2)
        if len(baselines) < self.min_data_points:
            return []

        metrics_data = self._extract_metrics_data(baselines)
        return self._find_correlation_patterns(metrics_data, days)

    def _extract_metrics_data(self, baselines: list[t.Any]) -> dict[str, list[float]]:
        """Extract metric data from baselines for correlation analysis."""
        metrics_data = {
            "quality_score": [],
            "coverage_percent": [],
            "hook_failures": [],
            "security_issues": [],
            "type_errors": [],
            "linting_issues": [],
        }

        for baseline in baselines:
            metrics_data["quality_score"].append(baseline.quality_score)
            metrics_data["coverage_percent"].append(baseline.coverage_percent)
            metrics_data["hook_failures"].append(baseline.hook_failures)
            metrics_data["security_issues"].append(baseline.security_issues)
            metrics_data["type_errors"].append(baseline.type_errors)
            metrics_data["linting_issues"].append(baseline.linting_issues)

        return metrics_data

    def _find_correlation_patterns(
        self, metrics_data: dict[str, list[float]], days: int
    ) -> list[QualityPattern]:
        """Find correlation patterns between metrics."""
        patterns = []
        metric_names = list[t.Any](metrics_data.keys())

        for i, metric1 in enumerate(metric_names):
            for metric2 in metric_names[i + 1 :]:
                pattern = self._analyze_metric_correlation(
                    metric1, metric2, metrics_data, days
                )
                if pattern:
                    patterns.append(pattern)

        return patterns

    def _analyze_metric_correlation(
        self,
        metric1: str,
        metric2: str,
        metrics_data: dict[str, list[float]],
        days: int,
    ) -> QualityPattern | None:
        """Analyze correlation between two metrics."""
        values1 = np.array(metrics_data[metric1])
        values2 = np.array(metrics_data[metric2])

        if len(values1) < self.min_data_points:
            return None

        # Handle constant input arrays that would cause correlation warnings
        try:
            # Check for constant arrays (all values the same)
            if 0 in (np.var(values1), np.var(values2)):
                # Cannot calculate correlation for constant arrays
                return None

            correlation, p_value = stats.pearsonr(values1, values2)
        except (ValueError, RuntimeWarning):
            # Handle any other correlation calculation issues
            return None

        # Strong correlation threshold
        if abs(correlation) > 0.7 and p_value < 0.05:
            return self._create_correlation_pattern(
                metric1, metric2, correlation, p_value, values1, days
            )

        return None

    def _create_correlation_pattern(
        self,
        metric1: str,
        metric2: str,
        correlation: float,
        p_value: float,
        values1: np.ndarray,
        days: int,
    ) -> QualityPattern:
        """Create a quality pattern from correlation analysis."""
        trend_dir, description = self._get_correlation_trend_and_description(
            metric1, metric2, correlation
        )

        return QualityPattern(
            pattern_type=PatternType.CORRELATION,
            metric_names=[metric1, metric2],
            detected_at=datetime.now(),
            confidence=abs(correlation),
            description=description,
            period_days=days,
            correlation_strength=abs(correlation),
            trend_direction=trend_dir,
            statistical_significance=p_value,
            context={
                "correlation_coefficient": correlation,
                "sample_size": len(values1),
                "strength": self._get_correlation_strength_label(correlation),
            },
        )

    def _get_correlation_trend_and_description(
        self, metric1: str, metric2: str, correlation: float
    ) -> tuple[TrendDirection, str]:
        """Get trend direction and description for correlation."""
        if correlation > 0:
            return (
                TrendDirection.IMPROVING,
                f"Strong positive correlation between {metric1} and {metric2}",
            )
        return (
            TrendDirection.DECLINING,
            f"Strong negative correlation between {metric1} and {metric2}",
        )

    def _get_correlation_strength_label(self, correlation: float) -> str:
        """Get strength label for correlation coefficient."""
        abs_corr = abs(correlation)
        if abs_corr > 0.9:
            return "very strong"
        elif abs_corr > 0.7:
            return "strong"
        return "moderate"

    def generate_advanced_predictions(
        self, horizon_days: int = 14, confidence_level: float = 0.95
    ) -> list[QualityPrediction]:
        """Generate advanced predictions with confidence intervals."""
        baselines = self.quality_service.get_recent_baselines(limit=90)
        if len(baselines) < self.min_data_points:
            return []

        predictions = []
        metrics = ["quality_score", "coverage_percent"]

        for metric_name in metrics:
            values, timestamps = self._extract_time_series(baselines, metric_name)

            if len(values) < self.min_data_points:
                continue

            prediction = self._create_metric_prediction(
                metric_name, values, horizon_days, confidence_level
            )
            predictions.append(prediction)

        return predictions

    def _extract_time_series(
        self, baselines: list[t.Any], metric_name: str
    ) -> tuple[list[t.Any], list[t.Any]]:
        """Extract time series data for specified metric."""
        values = []
        timestamps = []

        for baseline in baselines:
            if metric_name == "quality_score":
                values.append(baseline.quality_score)
            elif metric_name == "coverage_percent":
                values.append(baseline.coverage_percent)
            timestamps.append(baseline.timestamp)

        return values, timestamps

    def _create_metric_prediction(
        self,
        metric_name: str,
        values: list[t.Any],
        horizon_days: int,
        confidence_level: float,
    ) -> QualityPrediction:
        """Create prediction for a single metric."""
        regression_results = self._perform_linear_regression(values, horizon_days)
        confidence_bounds = self._calculate_confidence_interval(
            values, regression_results, confidence_level
        )
        risk_level = self._assess_prediction_risk(
            metric_name, regression_results["predicted_value"]
        )

        return QualityPrediction(
            metric_name=metric_name,
            predicted_value=float(regression_results["predicted_value"]),
            confidence_lower=float(confidence_bounds["lower"]),
            confidence_upper=float(confidence_bounds["upper"]),
            confidence_level=confidence_level,
            prediction_horizon_days=horizon_days,
            prediction_method="linear_regression_with_confidence_intervals",
            created_at=datetime.now(),
            factors=["historical_trend", "statistical_analysis"],
            risk_assessment=risk_level,
        )

    def _perform_linear_regression(
        self, values: list[t.Any], horizon_days: int
    ) -> dict[str, t.Any]:
        """Perform linear regression and predict future value."""
        values_array = np.array(values)
        time_indices = np.arange(len(values))

        slope, intercept, r_value, p_value, std_err = stats.linregress(
            time_indices, values_array
        )

        future_index = len(values) + horizon_days
        predicted_value = slope * future_index + intercept

        return {
            "slope": slope,
            "intercept": intercept,
            "predicted_value": predicted_value,
            "time_indices": time_indices,
            "values_array": values_array,
            "horizon_days": horizon_days,
        }

    def _calculate_confidence_interval(
        self,
        values: list[t.Any],
        regression_results: dict[str, t.Any],
        confidence_level: float,
    ) -> dict[str, t.Any]:
        """Calculate confidence interval for prediction."""
        slope = regression_results["slope"]
        intercept = regression_results["intercept"]
        time_indices = regression_results["time_indices"]
        values_array = regression_results["values_array"]
        predicted_value = regression_results["predicted_value"]

        residuals = values_array - (slope * time_indices + intercept)
        residual_std = np.std(residuals)

        future_index = len(values) + regression_results["horizon_days"]
        t_value = stats.t.ppf((1 + confidence_level) / 2, len(values) - 2)

        margin_error = self._calculate_margin_error(
            t_value, residual_std, len(values), future_index, time_indices
        )

        return {
            "lower": predicted_value - margin_error,
            "upper": predicted_value + margin_error,
        }

    def _calculate_margin_error(
        self,
        t_value: float,
        residual_std: float,
        n_values: int,
        future_index: int,
        time_indices: np.ndarray,
    ) -> float:
        """Calculate margin of error for confidence interval."""
        mean_time: float = float(np.mean(time_indices))
        sum_sq_diff: float = float(np.sum((time_indices - mean_time) ** 2))
        numerator: float = (future_index - mean_time) ** 2

        sqrt_term: float = float(np.sqrt(1 + 1 / n_values + numerator / sum_sq_diff))
        return t_value * residual_std * sqrt_term

    def _assess_prediction_risk(self, metric_name: str, predicted_value: float) -> str:
        """Assess risk level based on predicted value."""
        if metric_name == "quality_score":
            return self._assess_quality_score_risk(predicted_value)
        # coverage_percent
        return self._assess_coverage_risk(predicted_value)

    def _assess_quality_score_risk(self, predicted_value: float) -> str:
        """Assess risk for quality score predictions."""
        if predicted_value < 70:
            return "critical"
        elif predicted_value < 80:
            return "high"
        elif predicted_value < 90:
            return "medium"
        return "low"

    def _assess_coverage_risk(self, predicted_value: float) -> str:
        """Assess risk for coverage predictions."""
        if predicted_value < 70:
            return "high"
        elif predicted_value < 85:
            return "medium"
        return "low"

    def generate_ml_recommendations(
        self,
        anomalies: list[QualityAnomaly],
        patterns: list[QualityPattern],
        predictions: list[QualityPrediction],
    ) -> list[str]:
        """Generate intelligent recommendations based on ML analysis."""
        recommendations = []

        # Anomaly-based recommendations
        critical_anomalies = [
            a for a in anomalies if a.severity == AlertSeverity.CRITICAL
        ]
        if critical_anomalies:
            recommendations.append(
                f"🚨 CRITICAL: {len(critical_anomalies)} critical anomalies detected - immediate investigation required"
            )

        quality_drops = [
            a
            for a in anomalies
            if a.anomaly_type == AnomalyType.DROP and a.metric_name == "quality_score"
        ]
        if quality_drops:
            recommendations.append(
                "📉 Quality score drops detected - review recent commits and implement quality gates"
            )

        # Pattern-based recommendations
        declining_correlations = [
            p for p in patterns if p.trend_direction == TrendDirection.DECLINING
        ]
        if declining_correlations:
            recommendations.append(
                f"⚠️ Negative quality correlations identified - investigate dependencies between {declining_correlations[0].metric_names}"
            )

        strong_patterns = [p for p in patterns if p.confidence > 0.8]
        if strong_patterns:
            recommendations.append(
                "📊 Strong quality patterns detected - leverage insights for predictive quality management"
            )

        # Prediction-based recommendations
        high_risk_predictions = [
            p for p in predictions if p.risk_assessment in ("high", "critical")
        ]
        if high_risk_predictions:
            metrics = [p.metric_name for p in high_risk_predictions]
            recommendations.append(
                f"🔮 High-risk quality forecast for {', '.join(metrics)} - proactive intervention recommended"
            )

        low_confidence_predictions = [
            p for p in predictions if p.confidence_upper - p.confidence_lower > 20
        ]
        if low_confidence_predictions:
            recommendations.append(
                "📈 Wide prediction intervals detected - increase data collection frequency for better forecasting"
            )

        # General ML insights
        if len(anomalies) > 5:
            recommendations.append(
                f"🤖 High anomaly frequency ({len(anomalies)}) suggests systemic quality issues - consider ML-based automated quality monitoring"
            )

        if not recommendations:
            recommendations.append(
                "✅ Quality metrics show stable patterns with no significant anomalies detected - maintain current practices"
            )

        return recommendations

    def generate_comprehensive_insights(
        self, analysis_days: int = 30, prediction_days: int = 14
    ) -> QualityInsights:
        """Generate comprehensive quality insights with ML analysis."""
        # Collect all analysis results
        anomalies = self.detect_anomalies(days=analysis_days)
        patterns = self.identify_patterns(days=analysis_days * 2)
        predictions = self.generate_advanced_predictions(horizon_days=prediction_days)
        recommendations = self.generate_ml_recommendations(
            anomalies, patterns, predictions
        )

        # Calculate derived metrics
        health_score, risk_level = self._calculate_health_metrics(
            anomalies, predictions
        )

        return QualityInsights(
            anomalies=anomalies,
            patterns=patterns,
            predictions=predictions,
            recommendations=recommendations,
            overall_health_score=health_score,
            risk_level=risk_level,
        )

    def _calculate_health_metrics(
        self, anomalies: list[QualityAnomaly], predictions: list[QualityPrediction]
    ) -> tuple[float, str]:
        """Calculate overall health score and risk level."""
        anomaly_counts = self._count_anomalies_by_severity(anomalies)
        risk_prediction_count = self._count_high_risk_predictions(predictions)

        health_score = self._compute_health_score(anomaly_counts, risk_prediction_count)
        risk_level = self._determine_risk_level(health_score)

        return health_score, risk_level

    def _count_anomalies_by_severity(
        self, anomalies: list[QualityAnomaly]
    ) -> dict[str, int]:
        """Count anomalies by severity level."""
        return {
            "critical": len(
                [a for a in anomalies if a.severity == AlertSeverity.CRITICAL]
            ),
            "warning": len(
                [a for a in anomalies if a.severity == AlertSeverity.WARNING]
            ),
        }

    def _count_high_risk_predictions(self, predictions: list[QualityPrediction]) -> int:
        """Count predictions with high or critical risk assessment."""
        return len(
            [p for p in predictions if p.risk_assessment in ("high", "critical")]
        )

    def _compute_health_score(
        self, anomaly_counts: dict[str, int], risk_predictions: int
    ) -> float:
        """Compute health score based on anomalies and risk predictions."""
        health_score = 1.0
        health_score -= (
            anomaly_counts["critical"] * 0.2
        )  # Critical anomalies heavily impact health
        health_score -= (
            anomaly_counts["warning"] * 0.1
        )  # Warning anomalies moderately impact health
        health_score -= risk_predictions * 0.15  # High-risk predictions impact health
        return max(0.0, min(1.0, health_score))

    def _determine_risk_level(self, health_score: float) -> str:
        """Determine overall risk level based on health score."""
        if health_score < 0.5:
            return "critical"
        elif health_score < 0.7:
            return "high"
        elif health_score < 0.85:
            return "medium"
        return "low"

    def export_insights(self, insights: QualityInsights, output_path: Path) -> None:
        """Export quality insights to JSON file."""
        with output_path.open("w") as f:
            json.dump(insights.to_dict(), f, indent=2, default=str)

    # Protocol methods required by QualityIntelligenceProtocol
    def analyze_quality_trends(self) -> dict[str, t.Any]:
        """Analyze quality trends."""
        # Use existing identify_patterns method to analyze trends
        patterns = self.identify_patterns()
        trend_analysis = {
            "total_patterns": len(patterns),
            "patterns_by_type": {
                "cyclic": len(
                    [p for p in patterns if p.pattern_type == PatternType.CYCLIC]
                ),
                "seasonal": len(
                    [p for p in patterns if p.pattern_type == PatternType.SEASONAL]
                ),
                "correlation": len(
                    [p for p in patterns if p.pattern_type == PatternType.CORRELATION]
                ),
                "regression": len(
                    [p for p in patterns if p.pattern_type == PatternType.REGRESSION]
                ),
                "improvement": len(
                    [p for p in patterns if p.pattern_type == PatternType.IMPROVEMENT]
                ),
            },
            "trend_directions": {
                "improving": len(
                    [
                        p
                        for p in patterns
                        if p.trend_direction == TrendDirection.IMPROVING
                    ]
                ),
                "declining": len(
                    [
                        p
                        for p in patterns
                        if p.trend_direction == TrendDirection.DECLINING
                    ]
                ),
                "stable": len(
                    [p for p in patterns if p.trend_direction == TrendDirection.STABLE]
                ),
                "volatile": len(
                    [
                        p
                        for p in patterns
                        if p.trend_direction == TrendDirection.VOLATILE
                    ]
                ),
            },
            "generated_at": datetime.now().isoformat(),
        }
        return trend_analysis

    def predict_quality_issues(self) -> list[dict[str, t.Any]]:
        """Predict potential quality issues."""
        predictions = self.generate_advanced_predictions()

        return [
            {
                "metric": pred.metric_name,
                "predicted_value": pred.predicted_value,
                "risk_level": pred.risk_assessment,
                "confidence_interval": {
                    "lower": pred.confidence_lower,
                    "upper": pred.confidence_upper,
                },
                "prediction_horizon": pred.prediction_horizon_days,
                "factors": pred.factors,
            }
            for pred in predictions
            if pred.risk_assessment in ("high", "critical")
        ]

    def recommend_improvements(self) -> list[dict[str, t.Any]]:
        """Recommend quality improvements."""
        # Generate basic analysis to get data for recommendations
        anomalies = self.detect_anomalies()
        patterns = self.identify_patterns()
        predictions = self.generate_advanced_predictions()

        recommendations = self.generate_ml_recommendations(
            anomalies, patterns, predictions
        )

        # Convert to required format
        return [{"message": rec} for rec in recommendations]

    def get_intelligence_report(self) -> dict[str, t.Any]:
        """Get quality intelligence report."""
        insights = self.generate_comprehensive_insights()
        return insights.to_dict()
