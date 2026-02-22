import ast
import typing as t
from pathlib import Path

from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)
from .file_context import FileContextReader
from .helpers.refactoring.code_transformer import CodeTransformer
from .helpers.refactoring.complexity_analyzer import ComplexityAnalyzer
from .helpers.refactoring.dead_code_detector import DeadCodeDetector
from .semantic_helpers import (
    SemanticInsight,
    create_semantic_enhancer,
    get_session_enhanced_recommendations,
)


class RefactoringAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.semantic_enhancer = create_semantic_enhancer(context.project_path)
        self.semantic_insights: dict[str, SemanticInsight] = {}

        self._complexity_analyzer = ComplexityAnalyzer(context)
        self._code_transformer = CodeTransformer(context)
        self._dead_code_detector = DeadCodeDetector(context)
        self._file_reader = FileContextReader()

    async def _read_file_context(self, file_path: str | Path) -> str:
        """Read file context with caching."""
        return await self._file_reader.read_file(file_path)

    def _estimate_function_complexity(self, function_body: str) -> int:
        return self._complexity_analyzer._estimate_function_complexity(function_body)

    def _is_semantic_function_definition(self, line: str) -> bool:
        return self._complexity_analyzer._is_function_definition(line.strip())

    def _should_skip_semantic_line(
        self,
        stripped: str,
        current_function: dict[str, t.Any] | None,
        line: str,
    ) -> bool:
        return self._complexity_analyzer._should_skip_line(
            stripped,
            current_function,
            line,
        )

    def _should_remove_import_line(
        self,
        line: str,
        unused_import: dict[str, str],
    ) -> bool:
        return self._dead_code_detector._should_remove_import_line(line, unused_import)

    def _extract_nested_conditions(self, content: str) -> str:
        return self._code_transformer._extract_nested_conditions(content)

    def _simplify_boolean_expressions(self, content: str) -> str:
        return self._code_transformer._simplify_boolean_expressions(content)

    def _is_empty_except_block(self, lines: list[str], line_idx: int) -> bool:
        return self._dead_code_detector._is_empty_except_block(lines, line_idx)

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.COMPLEXITY, IssueType.DEAD_CODE, IssueType.TYPE_ERROR}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.COMPLEXITY:
            return 0.9 if self._has_complexity_markers(issue) else 0.85
        if issue.type == IssueType.DEAD_CODE:
            return 0.8 if self._has_dead_code_markers(issue) else 0.75
        if issue.type == IssueType.TYPE_ERROR:
            return await self._is_fixable_type_error(issue)
        return 0.0

    def _has_complexity_markers(self, issue: Issue) -> bool:
        if not issue.message:
            return False

        complexity_indicators = [
            "cognitive complexity",
            "too complex",
            "nested",
            "cyclomatic",
            "long function",
            "too many branches",
            "too many conditions",
        ]

        return any(
            indicator in issue.message.lower() for indicator in complexity_indicators
        )

    def _has_dead_code_markers(self, issue: Issue) -> bool:
        if not issue.message:
            return False

        dead_code_indicators = [
            "unused",
            "imported but unused",
            "defined but not used",
            "unreachable",
            "dead code",
            "never used",
        ]

        return any(
            indicator in issue.message.lower() for indicator in dead_code_indicators
        )

    async def _is_fixable_type_error(self, issue: Issue) -> float:
        if not issue.message:
            return 0.0

        message_lower = issue.message.lower()

        if (
            "missing return type" in message_lower
            or "needs return type" in message_lower
        ):
            return 0.9

        if any(
            x in message_lower
            for x in ("-> None", "-> Any", "needs annotation", "has no type")
        ):
            return 0.8

        if "parameter" in message_lower and "type annotation" in message_lower:
            return 0.7

        if any(
            x in message_lower
            for x in (
                "incompatible return type",
                "incompatible type",
                "argument of type",
                "has no attribute",
                "cannot be assigned to",
            )
        ):
            return 0.6

        if any(
            x in message_lower
            for x in (
                "incompatible",
                "assignment",
                "cannot be assigned",
                "type mismatch",
                "invalid type",
                "undefined name",
            )
        ):
            return 0.4

        if any(
            x in message_lower
            for x in (
                "type error",
                "annotation",
                "generic",
                "protocol",
                "signature",
            )
        ):
            return 0.3

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing {issue.type.value} issue: {issue.message}")

        if issue.type == IssueType.COMPLEXITY:
            return await self._reduce_complexity(issue)
        if issue.type == IssueType.DEAD_CODE:
            return await self._remove_dead_code(issue)
        if issue.type == IssueType.TYPE_ERROR:
            return await self._fix_type_error(issue)

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"RefactoringAgent cannot handle {issue.type.value}"],
        )

    async def _reduce_complexity(self, issue: Issue) -> FixResult:
        validation_result = self._validate_complexity_issue(issue)
        if validation_result:
            return validation_result

        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided for complexity issue"],
            )

        file_path = Path(issue.file_path)

        if "detect_agent_needs" in issue.message:
            return await self._apply_known_complexity_fix(file_path, issue)

        if issue.line_number is not None:
            self.log(
                f"Tier 1: Using line number {issue.line_number} from parser for complexity reduction"
            )
            try:
                return await self._process_complexity_reduction_with_line_number(
                    file_path, issue.line_number
                )
            except Exception as e:
                self.log(f"Tier 1 failed: {e}, falling back to Tier 2")

        function_name = self._extract_function_name_from_issue(issue)
        if function_name:
            self.log(f"Tier 2: Searching for function '{function_name}' by name")
            try:
                return await self._process_complexity_reduction_by_function_name(
                    file_path, function_name
                )
            except Exception as e:
                self.log(f"Tier 2 failed: {e}, falling back to Tier 3")

        self.log("Tier 3: Performing full file complexity analysis")
        try:
            return await self._process_complexity_reduction(file_path)
        except SyntaxError as e:
            return self._create_syntax_error_result(e)
        except Exception as e:
            return self._create_general_error_result(e)

    async def _apply_known_complexity_fix(
        self,
        file_path: Path,
        issue: Issue,
    ) -> FixResult:
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        refactored_content = self._code_transformer.refactor_detect_agent_needs_pattern(
            content,
        )

        if refactored_content != content:
            success = self.context.write_file_content(file_path, refactored_content)
            if success:
                return FixResult(
                    success=True,
                    confidence=0.9,
                    fixes_applied=[
                        "Applied proven complexity reduction pattern for detect_agent_needs",
                    ],
                    files_modified=[str(file_path)],
                    recommendations=await self._enhance_recommendations_with_semantic(
                        ["Verify functionality after complexity reduction"],
                    ),
                )
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"Failed to write refactored content to {file_path}",
                ],
            )
        return FixResult(
            success=False,
            confidence=0.3,
            remaining_issues=[
                "Refactoring pattern did not apply to current file content",
            ],
            recommendations=[
                "File may have been modified since pattern was created",
            ],
        )

    def _validate_complexity_issue(self, issue: Issue) -> FixResult | None:
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path specified for complexity issue"],
            )

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )

        return None

    async def _process_complexity_reduction(self, file_path: Path) -> FixResult:
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        tree = ast.parse(content)

        complex_functions = self._complexity_analyzer.find_complex_functions(
            tree,
            content,
        )

        semantic_complex_functions = await self._find_semantic_complex_patterns(
            content,
            file_path,
        )
        if semantic_complex_functions:
            complex_functions.extend(semantic_complex_functions)

        if not complex_functions:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No overly complex functions found to fix"],
                recommendations=["Manual review required"],
            )

        return await self._apply_and_save_refactoring(
            file_path,
            content,
            complex_functions,
        )

    async def _apply_and_save_refactoring(
        self,
        file_path: Path,
        content: str,
        complex_functions: list[dict[str, t.Any]],
    ) -> FixResult:
        refactored_content = self._code_transformer.refactor_complex_functions(
            content,
            complex_functions,
        )

        if refactored_content == content:
            refactored_content = self._code_transformer.apply_enhanced_strategies(
                content,
            )

        if refactored_content == content:
            return self._create_no_changes_result()

        success = self.context.write_file_content(file_path, refactored_content)
        if not success:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write refactored file: {file_path}"],
            )

        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=[f"Reduced complexity in {len(complex_functions)} functions"],
            files_modified=[str(file_path)],
            recommendations=await self._enhance_recommendations_with_semantic(
                ["Verify functionality after complexity reduction"],
            ),
        )

    def _create_no_changes_result(self) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.5,
            remaining_issues=["Could not automatically reduce complexity"],
            recommendations=[
                "Manual refactoring required",
                "Consider breaking down complex conditionals",
                "Extract helper methods for repeated patterns",
            ],
        )

    def _create_syntax_error_result(self, error: SyntaxError) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Syntax error in file: {error}"],
        )

    def _create_general_error_result(self, error: Exception) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Error processing file: {error}"],
        )

    def _extract_function_name_from_issue(self, issue: Issue) -> str | None:
        import re

        match = re.search(r"Function\s+'([\w:]+)'", issue.message)
        if match:
            full_name = match.group(1)

            if "::" in full_name:
                return full_name.split("::")[-1]
            return full_name

        match = re.search(r"^(\w+)\s+-", issue.message)
        if match:
            return match.group(1)

        for detail in issue.details:
            if detail.startswith("function:"):
                func_name = detail.split(":", 1)[1].strip()

                if "::" in func_name:
                    return func_name.split("::")[-1]
                return func_name

        return None

    async def _process_complexity_reduction_with_line_number(
        self, file_path: Path, line_number: int
    ) -> FixResult:
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        tree = ast.parse(content)

        target_function = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_start = node.lineno
                func_end = node.end_lineno or func_start
                if func_start <= line_number <= func_end:
                    target_function = self._build_function_dict(node, content)
                    if target_function:
                        target_function["complexity"] = max(
                            target_function.get("complexity", 0), 16
                        )
                    break

        if not target_function:
            self.log(
                f"Could not find function at line {line_number}, trying internal analyzer"
            )
            complex_functions = self._complexity_analyzer.find_complex_functions(
                tree, content
            )

            target_functions = [
                f
                for f in complex_functions
                if f.get("line_start", 0)
                <= line_number
                <= f.get("line_end", line_number + 100)
            ]

            if not target_functions:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[
                        f"No complex functions found near line {line_number}"
                    ],
                    recommendations=["Manual review required"],
                )

            return await self._apply_and_save_refactoring(
                file_path, content, target_functions
            )

        self.log(
            f"Found function '{target_function['name']}' at line {target_function['line_start']} "
            f"(complexipy reported line {line_number})"
        )

        return await self._apply_and_save_refactoring(
            file_path, content, [target_function]
        )

    async def _process_complexity_reduction_by_function_name(
        self, file_path: Path, function_name: str
    ) -> FixResult:
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        try:
            tree = ast.parse(content)
            target_function = self._find_function_by_name(tree, content, function_name)

            if not target_function:
                return self._create_function_not_found_result(function_name)

            return await self._apply_and_save_refactoring(
                file_path, content, [target_function]
            )

        except Exception:
            raise

    def _find_function_by_name(
        self, tree: ast.AST, content: str, function_name: str
    ) -> dict[str, t.Any] | None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    return self._build_function_dict(node, content)
        return None

    def _build_function_dict(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, content: str
    ) -> dict[str, t.Any] | None:

        source_segment = ast.get_source_segment(content, node) or ""
        internal_complexity = self._complexity_analyzer._estimate_function_complexity(
            source_segment
        )
        return {
            "name": node.name,
            "line_start": node.lineno,
            "line_end": node.end_lineno or node.lineno,
            "complexity": max(internal_complexity, 16),
            "node": node,
        }

    def _create_function_not_found_result(self, function_name: str) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Function '{function_name}' not found in file"],
            recommendations=[
                "Check if function was renamed or moved",
                "Verify the file path is correct",
            ],
        )

    async def _remove_dead_code(self, issue: Issue) -> FixResult:
        validation_result = self._validate_dead_code_issue(issue)
        if validation_result:
            return validation_result

        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided for dead code issue"],
            )

        file_path = Path(issue.file_path)

        try:
            return await self._process_dead_code_removal(file_path)
        except SyntaxError as e:
            return self._create_syntax_error_result(e)
        except Exception as e:
            return self._create_dead_code_error_result(e)

    def _validate_dead_code_issue(self, issue: Issue) -> FixResult | None:
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path specified for dead code issue"],
            )

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )

        return None

    async def _process_dead_code_removal(self, file_path: Path) -> FixResult:
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        tree = ast.parse(content)

        dead_code_analysis = self._dead_code_detector.analyze_dead_code(tree, content)

        if not dead_code_analysis["removable_items"]:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No obvious dead code found"],
            )

        return self._apply_and_save_cleanup(file_path, content, dead_code_analysis)

    def _apply_and_save_cleanup(
        self,
        file_path: Path,
        content: str,
        analysis: dict[str, t.Any],
    ) -> FixResult:
        lines = content.split("\n")
        lines_to_remove = self._collect_all_removable_lines(lines, analysis)

        filtered_lines = [
            line for i, line in enumerate(lines) if i not in lines_to_remove
        ]
        cleaned_content = "\n".join(filtered_lines)

        if cleaned_content == content:
            return self._create_no_cleanup_result()

        success = self.context.write_file_content(file_path, cleaned_content)
        if not success:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write cleaned file: {file_path}"],
            )

        removed_count = len(analysis["removable_items"])
        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=[f"Removed {removed_count} dead code items"],
            files_modified=[str(file_path)],
            recommendations=["Verify imports and functionality after cleanup"],
        )

    def _collect_all_removable_lines(
        self,
        lines: list[str],
        analysis: dict[str, t.Any],
    ) -> set[int]:
        lines_to_remove: set[int] = set()

        lines_to_remove.update(
            self._dead_code_detector.find_lines_to_remove(lines, analysis),
        )
        lines_to_remove.update(
            self._dead_code_detector._find_unreachable_lines(lines, analysis),
        )
        lines_to_remove.update(
            self._dead_code_detector._find_redundant_lines(lines, analysis),
        )

        return lines_to_remove

    def _create_no_cleanup_result(self) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.5,
            remaining_issues=["Could not automatically remove dead code"],
            recommendations=[
                "Manual review required",
                "Check for unused imports with tools like vulture",
            ],
        )

    def _create_dead_code_error_result(self, error: Exception) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Error processing file: {error}"],
        )

    async def _find_semantic_complex_patterns(
        self,
        content: str,
        file_path: Path,
    ) -> list[dict[str, t.Any]]:
        semantic_functions = []

        try:
            code_elements = (
                self._complexity_analyzer.extract_code_functions_for_semantic_analysis(
                    content,
                )
            )

            for element in code_elements:
                if (
                    element["type"] == "function"
                    and element["estimated_complexity"] > 10
                ):
                    insight = (
                        await self.semantic_enhancer.find_refactoring_opportunities(
                            element["signature"] + "\n" + element["body"][:150],
                            current_file=file_path,
                        )
                    )

                    if insight.total_matches > 2:
                        semantic_functions.append(
                            {
                                "name": element["name"],
                                "line_start": element["start_line"],
                                "line_end": element["end_line"],
                                "complexity": element["estimated_complexity"],
                                "semantic_matches": insight.total_matches,
                                "refactor_opportunities": insight.related_patterns[:3],
                                "node": element.get("node"),
                            },
                        )

                        self.semantic_insights[element["name"]] = insight

        except Exception as e:
            self.log(f"Warning: Semantic complexity detection failed: {e}")

        return semantic_functions

    async def _enhance_recommendations_with_semantic(
        self,
        base_recommendations: list[str],
    ) -> list[str]:
        enhanced = base_recommendations.copy()

        if self.semantic_insights:
            total_semantic_matches = sum(
                insight.total_matches for insight in self.semantic_insights.values()
            )
            high_conf_matches = sum(
                insight.high_confidence_matches
                for insight in self.semantic_insights.values()
            )

            if high_conf_matches > 0:
                enhanced.append(
                    f"Semantic analysis found {high_conf_matches} similar complex patterns - "
                    f"consider extracting common refactoring utilities",
                )

            if total_semantic_matches >= 3:
                enhanced.append(
                    f"Found {total_semantic_matches} related complexity patterns across codebase - "
                    f"review for consistent refactoring approach",
                )

            for func_name, insight in self.semantic_insights.items():
                summary = self.semantic_enhancer.get_semantic_context_summary(insight)
                self.log(f"Semantic context for {func_name}: {summary}")
                await self.semantic_enhancer.store_insight_to_session(
                    insight,
                    "RefactoringAgent",
                )

        return await get_session_enhanced_recommendations(
            enhanced,
            "RefactoringAgent",
            self.context.project_path,
        )

    async def _fix_type_error(self, issue: Issue) -> FixResult:
        confidence = await self._is_fixable_type_error(issue)
        if confidence == 0.0:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"Type error too complex for auto-fix: {issue.message}"
                ],
            )

        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided"],
            )

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not read file"],
            )

        try:
            tree = ast.parse(content)
            lines = content.splitlines(keepends=True)

            fixed = False

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.returns is None and not any(
                        decorator.id == "property"
                        for decorator in node.decorator_list
                        if isinstance(decorator, ast.Name)
                    ):
                        func_line = node.lineno - 1
                        if func_line < len(lines):
                            line = lines[func_line]
                            if ":" in line and "->" not in line:
                                lines[func_line] = line.replace(":", " -> None:", 1)
                                fixed = True

            if fixed:
                fixed_content = "".join(lines)

                if self.context.write_file_content(file_path, fixed_content):
                    return FixResult(
                        success=True,
                        confidence=confidence,
                        fixes_applied=["Added type annotation"],
                        files_modified=[str(file_path)],
                    )

        except Exception as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to add type annotation: {e}"],
            )

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No changes applied"],
        )

    # ========== NEW: Layer 2 Integration ==========
    async def execute_fix_plan(self, plan: "FixPlan") -> "FixResult":
        """
        Execute a validated FixPlan created by analysis stage.

        This is the new entry point for the two-stage pipeline.
        The old analyze_and_fix() method is kept for backwards compatibility.

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
            self.log(
                f"Plan has no changes to apply for {plan.file_path}", level="WARNING"
            )
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Plan has no changes to apply"],
                recommendations=["PlanningAgent should generate actual changes"],
            )

        # Validate that we can handle this file
        if not plan.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path in plan"],
                recommendations=["FixPlan must have file_path"],
            )

        # Read current file content
        try:
            file_content = await self._read_file_context(plan.file_path)
        except Exception as e:
            self.log(f"Failed to read file {plan.file_path}: {e}", level="ERROR")
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {e}"],
            )

        # Apply each change from the plan
        applied_changes = []
        for i, change in enumerate(plan.changes):
            try:
                # Validate line range
                lines = file_content.split("\n")
                if change.line_range[0] < 1 or change.line_range[1] > len(lines):
                    self.log(
                        f"Change {i}: Invalid line range {change.line_range} "
                        f"(file has {len(lines)} lines)"
                    )
                    continue

                # Extract old code
                old_lines = lines[change.line_range[0] - 1 : change.line_range[1]]
                old_code = "\n".join(old_lines)

                # Apply change
                new_content = file_content.replace(old_code, change.new_code)

                # Write back
                success = self.context.write_file_content(plan.file_path, new_content)
                if success:
                    applied_changes.append(f"Change {i}: {change.reason}")
                else:
                    self.log(f"Change {i} failed: {change.reason}", level="WARNING")
            except Exception as e:
                self.log(f"Change {i} failed: {e}", level="ERROR")
                applied_changes.append(f"Change {i} failed: {e}")

        # Return result
        success = len(applied_changes) == len(plan.changes)
        confidence = 0.8 if success else 0.0

        return FixResult(
            success=success,
            confidence=confidence,
            fixes_applied=applied_changes,
            remaining_issues=[] if success else ["Some changes failed"],
            files_modified=[plan.file_path] if success else [],
            recommendations=await self._enhance_recommendations_with_semantic([]),
        )


agent_registry.register(RefactoringAgent)
