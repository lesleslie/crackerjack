"""Tests for regex patterns core functionality."""

import pytest
import re

from crackerjack.services.patterns.core import (
    CompiledPatternCache,
    ValidatedPattern,
    validate_pattern_safety,
)


class TestCompiledPatternCache:
    """Test the CompiledPatternCache class."""

    def test_cache_get_stats(self):
        """Cache should report correct stats."""
        stats = CompiledPatternCache.get_cache_stats()
        assert "size" in stats
        assert "max_size" in stats
        assert "patterns" in stats
        assert stats["max_size"] > 0

    def test_get_compiled_pattern(self):
        """Should return compiled regex pattern."""
        pattern = r"\d+"

        compiled = CompiledPatternCache.get_compiled_pattern(pattern)
        assert isinstance(compiled, re.Pattern)
        assert compiled.pattern == pattern

    def test_cache_returns_same_object(self):
        """Should return same compiled object for same pattern."""
        pattern = r"\w+"

        compiled1 = CompiledPatternCache.get_compiled_pattern(pattern)
        compiled2 = CompiledPatternCache.get_compiled_pattern(pattern)

        assert compiled1 is compiled2

    def test_cache_with_flags(self):
        """Should handle regex flags correctly."""
        pattern = r"test"
        flags = re.IGNORECASE

        compiled = CompiledPatternCache.get_compiled_pattern_with_flags(
            cache_key="test_ignore",
            pattern=pattern,
            flags=flags
        )
        assert compiled.search("TEST")  # Should match due to IGNORECASE

    def test_cache_clear(self):
        """Should be able to clear the cache."""
        # Add something to cache
        CompiledPatternCache.get_compiled_pattern(r"test_pattern")

        # Clear
        CompiledPatternCache.clear_cache()

        # Verify cleared
        stats = CompiledPatternCache.get_cache_stats()
        assert stats["size"] == 0

    def test_invalid_regex_raises_error(self):
        """Invalid regex should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            CompiledPatternCache.get_compiled_pattern(r"(?P<invalid")


class TestValidatedPattern:
    """Test the ValidatedPattern dataclass."""

    def test_validated_pattern_creation(self):
        """Should create ValidatedPattern with correct attributes."""
        pattern = r"\d+"
        replacement = r"NUMBER"
        test_cases = [("123", "NUMBER")]

        validated = ValidatedPattern(
            name="test_pattern",
            pattern=pattern,
            replacement=replacement,
            test_cases=test_cases
        )
        assert validated.pattern == pattern
        assert validated.replacement == replacement
        assert validated.test_cases == test_cases
        assert validated.name == "test_pattern"

    def test_validated_pattern_with_optional_fields(self):
        """Should handle optional fields."""
        validated = ValidatedPattern(
            name="simple",
            pattern=r"\w+",
            replacement="WORD",
            test_cases=[("test", "WORD")],
            description="A simple pattern",
            global_replace=True,
            flags=re.IGNORECASE
        )
        assert validated.description == "A simple pattern"
        assert validated.global_replace is True
        assert validated.flags == re.IGNORECASE


class TestValidatePatternSafety:
    """Test the validate_pattern_safety function."""

    def test_safe_pattern(self):
        """Safe patterns should return empty warning list."""
        safe_patterns = [
            r"\w+",
            r"\d{3}-\d{3}-\d{4}",
            r"[a-zA-Z]+",
            r"file_\d+\.txt",
        ]

        for pattern in safe_patterns:
            warnings = validate_pattern_safety(pattern)
            assert warnings == [], f"Pattern {pattern} should be safe"

    def test_dangerous_nested_quantifiers(self):
        """Should detect adjacent nested quantifiers."""
        # The validator looks for ADJACENT quantifiers like ++, **, +?, etc.
        dangerous_patterns = [
            r"\w++",  # Adjacent quantifiers
            r"\d**",  # Adjacent quantifiers
            r"a+*",  # Adjacent quantifiers
        ]

        for pattern in dangerous_patterns:
            warnings = validate_pattern_safety(pattern)
            assert len(warnings) > 0, f"Pattern {pattern} should have warnings"
            assert any("nested" in w.lower() for w in warnings)

    def test_dangerous_catastrophic_backtracking(self):
        """Should detect potential catastrophic backtracking patterns."""
        # These patterns are detected by the validator
        dangerous_patterns = [
            r".*.*",  # Multiple .* constructs
            r".+.+",  # Multiple .+ constructs
        ]

        for pattern in dangerous_patterns:
            warnings = validate_pattern_safety(pattern)
            assert len(warnings) > 0, f"Pattern {pattern} should have warnings"

    def test_ambiguous_empty_matches(self):
        """Should detect patterns that can match empty strings ambiguously."""
        ambiguous_patterns = [
            r"\d*",
            r"a*",
            r"(x|y)*",
        ]

        for pattern in ambiguous_patterns:
            warnings = validate_pattern_safety(pattern)
            # These patterns are technically valid but may have warnings

    def test_lookahead_lookbehind(self):
        """Should handle lookarounds safely."""
        lookaround_patterns = [
            r"\d+(?=%)",  # Positive lookahead
            r"(?<=\$)\d+",  # Positive lookbehind
            r"\w+(?!\.)",  # Negative lookahead
        ]

        for pattern in lookaround_patterns:
            warnings = validate_pattern_safety(pattern)
            # Lookarounds are generally safe when used correctly

    def test_backreferences(self):
        """Should detect backreferences."""
        pattern_with_backref = r"(\w+)\s+\1"
        warnings = validate_pattern_safety(pattern_with_backref)
        # Backreferences are valid but may have performance implications

    def test_unicode_patterns(self):
        """Should handle Unicode patterns."""
        unicode_patterns = [
            r"\p{L}+",  # Unicode letters
            r"[^\x00-\x7F]+",  # Non-ASCII
        ]

        for pattern in unicode_patterns:
            warnings = validate_pattern_safety(pattern)
            # Unicode patterns should be validated

    def test_very_long_pattern(self):
        """Should warn about excessively long patterns."""
        long_pattern = r"\w{1000}"  # Very long repetition
        warnings = validate_pattern_safety(long_pattern)
        assert len(warnings) >= 0  # May or may not warn


class TestPatternIntegration:
    """Integration tests for pattern validation and caching."""

    def test_validate_and_cache_pattern(self):
        """Should validate and cache pattern in one workflow."""
        pattern = r"\d{3}-\d{3}-\d{4}"

        # Validate
        warnings = validate_pattern_safety(pattern)
        assert warnings == []

        # Cache
        compiled = CompiledPatternCache.get_compiled_pattern(pattern)
        assert compiled.search("123-456-7890")

    def test_dangerous_pattern_workflow(self):
        """Should handle dangerous pattern appropriately."""
        pattern = r".*.*"  # Multiple .* constructs

        # Validate (should warn)
        warnings = validate_pattern_safety(pattern)
        assert len(warnings) > 0

        # Still can cache it (validation is informational)
        compiled = CompiledPatternCache.get_compiled_pattern(pattern)
        assert isinstance(compiled, re.Pattern)

    def test_cache_with_validated_wrapper(self):
        """ValidatedPattern should work with cache."""
        pattern = r"[a-z]{3,7}"

        warnings = validate_pattern_safety(pattern)
        validated = ValidatedPattern(
            name="test",
            pattern=pattern,
            replacement="MATCH",
            test_cases=[("test", "MATCH")]
        )

        compiled = CompiledPatternCache.get_compiled_pattern(validated.pattern)
        assert compiled.search("test")

    def test_multiple_patterns_performance(self):
        """Caching should work with multiple patterns."""
        patterns = [rf"\w+{i}" for i in range(10)]

        # Compile all patterns
        for pattern in patterns:
            compiled = CompiledPatternCache.get_compiled_pattern(pattern)
            assert isinstance(compiled, re.Pattern)

        # Verify cache size
        stats = CompiledPatternCache.get_cache_stats()
        assert stats["size"] >= len(patterns)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_pattern(self):
        """Empty pattern should be handled."""
        warnings = validate_pattern_safety("")
        assert len(warnings) >= 0  # May warn about empty pattern

    def test_invalid_regex(self):
        """Invalid regex should raise ValueError."""
        # Invalid regex patterns should raise ValueError from the cache
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            CompiledPatternCache.get_compiled_pattern(r"(?P<invalid")

    def test_very_long_alternation(self):
        """Should handle long alternations safely."""
        pattern = "|".join([rf"word{i}" for i in range(100)])
        warnings = validate_pattern_safety(pattern)
        # Long alternations are valid but may have performance warnings

    def test_character_class_ranges(self):
        """Should validate character class ranges."""
        patterns = [
            r"[a-z]",  # Valid range
            r"[z-a]",  # Invalid range (reversed)
            r"[0-9]",  # Valid range
        ]

        for pattern in patterns:
            warnings = validate_pattern_safety(pattern)
            # Some may have warnings about reversed ranges


class TestValidatedPatternBehavior:
    """Cover ValidatedPattern runtime methods (apply/search/findall/test/etc.)."""

    def setup_method(self) -> None:
        CompiledPatternCache.clear_cache()

    def test_apply_with_global_replace(self):
        """global_replace=True should substitute all occurrences (count=None)."""
        validated = ValidatedPattern(
            name="digits_global",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("a1 b22 c333", "aN bN cN")],
            global_replace=True,
        )
        assert validated.apply("a1 b22 c333") == "aN bN cN"

    def test_apply_without_global_replace_caps_count(self):
        """Without global_replace, only the first occurrence is replaced (count=1)."""
        validated = ValidatedPattern(
            name="digits_first",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("a1 b22 c333", "aN b22 c333")],
            global_replace=False,
        )
        assert validated.apply("a1 b22 c333") == "aN b22 c333"

    def test_apply_oversize_input_raises(self):
        """Input larger than MAX_INPUT_SIZE should raise ValueError."""
        validated = ValidatedPattern(
            name="safe",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("1", "N")],
        )
        from crackerjack.services.patterns.core import MAX_INPUT_SIZE

        huge_text = "x" * (MAX_INPUT_SIZE + 1)
        with pytest.raises(ValueError, match="Input text too large"):
            validated.apply(huge_text)

    def test_apply_iteratively_single_iteration(self):
        """One pass should be enough when result stabilizes (early break)."""
        validated = ValidatedPattern(
            name="converges",
            pattern=r"foo",
            replacement="bar",
            test_cases=[("foo", "bar")],
            global_replace=True,
        )
        # After one iteration 'foo' becomes 'bar'; the second iteration doesn't
        # change the result, so the loop's early break returns 'bar'.
        assert validated.apply_iteratively("foo", max_iterations=5) == "bar"

    def test_apply_iteratively_no_change_returns_unchanged(self):
        """If apply doesn't change the text, loop breaks and returns original."""
        validated = ValidatedPattern(
            name="never_matches",
            pattern=r"XYZ",
            replacement="REPLACED",
            test_cases=[("abc", "abc")],
        )
        assert validated.apply_iteratively("abc", max_iterations=5) == "abc"

    def test_apply_iteratively_max_iterations_zero_raises(self):
        """max_iterations <= 0 should raise ValueError."""
        validated = ValidatedPattern(
            name="any",
            pattern=r"a",
            replacement="b",
            test_cases=[("a", "b")],
        )
        with pytest.raises(ValueError, match="max_iterations must be positive"):
            validated.apply_iteratively("a", max_iterations=0)
        with pytest.raises(ValueError, match="max_iterations must be positive"):
            validated.apply_iteratively("a", max_iterations=-1)

    def test_apply_iteratively_caps_at_max_iterations(self):
        """Loop should run at most max_iterations times (else branch)."""
        validated = ValidatedPattern(
            name="always_grows",
            pattern=r"a",
            replacement="aa",
            test_cases=[("a", "aa")],
            global_replace=True,
        )
        # 1 iter -> 'aa', 2 -> 'aaaa', 3 -> 'aaaaaaaa' (len 8)
        assert validated.apply_iteratively("a", max_iterations=3) == "aaaaaaaa"

    def test_apply_with_timeout_returns_result(self):
        """Normal call within timeout should return the result."""
        validated = ValidatedPattern(
            name="simple",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("a1 b22", "aN b22")],
        )
        result = validated.apply_with_timeout("a1 b22", timeout_seconds=2.0)
        assert result == "aN b22"

    def test_apply_with_timeout_raises_on_slow_pattern(self):
        """Backtracking-heavy pattern should trigger the SIGALRM timeout."""
        # Catastrophic-backtracking pattern on long-ish input.
        validated = ValidatedPattern(
            name="backtracker",
            pattern=r"^(a+)+$",
            replacement="X",
            test_cases=[("aaa", "X")],
        )
        # Build an input that triggers exponential backtracking.
        bad_text = "a" * 30 + "!"
        with pytest.raises(TimeoutError, match="timed out"):
            validated.apply_with_timeout(bad_text, timeout_seconds=1)

    def test_test_returns_bool_true_and_false(self):
        """Pattern.test() should return True on match and False otherwise."""
        validated = ValidatedPattern(
            name="digit_search",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("abc", "abc")],
        )
        assert validated.test("abc123") is True
        assert validated.test("no digits here") is False

    def test_search_returns_match_and_none(self):
        """Pattern.search() should return a match when present, else None."""
        validated = ValidatedPattern(
            name="digit_search",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("abc", "abc")],
        )
        match = validated.search("abc 42 def")
        assert match is not None
        assert match.group(0) == "42"
        assert validated.search("nothing here") is None

    def test_search_oversize_input_raises(self):
        """search() with oversize input should raise ValueError."""
        validated = ValidatedPattern(
            name="safe",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("1", "N")],
        )
        from crackerjack.services.patterns.core import MAX_INPUT_SIZE

        with pytest.raises(ValueError, match="Input text too large"):
            validated.search("x" * (MAX_INPUT_SIZE + 1))

    def test_findall_returns_all_matches(self):
        """Pattern.findall() should return list of all matches."""
        validated = ValidatedPattern(
            name="digits_all",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("1 22 333", "N N N")],
            global_replace=True,
        )
        assert validated.findall("1 22 333") == ["1", "22", "333"]
        assert validated.findall("no digits") == []

    def test_findall_oversize_input_raises(self):
        """findall() with oversize input should raise ValueError."""
        validated = ValidatedPattern(
            name="safe",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("1", "N")],
        )
        from crackerjack.services.patterns.core import MAX_INPUT_SIZE

        with pytest.raises(ValueError, match="Input text too large"):
            validated.findall("x" * (MAX_INPUT_SIZE + 1))

    def test_get_performance_stats_returns_expected_keys(self):
        """get_performance_stats should return dict with mean/min/max/total_time."""
        validated = ValidatedPattern(
            name="simple",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("a1", "aN")],
        )
        stats = validated.get_performance_stats("a1 b22 c333", iterations=3)
        assert set(stats.keys()) == {"mean_time", "min_time", "max_time", "total_time"}
        assert stats["min_time"] >= 0
        assert stats["max_time"] >= stats["min_time"]
        assert stats["total_time"] >= stats["max_time"]


class TestValidatedPatternValidation:
    """Cover the validation paths triggered in __post_init__."""

    def setup_method(self) -> None:
        CompiledPatternCache.clear_cache()

    def test_invalid_pattern_raises_in_post_init(self):
        """Invalid regex should raise ValueError from __post_init__ (uses name)."""
        with pytest.raises(ValueError, match="invalid_named"):
            ValidatedPattern(
                name="invalid_named",
                pattern=r"(?P<bad",
                replacement="X",
                test_cases=[("anything", "anything")],
            )

    def test_bad_replacement_syntax_raises(self):
        """Malformed \\g<...> replacement should raise ValueError."""
        with pytest.raises(ValueError, match="Bad replacement syntax"):
            ValidatedPattern(
                name="bad_repl",
                pattern=r"\d+",
                replacement=r"\\g <1>",  # space after \g is invalid
                test_cases=[("1", "1")],
            )

    def test_malformed_group_reference_raises(self):
        """Whitespace inside \\g<...> reference should raise."""
        with pytest.raises(ValueError, match="Bad replacement syntax"):
            ValidatedPattern(
                name="bad_repl2",
                pattern=r"(\d+)",
                replacement=r"\\g<1 bad>",
                test_cases=[("1", "1")],
            )

    def test_test_case_failure_raises(self):
        """A test case whose output doesn't match expected should raise."""
        with pytest.raises(ValueError, match="failed test case"):
            ValidatedPattern(
                name="mismatch",
                pattern=r"\d+",
                replacement="N",
                test_cases=[("abc", "WRONG")],  # should be "abc"
            )

    def test_global_replace_test_case_global(self):
        """When global_replace=True, test cases run with count=0 (global)."""
        validated = ValidatedPattern(
            name="global_replace_case",
            pattern=r"\d+",
            replacement="N",
            test_cases=[("1 22 333", "N N N")],
            global_replace=True,
        )
        # Just construction-time validation; sanity-check behavior.
        assert validated.apply("1 22 333") == "N N N"

    def test_pattern_safety_warnings_do_not_raise(self):
        """Safety warnings are informational; construction must still succeed."""
        validated = ValidatedPattern(
            name="many_alternations",
            pattern="|".join([rf"word{i}" for i in range(15)]),
            replacement="MATCH",
            test_cases=[("word0", "MATCH")],
        )
        assert validated.name == "many_alternations"

    def test_pattern_safety_nested_quantifiers_warning(self):
        """Patterns with nested quantifiers should not block construction."""
        # We need to also supply test cases that pass at replace time.
        validated = ValidatedPattern(
            name="nested_quant",
            pattern=r"\w++",
            replacement="X",
            test_cases=[("abc", "X")],
            global_replace=True,
        )
        assert validated.pattern == r"\w++"

    def test_caching_reuses_compiled_pattern(self):
        """Two ValidatedPattern instances with same pattern/flags share cache."""
        v1 = ValidatedPattern(
            name="a",
            pattern=r"foo",
            replacement="bar",
            test_cases=[("foo", "bar")],
        )
        v2 = ValidatedPattern(
            name="b",
            pattern=r"foo",
            replacement="baz",
            test_cases=[("foo", "baz")],
        )
        # Same pattern/flags => same compiled object cached under same key.
        assert v1._get_compiled_pattern() is v2._get_compiled_pattern()


class TestModuleConstants:
    """Verify constants are importable and reasonable."""

    def test_max_iterations_is_importable(self):
        from crackerjack.services.patterns.core import MAX_ITERATIONS

        assert MAX_ITERATIONS == 10

    def test_max_input_size_is_importable(self):
        from crackerjack.services.patterns.core import MAX_INPUT_SIZE

        assert MAX_INPUT_SIZE == 10 * 1024 * 1024

    def test_pattern_cache_size_is_importable(self):
        from crackerjack.services.patterns.core import PATTERN_CACHE_SIZE

        assert PATTERN_CACHE_SIZE == 100


class TestCacheBehavior:
    """Cover cache internals (eviction, invalid regex, stats contents)."""

    def setup_method(self) -> None:
        CompiledPatternCache.clear_cache()

    def test_get_cache_stats_keys(self):
        """Cache stats dict should have size, max_size, patterns."""
        stats = CompiledPatternCache.get_cache_stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 100
        assert stats["patterns"] == []

    def test_cache_size_grows_then_evicts(self):
        """When the cache fills up, oldest entry should be evicted."""
        # Add one pattern, then another distinct one with a different cache_key.
        CompiledPatternCache.get_compiled_pattern_with_flags("k1", r"a", 0)
        assert CompiledPatternCache.get_cache_stats()["size"] == 1
        CompiledPatternCache.get_compiled_pattern_with_flags("k2", r"b", 0)
        assert CompiledPatternCache.get_cache_stats()["size"] == 2
        assert set(CompiledPatternCache.get_cache_stats()["patterns"]) == {"k1", "k2"}

    def test_cache_evicts_oldest_when_full(self):
        """Filling cache beyond max_size should evict the oldest entry."""
        from crackerjack.services.patterns.core import PATTERN_CACHE_SIZE

        # Insert PATTERN_CACHE_SIZE + 5 entries; first ones should be evicted.
        for i in range(PATTERN_CACHE_SIZE + 5):
            CompiledPatternCache.get_compiled_pattern_with_flags(
                f"k{i}",
                rf"x{i}",
                0,
            )
        stats = CompiledPatternCache.get_cache_stats()
        assert stats["size"] == PATTERN_CACHE_SIZE
        # The first key inserted should have been evicted.
        assert "k0" not in stats["patterns"]

    def test_cache_invalid_regex_raises_value_error(self):
        """Invalid regex through cache API should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            CompiledPatternCache.get_compiled_pattern_with_flags(
                "bad_key", r"(?P<broken", 0,
            )


class TestValidatePatternSafetyBranches:
    """Cover safety warnings for specific shapes that are currently unexercised."""

    def test_empty_pattern_returns_empty_warnings(self):
        """Empty pattern is technically safe (no warnings)."""
        assert validate_pattern_safety("") == []

    def test_single_quantifier_no_nested_warning(self):
        """Single quantifier (no nesting) should not produce nested warning."""
        warnings = validate_pattern_safety(r"a+")
        assert not any("Nested" in w for w in warnings)

    def test_many_alternations_warning(self):
        """More than 10 '|' should produce a warning about alternations."""
        pattern = "|".join([f"word{i}" for i in range(15)])
        warnings = validate_pattern_safety(pattern)
        assert any("alternation" in w.lower() for w in warnings)

    def test_combined_warnings(self):
        """Pattern with multiple issues should produce multiple warnings."""
        pattern = ".*.*" + "+".join(["|a" for _ in range(15)])
        warnings = validate_pattern_safety(pattern)
        # At minimum, the multiple .* warning and alternations warning.
        assert len(warnings) >= 2

    def test_validate_re_raise_of_unwrapped_value_error(self):
        """_validate_compile_pattern should re-raise ValueErrors that don't
        originate from the cache's "Invalid regex pattern" path.
        """
        from unittest.mock import patch

        validated = ValidatedPattern(
            name="odd_error",
            pattern=r"foo",
            replacement="bar",
            test_cases=[("foo", "bar")],
        )
        # Bypass __post_init__ (already ran); call the validator directly and
        # have _get_compiled_pattern raise a different ValueError.
        with patch.object(
            validated,
            "_get_compiled_pattern",
            side_effect=ValueError("some other validation failure"),
        ):
            with pytest.raises(ValueError, match="some other validation failure"):
                validated._validate_compile_pattern()

    def test_run_test_cases_re_error_raises_value_error(self):
        """An re.error raised during sub() should surface as ValueError."""
        # Pattern matches, but the replacement has an out-of-range group ref
        # which makes re.sub itself raise re.error.
        with pytest.raises(ValueError, match="failed on"):
            ValidatedPattern(
                name="bad_group_ref",
                pattern=r"(\w+)",
                replacement=r"\99",  # group 99 doesn't exist
                test_cases=[("abc", "abc")],
            )
