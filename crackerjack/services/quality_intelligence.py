"""Advanced ML-based quality intelligence with anomaly detection and predictive analytics."""

import json
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

import numpy as np
from scipy import stats

from crackerjack.services.quality_baseline_enhanced import (
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
    context: dict[str, t.Any] = field(default_factory=dict)

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
    context: dict[str, t.Any] = field(default_factory=dict)

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


class QualityIntelligenceService:
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
        """Detect anomalies in quality metrics using statistical analysis."""
        if metrics is None:
            metrics = [
                "quality_score",
                "coverage_percent",
                "hook_failures",
                "security_issues",
                "type_errors",
                "linting_issues",
            ]

        baselines = self.quality_service.get_recent_baselines(limit=days * 2)
        if len(baselines) < self.min_data_points:
            return []

        anomalies = []

        for metric_name in metrics:
            # Extract metric values
            values = []
            timestamps = []

            for baseline in baselines:
                if metric_name == "quality_score":
                    values.append(baseline.quality_score)
                elif metric_name == "coverage_percent":
                    values.append(baseline.coverage_percent)
                elif metric_name == "hook_failures":
                    values.append(baseline.hook_failures)
                elif metric_name == "security_issues":
                    values.append(baseline.security_issues)
                elif metric_name == "type_errors":
                    values.append(baseline.type_errors)
                elif metric_name == "linting_issues":
                    values.append(baseline.linting_issues)
                else:
                    continue

                timestamps.append(baseline.timestamp)

            if len(values) < self.min_data_points:
                continue

            # Statistical analysis
            values_array = np.array(values)
            mean_val = np.mean(values_array)
            std_val = np.std(values_array)

            if std_val == 0:
                continue  # No variation to detect anomalies

            # Z-score based anomaly detection
            z_scores = np.abs((values_array - mean_val) / std_val)

            # Detect outliers
            for i, (value, timestamp, z_score) in enumerate(
                zip(values, timestamps, z_scores)
            ):
                if z_score > self.anomaly_sensitivity:
                    # Determine anomaly type
                    if value > mean_val:
                        anomaly_type = AnomalyType.SPIKE
                        severity = (
                            AlertSeverity.CRITICAL
                            if z_score > 3.0
                            else AlertSeverity.WARNING
                        )
                    else:
                        anomaly_type = AnomalyType.DROP
                        severity = (
                            AlertSeverity.CRITICAL
                            if z_score > 3.0
                            else AlertSeverity.WARNING
                        )

                    # Calculate confidence based on z-score
                    confidence = min(1.0, z_score / 4.0)  # Scale to 0-1

                    anomaly = QualityAnomaly(
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
                            "data_points": len(values),
                            "position_in_series": i,
                        },
                    )
                    anomalies.append(anomaly)

        return anomalies

    def identify_patterns(self, days: int = 60) -> list[QualityPattern]:
        """Identify patterns in quality metrics using correlation and trend analysis."""
        baselines = self.quality_service.get_recent_baselines(limit=days * 2)
        if len(baselines) < self.min_data_points:
            return []

        patterns = []

        # Extract metric data for correlation analysis
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

        # Find correlations between metrics
        metric_names = list(metrics_data.keys())
        for i, metric1 in enumerate(metric_names):
            for metric2 in metric_names[i + 1 :]:
                values1 = np.array(metrics_data[metric1])
                values2 = np.array(metrics_data[metric2])

                if len(values1) < self.min_data_points:
                    continue

                # Calculate correlation
                correlation, p_value = stats.pearsonr(values1, values2)

                # Strong correlation threshold
                if abs(correlation) > 0.7 and p_value < 0.05:
                    # Determine trend direction
                    if correlation > 0:
                        trend_dir = TrendDirection.IMPROVING
                        description = f"Strong positive correlation between {metric1} and {metric2}"
                    else:
                        trend_dir = TrendDirection.DECLINING
                        description = f"Strong negative correlation between {metric1} and {metric2}"

                    pattern = QualityPattern(
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
                            "strength": (
                                "very strong"
                                if abs(correlation) > 0.9
                                else "strong"
                                if abs(correlation) > 0.7
                                else "moderate"
                            ),
                        },
                    )
                    patterns.append(pattern)

        return patterns

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
            # Extract time series data
            values = []
            timestamps = []

            for baseline in baselines:
                if metric_name == "quality_score":
                    values.append(baseline.quality_score)
                elif metric_name == "coverage_percent":
                    values.append(baseline.coverage_percent)
                timestamps.append(baseline.timestamp)

            if len(values) < self.min_data_points:
                continue

            # Convert to numpy arrays for analysis
            values_array = np.array(values)
            time_indices = np.arange(len(values))

            # Linear regression for trend
            slope, intercept, r_value, p_value, std_err = stats.linregress(
                time_indices, values_array
            )

            # Predict future value
            future_index = len(values) + horizon_days
            predicted_value = slope * future_index + intercept

            # Calculate confidence interval
            residuals = values_array - (slope * time_indices + intercept)
            residual_std = np.std(residuals)

            # t-distribution for confidence interval
            t_value = stats.t.ppf((1 + confidence_level) / 2, len(values) - 2)
            margin_error = (
                t_value
                * residual_std
                * np.sqrt(
                    1
                    + 1 / len(values)
                    + (future_index - np.mean(time_indices)) ** 2
                    / np.sum((time_indices - np.mean(time_indices)) ** 2)
                )
            )

            confidence_lower = predicted_value - margin_error
            confidence_upper = predicted_value + margin_error

            # Risk assessment
            if metric_name == "quality_score":
                if predicted_value < 70:
                    risk = "critical"
                elif predicted_value < 80:
                    risk = "high"
                elif predicted_value < 90:
                    risk = "medium"
                else:
                    risk = "low"
            else:  # coverage_percent
                if predicted_value < 70:
                    risk = "high"
                elif predicted_value < 85:
                    risk = "medium"
                else:
                    risk = "low"

            prediction = QualityPrediction(
                metric_name=metric_name,
                predicted_value=float(predicted_value),
                confidence_lower=float(confidence_lower),
                confidence_upper=float(confidence_upper),
                confidence_level=confidence_level,
                prediction_horizon_days=horizon_days,
                prediction_method="linear_regression_with_confidence_intervals",
                created_at=datetime.now(),
                factors=["historical_trend", "statistical_analysis"],
                risk_assessment=risk,
            )
            predictions.append(prediction)

        return predictions

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
            p for p in predictions if p.risk_assessment in ["high", "critical"]
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
        # Detect anomalies
        anomalies = self.detect_anomalies(days=analysis_days)

        # Identify patterns
        patterns = self.identify_patterns(days=analysis_days * 2)

        # Generate predictions
        predictions = self.generate_advanced_predictions(horizon_days=prediction_days)

        # Generate recommendations
        recommendations = self.generate_ml_recommendations(
            anomalies, patterns, predictions
        )

        # Calculate overall health score
        critical_anomalies = len(
            [a for a in anomalies if a.severity == AlertSeverity.CRITICAL]
        )
        warning_anomalies = len(
            [a for a in anomalies if a.severity == AlertSeverity.WARNING]
        )
        high_risk_predictions = len(
            [p for p in predictions if p.risk_assessment in ["high", "critical"]]
        )

        # Health score calculation (0.0 to 1.0)
        health_score = 1.0
        health_score -= (
            critical_anomalies * 0.2
        )  # Critical anomalies heavily impact health
        health_score -= (
            warning_anomalies * 0.1
        )  # Warning anomalies moderately impact health
        health_score -= (
            high_risk_predictions * 0.15
        )  # High-risk predictions impact health
        health_score = max(0.0, min(1.0, health_score))

        # Overall risk level
        if health_score < 0.5:
            risk_level = "critical"
        elif health_score < 0.7:
            risk_level = "high"
        elif health_score < 0.85:
            risk_level = "medium"
        else:
            risk_level = "low"

        return QualityInsights(
            anomalies=anomalies,
            patterns=patterns,
            predictions=predictions,
            recommendations=recommendations,
            overall_health_score=health_score,
            risk_level=risk_level,
        )

    def export_insights(self, insights: QualityInsights, output_path: Path) -> None:
        """Export quality insights to JSON file."""
        with open(output_path, "w") as f:
            json.dump(insights.to_dict(), f, indent=2, default=str)
