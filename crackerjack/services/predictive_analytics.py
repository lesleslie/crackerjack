"""Advanced predictive analytics engine for quality metrics and trends."""

import logging
import statistics
import typing as t
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

if t.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


if t.TYPE_CHECKING:

    class PredictorProtocol(t.Protocol):
        def predict(self, values: list[float], periods: int = 1) -> list[float]: ...


@dataclass
class TrendAnalysis:
    """Trend analysis result for a metric."""

    metric_type: str
    trend_direction: str  # increasing, decreasing, stable, volatile
    trend_strength: float  # 0.0 to 1.0
    predicted_values: list[float]
    confidence_intervals: list[tuple[float, float]]
    analysis_period: timedelta
    last_updated: datetime


@dataclass
class Prediction:
    """Prediction for a specific metric at a future time."""

    metric_type: str
    predicted_at: datetime
    predicted_for: datetime
    predicted_value: float
    confidence_interval: tuple[float, float]
    confidence_level: float
    model_accuracy: float
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])


@dataclass
class CapacityForecast:
    """Capacity planning forecast."""

    resource_type: str
    current_usage: float
    predicted_usage: list[tuple[datetime, float]]
    capacity_threshold: float
    estimated_exhaustion: datetime | None
    recommended_actions: list[str]
    confidence: float


class MovingAveragePredictor:
    """Simple moving average predictor."""

    def __init__(self, window_size: int = 10):
        self.window_size = window_size

    def predict(self, values: list[float], periods: int = 1) -> list[float]:
        """Predict future values using moving average."""
        if len(values) < self.window_size:
            return [values[-1]] * periods if values else [0.0] * periods

        recent_values = values[-self.window_size :]
        ma = statistics.mean(recent_values)

        return [ma] * periods


class LinearTrendPredictor:
    """Linear trend-based predictor."""

    def predict(self, values: list[float], periods: int = 1) -> list[float]:
        """Predict future values using linear regression."""
        if len(values) < 2:
            return [values[-1]] * periods if values else [0.0] * periods

        # Simple linear regression
        n = len(values)
        x = list[t.Any](range(n))
        y = values

        # Calculate slope and intercept
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return [y_mean] * periods

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        # Predict future values
        predictions = []
        for i in range(1, periods + 1):
            future_x = n + i - 1
            prediction = slope * future_x + intercept
            predictions.append(prediction)

        return predictions


class SeasonalPredictor:
    """Seasonal pattern-based predictor."""

    def __init__(self, season_length: int = 24):
        self.season_length = season_length

    def predict(self, values: list[float], periods: int = 1) -> list[float]:
        """Predict using seasonal patterns."""
        if len(values) < self.season_length:
            return [values[-1]] * periods if values else [0.0] * periods

        predictions = []
        for i in range(periods):
            # Use seasonal pattern
            season_index = (len(values) + i) % self.season_length
            if season_index < len(values):
                seasonal_value = values[-(self.season_length - season_index)]
                predictions.append(seasonal_value)
            else:
                predictions.append(values[-1])

        return predictions


class PredictiveAnalyticsEngine:
    """Advanced predictive analytics system for quality metrics."""

    def __init__(self, history_limit: int = 1000):
        """Initialize predictive analytics engine."""
        self.history_limit = history_limit

        # Data storage
        self.metric_history: dict[str, deque[tuple[datetime, float]]] = defaultdict(
            lambda: deque[tuple[datetime, float]](maxlen=history_limit)
        )

        # Predictors
        self.predictors: dict[str, t.Any] = {  # type: ignore[var-annotated]
            "moving_average": MovingAveragePredictor(window_size=10),
            "linear_trend": LinearTrendPredictor(),
            "seasonal": SeasonalPredictor(season_length=24),
        }

        # Cached analyses
        self.trend_analyses: dict[str, TrendAnalysis] = {}
        self.predictions_cache: dict[str, list[Prediction]] = defaultdict(list)

        # Configuration
        self.metric_configs = {
            "test_pass_rate": {
                "critical_threshold": 0.8,
                "optimal_range": (0.95, 1.0),
                "predictor": "moving_average",
            },
            "coverage_percentage": {
                "critical_threshold": 0.7,
                "optimal_range": (0.9, 1.0),
                "predictor": "linear_trend",
            },
            "execution_time": {
                "critical_threshold": 300.0,
                "predictor": "seasonal",
            },
            "memory_usage": {
                "critical_threshold": 1024.0,
                "predictor": "linear_trend",
            },
            "complexity_score": {
                "critical_threshold": 15.0,
                "predictor": "moving_average",
            },
        }

    def add_metric(
        self,
        metric_type: str,
        value: float,
        timestamp: datetime | None = None,
    ) -> None:
        """Add new metric data point."""
        if timestamp is None:
            timestamp = datetime.now()

        self.metric_history[metric_type].append((timestamp, value))

        # Update trend analysis if we have enough data
        if len(self.metric_history[metric_type]) >= 10:
            self._update_trend_analysis(metric_type)

    def _update_trend_analysis(self, metric_type: str) -> None:
        """Update trend analysis for a metric."""
        history: list[tuple[datetime, float]] = list(self.metric_history[metric_type])
        values = [point[1] for point in history]
        timestamps = [point[0] for point in history]

        # Calculate trend direction and strength
        trend_direction, trend_strength = self._calculate_trend(values)

        # Generate predictions
        config = self.metric_configs.get(metric_type, {})
        predictor_name = config.get("predictor", "moving_average")
        predictor = self.predictors[t.cast(str, predictor_name)]  # type: ignore[index]

        predicted_values = t.cast(t.Any, predictor).predict(
            values, periods=24
        )  # 24 periods ahead  # type: ignore[union-attr]
        confidence_intervals = self._calculate_confidence_intervals(
            values, predicted_values
        )

        self.trend_analyses[metric_type] = TrendAnalysis(
            metric_type=metric_type,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            predicted_values=predicted_values,
            confidence_intervals=confidence_intervals,
            analysis_period=timestamps[-1] - timestamps[0],
            last_updated=datetime.now(),
        )

    def _calculate_trend(self, values: list[float]) -> tuple[str, float]:
        """Calculate trend direction and strength."""
        if len(values) < 3:
            return "stable", 0.0

        # Use linear regression to determine trend
        n = len(values)
        x: list[int] = list(range(n))
        y = values

        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return "stable", 0.0

        slope = numerator / denominator

        # Calculate R-squared for trend strength
        y_pred = [slope * xi + (y_mean - slope * x_mean) for xi in x]
        ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))

        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        trend_strength = max(0.0, min(1.0, r_squared))

        # Determine direction
        if abs(slope) < 0.01:
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"

        # Check for volatility
        if trend_strength < 0.3:
            recent_std = statistics.stdev(values[-10:]) if len(values) >= 10 else 0
            overall_std = statistics.stdev(values)
            if recent_std > overall_std * 1.5:
                direction = "volatile"

        return direction, trend_strength

    def _calculate_confidence_intervals(
        self, historical: list[float], predictions: list[float]
    ) -> list[tuple[float, float]]:
        """Calculate confidence intervals for predictions."""
        if len(historical) < 2:
            return [(pred, pred) for pred in predictions]

        # Use historical standard deviation for confidence intervals
        std_dev = statistics.stdev(historical)
        confidence_multiplier = 1.96  # 95% confidence

        intervals = []
        for pred in predictions:
            lower = pred - confidence_multiplier * std_dev
            upper = pred + confidence_multiplier * std_dev
            intervals.append((lower, upper))

        return intervals

    def predict_metric(
        self,
        metric_type: str,
        periods_ahead: int = 1,
        predictor_name: str | None = None,
    ) -> list[Prediction]:
        """Generate predictions for a metric."""
        if metric_type not in self.metric_history:
            return []

        history: list[tuple[datetime, float]] = list(self.metric_history[metric_type])
        values = [point[1] for point in history]
        last_timestamp = history[-1][0] if history else datetime.now()

        # Select predictor
        if predictor_name is None:
            config = self.metric_configs.get(metric_type, {})
            predictor_name = t.cast(str, config.get("predictor", "moving_average"))  # type: ignore[redundant-cast]

        predictor = self.predictors[t.cast(str, predictor_name)]  # type: ignore[index]
        predicted_values = t.cast(t.Any, predictor).predict(values, periods_ahead)  # type: ignore[union-attr]

        # Calculate confidence intervals
        confidence_intervals = self._calculate_confidence_intervals(
            values, predicted_values
        )

        # Calculate model accuracy
        accuracy = self._calculate_model_accuracy(metric_type, predictor_name)

        # Generate predictions
        predictions = []
        for i, (pred_value, conf_interval) in enumerate(
            zip(predicted_values, confidence_intervals)
        ):
            prediction_time = last_timestamp + timedelta(hours=i + 1)

            prediction = Prediction(
                metric_type=metric_type,
                predicted_at=datetime.now(),
                predicted_for=prediction_time,
                predicted_value=pred_value,
                confidence_interval=conf_interval,
                confidence_level=0.95,
                model_accuracy=accuracy,
                metadata={"predictor": predictor_name},
            )
            predictions.append(prediction)

        # Cache predictions
        self.predictions_cache[metric_type] = predictions

        return predictions

    def _calculate_model_accuracy(self, metric_type: str, predictor_name: str) -> float:
        """Calculate historical accuracy of the prediction model."""
        if len(self.metric_history[metric_type]) < 20:
            return 0.5  # Default accuracy for insufficient data

        history: list[tuple[datetime, float]] = list(self.metric_history[metric_type])
        values = [point[1] for point in history]

        # Use last 10 points for validation
        train_data = values[:-10]
        validation_data = values[-10:]

        if len(train_data) < 5:
            return 0.5

        # Generate predictions for validation period
        predictor = self.predictors[t.cast(str, predictor_name)]  # type: ignore[index]
        predictions = t.cast(t.Any, predictor).predict(
            train_data, periods=len(validation_data)
        )  # type: ignore[union-attr]

        # Calculate accuracy (inverse of mean absolute error)
        mae = statistics.mean(
            abs(pred - actual) for pred, actual in zip(predictions, validation_data)
        )

        # Convert to accuracy score (0-1)
        if mae == 0:
            return 1.0

        avg_value = statistics.mean(validation_data)
        relative_error = mae / abs(avg_value) if avg_value != 0 else mae

        return max(0.1, min(1.0, 1.0 - relative_error))

    def analyze_capacity_requirements(
        self, resource_type: str, current_usage: float, threshold: float = 0.8
    ) -> CapacityForecast:
        """Analyze capacity requirements and forecast exhaustion."""
        if resource_type not in self.metric_history:
            return CapacityForecast(
                resource_type=resource_type,
                current_usage=current_usage,
                predicted_usage=[],
                capacity_threshold=threshold,
                estimated_exhaustion=None,
                recommended_actions=["Insufficient data for analysis"],
                confidence=0.0,
            )

        # Get predictions for the next 30 days
        predictions = self.predict_metric(resource_type, periods_ahead=24 * 30)

        predicted_usage = [
            (pred.predicted_for, pred.predicted_value) for pred in predictions
        ]

        # Find when threshold will be exceeded
        estimated_exhaustion = None
        for timestamp, usage in predicted_usage:
            if usage >= threshold:
                estimated_exhaustion = timestamp
                break

        # Generate recommendations
        recommendations = self._generate_capacity_recommendations(
            resource_type, current_usage, threshold, estimated_exhaustion
        )

        # Calculate confidence based on prediction accuracy
        avg_accuracy = statistics.mean(pred.model_accuracy for pred in predictions)

        return CapacityForecast(
            resource_type=resource_type,
            current_usage=current_usage,
            predicted_usage=predicted_usage,
            capacity_threshold=threshold,
            estimated_exhaustion=estimated_exhaustion,
            recommended_actions=recommendations,
            confidence=avg_accuracy,
        )

    def _generate_capacity_recommendations(
        self,
        resource_type: str,
        current_usage: float,
        threshold: float,
        estimated_exhaustion: datetime | None,
    ) -> list[str]:
        """Generate capacity planning recommendations."""
        recommendations: list[str] = []

        utilization = current_usage / threshold if threshold > 0 else 0

        if estimated_exhaustion:
            days_until = (estimated_exhaustion - datetime.now()).days
            if days_until < 7:
                recommendations.extend(
                    (
                        f"URGENT: {resource_type} capacity will be exceeded in {days_until} days",
                        "Consider immediate scaling or optimization",
                    )
                )
            elif days_until < 30:
                recommendations.append(
                    f"Plan capacity increase for {resource_type} within {days_until} days"
                )
            else:
                recommendations.append(
                    f"Monitor {resource_type} usage, capacity limit expected in {days_until} days"
                )

        if utilization > 0.7:
            recommendations.extend(
                (
                    f"High {resource_type} utilization ({utilization:.1%})",
                    "Consider proactive scaling",
                )
            )

        if not recommendations:
            recommendations.append(f"{resource_type} capacity is within normal limits")

        return recommendations

    def get_trend_summary(self) -> dict[str, dict[str, t.Any]]:
        """Get summary of all trend analyses."""
        summary = {}

        for metric_type, analysis in self.trend_analyses.items():
            summary[metric_type] = {
                "trend_direction": analysis.trend_direction,
                "trend_strength": analysis.trend_strength,
                "next_predicted_value": analysis.predicted_values[0]
                if analysis.predicted_values
                else None,
                "confidence_range": analysis.confidence_intervals[0]
                if analysis.confidence_intervals
                else None,
                "last_updated": analysis.last_updated.isoformat(),
            }

        return summary

    def export_analytics_data(self, output_path: str | Path) -> None:
        """Export analytics data for external analysis."""
        import json

        data = {
            "trend_analyses": {
                metric_type: {
                    "metric_type": analysis.metric_type,
                    "trend_direction": analysis.trend_direction,
                    "trend_strength": analysis.trend_strength,
                    "predicted_values": analysis.predicted_values[:10],  # Limit size
                    "analysis_period": analysis.analysis_period.total_seconds(),
                    "last_updated": analysis.last_updated.isoformat(),
                }
                for metric_type, analysis in self.trend_analyses.items()
            },
            "predictions_summary": {
                metric_type: len(predictions)
                for metric_type, predictions in self.predictions_cache.items()
            },
            "exported_at": datetime.now().isoformat(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
