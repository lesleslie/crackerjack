from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.services.failure_recorder import FixAttemptRecord, _compute_fingerprint


def _make_record(**overrides: object) -> FixAttemptRecord:
    defaults: dict[str, object] = {
        "record_id": "rec-001",
        "run_id": "2026-06-21-1200-a1b2",
        "fix_task_id": "fix-0001",
        "repo": "crackerjack",
        "hook": "ruff",
        "issue_type": "E501",
        "issue_fingerprint": _compute_fingerprint("ruff", "E501", "Line too long"),
        "issue_description": "Line too long",
        "strategies_attempted": ["autofix"],
        "fix_code_generated": "x = 1",
        "failure_reason": "still failing after 3 iterations",
        "iterations_used": 3,
        "confidence_scores": [0.7, 0.6, 0.5],
        "crackerjack_version": "0.8.0",
        "timestamp": datetime.now(UTC),
    }
    defaults.update(overrides)
    return FixAttemptRecord(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestImprovementGeneratorNoiseGate:
    async def test_generator_skips_when_below_noise_gate(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.improvement_generator import ImprovementGenerator

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = 2  # below threshold of 3

        gen = ImprovementGenerator(repository=repo)
        result = await gen.maybe_generate(fingerprint="fp-abc")

        assert result is None
        repo.count_similar.assert_called_once_with("fp-abc")

    async def test_generator_triggers_when_ge_3_similar_failures(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.improvement_generator import ImprovementGenerator

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = 3  # at threshold

        gen = ImprovementGenerator(repository=repo)
        # generator triggers; returns job-id dict immediately (async, fire-and-forget generation)
        result = await gen.maybe_generate(fingerprint="fp-abc")

        assert result is not None
        assert "improvement_job_id" in result
        assert result["status"] == "generating"

    async def test_generator_returns_none_below_threshold_exact(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.improvement_generator import (
            ImprovementGenerator,
            MIN_FAILURES_BEFORE_IMPROVEMENT,
        )

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = MIN_FAILURES_BEFORE_IMPROVEMENT - 1

        gen = ImprovementGenerator(repository=repo)
        result = await gen.maybe_generate(fingerprint="fp-abc")

        assert result is None

    async def test_generator_fire_and_forget_survives_dhara_unavailable(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.improvement_generator import ImprovementGenerator

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.side_effect = ConnectionError("Dhara down")

        gen = ImprovementGenerator(repository=repo)
        # Must not raise even when Dhara is unavailable
        result = await gen.maybe_generate(fingerprint="fp-abc")
        assert result is None


@pytest.mark.unit
class TestImprovementGeneratorRateLimit:
    async def test_generator_respects_max_per_day_limit(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.improvement_generator import (
            ImprovementGenerator,
            MAX_IMPROVEMENTS_PER_DAY,
        )

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = 5  # above noise gate

        gen = ImprovementGenerator(repository=repo)
        # Inject daily counter above max
        gen._daily_count = MAX_IMPROVEMENTS_PER_DAY

        result = await gen.maybe_generate(fingerprint="fp-abc")
        assert result is None  # rate-limited

    async def test_generator_allows_when_under_daily_limit(self) -> None:
        from crackerjack.services.failure_metrics_repository import (
            FailureMetricsRepository,
        )
        from crackerjack.services.improvement_generator import (
            ImprovementGenerator,
            MAX_IMPROVEMENTS_PER_DAY,
        )

        repo = AsyncMock(spec=FailureMetricsRepository)
        repo.count_similar.return_value = 5

        gen = ImprovementGenerator(repository=repo)
        gen._daily_count = MAX_IMPROVEMENTS_PER_DAY - 1  # one slot remaining

        result = await gen.maybe_generate(fingerprint="fp-abc")
        assert result is not None
        assert result["status"] == "generating"


@pytest.mark.unit
class TestImprovementProposal:
    def test_proposal_has_required_fields(self) -> None:
        from crackerjack.services.improvement_generator import ImprovementProposal

        proposal = ImprovementProposal(
            improvement_id="imp-001",
            improvement_type="prompt",
            diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            rationale="Fixes prompt injection pattern",
            confidence=0.85,
            expected_improvement="Reduce E501 failures by 40%",
        )

        assert proposal.improvement_id == "imp-001"
        assert proposal.improvement_type in ("prompt", "config", "strategy_code")
        assert proposal.confidence >= 0.0
        assert proposal.diff

    def test_proposal_is_auto_apply_for_prompt_type(self) -> None:
        from crackerjack.services.improvement_generator import ImprovementProposal

        proposal = ImprovementProposal(
            improvement_id="imp-002",
            improvement_type="prompt",
            diff="--- diff ---",
            rationale="prompt tweak",
            confidence=0.9,
            expected_improvement="better",
        )
        assert proposal.is_auto_apply_candidate

    def test_proposal_is_not_auto_apply_for_strategy_code(self) -> None:
        from crackerjack.services.improvement_generator import ImprovementProposal

        proposal = ImprovementProposal(
            improvement_id="imp-003",
            improvement_type="strategy_code",
            diff="--- diff ---",
            rationale="new agent strategy",
            confidence=0.9,
            expected_improvement="better",
        )
        assert not proposal.is_auto_apply_candidate

    def test_proposal_constitution_prepended(self) -> None:
        from crackerjack.services.constitution import load_constitution
        from crackerjack.services.improvement_generator import ImprovementGenerator

        gen = ImprovementGenerator(repository=MagicMock())
        prompt = gen._build_generation_prompt(
            failure_context="some failures",
            current_impl="def fix(): pass",
        )
        constitution = load_constitution()
        # Constitution must be in the prompt (defense-in-depth per m-new-13)
        assert constitution[:50] in prompt
