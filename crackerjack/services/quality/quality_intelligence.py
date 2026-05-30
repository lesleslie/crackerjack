from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .quality_baseline_enhanced import (
    AlertSeverity,
    EnhancedQualityBaselineService,
    TrendDirection,
)

try:  # pragma: no cover - optional dependency
    import scipy  # type: ignore # noqa: F401

    SCIPY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    SCIPY_AVAILABLE = False


class AnomalyType(StrEnum):
    SPIKE = "spike"
    DROP = "drop"
    DRIFT = "drift"
    OSCILLATION = "oscillation"
    OUTLIER = "outlier"


class PatternType(StrEnum):
    CYCLIC = "cyclic"
    SEASONAL = "seasonal"
    CORRELATION = "correlation"
    REGRESSION = "regression"
    IMPROVEMENT = "improvement"


def _serialize(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


@dataclass
class QualityAnomaly:
    anomaly_type: AnomalyType
    metric_name: str
    detected_at: datetime
    confidence: float
    severity: AlertSeverity
    description: str
    actual_value: float | None = None
    expected_value: float | None = None
    deviation_sigma: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            field: _serialize(getattr(self, field))
            for field in self.__dataclass_fields__  # type: ignore[attr-defined]
        }


@dataclass
class QualityPattern:
    pattern_type: PatternType
    metric_names: list[str]
    detected_at: datetime
    confidence: float
    description: str
    period_days: int | None = None
    correlation_strength: float | None = None
    trend_direction: TrendDirection | None = None
    statistical_significance: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            field: _serialize(getattr(self, field))
            for field in self.__dataclass_fields__  # type: ignore[attr-defined]
        }


@dataclass
class QualityPrediction:
    metric_name: str
    predicted_value: float
    confidence_lower: float
    confidence_upper: float
    confidence_level: float
    prediction_horizon_days: int
    prediction_method: str
    created_at: datetime
    factors: list[str] = field(default_factory=list)
    risk_assessment: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            field: _serialize(getattr(self, field))
            for field in self.__dataclass_fields__  # type: ignore[attr-defined]
        }


@dataclass
class QualityInsights:
    anomalies: list[QualityAnomaly]
    patterns: list[QualityPattern]
    predictions: list[QualityPrediction]
    overall_health_score: float
    risk_level: str
    recommendations: list[str]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))  # type: ignore

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomalies": [item.to_dict() for item in self.anomalies],
            "patterns": [item.to_dict() for item in self.patterns],
            "predictions": [item.to_dict() for item in self.predictions],
            "overall_health_score": self.overall_health_score,
            "risk_level": self.risk_level,
            "recommendations": self.recommendations.copy(),
            "generated_at": self.generated_at.isoformat(),
        }


class QualityIntelligenceService:
    def __init__(
        self,
        quality_service: EnhancedQualityBaselineService,
        anomaly_sensitivity: float = 2.0,
        min_data_points: int = 10,
    ) -> None:
        self.quality_service = quality_service
        self.anomaly_sensitivity = anomaly_sensitivity
        self.min_data_points = min_data_points

    def _get_recent_baselines(self, days: int) -> list[Any]:
        return list(self.quality_service.get_recent_baselines(limit=days * 2))

    def _has_enough_data(self, days: int) -> bool:
        return len(self._get_recent_baselines(days)) >= self.min_data_points

    def detect_anomalies(self, days: int = 30) -> list[QualityAnomaly]:
        if not SCIPY_AVAILABLE or not self._has_enough_data(days):
            return []
        return []

    async def detect_anomalies_async(self, days: int = 30) -> list[QualityAnomaly]:
        return self.detect_anomalies(days=days)

    def identify_patterns(self, days: int = 30) -> list[QualityPattern]:
        if not SCIPY_AVAILABLE or not self._has_enough_data(days):
            return []
        return []

    def generate_advanced_predictions(
        self, horizon_days: int = 7
    ) -> list[QualityPrediction]:
        if not SCIPY_AVAILABLE or not self._has_enough_data(horizon_days):
            return []
        return []

    def generate_comprehensive_insights(
        self, analysis_days: int = 30
    ) -> QualityInsights:
        anomalies = self.detect_anomalies(days=analysis_days)
        patterns = self.identify_patterns(days=analysis_days)
        predictions = self.generate_advanced_predictions(
            horizon_days=max(1, analysis_days // 4)
        )
        overall_health_score = (
            1.0 if not self._get_recent_baselines(analysis_days) else 0.75
        )
        return QualityInsights(
            anomalies=anomalies,
            patterns=patterns,
            predictions=predictions,
            overall_health_score=overall_health_score,
            risk_level="low" if overall_health_score >= 0.75 else "medium",
            recommendations=[],
        )

    def _get_default_metrics(self) -> list[str]:
        return [
            "quality_score",
            "coverage_percent",
            "complexity_score",
            "maintainability_index",
            "duplication_percent",
        ]
