from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from oneiric.core.logging import get_logger

if TYPE_CHECKING:
    from crackerjack.services.failure_metrics_repository import FailureMetricsRepository
    from crackerjack.services.failure_recorder import FailureRecorder

logger = get_logger(__name__)

MIN_FAILURES_BEFORE_IMPROVEMENT: int = 3
MAX_IMPROVEMENTS_PER_DAY: int = 5


@dataclass
class ImprovementProposal:
    improvement_id: str
    improvement_type: str  # "prompt" | "config" | "strategy_code"
    diff: str
    rationale: str
    confidence: float
    expected_improvement: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_auto_apply_candidate(self) -> bool:
        return self.improvement_type in ("prompt", "config")


class ImprovementGenerator:
    """Generates Crackerjack self-improvement proposals from accumulated failure patterns.

    Injects FailureMetricsRepository — never bare DharaMCPClient (C-NEW-19).
    Optionally accepts FailureRecorder for Akosha trend-based early triggering (Task 17b).
    Returns immediately with a job-id dict; generation is fire-and-forget (C-NEW-5).
    """

    def __init__(
        self,
        repository: FailureMetricsRepository,
        recorder: FailureRecorder | None = None,
        min_failures: int = MIN_FAILURES_BEFORE_IMPROVEMENT,
        max_per_day: int = MAX_IMPROVEMENTS_PER_DAY,
    ) -> None:
        self._repo = repository
        self._recorder = recorder
        self._min_failures = min_failures
        self._max_per_day = max_per_day
        # In-process counter; production should persist to Dhara (M-NEW-4)
        self._daily_count: int = 0
        self._today: str = datetime.now(UTC).date().isoformat()

    def _reset_daily_count_if_new_day(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        if today != self._today:
            self._today = today
            self._daily_count = 0

    async def maybe_generate(self, fingerprint: str) -> dict[str, Any] | None:
        """Check noise gate and rate limit; return job-id dict or None.

        Noise gate (Task 17b upgrade):
        - Normal: count ≥ min_failures
        - Early trigger: count ≥ 1 AND Akosha reports abrupt downward trend
        On Akosha timeout/unavailable: fall back to count-only gate (M-NEW-30).
        """
        self._reset_daily_count_if_new_day()

        count = 0
        with suppress(Exception):
            count = await self._repo.count_similar(fingerprint)

        # Optional trend-based early trigger (M-NEW-30) — Akosha call with 5s timeout
        trend = None
        if self._recorder is not None:
            with suppress(Exception):
                trend = await asyncio.wait_for(
                    self._recorder.classify_failure_trend(fingerprint),
                    timeout=5.0,
                )

        abrupt_early_trigger = (
            count >= 1
            and trend is not None
            and trend.has_abrupt_trend
            and trend.latest_direction == "down"
        )

        if count < self._min_failures and not abrupt_early_trigger:
            return None

        if self._daily_count >= self._max_per_day:
            logger.warning(
                "ImprovementGenerator: daily rate limit reached (%d/%d)",
                self._daily_count,
                self._max_per_day,
            )
            return None

        self._daily_count += 1

        from uuid_utils import uuid4  # type: ignore[import-not-found]
        job_id = str(uuid4())

        priority = "high" if (trend is not None and trend.has_abrupt_trend) else "normal"

        logger.info(
            "ImprovementGenerator: triggered fingerprint=%s job_id=%s priority=%s",
            fingerprint,
            job_id,
            priority,
        )
        return {"improvement_job_id": job_id, "status": "generating", "priority": priority}

    def _build_generation_prompt(
        self,
        failure_context: str,
        current_impl: str,
    ) -> str:
        from crackerjack.services.constitution import load_constitution

        constitution = load_constitution()
        return (
            f"{constitution}\n\n"
            "=== Failure Context ===\n"
            f"{failure_context}\n\n"
            "=== Current Implementation ===\n"
            f"{current_impl}\n\n"
            "Generate an improvement proposal as a unified diff."
        )
