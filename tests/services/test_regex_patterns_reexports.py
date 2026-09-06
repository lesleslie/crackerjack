"""Tests for ``crackerjack.services.regex_patterns``.

Covers the re-export shim that surfaces ``crackerjack.services.patterns``
public API under a stable module path.
"""

from __future__ import annotations

import pytest

from crackerjack.services import regex_patterns
from crackerjack.services.patterns import (
    CompiledPatternCache,
    RegexPatternsService,
    ValidatedPattern,
)


def test_regex_patterns_module_has_all_attribute() -> None:
    assert isinstance(regex_patterns.__all__, list)
    assert len(regex_patterns.__all__) > 0


def test_regex_patterns_module_exposes_all_names() -> None:
    """Every name in ``__all__`` is accessible as a module attribute."""
    missing = [n for n in regex_patterns.__all__ if not hasattr(regex_patterns, n)]
    assert not missing, f"missing names: {missing}"


def test_regex_patterns_module_exposes_canonical_classes() -> None:
    """The most-used public classes resolve to the originals."""
    assert regex_patterns.RegexPatternsService is RegexPatternsService
    assert regex_patterns.CompiledPatternCache is CompiledPatternCache
    assert regex_patterns.ValidatedPattern is ValidatedPattern


def test_regex_patterns_module_exposes_constants() -> None:
    """The module-level limits are also re-exported."""
    for name in ("MAX_INPUT_SIZE", "MAX_ITERATIONS", "PATTERN_CACHE_SIZE"):
        assert hasattr(regex_patterns, name), name
        assert isinstance(getattr(regex_patterns, name), int)
        assert getattr(regex_patterns, name) > 0


def test_regex_patterns_module_exposes_helper_functions() -> None:
    """Common helper functions resolve via the re-export module."""
    for name in (
        "validate_pattern_safety",
        "validate_all_patterns",
        "clear_all_caches",
        "get_cache_info",
        "is_valid_job_id",
    ):
        assert callable(getattr(regex_patterns, name)), name
