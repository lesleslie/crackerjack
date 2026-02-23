
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ChangeSpec:

    line_range: tuple[int, int]
    old_code: str
    new_code: str
    reason: str


@dataclass
class FixPlan:

    file_path: str
    issue_type: str
    risk_level: Literal["low", "medium", "high"]
    validated_by: str
    rationale: str
    changes: list[ChangeSpec] = field(default_factory=list)

    def total_lines_changed(self) -> int:
        total = 0
        for change in self.changes:
            old_lines = change.old_code.count("\n")
            new_lines = change.new_code.count("\n")
            total += abs(new_lines - old_lines)
        return total

    def is_high_risk(self) -> bool:
        return self.risk_level == "high"


def create_change_spec(
    line_range: tuple[int, int],
    old_code: str,
    new_code: str,
    reason: str,
) -> ChangeSpec:
    return ChangeSpec(
        line_range=line_range,
        old_code=old_code,
        new_code=new_code,
        reason=reason,
    )


def create_fix_plan(
    file_path: str,
    issue_type: str,
    changes: list[ChangeSpec],
    rationale: str,
    risk_level: Literal["low", "medium", "high"] = "low",
    validated_by: str = "system",
) -> FixPlan:
    return FixPlan(
        file_path=file_path,
        issue_type=issue_type,
        changes=changes,
        rationale=rationale,
        risk_level=risk_level,
        validated_by=validated_by,
    )
