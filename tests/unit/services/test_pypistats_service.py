from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestPypiStatsServiceSnapshot:
    """PypiStatsService must fetch and structure 7d/30d download data."""

    def test_service_returns_snapshot_with_7d_and_30d_counts(self) -> None:
        """Happy path: recent() returns JSON → snapshot has correct counts."""
        from crackerjack.services.pypistats_service import PypiStatsService

        mock_response = json.dumps(
            {
                "data": {"last_day": 50, "last_week": 892, "last_month": 3421},
                "package": "crackerjack",
                "type": "recent_downloads",
            }
        )

        with patch("pypistats.recent", return_value=mock_response):
            service = PypiStatsService()
            snapshot = service.get_snapshot("crackerjack")

        assert snapshot is not None
        assert snapshot.downloads_7d == 892
        assert snapshot.downloads_30d == 3421
        assert snapshot.package == "crackerjack"

    def test_service_computes_prev_7d_as_prior_weekly_average(self) -> None:
        """downloads_7d_prev is the average weekly rate of prior 3 weeks."""
        from crackerjack.services.pypistats_service import PypiStatsService

        # 30d = 4000, 7d = 1000 → prior 3 weeks = 3000 → weekly avg = 1000
        mock_response = json.dumps(
            {
                "data": {"last_day": 0, "last_week": 1000, "last_month": 4000},
                "package": "crackerjack",
                "type": "recent_downloads",
            }
        )

        with patch("pypistats.recent", return_value=mock_response):
            service = PypiStatsService()
            snapshot = service.get_snapshot("crackerjack")

        assert snapshot is not None
        assert snapshot.downloads_7d_prev == 1000  # (4000 - 1000) / 3

    def test_service_detects_download_drop_above_threshold(self) -> None:
        """has_download_drop=True when 7d drops >30% vs prior weekly average."""
        from crackerjack.services.pypistats_service import PypiStatsService

        # Prior avg = (3000 - 500) / 3 ≈ 833 per week; current 500 → ~40% drop
        mock_response = json.dumps(
            {
                "data": {"last_day": 0, "last_week": 500, "last_month": 3000},
                "package": "crackerjack",
                "type": "recent_downloads",
            }
        )

        with patch("pypistats.recent", return_value=mock_response):
            service = PypiStatsService(drop_warn_threshold=0.30)
            snapshot = service.get_snapshot("crackerjack")

        assert snapshot is not None
        assert snapshot.has_download_drop is True

    def test_service_no_drop_flag_when_downloads_stable(self) -> None:
        """has_download_drop=False when 7d is within threshold of prior average."""
        from crackerjack.services.pypistats_service import PypiStatsService

        # Prior avg = (4000 - 1100) / 3 ≈ 967; current 1100 → no drop
        mock_response = json.dumps(
            {
                "data": {"last_day": 0, "last_week": 1100, "last_month": 4000},
                "package": "crackerjack",
                "type": "recent_downloads",
            }
        )

        with patch("pypistats.recent", return_value=mock_response):
            service = PypiStatsService(drop_warn_threshold=0.30)
            snapshot = service.get_snapshot("crackerjack")

        assert snapshot is not None
        assert snapshot.has_download_drop is False


@pytest.mark.unit
class TestPypiStatsServiceErrorHandling:
    """PypiStatsService must degrade gracefully on all error paths."""

    def test_service_returns_none_on_api_timeout(self) -> None:
        """Timeout from network → None snapshot, no exception propagated."""
        import requests

        from crackerjack.services.pypistats_service import PypiStatsService

        with patch("pypistats.recent", side_effect=requests.Timeout("timeout")):
            service = PypiStatsService()
            snapshot = service.get_snapshot("crackerjack")

        assert snapshot is None

    def test_service_returns_empty_snapshot_when_package_not_found_on_pypi(
        self,
    ) -> None:
        """404 / package not found → None snapshot, no crash."""
        from crackerjack.services.pypistats_service import PypiStatsService

        with patch("pypistats.recent", side_effect=Exception("404 Not Found")):
            service = PypiStatsService()
            snapshot = service.get_snapshot("nonexistent-package-xyz")

        assert snapshot is None

    def test_service_skips_panel_when_rate_limited(self) -> None:
        """429 rate limit from PyPI Stats API → None snapshot, no panel shown."""
        from crackerjack.services.pypistats_service import PypiStatsService

        with patch("pypistats.recent", side_effect=Exception("429 Too Many Requests")):
            service = PypiStatsService()
            snapshot = service.get_snapshot("crackerjack")

        assert snapshot is None

    def test_service_handles_malformed_json_gracefully(self) -> None:
        """Unexpected JSON shape → None, no KeyError propagated."""
        from crackerjack.services.pypistats_service import PypiStatsService

        with patch("pypistats.recent", return_value='{"unexpected": "shape"}'):
            service = PypiStatsService()
            snapshot = service.get_snapshot("crackerjack")

        assert snapshot is None


@pytest.mark.unit
class TestPypiStatsServiceDharaStore:
    """After publish, snapshot should be offered to Dhara for storage."""

    async def test_service_stores_snapshot_to_dhara_on_publish(self) -> None:
        """store_snapshot() passes key structured data to dhara.put_async()."""
        from crackerjack.services.pypistats_service import (
            PackageStatsSnapshot,
            PypiStatsService,
        )
        from datetime import datetime, timezone

        mock_dhara = AsyncMock()
        mock_dhara.put_async = AsyncMock(return_value=None)

        service = PypiStatsService(dhara=mock_dhara)
        snapshot = PackageStatsSnapshot(
            package="crackerjack",
            downloads_7d=892,
            downloads_30d=3421,
            downloads_7d_prev=843,
            has_download_drop=False,
            publish_timestamp=datetime.now(tz=timezone.utc),
        )

        await service.store_snapshot(snapshot, version="0.65.12")

        mock_dhara.put_async.assert_called_once()
        call_args = mock_dhara.put_async.call_args
        key = call_args[0][0]
        record = call_args[0][1]
        assert "pypistats-snapshots" in key
        assert record["downloads_7d"] == 892
        assert record["downloads_30d"] == 3421
        assert record["version"] == "0.65.12"

    async def test_service_skips_dhara_when_no_client_configured(self) -> None:
        """store_snapshot() with no dhara client is a no-op, never raises."""
        from crackerjack.services.pypistats_service import (
            PackageStatsSnapshot,
            PypiStatsService,
        )
        from datetime import datetime, timezone

        service = PypiStatsService()  # no dhara
        snapshot = PackageStatsSnapshot(
            package="crackerjack",
            downloads_7d=892,
            downloads_30d=3421,
            downloads_7d_prev=843,
            has_download_drop=False,
            publish_timestamp=datetime.now(tz=timezone.utc),
        )

        # Must not raise
        await service.store_snapshot(snapshot, version="0.65.12")
