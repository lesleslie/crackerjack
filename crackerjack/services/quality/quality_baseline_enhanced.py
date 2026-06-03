from __future__ import annotations

from enum import StrEnum


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EnhancedQualityBaselineService:
    def get_recent_baselines(self, limit: int = 60): # pragma: no cover - stub
        return []
