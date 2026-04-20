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
        r"^#\s*section\s+\d+\s*[:.)-]",
        r"^#\s*\d+\s*[:.)-]\s*[A-Z]",
        r"^#\s*---+$",
        r"^#\s*===+$",
        r"^#\s*(validate|check|verify|ensure|setup|initialize)",
        r"^#\s*(process|transform|convert|parse|format)",
        r"^#\s*(calculate|compute|aggregate|sum)",
        r"^#\s*(build|create|construct|generate)",
        r"^#\s*(handle|manage|execute|run|perform)",
        r"^#\s*(save|store|persist|write|load|fetch|get)",
        r"^#\s*(cleanup|teardown|finalize|complete)",
        r"^#\s*Configuration paths",
        r"^#\s*Default skip servers",
        r"^#\s*Helper functions",
        r"^#\s*Main sync logic",
        r"^#\s*Load configs",
        r"^#\s*Default sync types",
        r"^#\s*Sync MCP servers",
        r"^#\s*Sync extensions",
        r"^#\s*Sync commands",
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

        registration_wrapper = self._find_registration_wrapper_candidate(node)
        if registration_wrapper is not None:
            return PatternMatch(
                pattern_name=self.name,
                priority=self.priority,
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                node=node,
                match_info={
                    "type": "extract_method",
                    "node": node,
                    "lift_to_module": True,
                    "registration_wrapper": True,
                    "extraction_start": node.body[0].lineno,
                    "extraction_end": node.body[-1].end_lineno or node.body[-1].lineno,
                    "inputs": [],
                    "outputs": [],
                    "suggested_name": registration_wrapper["suggested_name"],
                    "block_statements": node.body,
                },
                estimated_reduction=registration_wrapper["estimated_reduction"],
                context={
                    "function_name": node.name,
                    "function_length": len(node.body),
                    "candidate_count": registration_wrapper["candidate_count"],
                    "registration_wrapper": True,
                },
            )

        nested_functions = [
            stmt
            for stmt in node.body
            if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        metrics_summary_candidates = self._find_metrics_summary_candidates(node)
        if metrics_summary_candidates is not None:
            return PatternMatch(
                pattern_name=self.name,
                priority=self.priority,
                line_start=metrics_summary_candidates[0]["extraction_start"],
                line_end=metrics_summary_candidates[-1]["extraction_end"],
                node=node,
                match_info={
                    "type": "split_sections",
                    "node": node,
                    "extraction_start": metrics_summary_candidates[0][
                        "extraction_start"
                    ],
                    "extraction_end": metrics_summary_candidates[-1]["extraction_end"],
                    "split_mode": "generic",
                    "section_candidates": metrics_summary_candidates,
                    "section_blocks": [
                        candidate["block_statements"]
                        for candidate in metrics_summary_candidates
                    ],
                    "section_names": [
                        candidate["suggested_name"]
                        for candidate in metrics_summary_candidates
                    ],
                },
                estimated_reduction=sum(
                    candidate["estimated_reduction"]
                    for candidate in metrics_summary_candidates
                ),
                context={
                    "function_name": node.name,
                    "function_length": len(node.body),
                    "candidate_count": len(metrics_summary_candidates),
                    "split_sections": True,
                    "metrics_summary": True,
                },
            )

        function_name = node.name.lower()
        helper_markers = ("helper", "sync", "config", "register", "metrics", "tools")
        if len(nested_functions) >= 2 and any(
            marker in function_name for marker in helper_markers
        ):
            return PatternMatch(
                pattern_name=self.name,
                priority=self.priority,
                line_start=nested_functions[0].lineno,
                line_end=nested_functions[-1].end_lineno or nested_functions[-1].lineno,
                node=node,
                match_info={
                    "type": "lift_nested_helpers",
                    "node": node,
                    "extraction_start": nested_functions[0].lineno,
                    "extraction_end": (
                        nested_functions[-1].end_lineno or nested_functions[-1].lineno
                    ),
                    "nested_function_names": [stmt.name for stmt in nested_functions],
                    "suggested_name": f"_{node.name}_impl",
                },
                estimated_reduction=sum(
                    (nested.end_lineno or nested.lineno) - nested.lineno + 1
                    for nested in nested_functions
                ),
                context={
                    "function_name": node.name,
                    "function_length": len(node.body),
                    "candidate_count": len(nested_functions),
                    "lift_nested_helpers": True,
                },
            )

        section_candidates = self._find_comment_sections(node, source_lines)
        if self._should_split_sections(node, section_candidates):
            section_blocks = [
                candidate["block_statements"] for candidate in section_candidates
            ]
            return PatternMatch(
                pattern_name=self.name,
                priority=self.priority,
                line_start=section_candidates[0]["extraction_start"],
                line_end=section_candidates[-1]["extraction_end"],
                node=node,
                match_info={
                    "type": "split_sections",
                    "node": node,
                    "extraction_start": section_candidates[0]["extraction_start"],
                    "extraction_end": section_candidates[-1]["extraction_end"],
                    "split_mode": "report"
                    if any(
                        marker in node.name.lower()
                        for marker in (
                            "compute",
                            "generate",
                            "report",
                            "summarize",
                            "build",
                        )
                    )
                    else "generic",
                    "section_candidates": section_candidates,
                    "section_blocks": section_blocks,
                    "section_names": [
                        candidate["suggested_name"] for candidate in section_candidates
                    ],
                },
                estimated_reduction=sum(
                    candidate["estimated_reduction"] for candidate in section_candidates
                ),
                context={
                    "function_name": node.name,
                    "function_length": len(node.body),
                    "candidate_count": len(section_candidates),
                    "split_sections": True,
                },
            )

        if len(node.body) < self.MIN_FUNCTION_SIZE:
            return None

        candidates = self._find_extraction_candidates(node, source_lines)

        if not candidates:
            return None

        best_candidate = max(candidates, key=operator.itemgetter("estimated_reduction"))
        lift_to_module = self._should_lift_to_module(node, best_candidate)

        return PatternMatch(
            pattern_name=self.name,
            priority=self.priority,
            line_start=best_candidate["extraction_start"],
            line_end=best_candidate["extraction_end"],
            node=node,
            match_info={
                "type": "extract_method",
                "node": node,
                "extraction_start": best_candidate["extraction_start"],
                "extraction_end": best_candidate["extraction_end"],
                "inputs": best_candidate["inputs"],
                "outputs": best_candidate["outputs"],
                "suggested_name": best_candidate["suggested_name"],
                "block_statements": best_candidate["block_statements"],
                "lift_to_module": lift_to_module,
            },
            estimated_reduction=best_candidate["estimated_reduction"],
            context={
                "function_name": node.name,
                "function_length": len(node.body),
                "candidate_count": len(candidates),
                "lift_to_module": lift_to_module,
            },
        )

    def _find_metrics_summary_candidates(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[ExtractionCandidate] | None:
        if "summary" not in node.name.lower():
            return None

        try_block = next(
            (stmt for stmt in node.body if isinstance(stmt, ast.Try) and stmt.body),
            None,
        )
        if try_block is None:
            return None

        loop_candidates: list[ExtractionCandidate] = []
        for stmt in try_block.body:
            if not isinstance(stmt, ast.For):
                continue

            loop_source = ast.unparse(stmt.iter)
            if ".collect()" not in loop_source:
                continue

            loop_candidates.append(
                {
                    "extraction_start": stmt.lineno,
                    "extraction_end": stmt.end_lineno or stmt.lineno,
                    "inputs": ["metrics", "summary"],
                    "outputs": [],
                    "suggested_name": self._suggest_metrics_helper_name(loop_source),
                    "block_statements": [stmt],
                    "estimated_reduction": (
                        (stmt.end_lineno or stmt.lineno) - stmt.lineno + 1
                    ),
                }
            )

        if len(loop_candidates) < 3:
            return None

        return loop_candidates

    def _suggest_metrics_helper_name(self, loop_source: str) -> str:
        match = re.search(r"metrics\.([A-Za-z_][\w]*)", loop_source)
        if match:
            return f"_collect_{match.group(1)}"

        return "_collect_metric_block"

    def _find_registration_wrapper_candidate(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> dict[str, Any] | None:
        if not func_node.name.startswith("register_"):
            return None

        if len(func_node.body) < 3:
            return None

        nested_defs = [
            stmt
            for stmt in func_node.body
            if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        decorated_nested_defs = [
            stmt for stmt in nested_defs if getattr(stmt, "decorator_list", [])
        ]

        if len(nested_defs) < 2 and len(decorated_nested_defs) < 1:
            return None

        suggested_name = f"_{func_node.name}_impl"
        estimated_reduction = max(4, len(func_node.body) + len(nested_defs))

        return {
            "suggested_name": suggested_name,
            "estimated_reduction": estimated_reduction,
            "candidate_count": len(nested_defs),
        }

    def _should_lift_to_module(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        best_candidate: ExtractionCandidate,
    ) -> bool:
        if self._is_registration_wrapper(func_node):
            return True

        if func_node.args.args and func_node.args.args[0].arg in {"self", "cls"}:
            return best_candidate["estimated_reduction"] >= 5

        return False

    @staticmethod
    def _is_registration_wrapper(
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        return func_node.name.startswith("register_")

    def _should_split_sections(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        section_candidates: list[ExtractionCandidate],
    ) -> bool:
        if len(section_candidates) < 3:
            return False

        if self._is_registration_wrapper(func_node):
            return False

        if (
            func_node.col_offset > 0
            and func_node.args.args
            and func_node.args.args[0].arg in {"self", "cls"}
        ):
            return False

        function_name = func_node.name.lower()
        report_markers = (
            "compute",
            "generate",
            "report",
            "summarize",
            "build",
        )
        if any(marker in function_name for marker in report_markers):
            return True

        helper_markers = (
            "helper",
            "sync",
            "config",
            "merge",
        )
        if any(marker in function_name for marker in helper_markers):
            return len(section_candidates) >= 4

        return any(
            candidate["estimated_reduction"] >= 8 for candidate in section_candidates
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

            elif isinstance(child, ast.ExceptHandler) and child.name:
                if isinstance(child.name, str):
                    defined.add(child.name)

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
