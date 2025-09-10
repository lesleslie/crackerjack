"""
Comprehensive unit tests for crackerjack.services.regex_patterns module.

Tests the ValidatedPattern class and all SAFE_PATTERNS to prevent regex-related
bugs and ensure proper replacement syntax.
"""

import re

import pytest

from crackerjack.services.regex_patterns import (
    SAFE_PATTERNS,
    ValidatedPattern,
    apply_safe_replacement,
    find_pattern_for_text,
    get_pattern_description,
    validate_all_patterns,
)


class TestValidatedPattern:
    """Test the ValidatedPattern dataclass functionality."""

    def test_valid_pattern_creation(self) -> None:
        """Test creating a valid pattern succeeds."""
        pattern = ValidatedPattern(
            name="test_pattern",
            pattern=r"hello\s+(\w+)",
            replacement=r"hello \1",
            test_cases=[
                ("hello  world", "hello world"),
                ("hello   test", "hello test"),
            ],
        )

        assert pattern.name == "test_pattern"
        assert pattern.pattern == r"hello\s+(\w+)"
        assert pattern.replacement == r"hello \1"
        assert len(pattern.test_cases) == 2
        assert not pattern.global_replace  # Default False

    def test_valid_pattern_with_global_replace(self) -> None:
        """Test creating a pattern with global replace."""
        pattern = ValidatedPattern(
            name="global_test",
            pattern=r"a+",
            replacement="A",
            test_cases=[
                ("aaa bbb aaa", "A bbb A"),
            ],
            global_replace=True,
        )

        assert pattern.global_replace

    def test_invalid_regex_pattern_raises_error(self) -> None:
        """Test that invalid regex patterns raise ValueError."""
        with pytest.raises(ValueError, match="Invalid regex pattern 'bad_pattern'"):
            ValidatedPattern(
                name="bad_pattern",
                pattern=r"[unclosed",  # Invalid regex
                replacement="fixed",
                test_cases=[],
            )

    def test_bad_replacement_syntax_raises_error(self) -> None:
        """Test that bad replacement syntax raises ValueError."""
        with pytest.raises(ValueError, match="Bad replacement syntax"):
            ValidatedPattern(
                name="bad_replacement",
                pattern=r"(\w+)",
                replacement=r"\g<1>",  # Bad syntax with spaces
                test_cases=[],
            )

    def test_bad_replacement_syntax_variations(self) -> None:
        """Test various bad replacement syntax patterns."""
        bad_replacements = [
            r"\g<1>",
            r"\g<1 >",
            r"\g<1>",
            r"text \g<2> more",
        ]

        for bad_replacement in bad_replacements:
            with pytest.raises(ValueError, match="Bad replacement syntax"):
                ValidatedPattern(
                    name="test",
                    pattern=r"(\w+)",
                    replacement=bad_replacement,
                    test_cases=[],
                )

    def test_failing_test_case_raises_error(self) -> None:
        """Test that failing test cases raise ValueError."""
        with pytest.raises(ValueError, match="Pattern 'failing_test' failed test case"):
            ValidatedPattern(
                name="failing_test",
                pattern=r"hello",
                replacement="hi",
                test_cases=[
                    ("hello world", "goodbye world"),  # Expected doesn't match actual
                ],
            )

    def test_apply_method_single_replacement(self) -> None:
        """Test apply method with single replacement."""
        pattern = ValidatedPattern(
            name="single_replace",
            pattern=r"(\w+)\s+(\w+)",
            replacement=r"\1-\2",
            test_cases=[
                ("hello world", "hello-world"),
                ("foo bar baz qux", "foo-bar baz qux"),  # Only first match
            ],
        )

        result = pattern.apply("foo bar baz qux")
        assert result == "foo-bar baz qux"

    def test_apply_method_global_replacement(self) -> None:
        """Test apply method with global replacement."""
        pattern = ValidatedPattern(
            name="global_replace",
            pattern=r"(\w+)\s+(\w+)",
            replacement=r"\1-\2",
            test_cases=[
                (
                    "foo bar baz qux",
                    "foo-bar baz-qux",
                ),  # All non-overlapping matches replaced
            ],
            global_replace=True,
        )

        result = pattern.apply("foo bar baz qux")
        assert result == "foo-bar baz-qux"

    def test_test_method_matches(self) -> None:
        """Test test method for pattern matching."""
        pattern = ValidatedPattern(
            name="match_test",
            pattern=r"\d+",
            replacement="NUM",
            test_cases=[("has 123 numbers", "has NUM numbers")],
        )

        assert pattern.test("has 123 numbers") is True
        assert pattern.test("no numbers here") is False

    def test_description_field(self) -> None:
        """Test optional description field."""
        pattern = ValidatedPattern(
            name="described_pattern",
            pattern=r"test",
            replacement="TEST",
            test_cases=[("test", "TEST")],
            description="A test pattern",
        )

        assert pattern.description == "A test pattern"


class TestSafePatternsValidation:
    """Test that all SAFE_PATTERNS are properly validated."""

    def test_all_patterns_validate(self) -> None:
        """Test that validate_all_patterns returns True for all patterns."""
        results = validate_all_patterns()

        assert isinstance(results, dict)
        assert len(results) == len(SAFE_PATTERNS)

        failed_patterns = [name for name, success in results.items() if not success]
        assert failed_patterns == [], f"Failed patterns: {failed_patterns}"

    def test_all_patterns_exist(self) -> None:
        """Test that all expected patterns exist in SAFE_PATTERNS."""
        expected_patterns = {
            "fix_command_spacing",
            "fix_long_flag_spacing",
            "fix_short_flag_spacing",
            "fix_hyphenated_names",
            "fix_hyphenated_names_global",
            "fix_spaced_hyphens",
            "fix_debug_log_pattern",
            "fix_job_file_pattern",
            "fix_markdown_bold",
            # Security patterns
            "mask_pypi_token",
            "mask_github_token",
            "mask_generic_long_token",
            "mask_token_assignment",
            "detect_hardcoded_paths",
            "detect_potential_secrets",
            "detect_suspicious_tmp_traversal",
            "detect_suspicious_var_traversal",
            # Tool output parsing patterns
            "ruff_check_error",
            "ruff_check_summary",
            "pyright_error",
            "pyright_warning",
            "pyright_summary",
            "bandit_issue",
            "bandit_location",
            "bandit_confidence",
            "bandit_severity",
            "mypy_error",
            "mypy_note",
            "vulture_unused",
            "complexipy_complex",
        }

        actual_patterns = set(SAFE_PATTERNS.keys())
        assert actual_patterns == expected_patterns

    def test_all_patterns_have_names(self) -> None:
        """Test that all patterns have correct names."""
        for pattern_name, pattern in SAFE_PATTERNS.items():
            assert pattern.name == pattern_name

    def test_all_patterns_have_descriptions(self) -> None:
        """Test that all patterns have non-empty descriptions."""
        for pattern_name, pattern in SAFE_PATTERNS.items():
            assert pattern.description, f"Pattern {pattern_name} has no description"

    def test_all_patterns_have_test_cases(self) -> None:
        """Test that all patterns have test cases."""
        for pattern_name, pattern in SAFE_PATTERNS.items():
            assert len(pattern.test_cases) > 0, (
                f"Pattern {pattern_name} has no test cases"
            )


class TestSpecificPatterns:
    """Test each specific pattern individually."""

    def test_fix_command_spacing_pattern(self) -> None:
        """Test fix_command_spacing pattern thoroughly."""
        pattern = SAFE_PATTERNS["fix_command_spacing"]

        # Test all defined test cases
        test_cases = [
            ("python - m crackerjack", "python -m crackerjack"),
            ("python -m crackerjack", "python -m crackerjack"),
            ("python  -  m  pytest", "python -m pytest"),
            ("other python - m stuff", "other python -m stuff"),
        ]

        for input_text, expected in test_cases:
            result = pattern.apply(input_text)
            assert result == expected, f"Failed: {input_text} -> {result} != {expected}"

        # Test edge cases
        assert (
            pattern.apply("python-m test") == "python -m test"
        )  # Hyphenated also matches
        assert pattern.apply("not python - m") == "not python - m"  # No word after 'm'

    def test_fix_long_flag_spacing_pattern(self) -> None:
        """Test fix_long_flag_spacing pattern thoroughly."""
        pattern = SAFE_PATTERNS["fix_long_flag_spacing"]

        # Use the actual test cases from the pattern definition
        for input_text, expected in pattern.test_cases:
            result = pattern.apply(input_text)
            assert result == expected

        # Test edge cases
        assert pattern.apply("--- help") == "---help"  # Three dashes: matches last two
        assert pattern.apply("-help") == "-help"  # Single dash, no match

    def test_fix_short_flag_spacing_pattern(self) -> None:
        """Test fix_short_flag_spacing pattern thoroughly."""
        pattern = SAFE_PATTERNS["fix_short_flag_spacing"]

        test_cases = [
            ("python -m crackerjack - t", "python -m crackerjack -t"),
            ("- q", "-q"),
            ("-t", "-t"),
            ("some - x flag", "some -x flag"),
        ]

        for input_text, expected in test_cases:
            result = pattern.apply(input_text)
            assert result == expected

        # Test edge cases
        assert pattern.apply("word- t") == "word- t"  # No space before dash
        assert pattern.apply("- test") == "- test"  # Multi-char after dash, no match

    def test_fix_hyphenated_names_pattern(self) -> None:
        """Test fix_hyphenated_names pattern (single replacement)."""
        pattern = SAFE_PATTERNS["fix_hyphenated_names"]

        test_cases = [
            ("python - pro", "python-pro"),
            ("pytest - hypothesis - specialist", "pytest-hypothesis - specialist"),
            ("backend - architect", "backend-architect"),
            ("python-pro", "python-pro"),
            ("end - of - file-fixer", "end-of - file-fixer"),
        ]

        for input_text, expected in test_cases:
            result = pattern.apply(input_text)
            assert result == expected

    def test_fix_hyphenated_names_global_pattern(self) -> None:
        """Test fix_hyphenated_names_global pattern (global replacement)."""
        pattern = SAFE_PATTERNS["fix_hyphenated_names_global"]

        # Use the actual test cases from the pattern definition
        for input_text, expected in pattern.test_cases:
            result = pattern.apply(input_text)
            assert result == expected

    def test_fix_debug_log_pattern(self) -> None:
        """Test fix_debug_log_pattern thoroughly."""
        pattern = SAFE_PATTERNS["fix_debug_log_pattern"]

        test_cases = [
            ("crackerjack - debug-12345.log", "crackerjack-debug-12345.log"),
            ("crackerjack-debug.log", "crackerjack-debug.log"),
            ("old crackerjack - debug files", "old crackerjack-debug files"),
        ]

        for input_text, expected in test_cases:
            result = pattern.apply(input_text)
            assert result == expected

    def test_fix_job_file_pattern(self) -> None:
        """Test fix_job_file_pattern thoroughly."""
        pattern = SAFE_PATTERNS["fix_job_file_pattern"]

        test_cases = [
            ("job - {self.web_job_id}.json", "job-{self.web_job_id}.json"),
            ("job - abc123.json", "job-abc123.json"),
            ("job-existing.json", "job-existing.json"),
        ]

        for input_text, expected in test_cases:
            result = pattern.apply(input_text)
            assert result == expected

    def test_fix_markdown_bold_pattern(self) -> None:
        """Test fix_markdown_bold_pattern thoroughly."""
        pattern = SAFE_PATTERNS["fix_markdown_bold"]

        test_cases = [
            ("* *Bold Text * *", "**Bold Text**"),
            ("* *🧪 pytest-specialist * *", "**🧪 pytest-specialist**"),
            ("**Already Bold**", "**Already Bold**"),
        ]

        for input_text, expected in test_cases:
            result = pattern.apply(input_text)
            assert result == expected


class TestUtilityFunctions:
    """Test utility functions in the module."""

    def test_apply_safe_replacement_success(self) -> None:
        """Test apply_safe_replacement with valid pattern."""
        result = apply_safe_replacement("python - m test", "fix_command_spacing")
        assert result == "python -m test"

    def test_apply_safe_replacement_unknown_pattern(self) -> None:
        """Test apply_safe_replacement with unknown pattern."""
        with pytest.raises(ValueError, match="Unknown pattern: nonexistent"):
            apply_safe_replacement("test", "nonexistent")

    def test_find_pattern_for_text_matches(self) -> None:
        """Test find_pattern_for_text finds correct patterns."""
        # Text that matches multiple patterns
        matches = find_pattern_for_text("python - m crackerjack")
        assert "fix_command_spacing" in matches

        # Text that matches hyphenated names
        matches = find_pattern_for_text("some - text")
        expected_matches = ["fix_hyphenated_names", "fix_hyphenated_names_global"]
        for expected in expected_matches:
            assert expected in matches

    def test_find_pattern_for_text_no_matches(self) -> None:
        """Test find_pattern_for_text with no matching patterns."""
        matches = find_pattern_for_text("nothing matches this text")
        assert matches == []

    def test_get_pattern_description_valid(self) -> None:
        """Test get_pattern_description with valid pattern."""
        description = get_pattern_description("fix_command_spacing")
        assert description == "Fix spacing in 'python -m command' patterns"

    def test_get_pattern_description_invalid(self) -> None:
        """Test get_pattern_description with invalid pattern."""
        description = get_pattern_description("nonexistent")
        assert description == "Unknown pattern"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_handling(self) -> None:
        """Test that patterns handle empty strings gracefully."""
        for pattern_name, pattern in SAFE_PATTERNS.items():
            result = pattern.apply("")
            assert result == "", f"Pattern {pattern_name} failed on empty string"

    def test_very_long_string_handling(self) -> None:
        """Test patterns with very long strings."""
        long_string = "word " * 1000 + "python - m test " + "word " * 1000
        pattern = SAFE_PATTERNS["fix_command_spacing"]
        result = pattern.apply(long_string)
        assert "python -m test" in result

    def test_unicode_handling(self) -> None:
        """Test patterns handle Unicode correctly."""
        unicode_text = "🐍 python - m test"  # Word character after 'm'
        pattern = SAFE_PATTERNS["fix_command_spacing"]
        result = pattern.apply(unicode_text)
        assert result == "🐍 python -m test"

    def test_newline_handling(self) -> None:
        """Test patterns handle newlines correctly."""
        text_with_newlines = "line1\npython - m test\nline3"
        pattern = SAFE_PATTERNS["fix_command_spacing"]
        result = pattern.apply(text_with_newlines)
        assert result == "line1\npython -m test\nline3"

    def test_special_regex_characters(self) -> None:
        """Test patterns handle special regex characters in input."""
        special_text = "python - m test.with[special]chars"
        pattern = SAFE_PATTERNS["fix_command_spacing"]
        result = pattern.apply(special_text)
        assert result == "python -m test.with[special]chars"


class TestPatternSafety:
    """Test that patterns are safe and don't cause issues."""

    def test_no_catastrophic_backtracking(self) -> None:
        """Test that patterns don't have catastrophic backtracking."""
        # Create potentially problematic input
        problematic_input = "a" * 100 + "python - m" + "b" * 100

        # Test each pattern completes quickly (should be nearly instant)
        import time

        for pattern_name, pattern in SAFE_PATTERNS.items():
            start_time = time.time()
            result = pattern.apply(problematic_input)
            end_time = time.time()

            # Should complete in well under a second
            assert end_time - start_time < 1.0, f"Pattern {pattern_name} too slow"
            assert isinstance(result, str), (
                f"Pattern {pattern_name} didn't return string"
            )

    def test_patterns_are_idempotent(self) -> None:
        """Test that applying patterns multiple times gives same result."""
        # Test idempotency with patterns that are likely to match
        # Note: Some patterns like fix_hyphenated_names_global and fix_spaced_hyphens may need multiple passes
        # and are not idempotent by design
        non_idempotent_patterns = {"fix_hyphenated_names_global", "fix_spaced_hyphens"}

        for pattern_name, pattern in SAFE_PATTERNS.items():
            if pattern_name in non_idempotent_patterns:
                continue  # Skip patterns that are expected to need multiple passes

            for input_text, expected in pattern.test_cases:
                # Apply pattern twice
                first_result = pattern.apply(input_text)
                second_result = pattern.apply(first_result)

                # Should be identical (idempotent)
                assert first_result == second_result, (
                    f"Pattern {pattern_name} not idempotent: "
                    f"{input_text} -> {first_result} -> {second_result}"
                )

    def test_patterns_dont_introduce_extra_spaces(self) -> None:
        """Test that patterns don't introduce unwanted extra spaces."""
        for pattern_name, pattern in SAFE_PATTERNS.items():
            for input_text, expected in pattern.test_cases:
                result = pattern.apply(input_text)

                # Check no double spaces introduced
                assert "  " not in result or "  " in expected, (
                    f"Pattern {pattern_name} introduced double spaces: "
                    f"{input_text} -> {result}"
                )

                # Check no leading/trailing spaces added unexpectedly
                if not expected.startswith(" "):
                    assert not result.startswith(" "), (
                        f"Pattern {pattern_name} added leading space: {result}"
                    )
                if not expected.endswith(" "):
                    assert not result.endswith(" "), (
                        f"Pattern {pattern_name} added trailing space: {result}"
                    )


class TestRegexPatternCompliance:
    """Test compliance with regex pattern requirements."""

    def test_no_raw_regex_in_patterns(self) -> None:
        """Test that patterns don't use problematic raw regex constructs."""
        for pattern_name, pattern in SAFE_PATTERNS.items():
            # Check for overly broad patterns
            assert not pattern.pattern == ".*", (
                f"Pattern {pattern_name} uses overly broad .*"
            )
            assert (
                ".+" not in pattern.pattern
                or pattern_name
                in [
                    "fix_hyphenated_names_global",  # This one legitimately uses word boundaries
                    "fix_markdown_bold",  # This one uses .+? for content matching
                ]
            ), f"Pattern {pattern_name} may be too broad"

    def test_replacement_syntax_compliance(self) -> None:
        """Test that all replacement syntax follows correct format."""
        for pattern_name, pattern in SAFE_PATTERNS.items():
            replacement = pattern.replacement

            # Should not contain bad syntax
            assert r"\g < " not in replacement, f"Bad syntax in {pattern_name}"
            assert r" >" not in replacement or r"\1>" not in replacement, (
                f"Bad syntax in {pattern_name}"
            )

            # If it contains group references, they should be properly formatted
            if r"\g<" in replacement:
                # Should be \g<N> format
                import re as regex_mod

                group_refs = regex_mod.findall(r"\\g<(\d+)>", replacement)
                assert len(group_refs) > 0, (
                    f"Malformed group reference in {pattern_name}"
                )

    def test_patterns_compile_successfully(self) -> None:
        """Test that all regex patterns compile without errors."""
        for pattern_name, pattern in SAFE_PATTERNS.items():
            try:
                compiled = re.compile(
                    pattern.pattern
                )  # REGEX OK: testing pattern compilation
                assert compiled is not None
            except re.error as e:
                pytest.fail(f"Pattern {pattern_name} failed to compile: {e}")


class TestToolOutputPatterns:
    """Test development tool output parsing patterns."""

    def test_tool_output_patterns_exist(self) -> None:
        """Test that all tool output parsing patterns exist."""
        tool_patterns = [
            "ruff_check_error",
            "ruff_check_summary",
            "pyright_error",
            "pyright_warning",
            "pyright_summary",
            "bandit_issue",
            "bandit_location",
            "bandit_confidence",
            "bandit_severity",
            "mypy_error",
            "mypy_note",
            "vulture_unused",
            "complexipy_complex",
        ]

        for pattern_name in tool_patterns:
            assert pattern_name in SAFE_PATTERNS, (
                f"Missing tool pattern: {pattern_name}"
            )

    def test_ruff_patterns(self) -> None:
        """Test ruff-check patterns."""

        # Test ruff error pattern
        ruff_error = SAFE_PATTERNS["ruff_check_error"]
        assert ruff_error.test("crackerjack/core.py: 123: 45: E501 line too long")
        assert not ruff_error.test("Not a ruff error line")

        # Test parsing groups
        pattern = ruff_error._get_compiled_pattern()
        match = pattern.match("crackerjack/core.py: 123: 45: E501 line too long")
        assert match is not None
        file_path, line_num, col_num, code, message = match.groups()
        assert file_path == "crackerjack/core.py"
        assert line_num == "123"
        assert col_num == "45"
        assert code == "E501"
        assert message == "line too long"

        # Test ruff summary pattern
        ruff_summary = SAFE_PATTERNS["ruff_check_summary"]
        assert ruff_summary.test("Found 5 error in file")
        assert not ruff_summary.test("No errors found")

    def test_pyright_patterns(self) -> None:
        """Test pyright patterns."""

        # Test error pattern
        pyright_error = SAFE_PATTERNS["pyright_error"]
        assert pyright_error.test("src/app.py: 45: 12 - error: Undefined variable")
        assert not pyright_error.test("src/app.py: 45: 12 - warning: Something")

        # Test warning pattern
        pyright_warning = SAFE_PATTERNS["pyright_warning"]
        assert pyright_warning.test("src/app.py: 45: 12 - warning: Unused variable")
        assert not pyright_warning.test("src/app.py: 45: 12 - error: Type error")

        # Test summary pattern
        pyright_summary = SAFE_PATTERNS["pyright_summary"]
        assert pyright_summary.test("5 errors, 3 warnings")
        assert pyright_summary.test("1 error, 1 warning")
        assert not pyright_summary.test("No issues found")

        # Test parsing groups
        error_pattern = pyright_error._get_compiled_pattern()
        match = error_pattern.match("src/app.py: 45: 12 - error: Undefined variable")
        assert match is not None
        file_path, line_num, col_num, message = match.groups()
        assert file_path == "src/app.py"
        assert line_num == "45"
        assert col_num == "12"
        assert message == "Undefined variable"

    def test_bandit_patterns(self) -> None:
        """Test bandit security patterns."""

        # Test issue pattern
        bandit_issue = SAFE_PATTERNS["bandit_issue"]
        assert bandit_issue.test(
            ">> Issue: [B602: subprocess_popen_with_shell_equals_true] Use of shell=True"
        )
        assert not bandit_issue.test("Some other security message")

        # Test parsing groups
        pattern = bandit_issue._get_compiled_pattern()
        match = pattern.match(
            ">> Issue: [B602: subprocess_popen_with_shell_equals_true] Use of shell=True"
        )
        assert match is not None
        code, message = match.groups()
        assert code == "B602"
        assert message == "Use of shell=True"

        # Test location pattern
        bandit_location = SAFE_PATTERNS["bandit_location"]
        assert bandit_location.test("Location: src/security.py: 123: 45")
        assert not bandit_location.test("File: src/security.py line 123")

        # Test confidence pattern
        bandit_confidence = SAFE_PATTERNS["bandit_confidence"]
        assert bandit_confidence.test("Confidence: HIGH")
        assert not bandit_confidence.test("Trust level: HIGH")

        # Test severity pattern
        bandit_severity = SAFE_PATTERNS["bandit_severity"]
        assert bandit_severity.test("Severity: MEDIUM")
        assert not bandit_severity.test("Risk level: MEDIUM")

    def test_mypy_patterns(self) -> None:
        """Test mypy patterns."""

        # Test error pattern
        mypy_error = SAFE_PATTERNS["mypy_error"]
        assert mypy_error.test(
            "src/app.py: 45: error: Name 'undefined_var' is not defined"
        )
        assert not mypy_error.test("src/app.py: 45: note: Something")

        # Test note pattern
        mypy_note = SAFE_PATTERNS["mypy_note"]
        assert mypy_note.test("src/app.py: 45: note: Expected type Union[int, str]")
        assert not mypy_note.test("src/app.py: 45: error: Type error")

        # Test parsing groups
        error_pattern = mypy_error._get_compiled_pattern()
        match = error_pattern.match(
            "src/app.py: 45: error: Name 'undefined_var' is not defined"
        )
        assert match is not None
        file_path, line_num, message = match.groups()
        assert file_path == "src/app.py"
        assert line_num == "45"
        assert message == "Name 'undefined_var' is not defined"

    def test_vulture_patterns(self) -> None:
        """Test vulture unused code detection patterns."""

        vulture_unused = SAFE_PATTERNS["vulture_unused"]
        assert vulture_unused.test("src/app.py: 45: unused variable 'temp_var'")
        assert vulture_unused.test("test.py: 1: unused function 'helper'")
        assert not vulture_unused.test("src/app.py: 45: used variable 'active_var'")

        # Test parsing groups
        pattern = vulture_unused._get_compiled_pattern()
        match = pattern.match("src/app.py: 45: unused variable 'temp_var'")
        assert match is not None
        file_path, line_num, item_type, item_name = match.groups()
        assert file_path == "src/app.py"
        assert line_num == "45"
        assert item_type == "variable"
        assert item_name == "temp_var"

    def test_complexipy_patterns(self) -> None:
        """Test complexipy complexity detection patterns."""

        complexipy_complex = SAFE_PATTERNS["complexipy_complex"]
        assert complexipy_complex.test(
            "src/app.py: 45: 1 - complex_function is too complex (15)"
        )
        assert not complexipy_complex.test(
            "src/app.py: 45: 1 - simple_function is fine (5)"
        )

        # Test parsing groups
        pattern = complexipy_complex._get_compiled_pattern()
        match = pattern.match(
            "src/app.py: 45: 1 - complex_function is too complex (15)"
        )
        assert match is not None
        file_path, line_num, col_num, function_name, complexity = match.groups()
        assert file_path == "src/app.py"
        assert line_num == "45"
        assert col_num == "1"
        assert function_name == "complex_function"
        assert complexity == "15"

    def test_all_patterns_validate(self) -> None:
        """Test that all patterns in SAFE_PATTERNS validate correctly."""
        results = validate_all_patterns()

        failed = [name for name, valid in results.items() if not valid]
        if failed:
            print(f"Failed patterns: {failed}")

        assert all(results.values()), f"Some patterns failed validation: {failed}"
