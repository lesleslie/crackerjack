"""Tests for session_metrics module."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crackerjack.models.session_metrics import SessionMetrics


class TestSessionMetricsBasic:
    """Tests for basic SessionMetrics creation."""

    def test_minimal_session_metrics(self) -> None:
        """Verify minimal SessionMetrics creation."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="session-1",
            project_path=Path("/home/user/project"),
            start_time=start,
        )
        assert metrics.session_id == "session-1"
        assert metrics.project_path == Path("/home/user/project")
        assert metrics.start_time == start
        assert metrics.end_time is None
        assert metrics.duration_seconds is None

    def test_session_metrics_full(self) -> None:
        """Verify SessionMetrics with all fields."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 30, 0)
        metrics = SessionMetrics(
            session_id="session-2",
            project_path=Path("/home/user/project"),
            start_time=start,
            end_time=end,
            duration_seconds=1800,
            git_commit_velocity=2.5,
            git_branch_count=5,
            git_merge_success_rate=0.95,
            conventional_commit_compliance=0.98,
            git_workflow_efficiency_score=85.5,
            tests_run=100,
            tests_passed=98,
            test_pass_rate=0.98,
            ai_fixes_applied=12,
            quality_gate_passes=8,
        )
        assert metrics.session_id == "session-2"
        assert metrics.duration_seconds == 1800
        assert metrics.tests_passed == 98


class TestSessionMetricsValidation:
    """Tests for SessionMetrics validation in __post_init__."""

    def test_percentage_field_valid_zero(self) -> None:
        """Verify percentage fields accept 0.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            git_merge_success_rate=0.0,
        )
        assert metrics.git_merge_success_rate == 0.0

    def test_percentage_field_valid_one(self) -> None:
        """Verify percentage fields accept 1.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            test_pass_rate=1.0,
        )
        assert metrics.test_pass_rate == 1.0

    def test_percentage_field_valid_mid(self) -> None:
        """Verify percentage fields accept values between 0 and 1."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            conventional_commit_compliance=0.75,
        )
        assert metrics.conventional_commit_compliance == 0.75

    def test_percentage_field_invalid_too_high(self) -> None:
        """Verify percentage fields reject values > 1.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match="git_merge_success_rate must be between 0.0 and 1.0"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                git_merge_success_rate=1.5,
            )

    def test_percentage_field_invalid_negative(self) -> None:
        """Verify percentage fields reject negative values."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match="test_pass_rate must be between 0.0 and 1.0"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                test_pass_rate=-0.1,
            )

    def test_score_field_valid_zero(self) -> None:
        """Verify score fields accept 0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            git_workflow_efficiency_score=0,
        )
        assert metrics.git_workflow_efficiency_score == 0

    def test_score_field_valid_hundred(self) -> None:
        """Verify score fields accept 100."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            git_workflow_efficiency_score=100,
        )
        assert metrics.git_workflow_efficiency_score == 100

    def test_score_field_invalid_too_high(self) -> None:
        """Verify score fields reject values > 100."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match="git_workflow_efficiency_score must be between 0 and 100"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                git_workflow_efficiency_score=101,
            )

    def test_score_field_invalid_negative(self) -> None:
        """Verify score fields reject negative values."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match="git_workflow_efficiency_score must be between 0 and 100"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                git_workflow_efficiency_score=-1,
            )

    def test_non_negative_field_zero(self) -> None:
        """Verify non-negative fields accept 0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            tests_run=0,
        )
        assert metrics.tests_run == 0

    def test_non_negative_field_positive(self) -> None:
        """Verify non-negative fields accept positive values."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            ai_fixes_applied=10,
        )
        assert metrics.ai_fixes_applied == 10

    def test_non_negative_field_invalid(self) -> None:
        """Verify non-negative fields reject negative values."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match="duration_seconds must be non-negative"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                duration_seconds=-1,
            )

    def test_git_commit_velocity_negative(self) -> None:
        """Verify git_commit_velocity rejects negative values."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match="git_commit_velocity must be non-negative"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                git_commit_velocity=-0.5,
            )

    def test_git_commit_velocity_positive(self) -> None:
        """Verify git_commit_velocity accepts positive values."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            git_commit_velocity=2.5,
        )
        assert metrics.git_commit_velocity == 2.5


class TestSessionMetricsAutocalculation:
    """Tests for automatic calculations in __post_init__."""

    def test_duration_auto_calculation(self) -> None:
        """Verify duration_seconds is auto-calculated from start/end times."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 30, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            end_time=end,
        )
        assert metrics.duration_seconds == 1800

    def test_duration_auto_calculation_not_overridden(self) -> None:
        """Verify explicit duration_seconds is not overridden."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 30, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            end_time=end,
            duration_seconds=3600,
        )
        assert metrics.duration_seconds == 3600

    def test_test_pass_rate_auto_calculation(self) -> None:
        """Verify test_pass_rate is auto-calculated from tests_run/tests_passed."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            tests_run=100,
            tests_passed=95,
        )
        assert metrics.test_pass_rate == 0.95

    def test_test_pass_rate_not_overridden(self) -> None:
        """Verify explicit test_pass_rate is not overridden."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            tests_run=100,
            tests_passed=95,
            test_pass_rate=0.90,
        )
        assert metrics.test_pass_rate == 0.90

    def test_test_pass_rate_zero_runs(self) -> None:
        """Verify test_pass_rate stays None when tests_run is 0 (falsy)."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            tests_run=0,
            tests_passed=0,
        )
        assert metrics.test_pass_rate is None


class TestSessionMetricsCalculateDuration:
    """Tests for calculate_duration() method."""

    def test_calculate_duration_with_both_times(self) -> None:
        """Verify calculate_duration() computes duration."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 45, 30)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            end_time=end,
        )
        result = metrics.calculate_duration()
        assert result == 2730  # 45 minutes 30 seconds

    def test_calculate_duration_updates_field(self) -> None:
        """Verify calculate_duration() updates duration_seconds field."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 11, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            end_time=end,
        )
        metrics.duration_seconds = None
        result = metrics.calculate_duration()
        assert metrics.duration_seconds == 3600
        assert result == 3600

    def test_calculate_duration_no_end_time(self) -> None:
        """Verify calculate_duration() returns None if no end_time."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
        )
        result = metrics.calculate_duration()
        assert result is None

    def test_calculate_duration_no_start_time(self) -> None:
        """Verify calculate_duration() returns None if no start_time."""
        end = datetime(2026, 5, 16, 10, 30, 0)
        # This would be an unusual state, but test for robustness
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=datetime(2026, 5, 16, 10, 0, 0),
        )
        metrics.start_time = None  # type: ignore
        metrics.end_time = end
        result = metrics.calculate_duration()
        assert result is None


class TestSessionMetricsToDict:
    """Tests for to_dict() method."""

    def test_to_dict_minimal(self) -> None:
        """Verify to_dict() serializes minimal metrics."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test/path"),
            start_time=start,
        )
        data = metrics.to_dict()
        assert data["session_id"] == "test"
        assert data["project_path"] == "/test/path"
        assert isinstance(data["project_path"], str)
        assert data["start_time"] == "2026-05-16T10:00:00"
        assert isinstance(data["start_time"], str)

    def test_to_dict_full(self) -> None:
        """Verify to_dict() serializes all fields."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 30, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test/path"),
            start_time=start,
            end_time=end,
            duration_seconds=1800,
            tests_run=100,
            tests_passed=95,
            test_pass_rate=0.95,
        )
        data = metrics.to_dict()
        assert data["end_time"] == "2026-05-16T10:30:00"
        assert isinstance(data["end_time"], str)
        assert data["duration_seconds"] == 1800
        assert data["tests_run"] == 100

    def test_to_dict_path_conversion(self) -> None:
        """Verify to_dict() converts Path to string."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/home/user/project"),
            start_time=start,
        )
        data = metrics.to_dict()
        assert data["project_path"] == "/home/user/project"
        assert isinstance(data["project_path"], str)

    def test_to_dict_datetime_conversion(self) -> None:
        """Verify to_dict() converts datetime to ISO format."""
        start = datetime(2026, 5, 16, 10, 30, 45)
        end = datetime(2026, 5, 16, 11, 15, 30)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            end_time=end,
        )
        data = metrics.to_dict()
        assert data["start_time"] == "2026-05-16T10:30:45"
        assert data["end_time"] == "2026-05-16T11:15:30"


class TestSessionMetricsFromDict:
    """Tests for from_dict() classmethod."""

    def test_from_dict_minimal(self) -> None:
        """Verify from_dict() creates metrics from minimal data."""
        data = {
            "session_id": "session-1",
            "project_path": "/test/path",
            "start_time": "2026-05-16T10:00:00",
        }
        metrics = SessionMetrics.from_dict(data)
        assert metrics.session_id == "session-1"
        assert metrics.project_path == Path("/test/path")
        assert metrics.start_time == datetime(2026, 5, 16, 10, 0, 0)

    def test_from_dict_full(self) -> None:
        """Verify from_dict() creates metrics from full data."""
        data = {
            "session_id": "session-1",
            "project_path": "/test/path",
            "start_time": "2026-05-16T10:00:00",
            "end_time": "2026-05-16T10:30:00",
            "duration_seconds": 1800,
            "tests_run": 100,
            "tests_passed": 95,
            "test_pass_rate": 0.95,
        }
        metrics = SessionMetrics.from_dict(data)
        assert metrics.session_id == "session-1"
        assert metrics.duration_seconds == 1800
        assert metrics.tests_passed == 95

    def test_from_dict_path_object(self) -> None:
        """Verify from_dict() accepts Path object."""
        data = {
            "session_id": "session-1",
            "project_path": Path("/test/path"),
            "start_time": "2026-05-16T10:00:00",
        }
        metrics = SessionMetrics.from_dict(data)
        assert metrics.project_path == Path("/test/path")

    def test_from_dict_datetime_object(self) -> None:
        """Verify from_dict() accepts datetime object."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        data = {
            "session_id": "session-1",
            "project_path": "/test",
            "start_time": start,
        }
        metrics = SessionMetrics.from_dict(data)
        assert metrics.start_time == start

    def test_from_dict_missing_required_field(self) -> None:
        """Verify from_dict() raises ValueError for missing required fields."""
        data = {
            "session_id": "session-1",
            "project_path": "/test",
            # Missing start_time
        }
        with pytest.raises(ValueError, match="Missing required fields"):
            SessionMetrics.from_dict(data)

    def test_from_dict_missing_multiple_required_fields(self) -> None:
        """Verify from_dict() reports all missing required fields."""
        data = {
            "session_id": "session-1",
            # Missing project_path and start_time
        }
        with pytest.raises(ValueError, match="project_path.*start_time"):
            SessionMetrics.from_dict(data)

    def test_from_dict_roundtrip(self) -> None:
        """Verify from_dict(to_dict()) roundtrip works."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 30, 0)
        original = SessionMetrics(
            session_id="test",
            project_path=Path("/test/path"),
            start_time=start,
            end_time=end,
            tests_run=100,
            tests_passed=95,
        )
        data = original.to_dict()
        restored = SessionMetrics.from_dict(data)
        assert restored.session_id == original.session_id
        assert restored.project_path == original.project_path
        assert restored.start_time == original.start_time
        assert restored.end_time == original.end_time


class TestSessionMetricsGetSummary:
    """Tests for get_summary() method."""

    def test_get_summary_basic(self) -> None:
        """Verify get_summary() with basic metrics."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 30, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            end_time=end,
            tests_run=100,
            tests_passed=95,
            test_pass_rate=0.95,
        )
        summary = metrics.get_summary()
        assert summary["session_id"] == "test"
        assert summary["duration_seconds"] == 1800
        assert summary["tests_run"] == 100
        assert summary["tests_passed"] == 95
        assert summary["test_pass_rate"] == 0.95

    def test_get_summary_includes_git_metrics(self) -> None:
        """Verify get_summary() includes git_metrics when present."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            git_commit_velocity=2.5,
            git_branch_count=5,
            git_merge_success_rate=0.95,
            conventional_commit_compliance=0.98,
            git_workflow_efficiency_score=85.0,
        )
        summary = metrics.get_summary()
        assert "git_metrics" in summary
        assert summary["git_metrics"]["commit_velocity"] == 2.5
        assert summary["git_metrics"]["branch_count"] == 5
        assert summary["git_metrics"]["merge_success_rate"] == 0.95

    def test_get_summary_includes_quality_metrics(self) -> None:
        """Verify get_summary() includes quality_metrics when present."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            ai_fixes_applied=12,
            quality_gate_passes=8,
        )
        summary = metrics.get_summary()
        assert "quality_metrics" in summary
        assert summary["quality_metrics"]["ai_fixes_applied"] == 12
        assert summary["quality_metrics"]["quality_gate_passes"] == 8

    def test_get_summary_excludes_git_metrics_when_absent(self) -> None:
        """Verify get_summary() excludes git_metrics when all None."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
        )
        summary = metrics.get_summary()
        assert "git_metrics" not in summary

    def test_get_summary_excludes_quality_metrics_when_absent(self) -> None:
        """Verify get_summary() excludes quality_metrics when all None."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            tests_run=100,
        )
        summary = metrics.get_summary()
        assert "quality_metrics" not in summary

    def test_get_summary_full(self) -> None:
        """Verify get_summary() with all metrics."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 11, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            end_time=end,
            git_commit_velocity=2.5,
            git_branch_count=3,
            git_merge_success_rate=0.95,
            conventional_commit_compliance=0.98,
            git_workflow_efficiency_score=90.0,
            tests_run=50,
            tests_passed=48,
            test_pass_rate=0.96,
            ai_fixes_applied=5,
            quality_gate_passes=4,
        )
        summary = metrics.get_summary()
        assert summary["session_id"] == "test"
        assert summary["duration_seconds"] == 3600
        assert "git_metrics" in summary
        assert "quality_metrics" in summary
        assert summary["git_metrics"]["efficiency_score"] == 90.0
        assert summary["quality_metrics"]["ai_fixes_applied"] == 5


class TestSessionMetricsExtraValidation:
    """Tests covering non-negative validation for fields not yet directly tested."""

    @pytest.mark.parametrize(
        "field_name",
        [
            "git_branch_count",
            "tests_passed",
            "quality_gate_passes",
        ],
    )
    def test_non_negative_field_rejects_negative(self, field_name: str) -> None:
        """Verify each non-negative field rejects negative values."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match=f"{field_name} must be non-negative"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                **{field_name: -1},
            )

    @pytest.mark.parametrize(
        "field_name",
        [
            "git_branch_count",
            "tests_passed",
            "quality_gate_passes",
            "tests_run",
            "ai_fixes_applied",
            "duration_seconds",
        ],
    )
    def test_non_negative_field_accepts_zero(self, field_name: str) -> None:
        """Verify each non-negative field accepts 0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            **{field_name: 0},
        )
        assert getattr(metrics, field_name) == 0

    def test_git_branch_count_negative_rejected(self) -> None:
        """Verify git_branch_count rejects negative values explicitly."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match="git_branch_count must be non-negative"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                git_branch_count=-3,
            )

    def test_tests_passed_negative_rejected(self) -> None:
        """Verify tests_passed rejects negative values explicitly."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match="tests_passed must be non-negative"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                tests_passed=-1,
            )

    def test_quality_gate_passes_negative_rejected(self) -> None:
        """Verify quality_gate_passes rejects negative values explicitly."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(ValueError, match="quality_gate_passes must be non-negative"):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                quality_gate_passes=-5,
            )

    def test_conventional_commit_compliance_zero(self) -> None:
        """Verify conventional_commit_compliance boundary at 0.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            conventional_commit_compliance=0.0,
        )
        assert metrics.conventional_commit_compliance == 0.0

    def test_conventional_commit_compliance_one(self) -> None:
        """Verify conventional_commit_compliance boundary at 1.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            conventional_commit_compliance=1.0,
        )
        assert metrics.conventional_commit_compliance == 1.0

    def test_conventional_commit_compliance_invalid_high(self) -> None:
        """Verify conventional_commit_compliance rejects > 1.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(
            ValueError,
            match="conventional_commit_compliance must be between 0.0 and 1.0",
        ):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                conventional_commit_compliance=1.1,
            )

    def test_conventional_commit_compliance_invalid_negative(self) -> None:
        """Verify conventional_commit_compliance rejects < 0.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(
            ValueError,
            match="conventional_commit_compliance must be between 0.0 and 1.0",
        ):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                conventional_commit_compliance=-0.1,
            )

    def test_git_merge_success_rate_zero(self) -> None:
        """Verify git_merge_success_rate accepts 0.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            git_merge_success_rate=0.0,
        )
        assert metrics.git_merge_success_rate == 0.0

    def test_git_merge_success_rate_one(self) -> None:
        """Verify git_merge_success_rate accepts 1.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            git_merge_success_rate=1.0,
        )
        assert metrics.git_merge_success_rate == 1.0

    def test_git_merge_success_rate_negative_rejected(self) -> None:
        """Verify git_merge_success_rate rejects < 0.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(
            ValueError,
            match="git_merge_success_rate must be between 0.0 and 1.0",
        ):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                git_merge_success_rate=-0.1,
            )

    def test_test_pass_rate_zero(self) -> None:
        """Verify test_pass_rate accepts 0.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            test_pass_rate=0.0,
        )
        assert metrics.test_pass_rate == 0.0

    def test_test_pass_rate_high_rejected(self) -> None:
        """Verify test_pass_rate rejects > 1.0."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        with pytest.raises(
            ValueError, match="test_pass_rate must be between 0.0 and 1.0"
        ):
            SessionMetrics(
                session_id="test",
                project_path=Path("/test"),
                start_time=start,
                test_pass_rate=1.1,
            )


class TestSessionMetricsComputePaths:
    """Tests for _compute_duration_if_needed and _compute_test_pass_rate_if_needed."""

    def test_duration_not_computed_when_end_none(self) -> None:
        """Verify duration_seconds stays None when end_time is missing."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
        )
        assert metrics.end_time is None
        assert metrics.duration_seconds is None

    def test_duration_not_computed_when_start_missing(self) -> None:
        """Verify _compute_duration_if_needed is a no-op without start_time."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
        )
        # Mutate after construction to simulate missing start_time.
        metrics.start_time = None  # type: ignore[assignment]
        # Calling helper directly should leave duration_seconds unchanged.
        metrics._compute_duration_if_needed()
        assert metrics.duration_seconds is None

    def test_duration_not_computed_when_both_missing(self) -> None:
        """Verify _compute_duration_if_needed is a no-op with no times set."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
        )
        metrics.start_time = None  # type: ignore[assignment]
        metrics.end_time = None
        metrics._compute_duration_if_needed()
        assert metrics.duration_seconds is None

    def test_duration_not_overwritten_when_already_set(self) -> None:
        """Verify explicit duration_seconds survives _compute_duration_if_needed."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 30, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            end_time=end,
            duration_seconds=999,
        )
        metrics._compute_duration_if_needed()
        assert metrics.duration_seconds == 999

    def test_test_pass_rate_not_computed_when_tests_passed_none(self) -> None:
        """Verify test_pass_rate stays None when tests_passed is None."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            tests_run=100,
            tests_passed=None,
        )
        assert metrics.test_pass_rate is None

    def test_test_pass_rate_not_computed_when_tests_run_none(self) -> None:
        """Verify test_pass_rate stays None when tests_run is None."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            tests_passed=5,
        )
        assert metrics.test_pass_rate is None

    def test_test_pass_rate_not_computed_when_both_tests_none(self) -> None:
        """Verify test_pass_rate stays None when both tests fields are None."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
        )
        assert metrics.test_pass_rate is None

    def test_test_pass_rate_direct_call_overwrites_none(self) -> None:
        """Verify calling _compute_test_pass_rate_if_needed sets the rate when missing."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            tests_run=10,
            tests_passed=7,
        )
        # Pre-set to None and confirm helper computes it.
        metrics.test_pass_rate = None
        metrics._compute_test_pass_rate_if_needed()
        assert metrics.test_pass_rate == 0.7

    def test_test_pass_rate_direct_call_skips_when_already_set(self) -> None:
        """Verify helper does not overwrite an existing test_pass_rate."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
            tests_run=10,
            tests_passed=7,
            test_pass_rate=0.5,
        )
        metrics._compute_test_pass_rate_if_needed()
        assert metrics.test_pass_rate == 0.5


class TestSessionMetricsCalculateDurationLogging:
    """Tests that calculate_duration() emits the expected debug log lines."""

    def test_calculate_duration_logs_debug_on_success(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify calculate_duration() logs the computed duration."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 30, 0)
        metrics = SessionMetrics(
            session_id="session-log-success",
            project_path=Path("/test"),
            start_time=start,
            end_time=end,
        )
        with caplog.at_level(logging.DEBUG, logger="crackerjack.models.session_metrics"):
            metrics.calculate_duration()
        assert any(
            "Calculated duration for session session-log-success" in record.message
            for record in caplog.records
        )

    def test_calculate_duration_logs_cannot_calculate_missing_end(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify calculate_duration() logs 'Cannot calculate' when end is None."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="session-log-noend",
            project_path=Path("/test"),
            start_time=start,
        )
        with caplog.at_level(logging.DEBUG, logger="crackerjack.models.session_metrics"):
            assert metrics.calculate_duration() is None
        assert any(
            "Cannot calculate duration for session session-log-noend" in record.message
            for record in caplog.records
        )

    def test_calculate_duration_logs_cannot_calculate_missing_start(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify calculate_duration() logs 'Cannot calculate' when start is None."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 10, 30, 0)
        metrics = SessionMetrics(
            session_id="session-log-nostart",
            project_path=Path("/test"),
            start_time=start,
        )
        metrics.start_time = None  # type: ignore[assignment]
        metrics.end_time = end
        with caplog.at_level(logging.DEBUG, logger="crackerjack.models.session_metrics"):
            assert metrics.calculate_duration() is None
        assert any(
            "Cannot calculate duration for session session-log-nostart"
            in record.message
            for record in caplog.records
        )


class TestSessionMetricsToDictExtra:
    """Additional to_dict() tests covering edge cases and branch coverage."""

    def test_to_dict_with_end_time_none(self) -> None:
        """Verify end_time=None is serialized as None (not converted)."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test"),
            start_time=start,
        )
        data = metrics.to_dict()
        assert data["end_time"] is None
        assert data["start_time"] == "2026-05-16T10:00:00"

    def test_to_dict_when_project_path_already_string(self) -> None:
        """Verify to_dict() leaves an already-string project_path untouched."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test/path"),
            start_time=start,
        )
        # Mutate to simulate a non-Path project_path stored in the dict.
        metrics.project_path = "/already/string"  # type: ignore[assignment]
        data = metrics.to_dict()
        assert data["project_path"] == "/already/string"

    def test_to_dict_when_start_time_already_string(self) -> None:
        """Verify to_dict() skips isoformat conversion for non-datetime start_time."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test/path"),
            start_time=start,
        )
        # Mutate to simulate an already-serialized start_time.
        metrics.start_time = "2026-05-16T10:00:00"  # type: ignore[assignment]
        data = metrics.to_dict()
        assert data["start_time"] == "2026-05-16T10:00:00"

    def test_to_dict_when_start_time_none(self) -> None:
        """Verify to_dict() handles start_time=None gracefully."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="test",
            project_path=Path("/test/path"),
            start_time=start,
        )
        metrics.start_time = None  # type: ignore[assignment]
        data = metrics.to_dict()
        assert data["start_time"] is None


class TestSessionMetricsFromDictExtra:
    """Additional from_dict() tests covering missing end_time and full round-trips."""

    def test_from_dict_end_time_string_round_trips(self) -> None:
        """Verify end_time as a string is converted to datetime."""
        data = {
            "session_id": "session-1",
            "project_path": "/test/path",
            "start_time": "2026-05-16T10:00:00",
            "end_time": "2026-05-16T10:30:00",
        }
        metrics = SessionMetrics.from_dict(data)
        assert metrics.end_time == datetime(2026, 5, 16, 10, 30, 0)

    def test_from_dict_end_time_absent(self) -> None:
        """Verify end_time defaults to None when absent from input dict."""
        data = {
            "session_id": "session-1",
            "project_path": "/test/path",
            "start_time": "2026-05-16T10:00:00",
        }
        metrics = SessionMetrics.from_dict(data)
        assert metrics.end_time is None

    def test_from_dict_round_trip_with_all_optional_fields(self) -> None:
        """Verify from_dict(to_dict(metrics)) preserves all optional fields."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        end = datetime(2026, 5, 16, 11, 0, 0)
        original = SessionMetrics(
            session_id="full-round-trip",
            project_path=Path("/home/user/proj"),
            start_time=start,
            end_time=end,
            duration_seconds=3600,
            git_commit_velocity=2.5,
            git_branch_count=3,
            git_merge_success_rate=0.95,
            conventional_commit_compliance=0.90,
            git_workflow_efficiency_score=88.5,
            tests_run=200,
            tests_passed=190,
            test_pass_rate=0.95,
            ai_fixes_applied=7,
            quality_gate_passes=4,
        )
        data = original.to_dict()
        restored = SessionMetrics.from_dict(data)
        assert restored.git_commit_velocity == original.git_commit_velocity
        assert restored.git_branch_count == original.git_branch_count
        assert restored.git_merge_success_rate == original.git_merge_success_rate
        assert (
            restored.conventional_commit_compliance
            == original.conventional_commit_compliance
        )
        assert (
            restored.git_workflow_efficiency_score
            == original.git_workflow_efficiency_score
        )
        assert restored.tests_run == original.tests_run
        assert restored.tests_passed == original.tests_passed
        assert restored.test_pass_rate == original.test_pass_rate
        assert restored.ai_fixes_applied == original.ai_fixes_applied
        assert restored.quality_gate_passes == original.quality_gate_passes
        assert restored.duration_seconds == original.duration_seconds

    def test_from_dict_missing_session_id(self) -> None:
        """Verify ValueError is raised when session_id is absent."""
        data = {
            "project_path": "/test",
            "start_time": "2026-05-16T10:00:00",
        }
        with pytest.raises(ValueError, match="Missing required fields: session_id"):
            SessionMetrics.from_dict(data)

    def test_from_dict_missing_project_path(self) -> None:
        """Verify ValueError is raised when project_path is absent."""
        data = {
            "session_id": "session-1",
            "start_time": "2026-05-16T10:00:00",
        }
        with pytest.raises(
            ValueError, match="Missing required fields: project_path"
        ):
            SessionMetrics.from_dict(data)


class TestSessionMetricsGetSummaryExtra:
    """Additional get_summary() tests covering minimal/bare-session scenarios."""

    def test_get_summary_bare_session(self) -> None:
        """Verify get_summary() returns only base keys when no extras are present."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="bare",
            project_path=Path("/test"),
            start_time=start,
        )
        summary = metrics.get_summary()
        assert set(summary.keys()) == {
            "session_id",
            "duration_seconds",
            "tests_passed",
            "tests_run",
            "test_pass_rate",
        }
        assert "git_metrics" not in summary
        assert "quality_metrics" not in summary

    def test_get_summary_with_only_one_git_field(self) -> None:
        """Verify git_metrics is added when a single git field is present."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="one-git",
            project_path=Path("/test"),
            start_time=start,
            git_branch_count=4,
        )
        summary = metrics.get_summary()
        assert "git_metrics" in summary
        assert summary["git_metrics"]["branch_count"] == 4
        assert summary["git_metrics"]["commit_velocity"] is None
        assert summary["git_metrics"]["merge_success_rate"] is None

    def test_get_summary_with_only_one_quality_field(self) -> None:
        """Verify quality_metrics is added when a single quality field is present."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="one-quality",
            project_path=Path("/test"),
            start_time=start,
            ai_fixes_applied=3,
        )
        summary = metrics.get_summary()
        assert "quality_metrics" in summary
        assert summary["quality_metrics"]["ai_fixes_applied"] == 3
        assert summary["quality_metrics"]["quality_gate_passes"] is None

    def test_get_summary_with_only_quality_gate_passes(self) -> None:
        """Verify quality_metrics is added when only quality_gate_passes is set."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="qgp",
            project_path=Path("/test"),
            start_time=start,
            quality_gate_passes=2,
        )
        summary = metrics.get_summary()
        assert "quality_metrics" in summary
        assert summary["quality_metrics"]["quality_gate_passes"] == 2

    def test_get_summary_with_only_git_commit_velocity(self) -> None:
        """Verify git_metrics is added when only git_commit_velocity is set."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="vel",
            project_path=Path("/test"),
            start_time=start,
            git_commit_velocity=1.5,
        )
        summary = metrics.get_summary()
        assert "git_metrics" in summary
        assert summary["git_metrics"]["commit_velocity"] == 1.5

    def test_get_summary_with_only_git_merge_success_rate(self) -> None:
        """Verify git_metrics is added when only git_merge_success_rate is set."""
        start = datetime(2026, 5, 16, 10, 0, 0)
        metrics = SessionMetrics(
            session_id="merge",
            project_path=Path("/test"),
            start_time=start,
            git_merge_success_rate=0.8,
        )
        summary = metrics.get_summary()
        assert "git_metrics" in summary
        assert summary["git_metrics"]["merge_success_rate"] == 0.8
