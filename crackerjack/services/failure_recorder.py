from __future__ import annotations

import asyncio
import hashlib
import re
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from oneiric.core.logging import get_logger

if TYPE_CHECKING:
    from crackerjack.services.failure_metrics_repository import FailureMetricsRepository

logger = get_logger(__name__)

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*(Human|Assistant|System)\s*:", re.MULTILINE),
    re.compile(
        r"<(system|instruction|prompt)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
    ),
]

_FILE_PATH_PATTERN = re.compile(r"\b[\w./\\-]+\.(py|js|ts|go|rs|java|rb)\b(:\d+)?")


def _sanitize_field(text: str, max_len: int = 2000) -> str:
    for pat in _INJECTION_PATTERNS:
        text = pat.sub("", text)
    return text[:max_len]


def _compute_fingerprint(hook: str, issue_type: str, error_pattern: str) -> str:
    normalized = _FILE_PATH_PATTERN.sub("<file>", error_pattern)
    payload = f"{hook}::{issue_type}::{normalized}"
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class FixAttemptRecord:
    record_id: str
    run_id: str
    fix_task_id: str
    repo: str
    hook: str
    issue_type: str
    issue_fingerprint: str
    issue_description: str
    strategies_attempted: list[str]
    fix_code_generated: str
    failure_reason: str
    iterations_used: int
    confidence_scores: list[float]
    crackerjack_version: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "fix_task_id": self.fix_task_id,
            "repo": self.repo,
            "hook": self.hook,
            "issue_type": self.issue_type,
            "issue_fingerprint": self.issue_fingerprint,
            "issue_description": self.issue_description,
            "strategies_attempted": self.strategies_attempted,
            "fix_code_generated": self.fix_code_generated,
            "failure_reason": self.failure_reason,
            "iterations_used": self.iterations_used,
            "confidence_scores": self.confidence_scores,
            "crackerjack_version": self.crackerjack_version,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TrendClassification:
    has_abrupt_trend: bool
    latest_direction: str  # "up" | "down" | "flat"
    largest_change_rank: int
    segment_count: int


class _SessionBuddyProtocol(Protocol):
    async def store_reflection(self, content: str, *, tags: list[str]) -> None: ...


class FailureRecorder:
    def __init__(
        self,
        repository: FailureMetricsRepository,
        session_buddy: _SessionBuddyProtocol | None = None,
        akosha_mcp_client: Any | None = None,
    ) -> None:
        self._repo = repository
        self._sb = session_buddy
        self._akosha = akosha_mcp_client

    async def record(self, rec: FixAttemptRecord) -> None:
        # Sanitize before any write (C-NEW-17: defense-in-depth)
        clean_desc = _sanitize_field(rec.issue_description)
        clean_code = _sanitize_field(rec.fix_code_generated, max_len=2000)
        clean_reason = _sanitize_field(rec.failure_reason)

        with suppress(Exception):
            await self._repo.record(rec)

        if self._sb is not None:
            content = (
                f"Fix exhausted: {clean_desc}\n"
                f"Hook: {rec.hook} | Type: {rec.issue_type} | Repo: {rec.repo}\n"
                f"Code generated: {clean_code[:200]}\n"
                f"Failure: {clean_reason[:200]}"
            )
            with suppress(Exception):
                await self._sb.store_reflection(
                    content,
                    tags=["fix-failure", rec.hook, rec.repo],
                )

    async def count_similar(self, fingerprint: str) -> int:
        try:
            return await self._repo.count_similar(fingerprint)
        except Exception:
            logger.exception("FailureRecorder.count_similar failed")
            return 0

    async def classify_failure_trend(
        self, fingerprint: str
    ) -> TrendClassification | None:
        """Query Akosha changepoint analysis for the given failure fingerprint.

        Called from ImprovementGenerator.maybe_generate() (M-NEW-30).
        Never called from FailureRecorder.record() — must not block recording path.
        Returns None when Akosha is unavailable.
        """
        if self._akosha is None:
            return None
        try:
            result = await asyncio.wait_for(
                self._akosha.analyze_changepoints(
                    metric_name="fix-failures",
                    system_id=fingerprint,
                    time_window_days=30,
                ),
                timeout=5.0,
            )
            if result is None or "error" in result:
                return None
            latest = result.get("latest_segment", {})
            return TrendClassification(
                has_abrupt_trend=bool(result.get("has_abrupt_trend", False)),
                latest_direction=str(latest.get("direction", "flat")),
                largest_change_rank=int(latest.get("change_rank", 0)),
                segment_count=len(result.get("segments", [])),
            )
        except Exception:
            logger.warning(
                "classify_failure_trend: Akosha unavailable for %s", fingerprint
            )
            return None
