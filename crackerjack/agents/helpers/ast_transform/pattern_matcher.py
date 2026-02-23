
import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class PatternPriority(IntEnum):

    EARLY_RETURN = 1
    GUARD_CLAUSE = 2
    DECOMPOSE_CONDITIONAL = 3
    EXTRACT_METHOD = 4


@dataclass
class PatternMatch:

    pattern_name: str
    priority: PatternPriority
    line_start: int
    line_end: int
    node: ast.AST
    match_info: dict[str, Any] = field(default_factory=dict)


    estimated_reduction: int = 0


    context: dict[str, Any] = field(default_factory=dict)


class BasePattern(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def priority(self) -> PatternPriority:
        ...

    @property
    def supports_async(self) -> bool:
        return True

    @abstractmethod
    def match(self, node: ast.AST, source_lines: list[str]) -> PatternMatch | None:
        ...

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        return 1


class PatternMatcher:

    def __init__(self, patterns: list[BasePattern] | None = None) -> None:
        self._patterns: list[BasePattern] = []
        if patterns:
            for pattern in patterns:
                self.register(pattern)

    def register(self, pattern: BasePattern) -> None:
        self._patterns.append(pattern)
        self._patterns.sort(key=lambda p: p.priority)

    def match_function(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: list[str],
    ) -> PatternMatch | None:

        is_async = isinstance(func_node, ast.AsyncFunctionDef)

        for pattern in self._patterns:

            if is_async and not pattern.supports_async:
                continue


            for node in ast.walk(func_node):
                match = pattern.match(node, source_lines)
                if match:

                    match.estimated_reduction = pattern.estimate_complexity_reduction(
                        match
                    )
                    return match

        return None

    def match_all(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: list[str],
    ) -> list[PatternMatch]:
        matches: list[PatternMatch] = []
        is_async = isinstance(func_node, ast.AsyncFunctionDef)

        for pattern in self._patterns:
            if is_async and not pattern.supports_async:
                continue

            for node in ast.walk(func_node):
                match = pattern.match(node, source_lines)
                if match:
                    match.estimated_reduction = pattern.estimate_complexity_reduction(
                        match
                    )
                    matches.append(match)


        matches.sort(key=lambda m: m.priority)
        return matches

    @property
    def registered_patterns(self) -> list[str]:
        return [p.name for p in self._patterns]
