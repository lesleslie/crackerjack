"""Test suite for SessionMetrics dataclass.

Tests the SessionMetrics model which captures session activity data including
git workflow metrics, quality gate results, and timing information for
analyzing development patterns and productivity trends.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crackerjack.models.session_metrics import SessionMetrics


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_session_metrics():
    """Fixture providing valid SessionMetrics with basic data."""
    return SessionMetrics(
        session_id="test-session-123",
        project_path=Path("/tmp/test_project"),
        start_time=datetime(2025, 2, 11, 10, 0, 0),
    )


@pytest.fixture
def metrics_with_git_data():
    """Fixture providing SessionMetrics with git metrics populated."""
    return SessionMetrics(
        session_id="git-session-456",
        project_path=Path("/tmp/test_project"),
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        end_time=datetime(2025, 2, 11, 11, 30, 0),
        git_commit_velocity=3.5,
        git_branch_count=5,
        git_merge_success_rate=0.85,
        conventional_commit_compliance=0.92,
        git_workflow_efficiency_score=78.5,
    )


@pytest.fixture
def metrics_with_quality_data():
    """Fixture providing SessionMetrics with quality metrics populated."""
    return SessionMetrics(
        session_id="quality-session-789",
        project_path=Path("/tmp/test_project"),
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        end_time=datetime(2025, 2, 11, 11, 0, 0),
        tests_run=150,
        tests_passed=142,
        ai_fixes_applied=3,
        quality_gate_passes=5,
    )


@pytest.fixture
def metrics_with_all_data():
    """Fixture providing SessionMetrics with all fields populated."""
    return SessionMetrics(
        session_id="full-session-abc",
        project_path=Path("/tmp/test_project"),
        start_time=datetime(2025, 2, 11, 9, 0, 0),
        end_time=datetime(2025, 2, 11, 12, 30, 0),
        duration_seconds=12600,
        git_commit_velocity=4.2,
        git_branch_count=8,
        git_merge_success_rate=0.90,
        conventional_commit_compliance=0.95,
        git_workflow_efficiency_score=88.0,
        tests_run=200,
        tests_passed=195,
        test_pass_rate=0.975,
        ai_fixes_applied=2,
        quality_gate_passes=7,
    )


# ============================================================================
# Basic Creation Tests
# ============================================================================


def test_session_metrics_creation(sample_session_metrics):
    """Test basic instantiation with required fields."""
    assert sample_session_metrics.session_id == "test-session-123"
    assert sample_session_metrics.project_path == Path("/tmp/test_project")
    assert sample_session_metrics.start_time == datetime(2025, 2, 11, 10, 0, 0)
    assert sample_session_metrics.end_time is None
    assert sample_session_metrics.duration_seconds is None


def test_git_metrics_fields():
    """Test that git-specific fields are settable."""
    metrics = SessionMetrics(
        session_id="git-test",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        git_commit_velocity=5.5,
        git_branch_count=10,
        git_merge_success_rate=0.75,
        conventional_commit_compliance=0.80,
        git_workflow_efficiency_score=65.0,
    )
    assert metrics.git_commit_velocity == 5.5
    assert metrics.git_branch_count == 10
    assert metrics.git_merge_success_rate == 0.75
    assert metrics.conventional_commit_compliance == 0.80
    assert metrics.git_workflow_efficiency_score == 65.0


def test_quality_metrics_fields():
    """Test that quality metrics fields are settable."""
    metrics = SessionMetrics(
        session_id="quality-test",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        tests_run=100,
        tests_passed=95,
        ai_fixes_applied=5,
        quality_gate_passes=3,
    )
    assert metrics.tests_run == 100
    assert metrics.tests_passed == 95
    assert metrics.ai_fixes_applied == 5
    assert metrics.quality_gate_passes == 3


# ============================================================================
# Duration Calculation Tests
# ============================================================================


def test_calculate_duration_with_both_times():
    """Test calculate_duration when both start and end times are present."""
    metrics = SessionMetrics(
        session_id="duration-test",
        project_path=Path("/tmp/test"),
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        end_time=datetime(2025, 2, 11, 11, 30, 0),
    )
    duration = metrics.calculate_duration()
    assert duration == 5400  # 1.5 hours in seconds
    assert metrics.duration_seconds == 5400


def test_calculate_duration_with_missing_end_time():
    """Test calculate_duration when end_time is None."""
    metrics = SessionMetrics(
        session_id="no-end-test",
        project_path=Path("/tmp/test"),
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        end_time=None,
    )
    duration = metrics.calculate_duration()
    assert duration is None
    assert metrics.duration_seconds is None


def test_auto_duration_calculation_in_post_init():
    """Test that duration is auto-calculated in __post_init__."""
    metrics = SessionMetrics(
        session_id="auto-duration-test",
        project_path=Path("/tmp/test"),
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        end_time=datetime(2025, 2, 11, 11, 0, 0),
    )
    assert metrics.duration_seconds == 3600


def test_explicit_duration_not_overridden():
    """Test that explicitly provided duration is not overridden."""
    metrics = SessionMetrics(
        session_id="explicit-duration-test",
        project_path=Path("/tmp/test"),
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        end_time=datetime(2025, 2, 11, 11, 0, 0),
        duration_seconds=7200,  # Explicit value
    )
    assert metrics.duration_seconds == 7200


# ============================================================================
# Serialization Tests
# ============================================================================


def test_to_dict_serialization_basic(metrics_with_git_data):
    """Test that to_dict converts basic fields correctly."""
    data = metrics_with_git_data.to_dict()
    assert data["session_id"] == "git-session-456"
    assert isinstance(data["project_path"], str)
    assert data["project_path"] == "/tmp/test_project"


def test_to_dict_serialization_dates(metrics_with_git_data):
    """Test that to_dict converts datetime to ISO format."""
    data = metrics_with_git_data.to_dict()
    assert isinstance(data["start_time"], str)
    assert data["start_time"] == "2025-02-11T10:00:00"
    assert isinstance(data["end_time"], str)
    assert data["end_time"] == "2025-02-11T11:30:00"


def test_to_dict_serialization_git_metrics(metrics_with_git_data):
    """Test that to_dict includes git metrics."""
    data = metrics_with_git_data.to_dict()
    assert data["git_commit_velocity"] == 3.5
    assert data["git_branch_count"] == 5
    assert data["git_merge_success_rate"] == 0.85
    assert data["conventional_commit_compliance"] == 0.92
    assert data["git_workflow_efficiency_score"] == 78.5


def test_from_dict_deserialization_basic():
    """Test from_dict creates instance from basic dict."""
    data = {
        "session_id": "dict-test-123",
        "project_path": "/tmp/from_dict_test",
        "start_time": "2025-02-11T10:00:00",
    }
    metrics = SessionMetrics.from_dict(data)
    assert metrics.session_id == "dict-test-123"
    assert isinstance(metrics.project_path, Path)
    assert metrics.project_path == Path("/tmp/from_dict_test")
    assert isinstance(metrics.start_time, datetime)


def test_from_dict_deserialization_with_all_fields():
    """Test from_dict creates instance with all fields."""
    data = {
        "session_id": "full-dict-test",
        "project_path": "/tmp/full_test",
        "start_time": "2025-02-11T09:00:00",
        "end_time": "2025-02-11T12:00:00",
        "duration_seconds": 10800,
        "git_commit_velocity": 6.0,
        "git_branch_count": 12,
        "git_merge_success_rate": 0.95,
        "conventional_commit_compliance": 0.88,
        "git_workflow_efficiency_score": 82.0,
        "tests_run": 180,
        "tests_passed": 175,
        "test_pass_rate": 0.972,
        "ai_fixes_applied": 4,
        "quality_gate_passes": 6,
    }
    metrics = SessionMetrics.from_dict(data)
    assert metrics.session_id == "full-dict-test"
    assert metrics.git_commit_velocity == 6.0
    assert metrics.git_branch_count == 12
    assert metrics.git_merge_success_rate == 0.95
    assert metrics.tests_run == 180
    assert metrics.tests_passed == 175


def test_from_dict_round_trip(metrics_with_all_data):
    """Test that to_dict -> from_dict round trip preserves data."""
    original = metrics_with_all_data
    data_dict = original.to_dict()
    restored = SessionMetrics.from_dict(data_dict)

    assert restored.session_id == original.session_id
    assert restored.project_path == original.project_path
    assert restored.start_time == original.start_time
    assert restored.end_time == original.end_time
    assert restored.git_commit_velocity == original.git_commit_velocity
    assert restored.git_branch_count == original.git_branch_count
    assert restored.tests_run == original.tests_run
    assert restored.tests_passed == original.tests_passed


def test_from_dict_missing_required_fields():
    """Test that from_dict raises ValueError for missing required fields."""
    data = {
        "session_id": "missing-fields",
        # Missing project_path and start_time
    }
    with pytest.raises(ValueError, match="Missing required fields"):
        SessionMetrics.from_dict(data)


def test_from_dict_with_path_object():
    """Test that from_dict handles Path objects in project_path."""
    data = {
        "session_id": "path-test",
        "project_path": Path("/tmp/test_path"),
        "start_time": "2025-02-11T10:00:00",
    }
    metrics = SessionMetrics.from_dict(data)
    assert isinstance(metrics.project_path, Path)


# ============================================================================
# Validation Tests
# ============================================================================


def test_percentage_validation_valid_values():
    """Test that valid percentage values are accepted."""
    metrics = SessionMetrics(
        session_id="valid-percent",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        git_merge_success_rate=0.0,
        conventional_commit_compliance=0.5,
        test_pass_rate=1.0,
    )
    assert metrics.git_merge_success_rate == 0.0
    assert metrics.conventional_commit_compliance == 0.5
    assert metrics.test_pass_rate == 1.0


def test_percentage_validation_invalid_high():
    """Test that percentages > 1.0 are rejected."""
    with pytest.raises(ValueError, match="git_merge_success_rate must be between 0.0 and 1.0"):
        SessionMetrics(
            session_id="invalid-high",
            project_path=Path("/tmp/test"),
            start_time=datetime.now(),
            git_merge_success_rate=1.5,
        )


def test_percentage_validation_invalid_low():
    """Test that percentages < 0.0 are rejected."""
    with pytest.raises(ValueError, match="test_pass_rate must be between 0.0 and 1.0"):
        SessionMetrics(
            session_id="invalid-low",
            project_path=Path("/tmp/test"),
            start_time=datetime.now(),
            test_pass_rate=-0.1,
        )


def test_percentage_validation_none_allowed():
    """Test that None is allowed for percentage fields."""
    metrics = SessionMetrics(
        session_id="none-percent",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        git_merge_success_rate=None,
        conventional_commit_compliance=None,
        test_pass_rate=None,
    )
    assert metrics.git_merge_success_rate is None
    assert metrics.conventional_commit_compliance is None
    assert metrics.test_pass_rate is None


def test_score_validation_valid_values():
    """Test that valid score values are accepted."""
    metrics = SessionMetrics(
        session_id="valid-score",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        git_workflow_efficiency_score=0,
    )
    assert metrics.git_workflow_efficiency_score == 0

    metrics2 = SessionMetrics(
        session_id="valid-score-2",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        git_workflow_efficiency_score=100,
    )
    assert metrics2.git_workflow_efficiency_score == 100


def test_score_validation_invalid_high():
    """Test that scores > 100 are rejected."""
    with pytest.raises(ValueError, match="git_workflow_efficiency_score must be between 0 and 100"):
        SessionMetrics(
            session_id="invalid-score-high",
            project_path=Path("/tmp/test"),
            start_time=datetime.now(),
            git_workflow_efficiency_score=150,
        )


def test_score_validation_invalid_low():
    """Test that scores < 0 are rejected."""
    with pytest.raises(ValueError, match="git_workflow_efficiency_score must be between 0 and 100"):
        SessionMetrics(
            session_id="invalid-score-low",
            project_path=Path("/tmp/test"),
            start_time=datetime.now(),
            git_workflow_efficiency_score=-10,
        )


def test_score_validation_none_allowed():
    """Test that None is allowed for score fields."""
    metrics = SessionMetrics(
        session_id="none-score",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        git_workflow_efficiency_score=None,
    )
    assert metrics.git_workflow_efficiency_score is None


def test_negative_validation_counts():
    """Test that negative values for count fields are rejected."""
    with pytest.raises(ValueError, match="duration_seconds must be non-negative"):
        SessionMetrics(
            session_id="negative-duration",
            project_path=Path("/tmp/test"),
            start_time=datetime.now(),
            duration_seconds=-100,
        )


def test_negative_validation_branch_count():
    """Test that negative branch count is rejected."""
    with pytest.raises(ValueError, match="git_branch_count must be non-negative"):
        SessionMetrics(
            session_id="negative-branches",
            project_path=Path("/tmp/test"),
            start_time=datetime.now(),
            git_branch_count=-5,
        )


def test_negative_validation_tests():
    """Test that negative test values are rejected."""
    with pytest.raises(ValueError, match="tests_run must be non-negative"):
        SessionMetrics(
            session_id="negative-tests",
            project_path=Path("/tmp/test"),
            start_time=datetime.now(),
            tests_run=-10,
        )


def test_negative_validation_velocity():
    """Test that negative velocity is rejected."""
    with pytest.raises(ValueError, match="git_commit_velocity must be non-negative"):
        SessionMetrics(
            session_id="negative-velocity",
            project_path=Path("/tmp/test"),
            start_time=datetime.now(),
            git_commit_velocity=-1.5,
        )


# ============================================================================
# Auto-Calculation Tests
# ============================================================================


def test_auto_calculations_test_pass_rate():
    """Test that test_pass_rate is auto-calculated from tests_run/tests_passed."""
    metrics = SessionMetrics(
        session_id="auto-rate",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        tests_run=100,
        tests_passed=85,
    )
    assert metrics.test_pass_rate == 0.85


def test_auto_calculations_test_pass_rate_zero_division():
    """Test that test_pass_rate is not calculated when tests_run is 0 (condition fails)."""
    metrics = SessionMetrics(
        session_id="zero-division",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        tests_run=0,
        tests_passed=0,
    )
    # When tests_run=0, the condition 'if self.tests_run' evaluates to False
    # so the auto-calculation is skipped
    assert metrics.test_pass_rate is None


def test_auto_calculations_test_pass_rate_not_overridden():
    """Test that explicit test_pass_rate is not overridden."""
    metrics = SessionMetrics(
        session_id="explicit-rate",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        tests_run=100,
        tests_passed=85,
        test_pass_rate=0.90,  # Explicit value
    )
    assert metrics.test_pass_rate == 0.90


def test_auto_calculations_missing_tests_passed():
    """Test that test_pass_rate is not calculated when tests_passed is None."""
    metrics = SessionMetrics(
        session_id="missing-passed",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        tests_run=100,
        tests_passed=None,
    )
    assert metrics.test_pass_rate is None


# ============================================================================
# Summary Tests
# ============================================================================


def test_get_summary_basic(metrics_with_quality_data):
    """Test get_summary returns basic session info."""
    summary = metrics_with_quality_data.get_summary()
    assert summary["session_id"] == "quality-session-789"
    assert summary["duration_seconds"] == 3600
    assert summary["tests_passed"] == 142
    assert summary["tests_run"] == 150
    assert summary["test_pass_rate"] == pytest.approx(0.9467, rel=1e-3)


def test_get_summary_with_git_metrics(metrics_with_git_data):
    """Test get_summary includes git_metrics section when available."""
    summary = metrics_with_git_data.get_summary()
    assert "git_metrics" in summary
    git_metrics = summary["git_metrics"]
    assert git_metrics["commit_velocity"] == 3.5
    assert git_metrics["branch_count"] == 5
    assert git_metrics["merge_success_rate"] == 0.85
    assert git_metrics["conventional_compliance"] == 0.92
    assert git_metrics["efficiency_score"] == 78.5


def test_get_summary_with_quality_metrics(metrics_with_quality_data):
    """Test get_summary includes quality_metrics section when available."""
    summary = metrics_with_quality_data.get_summary()
    assert "quality_metrics" in summary
    quality_metrics = summary["quality_metrics"]
    assert quality_metrics["ai_fixes_applied"] == 3
    assert quality_metrics["quality_gate_passes"] == 5


def test_get_summary_no_git_section(sample_session_metrics):
    """Test get_summary excludes git_metrics when no git data."""
    summary = sample_session_metrics.get_summary()
    assert "git_metrics" not in summary


def test_get_summary_no_quality_section(sample_session_metrics):
    """Test get_summary excludes quality_metrics when no quality data."""
    summary = sample_session_metrics.get_summary()
    assert "quality_metrics" not in summary


def test_get_summary_comprehensive(metrics_with_all_data):
    """Test get_summary with all sections populated."""
    summary = metrics_with_all_data.get_summary()
    assert "session_id" in summary
    assert "duration_seconds" in summary
    assert "tests_passed" in summary
    assert "tests_run" in summary
    assert "test_pass_rate" in summary
    assert "git_metrics" in summary
    assert "quality_metrics" in summary
