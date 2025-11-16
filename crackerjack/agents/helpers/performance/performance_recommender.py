"""Performance optimization recommendations and fixes."""

import operator
import typing as t
from dataclasses import dataclass

from ....services.regex_patterns import SAFE_PATTERNS
from ...base import AgentContext


@dataclass
class OptimizationResult:
    """Result of an optimization attempt."""

    lines: list[str]
    modified: bool
    optimization_description: str | None = None


class PerformanceRecommender:
    """Generates performance recommendations and applies optimizations."""

    def __init__(self, context: AgentContext) -> None:
        """Initialize recommender with agent context.

        Args:
            context: AgentContext for logging
        """
        self.context = context
        self.optimization_stats: dict[str, int] = {
            "nested_loops_optimized": 0,
            "list_ops_optimized": 0,
            "string_concat_optimized": 0,
            "repeated_ops_cached": 0,
            "comprehensions_applied": 0,
        }

    def apply_performance_optimizations(
        self,
        content: str,
        issues: list[dict[str, t.Any]],
    ) -> str:
        """Apply performance optimizations to content.

        Args:
            content: File content
            issues: Performance issues to fix

        Returns:
            Optimized content
        """
        lines = content.split("\n")
        modified = False
        optimizations_applied = []

        for issue in issues:
            result = self._process_single_issue(lines, issue)
            if result.modified:
                lines = result.lines
                modified = True
                if result.optimization_description:
                    optimizations_applied.append(result.optimization_description)

        if optimizations_applied:
            self.context.log(
                f"Applied optimizations: {', '.join(optimizations_applied)}"
            )

        return "\n".join(lines) if modified else content

    def _process_single_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Process single performance issue.

        Args:
            lines: File lines
            issue: Performance issue

        Returns:
            Optimization result
        """
        issue_type = issue["type"]

        if issue_type in (
            "inefficient_list_operations",
            "inefficient_list_operations_enhanced",
        ):
            return self._handle_list_operations_issue(lines, issue)
        elif issue_type in (
            "string_concatenation_in_loop",
            "string_inefficiencies_enhanced",
        ):
            return self._handle_string_operations_issue(lines, issue)
        elif issue_type == "repeated_expensive_operations":
            return self._handle_repeated_operations_issue(lines, issue)
        elif issue_type in ("nested_loops", "nested_loops_enhanced"):
            return self._handle_nested_loops_issue(lines, issue)
        elif issue_type == "list_comprehension_opportunities":
            return self._handle_comprehension_opportunities_issue(lines, issue)
        elif issue_type == "inefficient_builtin_usage":
            return self._handle_builtin_usage_issue(lines, issue)
        return self._create_no_change_result(lines)

    def _handle_list_operations_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle inefficient list operations.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Optimization result
        """
        new_lines, changed = self._fix_list_operations_enhanced(lines, issue)
        description = None

        if changed:
            instance_count = len(issue.get("instances", []))
            self.optimization_stats["list_ops_optimized"] += instance_count
            description = f"List operations: {instance_count}"

        return self._create_optimization_result(new_lines, changed, description)

    def _handle_string_operations_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle inefficient string operations.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Optimization result
        """
        new_lines, changed = self._fix_string_operations_enhanced(lines, issue)
        description = None

        if changed:
            total_string_fixes = (
                len(issue.get("string_concat_patterns", []))
                + len(issue.get("inefficient_joins", []))
                + len(issue.get("repeated_formatting", []))
            )
            self.optimization_stats["string_concat_optimized"] += total_string_fixes
            description = f"String operations: {total_string_fixes}"

        return self._create_optimization_result(new_lines, changed, description)

    def _handle_repeated_operations_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle repeated expensive operations.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Optimization result
        """
        new_lines, changed = self._fix_repeated_operations(lines, issue)

        if changed:
            self.optimization_stats["repeated_ops_cached"] += len(
                issue.get("instances", [])
            )

        return self._create_optimization_result(new_lines, changed)

    def _handle_nested_loops_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle nested loops.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Optimization result
        """
        new_lines, changed = self._add_nested_loop_comments(lines, issue)

        if changed:
            self.optimization_stats["nested_loops_optimized"] += len(
                issue.get("instances", [])
            )

        return self._create_optimization_result(new_lines, changed)

    def _handle_comprehension_opportunities_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle list comprehension opportunities.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Optimization result
        """
        new_lines, changed = self._apply_list_comprehension_optimizations(lines, issue)

        if changed:
            self.optimization_stats["comprehensions_applied"] += len(
                issue.get("instances", [])
            )

        return self._create_optimization_result(new_lines, changed)

    def _handle_builtin_usage_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle inefficient builtin usage.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Optimization result
        """
        new_lines, changed = self._add_builtin_caching_comments(lines, issue)
        return self._create_optimization_result(new_lines, changed)

    @staticmethod
    def _create_optimization_result(
        lines: list[str], modified: bool, description: str | None = None
    ) -> OptimizationResult:
        """Create optimization result.

        Args:
            lines: File lines
            modified: Whether modified
            description: Description

        Returns:
            Optimization result
        """
        return OptimizationResult(
            lines=lines, modified=modified, optimization_description=description
        )

    @staticmethod
    def _create_no_change_result(lines: list[str]) -> OptimizationResult:
        """Create no-change result.

        Args:
            lines: File lines

        Returns:
            Optimization result
        """
        return OptimizationResult(
            lines=lines, modified=False, optimization_description=None
        )

    @staticmethod
    def _fix_list_operations_enhanced(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Fix inefficient list operations.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Tuple of modified lines and bool
        """
        modified = False

        instances = sorted(
            issue["instances"],
            key=operator.itemgetter("line_number"),
            reverse=True,
        )

        for instance in instances:
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]

                optimization_type = instance.get("optimization", "append")

                if optimization_type == "append":
                    list_pattern = SAFE_PATTERNS["list_append_inefficiency_pattern"]
                    if list_pattern.test(original_line):
                        optimized_line = list_pattern.apply(original_line)
                        lines[line_idx] = optimized_line
                        modified = True

                        indent = original_line[
                            : len(original_line) - len(original_line.lstrip())
                        ]
                        performance_gain = instance.get("performance_gain", "2x")
                        comment = (
                            f"{indent}# Performance: {performance_gain}"
                            f" improvement (append vs +=)"
                        )
                        lines.insert(line_idx, comment)

                elif optimization_type == "extend":
                    extend_pattern = SAFE_PATTERNS["list_extend_optimization_pattern"]
                    if extend_pattern.test(original_line):
                        optimized_line = extend_pattern.apply(original_line)
                        lines[line_idx] = optimized_line
                        modified = True

                        indent = original_line[
                            : len(original_line) - len(original_line.lstrip())
                        ]
                        performance_gain = instance.get("performance_gain", "x")
                        impact_factor = int(instance.get("impact_factor", "1"))
                        comment = (
                            f"{indent}# Performance: {performance_gain} "
                            f"improvement, impact factor: {impact_factor}"
                        )
                        lines.insert(line_idx, comment)

        return lines, modified

    def _fix_string_operations_enhanced(
        self,
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Fix inefficient string operations.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Tuple of modified lines and bool
        """
        modified = False

        concat_patterns = issue.get("string_concat_patterns", [])
        if concat_patterns:
            lines, concat_modified = self._fix_string_concatenation(
                lines, {"instances": concat_patterns}
            )
            modified = modified or concat_modified

        inefficient_joins = issue.get("inefficient_joins", [])
        for join_issue in inefficient_joins:
            line_idx = join_issue["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                join_pattern = SAFE_PATTERNS["inefficient_string_join_pattern"]
                if join_pattern.test(original_line):
                    lines[line_idx] = join_pattern.apply(original_line)
                    modified = True

        repeated_formatting = issue.get("repeated_formatting", [])
        for format_issue in repeated_formatting:
            line_idx = format_issue["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                indent = original_line[
                    : len(original_line) - len(original_line.lstrip())
                ]
                comment = f"{indent}# Performance: Consider caching format string outside loop"
                lines.insert(line_idx, comment)
                modified = True

        return lines, modified

    @staticmethod
    def _add_nested_loop_comments(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Add comments for nested loops.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Tuple of modified lines and bool
        """
        modified = False

        instances = issue.get("instances", [])
        for instance in sorted(
            instances, key=operator.itemgetter("line_number"), reverse=True
        ):
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                indent = original_line[
                    : len(original_line) - len(original_line.lstrip())
                ]

                complexity = instance.get("complexity", "O(n²)")
                priority = instance.get("priority", "medium")

                comment_lines = [
                    f"{indent}# Performance: {complexity} nested loop detected - {priority} priority",
                ]

                if priority in ("high", "critical"):
                    if priority == "critical":
                        comment_lines.append(
                            f"{indent}# CRITICAL: Consider algorithmic redesign or"
                            f" data structure changes"
                        )
                    else:
                        comment_lines.append(
                            f"{indent}# Suggestion: Consider memoization, caching, "
                            f" or hash tables"
                        )

                for i, comment in enumerate(comment_lines):
                    lines.insert(line_idx + i, comment)

                modified = True

        return lines, modified

    @staticmethod
    def _apply_list_comprehension_optimizations(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Apply list comprehension optimizations.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Tuple of modified lines and bool
        """
        modified = False

        instances = issue.get("instances", [])
        for instance in sorted(
            instances, key=operator.itemgetter("line_number"), reverse=True
        ):
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                indent = original_line[
                    : len(original_line) - len(original_line.lstrip())
                ]

                comment = (
                    f"{indent}# Performance: Consider list[t.Any] comprehension for "
                    f"20-30% improvement"
                )
                lines.insert(line_idx, comment)
                modified = True

        return lines, modified

    @staticmethod
    def _add_builtin_caching_comments(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Add caching comments for builtins.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Tuple of modified lines and bool
        """
        modified = False

        instances = issue.get("instances", [])
        for instance in sorted(
            instances, key=operator.itemgetter("line_number"), reverse=True
        ):
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                indent = original_line[
                    : len(original_line) - len(original_line.lstrip())
                ]

                func_name = instance.get("function", "builtin")
                performance_gain = instance.get("performance_gain", "2-10x")

                comment = (
                    f"{indent}# Performance: Cache {func_name}() result outside"
                    f" loop for {performance_gain} improvement"
                )
                lines.insert(line_idx, comment)
                modified = True

        return lines, modified

    @staticmethod
    def _fix_string_concatenation(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Fix string concatenation issues.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Tuple of modified lines and bool
        """
        modified = False
        return lines, modified

    @staticmethod
    def _fix_repeated_operations(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Fix repeated operations.

        Args:
            lines: File lines
            issue: Issue dict

        Returns:
            Tuple of modified lines and bool
        """
        modified = False

        for instance in issue["instances"]:
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                indent_level = len(original_line) - len(original_line.lstrip())
                indent_str = " " * indent_level

                comment = (
                    f"{indent_str}# Performance: Consider caching this expensive"
                    f" operation outside the loop"
                )
                lines.insert(line_idx, comment)
                modified = True

        return lines, modified

    def generate_optimization_summary(self) -> str:
        """Generate summary of optimizations applied.

        Returns:
            Summary string
        """
        total_optimizations = sum(self.optimization_stats.values())
        if total_optimizations == 0:
            return "No optimizations applied in this session"

        summary_parts = [
            f"{opt_type}: {count}"
            for opt_type, count in self.optimization_stats.items()
            if count > 0
        ]

        return (
            f"Optimization Summary - {', '.join(summary_parts)} "
            f"(Total: {total_optimizations})"
        )
