"""AST Transform Engine for automated code refactoring."""

import ast
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import (
    ParseError,
)
from .pattern_matcher import BasePattern, PatternMatch, PatternMatcher
from .surgeons.base import BaseSurgeon
from .validator import TransformValidator


@dataclass
class ChangeSpec:
    """Specification for a code change to apply."""

    file_path: Path
    original_content: str
    transformed_content: str
    line_start: int
    line_end: int
    pattern_name: str
    complexity_reduction: int
    confidence: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file_path": str(self.file_path),
            "line_start": self.line_start,
            "line_end": self.line_end,
            "pattern_name": self.pattern_name,
            "complexity_reduction": self.complexity_reduction,
            "confidence": self.confidence,
        }


@dataclass
class TransformMetrics:
    """Metrics for tracking transform performance."""

    patterns_tried: int = 0
    patterns_matched: int = 0
    transforms_attempted: int = 0
    transforms_succeeded: int = 0
    validation_failures: int = 0
    fallback_used: int = 0


class ASTTransformEngine:
    """Main engine coordinating AST-based code transformation.

    The engine:
    1. Parses source code to AST
    2. Identifies refactoring patterns via PatternMatcher
    3. Applies transformations via surgeons (libcst primary, redbaron fallback)
    4. Validates results via TransformValidator
    5. Returns ChangeSpec or None for manual review
    """

    def __init__(
        self,
        patterns: list[BasePattern] | None = None,
        surgeons: list[BaseSurgeon] | None = None,
        validator: TransformValidator | None = None,
    ) -> None:
        """Initialize the transform engine.

        Args:
            patterns: Custom patterns to use (default: all registered)
            surgeons: Custom surgeons to use (default: libcst + redbaron)
            validator: Custom validator (default: TransformValidator())
        """
        self._pattern_matcher = PatternMatcher(patterns)
        self._surgeons = surgeons or []
        self._validator = validator or TransformValidator()

        # File-level locks for concurrent safety
        self._file_locks: dict[str, asyncio.Lock] = {}

        # Metrics tracking
        self._metrics = TransformMetrics()

    def register_pattern(self, pattern: BasePattern) -> None:
        """Register a refactoring pattern."""
        self._pattern_matcher.register(pattern)

    def register_surgeon(self, surgeon: BaseSurgeon) -> None:
        """Register a transformation surgeon."""
        self._surgeons.append(surgeon)

    async def transform(
        self,
        code: str,
        file_path: Path,
        line_start: int = 1,
        line_end: int | None = None,
    ) -> ChangeSpec | None:
        """Transform code to reduce complexity.

        Args:
            code: Source code to transform
            file_path: Path to the file (for error reporting)
            line_start: Starting line of the region to transform
            line_end: Ending line (None = entire file)

        Returns:
            ChangeSpec if transformation succeeded, None for manual review
        """
        # Get or create file lock for concurrency safety
        file_key = str(file_path)
        if file_key not in self._file_locks:
            self._file_locks[file_key] = asyncio.Lock()

        async with self._file_locks[file_key]:
            return await self._transform_impl(code, file_path, line_start, line_end)

    async def _transform_impl(
        self,
        code: str,
        file_path: Path,
        line_start: int,
        line_end: int | None,
    ) -> ChangeSpec | None:
        """Implementation of transform with lock already held."""
        source_lines = code.split("\n")

        # Parse to AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise ParseError(str(e), file_path) from e

        # Find function(s) in the target region
        target_functions = self._find_target_functions(
            tree, line_start, line_end or len(source_lines)
        )

        if not target_functions:
            return None

        # Try to transform each function, starting with highest complexity
        for func_node in target_functions:
            self._metrics.patterns_tried += 1

            # Find matching pattern
            match = self._pattern_matcher.match_function(func_node, source_lines)
            if not match:
                continue

            self._metrics.patterns_matched += 1

            # Try to apply transformation
            result = await self._apply_transformation(
                code, match, file_path, source_lines
            )

            if result:
                return result

        # No transformation succeeded - mark for manual review
        return None

    def _find_target_functions(
        self,
        tree: ast.AST,
        line_start: int,
        line_end: int,
    ) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Find functions in the target region, sorted by complexity."""
        functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Check if function overlaps with target region
                func_start = node.lineno
                func_end = node.end_lineno or func_start

                if func_start <= line_end and func_end >= line_start:
                    functions.append(node)

        # Sort by complexity (highest first for maximum impact)
        def get_complexity(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
            return self._validator._calculate_complexity(ast.unparse(func))

        functions.sort(key=get_complexity, reverse=True)
        return functions

    async def _apply_transformation(
        self,
        code: str,
        match: PatternMatch,
        file_path: Path,
        source_lines: list[str],
    ) -> ChangeSpec | None:
        """Try to apply transformation with all surgeons."""
        self._metrics.transforms_attempted += 1

        errors: list[str] = []

        for surgeon in self._surgeons:
            if not surgeon.can_handle(match.match_info):
                continue

            result = surgeon.apply(code, match.match_info, file_path)

            if not result.success:
                errors.append(f"{surgeon.name}: {result.error_message}")
                continue

            # Validate transformation
            validation = self._validator.validate(
                code,
                result.transformed_code or "",
                file_path,
            )

            if validation.valid:
                self._metrics.transforms_succeeded += 1
                return ChangeSpec(
                    file_path=file_path,
                    original_content=code,
                    transformed_content=result.transformed_code or "",
                    line_start=match.line_start,
                    line_end=match.line_end,
                    pattern_name=match.pattern_name,
                    complexity_reduction=abs(validation.complexity_delta or 0),
                )
            else:
                self._metrics.validation_failures += 1
                errors.append(f"Validation failed: {validation.errors}")

        # Track fallback usage if we tried multiple surgeons
        if len(errors) > 1:
            self._metrics.fallback_used += 1

        return None

    @property
    def metrics(self) -> TransformMetrics:
        """Get current transform metrics."""
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset metrics counters."""
        self._metrics = TransformMetrics()
