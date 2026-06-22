"""Tests for Task 17b noise gate upgrade and download trend classification."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestFailureRecorderTrendClassification:
    """classify_failure_trend() on FailureRecorder."""

    async def test_classify_failure_trend_returns_none_when_no_akosha(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.failure_recorder import FailureRecorder

        repo = MagicMock(spec=FailureMetricsRepository)
        recorder = FailureRecorder(repository=repo, akosha_mcp_client=None)
        result = await recorder.classify_failure_trend("abc123")
        assert result is None

    async def test_classify_failure_trend_parses_akosha_response(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.failure_recorder import FailureRecorder, TrendClassification

        akosha = AsyncMock()
        akosha.analyze_changepoints.return_value = {
            "has_abrupt_trend": True,
            "latest_segment": {"direction": "down", "change_rank": 1},
            "segments": [{"direction": "flat"}, {"direction": "down"}],
        }

        repo = MagicMock(spec=FailureMetricsRepository)
        recorder = FailureRecorder(repository=repo, akosha_mcp_client=akosha)
        result = await recorder.classify_failure_trend("abc123")

        assert isinstance(result, TrendClassification)
        assert result.has_abrupt_trend is True
        assert result.latest_direction == "down"
        assert result.segment_count == 2

    async def test_classify_failure_trend_returns_none_on_akosha_error(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.failure_recorder import FailureRecorder

        akosha = AsyncMock()
        akosha.analyze_changepoints.side_effect = Exception("akosha down")

        repo = MagicMock(spec=FailureMetricsRepository)
        recorder = FailureRecorder(repository=repo, akosha_mcp_client=akosha)
        result = await recorder.classify_failure_trend("abc123")
        assert result is None

    async def test_noise_gate_falls_back_to_count_when_akosha_unavailable(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.failure_recorder import FailureRecorder
        from crackerjack.services.improvement_generator import ImprovementGenerator

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = 3  # ≥ threshold

        recorder = FailureRecorder(repository=repo, akosha_mcp_client=None)
        generator = ImprovementGenerator(repository=repo, recorder=recorder)

        result = await generator.maybe_generate("abc123")
        # Count-only gate triggers even without trend data
        assert result is not None
        assert result.get("improvement_job_id") is not None


class TestImprovementGeneratorAbruptTrendEarlyTrigger:
    """Noise gate upgrade: abrupt downward trend triggers at count=1."""

    async def test_noise_gate_triggers_early_on_abrupt_failure_trend(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.failure_recorder import FailureRecorder, TrendClassification
        from crackerjack.services.improvement_generator import ImprovementGenerator

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = 1  # below normal threshold (3)

        recorder = MagicMock(spec=FailureRecorder)
        recorder.classify_failure_trend = AsyncMock(
            return_value=TrendClassification(
                has_abrupt_trend=True,
                latest_direction="down",
                largest_change_rank=1,
                segment_count=2,
            )
        )

        generator = ImprovementGenerator(repository=repo, recorder=recorder, min_failures=3)
        result = await generator.maybe_generate("abc123")

        assert result is not None
        assert result.get("priority") == "high"

    async def test_noise_gate_triggers_on_count_threshold_without_trend_data(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.improvement_generator import ImprovementGenerator

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = 3  # meets threshold

        generator = ImprovementGenerator(repository=repo, recorder=None, min_failures=3)
        result = await generator.maybe_generate("abc123")

        assert result is not None
        assert result.get("priority") == "normal"

    async def test_noise_gate_does_not_trigger_on_single_isolated_failure_without_trend(
        self,
    ) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.improvement_generator import ImprovementGenerator

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = 1  # below threshold

        generator = ImprovementGenerator(repository=repo, recorder=None, min_failures=3)
        result = await generator.maybe_generate("abc123")

        assert result is None

    async def test_noise_gate_no_early_trigger_when_trend_not_abrupt(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.failure_recorder import FailureRecorder, TrendClassification
        from crackerjack.services.improvement_generator import ImprovementGenerator

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = 1  # below threshold

        recorder = MagicMock(spec=FailureRecorder)
        recorder.classify_failure_trend = AsyncMock(
            return_value=TrendClassification(
                has_abrupt_trend=False,  # gradual trend, not abrupt
                latest_direction="down",
                largest_change_rank=2,
                segment_count=1,
            )
        )

        generator = ImprovementGenerator(repository=repo, recorder=recorder, min_failures=3)
        result = await generator.maybe_generate("abc123")

        # No early trigger: trend not abrupt AND count below threshold
        assert result is None


class TestDownloadTrendClassification:
    """DownloadTrendClass from PypiStatsService.classify_download_trend()."""

    def test_cliff_drop_classifies_as_abrupt_drop(self) -> None:
        from crackerjack.services.pypistats_service import (
            DownloadTrendClass,
            PackageStatsSnapshot,
            PypiStatsService,
        )
        from datetime import datetime, timezone

        snapshot = PackageStatsSnapshot(
            package="crackerjack",
            downloads_7d=500,
            downloads_30d=2500,
            downloads_7d_prev=1000,  # 50% drop → abrupt
            has_download_drop=True,
            publish_timestamp=datetime.now(tz=timezone.utc),
        )
        svc = PypiStatsService()
        assert svc.classify_download_trend(snapshot) == DownloadTrendClass.ABRUPT_DROP

    def test_slow_decline_classifies_as_gradual_decay(self) -> None:
        from crackerjack.services.pypistats_service import (
            DownloadTrendClass,
            PackageStatsSnapshot,
            PypiStatsService,
        )
        from datetime import datetime, timezone

        snapshot = PackageStatsSnapshot(
            package="crackerjack",
            downloads_7d=700,
            downloads_30d=2800,
            downloads_7d_prev=800,  # 12.5% drop → below 50%, gradual
            has_download_drop=True,
            publish_timestamp=datetime.now(tz=timezone.utc),
        )
        svc = PypiStatsService()
        assert svc.classify_download_trend(snapshot) == DownloadTrendClass.GRADUAL_DECAY

    def test_stable_downloads_produce_no_warning(self) -> None:
        from crackerjack.services.pypistats_service import (
            DownloadTrendClass,
            PackageStatsSnapshot,
            PypiStatsService,
        )
        from datetime import datetime, timezone

        snapshot = PackageStatsSnapshot(
            package="crackerjack",
            downloads_7d=1000,
            downloads_30d=4000,
            downloads_7d_prev=1000,
            has_download_drop=False,
            publish_timestamp=datetime.now(tz=timezone.utc),
        )
        svc = PypiStatsService()
        assert svc.classify_download_trend(snapshot) == DownloadTrendClass.STABLE

    def test_download_trend_warning_text_abrupt_drop(self) -> None:
        from crackerjack.services.pypistats_service import DownloadTrendClass
        from crackerjack.managers.publish_manager import get_download_trend_warning

        text = get_download_trend_warning(DownloadTrendClass.ABRUPT_DROP)
        assert "breaking change" in text.lower() or "sharp" in text.lower()

    def test_download_trend_warning_text_gradual_decay(self) -> None:
        from crackerjack.services.pypistats_service import DownloadTrendClass
        from crackerjack.managers.publish_manager import get_download_trend_warning

        text = get_download_trend_warning(DownloadTrendClass.GRADUAL_DECAY)
        assert "gradual" in text.lower() or "decline" in text.lower()

    def test_download_trend_no_warning_when_stable(self) -> None:
        from crackerjack.services.pypistats_service import DownloadTrendClass
        from crackerjack.managers.publish_manager import get_download_trend_warning

        text = get_download_trend_warning(DownloadTrendClass.STABLE)
        assert text == ""
