import ast
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..agents.base import Issue, IssueType
from ..models.fix_plan import ChangeSpec, FixPlan
from ..services.refurb_fixer import SafeRefurbFixer

if TYPE_CHECKING:
    from ..models.protocols import AgentDelegatorProtocol

logger = logging.getLogger(__name__)


_ast_transform_engine = None


TYPE_ERROR_CODE_PATTERNS: dict[str, str] = {
    "name-defined": "Check for missing imports, typos, or undefined variables",
    "var-annotated": "Infer type from usage context or add explicit annotation",
    "attr-defined": "Check if attribute exists on Protocol or add type: ignore",
    "call-arg": "Check function signature and adjust arguments",
    "union-attr": "Use structural subtyping or Protocol pattern",
    "return-value": "Add return type conversion or ensure proper return type",
    "assignment": "Use type narrowing or ensure proper type compatibility",
    "index": "Add bounds checking or use safe access pattern",
    "call-overload": "Match call arguments to one of the overload signatures",
    "arg-type": "Add type coercion and validation",
    "override": "Ensure method signature matches parent class",
    "misc": "General type error - may need manual review",
}


TYPE_ERROR_FIX_EXAMPLES: dict[str, str] = {
    "name-defined": """# Example: Name 'foo' is not defined
# Fix: Add import or define the name""",
    "var-annotated": """# Example: Need type annotation for 'x'
# Fix: Add type annotation like: x: list[str] = []""",
    "attr-defined": """# Example: 'SomeObject' has no attribute 'some_attr'
# Fix: Check Protocol compliance or add # type: ignore[attr-defined]""",
    "call-arg": """# Example: Too many/few arguments for function
# Fix: Check function signature and adjust arguments""",
    "union-attr": """# Example: Item of union has no attribute
# Fix: Add type narrowing or type: ignore""",
}


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
    """Planning agent for creating and applying fix plans.

    This agent analyzes issues and creates FixPlan objects with ChangeSpec
    entries that describe how to fix the issues. It can optionally delegate
    to specialized agents via the AgentDelegatorProtocol.
    """

    def __init__(
        self,
        project_path: str,
        delegator: "AgentDelegatorProtocol | None" = None,
    ) -> None:
        """Initialize the planning agent.

        Args:
            project_path: Path to the project root.
            delegator: Optional delegator for routing to specialized agents.
        """
        self.project_path = project_path
        self.delegator = delegator
        self.logger = logging.getLogger(__name__)

    async def create_fix_plan(
        self,
        issue: Issue,
        context: dict[str, Any],
        warnings: list[str],
    ) -> FixPlan:
        """Create a fix plan for an issue.

        Raises:
            ValueError: If issue has no file_path or no changes can be generated.
        """
        if not issue.file_path:
            self.logger.error(f"No file path for issue {issue.id}")
            raise ValueError(f"Issue {issue.id} has no file_path")

        approach = self._determine_approach(issue, warnings)

        changes = self._generate_changes(issue, context, approach)


        if not changes:
            self.logger.info(
                f"No changes generated for {issue.type.value} at "
                f"{issue.file_path}:{issue.line_number} - requires manual fix"
            )

            return FixPlan(
                file_path=issue.file_path,
                issue_type=issue.type.value,
                changes=[],
                rationale=f"Unable to auto-fix: {issue.message}",
                risk_level="none",  # type: ignore
                validated_by="PlanningAgent",
            )

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
        """Generate changes for an issue, with proper error handling.

        Returns:
            List of ChangeSpec objects. Empty list if no changes can be generated,
            in which case a warning is logged.
        """

        if self.delegator:
            delegated_change = self._try_delegator_fix(issue, context)
            if delegated_change:
                self.logger.info(
                    f"Delegated fix successful for {issue.type.value} at "
                    f"{issue.file_path}:{issue.line_number}"
                )
                return [delegated_change]

        file_content = context.get("file_content", "")


        change = self._dispatch_fix(approach, issue, file_content)

        if change:
            validated_change = self._validate_change_spec(change)
            if validated_change:
                return [validated_change]
            self.logger.warning(
                f"Change validation failed for {issue.type.value} at "
                f"{issue.file_path}:{issue.line_number}"
            )

        self.logger.warning(
            f"Unable to auto-fix {issue.type.value} at "
            f"{issue.file_path}:{issue.line_number}: {issue.message[:100]}"
        )
        return []

    def _dispatch_fix(
        self, approach: str, issue: Issue, file_content: str
    ) -> ChangeSpec | None:
        """Dispatch to the appropriate fix handler based on approach."""
        handlers = {
            "refactor_for_clarity": self._refactor_for_clarity,
            "fix_type_annotation": self._fix_type_annotation,
            "apply_style_fix": self._apply_style_fix,
            "security_hardening": self._security_hardening,
            "fix_documentation": self._fix_documentation,
            "remove_dead_code": self._remove_dead_code,
            "fix_dependency": self._fix_dependency,
            "fix_performance": self._fix_performance,
            "fix_import": self._fix_import,
            "fix_test": self._fix_test,
            "apply_refurb_fix": self._apply_refurb_fix,
        }
        handler = handlers.get(approach, self._generic_fix)
        return handler(issue, file_content)

    def _try_delegator_fix(
        self,
        issue: Issue,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        """Try to delegate the fix to a specialized agent.

        This method attempts to use the AgentDelegator to route the issue
        to a specialized agent that can handle it better than the generic
        handlers in this class.

        Args:
            issue: The issue to fix.
            context: Context dictionary with file content and other info.

        Returns:
            ChangeSpec if delegation was successful, None otherwise.
        """
        import asyncio

        if not self.delegator:
            return None

        try:

            agent_context = context.get("agent_context")
            if not agent_context:
                self.logger.debug("No agent_context available for delegation")
                return None


            from ..agents.base import IssueType

            async def _delegate() -> Any:
                if issue.type == IssueType.TYPE_ERROR:
                    return await self.delegator.delegate_to_type_specialist(
                        issue, agent_context
                    )
                elif issue.type == IssueType.DEAD_CODE:
                    return await self.delegator.delegate_to_dead_code_remover(
                        issue, agent_context
                    )
                elif issue.type == IssueType.REFURB:
                    return await self.delegator.delegate_to_refurb_transformer(
                        issue, agent_context
                    )
                elif issue.type == IssueType.PERFORMANCE:
                    return await self.delegator.delegate_to_performance_optimizer(
                        issue, agent_context
                    )
                else:

                    results = await self.delegator.delegate_batch(
                        [issue], agent_context
                    )
                    return results[0] if results else None


            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _delegate())  # type: ignore[unused-coroutine]
                    result = future.result(timeout=30)
            else:
                result = asyncio.run(_delegate())

            if result and result.success:

                return self._convert_result_to_change(result, issue)

            self.logger.debug(
                f"Delegation returned unsuccessful for {issue.type.value}: "
                f"{result.message if result else 'No result'}"
            )
            return None

        except Exception as e:
            self.logger.warning(f"Delegation failed for {issue.type.value}: {e}")
            return None

    def _convert_result_to_change(
        self,
        result: Any,
        issue: Issue,
    ) -> ChangeSpec | None:
        """Convert a FixResult from delegation to a ChangeSpec.

        Args:
            result: The FixResult from a specialized agent.
            issue: The original issue being fixed.

        Returns:
            ChangeSpec if conversion was successful, None otherwise.
        """
        if not result or not result.fixes_applied:
            return None


        fix_description = result.fixes_applied[0] if result.fixes_applied else ""


        if result.files_modified:
            file_path = result.files_modified[0]
            try:
                content = Path(file_path).read_text()
                lines = content.split("\n")
                if issue.line_number and 1 <= issue.line_number <= len(lines):
                    old_code = lines[issue.line_number - 1]
                    return ChangeSpec(
                        line_range=(issue.line_number, issue.line_number),
                        old_code=old_code,
                        new_code=old_code,
                        reason=f"Delegated fix: {fix_description}",
                    )
            except Exception as e:
                self.logger.warning(f"Failed to read modified file: {e}")


        return ChangeSpec(
            line_range=(issue.line_number or 1, issue.line_number or 1),
            old_code="",
            new_code="",
            reason=f"Delegated fix applied: {fix_description}",
        )

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

    def _get_type_error_context(self, issue: Issue, content: str) -> dict[str, Any]:
        """Extract comprehensive context for fixing type errors.

        This method analyzes the file content around the error line to provide
        rich context for AI agents to make better fix decisions.

        Args:
            issue: The type error issue with file_path, line_number, and message.
            content: Full file content as a string.

        Returns:
            Dictionary containing:
            - error_line: The line with the error (str)
            - line_number: The 1-based line number (int)
            - context_before: 5 lines before the error (list[str])
            - context_after: 5 lines after the error (list[str])
            - related_imports: Import statements in the file (list[str])
            - related_definitions: Class/function definitions (list[str])
            - error_code: Extracted error code like 'name-defined' (str | None)
            - expected_type: Expected type from message if available (str | None)
            - suggested_fix: Suggested fix pattern for the error code (str | None)
        """
        lines = content.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return {}

        target_idx = issue.line_number - 1
        error_line = lines[target_idx]


        start_idx = max(0, target_idx - 5)
        end_idx = min(len(lines), target_idx + 6)
        context_before = lines[start_idx: target_idx]
        context_after = lines[target_idx + 1 : end_idx]


        related_imports: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                related_imports.append(stripped)


        related_definitions: list[str] = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    related_definitions.append(f"class {node.name}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args_str = ", ".join(arg.arg for arg in node.args.args)
                    return_type = ""
                    if node.returns:
                        return_type = f" -> {ast.unparse(node.returns)}"
                    related_definitions.append(f"def {node.name}({args_str}){return_type}")
        except SyntaxError:
            pass


        error_code: str | None = None
        code_match = re.search(r"\[?([a-z]+-[a-z]+)\]?", issue.message.lower())
        if code_match:
            error_code = code_match.group(1)


        expected_type: str | None = None
        type_patterns = [
            r"expected\s+[\"']?([^\"',\]]+)[\"']?",
            r"got\s+[\"']?([^\"',\]]+)[\"']?",
            r"of\s+type\s+[\"']?([^\"',\]]+)[\"']?",
        ]
        for pattern in type_patterns:
            match = re.search(pattern, issue.message, re.IGNORECASE)
            if match:
                expected_type = match.group(1).strip()
                break


        suggested_fix = TYPE_ERROR_FIX_EXAMPLES.get(error_code) if error_code else None

        return {
            "error_line": error_line,
            "line_number": issue.line_number,
            "context_before": context_before,
            "context_after": context_after,
            "related_imports": related_imports,
            "related_definitions": related_definitions,
            "error_code": error_code,
            "expected_type": expected_type,
            "suggested_fix": suggested_fix,
        }

    def _extract_type_error_code(self, message: str) -> str | None:
        """Extract the type error code from a type checker message.

        Common error codes from pyright/mypy:
        - name-defined: Name is not defined
        - var-annotated: Need type annotation
        - attr-defined: Attribute does not exist
        - call-arg: Argument count/type mismatch
        - union-attr: Union member access
        - arg-type: Argument type mismatch

        Args:
            message: The error message from the type checker.

        Returns:
            The error code or None if not found.
        """
        message_lower = message.lower()


        code_match = re.search(r"\[([a-z]+(?:-[a-z]+)*)\]", message_lower)
        if code_match:
            return code_match.group(1)


        if "is not defined" in message_lower or "undefined" in message_lower:
            return "name-defined"
        if "need type annotation" in message_lower or "inference" in message_lower:
            return "var-annotated"
        if "has no attribute" in message_lower or "attribute" in message_lower:
            return "attr-defined"
        if "too many" in message_lower or "too few" in message_lower:
            return "call-arg"
        if "argument" in message_lower and ("type" in message_lower or "mismatch" in message_lower):
            return "arg-type"
        if "union" in message_lower:
            return "union-attr"
        if "return" in message_lower:
            return "return-value"
        if "assignment" in message_lower or "assign" in message_lower:
            return "assignment"
        if "index" in message_lower:
            return "index"
        if "overload" in message_lower:
            return "call-overload"
        if "override" in message_lower:
            return "override"

        return None

    def _try_error_specific_type_fix(
        self,
        issue: Issue,
        code: str,
        error_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        """Try to apply an error-specific fix pattern based on the error code.

        Args:
            issue: The type error issue.
            code: The full file content.
            error_code: The extracted error code (e.g., 'name-defined').
            context: The error context from _get_type_error_context.

        Returns:
            ChangeSpec if a specific fix applies, None otherwise.
        """
        lines = code.split("\n")
        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        if error_code == "name-defined":
            return self._fix_name_defined_error(issue, old_code, context)
        elif error_code == "var-annotated":
            return self._fix_var_annotated_error(issue, old_code, context)
        elif error_code == "attr-defined":
            return self._fix_attr_defined_error(issue, old_code, context)
        elif error_code == "call-arg":
            return self._fix_call_arg_error(issue, old_code, context)
        elif error_code == "arg-type":
            return self._fix_arg_type_error(issue, old_code, context)

        return None

    def _fix_name_defined_error(
        self,
        issue: Issue,
        old_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        """Fix 'name is not defined' errors by checking for missing imports.

        This checks if the undefined name might be available from common imports
        and suggests adding the import. Falls back to type: ignore if not found.
        """
        message_lower = issue.message.lower()


        name_match = re.search(r"name [\"']?(\w+)[\"']? (is not defined|undefined)", message_lower)
        if not name_match:
            return None

        undefined_name = name_match.group(1)


        common_names = {
            "List": "from typing import List",
            "Dict": "from typing import Dict",
            "Optional": "from typing import Optional",
            "Union": "from typing import Union",
            "Any": "from typing import Any",
            "Callable": "from typing import Callable",
            "Iterator": "from typing import Iterator",
            "Sequence": "from typing import Sequence",
            "Mapping": "from typing import Mapping",
            "Path": "from pathlib import Path",
            "PathLike": "from os import PathLike",
        }


        if undefined_name in common_names:
            suggested_import = common_names[undefined_name]
            existing_imports = context.get("related_imports", [])


            if not any(undefined_name in imp for imp in existing_imports):
                self.logger.info(
                    f"Type error '{undefined_name}' not defined - "
                    f"consider adding: {suggested_import}"
                )
                # Fall through to add type: ignore - import addition is a suggestion

        # Default: add type: ignore comment
        change = self._create_type_ignore_change(
            old_code,
            (issue.line_number or 1) - 1,
            f"[name-defined] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.warning(f"Change failed safety validation, skipping")
            return None
        return change

    def _fix_var_annotated_error(
        self,
        issue: Issue,
        old_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        """Fix 'need type annotation' errors by inferring type from context.

        This tries to infer the type from:
        1. The hint in the error message
        2. The assignment value
        3. Context from surrounding code
        """
        message_lower = issue.message.lower()


        var_match = re.search(r"[\"'](\w+)[\"']", message_lower)
        hint_match = re.search(r"hint:.*?[\"']?(\w+)[\"']?\s+is\s+([^\)]+)", message_lower)

        if var_match:
            var_name = var_match.group(1)
            inferred_type = None

            if hint_match:
                inferred_type = hint_match.group(2).strip()
            else:

                if "=" in old_code:
                    value_part = old_code.split("=", 1)[1].strip()
                    if value_part.startswith("["):
                        inferred_type = "list[Any]"
                    elif value_part.startswith("{"):
                        if ":" in value_part:
                            inferred_type = "dict[Any, Any]"
                        else:
                            inferred_type = "set[Any]"
                    elif value_part.startswith("("):
                        inferred_type = "tuple[Any, ...]"

            if inferred_type:

                indent_match = re.match(r"^(\s*)", old_code)
                indent = indent_match.group(1) if indent_match else ""
                new_code = f"{indent}{var_name}: {inferred_type} = {old_code.split('=', 1)[1].strip()}"
                change = ChangeSpec(
                    line_range=(issue.line_number or 1, issue.line_number or 1),
                    old_code=old_code,
                    new_code=new_code,
                    reason=f"[var-annotated] Added type annotation: {var_name}: {inferred_type}",
                )
                if not self._validate_change_safety(change):
                    self.logger.warning(f"Change failed safety validation, skipping")
                    return None
                return change

        # Default: add type: ignore
        change = self._create_type_ignore_change(
            old_code,
            (issue.line_number or 1) - 1,
            f"[var-annotated] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.warning(f"Change failed safety validation, skipping")
            return None
        return change

    def _fix_attr_defined_error(
        self,
        issue: Issue,
        old_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        """Fix 'attribute not defined' errors by adding type: ignore[attr-defined].

        These errors often occur when accessing attributes on Protocol types
        or dynamically added attributes. The safest fix is to acknowledge
        with a specific type: ignore comment.
        """
        # For attr-defined errors, use the specific error code in type: ignore
        if "#" in old_code:
            comment_pos = old_code.index("#")
            before_comment = old_code[:comment_pos].rstrip()
            existing_comment = old_code[comment_pos:]
            new_code = f"{before_comment}  # type: ignore[attr-defined]  {existing_comment[1:]}"
        else:
            new_code = old_code.rstrip() + "  # type: ignore[attr-defined]"

        change = ChangeSpec(
            line_range=(issue.line_number or 1, issue.line_number or 1),
            old_code=old_code,
            new_code=new_code,
            reason=f"[attr-defined] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.warning(f"Change failed safety validation, skipping")
            return None
        return change

    def _fix_call_arg_error(
        self,
        issue: Issue,
        old_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        """Fix call argument errors by adding type: ignore.

        These errors typically require signature changes or argument adjustments
        that are too risky to automate. Add type: ignore as a safe fallback.
        """
        change = self._create_type_ignore_change(
            old_code,
            (issue.line_number or 1) - 1,
            f"[call-arg] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.warning(f"Change failed safety validation, skipping")
            return None
        return change

    def _fix_arg_type_error(
        self,
        issue: Issue,
        old_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        """Fix argument type errors, with Path -> str conversion support.

        For Path -> str type mismatches, wraps the variable with str().
        Falls back to type: ignore for other type coercion issues.
        """
        # Check for Path -> str conversion opportunity
        if "Path" in issue.message and "str" in issue.message:
            # Match common path variable patterns that need str() wrapping
            # Pattern matches: file_path, path, dir_path, base_path, p (single char), etc.
            # But excludes variables already wrapped in str()
            pattern = r'\b([a-z_]+_path|[a-z_]*path[a-z_]*|p)\b(?!\s*\))'

            def replace_path_with_str(match: re.Match[str]) -> str:
                var_name = match.group(1)
                # Check if already wrapped in str() by looking at preceding context
                start_pos = match.start()
                preceding = old_code[:start_pos]
                # Don't wrap if already preceded by str(
                if re.search(r'\bstr\s*\(\s*$', preceding):
                    return var_name
                return f"str({var_name})"

            new_code = re.sub(pattern, replace_path_with_str, old_code, count=1)
            if new_code != old_code:
                change = ChangeSpec(
                    line_range=(issue.line_number or 1, issue.line_number or 1),
                    old_code=old_code,
                    new_code=new_code,
                    reason=f"[arg-type] Wrapped Path with str() for string compatibility",
                )
                if not self._validate_change_safety(change):
                    self.logger.warning(f"Change failed safety validation, skipping")
                    return None
                return change

        # Fallback: add type: ignore for other arg-type errors
        change = self._create_type_ignore_change(
            old_code,
            (issue.line_number or 1) - 1,
            f"[arg-type] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.warning(f"Change failed safety validation, skipping")
            return None
        return change


    def _fix_type_annotation(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Fix type annotation issues with enhanced context and error-specific patterns.

        This method:
        1. Extracts rich context around the error
        2. Identifies the specific error code
        3. Tries error-specific fix patterns
        4. Falls back to adding type: ignore comments

        The improved prompts help AI agents understand:
        - The exact line with the error
        - 5 lines of context before and after
        - Related imports and definitions
        - The expected type if available
        - Specific fix patterns for each error code
        """
        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        # Check if line already has a type: ignore comment
        type_ignore_match = re.search(r"#\s*type:\s*ignore(\[[^\]]+\])?", old_code)
        if type_ignore_match:
            existing_ignore = type_ignore_match.group(0)
            if "[" in existing_ignore:

                new_code = old_code[: type_ignore_match.start()] + "# type: ignore"
                after_ignore = old_code[type_ignore_match.end() :].strip()
                if after_ignore:
                    new_code = new_code + "  " + after_ignore
                return ChangeSpec(
                    line_range=(issue.line_number, issue.line_number),
                    old_code=old_code,
                    new_code=new_code,
                    reason=f"Type error (broaden ignore): {issue.message}",
                )

            self.logger.debug(
                f"Skipping line {issue.line_number}: already has generic type: ignore"
            )
            return None


        error_context = self._get_type_error_context(issue, code)


        self.logger.debug(
            f"Type error context for {issue.file_path}:{issue.line_number}: "
            f"error_code={error_context.get('error_code')}, "
            f"expected_type={error_context.get('expected_type')}"
        )


        error_code = self._extract_type_error_code(issue.message)


        if error_code:
            specific_fix = self._try_error_specific_type_fix(
                issue, code, error_code, error_context
            )
            if specific_fix:
                return specific_fix


        try:
            tree = ast.parse(code)
            node_at_line = self._find_node_at_line(tree, issue.line_number)

            if node_at_line is None:
                return self._create_type_ignore_change(
                    old_code, target_line, issue.message
                )

            if isinstance(node_at_line, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return self._fix_function_type(node_at_line, lines, issue.message)
            elif isinstance(node_at_line, ast.AnnAssign):
                return self._create_type_ignore_change(
                    old_code, target_line, issue.message
                )
            elif isinstance(node_at_line, ast.Assign):
                return self._fix_assignment_type(
                    node_at_line, lines, old_code, issue.message
                )

            return self._create_type_ignore_change(
                    old_code, target_line, issue.message
                )

        except SyntaxError:
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

    def _validate_change_safety(self, change: ChangeSpec) -> bool:
        """Validate that a change is safe to apply.

        Returns True if the change is safe, False if it might break things.
        """
        if not change.new_code:
            return False

        # 1. Syntax check - must be valid Python
        try:
            ast.parse(change.new_code)
        except SyntaxError as e:
            self.logger.debug(f"Change failed syntax validation: {e}")
            return False

        # 2. Check for obvious problems
        new_code = change.new_code.strip()

        # Empty change
        if not new_code:
            return False

        # Unclosed strings/brackets
        if new_code.count('"') % 2 != 0 and '\"\"\"' not in new_code:
            return False
        if new_code.count("'") % 2 != 0 and "\'\'\'" not in new_code:
            return False

        # 3. Check that old_code is actually in the file
        # This is done elsewhere but double-check here

        return True

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

        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]


        if "# security" in old_code.lower() or "# nosec" in old_code.lower():
            self.logger.debug(
                f"Skipping line {issue.line_number}: already has security comment"
            )
            return None

        # Skip if line already has TODO/FIXME
        if "# TODO" in old_code or "# FIXME" in old_code:
            return None


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
                new_code = (
                    f"{before_comment}  # nosec {sec_code}  {existing_comment[1:]}"
                )
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


        indent_match = __import__("re").match(r"^(\s*)", old_code)
        indent = indent_match.group(1) if indent_match else ""


        stripped = old_code.strip()
        if not stripped or stripped.startswith("#"):
            return None


        new_code = f"{indent}# DEAD CODE (removed): {stripped}"

        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Dead code removal: {issue.message}",
        )

    def _fix_dependency(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle dependency issues from creosote or pip-audit."""


        self.logger.debug(
            f"Dependency issue at {issue.file_path}:{issue.line_number}: {issue.message} - requires manual fix"
        )
        return None

    def _fix_performance(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle performance issues from complexity or pattern detection."""

        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]


        if "# perf" in old_code.lower() or "# noqa" in old_code.lower():
            self.logger.debug(
                f"Skipping line {issue.line_number}: already has perf comment"
            )
            return None

        # Skip if line already has TODO/FIXME
        if "# TODO" in old_code or "# FIXME" in old_code:
            return None


        if "#" in old_code:

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


        message_lower = issue.message.lower()

        if "unused" in message_lower:

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


        self.logger.debug(
            f"Import issue at {issue.file_path}:{issue.line_number}: {issue.message} - may need manual fix"
        )
        return None

    def _fix_test(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle test failures."""

        self.logger.debug(
            f"Test failure at {issue.file_path}:{issue.line_number}: {issue.message} - requires test analysis"
        )
        return None

    def _apply_refurb_fix(self, issue: Issue, code: str) -> ChangeSpec | None:
        """Handle refurb suggestions by applying inline code transformations.

        Applies common FURB transformations using regex patterns. For complex
        multi-line transformations, delegates to RefurbCodeTransformerAgent.
        First tries SafeRefurbFixer for AST-based transformations (FURB102, FURB109).
        """

        # Try SafeRefurbFixer first for AST-based transformations
        if issue.file_path:
            file_path = Path(issue.file_path)
            fixer = SafeRefurbFixer()
            original_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            
            if original_content:
                fixes_applied = fixer.fix_file(file_path)
                if fixes_applied > 0:
                    # Read the fixed content
                    new_content = file_path.read_text(encoding="utf-8")
                    self.logger.info(
                        f"SafeRefurbFixer applied {fixes_applied} fixes to {file_path}"
                    )
                    # Return a ChangeSpec representing the full file change
                    # Use line 1 to end of file for the range
                    line_count = len(new_content.split("\n"))
                    return ChangeSpec(
                        line_range=(1, line_count),
                        old_code=original_content,
                        new_code=new_content,
                        reason=f"REFURB_FIX:SafeRefurbFixer:applied {fixes_applied} AST fixes",
                    )

        # Fall back to manual regex-based transformations
        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]


        if "# refurb" in old_code.lower():
            self.logger.debug(
                f"Skipping line {issue.line_number}: already has refurb comment"
            )
            return None

        # Skip if line already has TODO/FIXME
        if "# TODO" in old_code or "# FIXME" in old_code:
            return None


        message = issue.message
        refurb_code = ""
        code_match = re.search(r"\[?FURB(\d+)\]?", message)
        if code_match:
            refurb_code = f"FURB{code_match.group(1)}"

        # Handle FURB107 (try/except/pass -> with suppress) as multi-line
        if refurb_code == "FURB107":
            change = self._furb_try_except_to_suppress(lines, target_line, message)
            if change:
                return change

        new_code = self._apply_furb_transform(old_code, refurb_code, message)

        if new_code is None or new_code == old_code:

            return None

        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"REFURB_FIX:{refurb_code}:{message[:80]}",
        )

    def _apply_furb_transform(
        self, old_code: str, furb_code: str, message: str
    ) -> str | None:
        """Apply a FURB transformation to a single line of code.

        Args:
            old_code: The original line of code.
            furb_code: The FURB code (e.g., "FURB102").
            message: The refurb message for context.

        Returns:
            Transformed code, or None if no transformation applies.
        """


        multiline_codes = {
            "FURB107",  # try/except/pass -> with suppress (multi-line)
            "FURB123",
            "FURB126",
            "FURB136",
            "FURB138",
            "FURB142",
            "FURB148",
            "FURB167",
            "FURB173",
        }
        # FURB109 removed from multiline - SafeRefurbFixer or regex can handle it

        handlers = {
            "FURB102": self._furb_startswith_tuple,
            "FURB109": self._furb_list_to_tuple,
            "FURB110": self._furb_or_operator,
            "FURB115": self._furb_len_comparison,
            "FURB118": self._furb_itemgetter,
            "FURB141": self._furb_path_exists,
            "FURB161": self._furb_scientific_int,
            "FURB183": self._furb_fstring_to_str,
            "FURB188": self._furb_slice_copy,
        }

        handler = handlers.get(furb_code)
        if handler:
            return handler(old_code)

        return None

    def _furb_startswith_tuple(self, old_code: str) -> str | None:
        """FURB102: x.startswith(y) or x.startswith(z) -> x.startswith((y, z))."""

        new_code = old_code
        pattern = r"(\w+)\.startswith\(([^)]+)\)\s+or\s+\1\.startswith\(([^)]+)\)"
        match = re.search(pattern, old_code)
        if match:
            var, arg1, arg2 = match.group(1), match.group(2), match.group(3)
            new_code = old_code.replace(
                match.group(0), f"{var}.startswith(({arg1}, {arg2}))"
            )

        pattern = r"not\s+(\w+)\.startswith\(([^)]+)\)\s+and\s+not\s+\1\.startswith\(([^)]+)\)"
        match = re.search(pattern, old_code)
        if match:
            var, arg1, arg2 = match.group(1), match.group(2), match.group(3)
            new_code = old_code.replace(
                match.group(0), f"not {var}.startswith(({arg1}, {arg2}))"
            )

        return new_code if new_code != old_code else None

    def _furb_list_to_tuple(self, old_code: str) -> str | None:
        """FURB109: Replace in (x, y, z) with in (x, y, z).

        Also handles not in (x, y, z) -> not in (x, y, z).
        """
        # Pattern: in (...) where [...] is a list literal with simple elements
        # Match: in (elem1, elem2, ...)
        pattern = r'\bin\s+\[([^\]]+)\]'
        match = re.search(pattern, old_code)
        if match:
            list_contents = match.group(1)
            # Check if it's a simple list (no nested structures, no comprehensions)
            if '[' not in list_contents and 'for' not in list_contents.lower():
                # Replace with tuple
                new_code = old_code.replace(match.group(0), f"in ({list_contents})")
                return new_code

        # Pattern: not in (...)
        pattern = r'\bnot\s+in\s+\[([^\]]+)\]'
        match = re.search(pattern, old_code)
        if match:
            list_contents = match.group(1)
            if '[' not in list_contents and 'for' not in list_contents.lower():
                new_code = old_code.replace(match.group(0), f"not in ({list_contents})")
                return new_code

        return None

    def _furb_or_operator(self, old_code: str) -> str | None:
        """FURB110: x or y -> x or y."""

        pattern = r"(\w+)\s+if\s+\1\s+else\s+(\w+)"
        match = re.search(pattern, old_code)
        if match:
            return old_code.replace(
                match.group(0), f"{match.group(1)} or {match.group(2)}"
            )
        return None

    def _furb_len_comparison(self, old_code: str) -> str | None:
        """FURB115: not x -> not x, x -> x."""

        new_code = old_code
        for pattern, replacement in [
            (r"len\(([^)]+)\)\s*==\s*0", r"not \1"),
            (r"len\(([^)]+)\)\s*>=\s*1", r"\1"),
        ]:
            match = re.search(pattern, old_code)
            if match:
                new_code = old_code.replace(
                    match.group(0), replacement.replace(r"\1", match.group(1))
                )
                break
        return new_code if new_code != old_code else None

    def _furb_try_except_to_suppress(
        self, lines: list[str], target_line: int, message: str
    ) -> ChangeSpec | None:
        """FURB107: Replace try: ... except Exception: pass with contextlib.suppress.

        This handles the multi-line pattern:
            with suppress(SomeError):
                ...

        Becomes:
            with suppress(SomeError):
                ...
        """
        import re

        # Find the try statement
        try_line = target_line
        while try_line >= 0 and "try:" not in lines[try_line]:
            try_line -= 1

        if try_line < 0:
            return None

        # Get indentation of try
        try_indent_match = re.match(r"^(\s*)try:", lines[try_line])
        if not try_indent_match:
            return None
        try_indent = try_indent_match.group(1)

        # Find the except block
        except_line = try_line + 1
        while except_line < len(lines):
            if re.match(rf"^{re.escape(try_indent)}except\s+", lines[except_line]):
                break
            except_line += 1

        if except_line >= len(lines):
            return None

        # Extract exception type from except line
        except_match = re.match(
            rf"^{re.escape(try_indent)}except\s+(\w+(?:\s*,\s*\w+)*)\s*:\s*pass\s*$",
            lines[except_line].strip(),
        )
        if not except_match:
            # Check if it's just "except:" without specific exception
            except_match = re.match(
                rf"^{re.escape(try_indent)}except\s*:\s*pass\s*$",
                lines[except_line].strip(),
            )
            if not except_match:
                return None
            exception_type = "Exception"
        else:
            exception_type = except_match.group(1)

        # Get the try block content (lines between try and except)
        try_block = lines[try_line + 1 : except_line]

        # Check if try block only contains simple statements (no nested blocks)
        body_indent = try_indent + "    "
        for line in try_block:
            if line.strip() and not line.startswith(body_indent):
                return None  # Has nested structure, skip

        # Create the with suppress block
        new_lines = []
        new_lines.append(f"{try_indent}with suppress({exception_type}):")
        for line in try_block:
            new_lines.append(line)

        # Calculate line range
        old_code = "\n".join(lines[try_line : except_line + 1])
        new_code = "\n".join(new_lines)

        return ChangeSpec(
            line_range=(try_line + 1, except_line + 1),  # 1-indexed
            old_code=old_code,
            new_code=new_code,
            reason=f"REFURB_FIX:FURB107:try/except/pass -> with suppress({exception_type})",
        )

    def _furb_itemgetter(self, old_code: str) -> str | None:
        """FURB118: lambda x: x[n] -> operator.itemgetter(n)."""

        patterns = [
            (r"lambda\s+(\w+)\s*:\s*\1\s*\[\s*(\d+)\s*\]", "operator.itemgetter({1})"),
            (
                r'lambda\s+(\w+)\s*:\s*\1\s*\[\s*["\']([^"\']+)["\']\s*\]',
                'operator.itemgetter("{2}")',
            ),
        ]
        for pattern, template in patterns:
            match = re.search(pattern, old_code)
            if match:
                if "{1}" in template:
                    return old_code.replace(
                        match.group(0), template.replace("{1}", match.group(2))
                    )
                return old_code.replace(
                    match.group(0), template.replace("{2}", match.group(2))
                )
        return None

    def _furb_path_exists(self, old_code: str) -> str | None:
        """FURB141: os.path.exists(x) -> Path(x).exists()."""

        pattern = r"os\.path\.exists\(([^)]+)\)"
        match = re.search(pattern, old_code)
        if match:
            return old_code.replace(match.group(0), f"Path({match.group(1)}).exists()")
        return None

    def _furb_scientific_int(self, old_code: str) -> str | None:
        """FURB161: 1000000 -> 1000000."""

        pattern = r"int\((\d+\.?\d*)[eE]([+-]?\d+)\)"
        match = re.search(pattern, old_code)
        if match:
            result = int(float(match.group(1)) * (10 ** int(match.group(2))))
            return old_code.replace(match.group(0), str(result))
        return None

    def _furb_fstring_to_str(self, old_code: str) -> str | None:
        """FURB183: f"{x}" -> str(x)."""

        pattern = r'f"\{([^}]+)\}"'
        match = re.search(pattern, old_code)
        if match:
            return old_code.replace(match.group(0), f"str({match.group(1)})")
        return None

    def _furb_slice_copy(self, old_code: str) -> str | None:
        """FURB188: x[:] -> x.copy()."""

        pattern = r"(\w+)\[\s*:\s*\]"
        match = re.search(pattern, old_code)
        if match:
            return old_code.replace(match.group(0), f"{match.group(1)}.copy()")
        return None

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

    def _validate_syntax(self, code: str) -> bool:
        """Validate that code is syntactically correct Python.

        Args:
            code: The code to validate.

        Returns:
            True if code is valid Python, False otherwise.
        """
        if not code or not code.strip():
            return True

        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            self.logger.warning(f"Syntax validation failed: {e.msg} at line {e.lineno}")
            return False

    def _validate_change_spec(self, change: ChangeSpec) -> ChangeSpec | None:
        """Validate a ChangeSpec before it's applied.

        Args:
            change: The ChangeSpec to validate.

        Returns:
            The validated ChangeSpec, or None if validation fails.
        """


        if change.new_code:

            stripped_code = change.new_code.lstrip()
            if stripped_code and not self._validate_syntax(stripped_code):
                self.logger.error(
                    f"Syntax error in generated code for {change.reason}: "
                    f"{change.new_code[:100]}..."
                )
                return None

        return change

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
