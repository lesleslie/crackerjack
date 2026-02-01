"""Tests for ComplexipyJSONParser with line number extraction.

Tests the three-tier fallback strategy for complexity issues:
- Tier 1: AST-based line number extraction in parser
- Tier 2: Function name search in agent
- Tier 3: Full file analysis as fallback
"""

import json
import pytest
from pathlib import Path

from crackerjack.parsers.json_parsers import ComplexipyJSONParser
from crackerjack.agents.base import Issue, IssueType, Priority


class TestComplexipyJSONParserLineNumberExtraction:
    """Test Tier 1: AST-based line number extraction."""

    @pytest.fixture
    def parser(self):
        """Create ComplexipyJSONParser instance."""
        return ComplexipyJSONParser(max_complexity=15)

    @pytest.fixture
    def sample_file(self, tmp_path):
        """Create a sample Python file with known line numbers."""
        test_file = tmp_path / "sample.py"
        test_file.write_text("""
def simple_function():
    '''Simple function with complexity 1.'''
    return True

def medium_function(x):
    '''Medium complexity function around line 7.'''
    if x > 10:
        return True
    elif x < 5:
        return False
    return None

class MyClass:
    def method_with_high_complexity(self, data):
        '''Method with complexity > 15, around line 21.'''
        results = []
        for item in data:
            if item.valid:
                for sub_item in item.nested:
                    if sub_item.value > 0:
                        if sub_item.active:
                            if sub_item.ready:
                                results.append(sub_item)
        return results

def another_function():
    '''Another simple function around line 36.'''
    pass
""")
        return test_file

    def test_extract_line_number_simple_function(self, parser, sample_file):
        """Test extracting line number for simple function."""
        line_num = parser._extract_line_number_tier1(
            str(sample_file), "simple_function"
        )

        assert line_num == 2  # Line 2 (after initial blank line)

    def test_extract_line_number_medium_function(self, parser, sample_file):
        """Test extracting line number for medium function."""
        line_num = parser._extract_line_number_tier1(
            str(sample_file), "medium_function"
        )

        assert line_num == 6

    def test_extract_line_number_class_method(self, parser, sample_file):
        """Test extracting line number for class method."""
        # Test with ClassName::method format (complexipy's format)
        line_num = parser._extract_line_number_tier1(
            str(sample_file), "MyClass::method_with_high_complexity"
        )

        assert line_num == 15  # Method starts at line 15

    def test_extract_line_number_with_cache(self, parser, sample_file):
        """Test that line numbers are cached for performance."""
        # First call
        line_num1 = parser._extract_line_number_tier1(
            str(sample_file), "simple_function"
        )

        # Second call should use cache
        line_num2 = parser._extract_line_number_tier1(
            str(sample_file), "simple_function"
        )

        assert line_num1 == line_num2 == 2

    def test_extract_line_number_nonexistent_function(self, parser, sample_file):
        """Test extracting line number for non-existent function."""
        line_num = parser._extract_line_number_tier1(
            str(sample_file), "nonexistent_function"
        )

        assert line_num is None

    def test_extract_line_number_nonexistent_file(self, parser):
        """Test extracting line number for non-existent file."""
        line_num = parser._extract_line_number_tier1(
            "/nonexistent/file.py", "some_function"
        )

        assert line_num is None

    def test_extract_line_number_python_file(self, parser, tmp_path):
        """Test that non-Python files are skipped."""
        non_py_file = tmp_path / "data.txt"
        non_py_file.write_text("not python code")

        line_num = parser._extract_line_number_tier1(
            str(non_py_file), "some_function"
        )

        assert line_num is None


class TestComplexipyJSONParserParsing:
    """Test ComplexipyJSONParser parsing with line numbers."""

    @pytest.fixture
    def parser(self):
        """Create ComplexipyJSONParser instance."""
        return ComplexipyJSONParser(max_complexity=15)

    @pytest.fixture
    def complexipy_output(self, tmp_path):
        """Create sample complexipy JSON output."""
        # Create actual Python file to reference
        test_file = tmp_path / "complex.py"
        test_file.write_text("""
def complex_function():
    '''Complex function with multiple branches.'''
    if x > 10:
        if y < 5:
            if z == 3:
                return True
    return False
""")

        return [
            {
                "complexity": 20,
                "file_name": "complex.py",
                "function_name": "complex_function",
                "path": str(test_file),
            },
            {
                "complexity": 5,
                "file_name": "complex.py",
                "function_name": "simple_function",
                "path": str(test_file),
            },
        ]

    def test_parse_with_line_number_extraction(self, parser, complexipy_output):
        """Test that parser extracts line numbers during parsing."""
        issues = parser.parse_json(complexipy_output)

        # Should only parse functions exceeding threshold (complexity > 15)
        assert len(issues) == 1

        # Line number should be extracted via AST
        assert issues[0].line_number == 2  # complex_function starts at line 2
        assert "complex_function" in issues[0].message
        assert "20" in issues[0].message  # Complexity value

    def test_parse_filters_by_threshold(self, parser, complexipy_output):
        """Test that only functions above threshold are parsed."""
        issues = parser.parse_json(complexipy_output)

        # Only complexity 20 should be included (threshold is 15)
        assert len(issues) == 1
        assert issues[0].details[0] == "complexity: 20"

    def test_parse_includes_line_number_in_details(self, parser, complexipy_output):
        """Test that line number is included in issue details."""
        issues = parser.parse_json(complexipy_output)

        # Check that line number detail is present
        line_detail = [d for d in issues[0].details if "line_number:" in d]
        assert len(line_detail) == 1
        assert "2" in line_detail[0]  # Line 2

    def test_parse_with_class_method_format(self, parser, tmp_path):
        """Test parsing with ClassName::method_name format."""
        test_file = tmp_path / "methods.py"
        test_file.write_text("""
class MyHandler:
    def complex_method(self, data):
        '''Complex method with many branches.'''
        for item in data:
            for sub in item.items:
                if sub.valid:
                    return True
        return False
""")

        output = [
            {
                "complexity": 18,
                "file_name": "methods.py",
                "function_name": "MyHandler::complex_method",
                "path": str(test_file),
            }
        ]

        issues = parser.parse_json(output)

        assert len(issues) == 1
        assert issues[0].line_number == 3  # complex_method starts at line 3

    def test_parse_with_no_line_number_fallback(self, parser, tmp_path):
        """Test parsing when line number cannot be extracted."""
        # Create file with syntax error to prevent AST parsing
        test_file = tmp_path / "invalid.py"
        test_file.write_text("def broken(\n")  # Invalid syntax

        output = [
            {
                "complexity": 20,
                "file_name": "invalid.py",
                "function_name": "broken",
                "path": str(test_file),
            }
        ]

        issues = parser.parse_json(output)

        # Should still parse the issue, but without line number
        assert len(issues) == 1
        assert issues[0].line_number is None
        # Detail should indicate agent will search by name
        assert any("agent will search by function name" in d for d in issues[0].details)


class TestComplexipyJSONParserGetIssueCount:
    """Test issue counting with threshold filtering."""

    @pytest.fixture
    def parser(self):
        """Create ComplexipyJSONParser instance."""
        return ComplexipyJSONParser(max_complexity=15)

    def test_get_issue_count_filters_by_threshold(self, parser):
        """Test that issue count only includes functions above threshold."""
        data = [
            {"complexity": 10, "file_name": "a.py", "function_name": "func1", "path": "a.py"},
            {"complexity": 20, "file_name": "b.py", "function_name": "func2", "path": "b.py"},
            {"complexity": 16, "file_name": "c.py", "function_name": "func3", "path": "c.py"},
            {"complexity": 5, "file_name": "d.py", "function_name": "func4", "path": "d.py"},
        ]

        count = parser.get_issue_count(data)

        # Only 20, 16 are > 15
        assert count == 2

    def test_get_issue_count_empty_list(self, parser):
        """Test issue count with empty list."""
        count = parser.get_issue_count([])
        assert count == 0

    def test_get_issue_count_non_list(self, parser):
        """Test issue count with non-list data."""
        count = parser.get_issue_count({"not": "a list"})
        assert count == 0
