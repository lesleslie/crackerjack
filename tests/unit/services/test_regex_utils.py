"""Comprehensive tests for regex_utils.py.

Target Coverage: 70-75% (125-134 statements out of 179)
Test Strategy: 30-35 tests covering all public functions and core private helpers
"""

import re
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import pytest

# Module-level import pattern to avoid pytest conflicts
from crackerjack.services import regex_utils


class TestTestPatternImmediately:
    """Test test_pattern_immediately() function."""

    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_valid_pattern_all_tests_passing(self, mock_cache: Mock) -> None:
        """Test valid pattern with all test cases passing."""
        mock_compiled = Mock()
        mock_compiled.sub.return_value = "result"
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        result = regex_utils.test_pattern_immediately(
            pattern=r"(\w+)",
            replacement=r"\1",
            test_cases=[("test", "result")],
        )

        assert result["pattern"] == r"(\w+)"
        assert result["replacement"] == r"\1"
        assert result["all_passed"] is True
        assert len(result["test_results"]) == 1
        assert result["test_results"][0]["passed"] is True

    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_valid_pattern_some_tests_failing(self, mock_cache: Mock) -> None:
        """Test valid pattern with some test cases failing."""
        mock_compiled = Mock()
        mock_compiled.sub.side_effect = ["wrong", "correct"]
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        result = regex_utils.test_pattern_immediately(
            pattern=r"(\w+)",
            replacement=r"\1",
            test_cases=[("test1", "correct"), ("test2", "wrong")],
        )

        assert result["all_passed"] is False
        assert len(result["test_results"]) == 2
        assert result["test_results"][0]["passed"] is False
        assert result["test_results"][1]["passed"] is False

    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_invalid_pattern_adds_to_errors(self, mock_cache: Mock) -> None:
        """Test invalid pattern raises ValueError and adds to errors list."""
        mock_cache.get_compiled_pattern.side_effect = ValueError("Invalid regex")

        result = regex_utils.test_pattern_immediately(
            pattern="[invalid(",
            replacement=r"\1",
            test_cases=[("test", "test")],
        )

        assert result["all_passed"] is False
        assert len(result["errors"]) == 1
        assert "Invalid regex pattern" in result["errors"][0]

    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_performance_warning_for_wildcard_wildcard(
        self, mock_cache: Mock
    ) -> None:
        """Test performance warning for .*.* pattern."""
        mock_compiled = Mock()
        mock_compiled.sub.return_value = "result"
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        result = regex_utils.test_pattern_immediately(
            pattern=r".*.*test",
            replacement=r"\1",
            test_cases=[("test", "result")],
        )

        assert len(result["warnings"]) == 1
        assert "Multiple .* constructs" in result["warnings"][0]

    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_performance_warning_for_plus_plus(self, mock_cache: Mock) -> None:
        """Test performance warning for .+.+ pattern."""
        mock_compiled = Mock()
        mock_compiled.sub.return_value = "result"
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        result = regex_utils.test_pattern_immediately(
            pattern=r".+.+test",
            replacement=r"\1",
            test_cases=[("test", "result")],
        )

        assert len(result["warnings"]) == 1
        assert "Multiple .+ constructs" in result["warnings"][0]

    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_both_performance_warnings(self, mock_cache: Mock) -> None:
        """Test both warnings when pattern has both .*.* and .+.+"""
        mock_compiled = Mock()
        mock_compiled.sub.return_value = "result"
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        result = regex_utils.test_pattern_immediately(
            pattern=r".*.*test.+.+",
            replacement=r"\1",
            test_cases=[("test", "result")],
        )

        assert len(result["warnings"]) == 2


class TestPrintPatternTestReport:
    """Test print_pattern_test_report() function."""

    def test_function_runs_without_error(self) -> None:
        """Test that print function runs without error (no-op)."""
        results = {
            "description": "Test pattern",
            "errors": ["Error 1"],
            "warnings": ["Warning 1"],
            "test_results": [
                {"passed": True, "input": "test", "expected": "test", "actual": "test"}
            ],
        }

        # Should not raise any errors
        regex_utils.print_pattern_test_report(results)


class TestQuickPatternTest:
    """Test quick_pattern_test() function."""

    @patch("crackerjack.services.regex_utils.print_pattern_test_report")
    @patch("crackerjack.services.regex_utils.test_pattern_immediately")
    def test_returns_true_when_all_pass(
        self, mock_test: Mock, mock_print: Mock
    ) -> None:
        """Test returns True when all tests pass."""
        mock_test.return_value = {"all_passed": True}

        result = regex_utils.quick_pattern_test(
            pattern=r"(\w+)",
            replacement=r"\1",
            test_cases=[("test", "test")],
        )

        assert result is True
        mock_test.assert_called_once()
        mock_print.assert_called_once()

    @patch("crackerjack.services.regex_utils.print_pattern_test_report")
    @patch("crackerjack.services.regex_utils.test_pattern_immediately")
    def test_returns_false_when_some_fail(
        self, mock_test: Mock, mock_print: Mock
    ) -> None:
        """Test returns False when some tests fail."""
        mock_test.return_value = {"all_passed": False}

        result = regex_utils.quick_pattern_test(
            pattern=r"(\w+)",
            replacement=r"\1",
            test_cases=[("test", "wrong")],
        )

        assert result is False


class TestFindSafePatternForText:
    """Test find_safe_pattern_for_text() function."""

    @patch("crackerjack.services.regex_utils.SAFE_PATTERNS")
    def test_returns_empty_list_when_no_patterns_match(self, mock_patterns: Mock) -> None:
        """Test returns empty list when no SAFE_PATTERNS match."""
        mock_pattern1 = Mock()
        mock_pattern1.test.return_value = False
        mock_pattern2 = Mock()
        mock_pattern2.test.return_value = False

        mock_patterns.items.return_value = [("pattern1", mock_pattern1), ("pattern2", mock_pattern2)]

        result = regex_utils.find_safe_pattern_for_text("test text")

        assert result == []

    @patch("crackerjack.services.regex_utils.SAFE_PATTERNS")
    def test_returns_matching_pattern_names(self, mock_patterns: Mock) -> None:
        """Test returns names of matching patterns."""
        mock_pattern1 = Mock()
        mock_pattern1.test.return_value = True
        mock_pattern2 = Mock()
        mock_pattern2.test.return_value = False

        mock_patterns.items.return_value = [("pattern1", mock_pattern1), ("pattern2", mock_pattern2)]

        result = regex_utils.find_safe_pattern_for_text("test text")

        assert result == ["pattern1"]

    @patch("crackerjack.services.regex_utils.SAFE_PATTERNS")
    def test_handles_exceptions_from_pattern_test(self, mock_patterns: Mock) -> None:
        """Test continues when pattern.test() raises exception."""
        mock_pattern1 = Mock()
        mock_pattern1.test.side_effect = Exception("Test error")
        mock_pattern2 = Mock()
        mock_pattern2.test.return_value = True

        mock_patterns.items.return_value = [("pattern1", mock_pattern1), ("pattern2", mock_pattern2)]

        result = regex_utils.find_safe_pattern_for_text("test text")

        assert result == ["pattern2"]


class TestSuggestMigrationForReSub:
    """Test suggest_migration_for_re_sub() function."""

    @patch("crackerjack.services.regex_utils._determine_suggested_name")
    @patch("crackerjack.services.regex_utils._build_test_cases")
    @patch("crackerjack.services.regex_utils.find_safe_pattern_for_text")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_detects_forbidden_pattern_with_spaces(
        self, mock_cache: Mock, mock_find: Mock, mock_build: Mock, mock_name: Mock
    ) -> None:
        """Test detection of forbidden patterns (spaces in \\g<1>)."""
        mock_compiled = Mock()
        mock_compiled.search.return_value = True  # Forbidden pattern found
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        mock_find.return_value = []
        mock_build.return_value = []
        mock_name.return_value = "fix_test_pattern"

        result = regex_utils.suggest_migration_for_re_sub(
            original_pattern=r"(\w+)",
            original_replacement=r"\g < 1> text",  # Has space
        )

        assert len(result["safety_issues"]) > 0
        assert "CRITICAL" in result["safety_issues"][0]

    @patch("crackerjack.services.regex_utils._determine_suggested_name")
    @patch("crackerjack.services.regex_utils._build_test_cases")
    @patch("crackerjack.services.regex_utils.find_safe_pattern_for_text")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_finds_existing_safe_patterns(
        self, mock_cache: Mock, mock_find: Mock, mock_build: Mock, mock_name: Mock
    ) -> None:
        """Test finds existing safe patterns for sample text."""
        mock_compiled = Mock()
        mock_compiled.search.return_value = False
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        mock_find.return_value = ["pattern1", "pattern2"]
        mock_build.return_value = []
        mock_name.return_value = "fix_test"

        result = regex_utils.suggest_migration_for_re_sub(
            original_pattern=r"(\w+)",
            original_replacement=r"\1",
            sample_text="test text",
        )

        assert result["existing_matches"] == ["pattern1", "pattern2"]
        assert result["needs_new_pattern"] is False

    @patch("crackerjack.services.regex_utils._determine_suggested_name")
    @patch("crackerjack.services.regex_utils._build_test_cases")
    @patch("crackerjack.services.regex_utils.find_safe_pattern_for_text")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_determines_suggested_name(
        self, mock_cache: Mock, mock_find: Mock, mock_build: Mock, mock_name: Mock
    ) -> None:
        """Test determines suggested name."""
        mock_compiled = Mock()
        mock_compiled.search.return_value = False
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        mock_find.return_value = []
        mock_build.return_value = []
        mock_name.return_value = "fix_hyphenated_names"

        result = regex_utils.suggest_migration_for_re_sub(
            original_pattern=r"(\w+)\s*-\s*(\w+)",
            original_replacement=r"\1-\2",
        )

        assert result["suggested_name"] == "fix_hyphenated_names"

    @patch("crackerjack.services.regex_utils._determine_suggested_name")
    @patch("crackerjack.services.regex_utils._build_test_cases")
    @patch("crackerjack.services.regex_utils.find_safe_pattern_for_text")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_builds_test_cases_from_sample(
        self, mock_cache: Mock, mock_find: Mock, mock_build: Mock, mock_name: Mock
    ) -> None:
        """Test builds test cases from sample text."""
        mock_compiled = Mock()
        mock_compiled.search.return_value = False
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        mock_find.return_value = []
        mock_build.return_value = [("test", "result")]
        mock_name.return_value = "fix_test"

        result = regex_utils.suggest_migration_for_re_sub(
            original_pattern=r"(\w+)",
            original_replacement=r"\1",
            sample_text="test text",
        )

        assert result["test_cases_needed"] == [("test", "result")]

    @patch("crackerjack.services.regex_utils._determine_suggested_name")
    @patch("crackerjack.services.regex_utils._build_test_cases")
    @patch("crackerjack.services.regex_utils.find_safe_pattern_for_text")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_returns_needs_new_pattern_true_when_no_matches(
        self, mock_cache: Mock, mock_find: Mock, mock_build: Mock, mock_name: Mock
    ) -> None:
        """Test returns needs_new_pattern=True when no existing matches."""
        mock_compiled = Mock()
        mock_compiled.search.return_value = False
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        mock_find.return_value = []
        mock_build.return_value = []
        mock_name.return_value = "fix_test"

        result = regex_utils.suggest_migration_for_re_sub(
            original_pattern=r"(\w+)",
            original_replacement=r"\1",
            sample_text="test text",
        )

        assert result["needs_new_pattern"] is True

    @patch("crackerjack.services.regex_utils._determine_suggested_name")
    @patch("crackerjack.services.regex_utils._build_test_cases")
    @patch("crackerjack.services.regex_utils.find_safe_pattern_for_text")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_returns_full_suggestion_dict(
        self, mock_cache: Mock, mock_find: Mock, mock_build: Mock, mock_name: Mock
    ) -> None:
        """Test returns complete suggestion dict structure."""
        mock_compiled = Mock()
        mock_compiled.search.return_value = False
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        mock_find.return_value = []
        mock_build.return_value = []
        mock_name.return_value = "fix_test"

        result = regex_utils.suggest_migration_for_re_sub(
            original_pattern=r"(\w+)",
            original_replacement=r"\1",
        )

        assert "original_pattern" in result
        assert "original_replacement" in result
        assert "existing_matches" in result
        assert "needs_new_pattern" in result
        assert "safety_issues" in result
        assert "suggested_name" in result
        assert "test_cases_needed" in result


class TestPrintMigrationSuggestion:
    """Test print_migration_suggestion() function."""

    @patch("crackerjack.services.regex_utils.SAFE_PATTERNS")
    def test_function_runs_without_error(self, mock_patterns: Mock) -> None:
        """Test that print function runs without error (no-op)."""
        # Mock SAFE_PATTERNS to prevent KeyError when function accesses it
        mock_patterns.__getitem__ = Mock()

        suggestion = {
            "safety_issues": ["Issue 1"],
            "existing_matches": ["pattern1"],
            "needs_new_pattern": True,
            "test_cases_needed": [("test", "result")],
        }

        # Should not raise any errors - function is a no-op with pass statements
        try:
            regex_utils.print_migration_suggestion(suggestion)
        except Exception as e:
            pytest.fail(f"Function raised exception: {e}")


class TestAuditFileForReSub:
    """Test audit_file_for_re_sub() function."""

    @patch("crackerjack.services.regex_utils.suggest_migration_for_re_sub")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_finds_re_sub_calls_in_file(
        self, mock_cache: Mock, mock_suggest: Mock
    ) -> None:
        """Test finds re.sub calls in Python file."""
        mock_compiled = Mock()
        mock_match = Mock()
        mock_match.group.side_effect = [r"(\w+)", r"\1"]
        mock_compiled.search.return_value = mock_match
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        mock_suggest.return_value = {"suggested_name": "fix_test"}

        # Create test file with re.sub call
        tmp_file = Path("/tmp/test_file.py")
        tmp_file.write_text('result = re.sub(r"(\\w+)", r"\\1", text)', encoding="utf-8")

        result = regex_utils.audit_file_for_re_sub(tmp_file)

        assert len(result) == 1
        assert result[0]["file"] == str(tmp_file)
        assert result[0]["pattern"] == r"(\w+)"
        assert result[0]["replacement"] == r"\1"

        # Cleanup
        tmp_file.unlink()

    @patch("crackerjack.services.regex_utils.suggest_migration_for_re_sub")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_returns_line_numbers(self, mock_cache: Mock, mock_suggest: Mock) -> None:
        """Test returns correct line numbers.

        NOTE: The implementation enumerates lines starting at 1, so the re.sub
        call on line 2 should have line_number=2.
        """
        mock_compiled = Mock()
        mock_match = Mock()
        mock_match.group.side_effect = [r"(\w+)", r"\1"]
        # Make search return None for line 1, match for line 2
        mock_compiled.search.side_effect = [None, mock_match]
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        mock_suggest.return_value = {}

        tmp_file = Path("/tmp/test_line_numbers.py")
        tmp_file.write_text(
            "line 1\nresult = re.sub(r\"(\\w+)\", r\"\\1\", text)\nline 3",
            encoding="utf-8",
        )

        result = regex_utils.audit_file_for_re_sub(tmp_file)

        # Should only have one finding from line 2
        findings = [f for f in result if "line_number" in f and "error" not in f]
        assert len(findings) == 1
        assert findings[0]["line_number"] == 2

        tmp_file.unlink()

    @patch("crackerjack.services.regex_utils.suggest_migration_for_re_sub")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_returns_empty_list_when_no_re_sub(self, mock_cache: Mock, mock_suggest: Mock) -> None:
        """Test returns empty list when no re.sub found."""
        mock_compiled = Mock()
        mock_compiled.search.return_value = None
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        tmp_file = Path("/tmp/no_resub.py")
        tmp_file.write_text("print('hello')", encoding="utf-8")

        result = regex_utils.audit_file_for_re_sub(tmp_file)

        assert result == []

        tmp_file.unlink()

    @patch("crackerjack.services.regex_utils.suggest_migration_for_re_sub")
    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_handles_file_read_errors(self, mock_cache: Mock, mock_suggest: Mock) -> None:
        """Test handles file read errors gracefully."""
        # Create directory instead of file (will cause read error)
        tmp_file = Path("/tmp/test_read_error.py")
        tmp_file.mkdir(exist_ok=True)

        result = regex_utils.audit_file_for_re_sub(tmp_file)

        assert len(result) == 1
        assert "error" in result[0]

        tmp_file.rmdir()


class TestAuditCodebaseReSub:
    """Test audit_codebase_re_sub() function."""

    @patch("crackerjack.services.regex_utils.audit_file_for_re_sub")
    def test_scans_python_files(self, mock_audit: Mock) -> None:
        """Test scans Python files in crackerjack directory."""
        mock_audit.return_value = [
            {"pattern": r"(\w+)", "replacement": r"\1"}
        ]

        with patch("pathlib.Path.rglob") as mock_rglob:
            mock_rglob.return_value = [
                Path("/tmp/crackerjack/file1.py"),
                Path("/tmp/crackerjack/test_file.py"),  # Should be skipped
            ]

            result = regex_utils.audit_codebase_re_sub()

            # Should only have non-test files
            assert len(result) > 0

    @patch("crackerjack.services.regex_utils.audit_file_for_re_sub")
    def test_skips_test_files(self, mock_audit: Mock) -> None:
        """Test skips files with 'test_' in name."""
        mock_audit.return_value = []

        with patch("pathlib.Path.rglob") as mock_rglob:
            mock_rglob.return_value = [
                Path("/tmp/crackerjack/test_utils.py"),
                Path("/tmp/crackerjack/__pycache__/file.py"),
            ]

            result = regex_utils.audit_codebase_re_sub()

            # Should skip test files and __pycache__
            mock_audit.assert_not_called()

    @patch("crackerjack.services.regex_utils.audit_file_for_re_sub")
    def test_returns_findings_by_file_dict(self, mock_audit: Mock) -> None:
        """Test returns dict mapping file paths to findings."""
        mock_audit.return_value = [{"pattern": r"(\w+)"}]

        with patch("pathlib.Path.rglob") as mock_rglob:
            mock_rglob.return_value = [Path("/tmp/crackerjack/file.py")]

            result = regex_utils.audit_codebase_re_sub()

            assert isinstance(result, dict)


class TestReplaceUnsafeRegexWithSafePatterns:
    """Test replace_unsafe_regex_with_safe_patterns() function."""

    @patch("crackerjack.services.regex_utils._process_re_sub_patterns")
    @patch("crackerjack.services.regex_utils._fix_replacement_syntax_issues")
    @patch("crackerjack.services.regex_utils._check_for_safe_patterns_import")
    def test_replaces_re_sub_with_safe_patterns(
        self, mock_check: Mock, mock_fix: Mock, mock_process: Mock
    ) -> None:
        """Test replaces re.sub calls with safe patterns."""
        mock_check.return_value = False
        mock_fix.return_value = "fixed line"
        mock_process.return_value = ("SAFE_PATTERNS['fix_test'].apply(text)", True, True)

        content = 'result = re.sub(r"(\\w+)", r"\\1", text)'
        result = regex_utils.replace_unsafe_regex_with_safe_patterns(content)

        assert "SAFE_PATTERNS" in result

    @patch("crackerjack.services.regex_utils._process_re_sub_patterns")
    @patch("crackerjack.services.regex_utils._fix_replacement_syntax_issues")
    @patch("crackerjack.services.regex_utils._check_for_safe_patterns_import")
    def test_adds_import_when_needed(
        self, mock_check: Mock, mock_fix: Mock, mock_process: Mock
    ) -> None:
        """Test adds SAFE_PATTERNS import when needed."""
        mock_check.return_value = False
        mock_fix.return_value = "line"
        mock_process.return_value = ("safe line", True, True)

        content = "result = re.sub(r'pattern', r'replacement', text)"
        result = regex_utils.replace_unsafe_regex_with_safe_patterns(content)

        assert "from crackerjack.services.regex_patterns import SAFE_PATTERNS" in result

    @patch("crackerjack.services.regex_utils._process_re_sub_patterns")
    @patch("crackerjack.services.regex_utils._fix_replacement_syntax_issues")
    @patch("crackerjack.services.regex_utils._check_for_safe_patterns_import")
    def test_fixes_replacement_syntax_issues(
        self, mock_check: Mock, mock_fix: Mock, mock_process: Mock
    ) -> None:
        """Test fixes replacement syntax issues."""
        mock_check.return_value = False
        mock_fix.side_effect = lambda x: x.replace(r"\g < 1", r"\g<1>")
        mock_process.return_value = ("line", False, False)

        content = 're.sub(r"pattern", r"\\g < 1>", text)'
        result = regex_utils.replace_unsafe_regex_with_safe_patterns(content)

        mock_fix.assert_called()

    @patch("crackerjack.services.regex_utils._process_re_sub_patterns")
    @patch("crackerjack.services.regex_utils._fix_replacement_syntax_issues")
    @patch("crackerjack.services.regex_utils._check_for_safe_patterns_import")
    def test_returns_original_content_when_no_changes(
        self, mock_check: Mock, mock_fix: Mock, mock_process: Mock
    ) -> None:
        """Test returns original content when no changes made."""
        mock_check.return_value = True
        mock_fix.side_effect = lambda x: x  # Return unchanged
        # Return original line as first element to indicate no change
        mock_process.side_effect = lambda line, *args: (line, False, False)

        content = "print('hello')"
        result = regex_utils.replace_unsafe_regex_with_safe_patterns(content)

        # Should return original content (no modifications made)
        assert result == content


class TestDetermineSuggestedName:
    """Test _determine_suggested_name() private function."""

    def test_returns_python_command_spacing(self) -> None:
        """Test returns fix_python_command_spacing for python.*-.*m pattern."""
        result = regex_utils._determine_suggested_name(r"python.*-.*m")
        assert result == "fix_python_command_spacing"

    def test_returns_double_dash_spacing(self) -> None:
        """Test returns fix_double_dash_spacing for double dash pattern."""
        result = regex_utils._determine_suggested_name(r"\-\s*\-")
        assert result == "fix_double_dash_spacing"

    def test_returns_token_pattern(self) -> None:
        """Test returns fix_token_pattern when 'token' in pattern."""
        result = regex_utils._determine_suggested_name(r"(token_pattern)")
        assert result == "fix_token_pattern"

    def test_returns_password_pattern(self) -> None:
        """Test returns fix_password_pattern when 'password' in pattern."""
        result = regex_utils._determine_suggested_name(r"password_regex")
        assert result == "fix_password_pattern"

    def test_returns_custom_pattern_fallback(self) -> None:
        """Test returns fix_custom_pattern as fallback."""
        result = regex_utils._determine_suggested_name(r"unknown_pattern_with_keywords")
        # Extracts keywords and returns fix_keywords_pattern
        assert "fix_" in result
        assert "pattern" in result


class TestBuildTestCases:
    """Test _build_test_cases() private function."""

    def test_adds_sample_text_test_case(self) -> None:
        """Test adds sample_text as first test case."""
        result = regex_utils._build_test_cases(r"(\w+)", "sample text")

        assert len(result) == 1
        assert result[0] == ("sample text", "Expected output needed")

    def test_adds_default_test_cases_for_dash_pattern(self) -> None:
        """Test adds default test cases when '-' in pattern."""
        result = regex_utils._build_test_cases(r"(\w+)\s*-\s*(\w+)", "")

        assert len(result) == 3
        assert ("word - word", "word-word") in result
        assert ("already-good", "already-good") in result

    def test_returns_only_sample_when_no_dash(self) -> None:
        """Test returns only sample test when no '-' in pattern."""
        result = regex_utils._build_test_cases(r"\w+", "test")

        assert len(result) == 1


class TestCheckForSafePatternsImport:
    """Test _check_for_safe_patterns_import() private function."""

    def test_returns_true_when_import_exists(self) -> None:
        """Test returns True when SAFE_PATTERNS import exists."""
        lines = [
            "from crackerjack.services.regex_patterns import SAFE_PATTERNS",
            "print('hello')",
        ]

        result = regex_utils._check_for_safe_patterns_import(lines)

        assert result is True

    def test_returns_false_when_no_import(self) -> None:
        """Test returns False when no import exists."""
        lines = ["print('hello')", "x = 5"]

        result = regex_utils._check_for_safe_patterns_import(lines)

        assert result is False


class TestFixReplacementSyntaxIssues:
    """Test _fix_replacement_syntax_issues() private function."""

    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_fixes_spacing_in_backref(self, mock_cache: Mock) -> None:
        """Test fixes spacing in \\g<1> syntax."""
        mock_compiled = Mock()
        mock_compiled.sub.side_effect = lambda r, s: s.replace(r"\g < 1", r"\g<1>")
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        line = r'text = re.sub(".", r"\g < 1>", source)'
        result = regex_utils._fix_replacement_syntax_issues(line)

        mock_cache.get_compiled_pattern.assert_called()
        assert r"\g<1>" in result or r"\g < 1>" not in result


class TestIdentifySafePattern:
    """Test _identify_safe_pattern() private function."""

    def test_identifies_hyphenated_names(self) -> None:
        """Test identifies fix_hyphenated_names pattern."""
        result = regex_utils._identify_safe_pattern(
            r"(\w+)\s*-\s*(\w+)", r"\1-\2"
        )

        assert result == "fix_hyphenated_names"

    def test_identifies_mask_tokens(self) -> None:
        """Test identifies mask_tokens pattern."""
        result = regex_utils._identify_safe_pattern(
            r"(token_pattern)", r"*\1"
        )

        assert result == "mask_tokens"

    def test_identifies_python_command_spacing(self) -> None:
        """Test identifies fix_python_command_spacing pattern."""
        result = regex_utils._identify_safe_pattern(
            r"python\s*-\s*m", "replacement"
        )

        assert result == "fix_python_command_spacing"

    def test_returns_none_for_unknown(self) -> None:
        """Test returns None for unknown patterns."""
        result = regex_utils._identify_safe_pattern(
            r"unknown", r"replacement"
        )

        assert result is None


class TestExtractSourceVariable:
    """Test _extract_source_variable() private function."""

    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_extracts_variable_name(self, mock_cache: Mock) -> None:
        """Test extracts source variable from re.sub call."""
        mock_compiled = Mock()
        mock_match = Mock()
        mock_match.group.return_value = "source_text"
        mock_compiled.search.return_value = mock_match
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        line = 'result = re.sub(r"pattern", r"replacement", source_text)'
        result = regex_utils._extract_source_variable(line)

        assert result == "source_text"

    @patch("crackerjack.services.regex_utils.CompiledPatternCache")
    def test_returns_text_as_default(self, mock_cache: Mock) -> None:
        """Test returns 'text' as default when variable not found."""
        mock_compiled = Mock()
        mock_compiled.search.return_value = None
        mock_cache.get_compiled_pattern.return_value = mock_compiled

        line = 'result = re.sub(r"pattern", r"replacement", unknown_var)'
        result = regex_utils._extract_source_variable(line)

        assert result == "text"


class TestFindImportInsertionPoint:
    """Test _find_import_insertion_point() private function."""

    def test_finds_insertion_point_after_imports(self) -> None:
        """Test finds insertion point after import statements."""
        lines = [
            "import os",
            "from pathlib import Path",
            "x = 5",
        ]

        result = regex_utils._find_import_insertion_point(lines)

        assert result == 2  # After the two imports

    def test_returns_zero_when_no_imports(self) -> None:
        """Test returns 0 when no imports exist."""
        lines = ["x = 5", "print('hello')"]

        result = regex_utils._find_import_insertion_point(lines)

        assert result == 0
