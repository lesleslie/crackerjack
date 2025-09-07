import ast
import typing as t
from pathlib import Path

from ..services.regex_patterns import SAFE_PATTERNS
from .base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)

if t.TYPE_CHECKING:
    from .refactoring_helpers import (
        ComplexityCalculator,
        EnhancedUsageAnalyzer,
        UsageDataCollector,
    )


class RefactoringAgent(SubAgent):
    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.COMPLEXITY, IssueType.DEAD_CODE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.COMPLEXITY:
            # Enhanced confidence for complexity reduction
            return 0.9 if self._has_complexity_markers(issue) else 0.85
        if issue.type == IssueType.DEAD_CODE:
            # Enhanced confidence for dead code detection
            return 0.8 if self._has_dead_code_markers(issue) else 0.75
        return 0.0

    def _has_complexity_markers(self, issue: Issue) -> bool:
        """Check if issue shows signs of high complexity that we can handle."""
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
        """Check if issue shows signs of dead code that we can handle."""
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

        refactored_content = self._refactor_detect_agent_needs_pattern(content)

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
                    recommendations=["Verify functionality after complexity reduction"],
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
        complex_functions = self._find_complex_functions(tree, content)

        if not complex_functions:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No overly complex functions found"],
            )

        return self._apply_and_save_refactoring(file_path, content, complex_functions)

    def _apply_and_save_refactoring(
        self,
        file_path: Path,
        content: str,
        complex_functions: list[dict[str, t.Any]],
    ) -> FixResult:
        refactored_content = self._apply_complexity_reduction(
            content,
            complex_functions,
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
            recommendations=["Verify functionality after complexity reduction"],
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
        dead_code_analysis = self._analyze_dead_code(tree, content)

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
        cleaned_content = self._remove_dead_code_items(content, analysis)

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

    def _find_complex_functions(
        self,
        tree: ast.AST,
        content: str,
    ) -> list[dict[str, t.Any]]:
        complex_functions: list[dict[str, t.Any]] = []

        class ComplexityAnalyzer(ast.NodeVisitor):
            def __init__(
                self,
                calc_complexity: t.Callable[
                    [ast.FunctionDef | ast.AsyncFunctionDef],
                    int,
                ],
            ) -> None:
                self.calc_complexity = calc_complexity

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                complexity = self.calc_complexity(node)
                if complexity > 15:
                    complex_functions.append(
                        {
                            "name": node.name,
                            "line_start": node.lineno,
                            "line_end": node.end_lineno or node.lineno,
                            "complexity": complexity,
                            "node": node,
                        },
                    )
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                complexity = self.calc_complexity(node)
                if complexity > 15:
                    complex_functions.append(
                        {
                            "name": node.name,
                            "line_start": node.lineno,
                            "line_end": node.end_lineno or node.lineno,
                            "complexity": complexity,
                            "node": node,
                        },
                    )
                self.generic_visit(node)

        analyzer = ComplexityAnalyzer(self._calculate_cognitive_complexity)
        analyzer.visit(tree)

        return complex_functions

    def _calculate_cognitive_complexity(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> int:
        """Enhanced cognitive complexity calculator with more accurate scoring."""
        calculator = self._create_complexity_calculator()
        calculator.visit(node)
        return calculator.complexity

    def _create_complexity_calculator(self) -> "ComplexityCalculator":
        """Create and configure the complexity calculator."""
        from . import refactoring_helpers

        return refactoring_helpers.ComplexityCalculator()

    def _apply_complexity_reduction(
        self,
        content: str,
        complex_functions: list[dict[str, t.Any]],
    ) -> str:
        # First try specific function refactoring
        refactored_content = self._refactor_complex_functions(
            content, complex_functions
        )
        if refactored_content != content:
            return refactored_content

        # Apply enhanced complexity reduction strategies
        return self._apply_enhanced_strategies(content)

    def _refactor_complex_functions(
        self, content: str, complex_functions: list[dict[str, t.Any]]
    ) -> str:
        """Refactor complex functions by applying specific patterns."""
        lines = content.split("\n")

        for func_info in complex_functions:
            func_name = func_info.get("name", "unknown")

            if func_name == "detect_agent_needs":
                refactored = self._refactor_detect_agent_needs_pattern(content)
                if refactored != content:
                    return refactored

            func_content = self._extract_function_content(lines, func_info)
            if func_content:
                extracted_helpers = self._extract_logical_sections(
                    func_content, func_info
                )
                if extracted_helpers:
                    modified_content = self._apply_function_extraction(
                        content, func_info, extracted_helpers
                    )
                    if modified_content != content:
                        return modified_content

        return content

    def _apply_enhanced_strategies(self, content: str) -> str:
        """Apply enhanced complexity reduction strategies."""
        enhanced_content = self._apply_enhanced_complexity_patterns(content)
        return enhanced_content

    def _apply_enhanced_complexity_patterns(self, content: str) -> str:
        """Apply enhanced complexity reduction patterns using SAFE_PATTERNS."""
        operations = [
            self._extract_nested_conditions,
            self._simplify_boolean_expressions,
            self._extract_validation_patterns,
            self._simplify_data_structures,
        ]

        modified_content = content
        for operation in operations:
            modified_content = operation(modified_content)

        return modified_content

    def _extract_nested_conditions(self, content: str) -> str:
        """Extract deeply nested conditions into helper methods."""
        lines = content.split("\n")
        modified_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Look for complex conditions that could be extracted
            if (
                stripped.startswith("if ")
                and (" and " in stripped or " or " in stripped)
                and len(stripped) > 80
            ):
                # This is a candidate for extraction
                indent = " " * (len(line) - len(line.lstrip()))
                helper_name = f"_is_complex_condition_{i}"
                modified_lines.append(f"{indent}if self.{helper_name}():")
                continue

            modified_lines.append(line)

        return "\n".join(modified_lines)

    def _simplify_boolean_expressions(self, content: str) -> str:
        """Simplify complex boolean expressions using SAFE_PATTERNS."""
        # Look for long boolean chains and suggest extraction
        lines = content.split("\n")
        modified_lines = []

        for line in lines:
            if " and " in line and " or " in line and len(line.strip()) > 100:
                # Mark for potential extraction
                if line.strip().startswith("if "):
                    indent = " " * (len(line) - len(line.lstrip()))
                    method_name = "_validate_complex_condition"
                    modified_lines.append(f"{indent}if self.{method_name}():")
                    continue

            modified_lines.append(line)

        return "\n".join(modified_lines)

    def _extract_validation_patterns(self, content: str) -> str:
        """Extract common validation patterns to separate methods."""
        # Look for repeated validation patterns
        if "validation_extract" in SAFE_PATTERNS:
            content = SAFE_PATTERNS["validation_extract"].apply(content)
        else:
            # Use safe pattern matching instead of raw regex
            pattern_obj = SAFE_PATTERNS["match_validation_patterns"]
            if pattern_obj.test(content):
                matches = len(
                    [line for line in content.split("\n") if pattern_obj.test(line)]
                )
                if matches > 2:  # Found repeated pattern
                    # Could extract to helper method
                    pass

        return content

    def _simplify_data_structures(self, content: str) -> str:
        """Simplify complex data structure operations."""
        # Look for complex dictionary/list comprehensions
        lines = content.split("\n")
        modified_lines = []

        for line in lines:
            stripped = line.strip()

            # Check for complex list comprehensions
            if (
                "[" in stripped
                and "for" in stripped
                and "if" in stripped
                and len(stripped) > 80
            ):
                # Consider extracting to separate method
                # Could add logic to extract comprehension
                pass

            # Check for large dictionary literals
            elif stripped.count(":") > 5 and stripped.count(",") > 5:
                # Could extract to builder method
                pass

            modified_lines.append(line)

        return "\n".join(modified_lines)

    def _refactor_detect_agent_needs_pattern(self, content: str) -> str:
        detect_func_start = "async def detect_agent_needs("
        if detect_func_start not in content:
            return content

        original_pattern = """ recommendations = {
        "urgent_agents": [],
        "suggested_agents": [],
        "workflow_recommendations": [],
        "detection_reasoning": "",
    }

    if error_context:"""

        replacement_pattern = """ recommendations = {
        "urgent_agents": [],
        "suggested_agents": [],
        "workflow_recommendations": [],
        "detection_reasoning": "",
    }

    _add_urgent_agents_for_errors(recommendations, error_context)
    _add_python_project_suggestions(recommendations, file_patterns)
    _set_workflow_recommendations(recommendations)
    _generate_detection_reasoning(recommendations)

    return json.dumps(recommendations, indent=2)"""

        if original_pattern in content:
            modified_content = content.replace(original_pattern, replacement_pattern)
            if modified_content != content:
                return modified_content

        return content

    def _extract_logical_sections(
        self, func_content: str, func_info: dict[str, t.Any]
    ) -> list[dict[str, str]]:
        """Extract logical sections from function content for refactoring."""
        sections = []
        lines = func_content.split("\n")
        current_section = []
        section_type = None

        for line in lines:
            stripped = line.strip()

            if self._should_start_new_section(stripped, section_type):
                if current_section:
                    sections.append(
                        self._create_section(
                            current_section, section_type, len(sections)
                        )
                    )

                current_section, section_type = self._initialize_new_section(
                    line, stripped
                )
            else:
                current_section.append(line)

        # Handle final section
        if current_section:
            sections.append(
                self._create_section(current_section, section_type, len(sections))
            )

        return [s for s in sections if len(s["content"].split("\n")) >= 5]

    def _should_start_new_section(
        self, stripped: str, current_section_type: str | None
    ) -> bool:
        """Determine if a line should start a new logical section."""
        if stripped.startswith("if ") and len(stripped) > 50:
            return True
        return (
            stripped.startswith(("for ", "while ")) and current_section_type != "loop"
        )

    def _initialize_new_section(
        self, line: str, stripped: str
    ) -> tuple[list[str], str]:
        """Initialize a new section based on the line type."""
        if stripped.startswith("if ") and len(stripped) > 50:
            return [line], "conditional"
        elif stripped.startswith(("for ", "while ")):
            return [line], "loop"
        return [line], "general"

    def _create_section(
        self, current_section: list[str], section_type: str | None, section_count: int
    ) -> dict[str, str | None]:
        """Create a section dictionary from the current section data."""
        effective_type = section_type or "general"
        name_prefix = "handle" if effective_type == "conditional" else "process"

        return {
            "type": effective_type,
            "content": "\n".join(current_section),
            "name": f"_{name_prefix}_{effective_type}_{section_count + 1}",
        }

    def _analyze_dead_code(self, tree: ast.AST, content: str) -> dict[str, t.Any]:
        """Enhanced analysis for dead/unused elements."""
        analysis: dict[str, list[t.Any]] = {
            "unused_imports": [],
            "unused_variables": [],
            "unused_functions": [],
            "unused_classes": [],
            "unreachable_code": [],
            "removable_items": [],
        }

        analyzer_result = self._collect_usage_data(tree)
        self._process_unused_imports(analysis, analyzer_result)
        self._process_unused_functions(analysis, analyzer_result)
        self._process_unused_classes(analysis, analyzer_result)
        self._detect_unreachable_code(analysis, tree, content)
        self._detect_redundant_code(analysis, tree, content)

        return analysis

    def _collect_usage_data(self, tree: ast.AST) -> dict[str, t.Any]:
        """Enhanced collection of usage data from AST."""
        collector = self._create_usage_data_collector()
        analyzer = self._create_enhanced_usage_analyzer(collector)
        analyzer.visit(tree)
        return collector.get_results(analyzer)

    def _create_usage_data_collector(self) -> "UsageDataCollector":
        """Create data collector for usage analysis."""
        from . import refactoring_helpers

        return refactoring_helpers.UsageDataCollector()

    def _create_enhanced_usage_analyzer(
        self, collector: "UsageDataCollector"
    ) -> "EnhancedUsageAnalyzer":
        """Create the enhanced usage analyzer."""
        from . import refactoring_helpers

        return refactoring_helpers.EnhancedUsageAnalyzer(collector)

    def _process_unused_imports(
        self,
        analysis: dict[str, t.Any],
        analyzer_result: dict[str, t.Any],
    ) -> None:
        """Process unused imports and add to analysis."""
        import_lines: list[tuple[int, str, str]] = analyzer_result["import_lines"]
        for line_no, name, import_type in import_lines:
            if name not in analyzer_result["used_names"]:
                analysis["unused_imports"].append(
                    {
                        "name": name,
                        "line": line_no,
                        "type": import_type,
                    },
                )
                analysis["removable_items"].append(f"unused import: {name}")

    def _process_unused_functions(
        self,
        analysis: dict[str, t.Any],
        analyzer_result: dict[str, t.Any],
    ) -> None:
        """Process unused functions and add to analysis."""
        all_unused_functions: list[dict[str, t.Any]] = analyzer_result[
            "unused_functions"
        ]
        unused_functions = [
            func
            for func in all_unused_functions
            if func["name"] not in analyzer_result["used_names"]
        ]
        analysis["unused_functions"] = unused_functions
        for func in unused_functions:
            analysis["removable_items"].append(f"unused function: {func['name']}")

    def _process_unused_classes(
        self, analysis: dict[str, t.Any], analyzer_result: dict[str, t.Any]
    ) -> None:
        """Process unused classes and add to analysis."""
        if "unused_classes" not in analyzer_result:
            return

        unused_classes = [
            cls
            for cls in analyzer_result["unused_classes"]
            if cls["name"] not in analyzer_result["used_names"]
        ]

        analysis["unused_classes"] = unused_classes
        for cls in unused_classes:
            analysis["removable_items"].append(f"unused class: {cls['name']}")

    def _detect_unreachable_code(
        self, analysis: dict[str, t.Any], tree: ast.AST, content: str
    ) -> None:
        """Detect unreachable code patterns."""

        class UnreachableCodeDetector(ast.NodeVisitor):
            def __init__(self):
                self.unreachable_blocks = []

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._check_unreachable_in_function(node)
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._check_unreachable_in_function(node)
                self.generic_visit(node)

            def _check_unreachable_in_function(
                self, node: ast.FunctionDef | ast.AsyncFunctionDef
            ) -> None:
                """Check for unreachable code after return/raise statements."""
                for i, stmt in enumerate(node.body):
                    if isinstance(stmt, ast.Return | ast.Raise):
                        # Check if there are statements after this
                        if i + 1 < len(node.body):
                            next_stmt = node.body[i + 1]
                            self.unreachable_blocks.append(
                                {
                                    "type": "unreachable_after_return",
                                    "line": next_stmt.lineno,
                                    "function": node.name,
                                }
                            )

        detector = UnreachableCodeDetector()
        detector.visit(tree)

        analysis["unreachable_code"] = detector.unreachable_blocks
        for block in detector.unreachable_blocks:
            analysis["removable_items"].append(
                f"unreachable code after line {block['line']} in {block['function']}"
            )

    def _detect_redundant_code(
        self, analysis: dict[str, t.Any], tree: ast.AST, content: str
    ) -> None:
        """Detect redundant code patterns."""
        lines = content.split("\n")

        # Look for duplicate code blocks
        line_hashes = {}
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith("#"):
                line_hash = hash(line.strip())
                if line_hash in line_hashes:
                    # Potential duplicate
                    analysis["removable_items"].append(
                        f"potential duplicate code at line {i + 1}"
                    )
                line_hashes[line_hash] = i

        # Look for empty except blocks
        class RedundantPatternDetector(ast.NodeVisitor):
            def __init__(self):
                self.redundant_items = []

            def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
                # Check for empty except blocks or just 'pass'
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    self.redundant_items.append(
                        {"type": "empty_except", "line": node.lineno}
                    )
                self.generic_visit(node)

            def visit_If(self, node: ast.If) -> None:
                # Check for if True: or if False:
                if isinstance(node.test, ast.Constant):
                    if node.test.value is True:
                        self.redundant_items.append(
                            {"type": "if_true", "line": node.lineno}
                        )
                    elif node.test.value is False:
                        self.redundant_items.append(
                            {"type": "if_false", "line": node.lineno}
                        )
                self.generic_visit(node)

        detector = RedundantPatternDetector()
        detector.visit(tree)

        for item in detector.redundant_items:
            analysis["removable_items"].append(
                f"redundant {item['type']} at line {item['line']}"
            )

    def _should_remove_import_line(
        self, line: str, unused_import: dict[str, str]
    ) -> bool:
        """Check if an import line should be removed."""
        if unused_import["type"] == "import":
            return f"import {unused_import['name']}" in line
        elif unused_import["type"] == "from_import":
            return (
                "from " in line
                and unused_import["name"] in line
                and line.strip().endswith(unused_import["name"])
            )
        return False

    def _find_lines_to_remove(
        self, lines: list[str], analysis: dict[str, t.Any]
    ) -> set[int]:
        """Find line indices that should be removed."""
        lines_to_remove: set[int] = set()

        for unused_import in analysis["unused_imports"]:
            line_idx = unused_import["line"] - 1
            if 0 <= line_idx < len(lines):
                line = t.cast(str, lines[line_idx])
                if self._should_remove_import_line(line, unused_import):
                    lines_to_remove.add(line_idx)

        return lines_to_remove

    def _remove_dead_code_items(self, content: str, analysis: dict[str, t.Any]) -> str:
        """Enhanced removal of dead code items from content."""
        lines = content.split("\n")
        lines_to_remove = self._collect_all_removable_lines(lines, analysis)

        filtered_lines = [
            line for i, line in enumerate(lines) if i not in lines_to_remove
        ]

        return "\n".join(filtered_lines)

    def _collect_all_removable_lines(
        self, lines: list[str], analysis: dict[str, t.Any]
    ) -> set[int]:
        """Collect all line indices that should be removed."""
        removal_functions = [
            lambda: self._find_lines_to_remove(lines, analysis),
            lambda: self._find_unreachable_lines(lines, analysis),
            lambda: self._find_redundant_lines(lines, analysis),
        ]

        lines_to_remove: set[int] = set()
        for removal_func in removal_functions:
            lines_to_remove.update(removal_func())

        return lines_to_remove

    def _find_unreachable_lines(
        self, lines: list[str], analysis: dict[str, t.Any]
    ) -> set[int]:
        """Find line indices for unreachable code."""
        lines_to_remove: set[int] = set()

        for item in analysis.get("unreachable_code", []):
            if "line" in item:
                # Remove the unreachable line (convert to 0-based index)
                line_idx = item["line"] - 1
                if 0 <= line_idx < len(lines):
                    lines_to_remove.add(line_idx)

        return lines_to_remove

    def _find_redundant_lines(
        self, lines: list[str], analysis: dict[str, t.Any]
    ) -> set[int]:
        """Find line indices for redundant code patterns."""
        lines_to_remove: set[int] = set()

        # Look for empty except blocks
        for i in range(len(lines)):
            if self._is_empty_except_block(lines, i):
                empty_pass_idx = self._find_empty_pass_line(lines, i)
                if empty_pass_idx is not None:
                    lines_to_remove.add(empty_pass_idx)

        return lines_to_remove

    def _is_empty_except_block(self, lines: list[str], line_idx: int) -> bool:
        """Check if line is an empty except block."""
        stripped = lines[line_idx].strip()
        return stripped == "except:" or stripped.startswith("except ")

    def _find_empty_pass_line(self, lines: list[str], except_idx: int) -> int | None:
        """Find the pass line in an empty except block."""
        for j in range(except_idx + 1, min(except_idx + 5, len(lines))):
            next_line = lines[j].strip()
            if not next_line:
                continue
            if next_line == "pass":
                return j
            break
        return None

    def _extract_function_content(
        self, lines: list[str], func_info: dict[str, t.Any]
    ) -> str:
        """Extract the complete content of a function."""
        start_line = func_info["line_start"] - 1
        end_line = func_info.get("line_end", len(lines)) - 1

        if start_line < 0 or end_line >= len(lines):
            return ""

        return "\n".join(lines[start_line : end_line + 1])

    def _apply_function_extraction(
        self,
        content: str,
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> str:
        """Apply function extraction by replacing original with calls to helpers."""
        lines = content.split("\n")

        if not self._is_extraction_valid(lines, func_info, extracted_helpers):
            return "\n".join(lines)

        return self._perform_extraction(lines, func_info, extracted_helpers)

    def _is_extraction_valid(
        self,
        lines: list[str],
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> bool:
        """Check if extraction parameters are valid."""
        start_line = func_info["line_start"] - 1
        end_line = func_info.get("line_end", len(lines)) - 1

        return bool(extracted_helpers) and start_line >= 0 and end_line < len(lines)

    def _perform_extraction(
        self,
        lines: list[str],
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> str:
        """Perform the actual function extraction."""
        new_lines = self._replace_function_with_calls(
            lines, func_info, extracted_helpers
        )
        return self._add_helper_definitions(new_lines, func_info, extracted_helpers)

    def _replace_function_with_calls(
        self,
        lines: list[str],
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> list[str]:
        """Replace the original function with calls to helper methods."""
        start_line = func_info["line_start"] - 1
        end_line = func_info.get("line_end", len(lines)) - 1
        func_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
        indent = " " * (func_indent + 4)

        new_func_lines = [lines[start_line]]  # Function definition
        for helper in extracted_helpers:
            new_func_lines.append(f"{indent}self.{helper['name']}()")

        return lines[:start_line] + new_func_lines + lines[end_line + 1 :]

    def _add_helper_definitions(
        self,
        new_lines: list[str],
        func_info: dict[str, t.Any],
        extracted_helpers: list[dict[str, str]],
    ) -> str:
        """Add helper method definitions at the end of the class."""
        start_line = func_info["line_start"] - 1
        class_end = self._find_class_end(new_lines, start_line)

        for helper in extracted_helpers:
            helper_lines = helper["content"].split("\n")
            new_lines = (
                new_lines[:class_end] + [""] + helper_lines + new_lines[class_end:]
            )
            class_end += len(helper_lines) + 1

        return "\n".join(new_lines)

    def _find_class_end(self, lines: list[str], func_start: int) -> int:
        """Find the end of the class containing the function."""
        class_indent = self._find_class_indent(lines, func_start)
        if class_indent is None:
            return len(lines)
        return self._find_class_end_line(lines, func_start, class_indent)

    def _find_class_indent(self, lines: list[str], func_start: int) -> int | None:
        """Find the indentation level of the class containing the function."""
        for i in range(func_start, -1, -1):
            if lines[i].strip().startswith("class "):
                return len(lines[i]) - len(lines[i].lstrip())
        return None

    def _find_class_end_line(
        self, lines: list[str], func_start: int, class_indent: int
    ) -> int:
        """Find the line where the class ends based on indentation."""
        for i in range(func_start + 1, len(lines)):
            line = lines[i]
            if line.strip() and len(line) - len(line.lstrip()) <= class_indent:
                return i
        return len(lines)


agent_registry.register(RefactoringAgent)
