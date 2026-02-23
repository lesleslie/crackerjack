"""
Planning agent for AI fix generation.

Creates FixPlans from context and pattern warnings with risk assessment.
"""

import ast
import logging
from pathlib import Path
from typing import Any

from ..agents.base import Issue, IssueType
from ..models.fix_plan import ChangeSpec, FixPlan

logger = logging.getLogger(__name__)

# Lazy import for AST Transform Engine to avoid circular imports
_ast_transform_engine = None


def _get_ast_engine():
    """Get or create the AST Transform Engine (lazy initialization)."""
    global _ast_transform_engine
    if _ast_transform_engine is None:
        from .helpers.ast_transform import (
            ASTTransformEngine,
            DataProcessingPattern,
            DecomposeConditionalPattern,
            EarlyReturnPattern,
            ExtractMethodPattern,
            GuardClausePattern,
            LibcstSurgeon,
        )

        engine = ASTTransformEngine()
        # Register patterns in priority order (lowest priority value first)
        engine.register_pattern(EarlyReturnPattern())  # Priority 1
        engine.register_pattern(GuardClausePattern())  # Priority 2
        engine.register_pattern(DataProcessingPattern())  # Priority 3
        engine.register_pattern(DecomposeConditionalPattern())  # Priority 3
        engine.register_pattern(ExtractMethodPattern())  # Priority 4
        engine.register_surgeon(LibcstSurgeon())
        _ast_transform_engine = engine
    return _ast_transform_engine


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
        # Use file_content for line number lookups (relevant_code is a window)
        file_content = context.get("file_content", "")

        # Generate change based on issue and approach
        if approach == "refactor_for_clarity":
            change = self._refactor_for_clarity(issue, file_content)
        elif approach == "fix_type_annotation":
            change = self._fix_type_annotation(issue, file_content)
        elif approach == "apply_style_fix":
            change = self._apply_style_fix(issue, file_content)
        elif approach == "fix_documentation":
            change = self._fix_documentation(issue, file_content)
        else:
            change = self._generic_fix(issue, file_content)

        return [change] if change else []

    def _refactor_for_clarity(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Generate change for complexity refactoring using AST Transform Engine.

        First attempts automated AST-based transformation. If that fails,
        falls back to manual TODO marker.
        """
        import asyncio

        lines = code.split("\n")

        # Find the target line
        if issue.line_number and 1 <= issue.line_number <= len(lines):
            target_line = issue.line_number - 1  # Convert to 0-indexed
        else:
            return None

        # Skip if line already has a TODO comment (prevent TODO spam)
        old_code = lines[target_line]
        if "# TODO" in old_code or "# FIXME" in old_code:
            self.logger.debug(
                f"Skipping line {issue.line_number}: already has TODO/FIXME comment"
            )
            return None

        # Also skip if the previous line has a TODO comment (we add TODOs above)
        if target_line > 0:
            prev_line = lines[target_line - 1]
            if "# TODO: Refactor" in prev_line or "# TODO" in prev_line:
                self.logger.debug(
                    f"Skipping line {issue.line_number}: previous line has TODO comment"
                )
                return None

        # Try AST-based transformation first
        try:
            engine = _get_ast_engine()
            file_path = Path(issue.file_path) if issue.file_path else Path("unknown.py")

            # Run async transform in sync context
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're already in an async context, schedule the transform
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        engine.transform(code, file_path, target_line + 1),
                    )
                    transform_result = future.result(timeout=30)
            else:
                # No running loop, can use asyncio.run directly
                transform_result = asyncio.run(
                    engine.transform(code, file_path, target_line + 1)
                )

            if transform_result:
                # Convert engine's ChangeSpec to PlanningAgent's ChangeSpec
                return ChangeSpec(
                    line_range=(
                        transform_result.line_start,
                        transform_result.line_end,
                    ),
                    old_code=transform_result.original_content,
                    new_code=transform_result.transformed_content,
                    reason=(
                        f"AST transform ({transform_result.pattern_name}): "
                        f"reduced complexity by {transform_result.complexity_reduction}"
                    ),
                )

            self.logger.info(
                f"AST transform did not find applicable pattern for {issue.file_path}:{issue.line_number}"
            )
            # Return None instead of adding TODO spam
            return None

        except Exception as e:
            self.logger.warning(
                f"AST transform failed for {issue.file_path}:{issue.line_number}: {e}"
            )
            # Return None instead of adding TODO spam
            return None

    def _fix_type_annotation(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Generate change for type error fix using AST-aware approach.

        Instead of naively appending text, we parse the AST to understand
        the code structure and apply appropriate type annotations.
        """
        import ast

        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]
        old_code.strip()

        # Skip if already has a type: ignore comment
        if "# type: ignore" in old_code:
            self.logger.debug(
                f"Skipping line {issue.line_number}: already has type: ignore"
            )
            return None

        # Parse AST to understand the line context
        try:
            tree = ast.parse(code)
            node_at_line = self._find_node_at_line(tree, issue.line_number)

            if node_at_line is None:
                # Fallback: add type: ignore comment for unparsable lines
                return self._create_type_ignore_change(
                    old_code, target_line, issue.message
                )

            # Handle different node types appropriately
            if isinstance(node_at_line, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Function definition - check if it needs return type
                return self._fix_function_type(node_at_line, lines, issue.message)
            elif isinstance(node_at_line, ast.AnnAssign):
                # Already has annotation - just add type: ignore
                return self._create_type_ignore_change(
                    old_code, target_line, issue.message
                )
            elif isinstance(node_at_line, ast.Assign):
                # Assignment that might need annotation
                return self._fix_assignment_type(
                    node_at_line, lines, old_code, issue.message
                )
            else:
                # Default: add type: ignore comment
                return self._create_type_ignore_change(
                    old_code, target_line, issue.message
                )

        except SyntaxError:
            # File has syntax errors - fall back to simple type: ignore
            return self._create_type_ignore_change(old_code, target_line, issue.message)

    def _find_node_at_line(self, tree: ast.AST, line_number: int) -> ast.AST | None:
        """Find the AST node at the specified line number."""
        for node in ast.walk(tree):
            if hasattr(node, "lineno") and node.lineno == line_number:
                return node
        return None

    def _fix_function_type(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
        message: str,
    ) -> ChangeSpec | None:
        """Fix type annotation for function definitions."""
        # If function has no return annotation, we can't safely add one
        # Just add type: ignore to the function def line
        old_code = lines[node.lineno - 1]
        return self._create_type_ignore_change(old_code, node.lineno - 1, message)

    def _fix_assignment_type(
        self,
        node: ast.Assign,
        lines: list[str],
        old_code: str,
        message: str,
    ) -> ChangeSpec | None:
        """Fix type annotation for assignments.

        We don't try to infer types - that's error-prone.
        Instead, we add a type: ignore comment.
        """
        return self._create_type_ignore_change(old_code, node.lineno - 1, message)

    def _create_type_ignore_change(
        self, old_code: str, line_index: int, message: str
    ) -> ChangeSpec:
        """Create a ChangeSpec that adds type: ignore comment."""
        # Preserve any existing inline comment
        if "#" in old_code:
            # Insert type: ignore before existing comment
            comment_pos = old_code.index("#")
            before_comment = old_code[:comment_pos].rstrip()
            existing_comment = old_code[comment_pos:]
            new_code = f"{before_comment}  # type: ignore  {existing_comment[1:]}"
        else:
            # Add type: ignore at end
            new_code = old_code.rstrip() + "  # type: ignore[untyped]"

        return ChangeSpec(
            line_range=(line_index + 1, line_index + 1),
            old_code=old_code,
            new_code=new_code,
            reason=f"Type error: {message}",
        )

    def _apply_style_fix(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Generate change for style fix."""
        # For now, just mark as TODO
        lines = code.split("\n")

        if issue.line_number and 1 <= issue.line_number <= len(lines):
            target_line = issue.line_number - 1
            old_code = lines[target_line]

            # Skip if line already has a TODO comment (prevent TODO spam)
            if (
                "# TODO" in old_code
                or "# FIXME" in old_code
                or "# Style fix" in old_code
            ):
                self.logger.debug(
                    f"Skipping line {issue.line_number}: already has TODO/FIXME comment"
                )
                return None

            # Also skip if the previous line has a TODO comment (we add TODOs above)
            if target_line > 0:
                prev_line = lines[target_line - 1]
                if "# TODO: Refactor" in prev_line or "# Style fix" in prev_line:
                    self.logger.debug(
                        f"Skipping line {issue.line_number}: previous line has TODO comment"
                    )
                    return None

            # Preserve indentation
            import re

            indent_match = re.match(r"^(\s*)", old_code)
            indent_match.group(1) if indent_match else ""

            # Return None instead of adding TODO-style comments
            # Style issues are better handled by formatters like ruff
            self.logger.debug(
                f"Skipping style issue at {issue.file_path}:{issue.line_number} - use ruff format instead"
            )
            return None

        return None

    def _fix_documentation(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Generate change for documentation fix (broken links, etc.)."""
        # Documentation fixes require context-specific changes
        # Return None to skip - these need manual intervention
        self.logger.debug(
            f"Skipping documentation issue at {issue.file_path}:{issue.line_number} - requires manual fix"
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
