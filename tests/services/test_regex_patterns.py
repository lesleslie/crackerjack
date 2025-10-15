"""Tests for the regex patterns module."""

import pytest
import re
from unittest.mock import patch

from crackerjack.services.regex_patterns import (
    CompiledPatternCache,
    ValidatedPattern,
    SAFE_PATTERNS,
    validate_all_patterns,
    find_pattern_for_text,
    apply_safe_replacement,
    get_pattern_description,
    fix_multi_word_hyphenation,
    update_pyproject_version,
    apply_formatting_fixes,
    apply_security_fixes,
    apply_test_fixes,
    is_valid_job_id,
    remove_coverage_fail_under,
    update_coverage_requirement,
    sanitize_internal_urls,
    apply_pattern_iteratively,
    get_all_pattern_stats,
    clear_all_caches,
    get_cache_info,
    validate_path_security,
    MAX_INPUT_SIZE,
    MAX_ITERATIONS,
    PATTERN_CACHE_SIZE
)


class TestCompiledPatternCache:
    """Test the CompiledPatternCache class."""

    @pytest.fixture(autouse=True)
    def clear_cache_before_test(self):
        """Clear the pattern cache before each test to ensure isolation."""
        CompiledPatternCache.clear_cache()
        yield
        # Optionally clear after test as well
        CompiledPatternCache.clear_cache()

    def test_get_compiled_pattern(self) -> None:
        """Test getting a compiled pattern."""
        pattern = r"\d+"
        compiled = CompiledPatternCache.get_compiled_pattern(pattern)
        assert isinstance(compiled, re.Pattern)
        assert compiled.pattern == pattern

    def test_get_compiled_pattern_with_flags(self) -> None:
        """Test getting a compiled pattern with flags."""
        pattern = r"test"
        flags = re.IGNORECASE
        compiled = CompiledPatternCache.get_compiled_pattern_with_flags("test_key", pattern, flags)
        assert isinstance(compiled, re.Pattern)
        assert compiled.pattern == pattern

    def test_get_compiled_pattern_invalid_pattern(self) -> None:
        """Test getting an invalid pattern raises ValueError."""
        with pytest.raises(ValueError, match=r"Invalid regex pattern.*unterminated character set"):
            CompiledPatternCache.get_compiled_pattern_with_flags("test_key", "[invalid", 0)

    def test_clear_cache(self) -> None:
        """Test clearing the cache."""
        # Add a pattern to cache
        CompiledPatternCache.get_compiled_pattern(r"\w+")
        assert len(CompiledPatternCache._cache) > 0

        # Clear cache
        CompiledPatternCache.clear_cache()
        assert len(CompiledPatternCache._cache) == 0

    def test_get_cache_stats(self) -> None:
        """Test getting cache stats."""
        stats = CompiledPatternCache.get_cache_stats()
        assert isinstance(stats, dict)
        assert "size" in stats
        assert "max_size" in stats
        assert "patterns" in stats
        assert stats["max_size"] == PATTERN_CACHE_SIZE


class TestValidatedPattern:
    """Test the ValidatedPattern class."""

    def test_basic_pattern_application(self) -> None:
        """Test basic pattern application."""
        pattern = ValidatedPattern(
            name="test_pattern",
            pattern=r"hello",
            replacement="hi",
            test_cases=[("hello world", "hi world")]
        )
        result = pattern.apply("hello world")
        assert result == "hi world"

    def test_pattern_with_global_replace(self) -> None:
        """Test pattern with global replacement."""
        pattern = ValidatedPattern(
            name="test_global",
            pattern=r"test",
            replacement="replaced",
            test_cases=[("test test test", "replaced replaced replaced")],
            global_replace=True
        )
        result = pattern.apply("test test test")
        assert result == "replaced replaced replaced"

    def test_pattern_with_flags(self) -> None:
        """Test pattern with flags."""
        pattern = ValidatedPattern(
            name="test_flags",
            pattern=r"case",
            replacement="replaced",
            test_cases=[("CaSe", "replaced")],
            flags=re.IGNORECASE
        )
        result = pattern.apply("CaSe")
        assert result == "replaced"

    def test_apply_iteratively(self) -> None:
        """Test applying pattern iteratively."""
        pattern = ValidatedPattern(
            name="test_iterative",
            pattern=r"test",
            replacement="replaced",
            test_cases=[("test test", "replaced replaced")],
            global_replace=True
        )
        result = pattern.apply_iteratively("test test", max_iterations=2)
        assert result == "replaced replaced"

    def test_apply_iteratively_max_iterations(self) -> None:
        """Test applying pattern with max iterations validation."""
        pattern = ValidatedPattern(
            name="test_iterative",
            pattern=r"test",
            replacement="test",
            test_cases=[("test", "test")]
        )
        with pytest.raises(ValueError, match="max_iterations must be positive"):
            pattern.apply_iteratively("test", max_iterations=0)

    def test_search_method(self) -> None:
        """Test the search method."""
        pattern = ValidatedPattern(
            name="test_search",
            pattern=r"world",
            replacement="universe",
            test_cases=[("hello world", "hello universe")]
        )
        match = pattern.search("hello world")
        assert match is not None

    def test_findall_method(self) -> None:
        """Test the findall method."""
        pattern = ValidatedPattern(
            name="test_findall",
            pattern=r"nonexistent_pattern",
            replacement="repl",
            test_cases=[("hello world", "hello world")]  # Pattern won't match anything
        )
        results = pattern.findall("hello world")
        assert len(results) == 0  # No matches found

    def test_test_method(self) -> None:
        """Test the test method."""
        pattern = ValidatedPattern(
            name="test_test",
            pattern=r"hello",
            replacement="hi",
            test_cases=[("hello world", "hi world")]
        )
        result = pattern.test("hello world")
        assert result is True

        result = pattern.test("goodbye world")
        assert result is False

    def test_large_input_size(self) -> None:
        """Test handling of large input sizes."""
        pattern = ValidatedPattern(
            name="test_large",
            pattern=r"test",
            replacement="replaced",
            test_cases=[("test", "replaced")]
        )

        # Test with actual size limitation
        large_text = "a" * (MAX_INPUT_SIZE + 100)
        with pytest.raises(ValueError, match="Input text too large"):
            pattern.apply(large_text)

    def test_invalid_regex_in_constructor(self) -> None:
        """Test invalid regex in constructor raises error."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            ValidatedPattern(
                name="invalid",
                pattern="[invalid",
                replacement="test",
                test_cases=[("test", "test")]
            )

    def test_bad_replacement_syntax(self) -> None:
        """Test bad replacement syntax raises error."""
        with pytest.raises(ValueError, match="Bad replacement syntax"):
            ValidatedPattern(
                name="bad_repl",
                pattern="test",
                replacement=r"\\g < ",  # Bad replacement syntax
                test_cases=[("test", "test")]
            )


class TestSafePatterns:
    """Test the SAFE_PATTERNS dictionary."""

    def test_all_patterns_valid(self) -> None:
        """Test that all patterns in SAFE_PATTERNS are valid."""
        results = validate_all_patterns()
        assert all(results.values()), f"Failed patterns: {[k for k, v in results.items() if not v]}"

    def test_find_pattern_for_text(self) -> None:
        """Test finding patterns for text."""
        results = find_pattern_for_text("python - m crackerjack")
        assert "fix_command_spacing" in results

    def test_apply_safe_replacement(self) -> None:
        """Test applying safe replacement."""
        result = apply_safe_replacement("python - m crackerjack", "fix_command_spacing")
        assert result == "python -m crackerjack"

    def test_apply_safe_replacement_unknown_pattern(self) -> None:
        """Test applying safe replacement with unknown pattern."""
        with pytest.raises(ValueError, match="Unknown pattern"):
            apply_safe_replacement("test", "unknown_pattern")

    def test_get_pattern_description(self) -> None:
        """Test getting pattern description."""
        desc = get_pattern_description("fix_command_spacing")
        assert "Fix spacing in 'python -m command' patterns" in desc

        desc = get_pattern_description("unknown_pattern")
        assert desc == "Unknown pattern"

    def test_fix_multi_word_hyphenation(self) -> None:
        """Test multi-word hyphenation fixes."""
        result = fix_multi_word_hyphenation("pytest - hypothesis - specialist")
        assert "pytest-hypothesis-specialist" in result

    def test_update_pyproject_version(self) -> None:
        """Test updating pyproject version."""
        content = 'version = "1.2.3"'
        result = update_pyproject_version(content, "2.0.0")
        assert 'version = "2.0.0"' in result

    def test_apply_formatting_fixes(self) -> None:
        """Test applying formatting fixes."""
        content = "line with spaces   \n\n\nnormal line\n"
        result = apply_formatting_fixes(content)
        # Should remove trailing whitespace and normalize newlines
        assert not result.endswith("   ")
        assert "\n\n\n" not in result

    def test_apply_security_fixes(self) -> None:
        """Test applying security fixes."""
        content = 'yaml.load(data)\nhashlib.md5(input)\nrandom.choice(options)'
        result = apply_security_fixes(content)
        assert "yaml.safe_load(data)" in result
        assert "hashlib.sha256(input)" in result
        assert "secrets.choice(options)" in result

    def test_apply_test_fixes(self) -> None:
        """Test applying test fixes."""
        content = "assert result==expected"
        result = apply_test_fixes(content)
        assert "assert result == expected" in result

    def test_is_valid_job_id(self) -> None:
        """Test job ID validation."""
        assert is_valid_job_id("valid_job-123") is True
        assert is_valid_job_id("invalid job") is False

    def test_remove_coverage_fail_under(self) -> None:
        """Test removing coverage fail under."""
        content = "--cov-fail-under=85 --verbose"
        result = remove_coverage_fail_under(content)
        assert "--cov-fail-under=85" not in result
        assert "--verbose" in result

    def test_update_coverage_requirement(self) -> None:
        """Test updating coverage requirement."""
        content = "--cov-fail-under=85"
        result = update_coverage_requirement(content, 90.0)
        assert "90" in result

    def test_sanitize_internal_urls(self) -> None:
        """Test sanitizing internal URLs."""
        # Test with a pattern that should match one of the sanitize patterns
        # Using the exact format from the test cases in regex_patterns.py
        content = "http: //localhost: 8000/api http: //127.0.0.1: 3000/admin"
        result = sanitize_internal_urls(content)
        # Check that at least one URL has been replaced
        assert "[INTERNAL_URL]" in result

    def test_apply_pattern_iteratively(self) -> None:
        """Test applying pattern iteratively."""
        result = apply_pattern_iteratively("a b c", "fix_spaced_hyphens", max_iterations=2)
        assert isinstance(result, str)

    def test_apply_pattern_iteratively_unknown_pattern(self) -> None:
        """Test applying pattern iteratively with unknown pattern."""
        with pytest.raises(ValueError, match="Unknown pattern"):
            apply_pattern_iteratively("test", "unknown_pattern")

    def test_get_all_pattern_stats(self) -> None:
        """Test getting all pattern stats."""
        with patch("crackerjack.services.regex_patterns.MAX_ITERATIONS", 1):
            stats = get_all_pattern_stats()
            assert isinstance(stats, dict)
            assert len(stats) > 0

    def test_clear_all_caches(self) -> None:
        """Test clearing all caches."""
        # Add something to the cache
        CompiledPatternCache.get_compiled_pattern(r"\w+")
        assert len(CompiledPatternCache._cache) > 0

        # Clear all caches
        clear_all_caches()
        assert len(CompiledPatternCache._cache) == 0

    def test_get_cache_info(self) -> None:
        """Test getting cache info."""
        info = get_cache_info()
        assert isinstance(info, dict)
        assert "size" in info
        assert "max_size" in info
        assert len(CompiledPatternCache._cache) == info["size"]

    def test_validate_path_security(self) -> None:
        """Test path security validation."""
        result = validate_path_security("../../etc/passwd")
        assert isinstance(result, dict)
        assert "traversal_patterns" in result
        assert "null_bytes" in result
        assert "dangerous_directories" in result
        assert "suspicious_patterns" in result
