"""Tests for ``crackerjack.services.improvement_overseer``.

Covers the ``OverseerVerdict`` dataclass, ``ImprovementOverseer`` async
review path, and the helper that builds review context for an
``ImprovementProposal``. The review path runs locally without making
network calls — it scans the diff string for known anti-patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from crackerjack.services.improvement_overseer import (
    ImprovementOverseer,
    OverseerVerdict,
)


def test_default_overseer_model_is_set() -> None:
    """The class exposes a documented default overseer model."""
    assert ImprovementOverseer.DEFAULT_OVERSEER_MODEL == "MiniMax-M3-highspeed"


def test_overseer_initializes_with_default_model() -> None:
    overseer = ImprovementOverseer()
    assert overseer._model == "MiniMax-M3-highspeed"  # type: ignore[attr-defined]


def test_overseer_accepts_custom_model() -> None:
    overseer = ImprovementOverseer(model="MiniMax-M3")
    assert overseer._model == "MiniMax-M3"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_review_diff_returns_verdict_with_no_concerns_for_clean_diff() -> None:
    overseer = ImprovementOverseer()
    verdict = await overseer.review_diff(
        diff="def clean() -> int: return 1",
        constitution="",
        failure_context="",
    )
    assert verdict.approved is True
    assert verdict.concerns == []
    assert verdict.model_used == "MiniMax-M3-highspeed"


@pytest.mark.asyncio
async def test_review_diff_flags_any_usage_without_type_ignore() -> None:
    overseer = ImprovementOverseer()
    verdict = await overseer.review_diff(
        diff="def f(x: Any) -> Any: return x",
        constitution="",
        failure_context="",
    )
    assert verdict.approved is False
    assert any("Any" in c for c in verdict.concerns)


@pytest.mark.asyncio
async def test_review_diff_allows_any_with_type_ignore() -> None:
    """``Any`` with a ``# type: ignore`` comment is permitted."""
    overseer = ImprovementOverseer()
    diff = "def f(x: Any) -> Any: return x  # type: ignore"
    verdict = await overseer.review_diff(diff, "", "")
    assert not any("Any" in c for c in verdict.concerns)


@pytest.mark.asyncio
async def test_review_diff_flags_stdlib_logging() -> None:
    overseer = ImprovementOverseer()
    verdict = await overseer.review_diff(
        diff="import logging\nlogger = logging.getLogger(__name__)",
        constitution="",
        failure_context="",
    )
    assert verdict.approved is False
    assert any("stdlib logging" in c for c in verdict.concerns)


@pytest.mark.asyncio
async def test_review_diff_flags_assert_statements() -> None:
    overseer = ImprovementOverseer()
    verdict = await overseer.review_diff(
        diff="def f(x): assert x > 0",
        constitution="",
        failure_context="",
    )
    assert verdict.approved is False
    assert any("assert" in c for c in verdict.concerns)


@pytest.mark.asyncio
async def test_review_diff_accumulates_multiple_concerns() -> None:
    """All anti-patterns in one diff are reported together."""
    overseer = ImprovementOverseer()
    diff = (
        "import logging\n"
        "def f(x: Any):\n"
        "    assert x\n"
    )
    verdict = await overseer.review_diff(diff, "", "")
    assert verdict.approved is False
    assert len(verdict.concerns) >= 3


@pytest.mark.asyncio
async def test_review_diff_records_model_used() -> None:
    overseer = ImprovementOverseer(model="MiniMax-M3")
    verdict = await overseer.review_diff("clean", "", "")
    assert verdict.model_used == "MiniMax-M3"


def test_build_review_context_returns_expected_dict() -> None:
    """Review context bundles proposal fields with model and constitution."""
    overseer = ImprovementOverseer()

    @dataclass
    class _Proposal:
        diff: str = "def f(): pass"
        rationale: str = "because"
        improvement_type: str = "bugfix"

    proposal: Any = _Proposal()
    ctx = overseer.build_review_context(
        proposal=proposal,
        constitution="c",
        failure_context="f",
    )
    assert ctx == {
        "model": "MiniMax-M3-highspeed",
        "constitution": "c",
        "diff": "def f(): pass",
        "rationale": "because",
        "improvement_type": "bugfix",
        "failure_context": "f",
    }


def test_build_review_context_uses_custom_model() -> None:
    overseer = ImprovementOverseer(model="MiniMax-M3")

    @dataclass
    class _Proposal:
        diff: str = ""
        rationale: str = ""
        improvement_type: str = ""

    proposal: Any = _Proposal()
    ctx = overseer.build_review_context(proposal=proposal, constitution="", failure_context="")
    assert ctx["model"] == "MiniMax-M3"
