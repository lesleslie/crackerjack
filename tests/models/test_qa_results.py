"""Tests for qa_results module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus


class TestQAResultStatus:
    """Tests for QAResultStatus enum."""

    def test_enum_values(self) -> None:
        """Verify all status values."""
        assert QAResultStatus.SUCCESS.value == "success"
        assert QAResultStatus.FAILURE.value == "failure"
        assert QAResultStatus.WARNING.value == "warning"
        assert QAResultStatus.SKIPPED.value == "skipped"
        assert QAResultStatus.ERROR.value == "error"

    def test_enum_members(self) -> None:
        """Verify all status members exist."""
        members = {member.value for member in QAResultStatus}
        assert members == {"success", "failure", "warning", "skipped", "error"}


class TestQACheckType:
    """Tests for QACheckType enum."""

    def test_enum_values(self) -> None:
        """Verify all check type values."""
        assert QACheckType.LINT.value == "lint"
        assert QACheckType.FORMAT.value == "format"
        assert QACheckType.TYPE.value == "type"
        assert QACheckType.SECURITY.value == "security"
        assert QACheckType.SAST.value == "sast"
        assert QACheckType.COMPLEXITY.value == "complexity"
        assert QACheckType.REFACTOR.value == "refactor"
        assert QACheckType.TEST.value == "test"
        assert QACheckType.BENCHMARK.value == "benchmark"
        assert QACheckType.PROFILE.value == "profile"

    def test_enum_members(self) -> None:
        """Verify all check type members exist."""
        members = {member.value for member in QACheckType}
        expected = {
            "lint",
            "format",
            "type",
            "security",
            "sast",
            "complexity",
            "refactor",
            "test",
            "benchmark",
            "profile",
        }
        assert members == expected


class TestQAResult:
    """Tests for QAResult model."""

    @pytest.fixture
    def check_id(self) -> UUID:
        """Provide a check ID."""
        return uuid4()

    def test_minimal_result(self, check_id: UUID) -> None:
        """Verify minimal QAResult creation."""
        result = QAResult(
            check_id=check_id,
            check_name="test-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
        )
        assert result.check_id == check_id
        assert result.check_name == "test-check"
        assert result.check_type == QACheckType.LINT
        assert result.status == QAResultStatus.SUCCESS

    def test_default_values(self, check_id: UUID) -> None:
        """Verify default field values."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
        )
        assert result.message == ""
        assert result.details == ""
        assert result.parsed_issues == []
        assert result.files_checked == []
        assert result.files_modified == []
        assert result.issues_found == 0
        assert result.issues_fixed == 0
        assert result.execution_time_ms == 0.0
        assert isinstance(result.timestamp, datetime)
        assert result.metadata == {}

    def test_all_fields(self, check_id: UUID) -> None:
        """Verify QAResult with all fields set."""
        now = datetime.now()
        files = [Path("/test1.py"), Path("/test2.py")]
        issues = [{"line": 1, "col": 2, "message": "issue"}]
        metadata = {"version": "1.0"}

        result = QAResult(
            check_id=check_id,
            check_name="full-check",
            check_type=QACheckType.TYPE,
            status=QAResultStatus.FAILURE,
            message="Type check failed",
            details="Detailed output here",
            parsed_issues=issues,
            files_checked=files,
            files_modified=files,
            issues_found=5,
            issues_fixed=2,
            execution_time_ms=1234.5,
            timestamp=now,
            metadata=metadata,
        )

        assert result.check_name == "full-check"
        assert result.check_type == QACheckType.TYPE
        assert result.status == QAResultStatus.FAILURE
        assert result.message == "Type check failed"
        assert result.details == "Detailed output here"
        assert result.parsed_issues == issues
        assert result.files_checked == files
        assert result.files_modified == files
        assert result.issues_found == 5
        assert result.issues_fixed == 2
        assert result.execution_time_ms == 1234.5
        assert result.timestamp == now
        assert result.metadata == metadata

    def test_is_success_with_success_status(self, check_id: UUID) -> None:
        """Verify is_success for SUCCESS status."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
        )
        assert result.is_success is True

    def test_is_success_with_warning_status(self, check_id: UUID) -> None:
        """Verify is_success includes WARNING status."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.WARNING,
        )
        assert result.is_success is True

    def test_is_success_with_failure_status(self, check_id: UUID) -> None:
        """Verify is_success is False for FAILURE status."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.FAILURE,
        )
        assert result.is_success is False

    def test_is_success_with_skipped_status(self, check_id: UUID) -> None:
        """Verify is_success is False for SKIPPED status."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SKIPPED,
        )
        assert result.is_success is False

    def test_is_failure_with_failure_status(self, check_id: UUID) -> None:
        """Verify is_failure for FAILURE status."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.FAILURE,
        )
        assert result.is_failure is True

    def test_is_failure_with_success_status(self, check_id: UUID) -> None:
        """Verify is_failure is False for SUCCESS status."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
        )
        assert result.is_failure is False

    def test_is_failure_with_other_statuses(self, check_id: UUID) -> None:
        """Verify is_failure is False for non-FAILURE statuses."""
        for status in [
            QAResultStatus.WARNING,
            QAResultStatus.SKIPPED,
            QAResultStatus.ERROR,
        ]:
            result = QAResult(
                check_id=check_id,
                check_name="test",
                check_type=QACheckType.LINT,
                status=status,
            )
            assert result.is_failure is False

    def test_is_warning_true(self, check_id: UUID) -> None:
        """Verify is_warning for WARNING status."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.WARNING,
        )
        assert result.is_warning is True

    def test_is_warning_false(self, check_id: UUID) -> None:
        """Verify is_warning is False for non-WARNING statuses."""
        for status in [
            QAResultStatus.SUCCESS,
            QAResultStatus.FAILURE,
            QAResultStatus.SKIPPED,
            QAResultStatus.ERROR,
        ]:
            result = QAResult(
                check_id=check_id,
                check_name="test",
                check_type=QACheckType.LINT,
                status=status,
            )
            assert result.is_warning is False

    def test_has_issues_true(self, check_id: UUID) -> None:
        """Verify has_issues returns True when issues found."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            issues_found=5,
        )
        assert result.has_issues is True

    def test_has_issues_false(self, check_id: UUID) -> None:
        """Verify has_issues returns False when no issues found."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            issues_found=0,
        )
        assert result.has_issues is False

    def test_to_summary_minimal(self, check_id: UUID) -> None:
        """Verify to_summary with minimal fields."""
        result = QAResult(
            check_id=check_id,
            check_name="ruff-lint",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
        )
        summary = result.to_summary()
        assert summary == "ruff-lint: success"

    def test_to_summary_with_issues(self, check_id: UUID) -> None:
        """Verify to_summary includes issue count."""
        result = QAResult(
            check_id=check_id,
            check_name="mypy",
            check_type=QACheckType.TYPE,
            status=QAResultStatus.FAILURE,
            issues_found=3,
        )
        summary = result.to_summary()
        assert "mypy: failure" in summary
        assert "3 issues found" in summary

    def test_to_summary_with_fixed(self, check_id: UUID) -> None:
        """Verify to_summary includes fixed count."""
        result = QAResult(
            check_id=check_id,
            check_name="formatter",
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.SUCCESS,
            issues_fixed=2,
        )
        summary = result.to_summary()
        assert "formatter: success" in summary
        assert "2 fixed" in summary

    def test_to_summary_with_time(self, check_id: UUID) -> None:
        """Verify to_summary includes execution time."""
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.TEST,
            status=QAResultStatus.SUCCESS,
            execution_time_ms=1234.7,
        )
        summary = result.to_summary()
        assert "test: success" in summary
        assert "1235ms" in summary  # Rounded to nearest ms

    def test_to_summary_all_fields(self, check_id: UUID) -> None:
        """Verify to_summary with all relevant fields."""
        result = QAResult(
            check_id=check_id,
            check_name="comprehensive-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.WARNING,
            issues_found=2,
            issues_fixed=1,
            execution_time_ms=500.0,
        )
        summary = result.to_summary()
        assert "comprehensive-check: warning" in summary
        assert "2 issues found" in summary
        assert "1 fixed" in summary
        assert "500ms" in summary

    def test_to_summary_zero_time_excluded(self, check_id: UUID) -> None:
        """Verify to_summary excludes time when 0ms."""
        result = QAResult(
            check_id=check_id,
            check_name="instant-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            execution_time_ms=0.0,
        )
        summary = result.to_summary()
        assert "(0ms)" not in summary
        assert summary == "instant-check: success"

    def test_different_check_types(self, check_id: UUID) -> None:
        """Verify QAResult works with all check types."""
        for check_type in QACheckType:
            result = QAResult(
                check_id=check_id,
                check_name=f"test-{check_type.value}",
                check_type=check_type,
                status=QAResultStatus.SUCCESS,
            )
            assert result.check_type == check_type

    def test_missing_required_field(self) -> None:
        """Verify ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            QAResult(
                check_id=uuid4(),
                check_name="test",
                # Missing check_type and status
            )

    def test_invalid_check_type(self, check_id: UUID) -> None:
        """Verify ValidationError for invalid check type."""
        with pytest.raises(ValidationError):
            QAResult(
                check_id=check_id,
                check_name="test",
                check_type="invalid-type",  # type: ignore
                status=QAResultStatus.SUCCESS,
            )

    def test_invalid_status(self, check_id: UUID) -> None:
        """Verify ValidationError for invalid status."""
        with pytest.raises(ValidationError):
            QAResult(
                check_id=check_id,
                check_name="test",
                check_type=QACheckType.LINT,
                status="invalid-status",  # type: ignore
            )

    def test_negative_issues_found(self, check_id: UUID) -> None:
        """Verify negative issues_found is accepted (Pydantic allows negative ints)."""
        # Pydantic doesn't validate int ranges by default
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            issues_found=-1,
        )
        assert result.issues_found == -1

    def test_path_serialization(self, check_id: UUID) -> None:
        """Verify Path objects are handled correctly."""
        path1 = Path("/test/path1.py")
        path2 = Path("/test/path2.py")
        result = QAResult(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            files_checked=[path1, path2],
        )
        assert result.files_checked == [path1, path2]
