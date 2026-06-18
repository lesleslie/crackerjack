from __future__ import annotations

import ast
import logging
import os
import re
import textwrap
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..agents.base import Issue, IssueType
from ..models.fix_plan import ChangeSpec, FixPlan
from ..services.debug import get_ai_agent_debugger
from ..services.import_resolution import get_safe_import_spec
from ..services.refurb_fixer import SafeRefurbFixer

if TYPE_CHECKING:
    from ..models.protocols import AgentDelegatorProtocol, DebuggerProtocol

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
    "name-defined": "# Example: Name 'foo' is not defined",
    "var-annotated": "# Example: Need type annotation for 'x'",
    "attr-defined": "# Example: 'SomeObject' has no attribute 'some_attr' - Fix: Check Protocol compliance or add # type: ignore[attr-defined]",
    "call-arg": "# Example: Too many/few arguments for function",
    "union-attr": "# Example: Item of union has no attribute - Fix: Add type narrowing or type: ignore",
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
    def __init__(
        self,
        project_path: str,
        delegator: AgentDelegatorProtocol | None = None,
        debugger: DebuggerProtocol | None = None,
    ) -> None:
        self.project_path = project_path
        self.delegator = delegator
        self.debugger = debugger or get_ai_agent_debugger()
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

        if not changes:
            self.logger.debug(
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
                issue_message=issue.message,
                issue_stage=issue.stage,
                issue_details=issue.details.copy(),
            )

        risk_level = self._assess_risk(issue, changes, warnings)

        file_path_for_plan = issue.file_path
        if changes and issue.stage == "lychee":
            first_change = changes[0]

            reason_lower = first_change.reason.lower()
            if "lychee" in reason_lower and "excluded" in reason_lower:
                file_path_for_plan = ".lycheeignore"
                self.logger.info(
                    f"Lychee exclusion change detected, targeting .lycheeignore instead of {issue.file_path}"
                )

        plan = FixPlan(
            file_path=file_path_for_plan,
            issue_type=issue.type.value,
            changes=changes,
            rationale=self._generate_rationale(issue, approach, warnings),
            risk_level=risk_level,  # type: ignore
            validated_by="PlanningAgent",
            issue_message=issue.message,
            issue_stage=issue.stage,
            issue_details=issue.details.copy(),
        )

        self.logger.info(
            f"Created FixPlan with {len(changes)} changes, "
            f"risk={risk_level}, for {issue.file_path}:{issue.line_number}"
        )

        return plan

    def _determine_approach(self, issue: Issue, warnings: list[str]) -> str:

        approach = "default"
        rule_code = self._extract_lint_rule_code(issue)

        if rule_code == "SIM102":
            return "apply_style_fix"

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
        elif issue.type == IssueType.WARNING:
            approach = "fix_warning"

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

        complexity_fallback = self._build_complexity_fallback_change(
            issue, file_content
        )
        if complexity_fallback is not None:
            return [complexity_fallback]

        self._log_unable_to_auto_fix(issue)
        return []

    def _build_complexity_fallback_change(
        self, issue: Issue, file_content: str
    ) -> ChangeSpec | None:
        if issue.type != IssueType.COMPLEXITY:
            return None
        if not issue.line_number:
            return None

        lines = file_content.split("\n")
        if not (1 <= issue.line_number <= len(lines)):
            return None

        target_line = lines[issue.line_number - 1]
        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=target_line,
            new_code=target_line,
            reason=(
                "Complexity fallback: preserve issue context for RefactoringAgent "
                "when planner transform is unavailable"
            ),
        )

    def _log_unable_to_auto_fix(self, issue: Issue) -> None:
        metadata = {
            "issue_type": issue.type.value,
            "file_path": issue.file_path,
            "line_number": issue.line_number,
            "reason": issue.message[:160],
        }

        self.logger.debug(
            f"Unable to auto-fix {issue.type.value} at "
            f"{issue.file_path}:{issue.line_number}: {issue.message[:100]}"
        )

        if self.debugger.enabled:
            self.debugger.log_agent_activity(
                agent_name="PlanningAgent",
                activity="unable_to_auto_fix",
                issue_id=issue.id,
                metadata=metadata,
            )

    def _dispatch_fix(
        self, approach: str, issue: Issue, file_content: str
    ) -> ChangeSpec | None:
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
            "fix_warning": self._fix_warning,
        }
        handler = handlers.get(approach)
        if handler is None and approach.endswith("_cautious"):
            handler = handlers.get(approach.removesuffix("_cautious"))
        if handler is None:
            handler = self._generic_fix
        return handler(issue, file_content)

    def _try_delegator_fix(
        self,
        issue: Issue,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
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
                elif issue.type == IssueType.SECURITY:
                    return await self.delegator.delegate_to_security_specialist(
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

    def _refactor_for_clarity(self, issue: Issue, code: str) -> ChangeSpec | None:  # noqa: C901

        lines = code.split("\n")

        if issue.line_number and 1 <= issue.line_number <= len(lines):
            issue.line_number - 1

        return None

    def _get_type_error_context(self, issue: Issue, content: str) -> dict[str, Any]:
        lines = content.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return {}

        target_idx = issue.line_number - 1
        error_line = lines[target_idx]

        start_idx = max(0, target_idx - 5)
        end_idx = min(len(lines), target_idx + 6)
        context_before = lines[start_idx:target_idx]
        context_after = lines[target_idx + 1 : end_idx]

        related_imports: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                related_imports.append(stripped)

        related_definitions: list[str] = []
        with suppress(SyntaxError):
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    related_definitions.append(f"class {node.name}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args_str = ", ".join(arg.arg for arg in node.args.args)
                    return_type = ""
                    if node.returns:
                        return_type = f" -> {ast.unparse(node.returns)}"
                    related_definitions.append(
                        f"def {node.name}({args_str}){return_type}"
                    )

        error_code: str | None = None
        code_match = re.search(r"\[?([a-z]+-[a-z]+)\]?", issue.message.lower())
        if code_match:
            error_code = code_match.group(1)

        expected_type: str | None = None
        type_patterns = [
            r"expected\s+[\"']?([^\"', \]]+)[\"']?",
            r"got\s+[\"']?([^\"', \]]+)[\"']?",
            r"of\s+type\s+[\"']?([^\"', \]]+)[\"']?",
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
        message_lower = message.lower()

        code_match = re.search(r"\[([a-z]+(?:-[a-z]+)*)\]", message_lower)
        if code_match:
            return code_match.group(1)

        error_code_map = [
            (("is not defined", "undefined"), "name-defined"),
            (("need type annotation", "inference"), "var-annotated"),
            (("has no attribute", "attribute"), "attr-defined"),
            (("too many", "too few"), "call-arg"),
            (("argument", "type"), "arg-type", "mismatch"),
            (("union",), "union-attr"),
            (("return",), "return-value"),
            (("assignment", "assign"), "assignment"),
            (("index",), "index"),
            (("overload",), "call-overload"),
            (("override",), "override"),
        ]

        for item in error_code_map:
            patterns, code = item[0], item[1]
            if all(p in message_lower for p in patterns):
                return code  # type: ignore[return-value]

        return None

    def _try_error_specific_type_fix(
        self,
        issue: Issue,
        code: str,
        error_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
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
        message_lower = issue.message.lower()

        name_match = re.search(
            r"name [\"']?(\w+)[\"']? (is not defined|undefined)", message_lower
        )
        if not name_match:
            return None

        undefined_name = name_match.group(1)

        import_spec = self._name_defined_import_spec(undefined_name)
        if import_spec:
            module_name, symbol_name, suggested_import = import_spec
            file_content = context.get("file_content", "")
            if file_content and not self._has_import(
                file_content, module_name, symbol_name
            ):
                change = self._build_import_only_change(
                    file_content,
                    suggested_import,
                    f"[name-defined] Added missing import for {undefined_name}",
                )
                if change:
                    return change

            self.logger.info(
                f"Type error '{undefined_name}' not defined - "
                f"consider adding: {suggested_import}"
            )
            # Fall through to add type: ignore only if import insertion is not viable

        # Default: add type: ignore comment
        change = self._create_type_ignore_change(
            old_code,
            (issue.line_number or 1) - 1,
            f"[name-defined] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _has_import(self, content: str, module: str, symbol: str | None = None) -> bool:
        if symbol is None:
            pattern = rf"^\s*import\s+{re.escape(module)}(?:\s+as\s+\w+)?(?:\s*, |\s*$)"
            return bool(re.search(pattern, content, re.MULTILINE))

        pattern = (
            rf"^\s*from\s+{re.escape(module)}\s+import\s+.*\b{re.escape(symbol)}\b"
        )
        return bool(re.search(pattern, content, re.MULTILINE))

    def _name_defined_import_spec(
        self, undefined_name: str
    ) -> tuple[str, str | None, str] | None:
        spec = get_safe_import_spec(undefined_name)
        if spec is None:
            return None
        return spec.module_name, spec.symbol_name, spec.import_line

    def _build_import_only_change(
        self, content: str, import_line: str, reason: str
    ) -> ChangeSpec | None:
        new_content = self._insert_import_into_content(content, import_line)
        new_content = self._normalize_future_import_position(new_content)
        if new_content == content:
            return None

        change = self._full_file_change(content, new_content, reason)
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _find_import_insertion_index(self, lines: list[str]) -> int:
        start_index = 0
        try:
            tree = ast.parse("\n".join(lines))
        except SyntaxError:
            tree = None

        if tree and tree.body:
            first_node = tree.body[0]
            docstring = ast.get_docstring(tree, clean=False)
            if docstring and isinstance(first_node, ast.Expr):
                end_lineno = getattr(first_node, "end_lineno", first_node.lineno)
                start_index = end_lineno

        insert_index = start_index
        saw_import = False
        for i in range(start_index, len(lines)):
            stripped = lines[i].strip()
            if stripped.startswith(("import ", "from ")):
                saw_import = True
                insert_index = i + 1
                continue
            if not stripped or stripped.startswith("#"):
                continue
            if saw_import:
                return insert_index
            return i

        return insert_index

    def _insert_import_into_content(self, content: str, import_line: str) -> str:
        if import_line in content:
            return content

        lines = content.split("\n")
        insert_index = self._find_import_insertion_index(lines)
        if insert_index < 0:
            insert_index = 0
        if insert_index > len(lines):
            insert_index = len(lines)

        lines.insert(insert_index, import_line)
        return "\n".join(lines)

    def _insert_multiple_imports_into_content(
        self, content: str, import_lines: list[str]
    ) -> str:
        new_content = content
        for import_line in import_lines:
            if import_line in new_content:
                continue
            new_content = self._insert_import_into_content(new_content, import_line)
        return self._normalize_future_import_position(new_content)

    def _normalize_future_import_position(self, content: str) -> str:
        had_trailing_newline = content.endswith("\n")
        lines = content.split("\n")
        future_lines = [
            line for line in lines if line.strip().startswith("from __future__ import ")
        ]
        if not future_lines:
            return content

        remaining_lines = [
            line
            for line in lines
            if not line.strip().startswith("from __future__ import ")
        ]
        insert_index = self._find_future_import_insertion_index(remaining_lines)
        for future_line in reversed(future_lines):
            remaining_lines.insert(insert_index, future_line)
        normalized_content = "\n".join(remaining_lines)
        if had_trailing_newline and not normalized_content.endswith("\n"):
            normalized_content += "\n"
        return normalized_content

    def _full_file_change(
        self, content: str, new_content: str, reason: str
    ) -> ChangeSpec:
        line_count = max(1, len(content.split("\n")))
        return ChangeSpec(
            line_range=(1, line_count),
            old_code=content,
            new_code=new_content,
            reason=reason,
        )

    def _fix_var_annotated_error(
        self,
        issue: Issue,
        old_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        message_lower = issue.message.lower()

        var_match = re.search(r"[\"'](\w+)[\"']", message_lower)
        hint_match = re.search(
            r"hint:.*?[\"']?(\w+)[\"']?\s+is\s+([^\)]+)", message_lower
        )

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
                    self.logger.debug("Change failed safety validation, skipping")
                    return None
                return change

        # Default: add type: ignore
        change = self._create_type_ignore_change(
            old_code,
            (issue.line_number or 1) - 1,
            f"[var-annotated] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _fix_attr_defined_error(
        self,
        issue: Issue,
        old_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        if "Path" in issue.message and "startswith" in old_code:
            new_code = re.sub(
                r"(\b[A-Za-z_][\w\.]*)\.startswith\(",
                r"str(\1).startswith(",
                old_code,
                count=1,
            )
            if new_code != old_code:
                change = ChangeSpec(
                    line_range=(issue.line_number or 1, issue.line_number or 1),
                    old_code=old_code,
                    new_code=new_code,
                    reason="[attr-defined] Converted Path.startswith to path.startswith",
                )
                if not self._validate_change_safety(change):
                    self.logger.debug("Change failed safety validation, skipping")
                    return None
                return change

        # For attr-defined errors, use the specific error code in type: ignore
        if "#" in old_code:
            comment_pos = old_code.index("#")
            before_comment = old_code[:comment_pos].rstrip()
            existing_comment = old_code[comment_pos:]
            new_code = (
                f"{before_comment} # type: ignore[attr-defined] {existing_comment[1:]}"
            )
        else:
            new_code = old_code.rstrip() + " # type: ignore[attr-defined]"

        change = ChangeSpec(
            line_range=(issue.line_number or 1, issue.line_number or 1),
            old_code=old_code,
            new_code=new_code,
            reason=f"[attr-defined] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _fix_call_arg_error(
        self,
        issue: Issue,
        old_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        change = self._create_type_ignore_change(
            old_code,
            (issue.line_number or 1) - 1,
            f"[call-arg] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _fix_arg_type_error(
        self,
        issue: Issue,
        old_code: str,
        context: dict[str, Any],
    ) -> ChangeSpec | None:
        code = context.get("file_content", "")

        suppress_fix = self._try_fix_suppress_tuple(issue, old_code, code)
        if suppress_fix:
            return suppress_fix

        path_fix = self._try_fix_path_str(issue, old_code, code)
        if path_fix:
            return path_fix

        # Fallback: add type: ignore for other arg-type errors
        return self._fallback_type_ignore(issue, old_code)

    def _try_fix_suppress_tuple(
        self, issue: Issue, old_code: str, code: str
    ) -> ChangeSpec | None:
        if "suppress" not in issue.message.lower() or "with suppress((" not in old_code:
            return None

        new_code = re.sub(
            r"with suppress\(\(([^)]+)\)\)",
            lambda match: f"with suppress({match.group(1)})",
            old_code,
            count=1,
        )
        if new_code == old_code:
            return None

        if code and not self._has_import(code, "contextlib", "suppress"):
            full_content = self._insert_import_into_content(
                code, "from contextlib import suppress"
            )
            full_content = full_content.replace(old_code, new_code, 1)
            change = self._full_file_change(
                code,
                full_content,
                "[arg-type] Added suppress import and flattened exception tuple",
            )
            if not self._validate_change_safety(change):
                self.logger.debug("Change failed safety validation, skipping")
                return None
            return change

        change = ChangeSpec(
            line_range=(issue.line_number or 1, issue.line_number or 1),
            old_code=old_code,
            new_code=new_code,
            reason="[arg-type] Flattened suppress() exception tuple",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _try_fix_path_str(
        self, issue: Issue, old_code: str, code: str
    ) -> ChangeSpec | None:
        if "Path" not in issue.message or "str" not in issue.message:
            return None
        if "Path(" not in old_code:
            return None

        new_code = re.sub(
            r"Path\(([^)]+)\)",
            r"str(Path(\1))",
            old_code,
            count=1,
        )
        if new_code == old_code:
            return None

        change = ChangeSpec(
            line_range=(issue.line_number or 1, issue.line_number or 1),
            old_code=old_code,
            new_code=new_code,
            reason="[arg-type] Wrapped Path with str() for string compatibility",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None

        if code and not self._has_import(code, "pathlib", "Path"):
            full_content = self._insert_import_into_content(
                code, "from pathlib import Path"
            )
            full_content = full_content.replace(old_code, new_code, 1)
            change = self._full_file_change(
                code,
                full_content,
                "[arg-type] Added Path import and wrapped Path with str()",
            )
            if not self._validate_change_safety(change):
                self.logger.debug("Change failed safety validation, skipping")
                return None
            return change

        return change

    def _fallback_type_ignore(self, issue: Issue, old_code: str) -> ChangeSpec | None:
        change = self._create_type_ignore_change(
            old_code,
            (issue.line_number or 1) - 1,
            f"[arg-type] {issue.message}",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _fix_type_annotation(self, issue: Issue, code: str) -> ChangeSpec | None:
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
                    new_code = new_code + " " + after_ignore
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

            return self._create_type_ignore_change(old_code, target_line, issue.message)

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
            new_code = f"{before_comment} # type: ignore {existing_comment[1:]}"
        else:
            # Add type: ignore at end (no specific code to cover all type errors)
            new_code = old_code.rstrip() + " # type: ignore"

        return ChangeSpec(
            line_range=(line_index + 1, line_index + 1),
            old_code=old_code,
            new_code=new_code,
            reason=f"Type error: {message}",
        )

    def _validate_change_safety(self, change: ChangeSpec) -> bool:
        if not change.new_code:
            return False

        new_code = change.new_code.strip()

        if not new_code:
            return False

        if self._is_non_python_file(change.new_code):
            return True

        if self._validate_fragment_syntax(new_code):
            return True

        with suppress(SyntaxError):
            ast.parse(new_code)
            return True

        code_part = new_code.split("#", 1)[0] if "#" in new_code else new_code

        stripped = re.sub(r'"""(?:[^"\\]|\\.)*"""', '""', code_part)
        stripped = re.sub(r"'''(?:[^'\\]|\\.)*'''", "''", stripped)
        stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', stripped)
        stripped = re.sub(r"'(?:[^'\\]|\\.)*'", "''", stripped)

        pairs = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{"}
        stack: list[str] = []
        for ch in stripped:
            if ch in pairs:
                opening = pairs[ch]
                if stack and stack[-1] == opening:
                    stack.pop()
                elif ch in ("(", "[", "{"):
                    stack.append(ch)

        if stack:
            self.logger.debug(f"Change failed bracket validation: unmatched {stack}")
            return False

        return True

    def _is_non_python_file(self, content: str) -> bool:
        if not content:
            return False

        first_line = (
            content.strip().split("\n", 1)[0] if "\n" in content else content.strip()
        )

        non_python_markers = [
            "# ",
            "---",
            "...",
            "- ",
            "* ",
            "1. ",
            "| ",
            "http://",
            "https://",
        ]

        if first_line.startswith(tuple(non_python_markers)):
            return True

        python_keywords = sum(
            1
            for kw in (
                "def ",
                "class ",
                "import ",
                "from ",
                "if ",
                "for ",
                "while ",
                "try:",
            )
            if kw in content
        )
        line_count = content.count("\n")

        if line_count > 5 and python_keywords == 0:
            if "#" in content and (
                "##" in content or "**" in content or "```" in content
            ):
                return True

        return False

    def _find_enclosing_span(
        self,
        code: str,
        line_number: int,
        node_types: tuple[type[ast.AST], ...] | None = None,
    ) -> tuple[int, int] | None:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None

        best_span: tuple[int, int] | None = None
        best_width: int | None = None

        for node in ast.walk(tree):
            if node_types is not None and not isinstance(node, node_types):
                continue

            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start is None or end is None:
                continue
            if not (start <= line_number <= end):
                continue

            width = end - start
            if best_span is None or width < (best_width or width + 1):
                best_span = (start, end)
                best_width = width

        return best_span

    def _replace_line_in_span(
        self,
        code: str,
        line_number: int,
        replacer: Callable[[str], str],
        node_types: tuple[type[ast.AST], ...] | None = None,
    ) -> ChangeSpec | None:
        span = self._find_enclosing_span(code, line_number, node_types=node_types)
        if span is None:
            return None

        start_line, end_line = span
        lines = code.splitlines()
        if not (1 <= start_line <= end_line <= len(lines)):
            return None

        span_lines = lines[start_line - 1 : end_line]
        target_index = line_number - start_line
        if not (0 <= target_index < len(span_lines)):
            return None

        old_span = "\n".join(span_lines)
        new_span_lines = span_lines.copy()
        new_span_lines[target_index] = replacer(span_lines[target_index])
        new_span = "\n".join(new_span_lines)

        if new_span == old_span:
            return None

        return ChangeSpec(
            line_range=(start_line, end_line),
            old_code=old_span,
            new_code=new_span,
            reason="",
        )

    def _apply_style_fix(self, issue: Issue, code: str) -> ChangeSpec | None:
        lines = code.split("\n")
        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]
        rule_code = self._extract_lint_rule_code(issue)

        return self._apply_style_fix_for_rule(issue, code, old_code, rule_code)

    def _apply_style_fix_for_rule(
        self,
        issue: Issue,
        code: str,
        old_code: str,
        rule_code: str,
    ) -> ChangeSpec | None:
        rule_handlers = {
            "ARG001": lambda: self._fix_unused_argument(issue, code, old_code),
            "ARG002": lambda: self._fix_unused_argument(issue, code, old_code),
            "B904": lambda: self._fix_raise_from_exception(issue, code, old_code),
            "F811": lambda: self._fix_f811_redefinition(issue, code, old_code),
            "UP031": lambda: self._fix_up031_percent_format(issue, code, old_code),
            "E722": lambda: self._fix_bare_except(issue, code, old_code),
        }

        handler = rule_handlers.get(rule_code)
        if handler is not None:
            change = handler()  # type: ignore
            if change is not None:
                return change

        if rule_code in {"F403", "F405"}:
            return self._suppress_single_lint_rule(issue, old_code, rule_code)

        if "spelling" in issue.message.lower():
            spelling_fix = self._fix_spelling_issue(issue)
            if spelling_fix is not None:
                return spelling_fix

        suppressible_rules = {
            "B008",
            "E402",
            "ERA001",
            "PTH123",
            "RUF001",
            "SIM102",
        }
        if rule_code in suppressible_rules:
            return self._suppress_single_lint_rule(issue, old_code, rule_code)
        return None

    def _suppress_single_lint_rule(
        self, issue: Issue, old_code: str, rule_code: str
    ) -> ChangeSpec | None:
        if f"# noqa: {rule_code}" in old_code:
            return None
        if "# noqa:" in old_code:
            new_code = f"{old_code.rstrip()}, {rule_code}"
        else:
            new_code = f"{old_code.rstrip()} # noqa: {rule_code}"
        change = ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Applied targeted lint suppression for {rule_code}",
        )
        if self._validate_change_safety(change):
            return change
        return None

    def _extract_quoted_name(self, message: str) -> str | None:
        match = re.search(r"`([^`]+)`", message)
        if match:
            return match.group(1).strip()
        match = re.search(r"'([^']+)'", message)
        if match:
            return match.group(1).strip()
        return None

    def _fix_unused_argument(
        self,
        issue: Issue,
        code: str,
        old_code: str,
    ) -> ChangeSpec | None:
        if old_code.lstrip().startswith("#"):
            return None

        arg_name = self._extract_quoted_name(issue.message)
        if not arg_name:
            return None
        if arg_name.startswith("_"):
            return None

        replacement = f"_{arg_name}"
        new_code = re.sub(
            rf"(?<![\w]){re.escape(arg_name)}(?![\w])",
            replacement,
            old_code,
            count=1,
        )
        if new_code == old_code:
            return None

        change = ChangeSpec(
            line_range=(issue.line_number or 1, issue.line_number or 1),
            old_code=old_code,
            new_code=new_code,
            reason=f"Renamed unused argument {arg_name} to avoid ARG001/ARG002",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _fix_raise_from_exception(
        self,
        issue: Issue,
        code: str,
        old_code: str,
    ) -> ChangeSpec | None:
        if " from " in old_code or old_code.lstrip().startswith("#"):
            return None

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None

        parent_map = self._build_parent_map(tree)
        raise_node = self._find_raise_node(tree, issue.line_number)
        if raise_node is None:
            return None

        handler = self._find_exception_handler(parent_map, raise_node)
        if handler is None or not handler.name:
            return None

        change = self._build_raise_chain_change(code, raise_node, handler)
        if change is None:
            return None

        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _build_parent_map(self, tree: ast.AST) -> dict[ast.AST, ast.AST]:
        parent_map: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent
        return parent_map

    def _find_raise_node(self, tree: ast.AST, line_number: int) -> ast.Raise | None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.lineno == line_number:
                return node
        return None

    def _find_exception_handler(
        self, parent_map: dict[ast.AST, ast.AST], raise_node: ast.AST
    ) -> ast.ExceptHandler | None:
        current: ast.AST | None = raise_node
        while current is not None:
            current = parent_map.get(current)
            if isinstance(current, ast.ExceptHandler):
                return current
        return None

    def _build_raise_chain_change(
        self, code: str, raise_node: ast.Raise, handler: ast.ExceptHandler
    ) -> ChangeSpec | None:
        lines = code.splitlines()
        start_line = raise_node.lineno - 1
        end_line = (raise_node.end_lineno or raise_node.lineno) - 1
        if not (0 <= start_line <= end_line < len(lines)):
            return None

        old_span = "\n".join(lines[start_line : end_line + 1])
        new_span = self._apply_exception_chain(old_span, handler.name)

        return ChangeSpec(
            line_range=(start_line + 1, end_line + 1),
            old_code=old_span,
            new_code=new_span,
            reason=f"Added exception chaining from {handler.name} for B904",
        )

    def _apply_exception_chain(self, span: str, handler_name: str) -> str:
        span_lines = span.splitlines()
        last_line = span_lines[-1]

        code_part = last_line
        comment = ""
        if "#" in last_line:
            code_part, comment = last_line.split("#", 1)
            code_part = code_part.rstrip()
            comment = "#" + comment

        span_lines[-1] = f"{code_part} from {handler_name}"
        if comment:
            span_lines[-1] = f"{span_lines[-1]} {comment.lstrip()}"

        return "\n".join(span_lines)

    def _fix_up031_percent_format(
        self, issue: Issue, code: str, old_code: str
    ) -> ChangeSpec | None:
        if old_code.lstrip().startswith("#"):
            return None

        line_number = issue.line_number or 0
        rewritten = self._rewrite_percent_format(issue, code)
        if rewritten is not None:
            rewritten.reason = "Rewrote percent format to f-string"
            if self._validate_change_safety(rewritten):
                return rewritten

        span_change = self._replace_line_in_span(
            code if line_number else "",
            line_number,
            lambda line: (
                f"{line.rstrip()} # noqa: UP031"
                if "# noqa:" not in line
                else f"{line.rstrip()}, UP031"
            ),
            node_types=(ast.stmt,),
        )
        if span_change is not None:
            span_change.reason = "Applied targeted lint suppression for UP031"
            if self._validate_change_safety(span_change):
                return span_change

        return self._suppress_single_lint_rule(issue, old_code, "UP031")

    def _fix_bare_except(
        self, issue: Issue, code: str, old_code: str
    ) -> ChangeSpec | None:
        if old_code.lstrip().startswith("#"):
            return None

        line_number = issue.line_number or 0
        span_change = self._replace_line_in_span(
            code if line_number else "",
            line_number,
            lambda line: re.sub(
                r"^(\s*)except\s*:(.*)$",
                r"\1except Exception:\2",
                line,
            ),
            node_types=(ast.Try,),
        )
        if span_change is None:
            return None

        span_change.reason = "Replaced bare except with explicit Exception"
        if not self._validate_change_safety(span_change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return span_change

    def _rewrite_percent_format(  # noqa: C901
        self, issue: Issue, code: str
    ) -> ChangeSpec | None:
        if not issue.line_number:
            return None

        span = self._find_enclosing_span(
            code, issue.line_number, node_types=(ast.stmt,)
        )
        if span is None:
            return None

        start_line, end_line = span
        lines = code.splitlines()
        if not (1 <= start_line <= end_line <= len(lines)):
            return None

        span_source = "\n".join(lines[start_line - 1 : end_line])
        try:
            tree = ast.parse(span_source)
        except SyntaxError:
            return None

        class _PercentFormatRewriter(ast.NodeTransformer):
            def __init__(self) -> None:
                self.changed = False

            def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
                self.generic_visit(node)
                if not isinstance(node.op, ast.Mod):
                    return node
                if not isinstance(node.left, ast.Constant) or not isinstance(
                    node.left.value, str
                ):
                    return node

                rewritten = self._build_joined_str(node.left.value, node.right)
                if rewritten is None:
                    return node

                self.changed = True
                return ast.copy_location(rewritten, node)

            def _build_joined_str(  # noqa: C901
                self, format_string: str, rhs: ast.expr
            ) -> ast.JoinedStr | None:
                values = (
                    rhs.elts.copy() if isinstance(rhs, (ast.Tuple, ast.List)) else [rhs]
                )
                pieces: list[ast.expr] = []
                literal_parts: list[str] = []
                value_index = 0
                pos = 0

                def flush_literal() -> None:
                    if literal_parts:
                        pieces.append(ast.Constant("".join(literal_parts)))
                        literal_parts.clear()

                while pos < len(format_string):
                    char = format_string[pos]
                    if char != "%":
                        literal_parts.append(char)
                        pos += 1
                        continue

                    if pos + 1 >= len(format_string):
                        return None
                    if format_string[pos + 1] == "%":
                        literal_parts.append("%")
                        pos += 2
                        continue

                    spec_pos = pos + 1
                    while (
                        spec_pos < len(format_string)
                        and format_string[spec_pos] in "#0- +"
                    ):
                        spec_pos += 1
                    while (
                        spec_pos < len(format_string)
                        and format_string[spec_pos].isdigit()
                    ):
                        spec_pos += 1
                    if spec_pos < len(format_string) and format_string[spec_pos] == ".":
                        spec_pos += 1
                        while (
                            spec_pos < len(format_string)
                            and format_string[spec_pos].isdigit()
                        ):
                            spec_pos += 1
                    if spec_pos >= len(format_string):
                        return None

                    spec_type = format_string[spec_pos]
                    if value_index >= len(values):
                        return None

                    format_spec = ""
                    if spec_type in {"s", "r", "a"}:
                        if spec_pos != pos + 1:
                            return None
                        conversion = {"s": -1, "r": ord("r"), "a": ord("a")}[spec_type]
                    else:
                        conversion = -1
                        format_spec = format_string[pos + 1 : spec_pos + 1]

                    flush_literal()
                    pieces.append(
                        ast.FormattedValue(
                            value=values[value_index],
                            conversion=conversion,
                            format_spec=(
                                ast.JoinedStr(values=[ast.Constant(format_spec)])
                                if format_spec
                                else None
                            ),
                        )
                    )
                    value_index += 1
                    pos = spec_pos + 1

                flush_literal()
                if value_index != len(values):
                    return None

                return ast.JoinedStr(values=pieces)

        rewriter = _PercentFormatRewriter()
        transformed = rewriter.visit(tree)
        ast.fix_missing_locations(transformed)
        if not rewriter.changed:
            return None

        stmt = transformed.body[0] if transformed.body else None
        if not isinstance(stmt, ast.stmt):
            return None

        try:
            rewritten_stmt = ast.unparse(stmt)
        except Exception:
            return None

        original_indent = re.match(r"^\s*", span_source.splitlines()[0]).group(0)
        new_span = textwrap.indent(rewritten_stmt, original_indent)
        if new_span == span_source:
            return None

        return ChangeSpec(
            line_range=(start_line, end_line),
            old_code=span_source,
            new_code=new_span,
            reason="",
        )

    def _fix_spelling_issue(self, issue: Issue) -> ChangeSpec | None:
        match = re.search(
            r"Spelling:\s*'([^']+)'\s*should be\s*'([^']+)'",
            issue.message,
        )
        if not match:
            return None

        original = match.group(1)
        suggestion = match.group(2).split(", ", 1)[0].strip()
        if not original or not suggestion or original == suggestion:
            return None

        file_path = Path(issue.file_path) if issue.file_path else None
        if file_path is None or not file_path.exists():
            return None

        content = file_path.read_text(encoding="utf-8")
        new_content = re.sub(
            rf"(?<!\w){re.escape(original)}(?!\w)",
            suggestion,
            content,
            count=1,
        )
        if new_content == content:
            return None

        change = self._full_file_change(
            content,
            new_content,
            f"Fixed spelling issue: {original} -> {suggestion}",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _fix_f811_redefinition(
        self,
        issue: Issue,
        code: str,
        old_code: str,
    ) -> ChangeSpec | None:
        if old_code.lstrip().startswith("#"):
            return None

        duplicate_name = self._extract_quoted_name(issue.message)
        if not duplicate_name:
            return None

        if old_code.startswith("import "):
            new_code = self._alias_duplicate_import(old_code, duplicate_name)
            if new_code and new_code != old_code:
                change = ChangeSpec(
                    line_range=(issue.line_number or 1, issue.line_number or 1),
                    old_code=old_code,
                    new_code=new_code,
                    reason=f"Aliased duplicate import {duplicate_name} to avoid F811",
                )
                if not self._validate_change_safety(change):
                    self.logger.debug("Change failed safety validation, skipping")
                    return None
                return change

        if old_code.startswith("from "):
            new_code = self._alias_duplicate_from_import(old_code, duplicate_name)
            if new_code and new_code != old_code:
                change = ChangeSpec(
                    line_range=(issue.line_number or 1, issue.line_number or 1),
                    old_code=old_code,
                    new_code=new_code,
                    reason=f"Aliased duplicate from-import {duplicate_name} to avoid F811",
                )
                if not self._validate_change_safety(change):
                    self.logger.debug("Change failed safety validation, skipping")
                    return None
                return change

        if old_code.startswith(("def ", "async def ")):
            return self._rename_duplicate_function(issue, code, duplicate_name)

        if old_code.startswith("class "):
            return self._alias_conflicting_import(issue, code, duplicate_name)

        return None

    def _rename_duplicate_function(
        self,
        issue: Issue,
        code: str,
        duplicate_name: str,
    ) -> ChangeSpec | None:
        lines = code.splitlines()
        target_index = (issue.line_number or 1) - 1
        if not (0 <= target_index < len(lines)):
            return None

        def_line = lines[target_index]
        new_name = f"{duplicate_name}_cli"
        if re.search(rf"\b{re.escape(new_name)}\b", code):
            return None

        new_def_line = re.sub(
            rf"\b{re.escape(duplicate_name)}\b",
            new_name,
            def_line,
            count=1,
        )
        if new_def_line == def_line:
            return None

        call_pattern = re.compile(rf"(?<!\w){re.escape(duplicate_name)}\(\)")
        call_replaced = False
        new_lines = lines.copy()
        new_lines[target_index] = new_def_line
        for index in range(target_index + 1, len(new_lines)):
            new_line = call_pattern.sub(f"{new_name}()", new_lines[index], count=1)
            if new_line != new_lines[index]:
                new_lines[index] = new_line
                call_replaced = True
                break

        change = ChangeSpec(
            line_range=(issue.line_number or 1, len(lines)),
            old_code="\n".join(lines[target_index:]),
            new_code="\n".join(new_lines[target_index:]),
            reason=(
                f"Renamed duplicate function {duplicate_name} to avoid F811"
                + (" and updated a later call site" if call_replaced else "")
            ),
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _alias_conflicting_import(
        self,
        issue: Issue,
        code: str,
        duplicate_name: str,
    ) -> ChangeSpec | None:
        target_line = issue.line_number or 1
        import_span = self._find_prior_import_for_name(
            code, target_line, duplicate_name
        )
        if import_span is None:
            return None

        start_line, end_line, import_block = import_span
        if import_block.startswith("import "):
            new_alias_block = self._alias_duplicate_import(import_block, duplicate_name)
        else:
            new_alias_block = self._alias_duplicate_from_import(
                import_block, duplicate_name
            )

        if not new_alias_block or new_alias_block == import_block:
            return None

        change = ChangeSpec(
            line_range=(start_line, end_line),
            old_code=import_block,
            new_code=new_alias_block,
            reason=f"Aliased conflicting import {duplicate_name} to avoid F811",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _find_prior_import_for_name(
        self,
        code: str,
        target_line: int,
        duplicate_name: str,
    ) -> tuple[int, int, str] | None:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None

        lines = code.splitlines()
        best_span: tuple[int, int, str] | None = None
        best_end = 0

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            if not self._import_node_valid(node, target_line, lines):
                continue

            imported_names = self._get_imported_names(node)
            if duplicate_name not in imported_names:
                continue

            if self._is_aliased_import(node, duplicate_name):
                continue

            span = self._extract_import_span(node, lines)
            if span and span[1] > best_end:
                best_span = (span[0], span[1], span[2])
                best_end = span[1]

        return best_span

    def _import_node_valid(
        self, node: ast.AST, target_line: int, lines: list[str]
    ) -> bool:
        start_line = getattr(node, "lineno", None)
        end_line = getattr(node, "end_lineno", None)
        if start_line is None or end_line is None:
            return False
        if end_line >= target_line:
            return False
        if not (1 <= start_line <= end_line <= len(lines)):
            return False
        return True

    def _get_imported_names(self, node: ast.AST) -> list[str]:
        if isinstance(node, ast.Import):
            return [alias.name.split(".", 1)[0] for alias in node.names]  # type: ignore[union-attr]
        if isinstance(node, ast.ImportFrom):
            return [alias.name for alias in node.names]  # type: ignore[union-attr]
        return []

    def _is_aliased_import(self, node: ast.AST, duplicate_name: str) -> bool:
        if not isinstance(node, ast.ImportFrom):
            return False
        return any(
            alias.name == duplicate_name and alias.asname is not None
            for alias in node.names  # type: ignore[union-attr]
        )

    def _extract_import_span(
        self, node: ast.AST, lines: list[str]
    ) -> tuple[int, int, str] | None:
        start_line = getattr(node, "lineno", None)
        end_line = getattr(node, "end_lineno", None)
        if start_line is None or end_line is None:
            return None
        block = "\n".join(lines[start_line - 1 : end_line])
        return (start_line, end_line, block)

    def _alias_duplicate_import(self, old_code: str, duplicate_name: str) -> str | None:
        parts = old_code.split("import", 1)
        if len(parts) != 2:
            return None

        prefix, imported = parts
        items = [item.strip() for item in imported.split(", ")]
        changed = False
        for index, item in enumerate(items):
            if item == duplicate_name:
                items[index] = f"{duplicate_name} as _{duplicate_name}"
                changed = True
            elif item.startswith(f"{duplicate_name} as "):
                return None

        if not changed:
            return None

        return f"{prefix}import {', '.join(items)}"

    def _alias_duplicate_from_import(
        self, old_code: str, duplicate_name: str
    ) -> str | None:
        if f"{duplicate_name} as " in old_code:
            return None

        new_code = re.sub(
            rf"(?<![\w]){re.escape(duplicate_name)}(?![\w])",
            f"{duplicate_name} as _{duplicate_name}",
            old_code,
            count=1,
        )
        if new_code == old_code:
            return None

        return new_code

    def _extract_lint_rule_code(self, issue: Issue) -> str:
        message = issue.message.strip()
        message_match = re.match(r"^([A-Z]+\d+)\b", message)
        if message_match:
            return message_match.group(1)

        details = issue.details
        for detail in details:
            detail_match = re.search(r"\bcode:\s*([A-Z]+\d+)\b", detail, re.IGNORECASE)
            if detail_match:
                return detail_match.group(1).upper()

        in_message = re.search(r"\b([A-Z]+\d{3, 4})\b", message)
        if in_message:
            return in_message.group(1)

        return ""

    def _fix_documentation(self, issue: Issue, code: str) -> ChangeSpec | None:
        if not (issue.line_number and 1 <= issue.line_number <= len(code.split("\n"))):
            return None
        lines = code.split("\n")
        target_line = issue.line_number - 1
        old_code = lines[target_line]
        if "# ARCHIVED" in old_code:
            return None

        target_link = self._extract_documentation_link_target(issue)
        if target_link:
            rewritten = self._rewrite_markdown_link(
                old_code,
                issue.file_path,
                target_link,
            )
            if rewritten and rewritten != old_code:
                change = ChangeSpec(
                    line_range=(issue.line_number, issue.line_number),
                    old_code=old_code,
                    new_code=rewritten,
                    reason=f"Fixed broken documentation link: {target_link}",
                )
                if not self._validate_change_safety(change):
                    self.logger.debug("Change failed safety validation, skipping")
                    return None
                return change

            stripped = self._strip_markdown_link(old_code)
            if stripped and stripped != old_code:
                change = ChangeSpec(
                    line_range=(issue.line_number, issue.line_number),
                    old_code=old_code,
                    new_code=stripped,
                    reason=f"Removed broken documentation link: {target_link}",
                )
                if not self._validate_change_safety(change):
                    self.logger.debug("Change failed safety validation, skipping")
                    return None
                return change

        if issue.stage == "lychee":
            url_match = re.search(r"(https?://\S+)", old_code)
            if url_match:
                lychee_exclusion = self._add_lychee_exclusion(url_match.group(1))
                if lychee_exclusion:
                    self.logger.info(
                        f"Lychee URL cannot be fixed, excluding from checks: {url_match.group(1)}"
                    )
                    return lychee_exclusion
            return None

        url_match = re.search(r"(https?://\S+)", old_code)
        if not url_match:
            return None
        indent_match = re.match(r"^(\s*)", old_code)
        indent = indent_match.group(1) if indent_match else ""
        archived_line = f"{indent}{old_code.rstrip()} # ARCHIVED: {issue.message[:80]}"
        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=archived_line,
            reason=f"Archived broken link: {issue.message[:100]}",
        )

    def _extract_documentation_link_target(self, issue: Issue) -> str | None:
        candidates = [issue.message, *issue.details]
        patterns = (
            r"Broken link:\s*([^\s]+)",
            r"File not found:\s*([^\s]+)",
            r"Target file:\s*([^\s]+)",
        )
        for candidate in candidates:
            for pattern in patterns:
                match = re.search(pattern, candidate, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        return None

    def _add_lychee_exclusion(self, url: str) -> ChangeSpec | None:
        lycheignore_path = Path(".lycheeignore")
        if lycheignore_path.exists():
            existing_content = lycheignore_path.read_text()
            if url in existing_content:
                return None
        else:
            existing_content = ""
        new_content = existing_content + f"{url}\n"
        existing_line_count = len(existing_content.split("\n"))
        return ChangeSpec(
            line_range=(1, existing_line_count),
            old_code=existing_content,
            new_code=new_content,
            reason=f"Excluded lychee URL from checks: {url}",
        )

    def _rewrite_markdown_link(
        self, old_code: str, file_path: str | None, target_path: str
    ) -> str | None:
        if not file_path:
            return None

        target_path = target_path.split("#", 1)[0].split("?", 1)[0]
        source_file = Path(file_path)
        resolved_target = self._resolve_link_target(source_file, target_path)
        if resolved_target is None:
            return None

        replacement_path = os.path.relpath(resolved_target, start=source_file.parent)
        replacement_path = Path(replacement_path).as_posix()

        pattern = r"\]\(([^)]+)\)"
        match = re.search(pattern, old_code)
        if not match:
            return None

        current_target = match.group(1)
        anchor = ""
        if "#" in current_target:
            _current_path, anchor = current_target.split("#", 1)
            anchor = f"#{anchor}"

        new_target = f"{replacement_path}{anchor}"
        return old_code[: match.start(1)] + new_target + old_code[match.end(1) :]

    def _strip_markdown_link(self, old_code: str) -> str | None:
        stripped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", old_code)
        return stripped if stripped != old_code else None

    def _resolve_link_target(self, source_file: Path, target_path: str) -> Path | None:
        repo_root = Path(self.project_path)
        direct_candidate = (source_file.parent / target_path).resolve()
        if direct_candidate.exists():
            return direct_candidate

        target_name = Path(target_path).name
        candidates = [
            candidate
            for candidate in repo_root.rglob(target_name)
            if candidate.is_file()
            and ".git" not in candidate.parts
            and ".venv" not in candidate.parts
            and ".crackerjack" not in candidate.parts
            and "docs/archive" not in str(candidate)
        ]

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda candidate: len(
                os.path.relpath(candidate, start=source_file.parent)
            ),
        )

    def _security_hardening(self, issue: Issue, code: str) -> ChangeSpec | None:

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
                new_code = f"{before_comment} # nosec {sec_code} {existing_comment[1:]}"
            else:
                new_code = f"{before_comment} # nosec {existing_comment[1:]}"
        else:
            if sec_code:
                new_code = old_code.rstrip() + f" # nosec {sec_code}"
            else:
                new_code = old_code.rstrip() + " # nosec"

        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Security issue: {message}",
        )

    def _remove_dead_code(self, issue: Issue, code: str) -> ChangeSpec | None:
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

        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        if "# noqa" in old_code or "# UNUSED" in old_code or "# DEAD" in old_code:
            self.logger.debug(
                f"Skipping dependency issue at {issue.file_path}:{issue.line_number}: already handled"
            )
            return None

        message_lower = issue.message.lower()

        if any(
            kw in message_lower
            for kw in ("unused", "not used", "imported but unused", "unneeded import")
        ):
            if old_code.strip().startswith(("import ", "from ")):
                indent_match = re.match(r"^(\s*)", old_code)
                indent = indent_match.group(1) if indent_match else ""
                new_code = f"{indent}# UNUSED: {old_code.strip()}"
                return ChangeSpec(
                    line_range=(issue.line_number, issue.line_number),
                    old_code=old_code,
                    new_code=new_code,
                    reason=f"Unused dependency: {issue.message}",
                )

        if any(
            kw in message_lower
            for kw in ("missing", "not found", "cannot find", "no module")
        ):
            # Can't auto-install dependencies, add TODO
            indent_match = re.match(r"^(\s*)", old_code)
            indent = indent_match.group(1) if indent_match else ""
            comment = f"# TODO: {issue.message[:100]}"
            new_code = f"{old_code.rstrip()} {comment}" if old_code.strip() else comment
            return ChangeSpec(
                line_range=(issue.line_number, issue.line_number),
                old_code=old_code,
                new_code=new_code,
                reason=f"Missing dependency: {issue.message}",
            )

        self.logger.debug(
            f"Dependency issue at {issue.file_path}:{issue.line_number}: {issue.message} - requires manual fix"
        )
        return None

    def _fix_performance(self, issue: Issue, code: str) -> ChangeSpec | None:

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
            new_code = f"{before_comment} # perf: optimize {existing_comment[1:]}"
        else:
            new_code = old_code.rstrip() + " # perf: optimize"

        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Performance issue: {issue.message}",
        )

    def _fix_import(self, issue: Issue, code: str) -> ChangeSpec | None:
        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]
        message_lower = issue.message.lower()

        if "from __future__" in message_lower or "__future__" in message_lower:
            future_change = self._move_future_import(code)
            if future_change:
                return future_change

        if "__all__" in message_lower:
            exports_change = self._fix_all_exports_name_defined(code)
            if exports_change:
                return exports_change

        lint_code = self._extract_lint_rule_code(issue)
        if lint_code in {"F403", "F405"}:
            lint_fix = self._suppress_single_lint_rule(issue, old_code, lint_code)
            if lint_fix is not None:
                return lint_fix

        undefined_name = self._extract_import_name(issue)
        if undefined_name:
            fix = self._try_fix_undefined_name_import(undefined_name, code, old_code)
            if fix:
                return fix

        if "unused" in message_lower:
            return self._comment_out_unused_import(old_code, issue)

        self.logger.debug(
            f"Import issue at {issue.file_path}:{issue.line_number}: {issue.message} - may need manual fix"
        )
        return None

    def _try_fix_undefined_name_import(
        self, undefined_name: str, code: str, old_code: str
    ) -> ChangeSpec | None:

        if undefined_name == "t" and "import typing as t" not in code:
            change = self._build_import_only_change(
                code,
                "import typing as t",
                "[name-defined] Added typing alias import",
            )
            if change:
                return change

        if undefined_name.endswith("_AVAILABLE"):
            module_name = undefined_name.removesuffix("_AVAILABLE").lower()
            change = self._build_available_guard_change(
                code, module_name, undefined_name
            )
            if change:
                return change

        import_spec = self._name_defined_import_spec(undefined_name)
        if import_spec:
            module_name, symbol_name, suggested_import = import_spec
            if code and not self._has_import(code, module_name, symbol_name):
                change = self._build_import_only_change(
                    code,
                    suggested_import,
                    f"[name-defined] Added missing import for {undefined_name}",
                )
                if change:
                    return change

        if undefined_name and undefined_name[0].isupper():
            typing_import = self._infer_typing_import(undefined_name)
            if typing_import:
                change = self._build_import_only_change(
                    code,
                    typing_import,
                    f"[name-defined] Added typing import for {undefined_name}",
                )
                if change:
                    return change

        project_import = self._find_project_symbol_import(undefined_name)
        if project_import:
            change = self._build_import_only_change(
                code,
                project_import,
                f"[name-defined] Added project import for {undefined_name}",
            )
            if change:
                return change

        return None

    def _comment_out_unused_import(
        self, old_code: str, issue: Issue
    ) -> ChangeSpec | None:
        if not old_code.strip().startswith(("import ", "from ")):
            return None
        indent_match = __import__("re").match(r"^(\s*)", old_code)
        indent = indent_match.group(1) if indent_match else ""
        new_code = f"{indent}# UNUSED: {old_code.strip()}"
        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Unused import: {issue.message}",
        )

    def _fix_all_exports_name_defined(self, content: str) -> ChangeSpec | None:
        undefined_exports = self._collect_undefined_all_exports(content)
        if not undefined_exports:
            return None

        import_lines: list[str] = []
        for symbol in undefined_exports:
            import_line = self._find_project_symbol_import(symbol)
            if import_line and import_line not in import_lines:
                import_lines.append(import_line)

        if not import_lines:
            return None

        new_content = self._insert_multiple_imports_into_content(content, import_lines)
        if new_content == content:
            return None

        change = self._full_file_change(
            content,
            new_content,
            f"[name-defined] Added project imports for __all__ exports: {', '.join(undefined_exports)}",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _collect_undefined_all_exports(self, content: str) -> list[str]:
        all_match = re.search(r"__all__\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if not all_match:
            return []

        exports = re.findall(r"""['"]([A-Za-z_]\w*)['"]""", all_match.group(1))
        if not exports:
            return []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        defined_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                defined_names.add(node.target.id)
            elif isinstance(node, ast.Import):
                defined_names.update(
                    alias.asname or alias.name.split(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                defined_names.update(alias.asname or alias.name for alias in node.names)

        return [name for name in exports if name not in defined_names]

    def _extract_import_name(self, issue: Issue) -> str | None:
        patterns = (
            r"Name [`\"']?([A-Za-z_][\w\.]*)[`\"']? is not defined",
            r"Undefined name [`\"']?([A-Za-z_][\w\.]*)[`\"']?",
            r"Name [`\"']?([A-Za-z_][\w\.]*)[`\"']?",
        )
        candidates = [issue.message, *issue.details]
        for candidate in candidates:
            for pattern in patterns:
                match = re.search(pattern, candidate)
                if match:
                    return match.group(1)
        return None

    def _move_future_import(self, content: str) -> ChangeSpec | None:
        lines = content.split("\n")
        future_lines = [
            line for line in lines if line.strip().startswith("from __future__ import ")
        ]
        if not future_lines:
            return None

        remaining_lines = [
            line
            for line in lines
            if not line.strip().startswith("from __future__ import ")
        ]

        insert_index = self._find_future_import_insertion_index(remaining_lines)
        for future_line in reversed(future_lines):
            remaining_lines.insert(insert_index, future_line)

        new_content = "\n".join(remaining_lines)
        if content.endswith("\n"):
            new_content += "\n"

        if new_content == content:
            return None

        change = self._full_file_change(
            content,
            new_content,
            "Moved __future__ import to the top of the file",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _find_future_import_insertion_index(self, lines: list[str]) -> int:
        insert_index = 0
        try:
            tree = ast.parse("\n".join(lines))
        except SyntaxError:
            tree = None

        if tree and tree.body:
            first_node = tree.body[0]
            docstring = ast.get_docstring(tree, clean=False)
            if docstring and isinstance(first_node, ast.Expr):
                insert_index = getattr(first_node, "end_lineno", first_node.lineno)

        while insert_index < len(lines):
            stripped = lines[insert_index].strip()
            if not stripped or stripped.startswith("#"):
                insert_index += 1
                continue
            break

        return insert_index

    def _build_available_guard_change(
        self, content: str, module_name: str, constant_name: str
    ) -> ChangeSpec | None:
        guard_block = "\n".join(
            [
                "try:",
                f" import {module_name}",
                f" {constant_name} = True",
                "except ImportError:",
                f" {constant_name} = False",
            ]
        )

        if guard_block in content:
            return None

        change = self._full_file_change(
            content,
            self._insert_import_block(content, guard_block),
            f"Added availability guard for {module_name}",
        )
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _insert_import_block(self, content: str, block: str) -> str:
        lines = content.split("\n")
        insert_index = self._find_import_insertion_index(lines)
        block_lines = block.split("\n")
        for offset, line in enumerate(block_lines):
            lines.insert(insert_index + offset, line)
        new_content = "\n".join(lines)
        if content.endswith("\n"):
            new_content += "\n"
        return new_content

    def _infer_typing_import(self, undefined_name: str) -> str | None:
        typing_names = {
            "Any",
            "Callable",
            "ClassVar",
            "Dict",
            "Final",
            "Iterable",
            "Iterator",
            "List",
            "Mapping",
            "MutableMapping",
            "MutableSequence",
            "Optional",
            "Protocol",
            "Sequence",
            "Set",
            "Tuple",
            "TypedDict",
            "Union",
        }
        if undefined_name in typing_names:
            return f"from typing import {undefined_name}"
        return None

    def _find_project_symbol_import(self, symbol: str) -> str | None:
        project_root = Path(self.project_path)
        if not project_root.exists():
            return None

        definition_patterns = (
            rf"^\s*class\s+{re.escape(symbol)}\b",
            rf"^\s*def\s+{re.escape(symbol)}\b",
            rf"^\s*{re.escape(symbol)}\s*=",
        )

        candidates: list[Path] = []
        for path in project_root.rglob("*.py"):
            if any(part.startswith(".") for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if any(
                re.search(pattern, text, re.MULTILINE)
                for pattern in definition_patterns
            ):
                candidates.append(path)

        if not candidates:
            return None

        module_name = self._path_to_module_name(candidates[0])
        if not module_name:
            return None
        return f"from {module_name} import {symbol}"

    def _path_to_module_name(self, path: Path) -> str | None:
        try:
            relative = path.relative_to(Path(self.project_path))
        except ValueError:
            return None

        if relative.name == "__init__.py":
            relative = relative.parent
        else:
            relative = relative.with_suffix("")

        parts = [part for part in relative.parts if part]
        if not parts:
            return None
        return ".".join(parts)

    def _fix_test(self, issue: Issue, code: str) -> ChangeSpec | None:

        self.logger.debug(
            f"Test failure at {issue.file_path}:{issue.line_number}: {issue.message} - requires test analysis"
        )
        return None

    def _apply_refurb_fix(self, issue: Issue, code: str) -> ChangeSpec | None:

        fixer_change = self._try_safe_refurb_fixer(issue)
        if fixer_change:
            return fixer_change

        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        if self._should_skip_refurb_line(old_code, issue.line_number):
            return None

        refurb_code = self._extract_refurb_code(issue.message)
        if refurb_code == "FURB107":
            return self._handle_refurb_107(lines, target_line, issue.message, code)

        return self._apply_generic_refurb_fix(issue, old_code, code, refurb_code)

    def _try_safe_refurb_fixer(self, issue: Issue) -> ChangeSpec | None:
        if not issue.file_path:
            return None

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return None

        original_content = file_path.read_text(encoding="utf-8")
        fixer = SafeRefurbFixer()
        new_content, fixes_applied = fixer._apply_fixes(original_content)

        if fixes_applied <= 0:
            return None

        self.logger.info(
            f"SafeRefurbFixer applied {fixes_applied} fixes to {file_path} (in-memory)"
        )
        line_count = len(new_content.split("\n"))

        return ChangeSpec(
            line_range=(1, line_count),
            old_code=original_content,
            new_code=new_content,
            reason=f"REFURB_FIX: SafeRefurbFixer:applied {fixes_applied} AST fixes",
        )

    def _should_skip_refurb_line(self, old_code: str, line_number: int) -> bool:
        if "# refurb" in old_code.lower():
            self.logger.debug(
                f"Skipping line {line_number}: already has refurb comment"
            )
            return True
        if "# TODO" in old_code or "# FIXME" in old_code:
            return True
        return False

    def _extract_refurb_code(self, message: str) -> str:
        code_match = re.search(r"\[?FURB(\d+)\]?", message)
        return f"FURB{code_match.group(1)}" if code_match else ""

    def _handle_refurb_107(
        self, lines: list[str], target_line: int, message: str, code: str
    ) -> ChangeSpec | None:
        change = self._furb_try_except_to_suppress(lines, target_line, message)
        if change is None:
            return None

        import_line = self._required_refurb_import(code, "FURB107", change.new_code)
        if import_line:
            return self._build_imported_refurb_change(
                code,
                change.old_code,
                change.new_code,
                import_line,
                "REFURB_FIX: FURB107: added suppress import",
            )
        return change

    def _apply_generic_refurb_fix(
        self, issue: Issue, old_code: str, code: str, refurb_code: str
    ) -> ChangeSpec | None:
        message = issue.message
        new_code = self._apply_furb_transform(old_code, refurb_code, message)

        if new_code is None or new_code == old_code:
            return None

        import_line = self._required_refurb_import(code, refurb_code, new_code)
        if import_line:
            return self._build_imported_refurb_change(
                code,
                old_code,
                new_code,
                import_line,
                self._build_refurb_reason(refurb_code, message),
            )

        return ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=self._build_refurb_reason(refurb_code, message),
        )

    def _build_refurb_reason(self, refurb_code: str, message: str) -> str:
        reason_map = {
            "FURB118": "REFURB_FIX: FURB118: added operator import",
            "FURB141": "REFURB_FIX: FURB141: added Path import",
        }
        return reason_map.get(refurb_code, f"REFURB_FIX:{refurb_code}:{message[:80]}")

    def _apply_furb_transform(
        self, old_code: str, furb_code: str, message: str
    ) -> str | None:

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

        pattern = r"(\w+)\.endswith\(([^)]+)\)\s+or\s+\1\.endswith\(([^)]+)\)"
        match = re.search(pattern, old_code)
        if match:
            var, arg1, arg2 = match.group(1), match.group(2), match.group(3)
            new_code = old_code.replace(
                match.group(0), f"{var}.endswith(({arg1}, {arg2}))"
            )

        pattern = (
            r"not\s+(\w+)\.endswith\(([^)]+)\)\s+and\s+not\s+\1\.endswith\(([^)]+)\)"
        )
        match = re.search(pattern, old_code)
        if match:
            var, arg1, arg2 = match.group(1), match.group(2), match.group(3)
            new_code = old_code.replace(
                match.group(0), f"not {var}.endswith(({arg1}, {arg2}))"
            )

        return new_code if new_code != old_code else None

    def _furb_list_to_tuple(self, old_code: str) -> str | None:

        pattern = r"\bin\s+\[([^\]]+)\]"
        match = re.search(pattern, old_code)
        if match:
            list_contents = match.group(1)

            if "[" not in list_contents and "for" not in list_contents.lower():
                new_code = old_code.replace(match.group(0), f"in ({list_contents})")
                return new_code

        pattern = r"\bnot\s+in\s+\[([^\]]+)\]"
        match = re.search(pattern, old_code)
        if match:
            list_contents = match.group(1)
            if "[" not in list_contents and "for" not in list_contents.lower():
                new_code = old_code.replace(match.group(0), f"not in ({list_contents})")
                return new_code

        return None

    def _furb_or_operator(self, old_code: str) -> str | None:

        pattern = r"(\w+)\s+if\s+\1\s+else\s+(\w+)"
        match = re.search(pattern, old_code)
        if match:
            return old_code.replace(
                match.group(0), f"{match.group(1)} or {match.group(2)}"
            )
        return None

    def _furb_len_comparison(self, old_code: str) -> str | None:

        new_code = old_code
        for pattern, replacement in (
            (r"len\(([^)]+)\)\s*==\s*0", r"not \1"),
            (r"len\(([^)]+)\)\s*>=\s*1", r"\1"),
        ):
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

        try_line = self._find_try_line(lines, target_line)
        if try_line < 0:
            return None

        try_indent = self._extract_try_indent(lines, try_line)
        if try_indent is None:
            return None

        except_line = self._find_except_line(lines, try_indent, try_line)
        if except_line < 0:
            return None

        exception_type = self._parse_exception_type_from_except(
            lines[except_line], try_indent
        )
        if exception_type is None:
            return None

        try_block = lines[try_line + 1 : except_line]
        if not self._is_valid_try_block(try_block, try_indent):
            return None

        new_code = self._build_suppress_block(try_indent, exception_type, try_block)
        old_code = "\n".join(lines[try_line : except_line + 1])

        return ChangeSpec(
            line_range=(try_line + 1, except_line + 1),
            old_code=old_code,
            new_code=new_code,
            reason=f"REFURB_FIX: FURB107:try/except/pass -> with suppress({exception_type})",
        )

    def _find_try_line(self, lines: list[str], target_line: int) -> int:
        try_line = target_line
        while try_line >= 0 and "try:" not in lines[try_line]:
            try_line -= 1
        return try_line

    def _extract_try_indent(self, lines: list[str], try_line: int) -> str | None:
        import re

        try_indent_match = re.match(r"^(\s*)try:", lines[try_line])
        return try_indent_match.group(1) if try_indent_match else None

    def _find_except_line(
        self, lines: list[str], try_indent: str, try_line: int
    ) -> int:
        import re

        except_line = try_line + 1
        while except_line < len(lines):
            if re.match(rf"^{re.escape(try_indent)}except\s+", lines[except_line]):
                break
            except_line += 1
        return except_line if except_line < len(lines) else -1

    def _parse_exception_type_from_except(
        self, except_line: str, try_indent: str
    ) -> str | None:
        import re

        except_match = re.match(
            rf"^{re.escape(try_indent)}except\s+(\w+(?:\s*, \s*\w+)*)\s*:\s*pass\s*$",
            except_line,
        )
        if not except_match:
            except_match = re.match(
                rf"^{re.escape(try_indent)}except\s*:\s*pass\s*$",
                except_line,
            )
            if not except_match:
                return None
            return "Exception"
        return except_match.group(1)

    def _is_valid_try_block(self, try_block: list[str], try_indent: str) -> bool:
        body_indent = try_indent + " "
        for line in try_block:
            if line.strip() and not line.startswith(body_indent):
                return False
        return True

    def _build_suppress_block(
        self, try_indent: str, exception_type: str, try_block: list[str]
    ) -> str:
        exception_names = [
            name.strip() for name in exception_type.split(", ") if name.strip()
        ]
        new_lines = [f"{try_indent}with suppress({', '.join(exception_names)}):"]
        new_lines.extend(try_block)
        return "\n".join(new_lines)

    def _required_refurb_import(
        self, code: str, refurb_code: str, new_code: str
    ) -> str | None:
        import_map = {
            "FURB107": ("contextlib", "suppress", "from contextlib import suppress"),
            "FURB118": ("operator", None, "import operator"),
            "FURB141": ("pathlib", "Path", "from pathlib import Path"),
        }

        spec = import_map.get(refurb_code)
        if spec is None:
            return None

        module_name, symbol_name, import_line = spec
        if symbol_name is None:
            if self._has_import(code, module_name):
                return None
            return import_line

        if refurb_code == "FURB141" and "Path(" not in new_code:
            return None

        if self._has_import(code, module_name, symbol_name):
            return None
        return import_line

    def _build_imported_refurb_change(
        self,
        content: str,
        old_code: str,
        new_code: str,
        import_line: str,
        reason: str,
    ) -> ChangeSpec | None:
        new_content = self._insert_import_into_content(content, import_line)
        new_content = new_content.replace(old_code, new_code, 1)
        change = self._full_file_change(content, new_content, reason)
        if not self._validate_change_safety(change):
            self.logger.debug("Change failed safety validation, skipping")
            return None
        return change

    def _furb_itemgetter(self, old_code: str) -> str | None:

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

        pattern = r"os\.path\.exists\(([^)]+)\)"
        match = re.search(pattern, old_code)
        if match:
            return old_code.replace(match.group(0), f"Path({match.group(1)}).exists()")
        return None

    def _furb_scientific_int(self, old_code: str) -> str | None:

        pattern = r"int\((\d+\.?\d*)[eE]([+-]?\d+)\)"
        match = re.search(pattern, old_code)
        if match:
            result = int(float(match.group(1)) * (10 ** int(match.group(2))))
            return old_code.replace(match.group(0), str(result))
        return None

    def _furb_fstring_to_str(self, old_code: str) -> str | None:

        pattern = r'f"\{([^}]+)\}"'
        match = re.search(pattern, old_code)
        if match:
            return old_code.replace(match.group(0), f"str({match.group(1)})")
        return None

    def _furb_slice_copy(self, old_code: str) -> str | None:

        pattern = r"(\w+)\[\s*:\s*\]"
        match = re.search(pattern, old_code)
        if match:
            return old_code.replace(match.group(0), f"{match.group(1)}.copy()")
        return None

    def _generic_fix(self, issue: Issue, code: str) -> ChangeSpec | None:
        return self._apply_style_fix(issue, code)

    def _fix_warning(self, issue: Issue, code: str) -> ChangeSpec | None:
        lines = code.split("\n")

        if not (issue.line_number and 1 <= issue.line_number <= len(lines)):
            return None

        target_line = issue.line_number - 1
        old_code = lines[target_line]

        if "# noqa" in old_code or "# type: ignore" in old_code:
            self.logger.debug(
                f"Skipping warning at {issue.file_path}:{issue.line_number}: already handled"
            )
            return None

        message = issue.message

        # Add appropriate noqa comment for common warnings
        code_match = re.search(r"[A-Z]+(\d+)?", message)
        warning_code = code_match.group(0) if code_match else ""

        if "#" in old_code:
            comment_pos = old_code.index("#")
            before_comment = old_code[:comment_pos].rstrip()
            existing_comment = old_code[comment_pos:]
            if warning_code:
                new_code = (
                    f"{before_comment} # noqa: {warning_code} {existing_comment[1:]}"
                )
            else:
                new_code = f"{before_comment} # noqa: warning {existing_comment[1:]}"
        else:
            if warning_code:
                new_code = old_code.rstrip() + f" # noqa: {warning_code}"
            else:
                new_code = old_code.rstrip() + " # noqa: warning"

        change = ChangeSpec(
            line_range=(issue.line_number, issue.line_number),
            old_code=old_code,
            new_code=new_code,
            reason=f"Warning suppression: {message}",
        )
        if not self._validate_change_safety(change):
            return None
        return change

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
        if not code or not code.strip():
            return True

        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            self.logger.debug(
                f"Syntax validation failed for module parse: {e.msg} at line {e.lineno}"
            )
            return False

    def _validate_fragment_syntax(self, code: str) -> bool:
        if not code or not code.strip():
            return True

        fragment = code.rstrip()
        code_body = fragment.split("#", 1)[0].rstrip()
        body_wrapper = "def __crackerjack_validate__():\n"
        body_fragment = textwrap.indent(code_body, " ")
        candidates = [body_wrapper + body_fragment]

        if code_body.endswith(":"):
            candidates.append(f"{body_wrapper}{body_fragment}\n pass")

        if code_body.endswith("):") and not code_body.startswith("with "):
            candidates.extend(
                (
                    f"{body_wrapper}{body_fragment}\n pass",
                    f"{body_wrapper}try:\n{body_fragment}\n pass\nexcept:\n pass",
                )
            )

        if code_body.startswith("with ") and code_body.endswith(":"):
            with_body = code_body[len("with ") :]
            inner = f" try:\n with {with_body}\n pass\n except:\n pass"
            candidates.append(f"{body_wrapper}{inner}")

        parameter_lines = [
            line.strip() for line in code_body.splitlines() if line.strip()
        ]
        if parameter_lines and all(
            not line.startswith(
                ("def ", "class ", "return ", "raise ", "import ", "from ")
            )
            for line in parameter_lines
        ):
            parameter_wrapper = "def __crackerjack_validate__(\n"
            parameter_fragment = textwrap.indent(code_body, " ")
            candidates.append(f"{parameter_wrapper}{parameter_fragment}\n):\n pass")

        last_error: SyntaxError | None = None
        for candidate in candidates:
            try:
                ast.parse(candidate)
                return True
            except SyntaxError as e:
                last_error = e

        if last_error is None:
            return False

        self.logger.debug(
            "Syntax validation failed for fragment parse: "
            f"{last_error.msg} at line {last_error.lineno}"
        )
        return False

    def _is_comment_only_change(self, change: ChangeSpec) -> bool:
        old_body = change.old_code.split("#", 1)[0].rstrip()
        new_body = change.new_code.split("#", 1)[0].rstrip()
        return bool(
            old_body and old_body == new_body and change.old_code != change.new_code
        )

    def _validate_change_spec(self, change: ChangeSpec) -> ChangeSpec | None:
        reason_lower = change.reason.lower()
        if any(
            marker in reason_lower
            for marker in (
                "documentation link",
                "broken link",
                "changelog",
                "lychee",
                "lycheignore",
            )
        ):
            return change

        if change.new_code:
            if self._is_comment_only_change(change):
                return change

            if self._is_non_python_file(change.new_code):
                return change
            candidate_code = change.new_code.rstrip()
            if candidate_code:
                syntax_valid = self._validate_syntax(candidate_code)

                if not syntax_valid and not (
                    candidate_code.endswith(":")
                    and self._validate_fragment_syntax(candidate_code)
                ):
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
