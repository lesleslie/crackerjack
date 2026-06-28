"""Tests for json_parsers module - comprehensive coverage for all JSON parsers."""

import json
import typing as t
from unittest.mock import patch, MagicMock, mock_open

import pytest

from crackerjack.parsers.json_parsers import (
    RuffJSONParser,
    MypyJSONParser,
    BanditJSONParser,
    SemgrepJSONParser,
    PipAuditJSONParser,
    GitleaksJSONParser,
    PytestJSONParser,
    register_json_parsers,
)
from crackerjack.agents.base import Issue, IssueType, Priority


# Mirrors the union ``dict[str, object] | list[object]`` accepted by the
# parsers' ``parse_json`` / ``get_issue_count`` methods. The parsers inspect
# JSON-shaped input defensively, so the static union is intentionally wide.
_JsonInput = t.Union[dict[str, t.Any], list[t.Any]]


def _json_input(value: t.Any) -> _JsonInput:
    """Cast a JSON-shaped literal to the parser's expected union type."""
    return t.cast("_JsonInput", value)


class TestRuffJSONParserCoverage:
    """Extended tests for RuffJSONParser - beyond existing test_ruff_parser_edge_cases.py."""

    @pytest.fixture
    def parser(self):
        return RuffJSONParser()

    def test_parse_json_with_fix_field(self, parser):
        """Test that fix field is properly detected."""
        data = [{
            "filename": "test.py",
            "location": {"row": 10, "column": 5},
            "code": "F401",
            "message": "Unused import",
            "fix": {"applicability": "automatic"}
        }]
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert "fixable: True" in issues[0].details

    def test_parse_json_without_fix_field(self, parser):
        """Test that missing fix field results in fixable: False."""
        data = [{
            "filename": "test.py",
            "location": {"row": 10, "column": 5},
            "code": "F811",
            "message": "Redefinition"
        }]
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert "fixable: False" in issues[0].details

    def test_parse_json_with_url_field(self, parser):
        """Test that URL field is included in details."""
        data = [{
            "filename": "test.py",
            "location": {"row": 10, "column": 5},
            "code": "UP017",
            "message": "Use datetime.UTC",
            "url": "https://docs.python.org/3/library/datetime.html"
        }]
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert any("url:" in d for d in issues[0].details)

    def test_extract_line_number_from_location_with_row(self, parser):
        """Test line number extraction from location dict."""
        location = {"row": 42, "column": 10}
        line_num = parser._extract_line_number_from_location(location)
        assert line_num == 42

    def test_extract_line_number_from_location_with_int(self, parser):
        """Test line number extraction from integer."""
        line_num = parser._extract_line_number_from_location(42)
        assert line_num is None  # Not a dict

    def test_extract_line_number_from_location_with_string(self, parser):
        """Test line number extraction from string."""
        line_num = parser._extract_line_number_from_location("42")
        assert line_num is None

    def test_issue_type_code_prefix_UP(self, parser):
        """Test UP prefix maps to FORMATTING."""
        assert parser._get_issue_type("UP017") == IssueType.FORMATTING

    def test_issue_type_code_prefix_C(self, parser):
        """Test C prefix maps to COMPLEXITY."""
        assert parser._get_issue_type("C901") == IssueType.COMPLEXITY

    def test_issue_type_code_prefix_PE(self, parser):
        """Test PE prefix maps to PERFORMANCE."""
        assert parser._get_issue_type("PERF001") == IssueType.PERFORMANCE

    def test_issue_type_code_prefix_F4(self, parser):
        """Test F4 prefix maps to IMPORT_ERROR."""
        assert parser._get_issue_type("F401") == IssueType.IMPORT_ERROR

    def test_issue_type_code_prefix_F8(self, parser):
        """Test F8 prefix maps to FORMATTING."""
        assert parser._get_issue_type("F821") == IssueType.FORMATTING

    def test_issue_type_code_E999(self, parser):
        """Test E999 maps to TYPE_ERROR."""
        assert parser._get_issue_type("E999") == IssueType.TYPE_ERROR

    def test_issue_type_code_E502(self, parser):
        """Test E502 maps to TYPE_ERROR."""
        assert parser._get_issue_type("E502") == IssueType.TYPE_ERROR

    def test_issue_type_code_prefix_S(self, parser):
        """Test S prefix maps to SECURITY."""
        assert parser._get_issue_type("S101") == IssueType.SECURITY

    def test_issue_type_code_prefix_PLR(self, parser):
        """Test PLR prefix maps to COMPLEXITY."""
        assert parser._get_issue_type("PLR0913") == IssueType.COMPLEXITY

    def test_issue_type_code_F(self, parser):
        """Test F prefix defaults to FORMATTING."""
        # F401 hits F4, F811 hits F8. Use codes outside those handlers.
        assert parser._get_issue_type("F401") == IssueType.IMPORT_ERROR
        assert parser._get_issue_type("F811") == IssueType.FORMATTING
        assert parser._get_issue_type("F111") == IssueType.FORMATTING

    def test_issue_type_code_E(self, parser):
        """Test E prefix defaults to FORMATTING."""
        assert parser._get_issue_type("E501") == IssueType.FORMATTING

    def test_issue_type_code_W(self, parser):
        """Test W prefix defaults to FORMATTING."""
        assert parser._get_issue_type("W503") == IssueType.FORMATTING

    def test_severity_C9(self, parser):
        """Test C9 code maps to HIGH severity."""
        assert parser._get_severity("C901") == Priority.HIGH

    def test_severity_S(self, parser):
        """Test S code maps to HIGH severity."""
        assert parser._get_severity("S101") == Priority.HIGH

    def test_severity_F4(self, parser):
        """Test F4 code maps to MEDIUM severity."""
        assert parser._get_severity("F401") == Priority.MEDIUM

    def test_severity_other(self, parser):
        """Test other codes map to LOW severity."""
        assert parser._get_severity("F811") == Priority.LOW

    def test_get_issue_count_list(self, parser):
        """Test issue count with list input."""
        data = [{}, {}, {}]
        assert parser.get_issue_count(data) == 3

    def test_get_issue_count_dict(self, parser):
        """Test issue count with dict input."""
        assert parser.get_issue_count({}) == 0


class TestMypyJSONParserCoverage:
    """Extended tests for MypyJSONParser - beyond existing test_json_parsers.py."""

    @pytest.fixture
    def parser(self):
        return MypyJSONParser()

    def test_validate_mypy_item_all_fields(self, parser):
        """Test validation with all required fields."""
        item = {"file": "test.py", "line": 10, "message": "Error"}
        assert parser._validate_mypy_item(item) is True

    def test_validate_mypy_item_missing_field(self, parser):
        """Test validation with missing required field."""
        item = {"file": "test.py", "message": "Error"}  # Missing line
        assert parser._validate_mypy_item(item) is False

    def test_build_mypy_issue_error(self, parser):
        """Test building issue with error severity."""
        item = {"file": "test.py", "line": 10, "message": "Type error", "severity": "error"}
        issue = parser._build_mypy_issue(item)
        assert issue.severity == Priority.HIGH

    def test_build_mypy_issue_warning(self, parser):
        """Test building issue with warning severity."""
        item = {"file": "test.py", "line": 10, "message": "Warning", "severity": "warning"}
        issue = parser._build_mypy_issue(item)
        assert issue.severity == Priority.MEDIUM

    def test_parse_line_number_int(self, parser):
        """Test parsing line number from integer."""
        assert parser._parse_line_number(42) == 42

    def test_parse_line_number_non_int(self, parser):
        """Test parsing line number from non-integer."""
        assert parser._parse_line_number("42") is None
        assert parser._parse_line_number(None) is None

    def test_get_issue_count(self, parser):
        """Test issue count."""
        data = [{}, {}]
        assert parser.get_issue_count(data) == 2

    def test_get_issue_count_not_list(self, parser):
        """Test issue count with non-list."""
        assert parser.get_issue_count("not a list") == 0
        assert parser.get_issue_count({}) == 0


class TestBanditJSONParserCoverage:
    """Extended tests for BanditJSONParser."""

    @pytest.fixture
    def parser(self):
        return BanditJSONParser()

    def test_parse_bandit_with_all_fields(self, parser):
        """Test parsing Bandit output with all fields."""
        data = {
            "results": [
                {
                    "filename": "app.py",
                    "line_number": 42,
                    "issue_text": "Use of hard-coded password",
                    "issue_severity": "HIGH",
                    "test_id": "B105",
                    "test_name": "hardcoded_password_string"
                }
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].type == IssueType.SECURITY
        assert issues[0].severity == Priority.CRITICAL  # HIGH is elevated to CRITICAL

    def test_parse_bandit_with_defaults(self, parser):
        """Test parsing Bandit with missing optional fields."""
        data = {
            "results": [
                {
                    "filename": "app.py",
                    "line_number": 10,
                    "issue_text": "Issue"
                }
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].severity == Priority.HIGH  # Default (MEDIUM) is elevated to HIGH
        assert issues[0].type == IssueType.SECURITY

    def test_map_severity_HIGH(self, parser):
        """Test severity mapping for HIGH."""
        assert parser._map_severity("HIGH") == Priority.CRITICAL

    def test_map_severity_MEDIUM(self, parser):
        """Test severity mapping for MEDIUM."""
        assert parser._map_severity("MEDIUM") == Priority.HIGH

    def test_map_severity_LOW(self, parser):
        """Test severity mapping for LOW."""
        assert parser._map_severity("LOW") == Priority.MEDIUM

    def test_map_severity_unknown(self, parser):
        """Test severity mapping for unknown values."""
        assert parser._map_severity("UNKNOWN") == Priority.MEDIUM

    def test_get_issue_count_with_results(self, parser):
        """Test issue count with results."""
        data = {"results": [{}, {}, {}]}
        assert parser.get_issue_count(data) == 3

    def test_get_issue_count_without_results(self, parser):
        """Test issue count without results."""
        assert parser.get_issue_count({}) == 0
        assert parser.get_issue_count({"results": "not a list"}) == 0


class TestSemgrepJSONParserCoverage:
    """Extended tests for SemgrepJSONParser."""

    @pytest.fixture
    def parser(self):
        return SemgrepJSONParser()

    def test_parse_semgrep_with_check_id(self, parser):
        """Test parsing Semgrep output with check_id."""
        data = {
            "results": [
                {
                    "check_id": "python.lang.security.audit.insecure-hash-md5",
                    "path": "src/crypto.py",
                    "start": {"line": 42},
                    "extra": {
                        "message": "Detected use of MD5 hash",
                        "severity": "WARNING"
                    }
                }
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].type == IssueType.SECURITY
        assert "audit.insecure-hash-md5" in issues[0].message

    def test_parse_semgrep_extracts_line_number(self, parser):
        """Test that line number is extracted from start."""
        data = {
            "results": [
                {
                    "check_id": "test",
                    "path": "test.py",
                    "start": {"line": 100},
                    "extra": {"message": "Issue", "severity": "ERROR"}
                }
            ]
        }
        issues = parser.parse_json(data)
        assert issues[0].line_number == 100

    def test_extract_line_number_from_start_valid(self, parser):
        """Test line number extraction from valid start dict."""
        start = {"line": 42, "column": 5}
        assert parser._extract_line_number_from_start(start) == 42

    def test_extract_line_number_from_start_invalid(self, parser):
        """Test line number extraction from invalid start."""
        assert parser._extract_line_number_from_start(None) is None
        assert parser._extract_line_number_from_start("not a dict") is None
        assert parser._extract_line_number_from_start({}) is None

    def test_get_extra_data(self, parser):
        """Test extracting extra data."""
        item = {"extra": {"message": "test", "severity": "WARNING"}}
        assert parser._get_extra_data(item) == {"message": "test", "severity": "WARNING"}

    def test_get_extra_data_invalid(self, parser):
        """Test extracting extra data with invalid type."""
        assert parser._get_extra_data("not a dict") == {}
        assert parser._get_extra_data(None) == {}

    def test_map_severity_ERROR(self, parser):
        """Test severity mapping for ERROR."""
        assert parser._map_severity("ERROR") == Priority.CRITICAL

    def test_map_severity_WARNING(self, parser):
        """Test severity mapping for WARNING."""
        assert parser._map_severity("WARNING") == Priority.HIGH

    def test_map_severity_INFO(self, parser):
        """Test severity mapping for INFO."""
        assert parser._map_severity("INFO") == Priority.MEDIUM

    def test_get_issue_count(self, parser):
        """Test issue count."""
        data = {"results": [{}, {}, {}]}
        assert parser.get_issue_count(data) == 3

    def test_get_issue_count_no_results(self, parser):
        """Test issue count without results."""
        assert parser.get_issue_count({}) == 0
        assert parser.get_issue_count({"results": None}) == 0


class TestPipAuditJSONParserCoverage:
    """Extended tests for PipAuditJSONParser."""

    @pytest.fixture
    def parser(self):
        return PipAuditJSONParser()

    def test_parse_pip_audit_with_vulns(self, parser):
        """Test parsing pip-audit with vulnerabilities."""
        data = {
            "dependencies": [
                {
                    "name": "django",
                    "vulns": [
                        {
                            "id": "PYSEC-1234",
                            "description": "SQL Injection vulnerability",
                            "severity": "HIGH"
                        }
                    ]
                }
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].type == IssueType.SECURITY
        assert "PYSEC-1234" in issues[0].message

    def test_parse_pip_audit_no_vulns(self, parser):
        """Test parsing pip-audit with no vulnerabilities."""
        data = {
            "dependencies": [
                {"name": "safe-package", "vulns": []}
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 0

    def test_parse_pip_audit_multiple_deps(self, parser):
        """Test parsing pip-audit with multiple dependencies."""
        data = {
            "dependencies": [
                {"name": "pkg1", "vulns": [{"id": "V1", "description": "Desc", "severity": "HIGH"}]},
                {"name": "pkg2", "vulns": [{"id": "V2", "description": "Desc", "severity": "MEDIUM"}]},
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 2

    def test_create_vulnerability_issue(self, parser):
        """Test creating vulnerability issue."""
        vuln = {
            "id": "CVE-2024-1234",
            "description": "Remote code execution",
            "severity": "CRITICAL"
        }
        issue = parser._create_vulnerability_issue("vulnerable_pkg", vuln)
        assert issue.type == IssueType.SECURITY
        assert issue.severity == Priority.CRITICAL
        assert issue.details[0] == "package: vulnerable_pkg"

    def test_map_severity_HIGH(self, parser):
        """Test severity mapping for HIGH."""
        assert parser._map_severity("HIGH") == Priority.CRITICAL

    def test_map_severity_MEDIUM(self, parser):
        """Test severity mapping for MEDIUM."""
        assert parser._map_severity("MEDIUM") == Priority.HIGH

    def test_map_severity_LOW(self, parser):
        """Test severity mapping for LOW."""
        assert parser._map_severity("LOW") == Priority.MEDIUM

    def test_get_dependencies_list(self, parser):
        """Test getting dependencies list."""
        data = {"dependencies": [{}, {}]}
        deps = parser._get_dependencies_list(data)
        assert deps is not None
        assert len(deps) == 2

    def test_get_dependencies_list_missing(self, parser):
        """Test getting dependencies list when missing."""
        assert parser._get_dependencies_list({}) is None
        assert parser._get_dependencies_list({"dependencies": "not a list"}) is None

    def test_count_vulnerabilities_in_dep(self, parser):
        """Test counting vulnerabilities in dependency."""
        dep = {"vulns": [{}, {}, {}]}
        assert parser._count_vulnerabilities_in_dep(dep) == 3

    def test_count_vulnerabilities_in_dep_no_vulns(self, parser):
        """Test counting vulnerabilities when none."""
        assert parser._count_vulnerabilities_in_dep({}) == 0
        assert parser._count_vulnerabilities_in_dep({"vulns": "not a list"}) == 0

    def test_get_issue_count(self, parser):
        """Test issue count."""
        data = {
            "dependencies": [
                {"vulns": [{"id": "1"}, {"id": "2"}]},
                {"vulns": [{"id": "3"}]},
            ]
        }
        assert parser.get_issue_count(data) == 3


class TestGitleaksJSONParserCoverage:
    """Extended tests for GitleaksJSONParser."""

    @pytest.fixture
    def parser(self):
        return GitleaksJSONParser()

    def test_parse_gitleaks_finding_format(self, parser):
        """Test parsing gitleaks finding format."""
        data = [
            {
                "Description": "AWS Access Key",
                "File": "config/aws.py",
                "StartLine": 42,
                "RuleID": "AWSKey",
                "Severity": "HIGH"
            }
        ]
        issues = parser.parse_json(data)
        assert len(issues) == 1
        assert issues[0].type == IssueType.SECURITY
        assert issues[0].file_path == "config/aws.py"
        assert "AWSKey" in issues[0].message

    def test_parse_gitleaks_with_findings_key(self, parser):
        """Test parsing gitleaks output with 'findings' key."""
        data = {
            "findings": [
                {"Description": "Secret", "File": "secrets.py", "StartLine": 1, "RuleID": "Test", "Severity": "MEDIUM"}
            ]
        }
        issues = parser.parse_json(data)
        assert len(issues) == 1

    def test_parse_gitleaks_dict_not_list(self, parser):
        """Test parsing when data is a dict instead of list."""
        data = {"Description": "Secret", "File": "secrets.py", "StartLine": 1, "RuleID": "Test", "Severity": "LOW"}
        issues = parser.parse_json(data)
        assert len(issues) == 1

    def test_parse_gitleaks_empty_list(self, parser):
        """Test parsing empty list."""
        assert parser.parse_json([]) == []

    def test_extract_json_from_output_with_brackets(self, parser):
        """Test extracting JSON from output with brackets."""
        output = """Some text before
[
  {"Description": "Secret", "File": "test.py", "StartLine": 1, "RuleID": "T", "Severity": "LOW"}
]
Some text after"""
        data = parser._extract_json_from_output(output)
        assert data is not None
        assert isinstance(data, list)

    def test_extract_json_from_output_empty(self, parser):
        """Test extracting JSON from empty output."""
        assert parser._extract_json_from_output("") is None

    def test_map_severity_HIGH(self, parser):
        """Test severity mapping for HIGH."""
        assert parser._map_severity("HIGH") == Priority.CRITICAL

    def test_map_severity_MEDIUM(self, parser):
        """Test severity mapping for MEDIUM."""
        assert parser._map_severity("MEDIUM") == Priority.HIGH

    def test_map_severity_LOW(self, parser):
        """Test severity mapping for LOW."""
        assert parser._map_severity("LOW") == Priority.MEDIUM

    def test_get_issue_count_list(self, parser):
        """Test issue count with list."""
        data = [{}, {}, {}]
        assert parser.get_issue_count(data) == 3

    def test_get_issue_count_not_list(self, parser):
        """Test issue count with non-list."""
        assert parser.get_issue_count({}) == 0


class TestPytestJSONParserCoverage:
    """Extended tests for PytestJSONParser."""

    @pytest.fixture
    def parser(self):
        return PytestJSONParser()

    @patch('crackerjack.parsers.json_parsers.TestResultParser')
    def test_parse_pytest_with_failures(self, mock_parser_class, parser):
        """Test parsing pytest with failures."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_failure = MagicMock()
        mock_failure.to_issue.return_value = Issue(
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="test_foo failed",
            file_path="tests/test_foo.py",
            line_number=42
        )
        mock_parser.parse_json_output.return_value = [mock_failure]

        data = {"tests": [{"outcome": "failed", "name": "test_foo"}]}
        issues = parser.parse_json(data)
        assert len(issues) == 1

    def test_get_issue_count_with_failed_tests(self, parser):
        """Test issue count with failed tests."""
        data = {
            "tests": [
                {"outcome": "passed"},
                {"outcome": "failed"},
                {"outcome": "failed"},
            ]
        }
        assert parser.get_issue_count(data) == 2

    def test_get_issue_count_no_tests(self, parser):
        """Test issue count with no tests."""
        assert parser.get_issue_count({}) == 0
        assert parser.get_issue_count({"tests": "not a list"}) == 0


class TestRegisterJsonParsers:
    """Tests for register_json_parsers function."""

    def test_register_json_parsers_adds_parsers(self):
        """Test that register_json_parsers adds all expected parsers."""
        factory = MagicMock()
        register_json_parsers(factory)

        calls = factory.register_json_parser.call_args_list
        tool_names = [call[0][0] for call in calls]

        expected_tools = [
            "ruff", "ruff-check", "mypy", "bandit",
            "complexipy", "semgrep", "pip-audit", "gitleaks", "pytest"
        ]

        for tool in expected_tools:
            assert tool in tool_names, f"Missing JSON parser for {tool}"


class TestJsonParsersEdgeCases:
    """Edge case tests for JSON parsers."""

    def test_all_json_parsers_handle_empty_list(self):
        """Test that all JSON parsers handle empty list gracefully."""
        parsers = [
            RuffJSONParser(),
            MypyJSONParser(),
            BanditJSONParser(),
            SemgrepJSONParser(),
            PipAuditJSONParser(),
            GitleaksJSONParser(),
            PytestJSONParser(),
        ]

        for parser in parsers:
            result = parser.parse_json([])
            assert result == [], f"{parser.__class__.__name__} failed on empty list"

    def test_all_json_parsers_handle_non_dict_non_list(self):
        """Test that all JSON parsers handle non-dict/non-list input gracefully."""
        parsers = [
            RuffJSONParser(),
            MypyJSONParser(),
            BanditJSONParser(),
            SemgrepJSONParser(),
            PipAuditJSONParser(),
            GitleaksJSONParser(),
            PytestJSONParser(),
        ]

        for parser in parsers:
            result = parser.parse_json(_json_input("not a list or dict"))
            assert result == [], f"{parser.__class__.__name__} failed on string input"
            result = parser.parse_json(_json_input(123))
            assert result == [], f"{parser.__class__.__name__} failed on int input"
            result = parser.parse_json(_json_input(None))
            assert result == [], f"{parser.__class__.__name__} failed on None input"
