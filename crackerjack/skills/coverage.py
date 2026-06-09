from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

DEFAULT_THRESHOLD_DAYS: int = 90


@dataclass(frozen=True)
class DistilledSkillRow:
    id: str
    problem_pattern: str
    importance_score: float
    evidence_count: int
    last_reinforced_at: str | None
    status: str


@dataclass(frozen=True)
class CoverageReport:
    cold: int = 0
    stale: int = 0
    under_utilized: int = 0
    fresh: int = 0
    distilled: list[DistilledSkillRow] = field(default_factory=list)
    crackerjack_only: list[str] = field(default_factory=list)
    threshold_days: int = DEFAULT_THRESHOLD_DAYS

    @property
    def total_distilled(self) -> int:
        return len(self.distilled)


@t.runtime_checkable
class _MCPClientProtocol(t.Protocol):
    async def call_tool(
        self,
        tool_name: str,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any: ...


def _normalize_status(status: str) -> str:
    if status in {"fresh", "stale", "under_utilized", "cold"}:
        return status
    return "cold"


def _row_from_distilled(raw: dict[str, t.Any]) -> DistilledSkillRow:
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
    from datetime import datetime, timedelta

    if row.last_reinforced_at is not None:
        try:
            reinforced_dt = datetime.fromisoformat(row.last_reinforced_at)
        except (TypeError, ValueError):
            reinforced_dt = None
        if reinforced_dt is not None:
            now = datetime.now()
            if now - reinforced_dt > timedelta(days=threshold_days):
                return "stale"

    if row.importance_score >= 0.9:
        if not _match_pattern_to_crackerjack(
            row.problem_pattern, crackerjack_skill_names
        ):
            return "under_utilized"

    if row.evidence_count == 0:
        return "cold"

    return "fresh"


def _match_pattern_to_crackerjack(
    pattern: str,
    crackerjack_skill_names: list[str],
) -> bool:
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
    if threshold_days <= 0:
        threshold_days = DEFAULT_THRESHOLD_DAYS

    raw_distilled: list[dict[str, t.Any]] = await session_buddy_client.call_tool(
        "distilled_skill_health",
        threshold_days=threshold_days,
        crackerjack_skill_names=list(crackerjack_skill_names),
    )

    rows = [_row_from_distilled(r) for r in raw_distilled]

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
