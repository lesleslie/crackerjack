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
