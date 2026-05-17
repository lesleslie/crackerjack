"""Tests for validation_contracts module."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from crackerjack.models.validation_contracts import (
    GateSeverity,
    QualityGateCheck,
    QualityGateReport,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    _coerce_datetime,
    _coerce_mapping,
    _coerce_string_list,
)


class TestValidationSeverity:
    """Tests for ValidationSeverity enum."""

    def test_enum_values(self) -> None:
        """Verify all validation severity values."""
        assert ValidationSeverity.ERROR.value == "error"
        assert ValidationSeverity.WARNING.value == "warning"
        assert ValidationSeverity.INFO.value == "info"

    def test_enum_members(self) -> None:
        """Verify all validation severity members exist."""
        members = {member.value for member in ValidationSeverity}
        assert members == {"error", "warning", "info"}


class TestGateSeverity:
    """Tests for GateSeverity enum."""

    def test_enum_values(self) -> None:
        """Verify all gate severity values."""
        assert GateSeverity.REQUIRED.value == "required"
        assert GateSeverity.WARNING.value == "warning"
        assert GateSeverity.OPTIONAL.value == "optional"

    def test_enum_members(self) -> None:
        """Verify all gate severity members exist."""
        members = {member.value for member in GateSeverity}
        assert members == {"required", "warning", "optional"}


class TestCoerceMapping:
    """Tests for _coerce_mapping function."""

    def test_none_returns_empty_dict(self) -> None:
        """Verify None returns empty dict."""
        result = _coerce_mapping(None)
        assert result == {}

    def test_dict_returns_dict(self) -> None:
        """Verify dict returns dict."""
        data = {"key": "value"}
        result = _coerce_mapping(data)
        assert result == data

    def test_mapping_returns_dict(self) -> None:
        """Verify Mapping returns dict."""
        data = {"key1": "value1", "key2": "value2"}
        result = _coerce_mapping(data)
        assert isinstance(result, dict)
        assert result == data

    def test_model_dump_object(self) -> None:
        """Verify object with model_dump returns dict."""
        obj = MagicMock()
        obj.model_dump.return_value = {"model": "data"}
        result = _coerce_mapping(obj)
        assert result == {"model": "data"}

    def test_to_dict_object(self) -> None:
        """Verify object with to_dict returns dict."""
        obj = MagicMock()
        obj.to_dict.return_value = {"custom": "data"}
        del obj.model_dump
        result = _coerce_mapping(obj)
        assert result == {"custom": "data"}

    def test_dict_object(self) -> None:
        """Verify object with __dict__ returns dict."""

        class CustomObject:
            def __init__(self) -> None:
                self.field1 = "value1"
                self._private = "hidden"

        obj = CustomObject()
        result = _coerce_mapping(obj)
        assert "field1" in result
        assert "_private" not in result

    def test_non_mapping_object_returns_empty(self) -> None:
        """Verify non-mapping object returns empty dict."""
        obj = object()
        result = _coerce_mapping(obj)
        assert result == {}


class TestCoerceDatetime:
    """Tests for _coerce_datetime function."""

    def test_datetime_returns_datetime(self) -> None:
        """Verify datetime returns datetime."""
        now = datetime.now(UTC)
        result = _coerce_datetime(now)
        assert result == now

    def test_iso_string_parses_datetime(self) -> None:
        """Verify ISO string parses to datetime."""
        iso_string = "2024-01-15T10:30:00+00:00"
        result = _coerce_datetime(iso_string)
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_invalid_string_returns_now(self) -> None:
        """Verify invalid string returns now."""
        before = datetime.now(UTC)
        result = _coerce_datetime("not a datetime")
        after = datetime.now(UTC)
        assert before <= result <= after

    def test_non_datetime_returns_now(self) -> None:
        """Verify non-datetime returns now."""
        before = datetime.now(UTC)
        result = _coerce_datetime({"dict": "value"})
        after = datetime.now(UTC)
        assert before <= result <= after


class TestCoerceStringList:
    """Tests for _coerce_string_list function."""

    def test_none_returns_empty_list(self) -> None:
        """Verify None returns empty list."""
        result = _coerce_string_list(None)
        assert result == []

    def test_string_returns_list_with_string(self) -> None:
        """Verify string returns list with string."""
        result = _coerce_string_list("error message")
        assert result == ["error message"]

    def test_list_returns_list_of_strings(self) -> None:
        """Verify list returns list of strings."""
        result = _coerce_string_list(["error1", "error2"])
        assert result == ["error1", "error2"]

    def test_dict_returns_list_of_values(self) -> None:
        """Verify dict returns list of values."""
        result = _coerce_string_list({"key1": "value1", "key2": "value2"})
        assert set(result) == {"value1", "value2"}

    def test_empty_list_returns_empty_list(self) -> None:
        """Verify empty list returns empty list."""
        result = _coerce_string_list([])
        assert result == []


class TestValidationIssue:
    """Tests for ValidationIssue model."""

    def test_minimal_validation_issue(self) -> None:
        """Verify minimal ValidationIssue creation."""
        issue = ValidationIssue(message="Test error")
        assert issue.severity == ValidationSeverity.ERROR
        assert issue.message == "Test error"
        assert issue.file_path is None
        assert issue.line_number is None
        assert issue.code is None
        assert issue.category is None
        assert issue.details == {}

    def test_validation_issue_with_all_fields(self) -> None:
        """Verify ValidationIssue with all fields."""
        issue = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            message="Test warning",
            file_path="src/main.py",
            line_number=42,
            code="W001",
            category="style",
            details={"extra": "data"},
        )
        assert issue.severity == ValidationSeverity.WARNING
        assert issue.message == "Test warning"
        assert issue.file_path == "src/main.py"
        assert issue.line_number == 42
        assert issue.code == "W001"
        assert issue.category == "style"
        assert issue.details == {"extra": "data"}

    def test_from_value_with_validation_issue(self) -> None:
        """Verify from_value returns same ValidationIssue."""
        issue = ValidationIssue(message="test")
        result = ValidationIssue.from_value(issue)
        assert result is issue

    def test_from_value_with_string(self) -> None:
        """Verify from_value with string creates issue."""
        result = ValidationIssue.from_value("error message")
        assert result.message == "error message"
        assert result.severity == ValidationSeverity.ERROR

    def test_from_value_with_dict(self) -> None:
        """Verify from_value with dict."""
        data = {
            "message": "Test error",
            "severity": "warning",
            "file_path": "test.py",
            "line_number": "10",
            "code": "E001",
            "category": "error",
            "details": {"key": "value"},
        }
        result = ValidationIssue.from_value(data)
        assert result.message == "Test error"
        assert result.severity == ValidationSeverity.WARNING
        assert result.file_path == "test.py"
        assert result.line_number == 10
        assert result.code == "E001"
        assert result.category == "error"

    def test_from_value_with_invalid_severity(self) -> None:
        """Verify from_value defaults invalid severity."""
        data = {"message": "test", "severity": "invalid"}
        result = ValidationIssue.from_value(data)
        assert result.severity == ValidationSeverity.ERROR

    def test_from_value_with_invalid_line_number(self) -> None:
        """Verify from_value handles invalid line number."""
        data = {"message": "test", "line_number": "not_a_number"}
        result = ValidationIssue.from_value(data)
        assert result.line_number is None

    def test_from_value_with_error_message_fallback(self) -> None:
        """Verify from_value uses error_message fallback."""
        data = {"error_message": "fallback message"}
        result = ValidationIssue.from_value(data)
        assert result.message == "fallback message"

    def test_to_dict(self) -> None:
        """Verify to_dict serialization."""
        issue = ValidationIssue(
            message="test",
            severity=ValidationSeverity.WARNING,
            code="W001",
        )
        result = issue.to_dict()
        assert result["message"] == "test"
        assert result["severity"] == "warning"
        assert result["code"] == "W001"


class TestValidationReport:
    """Tests for ValidationReport model."""

    def test_minimal_validation_report(self) -> None:
        """Verify minimal ValidationReport creation."""
        report = ValidationReport(valid=True)
        assert report.valid is True
        assert report.validation_type == ""
        assert report.source == "crackerjack"
        assert report.issues == []
        assert report.summary == ""
        assert isinstance(report.generated_at, datetime)
        assert report.metadata == {}

    def test_validation_report_with_issues(self) -> None:
        """Verify ValidationReport with issues."""
        issue1 = ValidationIssue(message="error", severity=ValidationSeverity.ERROR)
        issue2 = ValidationIssue(message="warning", severity=ValidationSeverity.WARNING)
        report = ValidationReport(
            valid=False,
            issues=[issue1, issue2],
            summary="2 issues found",
        )
        assert report.valid is False
        assert len(report.issues) == 2
        assert report.summary == "2 issues found"

    def test_errors_property(self) -> None:
        """Verify errors property filters error issues."""
        error = ValidationIssue(message="error", severity=ValidationSeverity.ERROR)
        warning = ValidationIssue(message="warning", severity=ValidationSeverity.WARNING)
        report = ValidationReport(valid=False, issues=[error, warning])
        assert len(report.errors) == 1
        assert report.errors[0].message == "error"

    def test_warnings_property(self) -> None:
        """Verify warnings property filters warning issues."""
        error = ValidationIssue(message="error", severity=ValidationSeverity.ERROR)
        warning = ValidationIssue(message="warning", severity=ValidationSeverity.WARNING)
        report = ValidationReport(valid=False, issues=[error, warning])
        assert len(report.warnings) == 1
        assert report.warnings[0].message == "warning"

    def test_error_count_property(self) -> None:
        """Verify error_count property."""
        error1 = ValidationIssue(message="error1", severity=ValidationSeverity.ERROR)
        error2 = ValidationIssue(message="error2", severity=ValidationSeverity.ERROR)
        warning = ValidationIssue(message="warning", severity=ValidationSeverity.WARNING)
        report = ValidationReport(valid=False, issues=[error1, error2, warning])
        assert report.error_count == 2

    def test_warning_count_property(self) -> None:
        """Verify warning_count property."""
        error = ValidationIssue(message="error", severity=ValidationSeverity.ERROR)
        warning1 = ValidationIssue(message="warning1", severity=ValidationSeverity.WARNING)
        warning2 = ValidationIssue(message="warning2", severity=ValidationSeverity.WARNING)
        report = ValidationReport(valid=False, issues=[error, warning1, warning2])
        assert report.warning_count == 2

    def test_from_result_with_valid(self) -> None:
        """Verify from_result with valid=True."""
        result = ValidationReport.from_result({"valid": True})
        assert result.valid is True

    def test_from_result_with_success_fallback(self) -> None:
        """Verify from_result uses success fallback."""
        result = ValidationReport.from_result({"success": True})
        assert result.valid is True

    def test_from_result_with_issues(self) -> None:
        """Verify from_result creates issues."""
        data = {
            "valid": False,
            "issues": [{"message": "error1"}, {"message": "error2"}],
        }
        result = ValidationReport.from_result(data)
        assert result.valid is False
        assert len(result.issues) == 2

    def test_from_result_with_errors_fallback(self) -> None:
        """Verify from_result uses errors fallback."""
        data = {"errors": [{"message": "error1"}]}
        result = ValidationReport.from_result(data)
        assert len(result.issues) == 1

    def test_from_result_infers_valid_from_issues(self) -> None:
        """Verify from_result infers valid from issues."""
        data = {"issues": [{"message": "error"}]}
        result = ValidationReport.from_result(data)
        assert result.valid is False

    def test_from_result_with_metadata(self) -> None:
        """Verify from_result merges metadata."""
        data = {"metadata": {"key1": "value1"}}
        result = ValidationReport.from_result(
            data,
            metadata={"key2": "value2"},
        )
        assert result.metadata == {"key1": "value1", "key2": "value2"}

    def test_from_result_uses_summary_from_data(self) -> None:
        """Verify from_result uses summary from data."""
        data = {"summary": "Test summary"}
        result = ValidationReport.from_result(data)
        assert result.summary == "Test summary"

    def test_from_result_generates_summary_from_first_issue(self) -> None:
        """Verify from_result generates summary from first issue."""
        data = {"issues": [{"message": "First error"}]}
        result = ValidationReport.from_result(data)
        assert result.summary == "First error"

    def test_to_dict(self) -> None:
        """Verify to_dict serialization."""
        issue = ValidationIssue(message="error", severity=ValidationSeverity.ERROR)
        report = ValidationReport(
            valid=False,
            validation_type="type1",
            issues=[issue],
        )
        result = report.to_dict()
        assert result["valid"] is False
        assert result["validation_type"] == "type1"
        assert result["error_count"] == 1
        assert result["warning_count"] == 0


class TestQualityGateCheck:
    """Tests for QualityGateCheck model."""

    def test_minimal_quality_gate_check(self) -> None:
        """Verify minimal QualityGateCheck creation."""
        check = QualityGateCheck(name="test", passed=True)
        assert check.name == "test"
        assert check.passed is True
        assert check.severity == GateSeverity.REQUIRED
        assert check.score is None
        assert check.threshold is None
        assert check.message == ""
        assert check.details == {}
        assert check.duration_ms is None

    def test_quality_gate_check_with_all_fields(self) -> None:
        """Verify QualityGateCheck with all fields."""
        check = QualityGateCheck(
            name="test",
            passed=False,
            severity=GateSeverity.OPTIONAL,
            score=0.85,
            threshold=0.90,
            message="Score below threshold",
            details={"actual": 0.85},
            duration_ms=1500.5,
        )
        assert check.name == "test"
        assert check.passed is False
        assert check.severity == GateSeverity.OPTIONAL
        assert check.score == 0.85
        assert check.threshold == 0.90
        assert check.message == "Score below threshold"
        assert check.duration_ms == 1500.5

    def test_from_value_with_quality_gate_check(self) -> None:
        """Verify from_value returns same check."""
        check = QualityGateCheck(name="test", passed=True)
        result = QualityGateCheck.from_value(check)
        assert result is check

    def test_from_value_with_dict(self) -> None:
        """Verify from_value with dict."""
        data = {
            "name": "test_check",
            "passed": True,
            "severity": "optional",
            "score": "0.95",
            "threshold": "0.90",
            "message": "test message",
            "duration_ms": "1500",
        }
        result = QualityGateCheck.from_value(data)
        assert result.name == "test_check"
        assert result.passed is True
        assert result.severity == GateSeverity.OPTIONAL
        assert result.score == 0.95
        assert result.threshold == 0.90
        assert result.duration_ms == 1500.0

    def test_from_value_with_invalid_severity(self) -> None:
        """Verify from_value defaults invalid severity."""
        data = {"name": "test", "passed": True, "severity": "invalid"}
        result = QualityGateCheck.from_value(data)
        assert result.severity == GateSeverity.REQUIRED

    def test_from_value_with_invalid_score(self) -> None:
        """Verify from_value handles invalid score."""
        data = {"name": "test", "passed": True, "score": "not_a_number"}
        result = QualityGateCheck.from_value(data)
        assert result.score is None

    def test_to_dict(self) -> None:
        """Verify to_dict serialization."""
        check = QualityGateCheck(name="test", passed=True, score=0.95)
        result = check.to_dict()
        assert result["name"] == "test"
        assert result["passed"] is True
        assert result["score"] == 0.95


class TestQualityGateReport:
    """Tests for QualityGateReport model."""

    def test_minimal_quality_gate_report(self) -> None:
        """Verify minimal QualityGateReport creation."""
        report = QualityGateReport(
            fast_hooks=True,
            tests=True,
            comprehensive=True,
            coverage=0.95,
        )
        assert report.fast_hooks is True
        assert report.tests is True
        assert report.comprehensive is True
        assert report.coverage == 0.95
        assert report.errors == []
        assert report.checks == []

    def test_quality_gate_report_with_all_fields(self) -> None:
        """Verify QualityGateReport with all fields."""
        check = QualityGateCheck(name="test", passed=True)
        report = QualityGateReport(
            fast_hooks=True,
            tests=False,
            comprehensive=False,
            coverage=0.80,
            errors=["tests_failed"],
            checks=[check],
            repository="test/repo",
            profile="strict",
            source="crackerjack",
        )
        assert report.fast_hooks is True
        assert report.tests is False
        assert report.coverage == 0.80
        assert len(report.checks) == 1

    def test_passed_property(self) -> None:
        """Verify passed property."""
        report_passed = QualityGateReport(
            fast_hooks=True,
            tests=True,
            comprehensive=True,
            coverage=0.95,
        )
        assert report_passed.passed is True

        report_failed = QualityGateReport(
            fast_hooks=False,
            tests=True,
            comprehensive=True,
            coverage=0.95,
        )
        assert report_failed.passed is False

    def test_all_passed_property(self) -> None:
        """Verify all_passed property."""
        report = QualityGateReport(
            fast_hooks=True,
            tests=True,
            comprehensive=True,
            coverage=0.95,
        )
        assert report.all_passed is True

    def test_blocking_failure_property(self) -> None:
        """Verify blocking_failure property."""
        report1 = QualityGateReport(
            fast_hooks=False,
            tests=True,
            comprehensive=True,
            coverage=0.95,
        )
        assert report1.blocking_failure is True

        report2 = QualityGateReport(
            fast_hooks=True,
            tests=False,
            comprehensive=True,
            coverage=0.95,
        )
        assert report2.blocking_failure is True

        report3 = QualityGateReport(
            fast_hooks=True,
            tests=True,
            comprehensive=False,
            coverage=0.95,
        )
        assert report3.blocking_failure is False

    def test_warnings_property(self) -> None:
        """Verify warnings property filters warning checks."""
        warning_check = QualityGateCheck(
            name="optional_test",
            passed=False,
            severity=GateSeverity.WARNING,
        )
        required_check = QualityGateCheck(
            name="required_test",
            passed=False,
            severity=GateSeverity.REQUIRED,
        )
        report = QualityGateReport(
            fast_hooks=True,
            tests=True,
            comprehensive=True,
            coverage=0.95,
            checks=[warning_check, required_check],
        )
        assert len(report.warnings) == 1
        assert report.warnings[0] == "optional_test"

    def test_from_result_minimal(self) -> None:
        """Verify from_result with minimal data."""
        result = QualityGateReport.from_result({})
        assert isinstance(result, QualityGateReport)

    def test_from_result_with_all_fields(self) -> None:
        """Verify from_result with all fields."""
        data = {
            "fast_hooks": True,
            "tests": False,
            "comprehensive": False,
            "coverage": 0.85,
            "errors": ["test_failed"],
            "repository": "test/repo",
            "profile": "strict",
        }
        result = QualityGateReport.from_result(
            data,
            repository="test/repo",
            profile="strict",
        )
        assert result.fast_hooks is True
        assert result.tests is False
        assert result.coverage == 0.85

    def test_from_result_creates_default_checks(self) -> None:
        """Verify from_result creates default checks if none provided."""
        result = QualityGateReport.from_result({})
        assert len(result.checks) == 3
        assert result.checks[0].name == "fast_hooks"
        assert result.checks[1].name == "tests"
        assert result.checks[2].name == "comprehensive"

    def test_from_result_with_checks(self) -> None:
        """Verify from_result with provided checks."""
        data = {"checks": [{"name": "test_check", "passed": True}]}
        result = QualityGateReport.from_result(data)
        assert len(result.checks) == 1
        assert result.checks[0].name == "test_check"

    def test_from_result_extracts_errors_from_checks(self) -> None:
        """Verify from_result extracts errors from checks."""
        data = {
            "checks": [
                {"name": "check1", "passed": False, "severity": "required"},
                {"name": "check2", "passed": True, "severity": "required"},
            ]
        }
        result = QualityGateReport.from_result(data)
        assert "check1" in result.errors
        assert "check2" not in result.errors

    def test_from_result_with_invalid_coverage(self) -> None:
        """Verify from_result handles invalid coverage."""
        data = {"coverage": "not_a_number"}
        result = QualityGateReport.from_result(data)
        assert result.coverage == 0.0

    def test_to_dict(self) -> None:
        """Verify to_dict serialization."""
        check = QualityGateCheck(name="test", passed=True)
        report = QualityGateReport(
            fast_hooks=True,
            tests=True,
            comprehensive=True,
            coverage=0.95,
            checks=[check],
        )
        result = report.to_dict()
        assert result["passed"] is True
        assert result["all_passed"] is True
        assert result["blocking_failure"] is False
        assert result["warnings"] == []
