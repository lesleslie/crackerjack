"""Pattern matching for AST-based refactoring."""

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class PatternPriority(IntEnum):
    """Priority ordering for refactoring patterns.

    Lower numbers = try first (smaller/simpler changes).
    """

    EARLY_RETURN = 1      # Try first - smallest change
    GUARD_CLAUSE = 2
    DECOMPOSE_CONDITIONAL = 3
    EXTRACT_METHOD = 4    # Try last - largest change


@dataclass
class PatternMatch:
    """Result of a successful pattern match."""

    pattern_name: str
    priority: PatternPriority
    line_start: int
    line_end: int
    node: ast.AST
    match_info: dict[str, Any] = field(default_factory=dict)

    # Estimated complexity reduction
    estimated_reduction: int = 0

    # Additional context for surgeons
    context: dict[str, Any] = field(default_factory=dict)


class BasePattern(ABC):
    """Abstract base class for refactoring patterns.

    Each pattern identifies a specific code structure that can be
    refactored to reduce cognitive complexity.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return pattern name for logging/error messages."""
        ...

    @property
    @abstractmethod
    def priority(self) -> PatternPriority:
        """Return pattern priority (lower = try first)."""
        ...

    @property
    def supports_async(self) -> bool:
        """Whether this pattern supports async functions.

        Override to return False if pattern doesn't work with async/await.
        """
        return True

    @abstractmethod
    def match(self, node: ast.AST, source_lines: list[str]) -> PatternMatch | None:
        """Check if this pattern matches the given AST node.

        Args:
            node: AST node to check
            source_lines: Original source code lines for context

        Returns:
            PatternMatch if pattern matches, None otherwise
        """
        ...

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        """Estimate how much complexity this pattern will reduce.

        Override for more accurate estimates.

        Args:
            match: The pattern match

        Returns:
            Estimated complexity reduction (default: 1)
        """
        return 1


class PatternMatcher:
    """Coordinates pattern matching across all registered patterns.

    Patterns are tried in priority order (lowest first). The first
    match is returned.
    """

    def __init__(self, patterns: list[BasePattern] | None = None) -> None:
        """Initialize with optional list of patterns.

        Args:
            patterns: Patterns to register. If None, uses default patterns.
        """
        self._patterns: list[BasePattern] = []
        if patterns:
            for pattern in patterns:
                self.register(pattern)

    def register(self, pattern: BasePattern) -> None:
        """Register a pattern for matching.

        Patterns are kept sorted by priority.

        Args:
            pattern: Pattern to register
        """
        self._patterns.append(pattern)
        self._patterns.sort(key=lambda p: p.priority)

    def match_function(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: list[str],
    ) -> PatternMatch | None:
        """Find the best matching pattern for a function.

        Tries patterns in priority order, returning first match.

        Args:
            func_node: Function AST node to analyze
            source_lines: Original source code lines

        Returns:
            First matching PatternMatch, or None if no patterns match
        """
        # Check async support
        is_async = isinstance(func_node, ast.AsyncFunctionDef)

        for pattern in self._patterns:
            # Skip patterns that don't support async
            if is_async and not pattern.supports_async:
                continue

            # Walk the function body looking for matches
            for node in ast.walk(func_node):
                match = pattern.match(node, source_lines)
                if match:
                    # Enhance match with estimated reduction
                    match.estimated_reduction = pattern.estimate_complexity_reduction(match)
                    return match

        return None

    def match_all(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: list[str],
    ) -> list[PatternMatch]:
        """Find all matching patterns for a function.

        Returns all matches in priority order.

        Args:
            func_node: Function AST node to analyze
            source_lines: Original source code lines

        Returns:
            List of all PatternMatches, sorted by priority
        """
        matches: list[PatternMatch] = []
        is_async = isinstance(func_node, ast.AsyncFunctionDef)

        for pattern in self._patterns:
            if is_async and not pattern.supports_async:
                continue

            for node in ast.walk(func_node):
                match = pattern.match(node, source_lines)
                if match:
                    match.estimated_reduction = pattern.estimate_complexity_reduction(match)
                    matches.append(match)

        # Sort by priority
        matches.sort(key=lambda m: m.priority)
        return matches

    @property
    def registered_patterns(self) -> list[str]:
        """Return names of all registered patterns."""
        return [p.name for p in self._patterns]
