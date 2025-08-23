import ast
import typing as t
from pathlib import Path

from .base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class RefactoringAgent(SubAgent):
    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.COMPLEXITY, IssueType.DEAD_CODE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.COMPLEXITY:
            return 0.9
        elif issue.type == IssueType.DEAD_CODE:
            return 0.8
        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing {issue.type.value} issue: {issue.message}")

        if issue.type == IssueType.COMPLEXITY:
            return await self._reduce_complexity(issue)
        elif issue.type == IssueType.DEAD_CODE:
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

        try:
            return await self._process_complexity_reduction(file_path)
        except SyntaxError as e:
            return self._create_syntax_error_result(e)
        except Exception as e:
            return self._create_general_error_result(e)

    def _validate_complexity_issue(self, issue: Issue) -> FixResult | None:
        """Validate the complexity issue has required information."""
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
        """Process complexity reduction for a file."""
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
        self, file_path: Path, content: str, complex_functions: list[dict[str, t.Any]]
    ) -> FixResult:
        """Apply refactoring and save changes."""
        refactored_content = self._apply_complexity_reduction(
            content, complex_functions
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
        """Create result for when no changes could be applied."""
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
        """Create result for syntax errors."""
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Syntax error in file: {error}"],
        )

    def _create_general_error_result(self, error: Exception) -> FixResult:
        """Create result for general errors."""
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
        """Validate the dead code issue has required information."""
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
        """Process dead code removal for a file."""
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
        self, file_path: Path, content: str, analysis: dict[str, t.Any]
    ) -> FixResult:
        """Apply dead code cleanup and save changes."""
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
        """Create result for when no cleanup could be applied."""
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
        """Create result for dead code processing errors."""
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Error processing file: {error}"],
        )

    def _find_complex_functions(
        self, tree: ast.AST, content: str
    ) -> list[dict[str, t.Any]]:
        complex_functions: list[dict[str, t.Any]] = []

        class ComplexityAnalyzer(ast.NodeVisitor):
            def __init__(
                self,
                calc_complexity: t.Callable[
                    [ast.FunctionDef | ast.AsyncFunctionDef], int
                ],
            ) -> None:
                self.calc_complexity = calc_complexity

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                complexity = self.calc_complexity(node)
                if complexity > 13:
                    complex_functions.append(
                        {
                            "name": node.name,
                            "line_start": node.lineno,
                            "line_end": node.end_lineno or node.lineno,
                            "complexity": complexity,
                            "node": node,
                        }
                    )
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                # Handle async functions like regular functions for complexity analysis
                complexity = self.calc_complexity(node)
                if complexity > 13:
                    complex_functions.append(
                        {
                            "name": node.name,
                            "line_start": node.lineno,
                            "line_end": node.end_lineno or node.lineno,
                            "complexity": complexity,
                            "node": node,
                        }
                    )
                self.generic_visit(node)

        analyzer = ComplexityAnalyzer(self._calculate_cognitive_complexity)
        analyzer.visit(tree)

        return complex_functions

    def _calculate_cognitive_complexity(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> int:
        class ComplexityCalculator(ast.NodeVisitor):
            def __init__(self):
                self.complexity = 0
                self.nesting_level = 0

            def visit_If(self, node: ast.If) -> None:
                self.complexity += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_For(self, node: ast.For) -> None:
                self.complexity += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_While(self, node: ast.While) -> None:
                self.complexity += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_Try(self, node: ast.Try) -> None:
                self.complexity += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_With(self, node):
                self.complexity += 1 + self.nesting_level
                self.nesting_level += 1
                self.generic_visit(node)
                self.nesting_level -= 1

            def visit_BoolOp(self, node):
                self.complexity += len(node.values) - 1
                self.generic_visit(node)

        calculator = ComplexityCalculator()
        calculator.visit(node)
        return calculator.complexity

    def _apply_complexity_reduction(
        self, content: str, complex_functions: list[dict[str, t.Any]]
    ) -> str:
        lines = content.split("\n")
        modified = False

        for func_info in complex_functions:
            func_lines = lines[func_info["line_start"] - 1 : func_info["line_end"]]

            extracted_methods = self._extract_helper_methods(func_lines, func_info)

            if extracted_methods:
                insert_pos = func_info["line_start"] - 1
                for method in reversed(extracted_methods):
                    lines.insert(insert_pos, method)
                    lines.insert(insert_pos, "")
                modified = True

        return "\n".join(lines) if modified else content

    def _extract_helper_methods(
        self, func_lines: list[str], func_info: dict[str, t.Any]
    ) -> list[str]:
        extracted_methods: list[str] = []

        for i, line in enumerate(func_lines):
            stripped = line.strip()

            if stripped.startswith("if ") and (
                " and " in stripped or " or " in stripped
            ):
                condition = stripped[3:].rstrip(": ")
                method_name = (
                    f"_is_{func_info['name']}_condition_{len(extracted_methods) + 1}"
                )

                helper_method = f"""def {method_name}(self) -> bool:
        \"\"\"Helper method for complex condition.\"\"\"
        return {condition}"""

                extracted_methods.append(helper_method)

                func_lines[i] = line.replace(condition, f"self.{method_name}()")

        return extracted_methods

    def _analyze_dead_code(self, tree: ast.AST, content: str) -> dict[str, t.Any]:
        analysis = {
            "unused_imports": [],
            "unused_variables": [],
            "unused_functions": [],
            "removable_items": [],
        }

        analyzer_result = self._collect_usage_data(tree)
        self._process_unused_imports(analysis, analyzer_result)
        self._process_unused_functions(analysis, analyzer_result)

        return analysis

    def _collect_usage_data(self, tree: ast.AST) -> dict[str, t.Any]:
        defined_names: set[str] = set()
        used_names: set[str] = set()
        import_lines: list[tuple[int, str, str]] = []
        unused_functions: list[dict[str, t.Any]] = []

        class UsageAnalyzer(ast.NodeVisitor):
            def visit_Import(self, node):
                for alias in node.names:
                    name = alias.asname or alias.name
                    defined_names.add(name)
                    import_lines.append((node.lineno, name, "import"))

            def visit_ImportFrom(self, node):
                for alias in node.names:
                    name = alias.asname or alias.name
                    defined_names.add(name)
                    import_lines.append((node.lineno, name, "from_import"))

            def visit_FunctionDef(self, node):
                defined_names.add(node.name)
                if not node.name.startswith("_"):
                    unused_functions.append(node.name)
                self.generic_visit(node)

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load):
                    used_names.add(node.id)

        analyzer = UsageAnalyzer()
        analyzer.visit(tree)

        return {
            "defined_names": defined_names,
            "used_names": used_names,
            "import_lines": import_lines,
            "unused_functions": unused_functions,
        }

    def _process_unused_imports(
        self, analysis: dict[str, t.Any], analyzer_result: dict[str, t.Any]
    ) -> None:
        for line_no, name, import_type in analyzer_result["import_lines"]:
            if name not in analyzer_result["used_names"]:
                analysis["unused_imports"].append(
                    {
                        "name": name,
                        "line": line_no,
                        "type": import_type,
                    }
                )
                analysis["removable_items"].append(f"unused import: {name}")

    def _process_unused_functions(
        self, analysis: dict[str, t.Any], analyzer_result: dict[str, t.Any]
    ) -> None:
        unused_functions = [
            func
            for func in analyzer_result["unused_functions"]
            if func not in analyzer_result["used_names"]
        ]
        analysis["unused_functions"] = unused_functions
        for func in unused_functions:
            analysis["removable_items"].append(f"unused function: {func}")

    def _remove_dead_code_items(self, content: str, analysis: dict[str, t.Any]) -> str:
        lines = content.split("\n")
        lines_to_remove = set()

        for unused_import in analysis["unused_imports"]:
            line_idx = unused_import["line"] - 1
            if 0 <= line_idx < len(lines):
                line = lines[line_idx]

                if unused_import["type"] == "import":
                    if f"import {unused_import['name']}" in line:
                        lines_to_remove.add(line_idx)
                elif unused_import["type"] == "from_import":
                    if "from " in line and unused_import["name"] in line:
                        if line.strip().endswith(unused_import["name"]):
                            lines_to_remove.add(line_idx)

        filtered_lines = [
            line for i, line in enumerate(lines) if i not in lines_to_remove
        ]

        return "\n".join(filtered_lines)


agent_registry.register(RefactoringAgent)
