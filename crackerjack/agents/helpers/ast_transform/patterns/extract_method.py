from __future__ import annotations

import ast
import operator
import re
from typing import Any

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)

ExtractionCandidate = dict[str, Any]


class ExtractMethodPattern(BasePattern):
    MIN_BLOCK_SIZE: int = 3

    MIN_FUNCTION_SIZE: int = 10

    SECTION_PATTERNS: tuple[str, ...] = (
        r"^#\s*[A-Z][A-Za-z\s]+$",
        r"^#\s*---+$",
        r"^#\s*===+$",
        r"^#\s*(validate|check|verify|ensure|setup|initialize)",
        r"^#\s*(process|transform|convert|parse|format)",
        r"^#\s*(calculate|compute|aggregate|sum)",
        r"^#\s*(build|create|construct|generate)",
        r"^#\s*(handle|manage|execute|run|perform)",
        r"^#\s*(save|store|persist|write|load|fetch|get)",
        r"^#\s*(cleanup|teardown|finalize|complete)",
    )

    METHOD_NAME_VERBS: tuple[str, ...] = (
        "validate",
        "check",
        "verify",
        "ensure",
        "setup",
        "initialize",
        "process",
        "transform",
        "convert",
        "parse",
        "format",
        "calculate",
        "compute",
        "aggregate",
        "build",
        "create",
        "construct",
        "generate",
        "handle",
        "manage",
        "execute",
        "run",
        "perform",
        "save",
        "store",
        "persist",
        "write",
        "load",
        "fetch",
        "get",
        "cleanup",
        "finalize",
        "complete",
    )

    @property
    def name(self) -> str:
        return "extract_method"

    @property
    def priority(self) -> PatternPriority:
        return PatternPriority.EXTRACT_METHOD

    @property
    def supports_async(self) -> bool:
        return True

    def match(self, node: ast.AST, source_lines: list[str]) -> PatternMatch | None:

        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return None

        if len(node.body) < self.MIN_FUNCTION_SIZE:
            return None

        candidates = self._find_extraction_candidates(node, source_lines)

        if not candidates:
            return None

        best_candidate = max(candidates, key=operator.itemgetter("estimated_reduction"))

        return PatternMatch(
            pattern_name=self.name,
            priority=self.priority,
            line_start=best_candidate["extraction_start"],
            line_end=best_candidate["extraction_end"],
            node=node,
            match_info={
                "type": "extract_method",
                "extraction_start": best_candidate["extraction_start"],
                "extraction_end": best_candidate["extraction_end"],
                "inputs": best_candidate["inputs"],
                "outputs": best_candidate["outputs"],
                "suggested_name": best_candidate["suggested_name"],
                "block_statements": best_candidate["block_statements"],
            },
            estimated_reduction=best_candidate["estimated_reduction"],
            context={
                "function_name": node.name,
                "function_length": len(node.body),
                "candidate_count": len(candidates),
            },
        )

    def _find_extraction_candidates(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: list[str],
    ) -> list[ExtractionCandidate]:
        candidates: list[ExtractionCandidate] = []

        comment_sections = self._find_comment_sections(func_node, source_lines)
        candidates.extend(comment_sections)

        variable_sections = self._find_variable_cohesive_blocks(func_node)
        candidates.extend(variable_sections)

        repeated_patterns = self._find_repeated_patterns(func_node)
        candidates.extend(repeated_patterns)

        return candidates

    def _find_comment_sections(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: list[str],
    ) -> list[ExtractionCandidate]:
        candidates: list[ExtractionCandidate] = []

        section_starts: list[tuple[int, str]] = []

        for i, stmt in enumerate(func_node.body):
            stmt_line = stmt.lineno

            if stmt_line > 1:
                prev_line = source_lines[stmt_line - 2].strip()
                if self._is_section_comment(prev_line):
                    section_name = self._extract_section_name(prev_line)
                    section_starts.append((i, section_name))

        if section_starts:
            for idx, (start_idx, section_name) in enumerate(section_starts):
                if idx + 1 < len(section_starts):
                    end_idx = section_starts[idx + 1][0] - 1
                else:
                    end_idx = len(func_node.body) - 1

                block_size = end_idx - start_idx + 1
                if block_size < self.MIN_BLOCK_SIZE:
                    continue

                block = func_node.body[start_idx : end_idx + 1]
                inputs, outputs = self._analyze_block_io(block)

                suggested_name = self._suggest_method_name(
                    section_name, inputs, outputs
                )

                candidates.append(
                    {
                        "extraction_start": block[0].lineno,
                        "extraction_end": block[-1].end_lineno or block[-1].lineno,
                        "inputs": inputs,
                        "outputs": outputs,
                        "suggested_name": suggested_name,
                        "block_statements": block,
                        "estimated_reduction": self._estimate_block_reduction(block),
                    }
                )

        return candidates

    def _find_variable_cohesive_blocks(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[ExtractionCandidate]:
        candidates: list[ExtractionCandidate] = []

        param_names: set[str] = set()
        for arg in func_node.args.args:
            param_names.add(arg.arg)
        if func_node.args.kwarg:
            param_names.add(func_node.args.kwarg.arg)
        if func_node.args.vararg:
            param_names.add(func_node.args.vararg.arg)

        defined_vars: set[str] = param_names.copy()
        var_def_positions: dict[str, int] = {}

        for i, stmt in enumerate(func_node.body):
            new_defs = self._get_defined_variables(stmt)
            for var in new_defs:
                var_def_positions[var] = i
            defined_vars.update(new_defs)

        for start_idx in range(len(func_node.body) - self.MIN_BLOCK_SIZE + 1):
            for end_idx in range(
                start_idx + self.MIN_BLOCK_SIZE - 1, len(func_node.body)
            ):
                block = func_node.body[start_idx : end_idx + 1]

                if self._has_complex_control_flow(block):
                    continue

                inputs, outputs = self._analyze_block_io(block)

                if inputs and outputs and len(inputs) <= 5:
                    suggested_name = self._suggest_method_name_from_io(inputs, outputs)

                    candidates.append(
                        {
                            "extraction_start": block[0].lineno,
                            "extraction_end": block[-1].end_lineno or block[-1].lineno,
                            "inputs": list(inputs),
                            "outputs": list(outputs),
                            "suggested_name": suggested_name,
                            "block_statements": block,
                            "estimated_reduction": self._estimate_block_reduction(
                                block
                            ),
                        }
                    )

        return self._deduplicate_candidates(candidates)

    def _find_repeated_patterns(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[ExtractionCandidate]:
        candidates: list[ExtractionCandidate] = []

        stmt_groups: dict[str, list[tuple[int, ast.stmt]]] = {}

        for i, stmt in enumerate(func_node.body):
            signature = self._get_statement_signature(stmt)
            if signature not in stmt_groups:
                stmt_groups[signature] = []
            stmt_groups[signature].append((i, stmt))

        for signature, group in stmt_groups.items():
            if len(group) < 2:
                continue

            if self._are_similar_statements([s for _, s in group]):
                _first_idx, first_stmt = group[0]

                block = [first_stmt]
                inputs, outputs = self._analyze_block_io(block)

                suggested_name = self._suggest_method_name_from_pattern(signature)

                candidates.append(
                    {
                        "extraction_start": first_stmt.lineno,
                        "extraction_end": first_stmt.end_lineno or first_stmt.lineno,
                        "inputs": list(inputs),
                        "outputs": list(outputs),
                        "suggested_name": suggested_name,
                        "block_statements": block,
                        "estimated_reduction": len(group) - 1,
                        "repeat_count": len(group),
                    }
                )

        return candidates

    def _is_section_comment(self, line: str) -> bool:
        if not line.startswith("#"):
            return False

        for pattern in self.SECTION_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True

        return False

    def _extract_section_name(self, comment: str) -> str:

        cleaned = comment.lstrip("#").strip()

        cleaned = re.sub(r"^[-=]+\s*", "", cleaned)
        cleaned = re.sub(r"\s*[-=]+$", "", cleaned)

        cleaned = cleaned.lower().replace(" ", "_")

        cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)

        return cleaned or "helper"

    def _analyze_block_io(
        self,
        block: list[ast.stmt],
    ) -> tuple[set[str], set[str]]:

        used_vars: set[str] = set()
        defined_vars: set[str] = set()

        for stmt in block:
            used_vars.update(self._get_used_variables(stmt))

            defined_vars.update(self._get_defined_variables(stmt))

        inputs = used_vars - defined_vars

        outputs = defined_vars

        return inputs, outputs

    def _get_used_variables(self, node: ast.AST) -> set[str]:
        used: set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(
                child.ctx,
                ast.Load,
            ):
                used.add(child.id)

            elif isinstance(child, ast.arg):
                used.add(child.arg)

        return used

    def _get_defined_variables(self, node: ast.AST) -> set[str]:
        defined: set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(
                child.ctx,
                ast.Store,
            ):
                defined.add(child.id)

            elif isinstance(child, ast.Tuple | ast.List):
                for elt in child.elts:
                    if isinstance(elt, ast.Name) and isinstance(
                        elt.ctx,
                        ast.Store,
                    ):
                        defined.add(elt.id)

            elif isinstance(child, ast.For):
                defined.update(self._get_target_names(child.target))

            elif isinstance(child, ast.comprehension):
                defined.update(self._get_target_names(child.target))

        return defined

    def _get_target_names(self, target: ast.expr) -> set[str]:
        names: set[str] = set()

        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Tuple | ast.List):
            for elt in target.elts:
                names.update(self._get_target_names(elt))

        return names

    def _has_complex_control_flow(self, block: list[ast.stmt]) -> bool:
        for stmt in block:
            for child in ast.walk(stmt):
                if isinstance(
                    child,
                    ast.Return | ast.Break | ast.Continue | ast.Yield | ast.YieldFrom,
                ):
                    return True

        return False

    def _estimate_block_reduction(self, block: list[ast.stmt]) -> int:
        base_reduction = len(block)

        nesting_bonus = 0
        for stmt in block:
            for child in ast.walk(stmt):
                if isinstance(child, ast.If | ast.For | ast.While | ast.With | ast.Try):
                    nesting_bonus += 1

        expr_count = 0
        for stmt in block:
            for child in ast.walk(stmt):
                if isinstance(child, ast.Expr):
                    expr_count += 1

        return base_reduction + nesting_bonus + (expr_count // 2)

    def _suggest_method_name(
        self,
        section_name: str,
        inputs: set[str],
        outputs: set[str],
    ) -> str:

        name = section_name.lower().replace(" ", "_")
        name = re.sub(r"[^a-z0-9_]", "", name)

        if name and name not in ("helper", "section", "part"):
            return f"_{name}"

        if outputs:
            output_name = next(iter(outputs))
            return f"_{self._verb_for_output(output_name)}_{output_name}"

        return "_helper"

    def _suggest_method_name_from_io(
        self,
        inputs: set[str],
        outputs: set[str],
    ) -> str:
        if outputs:
            output_name = next(iter(outputs))
            verb = self._verb_for_output(output_name)
            return f"_{verb}_{output_name}"

        if inputs:
            input_name = next(iter(inputs))
            return f"_process_{input_name}"

        return "_helper"

    def _suggest_method_name_from_pattern(self, pattern: str) -> str:

        words = re.findall(r"[a-z]+", pattern.lower())

        if words:
            for word in words:
                if word in self.METHOD_NAME_VERBS:
                    return f"_{word}"
            return f"_{words[0]}"

        return "_helper"

    def _verb_for_output(self, output_name: str) -> str:
        name_lower = output_name.lower()

        verb_mappings: dict[str, str] = {
            "result": "compute",
            "value": "calculate",
            "data": "process",
            "items": "collect",
            "total": "sum",
            "count": "count",
            "list": "build",
            "dict": "create",
            "config": "setup",
            "error": "check",
            "valid": "validate",
        }

        for key, verb in verb_mappings.items():
            if key in name_lower:
                return verb

        return "compute"

    def _get_statement_signature(self, stmt: ast.stmt) -> str:

        parts: list[str] = [type(stmt).__name__]

        for child in ast.iter_child_nodes(stmt):
            parts.append(type(child).__name__)

        return "_".join(parts)

    def _are_similar_statements(self, stmts: list[ast.stmt]) -> bool:
        if len(stmts) < 2:
            return False

        types = {type(s) for s in stmts}

        if len(types) != 1:
            return False

        first_type = type(stmts[0])

        if first_type == ast.Assign:
            target_counts = {len(s.targets) for s in stmts if isinstance(s, ast.Assign)}
            if len(target_counts) != 1:
                return False

        return True

    def _deduplicate_candidates(
        self, candidates: list[ExtractionCandidate]
    ) -> list[ExtractionCandidate]:
        if not candidates:
            return []

        sorted_candidates = sorted(
            candidates,  # type: ignore
            key=operator.itemgetter("estimated_reduction"),  # type: ignore
            reverse=True,
        )

        selected: list[ExtractionCandidate] = []
        selected_ranges: list[tuple[int, int]] = []

        for candidate in sorted_candidates:
            start = candidate["extraction_start"]
            end = candidate["extraction_end"]

            overlaps = False
            for sel_start, sel_end in selected_ranges:
                if not (end < sel_start or start > sel_end):
                    overlaps = True
                    break

            if not overlaps:
                selected.append(candidate)
                selected_ranges.append((start, end))

        return selected

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        return match.estimated_reduction
