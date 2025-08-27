import ast
import operator
import typing as t
from contextlib import suppress
from pathlib import Path

from .base import (
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class PerformanceAgent(SubAgent):
    """Agent specialized in detecting and fixing performance issues and anti-patterns."""

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.PERFORMANCE}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type == IssueType.PERFORMANCE:
            return 0.85
        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing performance issue: {issue.message}")

        validation_result = self._validate_performance_issue(issue)
        if validation_result:
            return validation_result

        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided for performance issue"],
            )

        file_path = Path(issue.file_path)

        try:
            return await self._process_performance_optimization(file_path)
        except Exception as e:
            return self._create_performance_error_result(e)

    def _validate_performance_issue(self, issue: Issue) -> FixResult | None:
        """Validate the performance issue has required information."""
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path specified for performance issue"],
            )

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )

        return None

    async def _process_performance_optimization(self, file_path: Path) -> FixResult:
        """Process performance issue detection and optimization for a file."""
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        performance_issues = self._detect_performance_issues(content, file_path)

        if not performance_issues:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No performance issues detected"],
            )

        return self._apply_and_save_optimizations(
            file_path,
            content,
            performance_issues,
        )

    def _apply_and_save_optimizations(
        self,
        file_path: Path,
        content: str,
        issues: list[dict[str, t.Any]],
    ) -> FixResult:
        """Apply performance optimizations and save changes."""
        optimized_content = self._apply_performance_optimizations(content, issues)

        if optimized_content == content:
            return self._create_no_optimization_result()

        success = self.context.write_file_content(file_path, optimized_content)
        if not success:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write optimized file: {file_path}"],
            )

        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=[
                f"Optimized {len(issues)} performance issues",
                "Applied algorithmic improvements",
            ],
            files_modified=[str(file_path)],
            recommendations=["Test performance improvements with benchmarks"],
        )

    def _create_no_optimization_result(self) -> FixResult:
        """Create result for when no optimizations could be applied."""
        return FixResult(
            success=False,
            confidence=0.6,
            remaining_issues=["Could not automatically optimize performance"],
            recommendations=[
                "Manual optimization required",
                "Consider algorithm complexity improvements",
                "Review data structure choices",
                "Profile code execution for bottlenecks",
            ],
        )

    def _create_performance_error_result(self, error: Exception) -> FixResult:
        """Create result for performance processing errors."""
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Error processing file: {error}"],
        )

    def _detect_performance_issues(
        self,
        content: str,
        file_path: Path,
    ) -> list[dict[str, t.Any]]:
        """Detect various performance anti-patterns in the code."""
        issues: list[dict[str, t.Any]] = []

        with suppress(SyntaxError):
            tree = ast.parse(content)

            # Detect nested loops
            issues.extend(self._detect_nested_loops(tree))

            # Detect inefficient list operations
            issues.extend(self._detect_inefficient_list_ops(content, tree))

            # Detect repeated expensive operations
            issues.extend(self._detect_repeated_operations(content, tree))

            # Detect inefficient string operations
            issues.extend(self._detect_string_inefficiencies(content))

        return issues

    def _detect_nested_loops(self, tree: ast.AST) -> list[dict[str, t.Any]]:
        """Detect nested loops that might have O(n²) or worse complexity."""
        issues: list[dict[str, t.Any]] = []

        class NestedLoopAnalyzer(ast.NodeVisitor):
            def __init__(self) -> None:
                self.loop_stack: list[tuple[str, ast.AST]] = []
                self.nested_loops: list[dict[str, t.Any]] = []

            def visit_For(self, node: ast.For) -> None:
                self.loop_stack.append(("for", node))
                if len(self.loop_stack) > 1:
                    self.nested_loops.append(
                        {
                            "line_number": node.lineno,
                            "type": "nested_for_loop",
                            "depth": len(self.loop_stack),
                            "node": node,
                        },
                    )
                self.generic_visit(node)
                self.loop_stack.pop()

            def visit_While(self, node: ast.While) -> None:
                self.loop_stack.append(("while", node))
                if len(self.loop_stack) > 1:
                    self.nested_loops.append(
                        {
                            "line_number": node.lineno,
                            "type": "nested_while_loop",
                            "depth": len(self.loop_stack),
                            "node": node,
                        },
                    )
                self.generic_visit(node)
                self.loop_stack.pop()

        analyzer = NestedLoopAnalyzer()
        analyzer.visit(tree)

        if analyzer.nested_loops:
            issues.append(
                {
                    "type": "nested_loops",
                    "instances": analyzer.nested_loops,
                    "suggestion": "Consider flattening loops or using more efficient algorithms",
                },
            )

        return issues

    def _detect_inefficient_list_ops(
        self,
        content: str,
        tree: ast.AST,
    ) -> list[dict[str, t.Any]]:
        """Detect inefficient list operations like repeated appends or concatenations."""
        issues: list[dict[str, t.Any]] = []
        content.split("\n")

        # Pattern: list += [item] or list = list + [item] in loops

        class ListOpAnalyzer(ast.NodeVisitor):
            def __init__(self) -> None:
                self.in_loop = False
                self.list_ops: list[dict[str, t.Any]] = []

            def visit_For(self, node: ast.For) -> None:
                old_in_loop = self.in_loop
                self.in_loop = True
                self.generic_visit(node)
                self.in_loop = old_in_loop

            def visit_While(self, node: ast.While) -> None:
                old_in_loop = self.in_loop
                self.in_loop = True
                self.generic_visit(node)
                self.in_loop = old_in_loop

            def visit_AugAssign(self, node: ast.AugAssign) -> None:
                if self.in_loop and isinstance(node.op, ast.Add):
                    if isinstance(node.value, ast.List):
                        self.list_ops.append(
                            {
                                "line_number": node.lineno,
                                "type": "list_concat_in_loop",
                                "pattern": "list += [item]",
                            },
                        )
                self.generic_visit(node)

        analyzer = ListOpAnalyzer()
        analyzer.visit(tree)

        if analyzer.list_ops:
            issues.append(
                {
                    "type": "inefficient_list_operations",
                    "instances": analyzer.list_ops,
                    "suggestion": "Use list.append() or collect items first, then extend",
                },
            )

        return issues

    def _detect_repeated_operations(
        self,
        content: str,
        tree: ast.AST,
    ) -> list[dict[str, t.Any]]:
        """Detect repeated expensive operations that could be cached."""
        lines = content.split("\n")
        repeated_calls = self._find_expensive_operations_in_loops(lines)

        return self._create_repeated_operations_issues(repeated_calls)

    def _find_expensive_operations_in_loops(
        self,
        lines: list[str],
    ) -> list[dict[str, t.Any]]:
        """Find expensive operations that occur within loop contexts."""
        repeated_calls: list[dict[str, t.Any]] = []
        expensive_patterns = self._get_expensive_operation_patterns()

        for i, line in enumerate(lines):
            stripped = line.strip()
            if self._contains_expensive_operation(stripped, expensive_patterns):
                if self._is_in_loop_context(lines, i):
                    repeated_calls.append(self._create_operation_record(i, stripped))

        return repeated_calls

    def _get_expensive_operation_patterns(self) -> tuple[str, ...]:
        """Get patterns for expensive operations to detect."""
        return (
            ".exists()",
            ".read_text()",
            ".glob(",
            ".rglob(",
            "Path(",
            "len(",
            ".get(",
        )

    def _contains_expensive_operation(
        self,
        line: str,
        patterns: tuple[str, ...],
    ) -> bool:
        """Check if line contains any expensive operation patterns."""
        return any(pattern in line for pattern in patterns)

    def _is_in_loop_context(self, lines: list[str], line_index: int) -> bool:
        """Check if line is within a loop context using simple heuristic."""
        context_start = max(0, line_index - 5)
        context_lines = lines[context_start : line_index + 1]
        # Performance: Use compiled patterns and single check per line
        loop_keywords = ("for ", "while ")
        return any(
            any(keyword in ctx_line for keyword in loop_keywords)
            for ctx_line in context_lines
        )

    def _create_operation_record(
        self,
        line_index: int,
        content: str,
    ) -> dict[str, t.Any]:
        """Create a record for an expensive operation found in a loop."""
        return {
            "line_number": line_index + 1,
            "content": content,
            "type": "expensive_operation_in_loop",
        }

    def _create_repeated_operations_issues(
        self,
        repeated_calls: list[dict[str, t.Any]],
    ) -> list[dict[str, t.Any]]:
        """Create issues list for repeated operations if threshold is met."""
        if len(repeated_calls) >= 2:
            return [
                {
                    "type": "repeated_expensive_operations",
                    "instances": repeated_calls,
                    "suggestion": "Cache expensive operations outside loops",
                },
            ]
        return []

    def _detect_string_inefficiencies(self, content: str) -> list[dict[str, t.Any]]:
        """Detect inefficient string operations."""
        issues: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        # Pattern: String concatenation in loops
        string_concat_in_loop: list[dict[str, t.Any]] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if "+=" in stripped and any(quote in stripped for quote in ('"', "'")):
                # Check if in loop context
                context_start = max(0, i - 5)
                context_lines = lines[context_start : i + 1]
                # Performance: Use tuple lookup for faster keyword matching
                loop_keywords = ("for ", "while ")
                if any(
                    any(keyword in ctx_line for keyword in loop_keywords)
                    for ctx_line in context_lines
                ):
                    string_concat_in_loop.append(
                        {
                            "line_number": i + 1,
                            "content": stripped,
                        },
                    )

        if len(string_concat_in_loop) >= 2:
            issues.append(
                {
                    "type": "string_concatenation_in_loop",
                    "instances": string_concat_in_loop,
                    "suggestion": 'Use list.append() and "".join() for string building',
                },
            )

        return issues

    def _apply_performance_optimizations(
        self,
        content: str,
        issues: list[dict[str, t.Any]],
    ) -> str:
        """Apply performance optimizations for detected issues."""
        lines = content.split("\n")
        modified = False

        for issue in issues:
            if issue["type"] == "inefficient_list_operations":
                lines, changed = self._fix_list_operations(lines, issue)
                modified = modified or changed
            elif issue["type"] == "string_concatenation_in_loop":
                lines, changed = self._fix_string_concatenation(lines, issue)
                modified = modified or changed
            elif issue["type"] == "repeated_expensive_operations":
                lines, changed = self._fix_repeated_operations(lines, issue)
                modified = modified or changed

        return "\n".join(lines) if modified else content

    def _fix_list_operations(
        self,
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Fix inefficient list operations by replacing list += [item] with list.append(item)."""
        modified = False

        # Process instances in reverse order (highest line numbers first) to avoid line number shifts
        instances = sorted(
            issue["instances"],
            key=operator.itemgetter("line_number"),
            reverse=True,
        )

        for instance in instances:
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = t.cast(str, lines[line_idx])

                # Transform: list += [item] -> list.append(item)
                # Pattern: variable_name += [expression]
                import re

                pattern = r"(\s*)(\w+)\s*\+=\s*\[([^]]+)\]"
                match = re.match(pattern, original_line)

                if match:
                    indent, var_name, item_expr = match.groups()
                    optimized_line = f"{indent}{var_name}.append({item_expr})"
                    lines[line_idx] = optimized_line
                    modified = True

                    # Add comment explaining the optimization
                    comment = (
                        f"{indent}# Performance: Changed += [item] to .append(item)"
                    )
                    lines.insert(line_idx, comment)

        return lines, modified

    def _fix_string_concatenation(
        self,
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Fix inefficient string concatenation in loops by transforming to list.append + join pattern."""
        var_groups = self._group_concatenation_instances(lines, issue["instances"])
        return self._apply_concatenation_optimizations(lines, var_groups)

    def _group_concatenation_instances(
        self,
        lines: list[str],
        instances: list[dict[str, t.Any]],
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Group string concatenation instances by variable name."""
        var_groups: dict[str, list[dict[str, t.Any]]] = {}

        for instance in instances:
            line_info = self._parse_concatenation_line(lines, instance)
            if line_info:
                var_name = line_info["var_name"]
                if var_name not in var_groups:
                    var_groups[var_name] = []
                var_groups[var_name].append(line_info)

        return var_groups

    def _parse_concatenation_line(
        self,
        lines: list[str],
        instance: dict[str, t.Any],
    ) -> dict[str, t.Any] | None:
        """Parse a string concatenation line to extract variable info."""
        line_idx = instance["line_number"] - 1
        if line_idx >= len(lines):
            return None

        original_line = t.cast(str, lines[line_idx])

        import re

        pattern = r"(\s*)(\w+)\s*\+=\s*(.+)"
        match = re.match(pattern, original_line)

        if match:
            indent, var_name, expr = match.groups()
            return {
                "line_idx": line_idx,
                "indent": indent,
                "var_name": var_name,
                "expr": expr.strip(),
                "original_line": original_line,
            }
        return None

    def _apply_concatenation_optimizations(
        self,
        lines: list[str],
        var_groups: dict[str, list[dict[str, t.Any]]],
    ) -> tuple[list[str], bool]:
        """Apply string building optimizations for each variable group."""
        modified = False

        for var_name, instances in var_groups.items():
            if instances:
                first_instance = instances[0]
                loop_start = self._find_loop_start(lines, first_instance["line_idx"])

                if loop_start is not None:
                    optimization_applied = self._apply_string_building_optimization(
                        lines, var_name, instances, loop_start
                    )
                    modified = modified or optimization_applied

        return lines, modified

    def _find_loop_start(self, lines: list[str], start_idx: int) -> int | None:
        """Find the start of the loop that contains the given line."""
        for i in range(start_idx, -1, -1):
            line = lines[i].strip()
            if line.startswith(("for ", "while ")):
                return i
            # Stop if we hit a function definition or class definition
            if line.startswith(("def ", "class ")):
                break
        return None

    def _apply_string_building_optimization(
        self,
        lines: list[str],
        var_name: str,
        instances: list[dict[str, t.Any]],
        loop_start: int,
    ) -> bool:
        """Apply string building optimization using list.append + join pattern."""
        if not instances:
            return False

        first_instance = instances[0]
        indent = first_instance["indent"]

        init_line_idx = self._find_variable_initialization(lines, var_name, loop_start)
        if init_line_idx is not None:
            self._transform_string_initialization(
                lines, init_line_idx, var_name, indent
            )
            self._replace_concatenations_with_appends(
                lines, instances, var_name, indent
            )
            self._add_join_after_loop(lines, var_name, indent, loop_start)
            return True

        return False

    def _find_variable_initialization(
        self,
        lines: list[str],
        var_name: str,
        loop_start: int,
    ) -> int | None:
        """Find the line where the string variable is initialized."""
        search_start = max(0, loop_start - 10)

        for i in range(loop_start - 1, search_start - 1, -1):
            line = lines[i].strip()
            if f"{var_name} =" in line and '""' in line:
                return i
        return None

    def _transform_string_initialization(
        self,
        lines: list[str],
        init_line_idx: int,
        var_name: str,
        indent: str,
    ) -> None:
        """Transform string initialization to list initialization."""
        lines[init_line_idx] = (
            f"{indent}{var_name}_parts = []  # Performance: Use list for string building"
        )

    def _replace_concatenations_with_appends(
        self,
        lines: list[str],
        instances: list[dict[str, t.Any]],
        var_name: str,
        indent: str,
    ) -> None:
        """Replace string concatenations with list appends."""
        for instance in instances:
            line_idx = instance["line_idx"]
            expr = instance["expr"]
            lines[line_idx] = f"{indent}{var_name}_parts.append({expr})"

    def _add_join_after_loop(
        self,
        lines: list[str],
        var_name: str,
        indent: str,
        loop_start: int,
    ) -> None:
        """Add join operation after the loop ends."""
        loop_end = self._find_loop_end(lines, loop_start)
        if loop_end is not None:
            join_line = f"{indent}{var_name} = ''.join({var_name}_parts)  # Performance: Join string parts"
            lines.insert(loop_end + 1, join_line)

    def _find_loop_end(self, lines: list[str], loop_start: int) -> int | None:
        """Find the end of the loop (last line with same or greater indentation)."""
        if loop_start >= len(lines):
            return None

        loop_indent = len(lines[loop_start]) - len(lines[loop_start].lstrip())

        for i in range(loop_start + 1, len(lines)):
            line = lines[i]
            if line.strip() == "":  # Skip empty lines
                continue

            current_indent = len(line) - len(line.lstrip())
            if current_indent <= loop_indent:
                return i - 1

        return len(lines) - 1

    def _fix_repeated_operations(
        self,
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Add comments suggesting caching for repeated expensive operations."""
        modified = False

        for instance in issue["instances"]:
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = t.cast(str, lines[line_idx])
                indent_level = len(original_line) - len(original_line.lstrip())
                indent_str = " " * indent_level

                # Add performance comment
                comment = f"{indent_str}# Performance: Consider caching this expensive operation outside the loop"
                lines.insert(line_idx, comment)
                modified = True

        return lines, modified


agent_registry.register(PerformanceAgent)
