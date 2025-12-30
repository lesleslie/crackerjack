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

        # Initialize helper modules
        self._complexity_analyzer = ComplexityAnalyzer(context)
        self._code_transformer = CodeTransformer(context)
        self._dead_code_detector = DeadCodeDetector(context)

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
            stripped, current_function, line
        )

    def _should_remove_import_line(
        self, line: str, unused_import: dict[str, str]
    ) -> bool:
        return self._dead_code_detector._should_remove_import_line(line, unused_import)

    def _extract_nested_conditions(self, content: str) -> str:
        return self._code_transformer._extract_nested_conditions(content)

    def _simplify_boolean_expressions(self, content: str) -> str:
        return self._code_transformer._simplify_boolean_expressions(content)

    def _is_empty_except_block(self, lines: list[str], line_idx: int) -> bool:
        return self._dead_code_detector._is_empty_except_block(lines, line_idx)

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.COMPLEXITY, IssueType.DEAD_CODE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.COMPLEXITY:
            return 0.9 if self._has_complexity_markers(issue) else 0.85
        if issue.type == IssueType.DEAD_CODE:
            return 0.8 if self._has_dead_code_markers(issue) else 0.75
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

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing {issue.type.value} issue: {issue.message}")

        if issue.type == IssueType.COMPLEXITY:
            return await self._reduce_complexity(issue)
        if issue.type == IssueType.DEAD_CODE:
            return await self._remove_dead_code(issue)

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

        try:
            return await self._process_complexity_reduction(file_path)
        except SyntaxError as e:
            return self._create_syntax_error_result(e)
        except Exception as e:
            return self._create_general_error_result(e)

    async def _apply_known_complexity_fix(
        self, file_path: Path, issue: Issue
    ) -> FixResult:
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        # Delegate to code transformer helper
        refactored_content = self._code_transformer.refactor_detect_agent_needs_pattern(
            content
        )

        if refactored_content != content:
            success = self.context.write_file_content(file_path, refactored_content)
            if success:
                return FixResult(
                    success=True,
                    confidence=0.9,
                    fixes_applied=[
                        "Applied proven complexity reduction pattern for detect_agent_needs"
                    ],
                    files_modified=[str(file_path)],
                    recommendations=await self._enhance_recommendations_with_semantic(
                        ["Verify functionality after complexity reduction"]
                    ),
                )
            else:
                return FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[
                        f"Failed to write refactored content to {file_path}"
                    ],
                )
        else:
            return FixResult(
                success=False,
                confidence=0.3,
                remaining_issues=[
                    "Refactoring pattern did not apply to current file content"
                ],
                recommendations=[
                    "File may have been modified since pattern was created"
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
        # Delegate to complexity analyzer helper
        complex_functions = self._complexity_analyzer.find_complex_functions(
            tree, content
        )

        # Enhance complex function detection with semantic analysis
        semantic_complex_functions = await self._find_semantic_complex_patterns(
            content, file_path
        )
        if semantic_complex_functions:
            complex_functions.extend(semantic_complex_functions)

        if not complex_functions:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No overly complex functions found"],
            )

        return await self._apply_and_save_refactoring(
            file_path, content, complex_functions
        )

    async def _apply_and_save_refactoring(
        self,
        file_path: Path,
        content: str,
        complex_functions: list[dict[str, t.Any]],
    ) -> FixResult:
        # Delegate refactoring to code transformer helper
        refactored_content = self._code_transformer.refactor_complex_functions(
            content, complex_functions
        )

        if refactored_content == content:
            # Try enhanced strategies if basic refactoring didn't work
            refactored_content = self._code_transformer.apply_enhanced_strategies(
                content
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
                ["Verify functionality after complexity reduction"]
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
        # Delegate to dead code detector helper
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
        # Remove dead code items
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
        self, lines: list[str], analysis: dict[str, t.Any]
    ) -> set[int]:
        """Collect all lines to remove from analysis."""
        lines_to_remove: set[int] = set()

        # Delegate to dead code detector helper for different removal types
        lines_to_remove.update(
            self._dead_code_detector.find_lines_to_remove(lines, analysis)
        )
        lines_to_remove.update(
            self._dead_code_detector._find_unreachable_lines(lines, analysis)
        )
        lines_to_remove.update(
            self._dead_code_detector._find_redundant_lines(lines, analysis)
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
        self, content: str, file_path: Path
    ) -> list[dict[str, t.Any]]:
        """Find semantically complex patterns using vector similarity."""
        semantic_functions = []

        try:
            # Delegate to complexity analyzer helper
            code_elements = (
                self._complexity_analyzer.extract_code_functions_for_semantic_analysis(
                    content
                )
            )

            for element in code_elements:
                if (
                    element["type"] == "function"
                    and element["estimated_complexity"] > 10
                ):
                    # Search for similar complex patterns
                    insight = (
                        await self.semantic_enhancer.find_refactoring_opportunities(
                            element["signature"]
                            + "\n"
                            + element["body"][:150],  # Include body sample
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
                                "refactor_opportunities": insight.related_patterns[
                                    :3
                                ],  # Top 3 matches
                                "node": element.get("node"),
                            }
                        )

                        # Store insight for recommendation enhancement
                        self.semantic_insights[element["name"]] = insight

        except Exception as e:
            self.log(f"Warning: Semantic complexity detection failed: {e}")

        return semantic_functions

    async def _enhance_recommendations_with_semantic(
        self, base_recommendations: list[str]
    ) -> list[str]:
        """Enhance recommendations with semantic insights."""
        enhanced = base_recommendations.copy()

        # Add semantic insights if available
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
                    f"consider extracting common refactoring utilities"
                )

            if total_semantic_matches >= 3:
                enhanced.append(
                    f"Found {total_semantic_matches} related complexity patterns across codebase - "
                    f"review for consistent refactoring approach"
                )

            # Store insights for session continuity
            for func_name, insight in self.semantic_insights.items():
                summary = self.semantic_enhancer.get_semantic_context_summary(insight)
                self.log(f"Semantic context for {func_name}: {summary}")
                await self.semantic_enhancer.store_insight_to_session(
                    insight, "RefactoringAgent"
                )

        # Enhance with session-stored insights
        enhanced = await get_session_enhanced_recommendations(
            enhanced, "RefactoringAgent", self.context.project_path
        )

        return enhanced


agent_registry.register(RefactoringAgent)
