from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from oneiric.core.logging import get_logger

if TYPE_CHECKING:
    from crackerjack.services.failure_recorder import FixAttemptRecord

logger = get_logger(__name__)


class FailureMetricsRepository:
    """Failure metrics store.

    .. deprecated::
        The remote KV / time-series store this class used to write to was
        decommissioned 2026-09-20; this class is now a silent no-op
        wrapper kept so existing call sites (failure_recorder,
        improvement_generator) continue to import. All methods return
        safe defaults and log a debug message.
    """

    async def record(self, rec: FixAttemptRecord) -> None:
        logger.debug(
            "FailureMetricsRepository.record: metrics store unavailable, skipping"
        )

    async def count_similar(self, fingerprint: str) -> int:
        logger.debug(
            "FailureMetricsRepository.count_similar: metrics store unavailable, "
            "returning 0"
        )
        return 0

    async def query_by_fingerprint(
        self,
        fingerprint: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        logger.debug(
            "FailureMetricsRepository.query_by_fingerprint: metrics store "
            "unavailable, returning no records"
        )
        return []
