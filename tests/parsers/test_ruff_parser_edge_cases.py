"""
Test edge cases for RuffJSONParser fix.

These tests address critical gaps identified in multi-agent review.
"""

import pytest
from crackerjack.parsers.json_parsers import RuffJSONParser
from crackerjack.agents.base import IssueType, Priority


class TestRuffJSONParserEdgeCases:
    """Edge case tests for RuffJSONParser identified in code review."""

    def test_parse_json_with_non_list_input(self):
        """Test that non-list input returns empty list gracefully."""
        parser = RuffJSONParser()

        # Dict input
        assert parser.parse_json({}) == []

        # String input
        assert parser.parse_json("not a list") == []

        # None input
        assert parser.parse_json(None) == []

    def test_parse_json_with_malformed_items(self):
        """Test handling of malformed items in list."""
        parser = RuffJSONParser()

        # Non-dict items
        data = ["string", 123, None]
        assert parser.parse_json(data) == []

        # Missing required fields
        data = [{"filename": "test.py"}]  # Missing location, code, message
        assert parser.parse_json(data) == []

        # Invalid location format
        data = [{
            "filename": "test.py",
            "location": "invalid",
            "code": "F401",
            "message": "Unused"
        }]
        assert parser.parse_json(data) == []

    def test_parse_json_error_recovery(self):
        """Test that parser continues after individual item failures."""
        parser = RuffJSONParser()

        # Mix of valid and invalid items
        data = [
            {
                "filename": "valid.py",
                "location": {"row": 10},
                "code": "F401",
                "message": "Unused"
            },
            "invalid item",
            {
                "filename": "valid2.py",
                "location": {"row": 20},
                "code": "F811",
                "message": "Duplicate"
            }
        ]
        issues = parser.parse_json(data)

        # Should parse the 2 valid items, skip invalid
        assert len(issues) == 2
        assert issues[0].file_path == "valid.py"
        assert issues[1].file_path == "valid2.py"

    @pytest.mark.parametrize("code,expected_type,expected_severity", [
        ("C901", IssueType.COMPLEXITY, Priority.HIGH),
        ("S101", IssueType.SECURITY, Priority.HIGH),
        ("F401", IssueType.IMPORT_ERROR, Priority.MEDIUM),
        ("F811", IssueType.FORMATTING, Priority.LOW),
        ("UP017", IssueType.FORMATTING, Priority.LOW),
    ])
    def test_code_mapping(self, code, expected_type, expected_severity):
        """Test that ruff codes map to correct type and severity."""
        parser = RuffJSONParser()

        data = [{
            "filename": "test.py",
            "location": {"row": 10},
            "code": code,
            "message": "Test"
        }]
        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].type == expected_type
        assert issues[0].severity == expected_severity

    def test_regression_dict_vs_list_bug(self):
        """Regression test for original bug: dict input should return empty list.

        Original bug: Parser found '{' inside array and tried to extract object.
        This test ensures we properly detect array vs object.
        """
        parser = RuffJSONParser()

        # Simulate ruff JSON array output
        array_data = [{
            "filename": "test.py",
            "location": {"row": 10, "column": 5},
            "code": "F401",
            "message": "Unused import"
        }]

        issues = parser.parse_json(array_data)
        assert len(issues) == 1
        assert issues[0].file_path == "test.py"
        assert issues[0].line_number == 10

        # Dict input (incorrect type) should return empty list
        dict_data = {
            "filename": "test.py",
            "location": {"row": 10},
            "code": "F401",
            "message": "Unused import"
        }

        issues = parser.parse_json(dict_data)
        assert len(issues) == 0  # Dict not supported, return empty
