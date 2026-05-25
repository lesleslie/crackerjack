"""Tests for defaults module."""

from pathlib import Path

import pytest

from crackerjack.core import defaults


class TestDefaultConstants:
    """Tests for default constant values."""

    def test_default_coverage_threshold(self) -> None:
        """Test DEFAULT_COVERAGE_THRESHOLD value."""
        assert defaults.DEFAULT_COVERAGE_THRESHOLD == 80

    def test_default_complexity_threshold(self) -> None:
        """Test DEFAULT_COMPLEXITY_THRESHOLD value."""
        assert defaults.DEFAULT_COMPLEXITY_THRESHOLD == 15

    def test_default_max_function_length(self) -> None:
        """Test DEFAULT_MAX_FUNCTION_LENGTH value."""
        assert defaults.DEFAULT_MAX_FUNCTION_LENGTH == 50

    def test_default_test_timeout(self) -> None:
        """Test DEFAULT_TEST_TIMEOUT value."""
        assert defaults.DEFAULT_TEST_TIMEOUT == 300

    def test_default_command_timeout(self) -> None:
        """Test DEFAULT_COMMAND_TIMEOUT value."""
        assert defaults.DEFAULT_COMMAND_TIMEOUT == 600

    def test_default_parallel_execution(self) -> None:
        """Test DEFAULT_PARALLEL_EXECUTION value."""
        assert defaults.DEFAULT_PARALLEL_EXECUTION is True

    def test_default_auto_detect_workers(self) -> None:
        """Test DEFAULT_AUTO_DETECT_WORKERS value."""
        assert defaults.DEFAULT_AUTO_DETECT_WORKERS is True

    def test_default_max_workers(self) -> None:
        """Test DEFAULT_MAX_WORKERS value."""
        assert defaults.DEFAULT_MAX_WORKERS == 8

    def test_default_min_workers(self) -> None:
        """Test DEFAULT_MIN_WORKERS value."""
        assert defaults.DEFAULT_MIN_WORKERS == 2

    def test_default_ruff_select(self) -> None:
        """Test DEFAULT_RUFF_SELECT is a list with expected values."""
        expected = ["E", "W", "F", "I", "N", "UP", "B", "C4", "SIM", "RUF"]
        assert defaults.DEFAULT_RUFF_SELECT == expected

    def test_default_ruff_ignore(self) -> None:
        """Test DEFAULT_RUFF_IGNORE is a list with expected values."""
        expected = ["E502"]
        assert defaults.DEFAULT_RUFF_IGNORE == expected

    def test_default_enable_coverage(self) -> None:
        """Test DEFAULT_ENABLE_COVERAGE value."""
        assert defaults.DEFAULT_ENABLE_COVERAGE is True

    def test_default_coverage_reports(self) -> None:
        """Test DEFAULT_COVERAGE_REPORTS is a list with expected values."""
        expected = ["term", "html"]
        assert defaults.DEFAULT_COVERAGE_REPORTS == expected

    def test_default_enable_security(self) -> None:
        """Test DEFAULT_ENABLE_SECURITY value."""
        assert defaults.DEFAULT_ENABLE_SECURITY is True

    def test_default_security_tools(self) -> None:
        """Test DEFAULT_SECURITY_TOOLS is a list with expected values."""
        expected = ["bandit", "safety"]
        assert defaults.DEFAULT_SECURITY_TOOLS == expected

    def test_default_project_root(self) -> None:
        """Test DEFAULT_PROJECT_ROOT is Path.cwd()."""
        assert defaults.DEFAULT_PROJECT_ROOT == Path.cwd()

    def test_default_package_name(self) -> None:
        """Test DEFAULT_PACKAGE_NAME is None."""
        assert defaults.DEFAULT_PACKAGE_NAME is None

    def test_default_exclude_dirs(self) -> None:
        """Test DEFAULT_EXCLUDE_DIRS contains expected patterns."""
        expected = [
            ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
            ".ruff_cache", ".mypy_cache", "htmlcov", "build", "dist", "*.egg-info",
        ]
        assert defaults.DEFAULT_EXCLUDE_DIRS == expected

    def test_default_output_format(self) -> None:
        """Test DEFAULT_OUTPUT_FORMAT value."""
        assert defaults.DEFAULT_OUTPUT_FORMAT == "console"

    def test_default_verbose(self) -> None:
        """Test DEFAULT_VERBOSE value."""
        assert defaults.DEFAULT_VERBOSE is False

    def test_default_show_progress(self) -> None:
        """Test DEFAULT_SHOW_PROGRESS value."""
        assert defaults.DEFAULT_SHOW_PROGRESS is True

    def test_default_color_output(self) -> None:
        """Test DEFAULT_COLOR_OUTPUT value."""
        assert defaults.DEFAULT_COLOR_OUTPUT is True

    def test_default_fail_on_test_errors(self) -> None:
        """Test DEFAULT_FAIL_ON_TEST_ERRORS value."""
        assert defaults.DEFAULT_FAIL_ON_TEST_ERRORS is True

    def test_default_fail_on_coverage(self) -> None:
        """Test DEFAULT_FAIL_ON_COVERAGE value."""
        assert defaults.DEFAULT_FAIL_ON_COVERAGE is True

    def test_default_fail_on_complexity(self) -> None:
        """Test DEFAULT_FAIL_ON_COMPLEXITY value."""
        assert defaults.DEFAULT_FAIL_ON_COMPLEXITY is True

    def test_default_fail_on_security(self) -> None:
        """Test DEFAULT_FAIL_ON_SECURITY value."""
        assert defaults.DEFAULT_FAIL_ON_SECURITY is True

    def test_default_enable_caching(self) -> None:
        """Test DEFAULT_ENABLE_CACHING value."""
        assert defaults.DEFAULT_ENABLE_CACHING is True

    def test_default_cache_ttl(self) -> None:
        """Test DEFAULT_CACHE_TTL value."""
        assert defaults.DEFAULT_CACHE_TTL == 3600

    def test_default_cache_max_entries(self) -> None:
        """Test DEFAULT_CACHE_MAX_ENTRIES value."""
        assert defaults.DEFAULT_CACHE_MAX_ENTRIES == 1000

    def test_default_ai_fix_enabled(self) -> None:
        """Test DEFAULT_AI_FIX_ENABLED value."""
        assert defaults.DEFAULT_AI_FIX_ENABLED is False

    def test_default_ai_provider(self) -> None:
        """Test DEFAULT_AI_PROVIDER value."""
        assert defaults.DEFAULT_AI_PROVIDER == "claude"

    def test_default_ai_max_iterations(self) -> None:
        """Test DEFAULT_AI_MAX_ITERATIONS value."""
        assert defaults.DEFAULT_AI_MAX_ITERATIONS == 5

    def test_default_docs_cleanup_enabled(self) -> None:
        """Test DEFAULT_DOCS_CLEANUP_ENABLED value."""
        assert defaults.DEFAULT_DOCS_CLEANUP_ENABLED is True

    def test_default_docs_backup_before_cleanup(self) -> None:
        """Test DEFAULT_DOCS_BACKUP_BEFORE_CLEANUP value."""
        assert defaults.DEFAULT_DOCS_BACKUP_BEFORE_CLEANUP is True

    def test_default_git_commit(self) -> None:
        """Test DEFAULT_GIT_COMMIT value."""
        assert defaults.DEFAULT_GIT_COMMIT is False

    def test_default_git_create_pr(self) -> None:
        """Test DEFAULT_GIT_CREATE_PR value."""
        assert defaults.DEFAULT_GIT_CREATE_PR is False

    def test_default_update_precommit(self) -> None:
        """Test DEFAULT_UPDATE_PRECOMMIT value."""
        assert defaults.DEFAULT_UPDATE_PRECOMMIT is False


class TestGetAllDefaults:
    """Tests for get_all_defaults function."""

    def test_returns_dict(self) -> None:
        """Test get_all_defaults returns a dictionary."""
        result = defaults.get_all_defaults()
        assert isinstance(result, dict)

    def test_keys_start_with_default_prefix(self) -> None:
        """Test all keys start with DEFAULT_."""
        result = defaults.get_all_defaults()
        for key in result:
            assert key.startswith("DEFAULT_")

    def test_contains_expected_keys(self) -> None:
        """Test result contains expected default keys."""
        result = defaults.get_all_defaults()
        expected_keys = [
            "DEFAULT_COVERAGE_THRESHOLD",
            "DEFAULT_COMPLEXITY_THRESHOLD",
            "DEFAULT_MAX_WORKERS",
            "DEFAULT_MIN_WORKERS",
            "DEFAULT_RUFF_SELECT",
            "DEFAULT_ENABLE_COVERAGE",
        ]
        for key in expected_keys:
            assert key in result

    def test_does_not_include_non_default_values(self) -> None:
        """Test that get_all_defaults doesn't include functions or modules."""
        result = defaults.get_all_defaults()
        for value in result.values():
            assert not callable(value)
            assert not hasattr(value, "__name__")  # modules have __name__


class TestGetDefault:
    """Tests for get_default function."""

    def test_get_existing_default(self) -> None:
        """Test getting an existing default value."""
        result = defaults.get_default("COVERAGE_THRESHOLD")
        assert result == 80

    def test_get_default_with_prefix(self) -> None:
        """Test getting a default with DEFAULT_ prefix."""
        result = defaults.get_default("DEFAULT_COVERAGE_THRESHOLD")
        assert result == 80

    def test_get_default_complexity_threshold(self) -> None:
        """Test getting COMPLEXITY_THRESHOLD."""
        result = defaults.get_default("COMPLEXITY_THRESHOLD")
        assert result == 15

    def test_get_default_ruff_select(self) -> None:
        """Test getting RUFF_SELECT."""
        result = defaults.get_default("RUFF_SELECT")
        assert result == ["E", "W", "F", "I", "N", "UP", "B", "C4", "SIM", "RUF"]

    def test_get_default_exclude_dirs(self) -> None:
        """Test getting EXCLUDE_DIRS."""
        result = defaults.get_default("EXCLUDE_DIRS")
        expected = [".git", ".venv", "venv", "__pycache__", ".pytest_cache",
                   ".ruff_cache", ".mypy_cache", "htmlcov", "build", "dist", "*.egg-info"]
        assert result == expected

    def test_get_nonexistent_default_raises(self) -> None:
        """Test getting a non-existent default raises AttributeError."""
        with pytest.raises(AttributeError, match="Default 'DEFAULT_NONEXISTENT' does not exist"):
            defaults.get_default("NONEXISTENT")

    def test_get_default_case_sensitive(self) -> None:
        """Test get_default is case sensitive."""
        with pytest.raises(AttributeError):
            defaults.get_default("coverage_threshold")  # lowercase


class TestAllList:
    """Tests for __all__ export list."""

    def test_all_list_exists(self) -> None:
        """Test __all__ is defined."""
        assert hasattr(defaults, "__all__")
        assert isinstance(defaults.__all__, list)

    def test_all_list_contains_expected_items(self) -> None:
        """Test __all__ contains expected items."""
        expected_in_all = [
            "DEFAULT_COVERAGE_THRESHOLD",
            "DEFAULT_COMPLEXITY_THRESHOLD",
            "DEFAULT_MAX_WORKERS",
            "get_all_defaults",
            "get_default",
        ]
        for item in expected_in_all:
            assert item in defaults.__all__

    def test_all_list_length(self) -> None:
        """Test __all__ has reasonable number of items."""
        assert len(defaults.__all__) > 20