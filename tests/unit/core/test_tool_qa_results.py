"""Tests for QA adapter results from various tools.

These tests verify that different QA tools correctly populate QAResult.parsed_issues
with appropriate ToolIssue data for the AI-fix workflow.
"""

import json
import pytest
from pathlib import Path
from uuid import uuid4

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.models.qa_results import (
    QAResult,
    QAResultStatus,
    QACheckType,
)
from unittest.mock import MagicMock


class TestMypyQAResult:
    """Test mypy QA adapter results."""

    @pytest.fixture
    def coordinator(self):
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_mypy_type_error_conversion(self, coordinator):
        """Test conversion of mypy type error to Issue."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="mypy",
            check_type=QACheckType.TYPE,
            status=QAResultStatus.FAILURE,
            message="Found 2 type errors",
            parsed_issues=[
                {
                    "file_path": "crackerjack/core/coordinator.py",
                    "line_number": 42,
                    "column_number": 5,
                    "message": "Incompatible return value type",
                    "code": "return-value",
                    "severity": "error",
                },
                {
                    "file_path": "crackerjack/agents/base.py",
                    "line_number": 100,
                    "message": "Argument 1 has incompatible type",
                    "severity": "warning",
                },
            ],
            files_checked=[
                Path("crackerjack/core/coordinator.py"),
                Path("crackerjack/agents/base.py"),
            ],
            issues_found=2,
        )

        issues = coordinator._convert_parsed_issues_to_issues(
            "mypy", qa_result.parsed_issues
        )

        assert len(issues) == 2
        assert issues[0].type == IssueType.TYPE_ERROR
        assert issues[0].severity == Priority.HIGH
        assert "Incompatible return value type" in issues[0].message
        assert issues[0].file_path == "crackerjack/core/coordinator.py"

        assert issues[1].type == IssueType.TYPE_ERROR
        assert issues[1].severity == Priority.MEDIUM  # warning


class TestBanditQAResult:
    """Test bandit QA adapter results."""

    @pytest.fixture
    def coordinator(self):
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_bandit_security_issue_conversion(self, coordinator):
        """Test conversion of bandit security issue to Issue."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="bandit",
            check_type=QACheckType.SECURITY,
            status=QAResultStatus.FAILURE,
            message="Found 1 security issue",
            parsed_issues=[
                {
                    "file_path": "crackerjack/services/subprocess.py",
                    "line_number": 25,
                    "column_number": 10,
                    "message": "Use of shell=True in subprocess is security risk",
                    "code": "B602",
                    "severity": "error",
                    "suggestion": "Use shell=False and pass arguments as list",
                }
            ],
            files_checked=[Path("crackerjack/services/subprocess.py")],
            issues_found=1,
        )

        issues = coordinator._convert_parsed_issues_to_issues(
            "bandit", qa_result.parsed_issues
        )

        assert len(issues) == 1
        assert issues[0].type == IssueType.SECURITY
        assert issues[0].severity == Priority.HIGH
        assert "shell=True" in issues[0].message
        assert "code: B602" in issues[0].details


class TestRuffQAResult:
    """Test ruff QA adapter results."""

    @pytest.fixture
    def coordinator(self):
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_ruff_formatting_issue_conversion(self, coordinator):
        """Test conversion of ruff formatting issue to Issue."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="ruff",
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.FAILURE,
            message="Found 3 formatting issues",
            parsed_issues=[
                {
                    "file_path": "crackerjack/utils/helpers.py",
                    "line_number": 15,
                    "column_number": 1,
                    "message": "Line too long (120 > 100 characters)",
                    "code": "E501",
                    "severity": "warning",
                },
                {
                    "file_path": "crackerjack/utils/helpers.py",
                    "line_number": 20,
                    "message": "Unused import 'os'",
                    "code": "F401",
                    "severity": "error",
                },
                {
                    "file_path": "crackerjack/utils/helpers.py",
                    "line_number": 25,
                    "message": "Missing trailing comma",
                    "code": "COM812",
                    "severity": "info",
                },
            ],
            files_checked=[Path("crackerjack/utils/helpers.py")],
            issues_found=3,
        )

        issues = coordinator._convert_parsed_issues_to_issues(
            "ruff", qa_result.parsed_issues
        )

        assert len(issues) == 3
        # All ruff issues should be FORMATTING type
        assert all(issue.type == IssueType.FORMATTING for issue in issues)

        # Check severity mapping
        assert issues[0].severity == Priority.MEDIUM  # warning
        assert issues[1].severity == Priority.HIGH  # error
        assert issues[2].severity == Priority.LOW  # info


class TestPytestQAResult:
    """Test pytest QA adapter results."""

    @pytest.fixture
    def coordinator(self):
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_pytest_failure_conversion(self, coordinator):
        """Test conversion of pytest test failure to Issue."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="pytest",
            check_type=QACheckType.TEST,
            status=QAResultStatus.FAILURE,
            message="2 tests failed",
            parsed_issues=[
                {
                    "file_path": "tests/unit/core/test_coordinator.py",
                    "line_number": 42,
                    "message": "assertion failed in test_coordinator_init",
                    "severity": "error",
                },
                {
                    "file_path": "tests/unit/agents/test_base.py",
                    "line_number": 15,
                    "message": "test_issue_creation raised TypeError",
                    "severity": "error",
                },
            ],
            files_checked=[
                Path("tests/unit/core/test_coordinator.py"),
                Path("tests/unit/agents/test_base.py"),
            ],
            issues_found=2,
        )

        issues = coordinator._convert_parsed_issues_to_issues(
            "pytest", qa_result.parsed_issues
        )

        assert len(issues) == 2
        assert all(issue.type == IssueType.TEST_FAILURE for issue in issues)
        assert all(issue.severity == Priority.HIGH for issue in issues)


class TestSkylosQAResult:
    """Test skylos QA adapter results."""

    @pytest.fixture
    def coordinator(self):
        console = MagicMock()
        return AutofixCoordinator(console=console)

    def test_skylos_dead_code_conversion(self, coordinator):
        """Test conversion of skylos dead code detection to Issue."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="skylos",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.FAILURE,
            message="Found 5 unused functions",
            parsed_issues=[
                {
                    "file_path": "crackerjack/agents/refactoring_agent.py",
                    "line_number": 150,
                    "message": "Function 'old_refactor_method' is never called",
                    "code": "dead_code",
                    "severity": "warning",
                },
                {
                    "file_path": "crackerjack/agents/helpers.py",
                    "line_number": 50,
                    "message": "Class 'DeprecatedHelper' is never instantiated",
                    "severity": "info",
                },
            ],
            files_checked=[
                Path("crackerjack/agents/refactoring_agent.py"),
                Path("crackerjack/agents/helpers.py"),
            ],
            issues_found=2,
        )

        issues = coordinator._convert_parsed_issues_to_issues(
            "skylos", qa_result.parsed_issues
        )

        assert len(issues) == 2
        assert all(issue.type == IssueType.DEAD_CODE for issue in issues)

        assert issues[0].severity == Priority.MEDIUM  # warning
        assert issues[1].severity == Priority.LOW  # info
        assert "never called" in issues[0].message
