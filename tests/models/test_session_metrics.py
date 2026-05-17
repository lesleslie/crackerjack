"""Tests for session_metrics module."""

from __future__ import annotations

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
