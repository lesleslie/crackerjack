"""ML-based anomaly detection service for quality metrics analysis."""

import logging
import statistics
import typing as t
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Individual metric data point."""

    timestamp: datetime
    value: float
    metric_type: str
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])


@dataclass
class AnomalyDetection:
    """Anomaly detection result."""

    timestamp: datetime
    metric_type: str
    value: float
    expected_range: tuple[float, float]
    severity: str  # low, medium, high, critical
    confidence: float
    description: str
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])


@dataclass
class BaselineModel:
    """Statistical baseline model for a metric."""

    metric_type: str
    mean: float
    std_dev: float
    min_value: float
    max_value: float
    sample_count: int
    last_updated: datetime
    seasonal_patterns: dict[str, float] = field(default_factory=dict[str, t.Any])


class AnomalyDetector:
    """ML-based anomaly detection system for quality metrics."""

    def __init__(
        self,
        baseline_window: int = 100,
        sensitivity: float = 2.0,
        min_samples: int = 10,
    ):
        """Initialize anomaly detector.

        Args:
            baseline_window: Number of recent samples for baseline calculation
            sensitivity: Standard deviation multiplier for anomaly threshold
            min_samples: Minimum samples required before anomaly detection
        """
        self.baseline_window = baseline_window
        self.sensitivity = sensitivity
        self.min_samples = min_samples

        # Data storage
        self.metric_history: dict[str, deque[MetricPoint]] = defaultdict(
            lambda: deque[MetricPoint](maxlen=baseline_window)
        )
        self.baselines: dict[str, BaselineModel] = {}
        self.anomalies: list[AnomalyDetection] = []

        # Configuration
        self.metric_configs = {
            "test_pass_rate": {"critical_threshold": 0.8, "direction": "both"},
            "coverage_percentage": {"critical_threshold": 0.7, "direction": "down"},
            "complexity_score": {"critical_threshold": 15.0, "direction": "up"},
            "execution_time": {"critical_threshold": 300.0, "direction": "up"},
            "memory_usage": {"critical_threshold": 1024.0, "direction": "up"},
            "error_count": {"critical_threshold": 5.0, "direction": "up"},
        }

    def add_metric(
        self,
        metric_type: str,
        value: float,
        timestamp: datetime | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Add new metric point and update baseline."""
        if timestamp is None:
            timestamp = datetime.now()

        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            metric_type=metric_type,
            metadata=metadata or {},
        )

        self.metric_history[metric_type].append(point)

        # Update baseline if we have enough samples
        if len(self.metric_history[metric_type]) >= self.min_samples:
            self._update_baseline(metric_type)

            # Check for anomalies
            anomaly = self._detect_anomaly(point)
            if anomaly:
                self.anomalies.append(anomaly)
                logger.info(f"Anomaly detected: {anomaly.description}")

    def _update_baseline(self, metric_type: str) -> None:
        """Update statistical baseline for a metric type."""
        history = list[t.Any](self.metric_history[metric_type])
        values = [point.value for point in history]

        # Calculate basic statistics
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0
        min_val = min(values)
        max_val = max(values)

        # Detect seasonal patterns (hourly, daily)
        seasonal_patterns = self._detect_seasonal_patterns(history)

        self.baselines[metric_type] = BaselineModel(
            metric_type=metric_type,
            mean=mean,
            std_dev=std_dev,
            min_value=min_val,
            max_value=max_val,
            sample_count=len(values),
            last_updated=datetime.now(),
            seasonal_patterns=seasonal_patterns,
        )

    def _detect_seasonal_patterns(self, history: list[MetricPoint]) -> dict[str, float]:
        """Detect seasonal patterns in metric history."""
        patterns: dict[str, float] = {}

        if len(history) < 24:  # Need at least 24 points for pattern detection
            return patterns

        # Group by hour of day
        hourly_values = defaultdict(list)
        for point in history:
            hour = point.timestamp.hour
            hourly_values[hour].append(point.value)

        # Calculate hourly averages
        for hour, values in hourly_values.items():
            if len(values) >= 3:  # Need at least 3 samples
                patterns[f"hour_{hour}"] = statistics.mean(values)

        return patterns

    def _detect_anomaly(self, point: MetricPoint) -> AnomalyDetection | None:
        """Detect if a metric point is anomalous."""
        metric_type = point.metric_type
        baseline = self.baselines.get(metric_type)

        if not baseline:
            return None

        # Calculate expected range
        lower_bound = baseline.mean - (self.sensitivity * baseline.std_dev)
        upper_bound = baseline.mean + (self.sensitivity * baseline.std_dev)

        # Apply seasonal adjustment if available
        seasonal_adjustment = self._get_seasonal_adjustment(point, baseline)
        if seasonal_adjustment:
            lower_bound += seasonal_adjustment
            upper_bound += seasonal_adjustment

        # Check for anomaly
        is_anomaly = point.value < lower_bound or point.value > upper_bound

        if not is_anomaly:
            return None

        # Determine severity
        severity = self._calculate_severity(point, baseline, lower_bound, upper_bound)

        # Calculate confidence
        confidence = self._calculate_confidence(point, baseline)

        # Generate description
        description = self._generate_anomaly_description(
            point, baseline, lower_bound, upper_bound, severity
        )

        return AnomalyDetection(
            timestamp=point.timestamp,
            metric_type=metric_type,
            value=point.value,
            expected_range=(lower_bound, upper_bound),
            severity=severity,
            confidence=confidence,
            description=description,
            metadata=point.metadata,
        )

    def _get_seasonal_adjustment(
        self, point: MetricPoint, baseline: BaselineModel
    ) -> float:
        """Get seasonal adjustment for the current time."""
        hour = point.timestamp.hour
        hour_pattern = baseline.seasonal_patterns.get(f"hour_{hour}")

        if hour_pattern is not None:
            return hour_pattern - baseline.mean

        return 0.0

    def _calculate_severity(
        self,
        point: MetricPoint,
        baseline: BaselineModel,
        lower_bound: float,
        upper_bound: float,
    ) -> str:
        """Calculate anomaly severity based on deviation magnitude."""
        if baseline.std_dev == 0:
            return "medium"

        # Check for critical threshold breaches first
        if self._is_critical_threshold_breached(point):
            return "critical"

        # Calculate z-score and map to severity
        z_score = self._calculate_z_score(point, baseline, lower_bound, upper_bound)
        return self._severity_from_z_score(z_score)

    def _is_critical_threshold_breached(self, point: MetricPoint) -> bool:
        """Check if point breaches critical thresholds."""
        config = self.metric_configs.get(point.metric_type, {})
        critical_threshold = config.get("critical_threshold")

        if not critical_threshold:
            return False

        direction = config.get("direction", "both")
        threshold_float: float = (
            float(str(critical_threshold)) if critical_threshold is not None else 0.0
        )
        return self._threshold_breached_in_direction(
            point.value, threshold_float, str(direction)
        )

    def _threshold_breached_in_direction(
        self, value: float, threshold: float, direction: str
    ) -> bool:
        """Check if value breaches threshold in specified direction."""
        if direction == "up":
            return value > threshold
        elif direction == "down":
            return value < threshold
        elif direction == "both":
            return value > threshold or value < -threshold
        return False

    def _calculate_z_score(
        self,
        point: MetricPoint,
        baseline: BaselineModel,
        lower_bound: float,
        upper_bound: float,
    ) -> float:
        """Calculate z-score for the point."""
        deviation = min(abs(point.value - lower_bound), abs(point.value - upper_bound))
        return deviation / baseline.std_dev

    def _severity_from_z_score(self, z_score: float) -> str:
        """Map z-score to severity level."""
        if z_score > 4:
            return "critical"
        elif z_score > 3:
            return "high"
        elif z_score > 2:
            return "medium"
        return "low"

    def _calculate_confidence(
        self, point: MetricPoint, baseline: BaselineModel
    ) -> float:
        """Calculate confidence in anomaly detection."""
        # Base confidence on sample size and consistency
        sample_factor = min(baseline.sample_count / 50, 1.0)  # Max at 50 samples

        # Factor in standard deviation consistency
        if baseline.std_dev == 0:
            std_factor = 0.5  # Low confidence for constant values
        else:
            # Higher confidence for more consistent baselines
            cv = baseline.std_dev / abs(baseline.mean) if baseline.mean != 0 else 1
            std_factor = max(0.1, min(1.0, 1.0 - cv))

        return sample_factor * std_factor

    def _generate_anomaly_description(
        self,
        point: MetricPoint,
        baseline: BaselineModel,
        lower_bound: float,
        upper_bound: float,
        severity: str,
    ) -> str:
        """Generate human-readable anomaly description."""
        direction = "above" if point.value > upper_bound else "below"
        expected_range = f"{lower_bound:.2f}-{upper_bound:.2f}"

        return (
            f"{severity.title()} anomaly in {point.metric_type}: "
            f"value {point.value:.2f} is {direction} expected range "
            f"{expected_range} (baseline: {baseline.mean:.2f})"
        )

    def get_anomalies(
        self,
        metric_type: str | None = None,
        severity: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AnomalyDetection]:
        """Get filtered anomalies."""
        anomalies = self.anomalies

        # Apply filters
        if metric_type:
            anomalies = [a for a in anomalies if a.metric_type == metric_type]

        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]

        if since:
            anomalies = [a for a in anomalies if a.timestamp >= since]

        # Sort by timestamp (newest first) and limit
        anomalies.sort(key=lambda x: x.timestamp, reverse=True)
        return anomalies[:limit]

    def get_baseline_summary(self) -> dict[str, dict[str, t.Any]]:
        """Get summary of all baseline models."""
        summary = {}

        for metric_type, baseline in self.baselines.items():
            summary[metric_type] = {
                "mean": baseline.mean,
                "std_dev": baseline.std_dev,
                "range": (baseline.min_value, baseline.max_value),
                "sample_count": baseline.sample_count,
                "last_updated": baseline.last_updated.isoformat(),
                "seasonal_patterns": len(baseline.seasonal_patterns),
            }

        return summary

    def export_model(self, output_path: str | Path) -> None:
        """Export anomaly detection model for persistence."""
        import json

        model_data = {
            "baselines": {
                metric_type: {
                    "metric_type": baseline.metric_type,
                    "mean": baseline.mean,
                    "std_dev": baseline.std_dev,
                    "min_value": baseline.min_value,
                    "max_value": baseline.max_value,
                    "sample_count": baseline.sample_count,
                    "last_updated": baseline.last_updated.isoformat(),
                    "seasonal_patterns": baseline.seasonal_patterns,
                }
                for metric_type, baseline in self.baselines.items()
            },
            "config": {
                "baseline_window": self.baseline_window,
                "sensitivity": self.sensitivity,
                "min_samples": self.min_samples,
            },
            "exported_at": datetime.now().isoformat(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(model_data, f, indent=2)
