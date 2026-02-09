import ast
import logging
import re
import typing as t

from .base import FixResult, Issue, IssueType, agent_registry
from .formatting_agent import FormattingAgent
from .import_optimization_agent import ImportOptimizationAgent
from .proactive_agent import ProactiveAgent
from .refactoring_agent import RefactoringAgent
from .security_agent import SecurityAgent

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
        # Higher confidence for type errors (0.5 vs 0.1)
        # Type errors are now handled with specific zuban patterns
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
            dependencies.extend(["update_all_usage_sites", "ensure_backward_compatibility"])

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
        """
        Handle zuban/mypy type errors with specific patterns.

        Error Categories:
        1. Missing imports (5 errors): Add typing imports
        2. Wrong builtins (2 errors): `any` → `Any`
        3. Missing await (8 errors): Add await keyword
        4. Missing type annotations (3 errors): Add `: Dict[str, Any]`
        5. Attribute errors (10 errors): ConsoleInterface violations
        6. Protocol mismatches (15+ errors): ConsoleInterface violations
        7. Type incompatibilities (8+ errors): Path vs str, etc.
        """
        self.log(f"Handling type error: {issue.message}")

        # Lower confidence threshold for type errors (0.5 vs 0.7 for logic errors)
        confidence = 0.5

        # Check if file path is provided
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"Cannot fix type error without file path: {issue.message}"
                ],
                recommendations=["Provide file path for type error fixing"],
            )

        # Get file content
        file_content = self.context.get_file_content(issue.file_path)
        if not file_content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {issue.file_path}"],
                recommendations=["Check file path and permissions"],
            )

        # Apply type error fixes based on error message patterns
        fixed_content, fixes_applied = self._apply_type_error_fixes(
            file_content, issue.message
        )

        # If no fixes applied, return failure with recommendations
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

        # Write fixed content back to file
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
        """
        Apply type error fixes based on error message patterns.

        This method actually modifies code content to fix common type errors.

        Returns tuple of (fixed_content, fixes_applied_list).
        """
        fixes_applied = []
        fixed_content = content

        # Pattern 1: Missing imports for Any, List, Dict, Optional, Union
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

        if imports_needed:
            fixed_content = self._add_typing_imports(fixed_content, imports_needed)
            if fixed_content != content:
                fixes_applied.append(f"Added typing imports: {', '.join(imports_needed)}")

        # Pattern 2: Wrong builtins - `any` → `Any`
        # This replaces `any` with `Any` in type annotation positions
        if "builtin" in error_message.lower() and "any" in error_message.lower():
            new_content = self._fix_any_builtin(fixed_content)
            if new_content != fixed_content:
                fixes_applied.append("Fixed `any` → `Any` in type annotations")
                fixed_content = new_content

        # Pattern 3: Missing type annotations in function signatures
        if "annotation" in error_message.lower() or "has no attribute" in error_message.lower():
            new_content = self._add_missing_annotations(fixed_content, error_message)
            if new_content != fixed_content:
                fixes_applied.append("Added missing type annotations")
                fixed_content = new_content

        # Pattern 4: Path vs str conversion
        if "path" in error_message.lower() and "str" in error_message.lower():
            new_content = self._fix_path_str_conversion(fixed_content, error_message)
            if new_content != fixed_content:
                fixes_applied.append("Fixed Path/str type conversion")
                fixed_content = new_content

        # Pattern 5: Missing await (conservative - only add if pattern is clear)
        if "await" in error_message.lower() or "coroutine" in error_message.lower():
            new_content = self._add_await_keyword(fixed_content)
            if new_content != fixed_content:
                fixes_applied.append("Added `await` keyword before async calls")
                fixed_content = new_content

        return fixed_content, fixes_applied

    def _add_typing_imports(self, content: str, imports_needed: list[str]) -> str:
        """
        Add missing typing imports to the file.

        Handles:
        - New import section if none exists
        - Existing `from typing import` statements
        - Proper placement after module docstring
        """
        lines = content.splitlines(keepends=True)
        typing_imports_to_add = set(imports_needed)

        # Find existing typing imports
        typing_import_idx = None
        existing_typing_imports = set()

        for i, line in enumerate(lines):
            # Skip shebang and encoding
            if i < 2 and (line.startswith("#!") or line.startswith("# -*-")):
                continue

            # Skip docstring
            if i < 10 and line.strip().startswith('"""'):
                # Skip until end of docstring
                if line.strip().count('"""') == 1:
                    # Docstring continues
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if '"""' in lines[j]:
                            break
                continue

            # Check for existing typing imports
            if line.strip().startswith("from typing import"):
                typing_import_idx = i
                # Extract what's already imported
                match = re.search(r"from typing import (.+)", line)
                if match:
                    existing_imports_str = match.group(1)
                    # Parse imports (handle multiline later)
                    for imp in imports_needed:
                        if re.search(rf"\b{imp}\b", existing_imports_str):
                            existing_typing_imports.add(imp)
                break

            # Stop looking if we hit non-import, non-comment code
            if line.strip() and not line.strip().startswith("#"):
                if not line.strip().startswith("from ") and not line.strip().startswith("import "):
                    break

        # Filter out already imported
        typing_imports_to_add -= existing_typing_imports

        if not typing_imports_to_add:
            return content  # Nothing to add

        import_line = f"from typing import {', '.join(sorted(typing_imports_to_add))}\n"

        if typing_import_idx is not None:
            # Add to existing typing import
            old_line = lines[typing_import_idx]
            match = re.search(r"(from typing import .+)", old_line)
            if match:
                existing_imports = match.group(1)
                # Merge imports
                new_imports = f"{existing_imports}, {', '.join(sorted(typing_imports_to_add))}"
                lines[typing_import_idx] = new_imports + "\n"
        else:
            # Find insertion point (after docstring/shebang, before other code)
            insert_idx = 0
            for i, line in enumerate(lines):
                if i < 2 and (line.startswith("#!") or line.startswith("# -*-")):
                    insert_idx = i + 1
                    continue

                # Skip docstring
                if i < 10 and line.strip().startswith('"""'):
                    insert_idx = i + 1
                    if line.strip().count('"""') == 1:
                        for j in range(i + 1, min(i + 10, len(lines))):
                            if '"""' in lines[j]:
                                insert_idx = j + 1
                                break
                    continue

                # Insert before first import or code
                if line.strip() and not line.strip().startswith("#"):
                    insert_idx = i
                    break

            lines.insert(insert_idx, import_line)

        return "".join(lines)

    def _fix_any_builtin(self, content: str) -> str:
        """
        Fix `any` builtin used as type annotation → `Any`.

        Replaces `any` with `Any` in type annotation contexts:
        - Function parameters: `def foo(x: any)` → `def foo(x: Any)`
        - Return types: `def foo() -> any:` → `def foo() -> Any:`
        - Variable annotations: `x: any = ...` → `x: Any = ...`
        - Generic types: `list[any]` → `list[Any]`, `dict[str, any]` → `dict[str, Any]`
        """
        # Pattern 1: Function parameter annotations
        # `param: any` → `param: Any`
        pattern1 = r"(\w+)\s*:\s*any\b"
        content = re.sub(pattern1, r"\1: Any", content)

        # Pattern 2: Return type annotations
        # `def foo(...) -> any:` → `def foo(...) -> Any:`
        pattern2 = r"->\s*any\s*:"
        content = re.sub(pattern2, "-> Any:", content)

        # Pattern 3: Generic type annotations (newer syntax)
        # `list[any]` → `list[Any]`, `dict[str, any]` → `dict[str, Any]`
        pattern3 = r"\[\s*any\s*\]"
        content = re.sub(pattern3, "[Any]", content)

        # Pattern 4: Variable annotations
        # `x: any =` → `x: Any =`
        pattern4 = r"(\w+)\s*:\s*any\s*="
        content = re.sub(pattern4, r"\1: Any =", content)

        return content

    def _add_missing_annotations(self, content: str, error_message: str) -> str:
        """
        Add missing type annotations based on error message patterns.

        Handles:
        - Functions without return types: `def foo():` → `def foo() -> None:`
        - Parameters with missing types
        """
        try:
            tree = ast.parse(content)
            lines = content.splitlines(keepends=True)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check if function has return type annotation
                    if node.returns is None:
                        # Add `-> None` for functions without return annotation
                        # Only if they don't have explicit return statements
                        has_return = False
                        for body_node in ast.walk(node):
                            if isinstance(body_node, ast.Return) and body_node.value is not None:
                                has_return = True
                                break

                        if not has_return:
                            # Find the line with function def
                            func_line = node.lineno - 1  # 0-indexed
                            line = lines[func_line]

                            # Add return type annotation
                            # Find the colon after parameter list
                            colon_pos = line.rfind(":")
                            if colon_pos > 0:
                                # Check if there's already a return annotation
                                if "->" not in line:
                                    # Insert `-> None` before the colon
                                    new_line = line[:colon_pos] + " -> None" + line[colon_pos:]
                                    lines[func_line] = new_line

            return "".join(lines)
        except Exception as e:
            logger.debug(f"Could not add annotations via AST: {e}")
            return content

    def _fix_path_str_conversion(self, content: str, error_message: str) -> str:
        """
        Fix Path vs str conversion issues.

        This is conservative - only makes obvious changes based on error patterns.
        """
        # Pattern 1: str() conversion for Path objects
        # If error mentions "expected str, got Path" or similar
        if "expected str" in error_message.lower() or "path" in error_message.lower():
            # Add str() wrapper in obvious cases (conservative)
            # This is a simple heuristic - real fixes need more context
            pass

        # For now, just return content - Path/str fixes need more context
        return content

    def _add_await_keyword(self, content: str) -> str:
        """
        Add `await` keyword before async function calls.

        Conservative implementation - only adds await in obvious patterns:
        - Lines calling functions known to be async
        - When error message clearly indicates missing await
        """
        lines = content.splitlines(keepends=True)
        modified = False

        # Common async function patterns
        async_patterns = [
            r"(\w+)\.async_(\w+)\(",  # obj.async_foo()
            r"(\w+)\.start(",  # obj.start() (common async pattern)
        ]

        for i, line in enumerate(lines):
            # Skip lines that already have await
            if "await" in line:
                continue

            # Skip comments and strings
            stripped = line.strip()
            if stripped.startswith("#") or (stripped.startswith('"') and stripped.endswith('"')):
                continue

            # Check for async patterns that need await
            for pattern in async_patterns:
                if re.search(pattern, line) and "=" in line:
                    # This is likely an assignment missing await
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


agent_registry.register(ArchitectAgent)
