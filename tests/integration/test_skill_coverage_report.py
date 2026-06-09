"""Integration tests for ``crackerjack.skills.coverage.skill_coverage_report``.

Phase 1.5 wiring (Item 4 of bodai-adoption-phase-1.5.md).
Crackerjack joins its own internal skill registry with
Session-Buddy's ``distilled_skill_health`` MCP tool to surface
three signals: cold-start (Crackerjack skill with no
distilled-skill evidence), stale (distilled skill reinforced
> threshold_days ago), and under-utilized (high-importance
distilled skill with no Crackerjack counterpart).

The acceptance (per the plan): given 3 distilled skills (fresh,
stale, high-importance with no Crackerjack counterpart), the
report returns 1 cold, 1 stale, 1 under-utilized.

Crackerjack MUST call the MCP tool rather than reading
``distilled_skills`` directly (A3 + Q3 default). Tests therefore
mock the MCP client — they do not boot a real Session-Buddy.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

from crackerjack.skills.coverage import (
    CoverageReport,
    skill_coverage_report,
)


def _make_distilled_skill(
    *,
    skill_id: str,
    problem_pattern: str,
    importance: float,
    last_reinforced_at: datetime,
    evidence_count: int = 5,
) -> dict[str, Any]:
    """Construct a row shaped like the ``distilled_skill_health`` MCP response."""
    return {
        "id": skill_id,
        "problem_pattern": problem_pattern,
        "suggested_approach": f"approach for {skill_id}",
        "because": f"because for {skill_id}",
        "evidence_count": evidence_count,
        "source_memory_ids": [],
        "importance_score": importance,
        "model": "heuristic",
        "created_at": last_reinforced_at,
        "last_reinforced_at": last_reinforced_at,
    }


# ---------------------------------------------------------------------------
# Test 1: the plan's 3-skill acceptance scenario
# ---------------------------------------------------------------------------


async def test_skill_coverage_report_three_skill_acceptance() -> None:
    """The plan's Item 4 acceptance scenario.

    3 distilled skills (fresh, stale, high-importance with no
    Crackerjack counterpart) → report has 1 cold, 1 stale,
    1 under-utilized.
    """
    now = datetime.now()
    distilled = [
        _make_distilled_skill(
            skill_id="fresh-skill",
            problem_pattern="pattern fresh",
            importance=0.75,
            last_reinforced_at=now - timedelta(days=1),
        ),
        _make_distilled_skill(
            skill_id="stale-skill",
            problem_pattern="pattern stale",
            importance=0.80,
            last_reinforced_at=now - timedelta(days=100),
        ),
        _make_distilled_skill(
            skill_id="under-utilized-skill",
            problem_pattern="pattern underutilized",
            importance=0.95,
            last_reinforced_at=now - timedelta(days=2),
        ),
    ]

    # Crackerjack's internal skill registry (the MCP side). The
    # report's "cold" bucket comes from here: a Crackerjack skill
    # with no distilled-skill evidence. None of the distilled
    # patterns match any Crackerjack skill name, so the high-
    # importance one reports as "under_utilized" and the fresh
    # one is neither stale nor under-utilized → "cold".
    crackerjack_skill_names = [
        "unrelated_crackerjack_skill_a",
        "unrelated_crackerjack_skill_b",
    ]

    # Mock the MCP client. The contract is:
    #   await client.call_tool("distilled_skill_health",
    #                           threshold_days=90,
    #                           crackerjack_skill_names=[...])
    # returns the list of distilled skill dicts.
    mcp_client = AsyncMock()
    mcp_client.call_tool = AsyncMock(return_value=distilled)

    report = await skill_coverage_report(
        session_buddy_client=mcp_client,
        crackerjack_skill_names=crackerjack_skill_names,
        threshold_days=90,
    )

    # The report is a CoverageReport dataclass with counts.
    assert isinstance(report, CoverageReport)
    assert report.cold == 1, f"expected 1 cold, got {report.cold}"
    assert report.stale == 1, f"expected 1 stale, got {report.stale}"
    assert report.under_utilized == 1, (
        f"expected 1 under_utilized, got {report.under_utilized}"
    )

    # The fresh row is in the cold bucket. (Per the plan, "cold"
    # is the cold-start indicator — a distilled skill with no
    # signal/no Crackerjack counterpart.)
    assert any(
        s.id == "fresh-skill" and s.status == "cold" for s in report.distilled
    ), f"fresh skill should be 'cold', got {report.distilled!r}"


# ---------------------------------------------------------------------------
# Test 2: the MCP tool is called with the right arguments
# ---------------------------------------------------------------------------


async def test_skill_coverage_report_calls_mcp_tool() -> None:
    """The report must invoke the Session-Buddy MCP tool, not read DuckDB.

    This is the A3 + Q3 default from the plan: Crackerjack stays
    out of the data layer's internals. The MCP tool receives
    ``threshold_days`` and ``crackerjack_skill_names`` so the
    data layer can apply the under-utilized check itself.
    """
    mcp_client = AsyncMock()
    mcp_client.call_tool = AsyncMock(return_value=[])

    crackerjack_skill_names = ["cruddy coverage", "another one"]
    await skill_coverage_report(
        session_buddy_client=mcp_client,
        crackerjack_skill_names=crackerjack_skill_names,
        threshold_days=42,
    )

    assert mcp_client.call_tool.await_count == 1, (
        f"MCP tool should be called exactly once, got "
        f"{mcp_client.call_tool.await_count}"
    )
    args, kwargs = mcp_client.call_tool.call_args
    # Either positional or keyword form. We accept both.
    tool_name = args[0] if args else kwargs.get("tool_name")
    assert tool_name == "distilled_skill_health", (
        f"expected 'distilled_skill_health' tool, got {tool_name!r}"
    )
    forwarded_threshold = kwargs.get(
        "threshold_days", args[1] if len(args) > 1 else None
    )
    assert forwarded_threshold == 42, (
        f"threshold_days must round-trip to the MCP tool, got "
        f"{forwarded_threshold!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: Crackerjack-only "cold-start" skills show up in the report
# ---------------------------------------------------------------------------


async def test_skill_coverage_report_includes_crackerjack_only_skills() -> None:
    """A Crackerjack skill with no distilled-skill evidence is a cold start.

    The plan: "Skills in Crackerjack's registry that have no
    distilled-skill evidence (cold-start indicator)". A pure
    Crackerjack-side row (no entry in the distilled list at all)
    must show up in the report's ``crackerjack_only`` list.
    """
    # Distilled side is empty.
    mcp_client = AsyncMock()
    mcp_client.call_tool = AsyncMock(return_value=[])

    crackerjack_skill_names = [
        "only-in-crackerjack-1",
        "only-in-crackerjack-2",
        "backed-by-distilled-skill",
    ]
    # The report cross-references distilled pattern names against
    # crackerjack_skill_names. A match means "not cold-start".
    distilled = [
        _make_distilled_skill(
            skill_id="has-match",
            problem_pattern="backed-by-distilled-skill",
            importance=0.75,
            last_reinforced_at=datetime.now() - timedelta(days=1),
        ),
    ]
    mcp_client.call_tool = AsyncMock(return_value=distilled)

    report = await skill_coverage_report(
        session_buddy_client=mcp_client,
        crackerjack_skill_names=crackerjack_skill_names,
        threshold_days=90,
    )

    # Two Crackerjack-only skills → ``crackerjack_only`` lists both.
    assert set(report.crackerjack_only) == {
        "only-in-crackerjack-1",
        "only-in-crackerjack-2",
    }, (
        f"expected both unmatched Crackerjack skills in "
        f"crackerjack_only, got {report.crackerjack_only!r}"
    )
    # The matched one is NOT cold-start.
    assert "backed-by-distilled-skill" not in report.crackerjack_only
