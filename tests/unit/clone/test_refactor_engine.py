from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.clone.grouper import CloneGroup, CloneLocation, CloneType
from crackerjack.clone.refactor_engine import CloneDecision, CloneRefactorEngine


def _make_group(
    clone_type: CloneType = CloneType.EXACT,
    similarity: float = 1.0,
    file_a: str = "crackerjack/core/a.py",
    file_b: str = "crackerjack/core/b.py",
) -> CloneGroup:
    loc1 = CloneLocation(
        file_path=Path(file_a), start_line=1, end_line=20, start_col=0, end_col=80
    )
    loc2 = CloneLocation(
        file_path=Path(file_b), start_line=1, end_line=20, start_col=0, end_col=80
    )
    return CloneGroup(
        group_id="test-group-001",
        clone_type=clone_type,
        similarity=similarity,
        locations=[loc1, loc2],
        pattern_description="duplicate helper function",
        line_count=20,
    )


@pytest.mark.unit
class TestConfidenceGate:
    def test_engine_auto_applies_type1_high_similarity(self) -> None:
        """Type 1 clone, same repo, similarity ≥ 0.95 → AUTO_APPLY."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.EXACT, similarity=1.0)
        decision = engine.confidence_gate(group, cross_repo=False)
        assert decision == CloneDecision.AUTO_APPLY

    def test_engine_auto_applies_type2_high_similarity(self) -> None:
        """Type 2 clone (renamed), similarity ≥ 0.95 → AUTO_APPLY (same repo)."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.RENAMED, similarity=0.97)
        decision = engine.confidence_gate(group, cross_repo=False)
        assert decision == CloneDecision.AUTO_APPLY

    def test_engine_proposes_for_medium_similarity(self) -> None:
        """Type 3 clone, similarity 0.70–0.94 → PROPOSE_APPROVE."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.MODIFIED, similarity=0.82)
        decision = engine.confidence_gate(group, cross_repo=False)
        assert decision == CloneDecision.PROPOSE_APPROVE

    def test_engine_report_only_for_semantic_low_similarity(self) -> None:
        """Type 4 / similarity < 0.70 → REPORT_ONLY."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.SEMANTIC, similarity=0.60)
        decision = engine.confidence_gate(group, cross_repo=False)
        assert decision == CloneDecision.REPORT_ONLY

    def test_cross_repo_refactor_always_propose_approve_never_auto_apply(
        self,
    ) -> None:
        """Cross-repo extraction → ALWAYS PROPOSE_APPROVE, regardless of similarity."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.EXACT, similarity=1.0)
        decision = engine.confidence_gate(group, cross_repo=True)
        assert decision == CloneDecision.PROPOSE_APPROVE, (
            "Cross-repo must never AUTO_APPLY per M-NEW-5"
        )

    def test_engine_type1_low_similarity_falls_to_propose(self) -> None:
        """Type 1 clone but similarity < 0.95 → PROPOSE_APPROVE (not auto-apply)."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.EXACT, similarity=0.90)
        decision = engine.confidence_gate(group, cross_repo=False)
        assert decision == CloneDecision.PROPOSE_APPROVE


@pytest.mark.unit
class TestRefactorEngineApply:
    async def test_engine_reverts_on_test_gate_failure(self) -> None:
        """If crackerjack run fails after applying diff, revert."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.EXACT, similarity=1.0)

        with (
            patch.object(engine, "_apply_diff", new_callable=AsyncMock) as mock_apply,
            patch.object(
                engine, "_run_test_gate", new_callable=AsyncMock, return_value=False
            ) as mock_gate,
            patch.object(engine, "_revert_diff", new_callable=AsyncMock) as mock_revert,
        ):
            result = await engine.auto_apply(group, diff="--- a\n+++ b\n")
            mock_apply.assert_called_once()
            mock_gate.assert_called_once()
            mock_revert.assert_called_once()
            assert not result["committed"]

    async def test_engine_commits_on_test_gate_pass(self) -> None:
        """If crackerjack run passes after applying diff, commit."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.EXACT, similarity=1.0)

        with (
            patch.object(engine, "_apply_diff", new_callable=AsyncMock),
            patch.object(
                engine, "_run_test_gate", new_callable=AsyncMock, return_value=True
            ),
            patch.object(engine, "_git_commit", new_callable=AsyncMock) as mock_commit,
            patch.object(engine, "_revert_diff", new_callable=AsyncMock) as mock_revert,
        ):
            result = await engine.auto_apply(group, diff="--- a\n+++ b\n")
            mock_commit.assert_called_once()
            mock_revert.assert_not_called()
            assert result["committed"]

    async def test_engine_uses_pycharm_refactor_when_available(self) -> None:
        """If PyCharm is detected, uses pycharm_refactor_symbol."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.EXACT, similarity=1.0)

        with (
            patch.object(engine, "_is_pycharm_available", return_value=True),
            patch.object(
                engine, "_pycharm_refactor_symbol", new_callable=AsyncMock
            ) as mock_pycharm,
            patch.object(
                engine, "_treesitter_splice", new_callable=AsyncMock
            ) as mock_treesitter,
        ):
            await engine.propose(group)
            mock_pycharm.assert_called_once()
            mock_treesitter.assert_not_called()

    async def test_engine_falls_back_to_treesitter_when_pycharm_unavailable(
        self,
    ) -> None:
        """If PyCharm is not available, falls back to treesitter splice."""
        engine = CloneRefactorEngine()
        group = _make_group(CloneType.EXACT, similarity=1.0)

        with (
            patch.object(engine, "_is_pycharm_available", return_value=False),
            patch.object(
                engine, "_pycharm_refactor_symbol", new_callable=AsyncMock
            ) as mock_pycharm,
            patch.object(
                engine, "_treesitter_splice", new_callable=AsyncMock
            ) as mock_treesitter,
        ):
            await engine.propose(group)
            mock_pycharm.assert_not_called()
            mock_treesitter.assert_called_once()
