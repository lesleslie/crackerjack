"""FixPlan data structures for validated AI fixes.

Provides structured data classes for representing atomic changes
and complete fix plans with validation tracking.
"""

from dataclasses import dataclass, field
from typing import List, Literal


@dataclass
class ChangeSpec:
    """Specification for a single atomic code change.

    Attributes:
        line_range: Tuple of (start_line, end_line) for the change
        old_code: Original code to be replaced
        new_code: New code to replace with
        reason: Explanation of why this change is needed
    """

    line_range: tuple[int, int]
    old_code: str
    new_code: str
    reason: str


@dataclass
class FixPlan:
    """Validated fix plan with atomic changes.

    This represents a complete, validated plan for fixing an issue.
    All changes in the plan should be applied atomically.

    Attributes:
        file_path: Path to file being modified
        issue_type: Type of issue being fixed (COMPLEXITY, TYPE_ERROR, etc.)
        risk_level: Risk assessment (low/medium/high)
        validated_by: Which validator/system approved this plan
        rationale: High-level explanation of the fix approach
        changes: List of atomic changes to apply
    """

    file_path: str
    issue_type: str
    risk_level: Literal["low", "medium", "high"]
    validated_by: str
    rationale: str
    changes: List[ChangeSpec] = field(default_factory=list)

    def total_lines_changed(self) -> int:
        """Calculate total lines that will be modified.

        Returns:
            Sum of line counts across all changes
        """
        total = 0
        for change in self.changes:
            old_lines = change.old_code.count("\n")
            new_lines = change.new_code.count("\n")
            total += abs(new_lines - old_lines)
        return total

    def is_high_risk(self) -> bool:
        """Check if this is a high-risk plan.

        Returns:
            True if risk_level is 'high'
        """
        return self.risk_level == "high"


def create_change_spec(
    line_range: tuple[int, int],
    old_code: str,
    new_code: str,
    reason: str,
) -> ChangeSpec:
    """Factory function to create a ChangeSpec.

    Args:
        line_range: Tuple of (start, end) lines
        old_code: Original code
        new_code: New code
        reason: Why change is needed

    Returns:
        ChangeSpec instance
    """
    return ChangeSpec(
        line_range=line_range,
        old_code=old_code,
        new_code=new_code,
        reason=reason,
    )


def create_fix_plan(
    file_path: str,
    issue_type: str,
    changes: List[ChangeSpec],
    rationale: str,
    risk_level: Literal["low", "medium", "high"] = "low",
    validated_by: str = "system",
) -> FixPlan:
    """Factory function to create a FixPlan.

    Args:
        file_path: Path to file
        issue_type: Type of issue
        changes: List of atomic changes
        rationale: Explanation of approach
        risk_level: Risk assessment (default: low)
        validated_by: What validated this (default: system)

    Returns:
        FixPlan instance
    """
    return FixPlan(
        file_path=file_path,
        issue_type=issue_type,
        changes=changes,
        rationale=rationale,
        risk_level=risk_level,
        validated_by=validated_by,
    )
