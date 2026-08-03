"""Tests for crackerjack.hooks.skill_coverage.pre_commit_skill_coverage_gate.

Q5 (Phase 1.5 close-out) — the gate consumes Session-Buddy's
``distilled_skill_health`` MCP tool and emits a warn-only verdict.
The gate is non-LLM and never consumes the LLM-Cost-Ceiling budget.

Exit code contract:
  0 — all skills fresh (pass)
  1 — stale skills detected or Session-Buddy unreachable (warn)
  2 — programming bug (assertion/schema mismatch) — reserved, not exercised here
"""

from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, patch

import pytest

from crackerjack.hooks.skill_coverage import pre_commit_skill_coverage_gate

pytestmark = pytest.mark.unit


async def test_skill_coverage_pre_commit_passes_with_fresh_skills(
    tmp_path: pathlib.Path,
) -> None:
    with patch(
        "crackerjack.hooks.skill_coverage.fetch_skill_health",
        new=AsyncMock(return_value={"status": "fresh", "stale_count": 0}),
    ):
        result = await pre_commit_skill_coverage_gate(tmp_path)
    assert result == 0


async def test_skill_coverage_pre_commit_warns_on_stale(
    tmp_path: pathlib.Path,
) -> None:
    with patch(
        "crackerjack.hooks.skill_coverage.fetch_skill_health",
        new=AsyncMock(return_value={"status": "stale", "stale_count": 3}),
    ):
        result = await pre_commit_skill_coverage_gate(tmp_path)
    assert result == 1


async def test_skill_coverage_pre_commit_warns_when_unreachable(
    tmp_path: pathlib.Path,
) -> None:
    with patch(
        "crackerjack.hooks.skill_coverage.fetch_skill_health",
        new=AsyncMock(side_effect=ConnectionError("session-buddy down")),
    ):
        result = await pre_commit_skill_coverage_gate(tmp_path)
    assert result == 1
