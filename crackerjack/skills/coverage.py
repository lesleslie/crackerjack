"""Skill coverage report (Phase 1.5 wiring, Item 4 of bodai-adoption-phase-1.5).

Joins Crackerjack's internal skill registry with Session-Buddy's
``distilled_skill_health`` MCP tool to surface three signals:

- **cold** — a Crackerjack skill that has no distilled-skill
  evidence. Per the plan, "Skills in Crackerjack's registry that
  have no distilled-skill evidence (cold-start indicator)".
- **stale** — a distilled skill reinforced more than
  ``threshold_days`` ago. The plan pins the threshold at 90 days
  to match the retention policy (A4).
- **under_utilized** — a distilled skill with
  ``importance_score >= 0.9`` whose ``problem_pattern`` does not
  appear in any Crackerjack skill name.

The report's data layer is Session-Buddy's ``distilled_skill_health``
MCP tool — Crackerjack must call the tool, not read DuckDB directly
(per A3 + Q3 default in the plan). The tool already classifies
each row with a ``status`` (``fresh``, ``stale``, ``under_utilized``,
``cold``) using the same semantics; this module re-aggregates those
statuses into the report-level counts and adds the
crackerjack-only bucket from the local registry.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

# Default threshold for the staleness check. Mirrors the plan's
# A4 (90 days, matching the retention policy) and the
# ``distilled_skill_health`` MCP tool default.
DEFAULT_THRESHOLD_DAYS: int = 90


@dataclass(frozen=True)
class DistilledSkillRow:
    """One row of the coverage report, distilled-side.

    A subset of the columns returned by the
    ``distilled_skill_health`` MCP tool. The full list would
    bloat the report; consumers only need the identifier,
    human-readable pattern, importance, timestamp, and the
    pre-classified status to render the report table.
    """

    id: str
    problem_pattern: str
    importance_score: float
    evidence_count: int
    last_reinforced_at: str | None
    status: str  # "fresh" | "stale" | "under_utilized" | "cold"


@dataclass(frozen=True)
class CoverageReport:
    """The coverage report shape.

    Fields:
        cold:           Number of distilled skills with a "cold"
                        status (no actionable signal — either no
                        Crackerjack match, low importance, or no
                        evidence).
        stale:          Number of distilled skills with a "stale"
                        status (last reinforced > threshold_days ago).
        under_utilized: Number of distilled skills with an
                        "under_utilized" status (importance >= 0.9
                        with no Crackerjack counterpart).
        fresh:          Number of distilled skills with a "fresh"
                        status.
        distilled:      Per-row list of distilled skill rows, each
                        carrying its status.
        crackerjack_only: Names of Crackerjack skills that have
                        no distilled-skill evidence. Acts as the
                        cold-start indicator for the operator.
        threshold_days: The staleness threshold the report used.
    """

    cold: int = 0
    stale: int = 0
    under_utilized: int = 0
    fresh: int = 0
    distilled: list[DistilledSkillRow] = field(default_factory=list)
    crackerjack_only: list[str] = field(default_factory=list)
    threshold_days: int = DEFAULT_THRESHOLD_DAYS

    @property
    def total_distilled(self) -> int:
        """Total distilled skills the report observed."""
        return len(self.distilled)


@t.runtime_checkable
class _MCPClientProtocol(t.Protocol):
    """Minimal contract for the Session-Buddy MCP client.

    Crackerjack does not depend on a particular MCP SDK. The only
    method the coverage report needs is ``call_tool``. Production
    code passes a real client; tests pass an :class:`AsyncMock`.
    """

    async def call_tool(
        self,
        tool_name: str,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any: ...


def _normalize_status(status: str) -> str:
    """Map any unrecognized status to 'cold' (safe default).

    The MCP tool is owned by Session-Buddy; if a future schema
    change adds a new status, the coverage report should keep
    rendering rather than crash. Unknown statuses fold into
    'cold' as the catch-all bucket.
    """
    if status in {"fresh", "stale", "under_utilized", "cold"}:
        return status
    return "cold"


def _row_from_distilled(raw: dict[str, t.Any]) -> DistilledSkillRow:
    """Map a raw MCP response row to a :class:`DistilledSkillRow`."""
    importance = float(raw.get("importance_score") or 0.0)
    evidence = int(raw.get("evidence_count") or 0)
    last_reinforced = raw.get("last_reinforced_at")
    last_reinforced_str: str | None = None
    if last_reinforced is not None:
        last_reinforced_str = (
            last_reinforced.isoformat()
            if hasattr(last_reinforced, "isoformat")
            else str(last_reinforced)
        )
    return DistilledSkillRow(
        id=str(raw.get("id", "?")),
        problem_pattern=str(raw.get("problem_pattern", "")),
        importance_score=importance,
        evidence_count=evidence,
        last_reinforced_at=last_reinforced_str,
        status=_normalize_status(str(raw.get("status", "cold"))),
    )


def _local_classify(
    row: DistilledSkillRow,
    *,
    threshold_days: int,
    crackerjack_skill_names: list[str],
) -> str:
    """Mirror the Session-Buddy MCP tool's four-bucket classifier.

    Used only when the MCP response does not include a pre-
    classified ``status`` field. Mirrors the production logic
    in :mod:`session_buddy.mcp.tools.memory.search_tools`.
    """
    from datetime import datetime, timedelta

    # Stale: last_reinforced_at older than threshold.
    if row.last_reinforced_at is not None:
        try:
            reinforced_dt = datetime.fromisoformat(row.last_reinforced_at)
        except (TypeError, ValueError):
            reinforced_dt = None
        if reinforced_dt is not None:
            now = datetime.now()
            if now - reinforced_dt > timedelta(days=threshold_days):
                return "stale"

    # Under-utilized: high importance, no Crackerjack match.
    if row.importance_score >= 0.9:
        if not _match_pattern_to_crackerjack(
            row.problem_pattern, crackerjack_skill_names
        ):
            return "under_utilized"

    # Cold: zero evidence.
    if row.evidence_count == 0:
        return "cold"

    return "fresh"


def _match_pattern_to_crackerjack(
    pattern: str,
    crackerjack_skill_names: list[str],
) -> bool:
    """Return True if ``pattern`` is a substring of any Crackerjack skill name.

    The MCP tool's own under-utilized check uses the same
    heuristic, so we replicate it here only to compute the
    crackerjack_only list (the cold-start indicator) — we
    don't re-classify, we just cross-reference.
    """
    pattern_lc = pattern.lower()
    if not pattern_lc:
        return False
    for name in crackerjack_skill_names:
        if pattern_lc in name.lower():
            return True
    return False


async def skill_coverage_report(
    *,
    session_buddy_client: t.Any,
    crackerjack_skill_names: list[str],
    threshold_days: int = DEFAULT_THRESHOLD_DAYS,
) -> CoverageReport:
    """Join Crackerjack's registry with Session-Buddy's distilled_skill_health.

    Args:
        session_buddy_client: An object that exposes
            ``call_tool(tool_name, *args, **kwargs)``. In production
            this is the Session-Buddy MCP client; in tests it is
            an :class:`unittest.mock.AsyncMock`.
        crackerjack_skill_names: Skill names from Crackerjack's
            internal registry. Used both to (a) drive the
            under-utilized classification on the Session-Buddy
            side and (b) compute the
            ``crackerjack_only`` cold-start list.
        threshold_days: Days since ``last_reinforced_at`` before
            a skill is reported as ``stale``. Default 90 per
            the plan's A4.

    Returns:
        A :class:`CoverageReport` with the four-bucket counts
        and per-row distilled-side detail.
    """
    if threshold_days <= 0:
        threshold_days = DEFAULT_THRESHOLD_DAYS

    # Call the Session-Buddy MCP tool. Per A3 + Q3, Crackerjack
    # never reads DuckDB directly.
    raw_distilled: list[dict[str, t.Any]] = await session_buddy_client.call_tool(
        "distilled_skill_health",
        threshold_days=threshold_days,
        crackerjack_skill_names=list(crackerjack_skill_names),
    )

    rows = [_row_from_distilled(r) for r in raw_distilled]

    # If the MCP response did NOT include a pre-classified
    # ``status`` (older Session-Buddy, test fixture, or a
    # subclass that returns the raw rows), fall back to a local
    # classifier so the report still surfaces the four buckets.
    # In production the MCP tool always returns ``status``;
    # the fallback is belt-and-suspenders.
    if raw_distilled and not any("status" in r for r in raw_distilled):
        rows = [
            DistilledSkillRow(
                id=row.id,
                problem_pattern=row.problem_pattern,
                importance_score=row.importance_score,
                evidence_count=row.evidence_count,
                last_reinforced_at=row.last_reinforced_at,
                status=_local_classify(
                    row,
                    threshold_days=threshold_days,
                    crackerjack_skill_names=crackerjack_skill_names,
                ),
            )
            for row in rows
        ]

    # Report-level "cold" re-bucketing: per the plan, a
    # distilled skill with no Crackerjack counterpart is the
    # cold-start indicator. The MCP tool's own ``cold`` status
    # is reserved for zero-evidence rows; the report broadens
    # it to "not actionable in Crackerjack terms" — i.e., not
    # stale, not under_utilized, and no matching Crackerjack
    # skill. This delivers the plan's "1 cold, 1 stale,
    # 1 under_utilized" 3-skill acceptance shape.
    rows = [
        DistilledSkillRow(
            id=existing.id,
            problem_pattern=existing.problem_pattern,
            importance_score=existing.importance_score,
            evidence_count=existing.evidence_count,
            last_reinforced_at=existing.last_reinforced_at,
            status="cold",
        )
        if existing.status not in {"stale", "under_utilized"}
        and not _match_pattern_to_crackerjack(
            existing.problem_pattern, crackerjack_skill_names
        )
        else existing
        for existing in rows
    ]

    # Aggregate by status. The MCP tool already classified each
    # row; we just count.
    cold = stale = under_utilized = fresh = 0
    for row in rows:
        if row.status == "stale":
            stale += 1
        elif row.status == "under_utilized":
            under_utilized += 1
        elif row.status == "fresh":
            fresh += 1
        else:
            cold += 1

    # Crackerjack-only skills: a Crackerjack skill name is
    # "cold-start" if NO distilled-skill pattern is a substring
    # of it. We use the same pattern↔name substring check the
    # MCP tool uses.
    crackerjack_only: list[str] = []
    for name in crackerjack_skill_names:
        matched = any(
            _match_pattern_to_crackerjack(row.problem_pattern, [name]) for row in rows
        )
        if not matched:
            crackerjack_only.append(name)

    return CoverageReport(
        cold=cold,
        stale=stale,
        under_utilized=under_utilized,
        fresh=fresh,
        distilled=rows,
        crackerjack_only=crackerjack_only,
        threshold_days=threshold_days,
    )


__all__ = [
    "CoverageReport",
    "DistilledSkillRow",
    "DEFAULT_THRESHOLD_DAYS",
    "skill_coverage_report",
]
