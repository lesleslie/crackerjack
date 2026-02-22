import ast
import logging
import re
import typing as t
from typing import TYPE_CHECKING

from .base import FixResult, Issue, IssueType, Priority, agent_registry
from .formatting_agent import FormattingAgent
from .import_optimization_agent import ImportOptimizationAgent
from .proactive_agent import ProactiveAgent
from .refactoring_agent import RefactoringAgent
from .security_agent import SecurityAgent

if TYPE_CHECKING:
    from ..models.fix_plan import FixPlan

logger = logging.getLogger(__name__)


class ArchitectAgent(ProactiveAgent):
    def __init__(self, context) -> None:
        super().__init__(context)

        self._refactoring_agent = RefactoringAgent(context)
        self._formatting_agent = FormattingAgent(context)
        self._import_agent = ImportOptimizationAgent(context)
        self._security_agent = SecurityAgent(context)

    def get_supported_types(self) -> set[IssueType]:
        return {
            IssueType.TYPE_ERROR,
            IssueType.TEST_ORGANIZATION,
        }

    async def can_handle(self, issue: Issue) -> float:

        if issue.type == IssueType.TYPE_ERROR:
            return 0.5

        if issue.type == IssueType.TEST_ORGANIZATION:
            return 0.1

        return 0.0

    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        if await self._needs_external_specialist(issue):
            return await self._get_specialist_plan(issue)

        return await self._get_internal_plan(issue)

    async def _needs_external_specialist(self, issue: Issue) -> bool:
        if issue.type == IssueType.COMPLEXITY:
            return True

        return issue.type == IssueType.DRY_VIOLATION

    async def _get_specialist_plan(self, issue: Issue) -> dict[str, t.Any]:
        return {
            "strategy": "external_specialist_guided",
            "specialist": "crackerjack-architect",
            "approach": self._get_specialist_approach(issue),
            "patterns": self._get_recommended_patterns(issue),
            "dependencies": self._analyze_dependencies(issue),
            "risks": self._identify_risks(issue),
            "validation": self._get_validation_steps(issue),
        }

    async def _get_internal_plan(self, issue: Issue) -> dict[str, t.Any]:
        return {
            "strategy": "internal_pattern_based",
            "approach": self._get_internal_approach(issue),
            "patterns": self._get_cached_patterns_for_issue(issue),
            "dependencies": [],
            "risks": ["minimal"],
            "validation": ["run_quality_checks"],
        }

    def _get_specialist_approach(self, issue: Issue) -> str:
        if issue.type == IssueType.COMPLEXITY:
            return "break_into_helper_methods"
        if issue.type == IssueType.DRY_VIOLATION:
            return "extract_common_patterns"
        if issue.type == IssueType.PERFORMANCE:
            return "optimize_algorithms"
        if issue.type == IssueType.SECURITY:
            return "apply_secure_patterns"
        return "apply_clean_code_principles"

    def _get_internal_approach(self, issue: Issue) -> str:
        return {
            IssueType.FORMATTING: "apply_standard_formatting",
            IssueType.IMPORT_ERROR: "optimize_imports",
            IssueType.TYPE_ERROR: "add_type_annotations",
            IssueType.TEST_FAILURE: "fix_test_patterns",
            IssueType.DEAD_CODE: "remove_unused_code",
            IssueType.DOCUMENTATION: "update_documentation",
        }.get(issue.type, "apply_standard_fix")

    def _get_recommended_patterns(self, issue: Issue) -> list[str]:
        return {
            IssueType.COMPLEXITY: [
                "extract_method",
                "dependency_injection",
                "protocol_interfaces",
                "helper_methods",
            ],
            IssueType.DRY_VIOLATION: [
                "common_base_class",
                "utility_functions",
                "protocol_pattern",
                "composition",
            ],
            IssueType.PERFORMANCE: [
                "list_comprehension",
                "generator_pattern",
                "caching",
                "algorithm_optimization",
            ],
            IssueType.SECURITY: [
                "secure_temp_files",
                "input_validation",
                "safe_subprocess",
                "token_handling",
            ],
        }.get(issue.type, ["standard_patterns"])

    def _get_cached_patterns_for_issue(self, issue: Issue) -> list[str]:
        cached = self.get_cached_patterns()
        matching_patterns = []

        for pattern_key, pattern_data in cached.items():
            if pattern_key.startswith(issue.type.value):
                matching_patterns.extend(
                    pattern_data.get("plan", {}).get("patterns", []),
                )

        return matching_patterns or ["default_pattern"]

    def _analyze_dependencies(self, issue: Issue) -> list[str]:
        dependencies = []

        if issue.type == IssueType.COMPLEXITY:
            dependencies.extend(
                [
                    "update_tests_for_extracted_methods",
                    "update_type_annotations",
                    "verify_imports",
                ],
            )

        if issue.type == IssueType.DRY_VIOLATION:
            dependencies.extend(
                ["update_all_usage_sites", "ensure_backward_compatibility"]
            )

        return dependencies

    def _identify_risks(self, issue: Issue) -> list[str]:
        risks = []

        if issue.type == IssueType.COMPLEXITY:
            risks.extend(
                [
                    "breaking_existing_functionality",
                    "changing_method_signatures",
                    "test_failures",
                ],
            )

        if issue.type == IssueType.DRY_VIOLATION:
            risks.extend(["breaking_dependent_code", "performance_impact"])

        return risks

    def _get_validation_steps(self, issue: Issue) -> list[str]:
        return [
            "run_fast_hooks",
            "run_full_tests",
            "run_comprehensive_hooks",
            "validate_complexity_reduction",
            "check_pattern_compliance",
        ]

    async def execute_with_plan(
        self,
        issue: Issue,
        plan: dict[str, t.Any],
    ) -> FixResult:
        strategy = plan.get("strategy", "internal_pattern_based")

        if strategy == "external_specialist_guided":
            self.log(
                f"Warning: execute_with_plan() called for specialist issue {issue.type.value}"
            )
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"Issue type {issue.type.value} should be delegated to specialist"
                ],
            )

        if issue.type == IssueType.TYPE_ERROR:
            return await self._fix_type_error_with_plan(issue, plan)

        if issue.type == IssueType.DEPENDENCY:
            return await self._fix_dependency_with_plan(issue, plan)

        if issue.type == IssueType.DOCUMENTATION:
            return await self._fix_documentation_with_plan(issue, plan)

        if issue.type == IssueType.TEST_ORGANIZATION:
            return await self._fix_test_organization_with_plan(issue, plan)

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                f"ArchitectAgent does not handle {issue.type.value} proactively"
            ],
        )

    async def _fix_type_error_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:
        self.log(f"Handling type error: {issue.message}")

        confidence = 0.5

        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"Cannot fix type error without file path: {issue.message}"
                ],
                recommendations=["Provide file path for type error fixing"],
            )

        file_content = self.context.get_file_content(issue.file_path)
        if not file_content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {issue.file_path}"],
                recommendations=["Check file path and permissions"],
            )

        fixed_content, fixes_applied = self._apply_type_error_fixes(
            file_content, issue.message
        )

        if not fixes_applied:
            return FixResult(
                success=False,
                confidence=confidence,
                remaining_issues=[f"Type error: {issue.message}"],
                recommendations=[
                    "Add missing typing imports: from typing import Any, Dict, List",
                    "Replace `any` with `Any` in type annotations",
                    "Add `await` keyword before async function calls",
                    "Add type annotations to function parameters and returns",
                    "Ensure Console/ConsoleInterface protocol compatibility",
                    "Convert Path to str: `str(path_obj)` or str to Path: `Path(str_obj)`",
                ],
            )

        write_success = self.context.write_file_content(issue.file_path, fixed_content)

        if not write_success:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write fixes to {issue.file_path}"],
                recommendations=["Check file permissions and disk space"],
            )

        return FixResult(
            success=True,
            confidence=confidence,
            fixes_applied=fixes_applied,
            remaining_issues=[],
            recommendations=[f"Fixed type error: {issue.message}"],
            files_modified=[issue.file_path],
        )

    def _apply_type_error_fixes(
        self, content: str, error_message: str
    ) -> tuple[str, list[str]]:
        fixes_applied = []
        fixed_content = content

        fixed_content, new_fixes = self._fix_missing_typing_imports(
            fixed_content, error_message, content
        )
        fixes_applied.extend(new_fixes)

        fixed_content, new_fixes = self._fix_any_builtin_type(
            fixed_content, error_message
        )
        fixes_applied.extend(new_fixes)

        fixed_content, new_fixes = self._fix_missing_annotations_type(
            fixed_content, error_message
        )
        fixes_applied.extend(new_fixes)

        fixed_content, new_fixes = self._fix_path_str_type_conversion(
            fixed_content, error_message
        )
        fixes_applied.extend(new_fixes)

        fixed_content, new_fixes = self._fix_missing_await(fixed_content, error_message)
        fixes_applied.extend(new_fixes)

        return fixed_content, fixes_applied

    def _fix_missing_typing_imports(
        self, content: str, error_message: str, original_content: str
    ) -> tuple[str, list[str]]:
        imports_needed = []
        if re.search(r"\bAny\b", error_message):
            imports_needed.append("Any")
        if re.search(r"\bList\b", error_message):
            imports_needed.append("List")
        if re.search(r"\bDict\b", error_message):
            imports_needed.append("Dict")
        if re.search(r"\bOptional\b", error_message):
            imports_needed.append("Optional")
        if re.search(r"\bUnion\b", error_message):
            imports_needed.append("Union")

        if not imports_needed:
            return content, []

        fixed_content = self._add_typing_imports(content, imports_needed)
        if fixed_content != original_content:
            return fixed_content, [f"Added typing imports: {', '.join(imports_needed)}"]
        return content, []

    def _fix_any_builtin_type(
        self, content: str, error_message: str
    ) -> tuple[str, list[str]]:
        if "builtin" in error_message.lower() and "any" in error_message.lower():
            new_content = self._fix_any_builtin(content)
            if new_content != content:
                return new_content, ["Fixed `any` → `Any` in type annotations"]
        return content, []

    def _fix_missing_annotations_type(
        self, content: str, error_message: str
    ) -> tuple[str, list[str]]:
        if (
            "annotation" in error_message.lower()
            or "has no attribute" in error_message.lower()
        ):
            new_content = self._add_missing_annotations(content, error_message)
            if new_content != content:
                return new_content, ["Added missing type annotations"]
        return content, []

    def _fix_path_str_type_conversion(
        self, content: str, error_message: str
    ) -> tuple[str, list[str]]:
        if "path" in error_message.lower() and "str" in error_message.lower():
            new_content = self._fix_path_str_conversion(content, error_message)
            if new_content != content:
                return new_content, ["Fixed Path/str type conversion"]
        return content, []

    def _fix_missing_await(
        self, content: str, error_message: str
    ) -> tuple[str, list[str]]:
        if "await" in error_message.lower() or "coroutine" in error_message.lower():
            new_content = self._add_await_keyword(content)
            if new_content != content:
                return new_content, ["Added `await` keyword before async calls"]
        return content, []

    def _add_typing_imports(self, content: str, imports_needed: list[str]) -> str:
        lines = content.splitlines(keepends=True)
        typing_imports_to_add = set(imports_needed)

        typing_import_idx, existing_typing_imports = self._find_existing_typing_imports(
            lines, imports_needed
        )

        typing_imports_to_add -= existing_typing_imports

        if not typing_imports_to_add:
            return content

        import_line = f"from typing import {', '.join(sorted(typing_imports_to_add))}\n"

        if typing_import_idx is not None:
            lines = self._merge_existing_imports(
                lines, typing_import_idx, typing_imports_to_add
            )
        else:
            insert_idx = self._find_import_insertion_point(lines)
            lines.insert(insert_idx, import_line)

        return "".join(lines)

    def _find_existing_typing_imports(
        self, lines: list[str], imports_needed: list[str]
    ) -> tuple[int | None, set[str]]:
        typing_import_idx = None
        existing_typing_imports = set()

        for i, line in enumerate(lines):
            if i < 2 and (line.startswith("#!") or line.startswith("# -*-")):
                continue

            if i < 10 and line.strip().startswith('"""'):
                i = self._skip_docstring(lines, i)
                continue

            if line.strip().startswith("from typing import"):
                typing_import_idx = i
                match = re.search(r"from typing import (.+)", line)
                if match:
                    existing_imports_str = match.group(1)
                    for imp in imports_needed:
                        if re.search(rf"\b{imp}\b", existing_imports_str):
                            existing_typing_imports.add(imp)
                break

            if line.strip() and not line.strip().startswith("#"):
                if not line.strip().startswith("from ") and not line.strip().startswith(
                    "import "
                ):
                    break

        return typing_import_idx, existing_typing_imports

    def _skip_docstring(self, lines: list[str], start_idx: int) -> int:
        if start_idx < 10 and lines[start_idx].strip().startswith('"""'):
            if lines[start_idx].strip().count('"""') == 1:
                for j in range(start_idx + 1, min(start_idx + 10, len(lines))):
                    if '"""' in lines[j]:
                        return j
        return start_idx

    def _merge_existing_imports(
        self, lines: list[str], typing_import_idx: int, imports_to_add: set[str]
    ) -> list[str]:
        old_line = lines[typing_import_idx]
        match = re.search(r"(from typing import .+)", old_line)
        if match:
            existing_imports = match.group(1)
            new_imports = f"{existing_imports}, {', '.join(sorted(imports_to_add))}"
            lines[typing_import_idx] = new_imports + "\n"
        return lines

    def _find_import_insertion_point(self, lines: list[str]) -> int:
        insert_idx = 0

        for i, line in enumerate(lines):
            if i < 2 and (line.startswith("#!") or line.startswith("# -*-")):
                insert_idx = i + 1
                continue

            if i < 10 and line.strip().startswith('"""'):
                insert_idx = i + 1
                if line.strip().count('"""') == 1:
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if '"""' in lines[j]:
                            insert_idx = j + 1
                            break
                continue

            if line.strip() and not line.strip().startswith("#"):
                insert_idx = i
                break

        return insert_idx

    def _fix_any_builtin(self, content: str) -> str:

        pattern1 = r"(\w+)\s*:\s*any\b"
        content = re.sub(pattern1, r"\1: Any", content)

        pattern2 = r"->\s*any\s*:"
        content = re.sub(pattern2, "-> Any:", content)

        pattern3 = r"\[\s*any\s*\]"
        content = re.sub(pattern3, "[Any]", content)

        pattern4 = r"(\w+)\s*:\s*any\s*="
        content = re.sub(pattern4, r"\1: Any =", content)

        return content

    def _add_missing_annotations(self, content: str, error_message: str) -> str:
        try:
            tree = ast.parse(content)
            lines = content.splitlines(keepends=True)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.returns is None:
                        has_return = False
                        for body_node in ast.walk(node):
                            if (
                                isinstance(body_node, ast.Return)
                                and body_node.value is not None
                            ):
                                has_return = True
                                break

                        if not has_return:
                            func_line = node.lineno - 1
                            line = lines[func_line]

                            colon_pos = line.rfind(":")
                            if colon_pos > 0:
                                if "->" not in line:
                                    new_line = (
                                        line[:colon_pos] + " -> None" + line[colon_pos:]
                                    )
                                    lines[func_line] = new_line

            return "".join(lines)
        except Exception as e:
            logger.debug(f"Could not add annotations via AST: {e}")
            return content

    def _fix_path_str_conversion(self, content: str, error_message: str) -> str:

        if "expected str" in error_message.lower() or "path" in error_message.lower():
            pass

        return content

    def _add_await_keyword(self, content: str) -> str:
        lines = content.splitlines(keepends=True)
        modified = False

        async_patterns = [
            r"(\w+)\.async_(\w+)\(",
            r"(\w+)\.start\(",
        ]

        for i, line in enumerate(lines):
            if "await" in line:
                continue

            stripped = line.strip()
            if stripped.startswith("#") or (
                stripped.startswith('"') and stripped.endswith('"')
            ):
                continue

            for pattern in async_patterns:
                if re.search(pattern, line) and "=" in line:
                    indent = len(line) - len(line.lstrip())
                    lines[i] = line[:indent] + "await " + line[indent:]
                    modified = True
                    break

        if modified:
            return "".join(lines)
        return content

    async def _fix_dependency_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:

        self.log(f"Dependency fixing not yet implemented: {issue.message}")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Dependency issue: {issue.message}"],
        )

    async def _fix_documentation_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:

        self.log(f"Documentation fixing not yet implemented: {issue.message}")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Documentation issue: {issue.message}"],
        )

    async def _fix_test_organization_with_plan(
        self, issue: Issue, plan: dict[str, t.Any]
    ) -> FixResult:

        self.log(f"Test organization fixing not yet implemented: {issue.message}")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Test organization issue: {issue.message}"],
        )

    async def analyze_and_fix(self, issue: Issue) -> FixResult:

        if issue.type in {
            IssueType.COMPLEXITY,
            IssueType.DRY_VIOLATION,
            IssueType.DEAD_CODE,
        }:
            self.log(f"Delegating to RefactoringAgent for {issue.type.value}")
            return await self._refactoring_agent.analyze_and_fix(issue)

        if issue.type == IssueType.FORMATTING:
            self.log(f"Delegating to FormattingAgent for {issue.type.value}")
            return await self._formatting_agent.analyze_and_fix(issue)

        if issue.type == IssueType.IMPORT_ERROR:
            self.log(f"Delegating to ImportOptimizationAgent for {issue.type.value}")
            return await self._import_agent.analyze_and_fix(issue)

        if issue.type == IssueType.SECURITY:
            self.log(f"Delegating to SecurityAgent for {issue.type.value}")
            return await self._security_agent.analyze_and_fix(issue)

        return await self.analyze_and_fix_proactively(issue)

    # ========== NEW: Layer 2 Integration ==========
    async def execute_fix_plan(self, plan: "FixPlan") -> "FixResult":
        """
        Execute a validated FixPlan created by analysis stage.

        Args:
            plan: Validated FixPlan from PlanningAgent

        Returns:
            FixResult with execution details
        """

        self.log(
            f"Executing FixPlan for {plan.file_path}:{plan.issue_type} "
            f"({len(plan.changes)} changes, risk={plan.risk_level})"
        )

        # Validate that we have changes to apply
        if not plan.changes:
            self.log(f"Plan has no changes to apply for {plan.file_path}", level="WARNING")
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Plan has no changes to apply"],
                recommendations=["PlanningAgent should generate actual changes"],
            )

        # For TYPE_ERROR, use existing fix logic
        if plan.issue_type == "TYPE_ERROR":
            # Create a mock issue from the plan
            issue = Issue(
                type=IssueType.TYPE_ERROR,
                severity=plan.changes[0].line_range[0] > 30
                and Priority.HIGH
                or Priority.MEDIUM,
                message=plan.rationale,
                file_path=plan.file_path,
            )

            # Create a plan dict for execute_with_plan
            plan_dict = {
                "strategy": "internal_pattern_based",
                "approach": "add_type_annotations",
            }

            return await self.execute_with_plan(issue, plan_dict)

        # For other types, delegate to appropriate specialist
        if plan.issue_type == "COMPLEXITY":
            return await self._refactoring_agent.execute_fix_plan(plan)

        if plan.issue_type == "FORMATTING":
            return await self._formatting_agent.execute_fix_plan(plan)

        if plan.issue_type == "SECURITY":
            return await self._security_agent.execute_fix_plan(plan)

        # Default: apply changes directly
        return await self._apply_plan_changes(plan)

    async def _apply_plan_changes(self, plan: "FixPlan") -> "FixResult":
        """Apply changes from plan directly to file."""

        if not plan.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path in plan"],
            )

        # Read current file content
        try:
            file_content = await self._read_file_context(plan.file_path)
        except Exception as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {e}"],
            )

        # Apply each change
        applied_changes = []
        for i, change in enumerate(plan.changes):
            try:
                lines = file_content.split("\n")
                if change.line_range[0] < 1 or change.line_range[1] > len(lines):
                    continue

                old_lines = lines[change.line_range[0] - 1 : change.line_range[1]]
                old_code = "\n".join(old_lines)

                new_content = file_content.replace(old_code, change.new_code)
                success = self.context.write_file_content(plan.file_path, new_content)

                if success:
                    applied_changes.append(f"Change {i}: {change.reason}")
            except Exception as e:
                self.log(f"Change {i} failed: {e}", level="ERROR")

        success = len(applied_changes) == len(plan.changes)
        return FixResult(
            success=success,
            confidence=0.7 if success else 0.0,
            fixes_applied=applied_changes,
            remaining_issues=[] if success else ["Some changes failed"],
            files_modified=[plan.file_path] if success else [],
        )


agent_registry.register(ArchitectAgent)
