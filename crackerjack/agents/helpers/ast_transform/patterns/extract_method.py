"""Extract Method pattern for reducing cognitive complexity.

The Extract Method pattern identifies cohesive code blocks within long
functions that can be extracted into separate helper methods.

Example transformation:
    # Before (complexity 8)
    def process_data(data: dict) -> Result:
        # Validate input
        if not data:
            return Result(error="Empty data")
        if "id" not in data:
            return Result(error="Missing ID")
        if "value" not in data:
            return Result(error="Missing value")

        # Transform values
        transformed = {}
        for key, value in data.items():
            if isinstance(value, str):
                transformed[key] = value.strip().lower()
            else:
                transformed[key] = value

        # Calculate metrics
        total = sum(v for v in transformed.values() if isinstance(v, int | float))
        count = len([v for v in transformed.values() if v is not None])
        avg = total / count if count > 0 else 0

        return Result(data=transformed, metrics={"total": total, "avg": avg})

    # After (complexity 3 per function)
    def process_data(data: dict) -> Result:
        if not (result := _validate_input(data)):
            return result
        transformed = _transform_values(data)
        metrics = _calculate_metrics(transformed)
        return Result(data=transformed, metrics=metrics)

    def _validate_input(data: dict) -> Result | None:
        if not data:
            return Result(error="Empty data")
        if "id" not in data:
            return Result(error="Missing ID")
        if "value" not in data:
            return Result(error="Missing value")
        return None

    def _transform_values(data: dict) -> dict:
        transformed = {}
        for key, value in data.items():
            if isinstance(value, str):
                transformed[key] = value.strip().lower()
            else:
                transformed[key] = value
        return transformed

    def _calculate_metrics(data: dict) -> dict:
        total = sum(v for v in data.values() if isinstance(v, int | float))
        count = len([v for v in data.values() if v is not None])
        avg = total / count if count > 0 else 0
        return {"total": total, "avg": avg}
"""

from __future__ import annotations

import ast
import re
from typing import Any

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)

# Type alias for extraction candidate dictionaries
ExtractionCandidate = dict[str, Any]


class ExtractMethodPattern(BasePattern):
    """Pattern that matches cohesive code blocks suitable for method extraction.

    Matches when:
    - A function body has clearly identifiable sections
    - A code block uses specific inputs and produces specific outputs
    - Comments indicate logical boundaries between sections
    - Code blocks are sufficiently large to benefit from extraction

    Does NOT match:
    - Trivially small code blocks (fewer than 3 statements)
    - Code blocks with complex control flow that spans entire function
    - Code that can't be cleanly isolated
    """

    # Minimum number of statements to consider for extraction
    MIN_BLOCK_SIZE: int = 3

    # Minimum function body size to consider for extraction
    MIN_FUNCTION_SIZE: int = 10

    # Comment patterns that often indicate section boundaries
    SECTION_PATTERNS: tuple[str, ...] = (
        # Standard section headers
        r"^#\s*[A-Z][A-Za-z\s]+$",  # # Section Name
        r"^#\s*---+$",  # # ---
        r"^#\s*===+$",  # # ===
        # Common action verbs
        r"^#\s*(validate|check|verify|ensure|setup|initialize)",
        r"^#\s*(process|transform|convert|parse|format)",
        r"^#\s*(calculate|compute|aggregate|sum)",
        r"^#\s*(build|create|construct|generate)",
        r"^#\s*(handle|manage|execute|run|perform)",
        r"^#\s*(save|store|persist|write|load|fetch|get)",
        r"^#\s*(cleanup|teardown|finalize|complete)",
    )

    # Common verbs for generating method names
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
        return True  # Extraction works the same for async functions

    def match(self, node: ast.AST, source_lines: list[str]) -> PatternMatch | None:
        """Check if this node is part of a function with extraction candidates.

        Looks for:
        1. Functions with multiple logical sections
        2. Code blocks with clear inputs and outputs
        3. Comments that indicate section boundaries
        4. Repeated code patterns

        Args:
            node: AST node to check (looking for FunctionDef/AsyncFunctionDef)
            source_lines: Original source code lines for context

        Returns:
            PatternMatch if extraction candidate found, None otherwise
        """
        # Only match function definitions
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            return None

        # Function must be large enough to benefit from extraction
        if len(node.body) < self.MIN_FUNCTION_SIZE:
            return None

        # Find extraction candidates within the function
        candidates = self._find_extraction_candidates(node, source_lines)

        if not candidates:
            return None

        # Select the best candidate (largest reduction potential)
        best_candidate = max(candidates, key=lambda c: c["estimated_reduction"])

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
        """Find all extraction candidates within a function.

        Args:
            func_node: Function AST node to analyze
            source_lines: Original source code lines

        Returns:
            List of candidate dictionaries with extraction details
        """
        candidates: list[ExtractionCandidate] = []

        # Strategy 1: Find sections marked by comments
        comment_sections = self._find_comment_sections(func_node, source_lines)
        candidates.extend(comment_sections)

        # Strategy 2: Find cohesive blocks based on variable usage
        variable_sections = self._find_variable_cohesive_blocks(func_node)
        candidates.extend(variable_sections)

        # Strategy 3: Find repeated patterns
        repeated_patterns = self._find_repeated_patterns(func_node)
        candidates.extend(repeated_patterns)

        return candidates

    def _find_comment_sections(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: list[str],
    ) -> list[ExtractionCandidate]:
        """Find sections delineated by comments.

        Args:
            func_node: Function AST node
            source_lines: Source code lines

        Returns:
            List of extraction candidates based on comment boundaries
        """
        candidates: list[ExtractionCandidate] = []

        # Track section boundaries
        section_starts: list[tuple[int, str]] = []

        for i, stmt in enumerate(func_node.body):
            stmt_line = stmt.lineno

            # Check for comment before this statement
            if stmt_line > 1:
                prev_line = source_lines[stmt_line - 2].strip()
                if self._is_section_comment(prev_line):
                    section_name = self._extract_section_name(prev_line)
                    section_starts.append((i, section_name))

        # If we found at least 1 section, create candidates
        if len(section_starts) >= 1:
            for idx, (start_idx, section_name) in enumerate(section_starts):
                # Determine end of this section
                if idx + 1 < len(section_starts):
                    end_idx = section_starts[idx + 1][0] - 1
                else:
                    end_idx = len(func_node.body) - 1

                # Skip if section is too small
                block_size = end_idx - start_idx + 1
                if block_size < self.MIN_BLOCK_SIZE:
                    continue

                block = func_node.body[start_idx : end_idx + 1]
                inputs, outputs = self._analyze_block_io(block)

                suggested_name = self._suggest_method_name(section_name, inputs, outputs)

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
        """Find blocks that use specific variables and produce specific outputs.

        This analyzes variable usage patterns to identify cohesive blocks
        that could be extracted.

        Args:
            func_node: Function AST node

        Returns:
            List of extraction candidates based on variable cohesion
        """
        candidates: list[ExtractionCandidate] = []

        # Get all variables defined in function parameters
        param_names: set[str] = set()
        for arg in func_node.args.args:
            param_names.add(arg.arg)
        if func_node.args.kwarg:
            param_names.add(func_node.args.kwarg.arg)
        if func_node.args.vararg:
            param_names.add(func_node.args.vararg.arg)

        # Track variable definitions and usages
        defined_vars: set[str] = set(param_names)
        var_def_positions: dict[str, int] = {}

        for i, stmt in enumerate(func_node.body):
            # Find variables defined in this statement
            new_defs = self._get_defined_variables(stmt)
            for var in new_defs:
                var_def_positions[var] = i
            defined_vars.update(new_defs)

        # Look for sequential blocks that form a cohesive unit
        # This is a heuristic: blocks where later statements use variables
        # from earlier statements but don't depend on function-level state

        # Slide a window over the function body
        for start_idx in range(len(func_node.body) - self.MIN_BLOCK_SIZE + 1):
            for end_idx in range(
                start_idx + self.MIN_BLOCK_SIZE - 1, len(func_node.body)
            ):
                block = func_node.body[start_idx : end_idx + 1]

                # Skip if block contains control flow that's hard to extract
                if self._has_complex_control_flow(block):
                    continue

                inputs, outputs = self._analyze_block_io(block)

                # Good candidate if:
                # - Block uses some inputs (connected to rest of function)
                # - Block produces some outputs (useful extraction)
                # - Block is self-contained (doesn't access too many external vars)
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
                            "estimated_reduction": self._estimate_block_reduction(block),
                        }
                    )

        # Deduplicate overlapping candidates, keeping best one
        return self._deduplicate_candidates(candidates)

    def _find_repeated_patterns(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[ExtractionCandidate]:
        """Find repeated code patterns that could be extracted.

        Args:
            func_node: Function AST node

        Returns:
            List of extraction candidates based on repeated patterns
        """
        candidates: list[ExtractionCandidate] = []

        # Group similar statements by their structural type
        stmt_groups: dict[str, list[tuple[int, ast.stmt]]] = {}

        for i, stmt in enumerate(func_node.body):
            # Create a structural signature for the statement
            signature = self._get_statement_signature(stmt)
            if signature not in stmt_groups:
                stmt_groups[signature] = []
            stmt_groups[signature].append((i, stmt))

        # Look for groups of similar statements
        for signature, group in stmt_groups.items():
            if len(group) < 2:
                continue

            # Check if these statements are similar enough to extract
            # (This is a simplified heuristic)
            if self._are_similar_statements([s for _, s in group]):
                # Use the first occurrence as the extraction template
                _first_idx, first_stmt = group[0]

                # Find the block containing this pattern
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
                        "estimated_reduction": len(group) - 1,  # Each repeat saved
                        "repeat_count": len(group),
                    }
                )

        return candidates

    def _is_section_comment(self, line: str) -> bool:
        """Check if a line is a section comment.

        Args:
            line: Source line to check

        Returns:
            True if line appears to be a section comment
        """
        if not line.startswith("#"):
            return False

        for pattern in self.SECTION_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True

        return False

    def _extract_section_name(self, comment: str) -> str:
        """Extract a descriptive name from a section comment.

        Args:
            comment: Comment line (starting with #)

        Returns:
            Extracted name or "helper" if nothing found
        """
        # Remove # and clean up
        cleaned = comment.lstrip("#").strip()

        # Remove common separators
        cleaned = re.sub(r"^[-=]+\s*", "", cleaned)
        cleaned = re.sub(r"\s*[-=]+$", "", cleaned)

        # Convert to snake_case
        cleaned = cleaned.lower().replace(" ", "_")

        # Remove special characters
        cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)

        return cleaned or "helper"

    def _analyze_block_io(
        self,
        block: list[ast.stmt],
    ) -> tuple[set[str], set[str]]:
        """Analyze the inputs and outputs of a code block.

        Inputs are variables used by the block but not defined within it.
        Outputs are variables defined within the block.

        Args:
            block: List of statements to analyze

        Returns:
            Tuple of (inputs, outputs) as sets of variable names
        """
        # Collect all variables used and defined
        used_vars: set[str] = set()
        defined_vars: set[str] = set()

        for stmt in block:
            # Get variables used (read) in this statement
            used_vars.update(self._get_used_variables(stmt))

            # Get variables defined (written) in this statement
            defined_vars.update(self._get_defined_variables(stmt))

        # Inputs = used but not defined in block
        inputs = used_vars - defined_vars

        # Outputs = defined in block
        outputs = defined_vars

        return inputs, outputs

    def _get_used_variables(self, node: ast.AST) -> set[str]:
        """Get all variables used (read) in an AST node.

        Args:
            node: AST node to analyze

        Returns:
            Set of variable names used
        """
        used: set[str] = set()

        for child in ast.walk(node):
            # Variable references (but not in assignment targets)
            if isinstance(child, ast.Name) and isinstance(
                child.ctx,
                ast.Load,
            ):
                used.add(child.id)
            # Function argument names
            elif isinstance(child, ast.arg):
                used.add(child.arg)

        return used

    def _get_defined_variables(self, node: ast.AST) -> set[str]:
        """Get all variables defined (written) in an AST node.

        Args:
            node: AST node to analyze

        Returns:
            Set of variable names defined
        """
        defined: set[str] = set()

        for child in ast.walk(node):
            # Simple assignment
            if isinstance(child, ast.Name) and isinstance(
                child.ctx,
                ast.Store,
            ):
                defined.add(child.id)
            # Tuple unpacking
            elif isinstance(child, ast.Tuple | ast.List):
                for elt in child.elts:
                    if isinstance(elt, ast.Name) and isinstance(
                        elt.ctx,
                        ast.Store,
                    ):
                        defined.add(elt.id)
            # For loop variable
            elif isinstance(child, ast.For):
                defined.update(self._get_target_names(child.target))
            # Comprehension target
            elif isinstance(child, ast.comprehension):
                defined.update(self._get_target_names(child.target))

        return defined

    def _get_target_names(self, target: ast.expr) -> set[str]:
        """Extract names from an assignment target.

        Args:
            target: AST expression (Name, Tuple, or List)

        Returns:
            Set of variable names
        """
        names: set[str] = set()

        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Tuple | ast.List):
            for elt in target.elts:
                names.update(self._get_target_names(elt))

        return names

    def _has_complex_control_flow(self, block: list[ast.stmt]) -> bool:
        """Check if a block has complex control flow that's hard to extract.

        Args:
            block: List of statements to check

        Returns:
            True if block has complex control flow
        """
        for stmt in block:
            # Returns, breaks, continues make extraction complex
            for child in ast.walk(stmt):
                if isinstance(
                    child,
                    ast.Return | ast.Break | ast.Continue | ast.Yield | ast.YieldFrom,
                ):
                    return True

        return False

    def _estimate_block_reduction(self, block: list[ast.stmt]) -> int:
        """Estimate complexity reduction from extracting a block.

        Larger blocks with more internal complexity benefit more from extraction.

        Args:
            block: List of statements to analyze

        Returns:
            Estimated complexity reduction
        """
        base_reduction = len(block)

        # Count nested structures
        nesting_bonus = 0
        for stmt in block:
            for child in ast.walk(stmt):
                if isinstance(child, ast.If | ast.For | ast.While | ast.With | ast.Try):
                    nesting_bonus += 1

        # Count expressions
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
        """Suggest a method name based on section name and I/O.

        Args:
            section_name: Name extracted from comment
            inputs: Set of input variable names
            outputs: Set of output variable names

        Returns:
            Suggested method name
        """
        # Clean up section name
        name = section_name.lower().replace(" ", "_")
        name = re.sub(r"[^a-z0-9_]", "", name)

        # If it's already a good name, use it
        if name and name not in ("helper", "section", "part"):
            return f"_{name}"

        # Otherwise, try to derive from outputs
        if outputs:
            output_name = next(iter(outputs))
            return f"_{self._verb_for_output(output_name)}_{output_name}"

        return "_helper"

    def _suggest_method_name_from_io(
        self,
        inputs: set[str],
        outputs: set[str],
    ) -> str:
        """Suggest a method name based on inputs and outputs.

        Args:
            inputs: Set of input variable names
            outputs: Set of output variable names

        Returns:
            Suggested method name
        """
        if outputs:
            output_name = next(iter(outputs))
            verb = self._verb_for_output(output_name)
            return f"_{verb}_{output_name}"

        if inputs:
            input_name = next(iter(inputs))
            return f"_process_{input_name}"

        return "_helper"

    def _suggest_method_name_from_pattern(self, pattern: str) -> str:
        """Suggest a method name based on a pattern signature.

        Args:
            pattern: Structural pattern signature

        Returns:
            Suggested method name
        """
        # Try to extract meaningful words from the pattern
        words = re.findall(r"[a-z]+", pattern.lower())

        if words:
            # Use the first meaningful verb or noun
            for word in words:
                if word in self.METHOD_NAME_VERBS:
                    return f"_{word}"
            return f"_{words[0]}"

        return "_helper"

    def _verb_for_output(self, output_name: str) -> str:
        """Get an appropriate verb for an output variable name.

        Args:
            output_name: Name of the output variable

        Returns:
            Verb to use in method name
        """
        name_lower = output_name.lower()

        # Map common output names to verbs
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
        """Get a structural signature for a statement.

        This is used to identify similar statements for extraction.

        Args:
            stmt: Statement to analyze

        Returns:
            String signature representing statement structure
        """
        # Create a simple structural signature
        parts: list[str] = [type(stmt).__name__]

        for child in ast.iter_child_nodes(stmt):
            parts.append(type(child).__name__)

        return "_".join(parts)

    def _are_similar_statements(self, stmts: list[ast.stmt]) -> bool:
        """Check if statements are structurally similar.

        Args:
            stmts: List of statements to compare

        Returns:
            True if statements are similar enough to extract
        """
        if len(stmts) < 2:
            return False

        # Get types of all statements
        types = {type(s) for s in stmts}

        # Must all be same type
        if len(types) != 1:
            return False

        # Check structural similarity
        first_type = type(stmts[0])

        # For assignments, check that they have similar structure
        if first_type == ast.Assign:
            # All should have same number of targets
            target_counts = {len(s.targets) for s in stmts if isinstance(s, ast.Assign)}
            if len(target_counts) != 1:
                return False

        return True

    def _deduplicate_candidates(
        self, candidates: list[ExtractionCandidate]
    ) -> list[ExtractionCandidate]:
        """Remove overlapping candidates, keeping the best ones.

        Args:
            candidates: List of extraction candidates

        Returns:
            Deduplicated list
        """
        if not candidates:
            return []

        # Sort by estimated reduction (descending)
        sorted_candidates = sorted(
            candidates,
            key=lambda c: c["estimated_reduction"],
            reverse=True,
        )

        # Keep candidates that don't overlap with already selected ones
        selected: list[ExtractionCandidate] = []
        selected_ranges: list[tuple[int, int]] = []

        for candidate in sorted_candidates:
            start = candidate["extraction_start"]
            end = candidate["extraction_end"]

            # Check if this overlaps with any selected candidate
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
        """Return the estimated complexity reduction for this match.

        Args:
            match: The pattern match

        Returns:
            Estimated complexity reduction
        """
        return match.estimated_reduction
