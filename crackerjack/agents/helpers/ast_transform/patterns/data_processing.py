from __future__ import annotations

import ast
from typing import Any

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)


class DataProcessingPattern(BasePattern):
    MIN_LOOPS: int = 2

    MIN_NESTED_CONDITIONS: int = 1

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

        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return None

        analysis = self._analyze_data_processing(node)

        if not self._is_data_processing_candidate(analysis):
            return None

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
                "has_aggregation": analysis["aggregations"],
                "is_report_generation": analysis["is_report_generation"],
            },
        )

    def _analyze_data_processing(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> dict[str, Any]:
        loops: list[ast.For] = []
        loop_candidates: list[dict[str, Any]] = []
        nested_conditions = 0
        aggregations: list[str] = []
        is_report_generation = False

        for stmt in func_node.body:
            if isinstance(stmt, ast.For):
                loops.append(stmt)

                loop_analysis = self._analyze_loop(stmt)
                nested_conditions += loop_analysis["nested_conditions"]
                aggregations.extend(loop_analysis["aggregations"])

                if loop_analysis["is_report_generation"]:
                    is_report_generation = True

                if not self._has_loop_side_effects(stmt):
                    candidate = self._create_loop_candidate(stmt, loop_analysis)
                    if candidate:
                        loop_candidates.append(candidate)

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
        nested_conditions = 0
        aggregations: list[str] = []
        is_report_generation = False

        for child in ast.walk(loop_node):
            if isinstance(child, ast.If) and child is not loop_node:
                nested_conditions += 1

            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    if child.func.id in self.AGGREGATION_FUNCS:
                        aggregations.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    if child.func.attr in self.AGGREGATION_FUNCS:
                        aggregations.append(child.func.attr)

            if isinstance(child, ast.Attribute):
                if child.attr in ("append", "extend", "update"):
                    is_report_generation = True

        return {
            "nested_conditions": nested_conditions,
            "aggregations": aggregations,
            "is_report_generation": is_report_generation,
            "complexity": 1 + nested_conditions,
        }

    def _create_loop_candidate(
        self, loop_node: ast.For, analysis: dict[str, Any]
    ) -> dict[str, Any] | None:

        action = self._identify_loop_action(loop_node, analysis)

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
        for child in ast.walk(loop_node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    if child.func.attr in ("write", "open", "close"):
                        return True
                if isinstance(child.func, ast.Name):
                    if child.func.id in ("open", "input", "print"):
                        return True

            if isinstance(child, ast.Await):
                return True

            if isinstance(child, ast.Return) and child is not loop_node:
                return True

        return False

    def _identify_loop_action(
        self, loop_node: ast.For, analysis: dict[str, Any]
    ) -> str:
        aggregations = analysis["aggregations"]

        for child in ast.walk(loop_node):
            if isinstance(child, ast.Continue):
                return "filter"

        if any(agg in aggregations for agg in ("sum", "count", "len", "min", "max")):
            return "aggregate"

        if "append" in aggregations or "extend" in aggregations:
            return "collect"

        if "update" in aggregations or "setdefault" in aggregations:
            return "build_dict"

        if analysis["nested_conditions"] > 0:
            return "transform"

        return "iterate"

    def _suggest_helper_name(self, loop_node: ast.For, action: str) -> str:

        iter_name = ""
        if isinstance(loop_node.target, ast.Name):
            iter_name = loop_node.target.id
        elif isinstance(loop_node.target, ast.Tuple):
            names = [
                elt.id for elt in loop_node.target.elts if isinstance(elt, ast.Name)
            ]
            if names:
                iter_name = names[0]

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
        loops = analysis["loops"]
        candidates = analysis["loop_candidates"]
        nested = analysis["nested_conditions"]

        if len(loops) < self.MIN_LOOPS and nested < self.MIN_NESTED_CONDITIONS:
            return False

        if not candidates:
            return False

        if nested < 1 and not analysis["aggregations"]:
            return False

        return True

    def _select_best_candidate(
        self, candidates: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        if not candidates:
            return None

        sorted_candidates = sorted(
            candidates,
            key=operator.itemgetter("complexity"),
            reverse=True,
        )

        return sorted_candidates[0]

    def _estimate_reduction(self, analysis: dict[str, Any]) -> int:
        reduction = 0

        for candidate in analysis["loop_candidates"]:
            reduction += candidate["complexity"]

        if analysis["aggregations"]:
            reduction += len(analysis["aggregations"])

        if analysis["is_report_generation"]:
            reduction += 2

        return max(1, reduction)

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        return match.estimated_reduction
