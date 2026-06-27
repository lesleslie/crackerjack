from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DownloadTrendClass(StrEnum):
    """Classification of download trend shape for publish panel display."""

    ABRUPT_DROP = "abrupt_drop"
    GRADUAL_DECAY = "gradual_decay"
    STABLE = "stable"


@dataclass
class PackageStatsSnapshot:
    package: str
    downloads_7d: int
    downloads_30d: int
    downloads_7d_prev: int  # weekly avg of prior 3 weeks: (30d - 7d) // 3
    has_download_drop: bool
    publish_timestamp: datetime | None = None


class PypiStatsService:
    def __init__(
        self,
        drop_warn_threshold: float = 0.30,
        dhara: Any | None = None,
    ) -> None:
        self._threshold = drop_warn_threshold
        self._dhara = dhara

    def get_snapshot(self, package: str) -> PackageStatsSnapshot | None:
        try:
            import pypistats

            raw = pypistats.recent(package)
            data = json.loads(raw)
            counts = data["data"]
            downloads_7d = int(counts["last_week"])
            downloads_30d = int(counts["last_month"])
        except Exception as e:
            logger.warning("pypistats fetch failed for %s: %s", package, e)
            return None

        downloads_7d_prev = (downloads_30d - downloads_7d) // 3

        has_drop = downloads_7d_prev > 0 and downloads_7d < downloads_7d_prev * (
            1.0 - self._threshold
        )

        return PackageStatsSnapshot(
            package=package,
            downloads_7d=downloads_7d,
            downloads_30d=downloads_30d,
            downloads_7d_prev=downloads_7d_prev,
            has_download_drop=has_drop,
            publish_timestamp=datetime.now(tz=UTC),
        )

    def classify_download_trend(
        self, snapshot: PackageStatsSnapshot
    ) -> DownloadTrendClass:
        """Classify the download trend shape for publish panel display.

        Uses a heuristic: drop ≥ 50% vs prior period = abrupt; lower = gradual.
        Optional Akosha `analyze_changepoints` integration can be added for
        production-grade segment analysis (requires historical time-series).
        """
        if not snapshot.has_download_drop:
            return DownloadTrendClass.STABLE

        if snapshot.downloads_7d_prev > 0:
            drop_ratio = (
                snapshot.downloads_7d_prev - snapshot.downloads_7d
            ) / snapshot.downloads_7d_prev
            if drop_ratio >= 0.50:
                return DownloadTrendClass.ABRUPT_DROP

        return DownloadTrendClass.GRADUAL_DECAY

    async def store_snapshot(
        self,
        snapshot: PackageStatsSnapshot,
        version: str,
    ) -> None:
        if self._dhara is None:
            return
        try:
            key = f"pypistats-snapshots/{snapshot.package}/{version}"
            record: dict[str, Any] = {
                "package": snapshot.package,
                "version": version,
                "downloads_7d": snapshot.downloads_7d,
                "downloads_30d": snapshot.downloads_30d,
                "downloads_7d_prev": snapshot.downloads_7d_prev,
                "has_download_drop": snapshot.has_download_drop,
                "publish_timestamp": (
                    snapshot.publish_timestamp.isoformat()
                    if snapshot.publish_timestamp
                    else None
                ),
            }
            await self._dhara.put_async(key, record)
        except Exception as e:
            logger.warning("Failed to store pypistats snapshot to Dhara: %s", e)
