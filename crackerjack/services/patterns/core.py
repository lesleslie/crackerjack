"""Core pattern validation classes and utilities.

This module contains the base classes and utilities for safely handling
regex patterns with validation, caching, and performance monitoring.
"""

import re
import signal
import threading
import time
import typing as t
from dataclasses import dataclass, field
from re import Pattern

MAX_INPUT_SIZE = 10 * 1024 * 1024
MAX_ITERATIONS = 10
PATTERN_CACHE_SIZE = 100


class CompiledPatternCache:
    _lock = threading.RLock()
    _cache: dict[str, Pattern[str]] = {}
    _max_size = PATTERN_CACHE_SIZE

    @classmethod
    def get_compiled_pattern(cls, pattern: str) -> Pattern[str]:
        return cls.get_compiled_pattern_with_flags(pattern, pattern, 0)

    @classmethod
    def get_compiled_pattern_with_flags(
        cls, cache_key: str, pattern: str, flags: int
    ) -> Pattern[str]:
        with cls._lock:
            if cache_key in cls._cache:
                return cls._cache[cache_key]

            try:
                compiled = re.compile(pattern, flags)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{pattern}': {e}")

            if len(cls._cache) >= cls._max_size:
                oldest_key = next(iter(cls._cache))
                del cls._cache[oldest_key]

            cls._cache[cache_key] = compiled
            return compiled

    @classmethod
    def clear_cache(cls) -> None:
        with cls._lock:
            cls._cache.clear()

    @classmethod
    def get_cache_stats(cls) -> dict[str, int | list[str]]:
        with cls._lock:
            return {
                "size": len(cls._cache),
                "max_size": cls._max_size,
                "patterns": list[t.Any](cls._cache.keys()),
            }


def validate_pattern_safety(pattern: str) -> list[str]:
    warnings = []

    if ".*.*" in pattern:
        warnings.append("Multiple .* constructs may cause performance issues")

    if ".+.+" in pattern:
        warnings.append("Multiple .+ constructs may cause performance issues")

    nested_quantifiers = re.findall(r"[+*?]\??[+*?]", pattern)
    if nested_quantifiers:
        warnings.append(f"Nested quantifiers detected: {nested_quantifiers}")

    if "|" in pattern and pattern.count("|") > 10:
        warnings.append("Many alternations may cause performance issues")

    return warnings


@dataclass
class ValidatedPattern:
    name: str
    pattern: str
    replacement: str
    test_cases: list[tuple[str, str]]
    description: str = ""
    global_replace: bool = False
    flags: int = 0
    _compiled_pattern: Pattern[str] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        try:
            self._get_compiled_pattern()
        except ValueError as e:
            if "Invalid regex pattern" in str(e):
                error_msg = str(e).replace(f"'{self.pattern}'", f"'{self.name}'")
                raise ValueError(error_msg) from e
            raise

        if r"\g < " in self.replacement or r" >" in self.replacement:
            raise ValueError(
                f"Bad replacement syntax in '{self.name}': {self.replacement}. "
                "Use \\g<1> not \\g<1>"  # REGEX OK: educational example
            )

        warnings = validate_pattern_safety(self.pattern)
        if warnings:
            pass

        for input_text, expected in self.test_cases:
            try:
                count = 0 if self.global_replace else 1
                result = self._apply_internal(input_text, count)
                if result != expected:
                    raise ValueError(
                        f"Pattern '{self.name}' failed test case: "
                        f"'{input_text}' -> '{result}' != expected '{expected}'"
                    )
            except re.error as e:
                raise ValueError(f"Pattern '{self.name}' failed on '{input_text}': {e}")

    def _get_compiled_pattern(self) -> Pattern[str]:
        cache_key = f"{self.pattern}|flags: {self.flags}"
        return CompiledPatternCache.get_compiled_pattern_with_flags(
            cache_key, self.pattern, self.flags
        )

    def _apply_internal(self, text: str, count: int = 1) -> str:
        if len(text) > MAX_INPUT_SIZE:
            raise ValueError(
                f"Input text too large: {len(text)} bytes > {MAX_INPUT_SIZE}"
            )

        return self._get_compiled_pattern().sub(self.replacement, text, count=count)

    def apply(self, text: str) -> str:
        count = 0 if self.global_replace else 1
        return self._apply_internal(text, count)

    def apply_iteratively(self, text: str, max_iterations: int = MAX_ITERATIONS) -> str:
        if max_iterations <= 0:
            raise ValueError("max_iterations must be positive")

        result = text
        for _ in range(max_iterations):
            new_result = self.apply(result)
            if new_result == result:
                break
            result = new_result
        else:
            pass

        return result

    def apply_with_timeout(self, text: str, timeout_seconds: float = 1.0) -> str:
        def timeout_handler(signum: int, frame: t.Any) -> None:
            raise TimeoutError(
                f"Pattern '{self.name}' timed out after {timeout_seconds}s"
            )

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout_seconds))

        try:
            result = self.apply(text)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

        return result

    def test(self, text: str) -> bool:
        compiled = self._get_compiled_pattern()
        return bool(compiled.search(text))

    def search(self, text: str) -> re.Match[str] | None:
        if len(text) > MAX_INPUT_SIZE:
            raise ValueError(
                f"Input text too large: {len(text)} bytes > {MAX_INPUT_SIZE}"
            )
        return self._get_compiled_pattern().search(text)

    def findall(self, text: str) -> list[str]:
        if len(text) > MAX_INPUT_SIZE:
            raise ValueError(
                f"Input text too large: {len(text)} bytes > {MAX_INPUT_SIZE}"
            )
        return self._get_compiled_pattern().findall(text)

    def get_performance_stats(
        self, text: str, iterations: int = 100
    ) -> dict[str, float]:
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            self.apply(text)
            end = time.perf_counter()
            times.append(end - start)

        return {
            "mean_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
            "total_time": sum(times),
        }
