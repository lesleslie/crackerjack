"""Tests for ``crackerjack.managers.constants``.

The constants module is a pure-data module — every name is a module-level
constant used by runtime config. These tests verify each constant exists,
has the expected type, and falls within plausible bounds.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def constants_module() -> object:
    return importlib.import_module("crackerjack.managers.constants")


def test_constants_module_exports_expected_names(constants_module: object) -> None:
    expected = {
        "TIMEOUT_THRESHOLD_MULTIPLIER",
        "MAX_TEST_DURATION_WARNING",
        "MAX_TEST_FAILURES_TO_DISPLAY",
        "MAX_TEST_ERRORS_TO_DISPLAY",
        "DEFAULT_PARALLEL_TESTS",
        "MIN_PARALLEL_THRESHOLD",
        "PROGRESS_UPDATE_PERCENTAGE",
        "MAX_AI_FIX_ITERATIONS",
        "MIN_AI_CONFIDENCE_THRESHOLD",
        "SLOW_HOOK_THRESHOLD",
        "VERY_SLOW_HOOK_THRESHOLD",
        "DEFAULT_PYPI_TIMEOUT",
        "DEFAULT_GITHUB_TIMEOUT",
        "PATTERN_CACHE_TTL",
        "INDEX_CACHE_TTL",
        "MAX_WATCHED_FILES",
        "DEBOUNCE_INTERVAL",
        "MAX_CONCURRENT_WORKERS",
        "TASK_DISPATCH_TIMEOUT",
        "DEFAULT_PANEL_WIDTH",
        "DEFAULT_COLUMN_WIDTH",
    }
    missing = expected - set(dir(constants_module))
    assert not missing, f"missing constants: {sorted(missing)}"


def test_timeout_threshold_multiplier_is_fraction(constants_module: object) -> None:
    """The timeout threshold should be a fraction in (0, 1]."""
    value = constants_module.TIMEOUT_THRESHOLD_MULTIPLIER
    assert isinstance(value, float)
    assert 0 < value <= 1


def test_parallel_bounds_are_sane(constants_module: object) -> None:
    """The ``DEFAULT`` parallel worker count must not exceed the absolute MAX.

    Note: ``MIN_PARALLEL_THRESHOLD`` is a test-count gate (only parallelize
    when total tests exceed this threshold), not a worker floor — so it can
    legitimately exceed ``DEFAULT_PARALLEL_TESTS``.
    """
    assert (
        constants_module.DEFAULT_PARALLEL_TESTS
        <= constants_module.MAX_CONCURRENT_WORKERS
    )
    assert constants_module.MIN_PARALLEL_THRESHOLD > 0


def test_ai_confidence_threshold_is_unit_interval(constants_module: object) -> None:
    value = constants_module.MIN_AI_CONFIDENCE_THRESHOLD
    assert isinstance(value, float)
    assert 0 < value <= 1


def test_hook_thresholds_ordered(constants_module: object) -> None:
    """``SLOW_HOOK_THRESHOLD`` < ``VERY_SLOW_HOOK_THRESHOLD``."""
    assert (
        constants_module.SLOW_HOOK_THRESHOLD
        < constants_module.VERY_SLOW_HOOK_THRESHOLD
    )


def test_panel_width_is_positive(constants_module: object) -> None:
    assert constants_module.DEFAULT_PANEL_WIDTH > 0
    assert constants_module.DEFAULT_COLUMN_WIDTH > 0


def test_ttls_are_positive_integers(constants_module: object) -> None:
    """TTL constants (seconds) should be positive ints."""
    for name in ("PATTERN_CACHE_TTL", "INDEX_CACHE_TTL"):
        assert getattr(constants_module, name) > 0


def test_timeouts_are_positive(constants_module: object) -> None:
    """Network/IO timeouts should be positive numbers (int or float)."""
    assert constants_module.DEFAULT_PYPI_TIMEOUT > 0
    assert constants_module.DEFAULT_GITHUB_TIMEOUT > 0
