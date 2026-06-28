from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from oneiric.core.logging import get_logger

if TYPE_CHECKING:
    from crackerjack.integration.dhara_mcp_client import DharaMCPClient
    from crackerjack.services.failure_recorder import FixAttemptRecord

logger = get_logger(__name__)

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*(Human|Assistant|System)\s*:", re.MULTILINE),
    re.compile(
        r"<(system|instruction|prompt)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
    ),
]

_MAX_FIELD_LEN = 2000


def _sanitize_record(record: dict[str, Any]) -> dict[str, Any]:
    sanitized = record.copy()
    for key in ("issue_description", "fix_code_generated", "failure_reason"):
        val = sanitized.get(key)
        if isinstance(val, str):
            for pat in _INJECTION_PATTERNS:
                val = pat.sub("", val)
            sanitized[key] = val[:_MAX_FIELD_LEN]
    return sanitized


class FailureMetricsRepository:
    """Single read/write interface for fix-failure time-series data in Dhara.

    FailureRecorder (write) and ImprovementGenerator (read) both inject this — never
    bare DharaMCPClient.
    """

    def __init__(self, client: DharaMCPClient) -> None:
        self._client = client

    async def record(self, rec: FixAttemptRecord) -> None:
        connected = await self._client.connect()
        if not connected:
            logger.warning(
                "FailureMetricsRepository.record: Dhara unavailable, skipping"
            )
            return
        try:
            await self._client.put(
                f"fix-failures/{rec.record_id}",
                rec.to_dict(),
            )
            await self._client.record_time_series(
                metric_type="fix-failures",
                entity_id=rec.issue_fingerprint,
                record={
                    "fingerprint": rec.issue_fingerprint,
                    "hook": rec.hook,
                    "repo": rec.repo,
                    "issue_type": rec.issue_type,
                    "timestamp": rec.timestamp.isoformat(),
                },
                timestamp=rec.timestamp.isoformat(),
            )
        except Exception:
            logger.exception("FailureMetricsRepository.record failed")

    async def count_similar(self, fingerprint: str) -> int:
        connected = await self._client.connect()
        if not connected:
            return 0
        try:
            records = await self._client.query_time_series(
                metric_type="fix-failures",
                entity_id=fingerprint,
            )
            return len(records)
        except Exception:
            logger.exception("FailureMetricsRepository.count_similar failed")
            return 0

    async def query_by_fingerprint(
        self,
        fingerprint: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        connected = await self._client.connect()
        if not connected:
            return []
        try:
            records = await self._client.query_time_series(
                metric_type="fix-failures",
                entity_id=fingerprint,
                start_date=start.date().isoformat(),
            )
            cutoff = end.replace(tzinfo=UTC) if end.tzinfo is None else end
            filtered = []
            for r in records:
                ts_str = r.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str).replace(tzinfo=UTC)
                    if ts <= cutoff:
                        filtered.append(_sanitize_record(r))
                except (ValueError, TypeError):
                    filtered.append(_sanitize_record(r))
            return filtered
        except Exception:
            logger.exception("FailureMetricsRepository.query_by_fingerprint failed")
            return []
