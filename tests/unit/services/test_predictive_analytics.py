"""Unit tests for PredictiveAnalytics.

Tests prediction algorithms, trend analysis, capacity planning,
and statistical forecasting functionality.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.services.predictive_analytics import (
    CapacityForecast,
    LinearTrendPredictor,
    MovingAveragePredictor,
 Prediction,
    SeasonalPredictor,
    TrendAnalysis,
    PredictiveAnalyticsEngine,
)


@pytest.mark.unit
class TestDataClasses:
    """Test predictive analytics data classes."""

    def test_trend_analysis_creation(self) -> None:
        """Test TrendAnalysis dataclass creation."""
        analysis = TrendAnalysis(
            metric_type="test_pass_rate",
            trend_direction="increasing",
            trend_strength=0.85,
            predicted_values=[0.9, 0.92, 0.94],
            confidence_intervals=[(0.88, 0.92), (0.90, 0.94), (0.92, 0.96)],
            analysis_period=timedelta(days=7),
            last_updated=datetime.now(),
        )

        assert analysis.metric_type == "test_pass_rate"
        assert analysis.trend_direction == "increasing"
        assert analysis.trend_strength == 0.85
        assert len(analysis.predicted_values) == 3

    def test_prediction_creation(self) -> None:
        """Test Prediction dataclass creation."""
        prediction = Prediction(
            metric_type="coverage_percentage",
            predicted_at=datetime.now(),
            predicted_for=datetime.now() + timedelta(hours=1),
            predicted_value=85.0,
            confidence_interval=(80.0, 90.0),
            confidence_level=0.95,
            model_accuracy=0.88,
        )

        assert prediction.metric_type == "coverage_percentage"
        assert prediction.predicted_value == 85.0
        assert prediction.confidence_level == 0.95

    def test_capacity_forecast_creation(self) -> None:
        """Test CapacityForecast dataclass creation."""
        forecast = CapacityForecast(
            resource_type="memory",
            current_usage=512.0,
            predicted_usage=[(datetime.now(), 600.0), (datetime.now() + timedelta(hours=1), 650.0)],
            capacity_threshold=1024.0,
            estimated_exhaustion=datetime.now() + timedelta(days=30),
            recommended_actions=["Monitor usage", "Plan scaling"],
            confidence=0.85,
        )

        assert forecast.resource_type == "memory"
        assert forecast.current_usage == 512.0
        assert len(forecast.predicted_usage) == 2


@pytest.mark.unit
class TestMovingAveragePredictor:
    """Test moving average prediction algorithm."""

    def test_initialization_default(self) -> None:
        """Test predictor initializes with default window size."""
        predictor = MovingAveragePredictor()

        assert predictor.window_size == 10

    def test_initialization_custom_window(self) -> None:
        """Test predictor initializes with custom window size."""
        predictor = MovingAveragePredictor(window_size=5)

        assert predictor.window_size == 5

    def test_predict_insufficient_data(self) -> None:
        """Test prediction with insufficient data points."""
        predictor = MovingAveragePredictor(window_size=10)

        result = predictor.predict([1.0, 2.0, 3.0], periods=2)

        assert result == [3.0, 3.0]

    def test_predict_empty_data(self) -> None:
        """Test prediction with empty data."""
        predictor = MovingAveragePredictor()

        result = predictor.predict([], periods=3)

        assert result == [0.0, 0.0, 0.0]

    def test_predict_sufficient_data(self) -> None:
        """Test prediction with sufficient data."""
        predictor = MovingAveragePredictor(window_size=3)

        result = predictor.predict([1.0, 2.0, 3.0, 4.0, 5.0], periods=2)

        # Average of last 3 values: (3 + 4 + 5) / 3 = 4.0
        assert result == [4.0, 4.0]

    def test_predict_single_period(self) -> None:
        """Test single period prediction."""
        predictor = MovingAveragePredictor(window_size=5)

        result = predictor.predict([10.0, 12.0, 14.0, 16.0, 18.0, 20.0], periods=1)

        # Average of last 5: (12 + 14 + 16 + 18 + 20) / 5 = 16.0
        assert result == [16.0]

    def test_predict_multiple_periods(self) -> None:
        """Test multiple period predictions."""
        predictor = MovingAveragePredictor(window_size=3)

        values = [1.0] * 10
        result = predictor.predict(values, periods=5)

        # All values are 1.0, so MA is 1.0
        assert result == [1.0, 1.0, 1.0, 1.0, 1.0]
        assert len(result) == 5


@pytest.mark.unit
class TestLinearTrendPredictor:
    """Test linear trend prediction algorithm."""

    def test_predict_insufficient_data(self) -> None:
        """Test prediction with insufficient data."""
        predictor = LinearTrendPredictor()

        result = predictor.predict([5.0], periods=2)

        assert result == [5.0, 5.0]

    def test_predict_empty_data(self) -> None:
        """Test prediction with empty data."""
        predictor = LinearTrendPredictor()

        result = predictor.predict([], periods=2)

        assert result == [0.0, 0.0]

    def test_predict_constant_values(self) -> None:
        """Test prediction with constant values (no trend)."""
        predictor = LinearTrendPredictor()

        result = predictor.predict([10.0, 10.0, 10.0, 10.0], periods=2)

        # Should predict mean (10.0) for all periods
        assert result == [10.0, 10.0]

    def test_predict_increasing_trend(self) -> None:
        """Test prediction with increasing trend."""
        predictor = LinearTrendPredictor()

        result = predictor.predict([1.0, 2.0, 3.0, 4.0, 5.0], periods=2)

        # Linear trend: y = x (slope = 1)
        # Next values should be 6.0 and 7.0
        assert len(result) == 2
        assert result[0] == 6.0
        assert result[1] == 7.0

    def test_predict_decreasing_trend(self) -> None:
        """Test prediction with decreasing trend."""
        predictor = LinearTrendPredictor()

        result = predictor.predict([10.0, 8.0, 6.0, 4.0, 2.0], periods=2)

        # Linear trend decreasing: slope = -2
        # Next values should be 0.0 and -2.0
        assert len(result) == 2
        assert result[0] == 0.0
        assert result[1] == pytest.approx(-2.0)

    def test_predict_single_period(self) -> None:
        """Test single period prediction."""
        predictor = LinearTrendPredictor()

        result = predictor.predict([2.0, 4.0, 6.0, 8.0], periods=1)

        # y = 2x, next value = 10.0
        assert result == [10.0]

    def test_predict_multiple_periods(self) -> None:
        """Test multiple period predictions."""
        predictor = LinearTrendPredictor()

        result = predictor.predict([1.0, 2.0, 3.0], periods=5)

        # y = x, so next values: 4, 5, 6, 7, 8
        assert result == [4.0, 5.0, 6.0, 7.0, 8.0]


@pytest.mark.unit
class TestSeasonalPredictor:
    """Test seasonal prediction algorithm."""

    def test_initialization_default(self) -> None:
        """Test predictor initializes with default season length."""
        predictor = SeasonalPredictor()

        assert predictor.season_length == 24

    def test_initialization_custom_season(self) -> None:
        """Test predictor initializes with custom season length."""
        predictor = SeasonalPredictor(season_length=12)

        assert predictor.season_length == 12

    def test_predict_insufficient_data(self) -> None:
        """Test prediction with insufficient data for season."""
        predictor = SeasonalPredictor(season_length=10)

        result = predictor.predict([1.0, 2.0, 3.0], periods=2)

        assert result == [3.0, 3.0]

    def test_predict_empty_data(self) -> None:
        """Test prediction with empty data."""
        predictor = SeasonalPredictor()

        result = predictor.predict([], periods=2)

        assert result == [0.0, 0.0]

    def test_predict_seasonal_pattern(self) -> None:
        """Test prediction detects seasonal pattern."""
        predictor = SeasonalPredictor(season_length=4)

        # Pattern: 1, 2, 3, 4, 1, 2, 3, 4
        values = [1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0]
        result = predictor.predict(values, periods=4)

        # Should repeat the pattern: 1, 2, 3, 4
        assert result == [1.0, 2.0, 3.0, 4.0]

    def test_predict_partial_season(self) -> None:
        """Test prediction with partial season data."""
        predictor = SeasonalPredictor(season_length=5)

        values = [10.0, 20.0, 30.0]
        result = predictor.predict(values, periods=2)

        # Should repeat last value when pattern incomplete
        assert result == [30.0, 30.0]


@pytest.mark.unit
class TestPredictiveAnalyticsEngineInitialization:
    """Test PredictiveAnalyticsEngine initialization and setup."""

    def test_initialization_default(self) -> None:
        """Test engine initializes with default settings."""
        engine = PredictiveAnalyticsEngine()

        assert engine.history_limit == 1000
        assert len(engine.predictors) == 3
        assert "moving_average" in engine.predictors
        assert "linear_trend" in engine.predictors
        assert "seasonal" in engine.predictors

    def test_initialization_custom_limit(self) -> None:
        """Test engine initializes with custom history limit."""
        engine = PredictiveAnalyticsEngine(history_limit=500)

        assert engine.history_limit == 500

    def test_metric_configs_populated(self) -> None:
        """Test metric configurations are properly set."""
        engine = PredictiveAnalyticsEngine()

        assert "test_pass_rate" in engine.metric_configs
        assert "coverage_percentage" in engine.metric_configs
        assert "execution_time" in engine.metric_configs

        # Check config structure
        test_config = engine.metric_configs["test_pass_rate"]
        assert "critical_threshold" in test_config
        assert "optimal_range" in test_config
        assert "predictor" in test_config


@pytest.mark.unit
class TestMetricManagement:
    """Test metric data management."""

    def test_add_metric_with_timestamp(self) -> None:
        """Test adding metric with explicit timestamp."""
        engine = PredictiveAnalyticsEngine()
        timestamp = datetime(2026, 1, 10, 12, 0, 0)

        engine.add_metric("test_metric", 85.0, timestamp=timestamp)

        assert "test_metric" in engine.metric_history
        assert len(engine.metric_history["test_metric"]) == 1

    def test_add_metric_auto_timestamp(self) -> None:
        """Test adding metric with automatic timestamp."""
        engine = PredictiveAnalyticsEngine()

        engine.add_metric("test_metric", 90.0)

        assert "test_metric" in engine.metric_history
        assert len(engine.metric_history["test_metric"]) == 1

    def test_add_multiple_metrics(self) -> None:
        """Test adding multiple metric values."""
        engine = PredictiveAnalyticsEngine()

        for i in range(15):
            engine.add_metric("test_metric", float(80 + i))

        assert len(engine.metric_history["test_metric"]) == 15

    def test_metric_history_limit(self) -> None:
        """Test metric history respects limit."""
        engine = PredictiveAnalyticsEngine(history_limit=5)

        for i in range(10):
            engine.add_metric("test_metric", float(i))

        # Should only keep last 5 due to limit
        assert len(engine.metric_history["test_metric"]) == 5


@pytest.mark.unit
class TestTrendAnalysis:
    """Test trend calculation and analysis."""

    def test_calculate_trend_insufficient_data(self) -> None:
        """Test trend calculation with insufficient data."""
        engine = PredictiveAnalyticsEngine()

        direction, strength = engine._calculate_trend([1.0, 2.0])

        assert direction == "stable"
        assert strength == 0.0

    def test_calculate_trend_increasing(self) -> None:
        """Test calculation detects increasing trend."""
        engine = PredictiveAnalyticsEngine()

        direction, strength = engine._calculate_trend([1.0, 2.0, 3.0, 4.0, 5.0])

        assert direction == "increasing"
        assert strength > 0.5  # Strong correlation

    def test_calculate_trend_decreasing(self) -> None:
        """Test calculation detects decreasing trend."""
        engine = PredictiveAnalyticsEngine()

        direction, strength = engine._calculate_trend([10.0, 8.0, 6.0, 4.0, 2.0])

        assert direction == "decreasing"
        assert strength > 0.5

    def test_calculate_trend_stable(self) -> None:
        """Test calculation detects stable trend."""
        engine = PredictiveAnalyticsEngine()

        direction, strength = engine._calculate_trend([5.0, 5.0, 5.0, 5.0, 5.0])

        assert direction == "stable"
        # strength may be 0 or low due to no variance

    def test_calculate_trend_volatile(self) -> None:
        """Test calculation detects volatile trend."""
        engine = PredictiveAnalyticsEngine()

        # Data with increasing variance
        values = [10.0, 11.0, 12.0, 15.0, 18.0, 25.0, 30.0, 40.0, 50.0, 65.0]
        direction, strength = engine._calculate_trend(values)

        # Should detect volatility if recent std > overall std * 1.5
        assert direction in ["increasing", "volatile"]

    def test_update_trend_analysis(self) -> None:
        """Test trend analysis updates after sufficient data."""
        engine = PredictiveAnalyticsEngine()

        # Add 10+ metrics to trigger trend analysis
        for i in range(15):
            engine.add_metric("test_metric", float(80 + i))

        assert "test_metric" in engine.trend_analyses
        analysis = engine.trend_analyses["test_metric"]

        assert analysis.metric_type == "test_metric"
        assert len(analysis.predicted_values) == 24  # 24 periods ahead
        assert len(analysis.confidence_intervals) == 24


@pytest.mark.unit
class TestConfidenceIntervals:
    """Test confidence interval calculation."""

    def test_confidence_intervals_insufficient_data(self) -> None:
        """Test confidence intervals with insufficient data."""
        engine = PredictiveAnalyticsEngine()

        intervals = engine._calculate_confidence_intervals([5.0], [6.0, 7.0])

        # Should return (pred, pred) for each prediction
        assert intervals == [(6.0, 6.0), (7.0, 7.0)]

    def test_confidence_intervals_sufficient_data(self) -> None:
        """Test confidence intervals with sufficient data."""
        engine = PredictiveAnalyticsEngine()

        historical = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
        predictions = [22.0, 24.0]

        intervals = engine._calculate_confidence_intervals(historical, predictions)

        assert len(intervals) == 2
        # Each interval should be (pred - 1.96*std, pred + 1.96*std)
        for lower, upper in intervals:
            assert lower < upper
            assert lower < 22.0  # Lower bound below prediction
            assert upper > 22.0  # Upper bound above prediction


@pytest.mark.unit
class TestPredictionGeneration:
    """Test prediction generation methods."""

    def test_predict_metric_no_history(self) -> None:
        """Test prediction with no historical data."""
        engine = PredictiveAnalyticsEngine()

        predictions = engine.predict_metric("unknown_metric", periods_ahead=3)

        assert predictions == []

    def test_predict_metric_with_history(self) -> None:
        """Test prediction with historical data."""
        engine = PredictiveAnalyticsEngine()

        # Add metric history
        for i in range(15):
            engine.add_metric("test_metric", float(80 + i))

        predictions = engine.predict_metric("test_metric", periods_ahead=2)

        assert len(predictions) == 2
        assert predictions[0].metric_type == "test_metric"
        assert isinstance(predictions[0].predicted_value, float)

    def test_predict_uses_configured_predictor(self) -> None:
        """Test prediction uses configured predictor."""
        engine = PredictiveAnalyticsEngine()

        # Add test_pass_rate (configured to use moving_average)
        for i in range(15):
            engine.add_metric("test_pass_rate", 0.8 + (i * 0.01))

        predictions = engine.predict_metric("test_pass_rate", periods_ahead=1)

        assert len(predictions) == 1
        assert "moving_average" in predictions[0].metadata.get("predictor", "")

    def test_predict_custom_predictor(self) -> None:
        """Test prediction with custom predictor."""
        engine = PredictiveAnalyticsEngine()

        for i in range(15):
            engine.add_metric("test_metric", float(i))

        predictions = engine.predict_metric("test_metric", predictor_name="linear_trend")

        assert len(predictions) > 0
        assert predictions[0].metadata.get("predictor") == "linear_trend"

    def test_predict_multiple_periods(self) -> None:
        """Test prediction for multiple periods ahead."""
        engine = PredictiveAnalyticsEngine()

        for i in range(20):
            engine.add_metric("test_metric", float(i))

        predictions = engine.predict_metric("test_metric", periods_ahead=5)

        assert len(predictions) == 5

        # Check timestamps are sequential
        for i in range(len(predictions) - 1):
            assert predictions[i + 1].predicted_for > predictions[i].predicted_for

    def test_predictions_cached(self) -> None:
        """Test predictions are cached."""
        engine = PredictiveAnalyticsEngine()

        for i in range(15):
            engine.add_metric("test_metric", float(i))

        predictions1 = engine.predict_metric("test_metric")
        predictions2 = engine.predict_metric("test_metric")

        assert "test_metric" in engine.predictions_cache
        assert len(predictions1) == len(predictions2)


@pytest.mark.unit
class TestModelAccuracy:
    """Test model accuracy calculation."""

    def test_accuracy_insufficient_data(self) -> None:
        """Test accuracy with insufficient historical data."""
        engine = PredictiveAnalyticsEngine()

        accuracy = engine._calculate_model_accuracy("test_metric", "moving_average")

        # Should return default accuracy
        assert accuracy == 0.5

    def test_accuracy_calculation(self) -> None:
        """Test accuracy calculation with sufficient data."""
        engine = PredictiveAnalyticsEngine()

        # Add 20+ data points
        for i in range(25):
            engine.add_metric("test_metric", float(100 + i))

        accuracy = engine._calculate_model_accuracy("test_metric", "moving_average")

        assert 0.0 <= accuracy <= 1.0

    def test_accuracy_perfect_prediction(self) -> None:
        """Test accuracy with perfect prediction."""
        engine = PredictiveAnalyticsEngine()

        # Constant values are perfectly predictable
        for _ in range(25):
            engine.add_metric("constant_metric", 50.0)

        accuracy = engine._calculate_model_accuracy("constant_metric", "moving_average")

        # Should be high accuracy
        assert accuracy > 0.8


@pytest.mark.unit
class TestCapacityPlanning:
    """Test capacity requirement analysis."""

    def test_analyze_capacity_no_history(self) -> None:
        """Test capacity analysis with no history."""
        engine = PredictiveAnalyticsEngine()

        forecast = engine.analyze_capacity_requirements("memory", 512.0)

        assert forecast.resource_type == "memory"
        assert forecast.current_usage == 512.0
        assert forecast.predicted_usage == []
        assert forecast.confidence == 0.0
        assert "Insufficient data" in forecast.recommended_actions[0]

    def test_analyze_capacity_with_predictions(self) -> None:
        """Test capacity analysis generates predictions."""
        engine = PredictiveAnalyticsEngine()

        # Add history
        for i in range(25):
            engine.add_metric("memory", 500.0 + (i * 10))

        forecast = engine.analyze_capacity_requirements("memory", 750.0)

        assert len(forecast.predicted_usage) > 0
        assert forecast.resource_type == "memory"
        assert forecast.current_usage == 750.0

    def test_estimates_exhaustion_time(self) -> None:
        """Test capacity exhaustion estimation."""
        engine = PredictiveAnalyticsEngine()

        # Add increasing memory usage
        for i in range(25):
            engine.add_metric("memory", 800.0 + (i * 5))

        forecast = engine.analyze_capacity_requirements("memory", 900.0, threshold=1000.0)

        # Should estimate when threshold will be exceeded
        if forecast.estimated_exhaustion:
            assert isinstance(forecast.estimated_exhaustion, datetime)

    def test_generate_recommendations_urgent(self) -> None:
        """Test urgent capacity recommendations."""
        engine = PredictiveAnalyticsEngine()

        # Create scenario with imminent exhaustion
        tomorrow = datetime.now() + timedelta(days=1)
        recommendations = engine._generate_capacity_recommendations(
            "memory",
            950.0,
            1000.0,
            tomorrow,
        )

        assert any("URGENT" in rec for rec in recommendations)
        assert any("immediate" in rec.lower() for rec in recommendations)

    def test_generate_recommendations_warning(self) -> None:
        """Test warning recommendations."""
        engine = PredictiveAnalyticsEngine()

        # High utilization but no immediate exhaustion
        recommendations = engine._generate_capacity_recommendations(
            "memory",
            750.0,
            1000.0,
            None,  # No exhaustion time
        )

        # Should mention high utilization
        assert any("utilization" in rec.lower() for rec in recommendations if recommendations)

    def test_generate_recommendations_normal(self) -> None:
        """Test normal capacity recommendations."""
        engine = PredictiveAnalyticsEngine()

        recommendations = engine._generate_capacity_recommendations(
            "memory",
            300.0,
            1000.0,
            None,
        )

        # Should indicate normal limits
        assert len(recommendations) > 0
        assert any("normal" in rec.lower() for rec in recommendations)


@pytest.mark.unit
class TestTrendSummary:
    """Test trend summary generation."""

    def test_get_trend_summary_empty(self) -> None:
        """Test trend summary with no analyses."""
        engine = PredictiveAnalyticsEngine()

        summary = engine.get_trend_summary()

        assert summary == {}

    def test_get_trend_summary_with_analyses(self) -> None:
        """Test trend summary with existing analyses."""
        engine = PredictiveAnalyticsEngine()

        # Add metrics to trigger analysis
        for i in range(15):
            engine.add_metric("test_metric", float(80 + i))

        summary = engine.get_trend_summary()

        assert "test_metric" in summary
        assert "trend_direction" in summary["test_metric"]
        assert "trend_strength" in summary["test_metric"]
        assert "next_predicted_value" in summary["test_metric"]
        assert "last_updated" in summary["test_metric"]


@pytest.mark.unit
class TestExportAnalytics:
    """Test analytics data export."""

    def test_export_to_json(self, tmp_path) -> None:
        """Test exporting analytics data to JSON."""
        engine = PredictiveAnalyticsEngine()

        # Add some data
        for i in range(15):
            engine.add_metric("test_metric", float(i))

        output_file = tmp_path / "analytics.json"
        engine.export_analytics_data(output_file)

        assert output_file.exists()

        # Verify JSON structure
        with open(output_file) as f:
            data = json.load(f)

        assert "trend_analyses" in data
        assert "predictions_summary" in data
        assert "exported_at" in data

    def test_export_includes_all_analyses(self, tmp_path) -> None:
        """Test export includes all trend analyses."""
        engine = PredictiveAnalyticsEngine()

        # Add multiple metrics
        for metric in ["metric1", "metric2", "metric3"]:
            for i in range(15):
                engine.add_metric(metric, float(i))

        output_file = tmp_path / "analytics.json"
        engine.export_analytics_data(output_file)

        with open(output_file) as f:
            data = json.load(f)

        # Should have all 3 metrics
        assert len(data["trend_analyses"]) == 3
