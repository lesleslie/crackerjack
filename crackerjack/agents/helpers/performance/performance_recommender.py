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

    def _log(self, message: str) -> None:
        log = getattr(self.context, "log", None)
        if callable(log):
            log(message)

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
            self._log(f"Applied optimizations: {', '.join(optimizations_applied)}")

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
                    modified |= self._handle_append_optimization(
                        lines, instance, line_idx, original_line
                    )

                elif optimization_type == "extend":
                    modified |= self._handle_extend_optimization(
                        lines, instance, line_idx, original_line
                    )

        return lines, modified

    def _handle_append_optimization(
        self,
        lines: list[str],
        instance: dict[str, t.Any],
        line_idx: int,
        original_line: str,
    ) -> bool:
        """Handle append optimization."""
        list_pattern = SAFE_PATTERNS["list_append_inefficiency_pattern"]
        target_idx = line_idx
        current_line = original_line

        if not list_pattern.test(current_line):
            for candidate_idx in range(
                max(0, line_idx - 2), min(len(lines), line_idx + 3)
            ):
                if list_pattern.test(lines[candidate_idx]):
                    target_idx = candidate_idx
                    current_line = lines[candidate_idx]
                    break

        if list_pattern.test(current_line):
            optimized_line = list_pattern.apply(current_line)
            lines[target_idx] = optimized_line

            indent = current_line[: len(current_line) - len(current_line.lstrip())]
            performance_gain = instance.get("performance_gain", "2x")
            comment = (
                f"{indent}# Performance: {performance_gain} improvement (append vs +=)"
            )
            lines.insert(target_idx, comment)
            return True

        return False

    def _handle_extend_optimization(
        self,
        lines: list[str],
        instance: dict[str, t.Any],
        line_idx: int,
        original_line: str,
    ) -> bool:
        """Handle extend optimization."""
        extend_pattern = SAFE_PATTERNS["list_extend_optimization_pattern"]
        target_idx = line_idx
        current_line = original_line

        if not extend_pattern.test(current_line):
            for candidate_idx in range(
                max(0, line_idx - 2), min(len(lines), line_idx + 3)
            ):
                if extend_pattern.test(lines[candidate_idx]):
                    target_idx = candidate_idx
                    current_line = lines[candidate_idx]
                    break

        if extend_pattern.test(current_line):
            optimized_line = extend_pattern.apply(current_line)
            lines[target_idx] = optimized_line

            indent = current_line[: len(current_line) - len(current_line.lstrip())]
            performance_gain = instance.get("performance_gain", "x")
            impact_factor = int(instance.get("impact_factor", "1"))
            comment = (
                f"{indent}# Performance: {performance_gain} "
                f"improvement, impact factor: {impact_factor}"
            )
            lines.insert(target_idx, comment)
            return True

        return False

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

                complexity = PerformanceRecommender._normalize_complexity_notation(
                    instance.get("complexity", "O(n^2)")
                )
                priority = instance.get("priority", "medium")
                priority_label = (
                    priority.upper() if isinstance(priority, str) else str(priority)
                )

                comment_lines = [
                    f"{indent}# Performance: {complexity} nested loop detected - {priority_label} priority",
                ]

                comment_lines.extend(
                    PerformanceRecommender._get_priority_specific_comments(
                        indent, priority
                    )
                )

                for i, comment in enumerate(comment_lines):
                    lines.insert(line_idx + i, comment)

                modified = True

        return lines, modified

    @staticmethod
    def _normalize_complexity_notation(complexity: str) -> str:
        """Normalize complexity notation."""
        if isinstance(complexity, str):
            return complexity.replace("²", "^2").replace("³", "^3").replace("⁴", "^4")
        return complexity

    @staticmethod
    def _get_priority_specific_comments(indent: str, priority: str) -> list[str]:
        """Get priority-specific comments."""
        comment_lines = []

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

        return comment_lines

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
        instances = issue.get("instances", [])

        # Early return if no instances to process
        if not instances:
            return lines, modified

        for instance in sorted(
            instances, key=operator.itemgetter("line_number"), reverse=True
        ):
            modified |= PerformanceRecommender._process_single_concatenation_instance(
                lines, instance
            )

        return lines, modified

    @staticmethod
    def _process_single_concatenation_instance(
        lines: list[str], instance: dict[str, t.Any]
    ) -> bool:
        """Process a single concatenation instance to reduce function complexity."""
        original_idx = instance.get("line_number", 1) - 1
        target_content = instance.get("content", "").strip()
        candidate_indices: list[int] = PerformanceRecommender._find_candidate_indices(
            lines, original_idx, target_content
        )

        if not candidate_indices:
            return False

        line_idx = min(
            candidate_indices,
            key=lambda idx: abs(idx - original_idx),
        )
        original_line = lines[line_idx]

        if "+=" not in original_line:
            return False

        return PerformanceRecommender._fix_line_at_index(lines, line_idx, original_line)

    @staticmethod
    def _find_candidate_indices(
        lines: list[str], original_idx: int, target_content: str
    ) -> list[int]:
        """Find candidate indices for string concatenation fix."""
        candidate_indices: list[int] = []

        if 0 <= original_idx < len(lines):
            original_line = lines[original_idx]
            if "+=" in original_line and (
                not target_content or original_line.strip() == target_content
            ):
                candidate_indices.append(original_idx)

        if not candidate_indices and target_content:
            for idx, line in enumerate(lines):
                if line.strip() == target_content:
                    candidate_indices.append(idx)

        if not candidate_indices:
            for idx, line in enumerate(lines):
                stripped = line.strip()
                if (
                    "+=" in stripped
                    and any(quote in stripped for quote in ('"', "'"))
                    and ".append(" not in stripped
                ):
                    candidate_indices.append(idx)

        return candidate_indices

    @staticmethod
    def _fix_line_at_index(lines: list[str], line_idx: int, original_line: str) -> bool:
        """Fix a single line at the given index."""
        modified = False
        line_body, sep, comment = original_line.partition("#")
        left, _, right = line_body.partition("+=")
        if not left.strip() or not right.strip():
            return False

        target = left.strip()
        expr = right.strip()

        current_indent = len(original_line) - len(original_line.lstrip())
        body_indent_str = " " * current_indent

        loop_start_idx = PerformanceRecommender._find_loop_start_idx(
            lines, line_idx, current_indent
        )

        parent_indent, parent_indent_str = (
            PerformanceRecommender._get_parent_indent_info(
                lines, loop_start_idx, current_indent
            )
        )

        parts_name = f"{target}_parts"
        modified |= PerformanceRecommender._ensure_parts_initialized(
            lines, loop_start_idx, line_idx, parts_name, parent_indent_str
        )

        new_line = f"{body_indent_str}{parts_name}.append({expr})"
        if comment:
            new_line = f"{new_line}  #{comment.strip()}"
        lines[line_idx] = new_line
        modified = True

        modified |= PerformanceRecommender._add_join_statement(
            lines, loop_start_idx, line_idx, target, parts_name, parent_indent_str
        )

        return modified

    @staticmethod
    def _find_loop_start_idx(
        lines: list[str], line_idx: int, current_indent: int
    ) -> int | None:
        """Find the start of the loop containing the line."""
        for i in range(line_idx - 1, -1, -1):
            candidate = lines[i]
            stripped = candidate.lstrip()
            if not stripped:
                continue
            indent = len(candidate) - len(candidate.lstrip())
            if indent < current_indent and stripped.startswith(("for ", "while ")):
                return i
        return None

    @staticmethod
    def _get_parent_indent_info(
        lines: list[str], loop_start_idx: int | None, current_indent: int
    ) -> tuple[int, str]:
        """Get parent indentation information."""
        parent_indent = (
            len(lines[loop_start_idx]) - len(lines[loop_start_idx].lstrip())
            if loop_start_idx is not None
            else current_indent
        )
        parent_indent_str = " " * parent_indent
        return parent_indent, parent_indent_str

    @staticmethod
    def _ensure_parts_initialized(
        lines: list[str],
        loop_start_idx: int | None,
        line_idx: int,
        parts_name: str,
        parent_indent_str: str,
    ) -> bool:
        """Ensure parts list is initialized."""
        has_parts_init = any(
            parts_name in line and line.strip().endswith("= []") for line in lines
        )
        if not has_parts_init:
            insert_at = loop_start_idx if loop_start_idx is not None else line_idx
            lines.insert(insert_at, f"{parent_indent_str}{parts_name} = []")
            lines.insert(
                insert_at,
                f"{parent_indent_str}# Performance: build strings with list join",
            )
            if loop_start_idx is not None and insert_at <= line_idx:
                line_idx += 2
            return True
        return False

    @staticmethod
    def _add_join_statement(
        lines: list[str],
        loop_start_idx: int | None,
        line_idx: int,
        target: str,
        parts_name: str,
        parent_indent_str: str,
    ) -> bool:
        """Add the join statement after processing."""
        modified = False
        join_line = f"{parent_indent_str}{target} = ''.join({parts_name})"

        if loop_start_idx is not None:
            current_indent = len(lines[line_idx]) - len(lines[line_idx].lstrip())
            loop_body_indent = current_indent
            insert_at = None
            for j in range(line_idx + 1, len(lines)):
                candidate = lines[j]
                stripped = candidate.lstrip()
                if not stripped:
                    continue
                indent = len(candidate) - len(candidate.lstrip())
                if indent < loop_body_indent:
                    insert_at = j
                    break
            if insert_at is None:
                insert_at = len(lines)
            if join_line not in lines:
                lines.insert(insert_at, join_line)
                modified = True
        else:
            if join_line not in lines:
                lines.insert(line_idx + 1, join_line)
                modified = True

        return modified

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
