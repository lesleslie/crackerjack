from __future__ import annotations

from typing import Final

import pytest

from crackerjack.managers import constants


pytestmark = pytest.mark.unit


class TestTimeoutConstants:
    """Verify timeout-related constants have expected types and values."""

    def test_timeout_threshold_multiplier_is_float_in_unit_range(self) -> None:
        assert isinstance(constants.TIMEOUT_THRESHOLD_MULTIPLIER, float)
        assert 0.0 < constants.TIMEOUT_THRESHOLD_MULTIPLIER <= 1.0

    def test_max_test_duration_warning_is_positive_float(self) -> None:
        assert isinstance(constants.MAX_TEST_DURATION_WARNING, float)
        assert constants.MAX_TEST_DURATION_WARNING > 0.0


class TestTestDisplayLimits:
    """Verify test display/result limits are sensible positive integers."""

    def test_max_test_failures_to_display_is_positive_int(self) -> None:
        assert isinstance(constants.MAX_TEST_FAILURES_TO_DISPLAY, int)
        assert constants.MAX_TEST_FAILURES_TO_DISPLAY > 0
        assert not isinstance(constants.MAX_TEST_FAILURES_TO_DISPLAY, bool)

    def test_max_test_errors_to_display_is_positive_int(self) -> None:
        assert isinstance(constants.MAX_TEST_ERRORS_TO_DISPLAY, int)
        assert constants.MAX_TEST_ERRORS_TO_DISPLAY > 0
        assert not isinstance(constants.MAX_TEST_ERRORS_TO_DISPLAY, bool)

    def test_max_test_errors_exceeds_max_test_failures(self) -> None:
        # Errors typically need at least as much headroom as failures
        assert (
            constants.MAX_TEST_ERRORS_TO_DISPLAY
            >= constants.MAX_TEST_FAILURES_TO_DISPLAY
        )


class TestParallelExecutionThresholds:
    """Verify parallel test execution thresholds are sane integers."""

    def test_default_parallel_tests_is_positive_int(self) -> None:
        assert isinstance(constants.DEFAULT_PARALLEL_TESTS, int)
        assert constants.DEFAULT_PARALLEL_TESTS > 0

    def test_min_parallel_threshold_is_positive_int(self) -> None:
        assert isinstance(constants.MIN_PARALLEL_THRESHOLD, int)
        assert constants.MIN_PARALLEL_THRESHOLD > 0

    def test_min_parallel_threshold_at_least_default(self) -> None:
        # It only makes sense to parallelize once the workload crosses the default
        assert (
            constants.MIN_PARALLEL_THRESHOLD
            >= constants.DEFAULT_PARALLEL_TESTS
        )


class TestProgressUpdateConstant:
    def test_progress_update_percentage_is_positive_int(self) -> None:
        assert isinstance(constants.PROGRESS_UPDATE_PERCENTAGE, int)
        assert 0 < constants.PROGRESS_UPDATE_PERCENTAGE <= 100


class TestAIFixConstants:
    def test_max_ai_fix_iterations_is_positive_int(self) -> None:
        assert isinstance(constants.MAX_AI_FIX_ITERATIONS, int)
        assert constants.MAX_AI_FIX_ITERATIONS > 0

    def test_min_ai_confidence_threshold_is_unit_float(self) -> None:
        assert isinstance(constants.MIN_AI_CONFIDENCE_THRESHOLD, float)
        assert 0.0 < constants.MIN_AI_CONFIDENCE_THRESHOLD <= 1.0


class TestHookThresholds:
    def test_slow_hook_threshold_is_positive_float(self) -> None:
        assert isinstance(constants.SLOW_HOOK_THRESHOLD, float)
        assert constants.SLOW_HOOK_THRESHOLD > 0.0

    def test_very_slow_hook_threshold_exceeds_slow_threshold(self) -> None:
        assert isinstance(constants.VERY_SLOW_HOOK_THRESHOLD, float)
        assert (
            constants.VERY_SLOW_HOOK_THRESHOLD
            > constants.SLOW_HOOK_THRESHOLD
        )


class TestNetworkTimeouts:
    def test_default_pypi_timeout_is_positive_int(self) -> None:
        assert isinstance(constants.DEFAULT_PYPI_TIMEOUT, int)
        assert constants.DEFAULT_PYPI_TIMEOUT > 0

    def test_default_github_timeout_is_positive_int(self) -> None:
        assert isinstance(constants.DEFAULT_GITHUB_TIMEOUT, int)
        assert constants.DEFAULT_GITHUB_TIMEOUT > 0


class TestCacheTTLs:
    def test_pattern_cache_ttl_is_positive_int(self) -> None:
        assert isinstance(constants.PATTERN_CACHE_TTL, int)
        assert constants.PATTERN_CACHE_TTL > 0

    def test_index_cache_ttl_is_positive_int(self) -> None:
        assert isinstance(constants.INDEX_CACHE_TTL, int)
        assert constants.INDEX_CACHE_TTL > 0

    def test_index_cache_ttl_at_least_pattern_cache_ttl(self) -> None:
        # Index caches are typically longer-lived than pattern caches
        assert constants.INDEX_CACHE_TTL >= constants.PATTERN_CACHE_TTL


class TestFileWatcherConstants:
    def test_max_watched_files_is_positive_int(self) -> None:
        assert isinstance(constants.MAX_WATCHED_FILES, int)
        assert constants.MAX_WATCHED_FILES > 0

    def test_debounce_interval_is_non_negative_float(self) -> None:
        assert isinstance(constants.DEBOUNCE_INTERVAL, float)
        assert constants.DEBOUNCE_INTERVAL >= 0.0


class TestWorkerPoolConstants:
    def test_max_concurrent_workers_is_positive_int(self) -> None:
        assert isinstance(constants.MAX_CONCURRENT_WORKERS, int)
        assert constants.MAX_CONCURRENT_WORKERS > 0

    def test_task_dispatch_timeout_is_positive_float(self) -> None:
        assert isinstance(constants.TASK_DISPATCH_TIMEOUT, float)
        assert constants.TASK_DISPATCH_TIMEOUT > 0.0


class TestDisplayConstants:
    def test_default_panel_width_is_positive_int(self) -> None:
        assert isinstance(constants.DEFAULT_PANEL_WIDTH, int)
        assert constants.DEFAULT_PANEL_WIDTH > 0

    def test_default_column_width_is_positive_int(self) -> None:
        assert isinstance(constants.DEFAULT_COLUMN_WIDTH, int)
        assert constants.DEFAULT_COLUMN_WIDTH > 0

    def test_default_column_width_exceeds_panel_width(self) -> None:
        # A column is rendered within a panel, so the column should be
        # at least as wide as the panel.
        assert (
            constants.DEFAULT_COLUMN_WIDTH
            >= constants.DEFAULT_PANEL_WIDTH
        )


def test_module_has_no_callables() -> None:
    """The constants module should be pure data — no functions or classes."""
    callables: Final[tuple[str, ...]] = tuple(
        name
        for name in dir(constants)
        if not name.startswith("_")
        and callable(getattr(constants, name))
    )
    assert callables == ()


def test_all_module_attributes_are_public() -> None:
    """Every attribute should be a public constant (UPPER_SNAKE_CASE)."""
    public_attrs: Final[tuple[str, ...]] = tuple(
        name for name in dir(constants) if not name.startswith("_")
    )
    for attr in public_attrs:
        assert attr.isupper(), f"{attr!r} should be UPPER_SNAKE_CASE"
        assert attr.replace("_", "").isalnum(), (
            f"{attr!r} should only contain alphanumerics and underscores"
        )
