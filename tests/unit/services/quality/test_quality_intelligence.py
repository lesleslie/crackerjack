"""Unit tests for QualityIntelligence.

Tests quality anomaly detection, pattern recognition,
predictions, recommendations, and comprehensive insights.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from crackerjack.services.quality.quality_intelligence import (
    AnomalyType,
    PatternType,
    QualityAnomaly,
    QualityInsights,
    QualityIntelligenceService,
    QualityPattern,
    QualityPrediction,
    SCIPY_AVAILABLE,
)
from crackerjack.services.quality.quality_baseline_enhanced import (
    AlertSeverity,
    EnhancedQualityBaselineService,
    TrendDirection,
)


@pytest.mark.unit
class TestAnomalyTypeEnum:
    """Test AnomalyType enum."""

    def test_anomaly_type_values(self) -> None:
        """Test all anomaly types are defined."""
        assert AnomalyType.SPIKE.value == "spike"
        assert AnomalyType.DROP.value == "drop"
        assert AnomalyType.DRIFT.value == "drift"
        assert AnomalyType.OSCILLATION.value == "oscillation"
        assert AnomalyType.OUTLIER.value == "outlier"

    def test_anomaly_type_count(self) -> None:
        """Test there are exactly 5 anomaly types."""
        assert len(AnomalyType) == 5


@pytest.mark.unit
class TestPatternTypeEnum:
    """Test PatternType enum."""

    def test_pattern_type_values(self) -> None:
        """Test all pattern types are defined."""
        assert PatternType.CYCLIC.value == "cyclic"
        assert PatternType.SEASONAL.value == "seasonal"
        assert PatternType.CORRELATION.value == "correlation"
        assert PatternType.REGRESSION.value == "regression"
        assert PatternType.IMPROVEMENT.value == "improvement"

    def test_pattern_type_count(self) -> None:
        """Test there are exactly 5 pattern types."""
        assert len(PatternType) == 5


@pytest.mark.unit
class TestQualityAnomalyDataClass:
    """Test QualityAnomaly dataclass."""

    def test_quality_anomaly_creation(self) -> None:
        """Test QualityAnomaly dataclass creation."""
        detected_at = datetime.now(timezone.utc)
        anomaly = QualityAnomaly(
            anomaly_type=AnomalyType.SPIKE,
            metric_name="test_coverage",
            detected_at=detected_at,
            confidence=0.9,
            severity=AlertSeverity.CRITICAL,
            description="Test coverage spiked unexpectedly",
            actual_value=75.0,
            expected_value=65.0,
            deviation_sigma=1.5,
        )

        assert anomaly.metric_name == "test_coverage"
        assert anomaly.anomaly_type == AnomalyType.SPIKE
        assert anomaly.confidence == 0.9
        assert anomaly.severity == AlertSeverity.CRITICAL
        assert anomaly.actual_value == 75.0
        assert anomaly.expected_value == 65.0
        assert anomaly.deviation_sigma == 1.5
        assert anomaly.detected_at == detected_at

    def test_quality_anomaly_to_dict(self) -> None:
        """Test QualityAnomaly to_dict method."""
        detected_at = datetime.now(timezone.utc)
        anomaly = QualityAnomaly(
            anomaly_type=AnomalyType.DROP,
            metric_name="complexity",
            detected_at=detected_at,
            confidence=0.8,
            severity=AlertSeverity.WARNING,
            description="Complexity dropped",
            actual_value=5.0,
            expected_value=10.0,
            deviation_sigma=2.0,
        )

        result = anomaly.to_dict()

        assert result["anomaly_type"] == "drop"
        assert result["metric_name"] == "complexity"
        assert result["confidence"] == 0.8
        assert result["severity"] == "warning"
        assert "detected_at" in result


@pytest.mark.unit
class TestQualityPatternDataClass:
    """Test QualityPattern dataclass."""

    def test_quality_pattern_creation(self) -> None:
        """Test QualityPattern dataclass creation."""
        detected_at = datetime.now(timezone.utc)
        pattern = QualityPattern(
            pattern_type=PatternType.CYCLIC,
            metric_names=["complexity", "test_coverage"],
            detected_at=detected_at,
            confidence=0.9,
            description="Complexity shows weekly cycle",
            period_days=7,
            correlation_strength=0.85,
            trend_direction=TrendDirection.IMPROVING,
            statistical_significance=0.95,
        )

        assert pattern.pattern_type == PatternType.CYCLIC
        assert pattern.metric_names == ["complexity", "test_coverage"]
        assert pattern.confidence == 0.9
        assert pattern.period_days == 7
        assert pattern.detected_at == detected_at
        assert pattern.correlation_strength == 0.85
        assert pattern.trend_direction == TrendDirection.IMPROVING
        assert pattern.statistical_significance == 0.95

    def test_quality_pattern_to_dict(self) -> None:
        """Test QualityPattern to_dict method."""
        detected_at = datetime.now(timezone.utc)
        pattern = QualityPattern(
            pattern_type=PatternType.SEASONAL,
            metric_names=["coverage"],
            detected_at=detected_at,
            confidence=0.85,
            description="Seasonal pattern",
            period_days=30,
            correlation_strength=0.75,
            trend_direction=TrendDirection.STABLE,
            statistical_significance=0.90,
        )

        result = pattern.to_dict()

        assert result["pattern_type"] == "seasonal"
        assert result["metric_names"] == ["coverage"]
        assert result["confidence"] == 0.85
        assert "detected_at" in result


@pytest.mark.unit
class TestQualityPredictionDataClass:
    """Test QualityPrediction dataclass."""

    def test_quality_prediction_creation(self) -> None:
        """Test QualityPrediction dataclass creation."""
        created_at = datetime.now(timezone.utc)
        prediction = QualityPrediction(
            metric_name="maintainability",
            predicted_value=70.0,
            confidence_lower=65.0,
            confidence_upper=75.0,
            confidence_level=0.95,
            prediction_horizon_days=7,
            prediction_method="linear_regression",
            created_at=created_at,
            factors=["complexity", "duplication"],
            risk_assessment="low",
        )

        assert prediction.metric_name == "maintainability"
        assert prediction.predicted_value == 70.0
        assert prediction.confidence_lower == 65.0
        assert prediction.confidence_upper == 75.0
        assert prediction.confidence_level == 0.95
        assert prediction.prediction_horizon_days == 7
        assert prediction.prediction_method == "linear_regression"
        assert prediction.created_at == created_at
        assert prediction.risk_assessment == "low"

    def test_quality_prediction_to_dict(self) -> None:
        """Test QualityPrediction to_dict method."""
        created_at = datetime.now(timezone.utc)
        prediction = QualityPrediction(
            metric_name="quality_score",
            predicted_value=80.0,
            confidence_lower=75.0,
            confidence_upper=85.0,
            confidence_level=0.99,
            prediction_horizon_days=14,
            prediction_method="polynomial_regression",
            created_at=created_at,
        )

        result = prediction.to_dict()

        assert result["metric_name"] == "quality_score"
        assert result["predicted_value"] == 80.0
        assert result["prediction_method"] == "polynomial_regression"
        assert "created_at" in result


@pytest.mark.unit
class TestQualityInsightsDataClass:
    """Test QualityInsights dataclass."""

    def test_quality_insights_creation(self) -> None:
        """Test QualityInsights dataclass creation."""
        detected_at = datetime.now(timezone.utc)
        created_at = datetime.now(timezone.utc)

        anomaly = QualityAnomaly(
            anomaly_type=AnomalyType.SPIKE,
            metric_name="test_coverage",
            detected_at=detected_at,
            confidence=0.9,
            severity=AlertSeverity.CRITICAL,
            description="Test coverage spiked",
            actual_value=75.0,
            expected_value=65.0,
            deviation_sigma=1.5,
        )
        pattern = QualityPattern(
            pattern_type=PatternType.CYCLIC,
            metric_names=["complexity"],
            detected_at=detected_at,
            confidence=0.9,
            description="Weekly cycle",
            period_days=7,
            correlation_strength=0.8,
            trend_direction=TrendDirection.STABLE,
            statistical_significance=0.95,
        )
        prediction = QualityPrediction(
            metric_name="maintainability",
            predicted_value=70.0,
            confidence_lower=65.0,
            confidence_upper=75.0,
            confidence_level=0.95,
            prediction_horizon_days=7,
            prediction_method="linear_regression",
            created_at=created_at,
        )

        insights = QualityInsights(
            anomalies=[anomaly],
            patterns=[pattern],
            predictions=[prediction],
            overall_health_score=0.75,
            risk_level="medium",
            recommendations=["Monitor test coverage closely"],
        )

        assert len(insights.anomalies) == 1
        assert len(insights.patterns) == 1
        assert len(insights.predictions) == 1
        assert insights.overall_health_score == 0.75
        assert insights.risk_level == "medium"
        assert insights.recommendations == ["Monitor test coverage closely"]

    def test_quality_insights_to_dict(self) -> None:
        """Test QualityInsights to_dict method."""
        insights = QualityInsights(
            anomalies=[],
            patterns=[],
            predictions=[],
            overall_health_score=0.8,
            risk_level="low",
            recommendations=["All good"],
        )

        result = insights.to_dict()

        assert result["overall_health_score"] == 0.8
        assert result["risk_level"] == "low"
        assert result["recommendations"] == ["All good"]
        assert "generated_at" in result


@pytest.mark.unit
class TestQualityIntelligenceServiceInitialization:
    """Test QualityIntelligenceService initialization."""

    def test_initialization(self) -> None:
        """Test service initialization with default parameters."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)

        service = QualityIntelligenceService(
            quality_service=mock_quality_service,
        )

        assert service.quality_service is mock_quality_service
        assert service.anomaly_sensitivity == 2.0
        assert service.min_data_points == 10

    def test_initialization_custom_params(self) -> None:
        """Test service initialization with custom parameters."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)

        service = QualityIntelligenceService(
            quality_service=mock_quality_service,
            anomaly_sensitivity=3.0,
            min_data_points=20,
        )

        assert service.anomaly_sensitivity == 3.0
        assert service.min_data_points == 20


@pytest.mark.unit
class TestAnomalyDetection:
    """Test anomaly detection methods."""

    def test_detect_anomalies_without_scipy(self) -> None:
        """Test detect_anomalies returns empty list when scipy unavailable."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)

        with patch("crackerjack.services.quality.quality_intelligence.SCIPY_AVAILABLE", False):
            service = QualityIntelligenceService(
                quality_service=mock_quality_service,
            )

            anomalies = service.detect_anomalies(days=30)

            assert anomalies == []

    def test_detect_anomalies_with_insufficient_data(self) -> None:
        """Test detect_anomalies returns empty with insufficient data points."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)
        mock_quality_service.get_recent_baselines.return_value = []

        service = QualityIntelligenceService(
            quality_service=mock_quality_service,
            min_data_points=10,
        )

        anomalies = service.detect_anomalies(days=30)

        assert anomalies == []
        mock_quality_service.get_recent_baselines.assert_called_once_with(limit=60)

    def test_detect_anomalies_async_without_scipy(self) -> None:
        """Test detect_anomalies_async returns empty when scipy unavailable."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)

        with patch("crackerjack.services.quality.quality_intelligence.SCIPY_AVAILABLE", False):
            service = QualityIntelligenceService(
                quality_service=mock_quality_service,
            )

            import asyncio

            async def test_async():
                anomalies = await service.detect_anomalies_async(days=30)
                return anomalies

            anomalies = asyncio.run(test_async())
            assert anomalies == []


@pytest.mark.unit
class TestPatternRecognition:
    """Test pattern recognition methods."""

    def test_identify_patterns_without_scipy(self) -> None:
        """Test identify_patterns returns empty list when scipy unavailable."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)

        with patch("crackerjack.services.quality.quality_intelligence.SCIPY_AVAILABLE", False):
            service = QualityIntelligenceService(
                quality_service=mock_quality_service,
            )

            patterns = service.identify_patterns(days=30)

            assert patterns == []

    def test_identify_patterns_with_insufficient_data(self) -> None:
        """Test identify_patterns returns empty with insufficient data."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)
        mock_quality_service.get_recent_baselines.return_value = []

        service = QualityIntelligenceService(
            quality_service=mock_quality_service,
            min_data_points=10,
        )

        patterns = service.identify_patterns(days=30)

        assert patterns == []


@pytest.mark.unit
class TestPredictionGeneration:
    """Test prediction generation methods."""

    def test_generate_advanced_predictions_without_scipy(self) -> None:
        """Test predictions return empty when scipy unavailable."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)

        with patch("crackerjack.services.quality.quality_intelligence.SCIPY_AVAILABLE", False):
            service = QualityIntelligenceService(
                quality_service=mock_quality_service,
            )

            predictions = service.generate_advanced_predictions(horizon_days=7)

            assert predictions == []

    def test_generate_advanced_predictions_with_insufficient_data(self) -> None:
        """Test predictions return empty with insufficient data."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)
        mock_quality_service.get_recent_baselines.return_value = []

        service = QualityIntelligenceService(
            quality_service=mock_quality_service,
            min_data_points=10,
        )

        predictions = service.generate_advanced_predictions(horizon_days=7)

        assert predictions == []


@pytest.mark.unit
class TestComprehensiveInsights:
    """Test comprehensive insights generation."""

    def test_generate_comprehensive_insights_without_scipy(self) -> None:
        """Test comprehensive insights work without scipy."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)
        mock_quality_service.get_recent_baselines.return_value = []

        with patch("crackerjack.services.quality.quality_intelligence.SCIPY_AVAILABLE", False):
            service = QualityIntelligenceService(
                quality_service=mock_quality_service,
            )

            insights = service.generate_comprehensive_insights(analysis_days=30)

            assert isinstance(insights, QualityInsights)
            assert insights.anomalies == []
            assert insights.patterns == []
            assert insights.predictions == []
            assert insights.overall_health_score >= 0.0
            assert insights.overall_health_score <= 1.0


@pytest.mark.unit
class TestDefaultMetrics:
    """Test default metrics configuration."""

    def test_get_default_metrics(self) -> None:
        """Test _get_default_metrics returns expected metrics."""
        mock_quality_service = Mock(spec=EnhancedQualityBaselineService)
        service = QualityIntelligenceService(
            quality_service=mock_quality_service,
        )

        metrics = service._get_default_metrics()

        # Should contain core quality metrics
        assert isinstance(metrics, list)
        assert len(metrics) > 0
        assert "quality_score" in metrics
        assert "coverage_percent" in metrics
