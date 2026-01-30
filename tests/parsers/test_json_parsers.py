"""Tests for JSON-based parsers."""

import json
import pytest

from crackerjack.parsers.factory import ParserFactory
from crackerjack.parsers.json_parsers import RuffJSONParser, MypyJSONParser, BanditJSONParser
from crackerjack.agents.base import Issue


class TestRuffJSONParser:
    """Test ruff JSON parser."""

    @pytest.fixture
    def ruff_json_output(self):
        """Sample ruff JSON output with 16 issues."""
        return json.dumps([
            {
                "filename": "mahavishnu/core/auth.py",
                "location": {"row": 51, "column": 34},
                "code": "UP017",
                "message": "Use `datetime.UTC` alias",
                "fix": {"applicability": "automatic"}
            },
            {
                "filename": "mahavishnu/core/auth.py",
                "location": {"row": 99, "column": 28},
                "code": "UP017",
                "message": "Use `datetime.UTC` alias"
            },
            {
                "filename": "mahavishnu/core/backup_recovery.py",
                "location": {"row": 3, "column": 1},
                "code": "I001",
                "message": "Import block is un-sorted or un-formatted"
            },
        ])

    def test_parse_ruff_json(self, ruff_json_output):
        """Test parsing ruff JSON output."""
        parser = RuffJSONParser()
        data = json.loads(ruff_json_output)

        issues = parser.parse_json(data)

        assert len(issues) == 3
        assert issues[0].file_path == "mahavishnu/core/auth.py"
        assert issues[0].line_number == 51
        assert "UP017" in issues[0].message
        assert issues[0].details[0] == "code: UP017"
        assert issues[0].details[1] == "fixable: True"  # Has 'fix' field

        assert issues[1].line_number == 99
        assert issues[1].details[1] == "fixable: False"  # No 'fix' field

        assert issues[2].file_path == "mahavishnu/core/backup_recovery.py"
        assert "I001" in issues[2].message

    def test_get_issue_count(self, ruff_json_output):
        """Test extracting issue count."""
        parser = RuffJSONParser()
        data = json.loads(ruff_json_output)

        count = parser.get_issue_count(data)
        assert count == 3


class TestMypyJSONParser:
    """Test mypy JSON parser."""

    @pytest.fixture
    def mypy_json_output(self):
        """Sample mypy JSON output."""
        return json.dumps([
            {
                "file": "crackerjack/core/auth.py",
                "line": 51,
                "column": 34,
                "message": "Incompatible return value type",
                "severity": "error"
            },
            {
                "file": "crackerjack/core/session.py",
                "line": 100,
                "column": 5,
                "message": "Argument 1 has incompatible type",
                "severity": "warning"
            }
        ])

    def test_parse_mypy_json(self, mypy_json_output):
        """Test parsing mypy JSON output."""
        parser = MypyJSONParser()
        data = json.loads(mypy_json_output)

        issues = parser.parse_json(data)

        assert len(issues) == 2
        assert issues[0].file_path == "crackerjack/core/auth.py"
        assert issues[0].line_number == 51
        assert issues[0].severity.name == "HIGH"  # error

        assert issues[1].line_number == 100
        assert issues[1].severity.name == "MEDIUM"  # warning


class TestBanditJSONParser:
    """Test bandit JSON parser."""

    @pytest.fixture
    def bandit_json_output(self):
        """Sample bandit JSON output."""
        return json.dumps({
            "results": [
                {
                    "filename": "app.py",
                    "line_number": 42,
                    "issue_text": "A Flask app appears to be run with debug=True",
                    "issue_severity": "MEDIUM",
                    "test_id": "B201",
                    "test_name": "flask_debug_true"
                }
            ]
        })

    def test_parse_bandit_json(self, bandit_json_output):
        """Test parsing bandit JSON output."""
        parser = BanditJSONParser()
        data = json.loads(bandit_json_output)

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].file_path == "app.py"
        assert issues[0].line_number == 42
        assert "B201" in issues[0].message
        assert "Flask app appears to be run with debug=True" in issues[0].message

    def test_get_issue_count(self, bandit_json_output):
        """Test extracting issue count."""
        parser = BanditJSONParser()
        data = json.loads(bandit_json_output)

        count = parser.get_issue_count(data)
        assert count == 1


class TestParserFactory:
    """Test parser factory with validation."""

    @pytest.fixture
    def ruff_json_output(self):
        """Sample ruff JSON output."""
        return json.dumps([
            {"filename": "test.py", "location": {"row": 10}, "code": "UP017", "message": "Use datetime.UTC"},
            {"filename": "test.py", "location": {"row": 20}, "code": "I001", "message": "Import unsorted"}
        ])

    def test_parse_with_validation_success(self, ruff_json_output):
        """Test successful parsing with validation."""
        factory = ParserFactory()

        issues = factory.parse_with_validation(
            tool_name="ruff",
            output=ruff_json_output,
            expected_count=2
        )

        assert len(issues) == 2

    def test_parse_with_validation_mismatch(self, ruff_json_output):
        """Test validation failure on count mismatch."""
        from crackerjack.parsers.factory import ParsingError

        factory = ParserFactory()

        with pytest.raises(ParsingError) as exc_info:
            factory.parse_with_validation(
                tool_name="ruff",
                output=ruff_json_output,
                expected_count=5  # Wrong count
            )

        error = exc_info.value
        assert "Issue count mismatch" in str(error)
        assert error.expected_count == 5
        assert error.actual_count == 2

    def test_parser_caching(self, ruff_json_output):
        """Test that parser instances are cached."""
        factory = ParserFactory()

        parser1 = factory.create_parser("ruff")
        parser2 = factory.create_parser("ruff")

        assert parser1 is parser2  # Same instance (cached)
