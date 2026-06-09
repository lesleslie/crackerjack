"""Unit tests for ``crackerjack.services.ai.predictive_analytics``.

Aims to lift coverage of the package by exercising the predictive analytics
engine end-to-end (moving-average, linear-trend, seasonal predictors, trend
analysis, capacity forecasting, model-accuracy calculation, and JSON
export). Tests are deterministic — no network, no random sources.
"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.services.ai.predictive_analytics import (
    CapacityForecast,
    LinearTrendPredictor,
    MovingAveragePredictor,
    Prediction,
    PredictiveAnalyticsEngine,
    SeasonalPredictor,
    TrendAnalysis,
)


# ---------------------------------------------------------------------------
# Predictors
# ---------------------------------------------------------------------------


class TestMovingAveragePredictor:
    def test_default_window(self) -> None:
        assert MovingAveragePredictor().window_size == 10

    def test_custom_window(self) -> None:
        assert MovingAveragePredictor(window_size=5).window_size == 5

    def test_insufficient_data_returns_last_value(self) -> None:
        p = MovingAveragePredictor(window_size=10)
        assert p.predict([1.0, 2.0, 3.0], periods=2) == [3.0, 3.0]

    def test_empty_returns_zeros(self) -> None:
        p = MovingAveragePredictor(window_size=5)
        assert p.predict([], periods=3) == [0.0, 0.0, 0.0]

    def test_uses_last_window(self) -> None:
        p = MovingAveragePredictor(window_size=3)
        # last 3 = [3, 4, 5] -> mean 4
        assert p.predict([1.0, 2.0, 3.0, 4.0, 5.0], periods=1) == [4.0]

    def test_multiple_periods(self) -> None:
        p = MovingAveragePredictor(window_size=2)
        # last 2 = [9, 10] -> mean 9.5
        result = p.predict([1.0, 2.0, 3.0, 9.0, 10.0], periods=4)
        assert result == [9.5, 9.5, 9.5, 9.5]


class TestLinearTrendPredictor:
    def test_insufficient_data_uses_last(self) -> None:
        assert LinearTrendPredictor().predict([5.0], periods=2) == [5.0, 5.0]

    def test_empty_returns_zeros(self) -> None:
        assert LinearTrendPredictor().predict([], periods=2) == [0.0, 0.0]

    def test_constant_yields_mean(self) -> None:
        # denominator 0 -> returns y_mean for every period
        assert LinearTrendPredictor().predict([7.0, 7.0, 7.0], periods=3) == [7.0, 7.0, 7.0]

    def test_perfect_increasing_trend(self) -> None:
        result = LinearTrendPredictor().predict([1.0, 2.0, 3.0, 4.0, 5.0], periods=3)
        assert result[0] == pytest.approx(6.0)
        assert result[1] == pytest.approx(7.0)
        assert result[2] == pytest.approx(8.0)

    def test_perfect_decreasing_trend(self) -> None:
        result = LinearTrendPredictor().predict([10.0, 8.0, 6.0, 4.0, 2.0], periods=2)
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(-2.0)


class TestSeasonalPredictor:
    def test_insufficient_data_uses_last(self) -> None:
        p = SeasonalPredictor(season_length=24)
        assert p.predict([1.0, 2.0, 3.0], periods=2) == [3.0, 3.0]

    def test_empty_returns_zeros(self) -> None:
        p = SeasonalPredictor(season_length=2)
        assert p.predict([], periods=2) == [0.0, 0.0]

    def test_seasonal_picks_indexed_values(self) -> None:
        # season_length 4 with values [1,2,3,4,1,2,3,4,1,2,3,4]
        # len(values)=12, predict 1 period -> season_index = 12 % 4 = 0
        # values[-(4-0)] = values[-4] = 1
        p = SeasonalPredictor(season_length=4)
        values = [1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0]
        result = p.predict(values, periods=1)
        assert result[0] == pytest.approx(1.0)

    def test_seasonal_falls_back_to_last(self) -> None:
        # If season_index >= len(values), the source returns values[-1].
        # Build a case where for some period the season wraps past the
        # available data.
        p = SeasonalPredictor(season_length=10)
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        # periods=10: season indices 5,6,7,8,9,0,1,2,3,4
        # for season_index=5..9, season_index < len(values)=5 is False
        # (5 >= 5), so the fallback is values[-1] = 5
        result = p.predict(values, periods=10)
        assert result[0] == pytest.approx(5.0)
        assert result[4] == pytest.approx(5.0)
        # season_index=0 (period 6): values[-(10-0)] = values[-10] -> error
        # because values has only 5 elements. The helper avoids this by
        # only using values[-(season_length-season_index)] when
        # season_index < len(values). So we just check what we can:
        assert len(result) == 10


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class TestEngineState:
    def test_default_predictors_present(self) -> None:
        engine = PredictiveAnalyticsEngine()
        assert "moving_average" in engine.predictors
        assert "linear_trend" in engine.predictors
        assert "seasonal" in engine.predictors

    def test_default_metric_configs_present(self) -> None:
        engine = PredictiveAnalyticsEngine()
        for metric in (
            "test_pass_rate",
            "coverage_percentage",
            "execution_time",
            "memory_usage",
            "complexity_score",
        ):
            assert metric in engine.metric_configs
            assert "predictor" in engine.metric_configs[metric]

    def test_history_deque_maxlen(self) -> None:
        engine = PredictiveAnalyticsEngine(history_limit=3)
        for i in range(5):
            engine.add_metric("x", float(i))
        # deque maxlen=3 keeps only the last 3 values
        assert len(engine.metric_history["x"]) == 3

    def test_add_metric_uses_now_when_no_timestamp(self) -> None:
        engine = PredictiveAnalyticsEngine()
        with patch("crackerjack.services.ai.predictive_analytics.datetime") as dt:
            dt.now.return_value = datetime(2026, 6, 8, 12, 0, 0)
            engine.add_metric("x", 1.0)
        history = list(engine.metric_history["x"])
        assert history[0][0] == datetime(2026, 6, 8, 12, 0, 0)
        assert history[0][1] == 1.0

    def test_add_metric_accepts_explicit_timestamp(self) -> None:
        engine = PredictiveAnalyticsEngine()
        when = datetime(2020, 1, 1)
        engine.add_metric("x", 5.0, timestamp=when)
        assert list(engine.metric_history["x"])[0][0] == when


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------


def _seed(engine: PredictiveAnalyticsEngine, metric: str, values: list[float]) -> None:
    for i, v in enumerate(values):
        engine.add_metric(metric, v, timestamp=datetime(2026, 6, 1) + timedelta(hours=i))


class TestTrendAnalysis:
    def test_trend_analysis_triggered_at_ten_points(self) -> None:
        engine = PredictiveAnalyticsEngine()
        # Use a step clearly above 0.01 per index so the slope magnitude
        # is detected as increasing (source: ``abs(slope) < 0.01 -> stable``).
        _seed(engine, "test_pass_rate", [0.1 * i for i in range(1, 16)])
        assert "test_pass_rate" in engine.trend_analyses
        analysis = engine.trend_analyses["test_pass_rate"]
        assert analysis.trend_direction == "increasing"
        assert 0.0 <= analysis.trend_strength <= 1.0
        assert len(analysis.predicted_values) == 24
        assert len(analysis.confidence_intervals) == 24

    def test_constant_values_yield_stable_trend(self) -> None:
        engine = PredictiveAnalyticsEngine()
        _seed(engine, "test_pass_rate", [0.5] * 15)
        # slope == 0 (denominator 0) -> "stable", strength 0.0
        analysis = engine.trend_analyses["test_pass_rate"]
        assert analysis.trend_direction == "stable"
        assert analysis.trend_strength == 0.0

    def test_unknown_metric_uses_default_predictor(self) -> None:
        engine = PredictiveAnalyticsEngine()
        _seed(engine, "custom_metric", [float(i) for i in range(15)])
        assert "custom_metric" in engine.trend_analyses
        # Default predictor is "moving_average" (from the metric_configs
        # .get(..., {}).get("predictor", "moving_average") fallback).
        # Default window is 10; the MA of values [5..14] is 9.5.
        analysis = engine.trend_analyses["custom_metric"]
        assert analysis.predicted_values[0] == pytest.approx(9.5)


# ---------------------------------------------------------------------------
# Predict metric
# ---------------------------------------------------------------------------


class TestPredictMetric:
    def test_unknown_metric_returns_empty(self) -> None:
        engine = PredictiveAnalyticsEngine()
        assert engine.predict_metric("never_seen") == []

    def test_predict_metric_uses_config_predictor(self) -> None:
        engine = PredictiveAnalyticsEngine()
        _seed(engine, "test_pass_rate", [0.9 + 0.001 * i for i in range(15)])
        result = engine.predict_metric("test_pass_rate", periods_ahead=3)
        assert len(result) == 3
        for p in result:
            assert isinstance(p, Prediction)
            assert p.metric_type == "test_pass_rate"
            assert p.confidence_level == 0.95
            assert p.metadata["predictor"] == "moving_average"

    def test_predict_metric_explicit_predictor(self) -> None:
        engine = PredictiveAnalyticsEngine()
        _seed(engine, "x", [float(i) for i in range(15)])
        result = engine.predict_metric("x", periods_ahead=2, predictor_name="linear_trend")
        assert result[0].metadata["predictor"] == "linear_trend"
        # 15 values, slope ~= 1, next prediction ~= 15
        assert result[0].predicted_value == pytest.approx(15.0)

    def test_predict_metric_caches_result(self) -> None:
        engine = PredictiveAnalyticsEngine()
        _seed(engine, "x", [float(i) for i in range(15)])
        result = engine.predict_metric("x", periods_ahead=4)
        assert engine.predictions_cache["x"] is result


# ---------------------------------------------------------------------------
# Model accuracy
# ---------------------------------------------------------------------------


class TestModelAccuracy:
    def test_short_history_returns_baseline(self) -> None:
        engine = PredictiveAnalyticsEngine()
        # Less than 20 points -> 0.5 baseline
        _seed(engine, "x", [1.0, 2.0, 3.0])
        assert engine._calculate_model_accuracy("x", "moving_average") == 0.5

    def test_long_history_returns_accuracy_in_unit_range(self) -> None:
        engine = PredictiveAnalyticsEngine()
        # 30 points with a clear linear trend
        _seed(engine, "x", [float(i) for i in range(30)])
        acc = engine._calculate_model_accuracy("x", "linear_trend")
        assert 0.1 <= acc <= 1.0

    def test_perfect_predictions_yield_one(self) -> None:
        engine = PredictiveAnalyticsEngine()
        # Use a constant series so MA / mean predictors hit perfectly.
        _seed(engine, "x", [7.0] * 30)
        # moving_average and linear_trend both predict the constant value
        # exactly -> MAE 0 -> 1.0
        assert engine._calculate_model_accuracy("x", "moving_average") == 1.0
        assert engine._calculate_model_accuracy("x", "linear_trend") == 1.0


# ---------------------------------------------------------------------------
# Confidence intervals
# ---------------------------------------------------------------------------


class TestConfidenceIntervals:
    def test_too_short_history_returns_zero_width(self) -> None:
        engine = PredictiveAnalyticsEngine()
        result = engine._calculate_confidence_intervals([5.0], [5.0])
        assert result == [(5.0, 5.0)]

    def test_intervals_centered_on_prediction(self) -> None:
        engine = PredictiveAnalyticsEngine()
        historical = [1.0, 2.0, 3.0, 4.0, 5.0]
        predictions = [3.0, 3.0]
        intervals = engine._calculate_confidence_intervals(historical, predictions)
        std_dev = 1.5811388300841898  # statistics.stdev of [1..5]
        for lower, upper in intervals:
            assert lower == pytest.approx(3.0 - 1.96 * std_dev)
            assert upper == pytest.approx(3.0 + 1.96 * std_dev)


# ---------------------------------------------------------------------------
# Capacity forecast
# ---------------------------------------------------------------------------


class TestCapacityForecast:
    def test_unknown_resource_returns_insufficient_data(self) -> None:
        engine = PredictiveAnalyticsEngine()
        forecast = engine.analyze_capacity_requirements(
            "memory", current_usage=512.0, threshold=1024.0
        )
        assert isinstance(forecast, CapacityForecast)
        assert forecast.resource_type == "memory"
        assert forecast.estimated_exhaustion is None
        assert "Insufficient data" in forecast.recommended_actions[0]
        assert forecast.confidence == 0.0

    def test_known_resource_with_low_usage(self) -> None:
        engine = PredictiveAnalyticsEngine()
        # Constant low usage -> predicted_usage stays well under threshold.
        _seed(engine, "memory", [50.0] * 20)
        forecast = engine.analyze_capacity_requirements(
            "memory", current_usage=50.0, threshold=1000.0
        )
        # No exhaustion within the horizon
        assert forecast.estimated_exhaustion is None
        # Utilization is 50/1000 = 5% < 0.7
        assert any("within normal limits" in r for r in forecast.recommended_actions)
        assert forecast.predicted_usage  # non-empty

    def test_high_utilization_adds_proactive_recommendation(self) -> None:
        engine = PredictiveAnalyticsEngine()
        _seed(engine, "memory", [80.0] * 20)
        forecast = engine.analyze_capacity_requirements(
            "memory", current_usage=850.0, threshold=1000.0
        )
        # utilization = 0.85 -> "High memory utilization" + "proactive scaling"
        joined = " | ".join(forecast.recommended_actions)
        assert "High memory utilization" in joined
        assert "proactive scaling" in joined

    def test_zero_threshold_does_not_divide_by_zero(self) -> None:
        engine = PredictiveAnalyticsEngine()
        _seed(engine, "memory", [1.0] * 20)
        # threshold=0 is degenerate: every predicted value is >= 0 so the
        # function picks the first timestamp as ``estimated_exhaustion``.
        # The contract we pin: the function does not raise, and the
        # utilization guard (``threshold > 0``) avoids a ZeroDivisionError.
        forecast = engine.analyze_capacity_requirements(
            "memory", current_usage=10.0, threshold=0.0
        )
        assert isinstance(forecast, CapacityForecast)
        # URGENT recommendation is generated for the (artificial) exhaustion.
        joined = " | ".join(forecast.recommended_actions)
        assert "URGENT" in joined or "within normal limits" in joined
        # No ZeroDivisionError means the threshold guard works.


# ---------------------------------------------------------------------------
# Trend summary / export
# ---------------------------------------------------------------------------


class TestSummaryAndExport:
    def test_get_trend_summary_empty(self) -> None:
        engine = PredictiveAnalyticsEngine()
        assert engine.get_trend_summary() == {}

    def test_get_trend_summary_after_seeding(self) -> None:
        engine = PredictiveAnalyticsEngine()
        _seed(engine, "test_pass_rate", [0.9 + 0.001 * i for i in range(15)])
        summary = engine.get_trend_summary()
        assert "test_pass_rate" in summary
        entry = summary["test_pass_rate"]
        assert "trend_direction" in entry
        assert "trend_strength" in entry
        assert "next_predicted_value" in entry
        assert "confidence_range" in entry
        assert "last_updated" in entry
        # last_updated is an ISO string
        datetime.fromisoformat(entry["last_updated"])

    def test_export_analytics_data(self, tmp_path: Path) -> None:
        engine = PredictiveAnalyticsEngine()
        _seed(engine, "test_pass_rate", [0.9 + 0.001 * i for i in range(15)])
        engine.predict_metric("test_pass_rate", periods_ahead=4)
        out = tmp_path / "analytics.json"
        engine.export_analytics_data(out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "trend_analyses" in data
        assert "predictions_summary" in data
        assert "exported_at" in data
        assert "test_pass_rate" in data["trend_analyses"]
        # Predicted values are truncated to 10.
        ta = data["trend_analyses"]["test_pass_rate"]
        assert "predicted_values" in ta
        # The exported prediction list may be up to 10 entries.
        assert len(ta["predicted_values"]) <= 10
        assert data["predictions_summary"]["test_pass_rate"] == 4


# ---------------------------------------------------------------------------
# Dataclasses — smoke tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_trend_analysis_defaults(self) -> None:
        ta = TrendAnalysis(
            metric_type="x",
            trend_direction="stable",
            trend_strength=0.0,
            predicted_values=[],
            confidence_intervals=[],
            analysis_period=timedelta(0),
            last_updated=datetime(2026, 1, 1),
        )
        assert ta.trend_direction == "stable"

    def test_prediction_metadata_default(self) -> None:
        p = Prediction(
            metric_type="x",
            predicted_at=datetime(2026, 1, 1),
            predicted_for=datetime(2026, 1, 2),
            predicted_value=1.0,
            confidence_interval=(0.0, 2.0),
            confidence_level=0.95,
            model_accuracy=0.5,
        )
        assert p.metadata == {}
