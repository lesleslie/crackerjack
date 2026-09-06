"""Tests for ``crackerjack.services.anomaly_detector``.

The ``AnomalyDetector`` collects metric points in a rolling deque,
updates a ``BaselineModel`` per metric type, and emits
``AnomalyDetection`` records when a new point falls outside the
expected range. Tests exercise the dispatch logic with synthetic data
(small histories with a clearly-out-of-range point) so we don't depend
on statistical noise.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from crackerjack.services.anomaly_detector import (
    AnomalyDetection,
    AnomalyDetector,
    BaselineModel,
    MetricPoint,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


def test_metric_point_defaults() -> None:
    p = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=1.0,
        metric_type="x",
    )
    assert p.metadata == {}


def test_anomaly_detection_defaults() -> None:
    a = AnomalyDetection(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        metric_type="x",
        value=1.0,
        expected_range=(0.0, 1.0),
        severity="low",
        confidence=0.5,
        description="d",
    )
    assert a.metadata == {}


def test_baseline_model_defaults() -> None:
    b = BaselineModel(
        metric_type="x",
        mean=1.0,
        std_dev=0.0,
        min_value=1.0,
        max_value=1.0,
        sample_count=1,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert b.seasonal_patterns == {}


# ---------------------------------------------------------------------------
# AnomalyDetector.__init__
# ---------------------------------------------------------------------------


def test_detector_init_defaults() -> None:
    d = AnomalyDetector()
    assert d.baseline_window == 100
    assert d.sensitivity == 2.0
    assert d.min_samples == 10
    assert "test_pass_rate" in d.metric_configs
    assert "error_count" in d.metric_configs


def test_detector_init_custom() -> None:
    d = AnomalyDetector(baseline_window=50, sensitivity=3.0, min_samples=5)
    assert d.baseline_window == 50
    assert d.sensitivity == 3.0
    assert d.min_samples == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


def test_add_metric_uses_default_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When timestamp is None, ``add_metric`` calls ``datetime.now()``."""
    fixed = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    class _FakeDateTime:
        @classmethod
        def now(cls) -> datetime:
            return fixed

    monkeypatch.setattr(
        "crackerjack.services.anomaly_detector.datetime", _FakeDateTime
    )

    d = AnomalyDetector()
    d.add_metric(metric_type="x", value=1.0)
    history = list(d.metric_history["x"])
    assert len(history) == 1
    assert history[0].timestamp == fixed


def test_add_metric_records_history() -> None:
    d = AnomalyDetector()
    d.add_metric(
        metric_type="test_pass_rate",
        value=0.95,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    history = list(d.metric_history["test_pass_rate"])
    assert len(history) == 1
    assert history[0].value == 0.95


def test_add_metric_metadata_default() -> None:
    d = AnomalyDetector()
    d.add_metric(metric_type="x", value=1.0)
    assert d.metric_history["x"][0].metadata == {}


def test_add_metric_metadata_explicit() -> None:
    d = AnomalyDetector()
    d.add_metric(metric_type="x", value=1.0, metadata={"k": "v"})
    assert d.metric_history["x"][0].metadata == {"k": "v"}


def test_add_metric_emits_anomaly_for_outlier() -> None:
    """A value far outside the baseline range is flagged."""
    d = AnomalyDetector(min_samples=5, sensitivity=2.0)
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    # Feed 10 nearly-identical points (so std_dev is tiny).
    for i in range(10):
        d.add_metric(
            metric_type="custom_metric",
            value=100.0 + (i % 2) * 0.001,  # 100.0 or 100.001
            timestamp=base_time + timedelta(minutes=i),
        )
    # Add a clear outlier.
    d.add_metric(
        metric_type="custom_metric",
        value=999.0,
        timestamp=base_time + timedelta(minutes=10),
    )
    assert len(d.anomalies) >= 1
    assert d.anomalies[-1].value == 999.0


def test_add_metric_below_min_samples_skips_anomaly() -> None:
    """No anomaly detection runs when fewer than ``min_samples`` points exist."""
    d = AnomalyDetector(min_samples=10)
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        d.add_metric(
            metric_type="custom_metric",
            value=1.0,
            timestamp=base_time + timedelta(minutes=i),
        )
    assert d.anomalies == []


# ---------------------------------------------------------------------------
# _detect_anomaly
# ---------------------------------------------------------------------------


def test_detect_anomaly_no_baseline_returns_none() -> None:
    d = AnomalyDetector()
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=1.0,
        metric_type="x",
    )
    assert d._detect_anomaly(point) is None


def test_detect_anomaly_within_bounds_returns_none() -> None:
    """A point within the baseline range is NOT an anomaly."""
    d = AnomalyDetector(min_samples=3, sensitivity=2.0)
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        d.add_metric(
            metric_type="custom_metric",
            value=10.0 + i,
            timestamp=base_time + timedelta(minutes=i),
        )
    # Now add an in-range point (the 5th point was already added; add
    # a 6th within range).
    in_range_point = MetricPoint(
        timestamp=base_time + timedelta(minutes=10),
        value=12.0,
        metric_type="custom_metric",
    )
    assert d._detect_anomaly(in_range_point) is None


# ---------------------------------------------------------------------------
# _detect_seasonal_patterns
# ---------------------------------------------------------------------------


def test_detect_seasonal_patterns_short_history_returns_empty() -> None:
    d = AnomalyDetector()
    history = [
        MetricPoint(
            timestamp=datetime(2026, 1, 1, i, tzinfo=UTC),
            value=float(i),
            metric_type="x",
        )
        for i in range(10)
    ]
    assert d._detect_seasonal_patterns(history) == {}


def test_detect_seasonal_patterns_finds_hourly() -> None:
    """With 3+ values at the same hour (and >=24 total points), an hourly pattern is recorded."""
    d = AnomalyDetector()
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    # Need at least 24 points to enter the seasonal-pattern detection loop.
    # Use ``timedelta(days=...)`` to keep all 25 points at the same hour-of-day.
    history = [
        MetricPoint(
            timestamp=base_time.replace(hour=10) + timedelta(days=i),
            value=42.0,
            metric_type="x",
        )
        for i in range(25)  # 25 points all at hour 10
    ]
    patterns = d._detect_seasonal_patterns(history)
    assert "hour_10" in patterns
    assert patterns["hour_10"] == 42.0


# ---------------------------------------------------------------------------
# Severity / confidence
# ---------------------------------------------------------------------------


def test_severity_from_z_score_critical() -> None:
    d = AnomalyDetector()
    assert d._severity_from_z_score(5.0) == "critical"


def test_severity_from_z_score_high() -> None:
    d = AnomalyDetector()
    assert d._severity_from_z_score(3.5) == "high"


def test_severity_from_z_score_medium() -> None:
    d = AnomalyDetector()
    assert d._severity_from_z_score(2.5) == "medium"


def test_severity_from_z_score_low() -> None:
    d = AnomalyDetector()
    assert d._severity_from_z_score(1.5) == "low"


def test_calculate_severity_zero_std_dev_returns_medium() -> None:
    d = AnomalyDetector()
    baseline = BaselineModel(
        metric_type="x",
        mean=10.0,
        std_dev=0.0,
        min_value=10.0,
        max_value=10.0,
        sample_count=10,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
    )
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=10.0,
        metric_type="x",
    )
    assert d._calculate_severity(point, baseline, 10.0, 10.0) == "medium"


def test_threshold_breached_in_direction_up() -> None:
    d = AnomalyDetector()
    assert d._threshold_breached_in_direction(100.0, 50.0, "up") is True
    assert d._threshold_breached_in_direction(10.0, 50.0, "up") is False


def test_threshold_breached_in_direction_down() -> None:
    d = AnomalyDetector()
    assert d._threshold_breached_in_direction(10.0, 50.0, "down") is True
    assert d._threshold_breached_in_direction(100.0, 50.0, "down") is False


def test_threshold_breached_in_direction_both() -> None:
    d = AnomalyDetector()
    assert d._threshold_breached_in_direction(100.0, 50.0, "both") is True
    assert d._threshold_breached_in_direction(-100.0, 50.0, "both") is True
    assert d._threshold_breached_in_direction(0.0, 50.0, "both") is False


def test_threshold_breached_in_direction_unknown() -> None:
    d = AnomalyDetector()
    assert d._threshold_breached_in_direction(100.0, 50.0, "sideways") is False


def test_is_critical_threshold_breached_unknown_metric() -> None:
    d = AnomalyDetector()
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=1.0,
        metric_type="not_in_configs",
    )
    assert d._is_critical_threshold_breached(point) is False


def test_is_critical_threshold_breached_known_metric() -> None:
    """When ``direction="up"`` and value > threshold, the critical branch fires."""
    d = AnomalyDetector()
    # Use ``complexity_score`` which has ``direction="up"`` and threshold=15.0.
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=20.0,  # > 15.0 threshold
        metric_type="complexity_score",
    )
    assert d._is_critical_threshold_breached(point) is True


def test_is_critical_threshold_breached_below_up_threshold() -> None:
    d = AnomalyDetector()
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=10.0,  # < 15.0 threshold for complexity_score (direction=up)
        metric_type="complexity_score",
    )
    assert d._is_critical_threshold_breached(point) is False


def test_is_critical_threshold_breached_down_direction() -> None:
    """When ``direction="down"`` and value < threshold, the critical branch fires."""
    d = AnomalyDetector()
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=0.5,  # < 0.7 threshold for coverage_percentage (direction=down)
        metric_type="coverage_percentage",
    )
    assert d._is_critical_threshold_breached(point) is True


def test_calculate_confidence_zero_std_dev() -> None:
    d = AnomalyDetector()
    baseline = BaselineModel(
        metric_type="x",
        mean=10.0,
        std_dev=0.0,
        min_value=10.0,
        max_value=10.0,
        sample_count=10,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
    )
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=10.0,
        metric_type="x",
    )
    conf = d._calculate_confidence(point, baseline)
    # sample_factor = 10/50 = 0.2, std_factor = 0.5 → 0.1
    assert conf == 0.1


def test_calculate_confidence_zero_mean() -> None:
    d = AnomalyDetector()
    baseline = BaselineModel(
        metric_type="x",
        mean=0.0,
        std_dev=1.0,
        min_value=0.0,
        max_value=0.0,
        sample_count=50,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
    )
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=1.0,
        metric_type="x",
    )
    conf = d._calculate_confidence(point, baseline)
    # cv = 1.0 (mean==0 default), std_factor = max(0.1, min(1.0, 0.0)) = 0.1
    assert conf == 0.1 * 1.0  # sample_factor=1.0 * std_factor=0.1


def test_calculate_z_score() -> None:
    d = AnomalyDetector()
    baseline = BaselineModel(
        metric_type="x",
        mean=10.0,
        std_dev=2.0,
        min_value=8.0,
        max_value=12.0,
        sample_count=20,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
    )
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        value=2.0,  # below lower_bound=6.0
        metric_type="x",
    )
    z = d._calculate_z_score(point, baseline, 6.0, 14.0)
    assert z == 4.0 / 2.0  # |2-6|=4 / std_dev=2


def test_get_seasonal_adjustment_no_pattern() -> None:
    d = AnomalyDetector()
    baseline = BaselineModel(
        metric_type="x",
        mean=10.0,
        std_dev=1.0,
        min_value=10.0,
        max_value=10.0,
        sample_count=5,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
    )
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, 3, tzinfo=UTC),
        value=10.0,
        metric_type="x",
    )
    assert d._get_seasonal_adjustment(point, baseline) == 0.0


def test_get_seasonal_adjustment_with_pattern() -> None:
    d = AnomalyDetector()
    baseline = BaselineModel(
        metric_type="x",
        mean=10.0,
        std_dev=1.0,
        min_value=10.0,
        max_value=10.0,
        sample_count=5,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        seasonal_patterns={"hour_3": 15.0},
    )
    point = MetricPoint(
        timestamp=datetime(2026, 1, 1, 3, tzinfo=UTC),
        value=10.0,
        metric_type="x",
    )
    # 15.0 - 10.0 = 5.0
    assert d._get_seasonal_adjustment(point, baseline) == 5.0


# ---------------------------------------------------------------------------
# get_anomalies / get_baseline_summary
# ---------------------------------------------------------------------------


def test_get_anomalies_no_filter() -> None:
    d = AnomalyDetector()
    d.anomalies = [
        AnomalyDetection(
            timestamp=datetime(2026, 1, 1, i, tzinfo=UTC),
            metric_type="x",
            value=float(i),
            expected_range=(0.0, 1.0),
            severity="low",
            confidence=0.5,
            description="d",
        )
        for i in range(5)
    ]
    result = d.get_anomalies()
    assert len(result) == 5
    # Sorted descending by timestamp.
    assert result[0].timestamp > result[-1].timestamp


def test_get_anomalies_filter_by_metric_type() -> None:
    d = AnomalyDetector()
    d.anomalies = [
        AnomalyDetection(
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            metric_type="a",
            value=1.0,
            expected_range=(0.0, 1.0),
            severity="low",
            confidence=0.5,
            description="d",
        ),
        AnomalyDetection(
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            metric_type="b",
            value=1.0,
            expected_range=(0.0, 1.0),
            severity="low",
            confidence=0.5,
            description="d",
        ),
    ]
    assert len(d.get_anomalies(metric_type="a")) == 1


def test_get_anomalies_filter_by_severity() -> None:
    d = AnomalyDetector()
    d.anomalies = [
        AnomalyDetection(
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            metric_type="x",
            value=1.0,
            expected_range=(0.0, 1.0),
            severity=sev,
            confidence=0.5,
            description="d",
        )
        for sev in ("low", "high", "low")
    ]
    assert len(d.get_anomalies(severity="high")) == 1


def test_get_anomalies_filter_by_since() -> None:
    d = AnomalyDetector()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    d.anomalies = [
        AnomalyDetection(
            timestamp=base - timedelta(days=i),
            metric_type="x",
            value=1.0,
            expected_range=(0.0, 1.0),
            severity="low",
            confidence=0.5,
            description="d",
        )
        for i in range(5)
    ]
    result = d.get_anomalies(since=base - timedelta(days=2))
    assert len(result) == 3


def test_get_anomalies_limit() -> None:
    d = AnomalyDetector()
    d.anomalies = [
        AnomalyDetection(
            timestamp=datetime(2026, 1, 1, i, tzinfo=UTC),
            metric_type="x",
            value=1.0,
            expected_range=(0.0, 1.0),
            severity="low",
            confidence=0.5,
            description="d",
        )
        for i in range(10)
    ]
    assert len(d.get_anomalies(limit=3)) == 3


def test_get_baseline_summary_empty() -> None:
    d = AnomalyDetector()
    assert d.get_baseline_summary() == {}


def test_get_baseline_summary_populated() -> None:
    d = AnomalyDetector()
    d.baselines["x"] = BaselineModel(
        metric_type="x",
        mean=10.0,
        std_dev=1.0,
        min_value=9.0,
        max_value=11.0,
        sample_count=20,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        seasonal_patterns={"hour_10": 10.0},
    )
    summary = d.get_baseline_summary()
    assert "x" in summary
    assert summary["x"]["mean"] == 10.0
    assert summary["x"]["range"] == (9.0, 11.0)
    assert summary["x"]["seasonal_patterns"] == 1


# ---------------------------------------------------------------------------
# export_model
# ---------------------------------------------------------------------------


def test_export_model_writes_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    d = AnomalyDetector()
    d.baselines["x"] = BaselineModel(
        metric_type="x",
        mean=10.0,
        std_dev=1.0,
        min_value=9.0,
        max_value=11.0,
        sample_count=20,
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        seasonal_patterns={"hour_10": 10.5},
    )
    out = tmp_path / "model.json"
    d.export_model(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "baselines" in data
    assert "x" in data["baselines"]
    assert data["baselines"]["x"]["mean"] == 10.0
    assert data["baselines"]["x"]["seasonal_patterns"] == {"hour_10": 10.5}
    assert data["config"]["baseline_window"] == 100
    assert "exported_at" in data
