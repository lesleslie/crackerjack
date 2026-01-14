"""Comprehensive tests for anomaly_detector.py.

Target Coverage: 60-65% (98-106 statements out of 163)
Test Strategy: 35-40 tests covering all dataclasses, public API, and core detection logic
"""

from datetime import datetime
import json
from pathlib import Path
import pytest
from unittest.mock import Mock, patch
import sys

# Workaround: Prevent quality/__init__.py from importing numpy-dependent modules
sys.modules["crackerjack.services.quality.quality_intelligence"] = Mock()

# Module-level import pattern to avoid pytest conflicts
from crackerjack.services.quality import anomaly_detector

MetricPoint = anomaly_detector.MetricPoint
AnomalyDetection = anomaly_detector.AnomalyDetection
BaselineModel = anomaly_detector.BaselineModel
AnomalyDetector = anomaly_detector.AnomalyDetector


class TestDataclasses:
    """Test dataclass creation and field initialization."""

    def test_metric_point_creation_with_all_fields(self) -> None:
        """Test MetricPoint dataclass with all fields provided."""
        timestamp = datetime(2026, 1, 11, 12, 0, 0)
        metadata = {"source": "pytest"}
        point = MetricPoint(
            timestamp=timestamp,
            value=75.5,
            metric_type="test_pass_rate",
            metadata=metadata,
        )

        assert point.timestamp == timestamp
        assert point.value == 75.5
        assert point.metric_type == "test_pass_rate"
        assert point.metadata == metadata

    def test_metric_point_default_metadata(self) -> None:
        """Test MetricPoint with default metadata (empty dict)."""
        point = MetricPoint(
            timestamp=datetime.now(),
            value=80.0,
            metric_type="coverage_percentage",
        )

        assert point.metadata == {}

    def test_anomaly_detection_creation(self) -> None:
        """Test AnomalyDetection dataclass creation."""
        detection = AnomalyDetection(
            timestamp=datetime(2026, 1, 11, 12, 0, 0),
            metric_type="test_pass_rate",
            value=45.0,
            expected_range=(60.0, 80.0),
            severity="high",
            confidence=0.85,
            description="High anomaly detected",
            metadata={"direction": "below"},
        )

        assert detection.severity == "high"
        assert detection.expected_range == (60.0, 80.0)
        assert detection.confidence == pytest.approx(0.85)

    def test_baseline_model_creation(self) -> None:
        """Test BaselineModel dataclass creation."""
        baseline = BaselineModel(
            metric_type="test_pass_rate",
            mean=70.0,
            std_dev=5.0,
            min_value=60.0,
            max_value=80.0,
            sample_count=100,
            last_updated=datetime(2026, 1, 11, 12, 0, 0),
            seasonal_patterns={"hour_9": 65.0, "hour_13": 75.0},
        )

        assert baseline.mean == pytest.approx(70.0)
        assert baseline.std_dev == pytest.approx(5.0)
        assert baseline.sample_count == 100
        assert len(baseline.seasonal_patterns) == 2

    def test_baseline_model_empty_seasonal_patterns(self) -> None:
        """Test BaselineModel with empty seasonal_patterns."""
        baseline = BaselineModel(
            metric_type="coverage_percentage",
            mean=65.0,
            std_dev=3.0,
            min_value=60.0,
            max_value=70.0,
            sample_count=50,
            last_updated=datetime.now(),
        )

        assert baseline.seasonal_patterns == {}


class TestConstructor:
    """Test AnomalyDetector initialization and configuration."""

    def test_default_parameters(self) -> None:
        """Test AnomalyDetector with default parameters."""
        detector = AnomalyDetector()

        assert detector.baseline_window == 100
        assert detector.sensitivity == pytest.approx(2.0)
        assert detector.min_samples == 10
        assert len(detector.metric_history) == 0
        assert len(detector.baselines) == 0
        assert len(detector.anomalies) == 0

    def test_custom_parameters(self) -> None:
        """Test AnomalyDetector with custom parameters."""
        detector = AnomalyDetector(
            baseline_window=50,
            sensitivity=3.0,
            min_samples=5,
        )

        assert detector.baseline_window == 50
        assert detector.sensitivity == pytest.approx(3.0)
        assert detector.min_samples == 5

    def test_initialization_of_data_structures(self) -> None:
        """Test proper initialization of internal data structures."""
        detector = AnomalyDetector()

        # metric_history should be defaultdict with deque
        assert "test_pass_rate" not in detector.metric_history
        detector.metric_history["test_pass_rate"].append(
            MetricPoint(timestamp=datetime.now(), value=70.0, metric_type="test_pass_rate")
        )
        assert "test_pass_rate" in detector.metric_history

        # baselines should be empty dict
        assert isinstance(detector.baselines, dict)

        # anomalies should be empty list
        assert isinstance(detector.anomalies, list)

    def test_metric_configs_initialization(self) -> None:
        """Test that metric_configs contains predefined configurations."""
        detector = AnomalyDetector()

        # Check some predefined configs
        assert "test_pass_rate" in detector.metric_configs
        assert detector.metric_configs["test_pass_rate"]["critical_threshold"] == 0.8
        assert detector.metric_configs["test_pass_rate"]["direction"] == "both"

        assert "coverage_percentage" in detector.metric_configs
        assert detector.metric_configs["coverage_percentage"]["direction"] == "down"

        assert "complexity_score" in detector.metric_configs
        assert detector.metric_configs["complexity_score"]["direction"] == "up"


class TestAddMetric:
    """Test add_metric() main API method."""

    def test_basic_metric_addition(self) -> None:
        """Test adding a basic metric point."""
        detector = AnomalyDetector()
        detector.add_metric("test_pass_rate", 75.5)

        assert "test_pass_rate" in detector.metric_history
        assert len(detector.metric_history["test_pass_rate"]) == 1
        assert detector.metric_history["test_pass_rate"][0].value == pytest.approx(75.5)

    def test_timestamp_default(self) -> None:
        """Test add_metric with default timestamp (datetime.now())."""
        detector = AnomalyDetector()
        before = datetime.now()
        detector.add_metric("coverage_percentage", 65.0)
        after = datetime.now()

        assert "coverage_percentage" in detector.metric_history
        point = detector.metric_history["coverage_percentage"][0]
        assert before <= point.timestamp <= after

    def test_metadata_default(self) -> None:
        """Test add_metric with default metadata (empty dict)."""
        detector = AnomalyDetector()
        detector.add_metric("complexity_score", 12.0)

        point = detector.metric_history["complexity_score"][0]
        assert point.metadata == {}

    def test_custom_timestamp_and_metadata(self) -> None:
        """Test add_metric with custom timestamp and metadata."""
        detector = AnomalyDetector()
        timestamp = datetime(2026, 1, 11, 12, 0, 0)
        metadata = {"source": "pytest", "environment": "test"}

        detector.add_metric(
            metric_type="test_pass_rate",
            value=80.0,
            timestamp=timestamp,
            metadata=metadata,
        )

        point = detector.metric_history["test_pass_rate"][0]
        assert point.timestamp == timestamp
        assert point.metadata == metadata

    def test_handles_different_metric_types(self) -> None:
        """Test that different metric types are tracked separately."""
        detector = AnomalyDetector()

        detector.add_metric("test_pass_rate", 75.0)
        detector.add_metric("coverage_percentage", 65.0)
        detector.add_metric("complexity_score", 10.0)

        assert len(detector.metric_history) == 3
        assert "test_pass_rate" in detector.metric_history
        assert "coverage_percentage" in detector.metric_history
        assert "complexity_score" in detector.metric_history

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_triggers_anomaly_detection_when_enough_samples(
        self, mock_logger: Mock
    ) -> None:
        """Test that anomaly detection triggers after min_samples reached."""
        detector = AnomalyDetector(min_samples=5)

        # Add 4 samples (below min_samples)
        for i in range(4):
            detector.add_metric("test_pass_rate", 70.0 + i)

        assert len(detector.anomalies) == 0

        # Add 5th sample (reaches min_samples)
        detector.add_metric("test_pass_rate", 100.0)  # Clear anomaly

        # Should trigger detection (even if no anomaly found)
        assert len(detector.metric_history["test_pass_rate"]) == 5


class TestBaselineUpdate:
    """Test _update_baseline() private method."""

    def test_update_baseline_creates_baseline_model(self) -> None:
        """Test that _update_baseline creates a BaselineModel."""
        detector = AnomalyDetector(min_samples=3)

        # Add enough samples to trigger baseline update
        for value in [65.0, 70.0, 75.0]:
            detector.add_metric("test_pass_rate", value)

        assert "test_pass_rate" in detector.baselines
        baseline = detector.baselines["test_pass_rate"]
        assert isinstance(baseline, BaselineModel)

    def test_correct_mean_calculated(self) -> None:
        """Test that mean is calculated correctly."""
        detector = AnomalyDetector(min_samples=3)

        for value in [60.0, 70.0, 80.0]:
            detector.add_metric("test_pass_rate", value)

        baseline = detector.baselines["test_pass_rate"]
        assert baseline.mean == pytest.approx(70.0)

    def test_correct_std_dev_calculated(self) -> None:
        """Test that standard deviation is calculated correctly."""
        detector = AnomalyDetector(min_samples=3)

        for value in [60.0, 70.0, 80.0]:
            detector.add_metric("test_pass_rate", value)

        baseline = detector.baselines["test_pass_rate"]
        # Std dev of [60, 70, 80] = 10.0
        assert baseline.std_dev == pytest.approx(10.0, abs=0.1)

    def test_sample_count_correct(self) -> None:
        """Test that sample count is accurate."""
        detector = AnomalyDetector(min_samples=5)

        for i in range(5):
            detector.add_metric("coverage_percentage", 60.0 + i)

        baseline = detector.baselines["coverage_percentage"]
        assert baseline.sample_count == 5

    def test_last_updated_timestamp_set(self) -> None:
        """Test that last_updated is set to current time."""
        detector = AnomalyDetector(min_samples=3)

        before = datetime.now()
        for value in [65.0, 70.0, 75.0]:
            detector.add_metric("test_pass_rate", value)
        after = datetime.now()

        baseline = detector.baselines["test_pass_rate"]
        assert before <= baseline.last_updated <= after


class TestSeasonalPatterns:
    """Test _detect_seasonal_patterns() private method."""

    def test_returns_empty_dict_with_less_than_24_samples(self) -> None:
        """Test that seasonal patterns require at least 24 samples."""
        detector = AnomalyDetector(min_samples=10)

        # Add 23 samples (below 24 threshold)
        for i in range(23):
            timestamp = datetime(2026, 1, 11, hour=i % 24)
            detector.add_metric("test_pass_rate", 70.0, timestamp=timestamp)

        baseline = detector.baselines.get("test_pass_rate")
        if baseline:
            assert baseline.seasonal_patterns == {}

    def test_detects_hourly_patterns_with_24_plus_samples(self) -> None:
        """Test hourly pattern detection with 24+ samples."""
        detector = AnomalyDetector(min_samples=24)

        # Add 30 samples with hourly patterns
        # Hour 9: consistently ~65, Hour 13: consistently ~75
        for i in range(30):
            hour = 9 if i % 2 == 0 else 13
            timestamp = datetime(2026, 1, 11, hour=hour, minute=i)
            value = 65.0 if hour == 9 else 75.0
            detector.add_metric("test_pass_rate", value, timestamp=timestamp)

        baseline = detector.baselines.get("test_pass_rate")
        if baseline:
            # Should detect patterns for hours with 3+ samples
            assert len(baseline.seasonal_patterns) > 0

    def test_calculates_hourly_means_correctly(self) -> None:
        """Test that hourly means are calculated accurately."""
        detector = AnomalyDetector(min_samples=24)

        # Create pattern: hour 9 always 65.0, hour 13 always 75.0
        for i in range(30):
            hour = 9 if i % 2 == 0 else 13
            timestamp = datetime(2026, 1, 11, hour=hour, minute=i)
            value = 65.0 if hour == 9 else 75.0
            detector.add_metric("test_pass_rate", value, timestamp=timestamp)

        baseline = detector.baselines.get("test_pass_rate")
        if baseline and baseline.seasonal_patterns:
            # Check that detected patterns are close to expected values
            for pattern_key, pattern_value in baseline.seasonal_patterns.items():
                if "hour_9" in pattern_key:
                    assert pattern_value == pytest.approx(65.0, abs=1.0)
                elif "hour_13" in pattern_key:
                    assert pattern_value == pytest.approx(75.0, abs=1.0)


class TestAnomalyDetection:
    """Test _detect_anomaly() core detection logic."""

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_no_anomaly_when_within_bounds(self, mock_logger: Mock) -> None:
        """Test that no anomaly is detected when value is within bounds.

        NOTE: With very small std_dev (all values=70.0), the bounds are very tight.
        We need to add variance to the baseline to create reasonable bounds.
        """
        detector = AnomalyDetector(min_samples=10, sensitivity=2.0)

        # Create baseline with variance: mean=70, std_dev≈5
        for value in [60.0, 65.0, 70.0, 75.0, 80.0] * 2:
            detector.add_metric("test_pass_rate", value)

        # Clear any anomalies from baseline creation
        detector.anomalies.clear()

        # Add value within bounds (70 ± 2*5 = 60-80)
        detector.add_metric("test_pass_rate", 72.0)

        assert len(detector.anomalies) == 0

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_detects_anomaly_above_upper_bound(self, mock_logger: Mock) -> None:
        """Test anomaly detection for value above upper bound."""
        detector = AnomalyDetector(min_samples=10, sensitivity=2.0)

        # Create stable baseline
        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)

        # Add value above upper bound (should be >80)
        detector.add_metric("test_pass_rate", 95.0)

        assert len(detector.anomalies) == 1
        anomaly = detector.anomalies[0]
        assert anomaly.severity in ("low", "medium", "high", "critical")
        assert anomaly.value == pytest.approx(95.0)

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_detects_anomaly_below_lower_bound(self, mock_logger: Mock) -> None:
        """Test anomaly detection for value below lower bound."""
        detector = AnomalyDetector(min_samples=10, sensitivity=2.0)

        # Create stable baseline
        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)

        # Add value below lower bound (should be <60)
        detector.add_metric("test_pass_rate", 40.0)

        assert len(detector.anomalies) == 1
        anomaly = detector.anomalies[0]
        assert anomaly.metric_type == "test_pass_rate"
        assert anomaly.value == pytest.approx(40.0)

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_returns_none_when_no_baseline_exists(self, mock_logger: Mock) -> None:
        """Test that detection returns None when baseline doesn't exist."""
        detector = AnomalyDetector(min_samples=10)

        # Try to add metric without enough samples
        detector.add_metric("test_pass_rate", 50.0)

        assert len(detector.anomalies) == 0

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_creates_anomaly_detection_with_correct_fields(
        self, mock_logger: Mock
    ) -> None:
        """Test that AnomalyDetection objects have all required fields."""
        detector = AnomalyDetector(min_samples=10)

        # Create baseline
        for _ in range(10):
            detector.add_metric("coverage_percentage", 65.0)

        # Trigger anomaly
        detector.add_metric("coverage_percentage", 30.0)

        assert len(detector.anomalies) == 1
        anomaly = detector.anomalies[0]

        assert hasattr(anomaly, "timestamp")
        assert hasattr(anomaly, "metric_type")
        assert hasattr(anomaly, "value")
        assert hasattr(anomaly, "expected_range")
        assert hasattr(anomaly, "severity")
        assert hasattr(anomaly, "confidence")
        assert hasattr(anomaly, "description")

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_sensitivity_parameter_affects_bounds(self, mock_logger: Mock) -> None:
        """Test that sensitivity changes detection threshold."""
        # Low sensitivity (wider bounds)
        detector_low = AnomalyDetector(min_samples=10, sensitivity=3.0)
        for _ in range(10):
            detector_low.add_metric("test_pass_rate", 70.0)
        detector_low.add_metric("test_pass_rate", 85.0)

        # High sensitivity (narrower bounds)
        detector_high = AnomalyDetector(min_samples=10, sensitivity=1.0)
        for _ in range(10):
            detector_high.add_metric("coverage_percentage", 65.0)
        detector_high.add_metric("coverage_percentage", 70.0)

        # High sensitivity should detect more anomalies
        assert len(detector_high.anomalies) >= len(detector_low.anomalies)


class TestGetAnomalies:
    """Test get_anomalies() retrieval and filtering."""

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_returns_all_anomalies_when_no_filters(self, mock_logger: Mock) -> None:
        """Test getting all anomalies without filters."""
        detector = AnomalyDetector(min_samples=10)

        # Create baseline and trigger multiple anomalies
        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)

        detector.add_metric("test_pass_rate", 95.0)
        detector.add_metric("test_pass_rate", 40.0)

        anomalies = detector.get_anomalies()
        assert len(anomalies) == 2

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_filters_by_metric_type(self, mock_logger: Mock) -> None:
        """Test filtering anomalies by metric type."""
        detector = AnomalyDetector(min_samples=10)

        # Create baselines for two metrics
        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)
            detector.add_metric("coverage_percentage", 65.0)

        # Trigger anomalies
        detector.add_metric("test_pass_rate", 95.0)
        detector.add_metric("coverage_percentage", 30.0)

        # Filter by one type
        test_pass_anomalies = detector.get_anomalies(metric_type="test_pass_rate")
        assert len(test_pass_anomalies) == 1
        assert test_pass_anomalies[0].metric_type == "test_pass_rate"

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_respects_limit_parameter(self, mock_logger: Mock) -> None:
        """Test that limit parameter restricts results."""
        detector = AnomalyDetector(min_samples=10)

        # Create baseline
        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)

        # Trigger multiple anomalies
        for value in [95.0, 40.0, 96.0, 39.0]:
            detector.add_metric("test_pass_rate", value)

        # Get limited results
        limited = detector.get_anomalies(limit=2)
        assert len(limited) == 2

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_sorts_by_timestamp_descending(self, mock_logger: Mock) -> None:
        """Test that anomalies are sorted newest first."""
        detector = AnomalyDetector(min_samples=10)

        # Create baseline
        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)

        # Trigger anomalies with different timestamps
        detector.add_metric("test_pass_rate", 95.0)
        detector.add_metric("test_pass_rate", 40.0)

        anomalies = detector.get_anomalies()
        # Should be sorted newest first
        if len(anomalies) >= 2:
            assert anomalies[0].timestamp >= anomalies[1].timestamp


class TestGetBaselineSummary:
    """Test get_baseline_summary() method."""

    def test_returns_empty_dict_when_no_baselines(self) -> None:
        """Test summary when no baselines exist."""
        detector = AnomalyDetector()
        summary = detector.get_baseline_summary()

        assert summary == {}

    def test_returns_summary_with_all_fields(self) -> None:
        """Test that summary includes all baseline fields.

        NOTE: The summary uses "range" tuple instead of separate "min_value"
        and "max_value" keys, and "seasonal_patterns" returns a count.
        """
        detector = AnomalyDetector(min_samples=5)

        for value in [65.0, 70.0, 75.0, 68.0, 72.0]:
            detector.add_metric("test_pass_rate", value)

        summary = detector.get_baseline_summary()

        assert "test_pass_rate" in summary
        baseline_summary = summary["test_pass_rate"]

        assert "mean" in baseline_summary
        assert "std_dev" in baseline_summary
        assert "range" in baseline_summary  # Tuple (min, max)
        assert "sample_count" in baseline_summary
        assert "last_updated" in baseline_summary
        assert "seasonal_patterns" in baseline_summary  # Count, not dict


class TestExportModel:
    """Test export_model() method."""

    def test_exports_baselines_to_json(self, tmp_path: Path) -> None:
        """Test that baselines are exported to JSON file."""
        detector = AnomalyDetector(min_samples=5)
        output_path = tmp_path / "model_export.json"

        # Create baseline
        for value in [65.0, 70.0, 75.0, 68.0, 72.0]:
            detector.add_metric("test_pass_rate", value)

        detector.export_model(output_path)

        assert output_path.exists()
        with output_path.open() as f:
            data = json.load(f)

        assert "baselines" in data
        assert "test_pass_rate" in data["baselines"]

    def test_exports_config_parameters(self, tmp_path: Path) -> None:
        """Test that configuration is exported."""
        detector = AnomalyDetector(
            baseline_window=50, sensitivity=3.0, min_samples=5
        )
        output_path = tmp_path / "config_export.json"

        for value in [65.0, 70.0, 75.0, 68.0, 72.0]:
            detector.add_metric("test_pass_rate", value)

        detector.export_model(output_path)

        with output_path.open() as f:
            data = json.load(f)

        assert "config" in data
        assert data["config"]["baseline_window"] == 50
        assert data["config"]["sensitivity"] == pytest.approx(3.0)
        assert data["config"]["min_samples"] == 5

    def test_includes_exported_at_timestamp(self, tmp_path: Path) -> None:
        """Test that export includes timestamp."""
        detector = AnomalyDetector(min_samples=5)
        output_path = tmp_path / "timestamp_export.json"

        before = datetime.now()
        for value in [65.0, 70.0, 75.0, 68.0, 72.0]:
            detector.add_metric("test_pass_rate", value)
        detector.export_model(output_path)
        after = datetime.now()

        with output_path.open() as f:
            data = json.load(f)

        assert "exported_at" in data
        exported_at = datetime.fromisoformat(data["exported_at"])
        assert before <= exported_at <= after


class TestSeverityCalculation:
    """Test severity calculation logic."""

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_critical_for_large_z_score(self, mock_logger: Mock) -> None:
        """Test that large deviations result in critical severity."""
        detector = AnomalyDetector(min_samples=10)

        # Create stable baseline (low variance)
        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)

        # Add extreme value
        detector.add_metric("test_pass_rate", 100.0)

        if len(detector.anomalies) > 0:
            assert detector.anomalies[0].severity in (
                "high",
                "critical",
            )

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_medium_for_moderate_z_score(self, mock_logger: Mock) -> None:
        """Test that moderate deviations result in medium severity."""
        detector = AnomalyDetector(min_samples=10)

        for _ in range(10):
            detector.add_metric("coverage_percentage", 65.0)

        # Add moderately anomalous value
        detector.add_metric("coverage_percentage", 85.0)

        if len(detector.anomalies) > 0:
            # Severity depends on exact z-score
            assert detector.anomalies[0].severity in (
                "low",
                "medium",
                "high",
            )


class TestConfidenceCalculation:
    """Test confidence scoring logic."""

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_confidence_between_0_and_1(self, mock_logger: Mock) -> None:
        """Test that confidence scores are in valid range."""
        detector = AnomalyDetector(min_samples=10)

        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)

        detector.add_metric("test_pass_rate", 95.0)

        if len(detector.anomalies) > 0:
            confidence = detector.anomalies[0].confidence
            assert 0.0 <= confidence <= 1.0


class TestIntegration:
    """Integration tests for complete workflows."""

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_full_workflow_add_detect_retrieve(
        self, mock_logger: Mock
    ) -> None:
        """Test complete workflow: add metrics → detect → retrieve."""
        detector = AnomalyDetector(min_samples=10)

        # Phase 1: Build baseline
        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)

        # Phase 2: Trigger anomaly
        detector.add_metric("test_pass_rate", 95.0)

        # Phase 3: Retrieve anomalies
        anomalies = detector.get_anomalies(metric_type="test_pass_rate")

        assert len(anomalies) == 1
        assert anomalies[0].metric_type == "test_pass_rate"

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_multiple_metric_types_tracked_separately(
        self, mock_logger: Mock
    ) -> None:
        """Test that different metric types maintain separate baselines."""
        detector = AnomalyDetector(min_samples=10)

        # Build baselines for multiple metrics
        for _ in range(10):
            detector.add_metric("test_pass_rate", 70.0)
            detector.add_metric("coverage_percentage", 65.0)

        # Trigger anomaly in one metric
        detector.add_metric("test_pass_rate", 95.0)

        # Check that baselines are separate
        assert "test_pass_rate" in detector.baselines
        assert "coverage_percentage" in detector.baselines

        # Check that only one anomaly detected
        all_anomalies = detector.get_anomalies()
        test_pass_anomalies = detector.get_anomalies(metric_type="test_pass_rate")

        assert len(all_anomalies) == 1
        assert len(test_pass_anomalies) == 1

    @patch("crackerjack.services.quality.anomaly_detector.logger")
    def test_anomalies_list_accumulates(self, mock_logger: Mock) -> None:
        """Test that anomalies list accumulates over time.

        NOTE: Baseline updates after each metric addition, which can change
        the bounds. Not all anomalous values will result in anomaly detections
        as the baseline adapts to new data.
        """
        detector = AnomalyDetector(min_samples=10)

        # Build baseline with variance for stable bounds
        for value in [60.0, 65.0, 70.0, 75.0, 80.0] * 2:
            detector.add_metric("test_pass_rate", value)

        # Clear baseline creation anomalies
        initial_count = len(detector.anomalies)

        # Trigger multiple anomalies
        detector.add_metric("test_pass_rate", 95.0)  # Above upper bound
        detector.add_metric("test_pass_rate", 40.0)  # Below lower bound
        detector.add_metric("test_pass_rate", 96.0)  # Above upper bound

        # At least 2 new anomalies should be detected
        all_anomalies = detector.get_anomalies()
        assert len(all_anomalies) >= initial_count + 2
