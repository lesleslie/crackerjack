"""
Planning agent for AI fix generation.

Creates FixPlans from context and pattern warnings with risk assessment.
"""

import logging
from typing import Any

from ..agents.base import Issue, IssueType
from ..models.fix_plan import ChangeSpec, FixPlan

logger = logging.getLogger(__name__)


class PlanningAgent:
    """
    Create FixPlans from context and patterns.

    Responsibilities:
    - Generate minimal, targeted changes
    - Assess risk level (low/medium/high)
    - Create validated FixPlan
    """

    def __init__(self, project_path: str) -> None:
        """
        Initialize planning agent.

        Args:
            project_path: Root path for file operations
        """
        self.project_path = project_path
        self.logger = logging.getLogger(__name__)

    async def create_fix_plan(
        self,
        issue: Issue,
        context: dict[str, Any],
        warnings: list[str],
    ) -> FixPlan:
        """
        Create FixPlan from issue context and warnings.

        Args:
            issue: Issue to fix
            context: Context from ContextAgent
            warnings: Anti-pattern warnings from PatternAgent

        Returns:
            Validated FixPlan for execution
        """
        if not issue.file_path:
            self.logger.error(f"No file path for issue {issue.id}")
            raise ValueError(f"Issue {issue.id} has no file_path")

        # Generate fix approach
        approach = self._determine_approach(issue, warnings)

        # Generate specific changes
        changes = self._generate_changes(issue, context, approach)

        # Assess risk
        risk_level = self._assess_risk(issue, changes, warnings)

        plan = FixPlan(
            file_path=issue.file_path,
            issue_type=issue.type.value,
            changes=changes,
            rationale=self._generate_rationale(issue, approach, warnings),
            risk_level=risk_level,
            validated_by="PlanningAgent",
        )

        self.logger.info(
            f"Created FixPlan with {len(changes)} changes, "
            f"risk={risk_level}, for {issue.file_path}:{issue.line_number}"
        )

        return plan

    def _determine_approach(self, issue: Issue, warnings: list[str]) -> str:
        """
        Determine fix approach based on issue and warnings.

        Args:
            issue: Issue to fix
            warnings: Anti-pattern warnings

        Returns:
            Strategy/approach description
        """
        # Default approach
        approach = "default"

        # Adjust based on issue type (use enum directly for reliability)
        if issue.type == IssueType.COMPLEXITY:
            approach = "refactor_for_clarity"
        elif issue.type == IssueType.TYPE_ERROR:
            approach = "fix_type_annotation"
        elif issue.type == IssueType.FORMATTING:
            approach = "apply_style_fix"
        elif issue.type == IssueType.SECURITY:
            approach = "security_hardening"
        elif issue.type == IssueType.DOCUMENTATION:
            approach = "fix_documentation"

        # Check warnings for high-risk indicators
        high_risk_patterns = ["duplicate", "unclosed", "incomplete", "syntax error"]
        if any(pattern in " ".join(warnings).lower() for pattern in high_risk_patterns):
            approach = f"{approach}_cautious"

        return approach

    def _generate_changes(
        self,
        issue: Issue,
        context: dict[str, Any],
        approach: str,
    ) -> list[ChangeSpec]:
        """
        Generate specific changes for the fix.

        Args:
            issue: Issue to fix
            context: Context from ContextAgent
            approach: Fix approach

        Returns:
            List of ChangeSpec objects
        """
        file_content = context.get("file_content", "")
        relevant_code = context.get("relevant_code", file_content)

        # Generate change based on issue and approach
        if approach == "refactor_for_clarity":
            change = self._refactor_for_clarity(issue, relevant_code)
        elif approach == "fix_type_annotation":
            change = self._fix_type_annotation(issue, relevant_code)
        elif approach == "apply_style_fix":
            change = self._apply_style_fix(issue, relevant_code)
        elif approach == "fix_documentation":
            change = self._fix_documentation(issue, relevant_code)
        else:
            change = self._generic_fix(issue, relevant_code)

        return [change] if change else []

    def _refactor_for_clarity(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Generate change for complexity refactoring."""
        lines = code.split("\n")

        # Find the target line
        if issue.line_number and 1 <= issue.line_number <= len(lines):
            target_line = issue.line_number - 1  # Convert to 0-indexed
        else:
            return None

        # Extract old code
        old_code = lines[target_line]

        # Generate new code (add comment, extract logic)
        new_code = f"# TODO: Refactor {old_code.strip()}\n{old_code}"

        return ChangeSpec(
            line_range=(target_line + 1, target_line + 1),
            old_code=old_code,
            new_code=new_code,
            reason=f"Complexity issue: {issue.message}",
        )

    def _fix_type_annotation(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Generate change for type error fix."""
        # Simple type annotation addition
        lines = code.split("\n")

        if issue.line_number and 1 <= issue.line_number <= len(lines):
            target_line = issue.line_number - 1
            old_code = lines[target_line]

            # Add type hint
            new_code = old_code.rstrip() + ":  # type: ignore[comment]"

            return ChangeSpec(
                line_range=(target_line + 1, target_line + 1),
                old_code=old_code,
                new_code=new_code,
                reason=f"Type error: {issue.message}",
            )

        return None

    def _apply_style_fix(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Generate change for style fix."""
        # For now, just mark as TODO
        lines = code.split("\n")

        if issue.line_number and 1 <= issue.line_number <= len(lines):
            target_line = issue.line_number - 1
            old_code = lines[target_line]
            new_code = f"# Style fix needed: {old_code}"

            return ChangeSpec(
                line_range=(target_line + 1, target_line + 1),
                old_code=old_code,
                new_code=new_code,
                reason=f"Formatting issue: {issue.message}",
            )

        return None

    def _fix_documentation(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Generate change for documentation fix (broken links, etc.)."""
        lines = code.split("\n")

        if issue.line_number and 1 <= issue.line_number <= len(lines):
            target_line = issue.line_number - 1
            old_code = lines[target_line]
            # For documentation issues, we typically need to fix or remove broken links
            # The actual fix depends on the specific issue
            return ChangeSpec(
                line_range=(target_line + 1, target_line + 1),
                old_code=old_code,
                new_code=old_code,  # Placeholder - actual fix needs context
                reason=f"Documentation issue: {issue.message}",
            )

        return None

    def _generic_fix(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Generate generic fix change."""
        return self._apply_style_fix(issue, code)

    def _assess_risk(
        self,
        issue: Issue,
        changes: list[ChangeSpec],
        warnings: list[str],
    ) -> str:
        """
        Assess risk level of planned changes.

        Args:
            issue: Issue to fix
            changes: Planned changes
            warnings: Anti-pattern warnings

        Returns:
            Risk level: low/medium/high
        """
        # Start with low
        risk = "low"

        # Check for high-risk patterns in warnings
        warning_text = " ".join(warnings).lower()

        if "duplicate" in warning_text or "syntax error" in warning_text:
            risk = "high"
        elif "unclosed" in warning_text or "incomplete" in warning_text:
            risk = "high"
        elif "misplaced" in warning_text:
            risk = "medium"

        # Check change size
        total_lines = sum(
            change.line_range[1] - change.line_range[0] + 1 for change in changes
        )

        if total_lines > 30:
            risk = "high"
        elif total_lines > 15:
            if risk != "high":
                risk = "medium"

        # Check issue severity
        if issue.severity.value == "critical":
            risk = "high"
        elif issue.severity.value == "high":
            if risk == "low":
                risk = "medium"

        return risk

    def _generate_rationale(
        self,
        issue: Issue,
        approach: str,
        warnings: list[str],
    ) -> str:
        """
        Generate rationale for the fix plan.

        Args:
            issue: Issue being fixed
            approach: Strategy/approach
            warnings: Anti-pattern warnings

        Returns:
            Human-readable rationale
        """
        rationale_parts = [
            f"Fixing {issue.type.value} issue: {issue.message}",
            f"Using approach: {approach}",
        ]

        if warnings:
            rationale_parts.append(f"Considerations: {'; '.join(warnings[:3])}")

        return ". ".join(rationale_parts)

    async def can_handle(self, issue: Issue) -> float:
        """Planning agent can handle any issue type."""
        return 0.9  # High confidence for planning

    def get_supported_types(self) -> set:
        """Planning agent works with all issue types."""
        from ..agents.base import IssueType

        return set(IssueType)
