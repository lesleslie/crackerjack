"""Data Processing pattern for reducing cognitive complexity.

The Data Processing pattern identifies functions with multiple sequential
loops containing nested conditions and data aggregation logic that can
be refactored into smaller helper methods.

Example transformation:
    # Before (complexity 11)
    def generate_report(self) -> str:
        lines = ["header"]
        for item in items:
            if item.active:
                lines.append(f"Item: {item.name}")
                for sub in item.subitems:
                    if sub.valid:
                        lines.append(f"  Sub: {sub.name}")

        totals = {}
        for item in items:
            if item.value:
                totals[item.category] = totals.get(item.category, 0) + item.value

        return "\\n".join(lines)

    # After (complexity 3 per function)
    def generate_report(self) -> str:
        lines = self._build_item_lines(items)
        totals = self._calculate_totals(items)
        return "\\n".join(lines) + self._format_totals(totals)

    def _build_item_lines(self, items) -> list[str]:
        ...

    def _calculate_totals(self, items) -> dict:
        ...
"""

from __future__ import annotations

import ast
from typing import Any

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)


class DataProcessingPattern(BasePattern):
    """Pattern that matches data processing functions with multiple loops.

    Matches when:
    - Function has 2+ for loops with nested conditions
    - Loops contain data aggregation patterns (sum, count, collect)
    - Report generation patterns with sequential data transformations
    - Each loop can be extracted into a helper method

    Does NOT match:
    - Functions with fewer than 2 loops (use ExtractMethodPattern)
    - Loops with side effects (file I/O, network calls)
    - Simple iteration without nested conditions
    """

    # Minimum loops to consider for data processing pattern
    MIN_LOOPS: int = 2

    # Minimum nested conditions to consider
    MIN_NESTED_CONDITIONS: int = 1

    # Common aggregation function names
    AGGREGATION_FUNCS: tuple[str, ...] = (
        "sum",
        "len",
        "count",
        "min",
        "max",
        "avg",
        "mean",
        "append",
        "extend",
        "update",
        "get",
        "setdefault",
    )

    @property
    def name(self) -> str:
        return "data_processing"

    @property
    def priority(self) -> PatternPriority:
        return PatternPriority.DECOMPOSE_CONDITIONAL

    @property
    def supports_async(self) -> bool:
        return True

    def match(self, node: ast.AST, source_lines: list[str]) -> PatternMatch | None:
        """Check if this node is a data processing function.

        Looks for:
        1. Functions with multiple for loops
        2. Loops with nested if conditions
        3. Data aggregation patterns

        Args:
            node: AST node to check (looking for FunctionDef/AsyncFunctionDef)
            source_lines: Original source code lines for context

        Returns:
            PatternMatch if data processing candidate found, None otherwise
        """
        # Only match function definitions
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return None

        # Analyze the function body
        analysis = self._analyze_data_processing(node)

        if not self._is_data_processing_candidate(analysis):
            return None

        # Get the best extraction candidate
        best_candidate = self._select_best_candidate(analysis["loop_candidates"])

        if not best_candidate:
            return None

        return PatternMatch(
            pattern_name=self.name,
            priority=self.priority,
            line_start=best_candidate["line_start"],
            line_end=best_candidate["line_end"],
            node=node,
            match_info={
                "type": "data_processing",
                "loops": analysis["loops"],
                "loop_candidates": analysis["loop_candidates"],
                "nested_conditions": analysis["nested_conditions"],
                "aggregations": analysis["aggregations"],
                "suggested_refactor": best_candidate["suggested_name"],
            },
            estimated_reduction=self._estimate_reduction(analysis),
            context={
                "function_name": node.name,
                "function_length": len(node.body),
                "loop_count": len(analysis["loops"]),
                "total_nested_conditions": analysis["nested_conditions"],
                "has_aggregation": len(analysis["aggregations"]) > 0,
                "is_report_generation": analysis["is_report_generation"],
            },
        )

    def _analyze_data_processing(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> dict[str, Any]:
        """Analyze a function for data processing patterns.

        Args:
            func_node: Function AST node to analyze

        Returns:
            Dictionary with analysis results
        """
        loops: list[ast.For] = []
        loop_candidates: list[dict[str, Any]] = []
        nested_conditions = 0
        aggregations: list[str] = []
        is_report_generation = False

        for stmt in func_node.body:
            # Find for loops
            if isinstance(stmt, ast.For):
                loops.append(stmt)

                # Analyze this loop
                loop_analysis = self._analyze_loop(stmt)
                nested_conditions += loop_analysis["nested_conditions"]
                aggregations.extend(loop_analysis["aggregations"])

                if loop_analysis["is_report_generation"]:
                    is_report_generation = True

                # Check if this loop can be extracted
                if not self._has_loop_side_effects(stmt):
                    candidate = self._create_loop_candidate(stmt, loop_analysis)
                    if candidate:
                        loop_candidates.append(candidate)

            # Check for nested for loops in other structures
            for child in ast.walk(stmt):
                if isinstance(child, ast.For) and child not in loops:
                    loops.append(child)

        return {
            "loops": loops,
            "loop_candidates": loop_candidates,
            "nested_conditions": nested_conditions,
            "aggregations": list(set(aggregations)),
            "is_report_generation": is_report_generation,
        }

    def _analyze_loop(self, loop_node: ast.For) -> dict[str, Any]:
        """Analyze a single for loop for complexity patterns.

        Args:
            loop_node: For loop AST node

        Returns:
            Dictionary with loop analysis
        """
        nested_conditions = 0
        aggregations: list[str] = []
        is_report_generation = False

        for child in ast.walk(loop_node):
            # Count nested if statements
            if isinstance(child, ast.If) and child is not loop_node:
                nested_conditions += 1

            # Check for aggregation calls
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    if child.func.id in self.AGGREGATION_FUNCS:
                        aggregations.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    if child.func.attr in self.AGGREGATION_FUNCS:
                        aggregations.append(child.func.attr)

            # Check for report generation patterns (list/dict building)
            if isinstance(child, ast.Attribute):
                if child.attr in ("append", "extend", "update"):
                    is_report_generation = True

        return {
            "nested_conditions": nested_conditions,
            "aggregations": aggregations,
            "is_report_generation": is_report_generation,
            "complexity": 1 + nested_conditions,  # Base + nesting
        }

    def _create_loop_candidate(
        self, loop_node: ast.For, analysis: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Create an extraction candidate for a loop.

        Args:
            loop_node: For loop AST node
            analysis: Loop analysis results

        Returns:
            Candidate dictionary or None if not extractable
        """
        # Determine the loop's action type
        action = self._identify_loop_action(loop_node, analysis)

        # Generate a suggested helper method name
        suggested_name = self._suggest_helper_name(loop_node, action)

        return {
            "loop": loop_node,
            "line_start": loop_node.lineno,
            "line_end": loop_node.end_lineno or loop_node.lineno,
            "nested_conditions": analysis["nested_conditions"],
            "aggregations": analysis["aggregations"],
            "action": action,
            "suggested_name": suggested_name,
            "complexity": analysis["complexity"],
        }

    def _has_loop_side_effects(self, loop_node: ast.For) -> bool:
        """Check if a loop has side effects that prevent extraction.

        Args:
            loop_node: For loop AST node

        Returns:
            True if loop has side effects
        """
        for child in ast.walk(loop_node):
            # File operations
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    if child.func.attr in ("write", "open", "close"):
                        return True
                if isinstance(child.func, ast.Name):
                    if child.func.id in ("open", "input", "print"):
                        return True

            # Async operations
            if isinstance(child, ast.Await):
                return True

            # Return statements (can't extract return logic)
            if isinstance(child, ast.Return) and child is not loop_node:
                return True

        return False

    def _identify_loop_action(
        self, loop_node: ast.For, analysis: dict[str, Any]
    ) -> str:
        """Identify the primary action of a loop.

        Args:
            loop_node: For loop AST node
            analysis: Loop analysis results

        Returns:
            Action type string (filter, transform, aggregate, collect, iterate)
        """
        aggregations = analysis["aggregations"]

        # Check for filtering (if with continue)
        for child in ast.walk(loop_node):
            if isinstance(child, ast.Continue):
                return "filter"

        # Check for aggregation
        if any(agg in aggregations for agg in ("sum", "count", "len", "min", "max")):
            return "aggregate"

        # Check for collection building
        if "append" in aggregations or "extend" in aggregations:
            return "collect"

        # Check for dictionary building
        if "update" in aggregations or "setdefault" in aggregations:
            return "build_dict"

        # Check for transformation (creating new values)
        if analysis["nested_conditions"] > 0:
            return "transform"

        return "iterate"

    def _suggest_helper_name(self, loop_node: ast.For, action: str) -> str:
        """Suggest a name for a helper method.

        Args:
            loop_node: For loop AST node
            action: Identified action type

        Returns:
            Suggested method name
        """
        # Try to get the iterator variable name
        iter_name = ""
        if isinstance(loop_node.target, ast.Name):
            iter_name = loop_node.target.id
        elif isinstance(loop_node.target, ast.Tuple):
            names = [
                elt.id
                for elt in loop_node.target.elts
                if isinstance(elt, ast.Name)
            ]
            if names:
                iter_name = names[0]

        # Build name based on action
        action_prefixes = {
            "filter": "_filter",
            "aggregate": "_aggregate",
            "collect": "_collect",
            "build_dict": "_build",
            "transform": "_transform",
            "iterate": "_process",
        }

        prefix = action_prefixes.get(action, "_process")

        if iter_name:
            return f"{prefix}_{iter_name}"

        return f"{prefix}_items"

    def _is_data_processing_candidate(self, analysis: dict[str, Any]) -> bool:
        """Check if the analysis indicates a data processing pattern.

        Args:
            analysis: Function analysis results

        Returns:
            True if this is a data processing candidate
        """
        loops = analysis["loops"]
        candidates = analysis["loop_candidates"]
        nested = analysis["nested_conditions"]

        # Must have at least 2 loops OR 1 complex loop
        if len(loops) < self.MIN_LOOPS and nested < self.MIN_NESTED_CONDITIONS:
            return False

        # Must have at least 1 extractable candidate
        if not candidates:
            return False

        # Must have some complexity to reduce
        if nested < 1 and not analysis["aggregations"]:
            return False

        return True

    def _select_best_candidate(
        self, candidates: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Select the best extraction candidate.

        Args:
            candidates: List of extraction candidates

        Returns:
            Best candidate or None
        """
        if not candidates:
            return None

        # Sort by complexity (highest first for maximum impact)
        sorted_candidates = sorted(
            candidates,
            key=lambda c: c["complexity"],
            reverse=True,
        )

        return sorted_candidates[0]

    def _estimate_reduction(self, analysis: dict[str, Any]) -> int:
        """Estimate complexity reduction from refactoring.

        Args:
            analysis: Function analysis results

        Returns:
            Estimated complexity reduction
        """
        reduction = 0

        # Each extractable loop reduces complexity
        for candidate in analysis["loop_candidates"]:
            reduction += candidate["complexity"]

        # Bonus for aggregation patterns (clear separation of concerns)
        if analysis["aggregations"]:
            reduction += len(analysis["aggregations"])

        # Bonus for report generation (very decomposable)
        if analysis["is_report_generation"]:
            reduction += 2

        return max(1, reduction)

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        """Return the estimated complexity reduction for this match.

        Args:
            match: The pattern match

        Returns:
            Estimated complexity reduction
        """
        return match.estimated_reduction
