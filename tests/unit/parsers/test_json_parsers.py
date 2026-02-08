"""Tests for JSON parsers."""

import json
import pytest
from pathlib import Path

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.json_parsers import (
    RuffJSONParser,
    MypyJSONParser,
    BanditJSONParser,
    SemgrepJSONParser,
    PipAuditJSONParser,
    GitleaksJSONParser,
)


class TestRuffJSONParser:
    """Test Ruff JSON parser."""

    @pytest.fixture
    def parser(self):
        return RuffJSONParser()

    def test_parse_valid_ruff_output(self, parser):
        """Test parsing valid ruff JSON output."""
        data = [
            {
                "filename": "test.py",
                "location": {"row": 10, "column": 5},
                "code": "F401",
                "message": "Unused import",
                "fix": {"applicability": "safe"},
                "url": "https://docs.astral.sh/ruff/rules/unused-import",
            }
        ]

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert "code: F401" in issues[0].details
        assert issues[0].file_path == "test.py"
        assert issues[0].line_number == 10
        assert issues[0].type == IssueType.IMPORT_ERROR
        assert issues[0].severity == Priority.MEDIUM
        assert issues[0].message.startswith("F401")

    def test_parse_complexity_issue(self, parser):
        """Test parsing C9 (complexity) issues."""
        data = [
            {
                "filename": "complex.py",
                "location": {"row": 50},
                "code": "C901",
                "message": "Function is too complex",
            }
        ]

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].type == IssueType.COMPLEXITY
        assert issues[0].severity == Priority.HIGH

    def test_parse_security_issue(self, parser):
        """Test parsing S (security) issues."""
        data = [
            {
                "filename": "security.py",
                "location": {"row": 5},
                "code": "S101",
                "message": "Use of assert detected",
            }
        ]

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].type == IssueType.SECURITY
        assert issues[0].severity == Priority.HIGH

    def test_parse_non_list_data(self, parser):
        """Test parsing non-list data."""
        data = {"key": "value"}

        issues = parser.parse_json(data)

        assert issues == []

    def test_parse_item_missing_required_fields(self, parser):
        """Test parsing item missing required fields."""
        data = [{"filename": "test.py", "location": {"row": 5}}]

        issues = parser.parse_json(data)

        assert issues == []

    def test_parse_item_invalid_location(self, parser):
        """Test parsing item with invalid location."""
        data = [
            {
                "filename": "test.py",
                "location": "not a dict",
                "code": "F401",
                "message": "Error",
            }
        ]

        issues = parser.parse_json(data)

        assert issues == []

    def test_get_issue_count(self, parser):
        """Test get_issue_count method."""
        data = [{"item": 1}, {"item": 2}, {"item": 3}]

        count = parser.get_issue_count(data)

        assert count == 3

    def test_get_issue_count_non_list(self, parser):
        """Test get_issue_count with non-list data."""
        count = parser.get_issue_count({"key": "value"})

        assert count == 0


class TestMypyJSONParser:
    """Test Mypy JSON parser."""

    @pytest.fixture
    def parser(self):
        return MypyJSONParser()

    def test_parse_valid_mypy_output(self, parser):
        """Test parsing valid mypy JSON output."""
        data = [
            {
                "file": "test.py",
                "line": 10,
                "column": 5,
                "message": "Incompatible types",
                "severity": "error",
            }
        ]

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].file_path == "test.py"
        assert issues[0].line_number == 10
        assert issues[0].type == IssueType.TYPE_ERROR
        assert issues[0].severity == Priority.HIGH

    def test_parse_warning_severity(self, parser):
        """Test parsing warning severity."""
        data = [
            {
                "file": "test.py",
                "line": 5,
                "message": "Unused variable",
                "severity": "warning",
            }
        ]

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].severity == Priority.MEDIUM

    def test_parse_item_missing_fields(self, parser):
        """Test parsing item missing required fields."""
        data = [{"file": "test.py"}]

        issues = parser.parse_json(data)

        assert issues == []

    def test_parse_non_list_data(self, parser):
        """Test parsing non-list data."""
        issues = parser.parse_json({"key": "value"})

        assert issues == []

    def test_get_issue_count(self, parser):
        """Test get_issue_count method."""
        data = [
            {"file": "a.py", "line": 1, "message": "error 1"},
            {"file": "b.py", "line": 2, "message": "error 2"},
        ]

        count = parser.get_issue_count(data)

        assert count == 2


class TestBanditJSONParser:
    """Test Bandit JSON parser."""

    @pytest.fixture
    def parser(self):
        return BanditJSONParser()

    def test_parse_valid_bandit_output(self, parser):
        """Test parsing valid bandit JSON output."""
        data = {
            "results": [
                {
                    "filename": "test.py",
                    "line_number": 10,
                    "issue_text": "Use of assert detected",
                    "issue_severity": "MEDIUM",
                    "test_id": "S101",
                }
            ]
        }

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].file_path == "test.py"
        assert issues[0].line_number == 10
        assert issues[0].type == IssueType.SECURITY
        assert issues[0].severity == Priority.HIGH
        assert "S101" in issues[0].message

    def test_parse_high_severity(self, parser):
        """Test parsing HIGH severity."""
        data = {
            "results": [
                {
                    "filename": "test.py",
                    "line_number": 5,
                    "issue_text": "Critical security issue",
                    "issue_severity": "HIGH",
                    "test_id": "S001",
                }
            ]
        }

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].severity == Priority.CRITICAL

    def test_parse_low_severity(self, parser):
        """Test parsing LOW severity."""
        data = {
            "results": [
                {
                    "filename": "test.py",
                    "line_number": 1,
                    "issue_text": "Minor issue",
                    "issue_severity": "LOW",
                    "test_id": "S000",
                }
            ]
        }

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].severity == Priority.MEDIUM

    def test_parse_no_results_key(self, parser):
        """Test parsing output without results key."""
        data = {"other_key": "value"}

        issues = parser.parse_json(data)

        assert issues == []

    def test_parse_non_list_results(self, parser):
        """Test parsing when results is not a list."""
        data = {"results": "not a list"}

        issues = parser.parse_json(data)

        assert issues == []

    def test_parse_item_missing_fields(self, parser):
        """Test parsing item missing required fields."""
        data = {
            "results": [
                {
                    "filename": "test.py",
                    # Missing line_number, issue_text, test_id
                }
            ]
        }

        issues = parser.parse_json(data)

        assert issues == []

    def test_get_issue_count(self, parser):
        """Test get_issue_count method."""
        data = {
            "results": [
                {"filename": "a.py", "line_number": 1, "issue_text": "err1", "test_id": "S001"},
                {"filename": "b.py", "line_number": 2, "issue_text": "err2", "test_id": "S002"},
            ]
        }

        count = parser.get_issue_count(data)

        assert count == 2


class TestSemgrepJSONParser:
    """Test Semgrep JSON parser."""

    @pytest.fixture
    def parser(self):
        return SemgrepJSONParser()

    def test_parse_valid_semgrep_output(self, parser):
        """Test parsing valid semgrep JSON output."""
        data = {
            "results": [
                {
                    "path": "test.py",
                    "start": {"line": 10},
                    "extra": {
                        "message": "Dangerous function call",
                        "severity": "ERROR",
                    },
                    "check_id": "python.lang.security.dangerous-function",
                }
            ]
        }

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].file_path == "test.py"
        assert issues[0].line_number == 10
        assert issues[0].type == IssueType.SECURITY
        assert issues[0].severity == Priority.CRITICAL

    def test_parse_warning_severity(self, parser):
        """Test parsing WARNING severity."""
        data = {
            "results": [
                {
                    "path": "test.py",
                    "start": {"line": 5},
                    "extra": {"message": "Potential issue", "severity": "WARNING"},
                    "check_id": "test.check",
                }
            ]
        }

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].severity == Priority.HIGH

    def test_parse_no_path(self, parser):
        """Test parsing result without path."""
        data = {
            "results": [
                {
                    "start": {"line": 1},
                    "extra": {"message": "No path"},
                    "check_id": "test",
                }
            ]
        }

        issues = parser.parse_json(data)

        assert issues == []

    def test_parse_non_dict_data(self, parser):
        """Test parsing non-dict data."""
        issues = parser.parse_json([1, 2, 3])

        assert issues == []

    def test_parse_no_results_key(self, parser):
        """Test parsing without results key."""
        issues = parser.parse_json({"other": "data"})

        assert issues == []

    def test_get_issue_count(self, parser):
        """Test get_issue_count method."""
        data = {
            "results": [
                {"path": "a.py", "start": {"line": 1}, "extra": {}, "check_id": "test1"},
                {"path": "b.py", "start": {"line": 2}, "extra": {}, "check_id": "test2"},
            ]
        }

        count = parser.get_issue_count(data)

        assert count == 2


class TestPipAuditJSONParser:
    """Test pip-audit JSON parser."""

    @pytest.fixture
    def parser(self):
        return PipAuditJSONParser()

    def test_parse_valid_pip_audit_output(self, parser):
        """Test parsing valid pip-audit JSON output."""
        data = {
            "dependencies": [
                {
                    "name": "requests",
                    "vulns": [
                        {
                            "id": "CVE-2023-1234",
                            "description": "Security vulnerability",
                            "severity": "HIGH",
                        }
                    ],
                }
            ]
        }

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].type == IssueType.SECURITY
        assert issues[0].severity == Priority.CRITICAL
        assert "CVE-2023-1234" in issues[0].message
        assert "requests" in issues[0].details[0]

    def test_parse_multiple_vulnerabilities(self, parser):
        """Test parsing multiple vulnerabilities in one package."""
        data = {
            "dependencies": [
                {
                    "name": "package",
                    "vulns": [
                        {"id": "CVE-1", "description": "Vuln 1", "severity": "HIGH"},
                        {"id": "CVE-2", "description": "Vuln 2", "severity": "MEDIUM"},
                    ],
                }
            ]
        }

        issues = parser.parse_json(data)

        assert len(issues) == 2

    def test_parse_no_vulnerabilities(self, parser):
        """Test parsing package with no vulnerabilities."""
        data = {
            "dependencies": [
                {
                    "name": "safe-package",
                    "vulns": [],
                }
            ]
        }

        issues = parser.parse_json(data)

        assert len(issues) == 0

    def test_parse_non_list_dependencies(self, parser):
        """Test parsing when dependencies is not a list."""
        data = {"dependencies": "not a list"}

        issues = parser.parse_json(data)

        assert issues == []

    def test_parse_non_list_vulns(self, parser):
        """Test parsing when vulns is not a list."""
        data = {
            "dependencies": [
                {
                    "name": "package",
                    "vulns": "not a list",
                }
            ]
        }

        issues = parser.parse_json(data)

        assert issues == []

    def test_get_issue_count(self, parser):
        """Test get_issue_count method."""
        data = {
            "dependencies": [
                {
                    "name": "pkg1",
                    "vulns": [
                        {"id": "CVE-1"},
                        {"id": "CVE-2"},
                    ],
                },
                {
                    "name": "pkg2",
                    "vulns": [
                        {"id": "CVE-3"},
                    ],
                },
            ]
        }

        count = parser.get_issue_count(data)

        assert count == 3


class TestGitleaksJSONParser:
    """Test Gitleaks JSON parser."""

    @pytest.fixture
    def parser(self):
        return GitleaksJSONParser()

    def test_parse_valid_gitleaks_output(self, parser):
        """Test parsing valid gitleaks JSON output."""
        data = [
            {
                "Description": "AWS Access Key",
                "File": "config.py",
                "StartLine": 10,
                "RuleID": "aws-access-key",
                "Severity": "HIGH",
            }
        ]

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].file_path == "config.py"
        assert issues[0].line_number == 10
        assert issues[0].type == IssueType.SECURITY
        assert issues[0].severity == Priority.CRITICAL
        assert "aws-access-key" in issues[0].message

    def test_parse_medium_severity(self, parser):
        """Test parsing MEDIUM severity."""
        data = [
            {
                "Description": "Potential secret",
                "File": "test.txt",
                "StartLine": 5,
                "RuleID": "generic-secret",
                "Severity": "MEDIUM",
            }
        ]

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].severity == Priority.HIGH

    def test_parse_missing_optional_fields(self, parser):
        """Test parsing with missing optional fields."""
        data = [
            {
                "Description": "Secret",
                "File": "test.py",
                # StartLine missing
                "RuleID": "test-rule",
                "Severity": "LOW",
            }
        ]

        issues = parser.parse_json(data)

        assert len(issues) == 1
        assert issues[0].line_number is None
        assert issues[0].severity == Priority.MEDIUM

    def test_parse_non_list_data(self, parser):
        """Test parsing non-list data."""
        issues = parser.parse_json({"key": "value"})

        assert issues == []

    def test_get_issue_count(self, parser):
        """Test get_issue_count method."""
        data = [
            {"Description": "A", "File": "a.py", "StartLine": 1},
            {"Description": "B", "File": "b.py", "StartLine": 2},
        ]

        count = parser.get_issue_count(data)

        assert count == 2
