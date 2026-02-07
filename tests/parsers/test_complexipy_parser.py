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


class TestComplexipyJSONParserParseMethod:
    """Test the parse() method with file-based JSON output."""

    @pytest.fixture
    def parser(self):
        """Create ComplexipyJSONParser instance."""
        return ComplexipyJSONParser(max_complexity=15)

    def test_parse_multiline_output_with_json_path(self, parser, tmp_path):
        """Test that re.DOTALL enables matching across newlines."""
        # Create actual JSON file
        json_file = tmp_path / "complexipy_results.json"
        json_file.write_text(
            '[{"complexity": 20, "file_name": "test.py", "function_name": "func", "path": "test.py"}]'
        )

        output = f"""Results saved at
{json_file}
Some other text here"""

        issues = parser.parse(output, "complexipy")

        assert len(issues) == 1
        assert issues[0].details[0] == "complexity: 20"

    def test_parse_no_results_saved_message(self, parser):
        """Test parse() when 'Results saved at' is missing."""
        output = "No results here"
        issues = parser.parse(output, "complexipy")
        assert issues == []

    def test_parse_json_file_not_found(self, parser):
        """Test parse() when extracted JSON path doesn't exist."""
        output = """Results saved at
/nonexistent/path/to/file.json"""
        issues = parser.parse(output, "complexipy")
        assert issues == []

    def test_parse_malformed_json(self, parser, tmp_path, caplog):
        """Test parsing handles malformed JSON gracefully."""
        import logging

        json_file = tmp_path / "malformed.json"
        json_file.write_text('{"invalid": json syntax}')  # Missing quotes

        output = f"Results saved at\n{json_file}"

        with caplog.at_level(logging.ERROR):
            issues = parser.parse(output, "complexipy")

        assert issues == []
        assert "Error reading/parsing complexipy JSON file" in caplog.text

    def test_parse_json_wrong_structure(self, parser, tmp_path, caplog):
        """Test parsing when JSON is dict instead of list."""
        import logging

        json_file = tmp_path / "wrong_structure.json"
        json_file.write_text('{"files": []}')  # Dict, not list

        output = f"Results saved at\n{json_file}"

        with caplog.at_level(logging.WARNING):
            issues = parser.parse(output, "complexipy")

        assert issues == []
        assert "not a list" in caplog.text

    def test_parse_json_missing_required_fields(self, parser, tmp_path, caplog):
        """Test parsing handles missing required fields."""
        import logging

        json_file = tmp_path / "missing_fields.json"
        json_file.write_text('[{"complexity": 20, "file_name": "test.py"}]')  # Missing function_name, path

        output = f"Results saved at\n{json_file}"

        with caplog.at_level(logging.WARNING):
            issues = parser.parse(output, "complexipy")

        assert issues == []
        assert "missing required fields" in caplog.text

    def test_parse_multiple_json_paths_chooses_first(self, parser, tmp_path):
        """Test that parser extracts the FIRST .json path after 'Results saved at'."""
        # Create the expected JSON file
        expected_json = tmp_path / "complexipy_results.json"
        expected_json.write_text(
            '[{"complexity": 20, "file_name": "test.py", "function_name": "func", "path": "test.py"}]'
        )

        # Create a decoy JSON file
        decoy_json = tmp_path / "other.json"
        decoy_json.write_text("[]")

        output = f"""Results saved at
{expected_json}
Also check {decoy_json}
And another_file.json"""

        issues = parser.parse(output, "complexipy")

        # Should only parse the expected file, not decoys
        assert len(issues) == 1
        assert "func" in issues[0].message

    def test_parse_regex_requires_dotall_for_multiline(self):
        """Test that regex pattern works with multiline output."""
        import re

        pattern = r"Results saved at\s+(.+?\.json)"

        # Multiline output like complexipy produces
        multiline_output = """Results saved at
/path/to/file.json
more text"""

        # With DOTALL (as implemented in the parser), should match
        match_dotall = re.search(pattern, multiline_output, re.DOTALL)
        assert match_dotall is not None
        assert match_dotall.group(1).strip() == "/path/to/file.json"

        # The key is that DOTALL ensures . matches newlines throughout the pattern,
        # making it more robust for complex multiline outputs
        assert ".json" in match_dotall.group(0)


class TestComplexipyJSONParserMalformedData:
    """Test error handling for malformed JSON data."""

    @pytest.fixture
    def parser(self):
        """Create ComplexipyJSONParser instance."""
        return ComplexipyJSONParser(max_complexity=15)

    def test_parse_json_with_syntax_error(self, parser, tmp_path, caplog):
        """Test parsing JSON with syntax errors."""
        import logging

        json_file = tmp_path / "syntax_error.json"
        json_file.write_text('{"unclosed": true')  # Missing closing brace

        output = f"Results saved at\n{json_file}"

        with caplog.at_level(logging.ERROR):
            issues = parser.parse(output, "complexipy")

        assert issues == []
        assert any("Error reading/parsing" in record.message for record in caplog.records)

    def test_parse_json_empty_array(self, parser, tmp_path):
        """Test parsing empty JSON array."""
        json_file = tmp_path / "empty.json"
        json_file.write_text("[]")

        output = f"Results saved at\n{json_file}"

        issues = parser.parse(output, "complexipy")

        assert issues == []

    def test_parse_json_with_null_values(self, parser, tmp_path):
        """Test parsing JSON with null values in required fields."""
        json_file = tmp_path / "null_values.json"
        json_file.write_text(
            '[{"complexity": null, "file_name": null, "function_name": null, "path": null}]'
        )

        output = f"Results saved at\n{json_file}"

        issues = parser.parse(output, "complexipy")

        # Should skip items with null required fields
        assert len(issues) == 0


class TestComplexipyJSONParserIntegration:
    """Integration tests with real complexipy tool (if available)."""

    @pytest.fixture
    def parser(self):
        """Create ComplexipyJSONParser instance."""
        return ComplexipyJSONParser(max_complexity=15)

    @pytest.mark.integration
    @pytest.mark.skipif(
        True,  # Skip by default, enable with: pytest -m integration --runxfail
        reason="Integration test - enable manually to test with real complexipy",
    )
    def test_integration_with_real_complexipy(self, parser, tmp_path):
        """Test parser with real complexipy output."""
        import shutil
        import subprocess

        if not shutil.which("complexipy"):
            pytest.skip("complexipy not installed")

        # Create test Python file with high complexity
        test_file = tmp_path / "complex_code.py"
        test_file.write_text(
            """
def complex_function(x):
    '''Function with high complexity.'''
    if x > 10:
        if x < 20:
            if x == 15:
                if x > 0:
                    return True
    return False
"""
        )

        # Run complexipy
        result = subprocess.run(
            ["complexipy", str(test_file), "--output-json"],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )

        # Parse output
        issues = parser.parse(result.stdout, "complexipy")

        # Verify we got the complexity issue
        assert len(issues) > 0, "Should find at least one complex function"
        assert any("complex_function" in issue.message for issue in issues)

    def test_integration_realistic_output(self, parser, tmp_path):
        """Test with realistic complexipy output format."""
        # Create a realistic JSON file
        json_file = tmp_path / "complexipy_results_2026_02_06__12-00-00.json"
        test_py = tmp_path / "module.py"
        test_py.write_text(
            """
class MyClass:
    def complex_method(self, data):
        '''Complex method.'''
        results = []
        for item in data:
            if item.valid:
                for sub in item.items:
                    if sub.value > 0:
                        if sub.active:
                            results.append(sub)
        return results
"""
        )

        json_file.write_text(
            json.dumps(
                [
                    {
                        "complexity": 18,
                        "file_name": "module.py",
                        "function_name": "MyClass::complex_method",
                        "path": str(test_py),
                    }
                ]
            )
        )

        # Realistic complexipy stdout format
        output = f"""Analyzing {tmp_path}
Found 1 complex functions

──────────────────────────────── 🐙 complexipy ─────────────────────────────────
Results saved at
{json_file}

Summary: 1 function(s) exceed threshold 15
"""

        issues = parser.parse(output, "complexipy")

        assert len(issues) == 1
        assert issues[0].line_number == 3  # complex_method starts at line 3 (after initial blank)
        assert "MyClass::complex_method" in issues[0].message
        assert issues[0].details[0] == "complexity: 18"
