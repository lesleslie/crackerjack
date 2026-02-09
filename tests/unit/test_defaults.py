"""
Unit tests for Crackerjack defaults module.

Tests verify that default values are properly defined and accessible.
"""

import pytest

from crackerjack.core.defaults import (
    get_all_defaults,
    get_default,
    DEFAULT_COVERAGE_THRESHOLD,
    DEFAULT_COMPLEXITY_THRESHOLD,
    DEFAULT_TEST_TIMEOUT,
    DEFAULT_COMMAND_TIMEOUT,
    DEFAULT_PARALLEL_EXECUTION,
    DEFAULT_RUFF_SELECT,
    DEFAULT_ENABLE_COVERAGE,
)


class TestDefaults:
    """Test default values."""

    def test_coverage_threshold_default(self):
        """Test coverage threshold default is 80%."""
        assert DEFAULT_COVERAGE_THRESHOLD == 80

    def test_complexity_threshold_default(self):
        """Test complexity threshold default is 15."""
        assert DEFAULT_COMPLEXITY_THRESHOLD == 15

    def test_test_timeout_default(self):
        """Test test timeout default is 300 seconds (5 minutes)."""
        assert DEFAULT_TEST_TIMEOUT == 300

    def test_command_timeout_default(self):
        """Test command timeout default is 600 seconds (10 minutes)."""
        assert DEFAULT_COMMAND_TIMEOUT == 600

    def test_parallel_execution_default(self):
        """Test parallel execution is enabled by default."""
        assert DEFAULT_PARALLEL_EXECUTION is True

    def test_ruff_select_default(self):
        """Test Ruff select includes essential rules."""
        assert "E" in DEFAULT_RUFF_SELECT  # pycodestyle errors
        assert "F" in DEFAULT_RUFF_SELECT  # Pyflakes
        assert "I" in DEFAULT_RUFF_SELECT  # isort
        assert "B" in DEFAULT_RUFF_SELECT  # flake8-bugbear

    def test_enable_coverage_default(self):
        """Test coverage is enabled by default."""
        assert DEFAULT_ENABLE_COVERAGE is True


class TestDefaultAccessors:
    """Test default accessor functions."""

    def test_get_all_defaults(self):
        """Test get_all_defaults returns a dictionary."""
        defaults = get_all_defaults()
        assert isinstance(defaults, dict)
        assert len(defaults) > 0
        assert "DEFAULT_COVERAGE_THRESHOLD" in defaults

    def test_get_all_defaults_values(self):
        """Test get_all_defaults returns correct values."""
        defaults = get_all_defaults()
        assert defaults["DEFAULT_COVERAGE_THRESHOLD"] == 80
        assert defaults["DEFAULT_COMPLEXITY_THRESHOLD"] == 15

    def test_get_default_with_prefix(self):
        """Test get_default with DEFAULT_ prefix."""
        value = get_default("DEFAULT_COVERAGE_THRESHOLD")
        assert value == 80

    def test_get_default_without_prefix(self):
        """Test get_default without DEFAULT_ prefix."""
        value = get_default("COVERAGE_THRESHOLD")
        assert value == 80

    def test_get_default_invalid(self):
        """Test get_default raises AttributeError for invalid default."""
        with pytest.raises(AttributeError):
            get_default("INVALID_DEFAULT")


class TestDefaultRationale:
    """Test that defaults follow best practices."""

    def test_coverage_threshold_is_reasonable(self):
        """Test coverage threshold is industry standard."""
        assert 70 <= DEFAULT_COVERAGE_THRESHOLD <= 90

    def test_complexity_threshold_is_reasonable(self):
        """Test complexity threshold follows McCabe's recommendations."""
        assert 10 <= DEFAULT_COMPLEXITY_THRESHOLD <= 20

    def test_timeout_values_are_reasonable(self):
        """Test timeouts are reasonable for CI/CD."""
        assert 60 <= DEFAULT_TEST_TIMEOUT <= 1800  # 1 min to 30 min
        assert 60 <= DEFAULT_COMMAND_TIMEOUT <= 3600  # 1 min to 1 hour

    def test_parallel_execution_enabled(self):
        """Test parallel execution is enabled for modern hardware."""
        assert DEFAULT_PARALLEL_EXECUTION is True

    def test_coverage_enabled_by_default(self):
        """Test coverage tracking is enabled for quality assurance."""
        assert DEFAULT_ENABLE_COVERAGE is True
