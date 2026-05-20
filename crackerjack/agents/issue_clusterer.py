from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from crackerjack.agents.base import Issue
from crackerjack.models.fix_plan import FixPlan


@dataclass
class EditUnit:
    file: Path
    issues: list[Issue]
    primary_hook: str
    estimated_complexity: int


class IssueClusterer:
    """Groups issues and FixPlans by file for parallel dispatch.

    Clustering rule: all issues or plans for the same file form one unit.
    Units are ordered by complexity descending so the most expensive work
    starts first, minimising wall-clock via head-of-line scheduling.
    """

    def cluster(self, issues: list[Issue]) -> list[EditUnit]:
        by_file: dict[Path, list[Issue]] = {}
        for issue in issues:
            file = Path(issue.file_path or "unknown")
            by_file.setdefault(file, []).append(issue)

        units = [
            EditUnit(
                file=file,
                issues=file_issues,
                primary_hook=file_issues[0].stage if file_issues else "unknown",
                estimated_complexity=len(file_issues),
            )
            for file, file_issues in by_file.items()
        ]
        units.sort(key=lambda u: u.estimated_complexity, reverse=True)
        return units

    def cluster_plans(self, plans: list[FixPlan]) -> list[list[FixPlan]]:
        """Return plans grouped by file, each group sorted by line number."""
        by_file: dict[str, list[FixPlan]] = {}
        for plan in plans:
            by_file.setdefault(plan.file_path, []).append(plan)

        groups = list(by_file.values())
        for group in groups:
            group.sort(
                key=lambda p: p.changes[0].line_range[0] if p.changes else 0
            )
        groups.sort(key=lambda g: len(g), reverse=True)
        return groups
