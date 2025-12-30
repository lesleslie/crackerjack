"""Tests for the AnomalyDetector service."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crackerjack.services.quality.anomaly_detector import (
    AnomalyDetector,
    AnomalyDetection,
    BaselineModel,
    MetricPoint,
)

# Check if scipy is available
try:
    from crackerjack.services.quality.quality_intelligence import SCIPY_AVAILABLE
except ImportError:
    # If there's an import error, assume scipy is not available
    SCIPY_AVAILABLE = False


class TestAnomalyDetector:
    """Test cases for the AnomalyDetector class."""

    def test_init(self):
        """Test that AnomalyDetector initializes with default parameters."""
        detector = AnomalyDetector()

        # Verify default parameters
        assert detector.baseline_window == 100
        assert detector.sensitivity == 2.0
        assert detector.min_samples == 10

        # Verify data structures are initialized
        assert isinstance(detector.metric_history, dict)
        assert isinstance(detector.baselines, dict)
        assert isinstance(detector.anomalies, list)
        assert len(detector.anomalies) == 0

    def test_init_custom_parameters(self):
        """Test that AnomalyDetector initializes with custom parameters."""
        detector = AnomalyDetector(baseline_window=50, sensitivity=3.0, min_samples=5)

        # Verify custom parameters
        assert detector.baseline_window == 50
        assert detector.sensitivity == 3.0
        assert detector.min_samples == 5

    def test_add_metric_creates_history(self):
        """Test that adding a metric creates history entries."""
        detector = AnomalyDetector(min_samples=3)

        # Add metrics
        detector.add_metric("test_metric", 10.0)
        detector.add_metric("test_metric", 15.0)
        detector.add_metric("test_metric", 20.0)

        # Verify history was created
        assert "test_metric" in detector.metric_history
        assert len(detector.metric_history["test_metric"]) == 3

        # Verify metric points
        points = list(detector.metric_history["test_metric"])
        assert all(isinstance(point, MetricPoint) for point in points)
        assert [point.value for point in points] == [10.0, 15.0, 20.0]

    def test_add_metric_with_timestamp(self):
        """Test that adding a metric with custom timestamp works."""
        detector = AnomalyDetector(min_samples=2)
        custom_timestamp = datetime(2023, 1, 1, 12, 0, 0)

        # Add metric with custom timestamp
        detector.add_metric("test_metric", 10.0, timestamp=custom_timestamp)

        # Verify timestamp was stored
        points = list(detector.metric_history["test_metric"])
        assert len(points) == 1
        assert points[0].timestamp == custom_timestamp

    def test_add_metric_with_metadata(self):
        """Test that adding a metric with metadata works."""
        detector = AnomalyDetector(min_samples=2)
        metadata = {"source": "test", "version": "1.0"}

        # Add metric with metadata
        detector.add_metric("test_metric", 10.0, metadata=metadata)

        # Verify metadata was stored
        points = list(detector.metric_history["test_metric"])
        assert len(points) == 1
        assert points[0].metadata == metadata

    def test_update_baseline_creates_model(self):
        """Test that baseline is updated when enough samples are available."""
        detector = AnomalyDetector(min_samples=5)

        # Add enough samples to trigger baseline update
        values = [10.0, 12.0, 8.0, 11.0, 9.0, 13.0, 7.0, 14.0, 6.0, 15.0]
        for value in values:
            detector.add_metric("test_metric", value)

        # Verify baseline was created
        assert "test_metric" in detector.baselines
        baseline = detector.baselines["test_metric"]
        assert isinstance(baseline, BaselineModel)
        assert baseline.metric_type == "test_metric"
        assert baseline.sample_count == len(values)

    def test_detect_normal_values_no_anomalies(self):
        """Test that normal values within bounds don't create anomalies."""
        detector = AnomalyDetector(min_samples=5)

        # Add normal values that shouldn't trigger anomalies
        for i in range(20):
            detector.add_metric("test_metric", 10.0 + (i % 3))  # Values 10-12

        # Verify no anomalies were detected
        assert len(detector.anomalies) == 0

    def test_detect_anomaly_creates_detection(self):
        """Test that anomalous values create anomaly detections."""
        detector = AnomalyDetector(min_samples=10, sensitivity=2.0)

        # Add normal values to establish baseline
        for i in range(20):
            detector.add_metric("test_metric", 10.0 + (i % 3))  # Values 10-12

        # Add an anomalous value
        detector.add_metric("test_metric", 50.0)  # Way outside normal range

        # Verify anomaly was detected
        assert len(detector.anomalies) == 1
        anomaly = detector.anomalies[0]
        assert isinstance(anomaly, AnomalyDetection)
        assert anomaly.metric_type == "test_metric"
        assert anomaly.value == 50.0
        assert anomaly.severity in ["low", "medium", "high", "critical"]

    def test_get_anomalies_returns_filtered_results(self):
        """Test that get_anomalies filters results correctly."""
        detector = AnomalyDetector(min_samples=5)

        # Create some anomalies
        timestamps = [datetime.now() - timedelta(hours=i) for i in range(5)]

        # Add normal values first
        for i in range(10):
            detector.add_metric("metric1", 10.0 + (i % 3))

        # Add anomalous values
        detector.add_metric("metric1", 50.0)  # Creates anomaly
        detector.add_metric("metric2", 75.0)  # Creates anomaly

        # Test filtering by metric type
        metric1_anomalies = detector.get_anomalies(metric_type="metric1")
        assert len(metric1_anomalies) >= 1
        assert all(a.metric_type == "metric1" for a in metric1_anomalies)

        # Test filtering by severity
        critical_anomalies = detector.get_anomalies(severity="critical")
        if critical_anomalies:
            assert all(a.severity == "critical" for a in critical_anomalies)

        # Test filtering by time
        recent_anomalies = detector.get_anomalies(since=timestamps[2])
        if recent_anomalies:
            assert all(a.timestamp >= timestamps[2] for a in recent_anomalies)

    def test_get_baseline_summary_returns_summary(self):
        """Test that get_baseline_summary returns proper summary."""
        detector = AnomalyDetector(min_samples=5)

        # Add metrics to create baselines
        for i in range(10):
            detector.add_metric("metric1", 10.0 + (i % 3))
            detector.add_metric("metric2", 20.0 + (i % 4))

        # Get summary
        summary = detector.get_baseline_summary()

        # Verify summary structure
        assert isinstance(summary, dict)
        assert "metric1" in summary
        assert "metric2" in summary

        metric1_summary = summary["metric1"]
        assert "mean" in metric1_summary
        assert "std_dev" in metric1_summary
        assert "range" in metric1_summary
        assert "sample_count" in metric1_summary

    def test_export_model_creates_file(self):
        """Test that export_model creates a valid JSON file."""
        detector = AnomalyDetector(min_samples=5)

        # Add metrics to create baselines
        for i in range(10):
            detector.add_metric("test_metric", 10.0 + (i % 3))

        # Export model
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "model.json"
            detector.export_model(output_path)

            # Verify file was created
            assert output_path.exists()

            # Verify file contains valid JSON
            import json
            with open(output_path, "r", encoding="utf-8") as f:
                model_data = json.load(f)

            # Verify model data structure
            assert "baselines" in model_data
            assert "config" in model_data
            assert "exported_at" in model_data

            # Verify baseline data
            baselines = model_data["baselines"]
            assert "test_metric" in baselines
            baseline_data = baselines["test_metric"]
            assert "metric_type" in baseline_data
            assert "mean" in baseline_data
            assert "std_dev" in baseline_data

    @pytest.mark.skipif(
        not SCIPY_AVAILABLE,
        reason="Test requires scipy which is not available"
    )
    def test_detect_seasonal_patterns_identifies_patterns(self):
        """Test that seasonal patterns are detected correctly."""
        detector = AnomalyDetector(min_samples=5)

        # Add metrics with clear hourly patterns
        base_time = datetime(2023, 1, 1, 0, 0, 0)
        for i in range(72):  # Three days of hourly data (>=3 samples/hour)
            timestamp = base_time + timedelta(hours=i)
            # Create pattern where even hours have higher values
            value = 20.0 if i % 2 == 0 else 10.0
            point = MetricPoint(
                timestamp=timestamp,
                value=value,
                metric_type="hourly_metric"
            )
            detector.metric_history["hourly_metric"].append(point)

        # Force baseline update
        detector._update_baseline("hourly_metric")

        # Verify seasonal patterns were detected
        baseline = detector.baselines["hourly_metric"]
        assert isinstance(baseline.seasonal_patterns, dict)
        # Should have some hourly patterns
        assert len(baseline.seasonal_patterns) > 0

    def test_calculate_severity_handles_edge_cases(self):
        """Test severity calculation handles edge cases."""
        detector = AnomalyDetector(min_samples=3)

        # Add metrics to create baseline
        for i in range(10):
            detector.add_metric("test_metric", 10.0)

        # Test with zero standard deviation (constant values)
        point = MetricPoint(
            timestamp=datetime.now(),
            value=50.0,  # Large deviation from constant baseline
            metric_type="test_metric"
        )

        # This should not crash and should return a severity
        # Note: We're testing internal methods that would normally be called internally
        baseline = detector.baselines["test_metric"]
        severity = detector._calculate_severity(point, baseline, 5.0, 15.0)
        assert isinstance(severity, str)
        assert severity in ["low", "medium", "high", "critical"]

    def test_threshold_breach_detection_works(self):
        """Test that threshold breach detection works correctly."""
        detector = AnomalyDetector()

        # Test upward threshold breach
        result = detector._threshold_breached_in_direction(15.0, 10.0, "up")
        assert result is True

        result = detector._threshold_breached_in_direction(5.0, 10.0, "up")
        assert result is False

        # Test downward threshold breach
        result = detector._threshold_breached_in_direction(5.0, 10.0, "down")
        assert result is True

        result = detector._threshold_breached_in_direction(15.0, 10.0, "down")
        assert result is False

        # Test two-sided threshold breach
        result = detector._threshold_breached_in_direction(15.0, 10.0, "both")
        assert result is True

        result = detector._threshold_breached_in_direction(-15.0, 10.0, "both")
        assert result is True

        result = detector._threshold_breached_in_direction(5.0, 10.0, "both")
        assert result is False

    def test_anomaly_description_generation(self):
        """Test that anomaly descriptions are generated correctly."""
        detector = AnomalyDetector()

        # Create test point and baseline
        point = MetricPoint(
            timestamp=datetime.now(),
            value=50.0,
            metric_type="test_metric"
        )
        baseline = BaselineModel(
            metric_type="test_metric",
            mean=25.0,
            std_dev=5.0,
            min_value=10.0,
            max_value=40.0,
            sample_count=100,
            last_updated=datetime.now()
        )

        # Test description generation
        description = detector._generate_anomaly_description(
            point, baseline, 15.0, 35.0, "high"
        )

        # Verify description contains key information
        assert "High anomaly" in description
        assert "test_metric" in description
        assert "50.0" in description
        assert "above" in description or "below" in description

    def test_get_anomalies_sorts_by_timestamp(self):
        """Test that get_anomalies returns results sorted by timestamp."""
        detector = AnomalyDetector()

        # Add some anomalies with different timestamps
        base_time = datetime(2023, 1, 1, 12, 0, 0)
        for i in range(5):
            timestamp = base_time + timedelta(hours=i)
            anomaly = AnomalyDetection(
                timestamp=timestamp,
                metric_type="test_metric",
                value=10.0 + i,
                expected_range=(5.0, 15.0),
                severity="medium",
                confidence=0.8,
                description=f"Test anomaly {i}"
            )
            detector.anomalies.append(anomaly)

        # Get anomalies (should be sorted newest first)
        anomalies = detector.get_anomalies()

        # Verify sorting
        assert len(anomalies) == 5
        for i in range(len(anomalies) - 1):
            assert anomalies[i].timestamp >= anomalies[i + 1].timestamp

    def test_get_anomalies_respects_limit(self):
        """Test that get_anomalies respects the limit parameter."""
        detector = AnomalyDetector()

        # Add many anomalies
        for i in range(20):
            anomaly = AnomalyDetection(
                timestamp=datetime.now(),
                metric_type="test_metric",
                value=10.0,
                expected_range=(5.0, 15.0),
                severity="medium",
                confidence=0.8,
                description=f"Test anomaly {i}"
            )
            detector.anomalies.append(anomaly)

        # Get limited anomalies
        limited_anomalies = detector.get_anomalies(limit=5)
        assert len(limited_anomalies) == 5

        # Get all anomalies
        all_anomalies = detector.get_anomalies()
        assert len(all_anomalies) == 20
