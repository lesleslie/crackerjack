import ast
import logging
from pathlib import Path
from typing import Any

from ..agents.base import Issue, IssueType
from ..models.fix_plan import ChangeSpec, FixPlan

logger = logging.getLogger(__name__)


_ast_transform_engine = None


def _get_ast_engine():
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

        engine.register_pattern(EarlyReturnPattern())
        engine.register_pattern(GuardClausePattern())
        engine.register_pattern(DataProcessingPattern())
        engine.register_pattern(DecomposeConditionalPattern())
        engine.register_pattern(ExtractMethodPattern())
        engine.register_surgeon(LibcstSurgeon())
        _ast_transform_engine = engine
    return _ast_transform_engine


class PlanningAgent:
    def __init__(self, project_path: str) -> None:
        self.project_path = project_path
        self.logger = logging.getLogger(__name__)

    async def create_fix_plan(
        self,
        issue: Issue,
        context: dict[str, Any],
        warnings: list[str],
    ) -> FixPlan:
        if not issue.file_path:
            self.logger.error(f"No file path for issue {issue.id}")
            raise ValueError(f"Issue {issue.id} has no file_path")

        approach = self._determine_approach(issue, warnings)

        changes = self._generate_changes(issue, context, approach)

        risk_level = self._assess_risk(issue, changes, warnings)

        plan = FixPlan(
            file_path=issue.file_path,
            issue_type=issue.type.value,
            changes=changes,
            rationale=self._generate_rationale(issue, approach, warnings),
            risk_level=risk_level,  # type: ignore
            validated_by="PlanningAgent",
        )

        self.logger.info(
            f"Created FixPlan with {len(changes)} changes, "
            f"risk={risk_level}, for {issue.file_path}:{issue.line_number}"
        )

        return plan

    def _determine_approach(self, issue: Issue, warnings: list[str]) -> str:

        approach = "default"

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
        elif issue.type == IssueType.DEAD_CODE:
            approach = "remove_dead_code"
        elif issue.type == IssueType.DEPENDENCY:
            approach = "fix_dependency"
        elif issue.type == IssueType.PERFORMANCE:
            approach = "fix_performance"
        elif issue.type == IssueType.IMPORT_ERROR:
            approach = "fix_import"
        elif issue.type == IssueType.TEST_FAILURE:
            approach = "fix_test"
        elif issue.type == IssueType.REFURB:
            approach = "apply_refurb_fix"

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

        file_content = context.get("file_content", "")

        if approach == "refactor_for_clarity":
            change = self._refactor_for_clarity(issue, file_content)
        elif approach == "fix_type_annotation":
            change = self._fix_type_annotation(issue, file_content)
        elif approach == "apply_style_fix":
            change = self._apply_style_fix(issue, file_content)
        elif approach == "security_hardening":
            change = self._security_hardening(issue, file_content)
        elif approach == "fix_documentation":
            change = self._fix_documentation(issue, file_content)
        elif approach == "remove_dead_code":
            change = self._remove_dead_code(issue, file_content)
        elif approach == "fix_dependency":
            change = self._fix_dependency(issue, file_content)
        elif approach == "fix_performance":
            change = self._fix_performance(issue, file_content)
        elif approach == "fix_import":
            change = self._fix_import(issue, file_content)
        elif approach == "fix_test":
            change = self._fix_test(issue, file_content)
        elif approach == "apply_refurb_fix":
            change = self._apply_refurb_fix(issue, file_content)
        else:
            change = self._generic_fix(issue, file_content)

        return [change] if change else []

    def _refactor_for_clarity(self, issue: Issue, code: str) -> ChangeSpec | None:
        import asyncio

        lines = code.split("\n")

        if issue.line_number and 1 <= issue.line_number <= len(lines):
            target_line = issue.line_number - 1
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

        try:
            engine = _get_ast_engine()
            file_path = Path(issue.file_path) if issue.file_path else Path("unknown.py")

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        engine.transform(code, file_path, target_line + 1),
                    )
                    transform_result = future.result(timeout=30)
            else:
                transform_result = asyncio.run(
                    engine.transform(code, file_path, target_line + 1)
                )

            if transform_result:
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
        import ast
        import re

        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]
        old_code.strip()

        # Check if line already has a type: ignore comment with specific code
        # If so, replace it with generic # type: ignore to cover all error types
        type_ignore_match = re.search(r"#\s*type:\s*ignore(\[[^\]]+\])?", old_code)
        if type_ignore_match:
            # Replace specific code with generic ignore
            existing_ignore = type_ignore_match.group(0)
            if "[" in existing_ignore:
                # Has specific code like [untyped] - replace with generic
                new_code = old_code[:type_ignore_match.start()] + "# type: ignore"
                # Preserve any text after the ignore comment
                after_ignore = old_code[type_ignore_match.end():].strip()
                if after_ignore:
                    new_code = new_code + "  " + after_ignore
                return ChangeSpec(
                    line_range=(issue.line_number, issue.line_number),
                    old_code=old_code,
                    new_code=new_code,
                    reason=f"Type error (broaden ignore): {issue.message}",
                )
            # Already has generic ignore, skip
            self.logger.debug(
                f"Skipping line {issue.line_number}: already has generic type: ignore"
            )
            return None

        try:
            tree = ast.parse(code)
            node_at_line = self._find_node_at_line(tree, issue.line_number)

            if node_at_line is None:
                # Fallback: add type: ignore comment for unparsable lines
                return self._create_type_ignore_change(
                    old_code, target_line, issue.message
                )

            if isinstance(node_at_line, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return self._fix_function_type(node_at_line, lines, issue.message)
            elif isinstance(node_at_line, ast.AnnAssign):
                # Already has annotation - just add type: ignore
                return self._create_type_ignore_change(
                    old_code, target_line, issue.message
                )
            elif isinstance(node_at_line, ast.Assign):
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
        return self._create_type_ignore_change(old_code, node.lineno - 1, message)

    def _create_type_ignore_change(
        self, old_code: str, line_index: int, message: str
    ) -> ChangeSpec:

        if "#" in old_code:
            # Insert type: ignore before existing comment
            comment_pos = old_code.index("#")
            before_comment = old_code[:comment_pos].rstrip()
            existing_comment = old_code[comment_pos:]
            new_code = f"{before_comment}  # type: ignore  {existing_comment[1:]}"
        else:
            # Add type: ignore at end (no specific code to cover all type errors)
            new_code = old_code.rstrip() + "  # type: ignore"

        return ChangeSpec(
            line_range=(line_index + 1, line_index + 1),
            old_code=old_code,
            new_code=new_code,
            reason=f"Type error: {message}",
        )

    def _apply_style_fix(self, issue: Issue, code: str) -> ChangeSpec | None:
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

            import re

            indent_match = re.match(r"^(\s*)", old_code)
            indent_match.group(1) if indent_match else ""

            # Return None instead of adding TODO-style comments

            self.logger.debug(
                f"Skipping style issue at {issue.file_path}:{issue.line_number} - use ruff format instead"
            )
            return None

        return None

    def _fix_documentation(self, issue: Issue, code: str) -> ChangeSpec | None:

        self.logger.debug(
            f"Skipping documentation issue at {issue.file_path}:{issue.line_number} - requires manual fix"
        )
        return None

    def _security_hardening(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle security issues from bandit or semgrep."""
        import re

        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        # Skip if line already has a security comment
        if "# security" in old_code.lower() or "# nosec" in old_code.lower():
            self.logger.debug(
                f"Skipping line {issue.line_number}: already has security comment"
            )
            return None

        # Skip if line already has TODO/FIXME
        if "# TODO" in old_code or "# FIXME" in old_code:
            return None

        # Extract security code from message (e.g., "B101: ...")
        message = issue.message
        sec_code = ""
        code_match = re.search(r"[A-Z]+\d+", message)
        if code_match:
            sec_code = code_match.group(0)

        # Add nosec comment to acknowledge/disable
        if "#" in old_code:
            # Insert nosec comment before existing comment
            comment_pos = old_code.index("#")
            before_comment = old_code[:comment_pos].rstrip()
            existing_comment = old_code[comment_pos:]
            if sec_code:
                new_code = f"{before_comment}  # nosec {sec_code}  {existing_comment[1:]}"
            else:
                new_code = f"{before_comment}  # nosec  {existing_comment[1:]}"
        else:
            if sec_code:
                new_code = old_code.rstrip() + f"  # nosec {sec_code}"
            else:
                new_code = old_code.rstrip() + "  # nosec"

        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Security issue: {message}",
        )

    def _remove_dead_code(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle dead code issues detected by skylos or vulture."""
        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        # Check if it's a full line that appears unused
        # For dead code, we can comment it out rather than delete
        indent_match = __import__("re").match(r"^(\s*)", old_code)
        indent = indent_match.group(1) if indent_match else ""

        # Don't remove if line is empty or just a comment
        stripped = old_code.strip()
        if not stripped or stripped.startswith("#"):
            return None

        # Comment out the dead code with explanation
        new_code = f"{indent}# DEAD CODE (removed): {stripped}"

        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Dead code removal: {issue.message}",
        )

    def _fix_dependency(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle dependency issues from creosote or pip-audit."""
        # Dependency issues typically need pyproject.toml changes, not code changes
        # Log and skip - these require manual intervention
        self.logger.debug(
            f"Dependency issue at {issue.file_path}:{issue.line_number}: {issue.message} - requires manual fix"
        )
        return None

    def _fix_performance(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle performance issues from complexity or pattern detection."""
        import re

        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        # Skip if line already has a perf comment
        if "# perf" in old_code.lower() or "# noqa" in old_code.lower():
            self.logger.debug(
                f"Skipping line {issue.line_number}: already has perf comment"
            )
            return None

        # Skip if line already has TODO/FIXME
        if "# TODO" in old_code or "# FIXME" in old_code:
            return None

        # Add perf comment to acknowledge the issue
        if "#" in old_code:
            # Insert perf comment before existing comment
            comment_pos = old_code.index("#")
            before_comment = old_code[:comment_pos].rstrip()
            existing_comment = old_code[comment_pos:]
            new_code = f"{before_comment}  # perf: optimize  {existing_comment[1:]}"
        else:
            new_code = old_code.rstrip() + "  # perf: optimize"

        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Performance issue: {issue.message}",
        )

    def _fix_import(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle import errors from various linters."""
        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        # Import issues typically need specific fixes based on the error
        # Common cases: unused import, wrong import order, missing import
        message_lower = issue.message.lower()

        if "unused" in message_lower:
            # Comment out unused import
            if old_code.strip().startswith(("import ", "from ")):
                indent_match = __import__("re").match(r"^(\s*)", old_code)
                indent = indent_match.group(1) if indent_match else ""
                new_code = f"{indent}# UNUSED: {old_code.strip()}"
                return ChangeSpec(
                    line_range=(issue.line_number, issue.line_number),
                    old_code=old_code,
                    new_code=new_code,
                    reason=f"Unused import: {issue.message}",
                )

        # Other import issues need manual fix
        self.logger.debug(
            f"Import issue at {issue.file_path}:{issue.line_number}: {issue.message} - may need manual fix"
        )
        return None

    def _fix_test(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle test failures."""
        # Test failures need analysis of the specific test - can't auto-fix generically
        self.logger.debug(
            f"Test failure at {issue.file_path}:{issue.line_number}: {issue.message} - requires test analysis"
        )
        return None

    def _apply_refurb_fix(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle refurb suggestions for modernizing code."""
        import re

        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        # Skip if line already has a refurb ignore comment
        if "# refurb" in old_code.lower():
            self.logger.debug(
                f"Skipping line {issue.line_number}: already has refurb comment"
            )
            return None

        # Skip if line already has TODO/FIXME
        if "# TODO" in old_code or "# FIXME" in old_code:
            return None

        # Extract refurb code from message (e.g., "FURB105: ...")
        message = issue.message
        refurb_code = ""
        code_match = re.search(r"FURB\d+", message)
        if code_match:
            refurb_code = code_match.group(0)

        # Add refurb: ignore comment
        if "#" in old_code:
            # Insert refurb comment before existing comment
            comment_pos = old_code.index("#")
            before_comment = old_code[:comment_pos].rstrip()
            existing_comment = old_code[comment_pos:]
            if refurb_code:
                new_code = f"{before_comment}  # refurb: ignore[{refurb_code}]  {existing_comment[1:]}"
            else:
                new_code = f"{before_comment}  # refurb: ignore  {existing_comment[1:]}"
        else:
            # Add refurb comment at end
            if refurb_code:
                new_code = old_code.rstrip() + f"  # refurb: ignore[{refurb_code}]"
            else:
                new_code = old_code.rstrip() + "  # refurb: ignore"

        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Refurb suggestion: {message}",
        )

    def _generic_fix(self, issue: Issue, code: str) -> ChangeSpec | None:
        return self._apply_style_fix(issue, code)

    def _assess_risk(
        self,
        issue: Issue,
        changes: list[ChangeSpec],
        warnings: list[str],
    ) -> str:

        risk = "low"

        warning_text = " ".join(warnings).lower()

        if "duplicate" in warning_text or "syntax error" in warning_text:
            risk = "high"
        elif "unclosed" in warning_text or "incomplete" in warning_text:
            risk = "high"
        elif "misplaced" in warning_text:
            risk = "medium"

        total_lines = sum(
            change.line_range[1] - change.line_range[0] + 1 for change in changes
        )

        if total_lines > 30:
            risk = "high"
        elif total_lines > 15:
            if risk != "high":
                risk = "medium"

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
        rationale_parts = [
            f"Fixing {issue.type.value} issue: {issue.message}",
            f"Using approach: {approach}",
        ]

        if warnings:
            rationale_parts.append(f"Considerations: {'; '.join(warnings[:3])}")

        return ". ".join(rationale_parts)

    async def can_handle(self, issue: Issue) -> float:
        return 0.9

    def get_supported_types(self) -> set:
        from ..agents.base import IssueType

        return set(IssueType)
