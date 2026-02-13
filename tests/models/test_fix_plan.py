"""
Tests for FixPlan and ChangeSpec models.

Test fix planning data structures.
"""
import pytest

from crackerjack.models.fix_plan import ChangeSpec, FixPlan


class TestChangeSpec:
    """Test suite for ChangeSpec."""

    def test_valid_change_spec(self) -> None:
        """Test creating a valid ChangeSpec."""
        change = ChangeSpec(
            line_range=(1, 5),
            old_code="old line\n" * 5,
            new_code="new line\n" * 5,
            reason="Refactoring for clarity"
        )

        assert change.line_range == (1, 5)
        assert change.old_code == "old line\n" * 5
        assert change.new_code == "new line\n" * 5
        assert change.reason == "Refactoring for clarity"

    def test_invalid_line_range_not_tuple(self) -> None:
        """Test that non-tuple line_range raises error."""
        with pytest.raises(ValueError, match="line_range must be tuple"):
            ChangeSpec(
                line_range=[1, 5],  # type: ignore
                old_code="old",
                new_code="new",
                reason="test"
            )

    def test_invalid_line_range_wrong_length(self) -> None:
        """Test that wrong length line_range raises error."""
        with pytest.raises(ValueError, match="line_range must be tuple of 2"):
            ChangeSpec(
                line_range=(1, 5, 10),
                old_code="old",
                new_code="new",
                reason="test"
            )

    def test_invalid_empty_old_code(self) -> None:
        """Test that empty old_code raises error."""
        with pytest.raises(ValueError, match="old_code cannot be empty"):
            ChangeSpec(
                line_range=(1, 1),
                old_code="   ",  # Only whitespace
                new_code="new",
                reason="test"
            )

    def test_invalid_line_start_too_low(self) -> None:
        """Test that line start < 1 raises error."""
        with pytest.raises(ValueError, match="line_range start must be >= 1"):
            ChangeSpec(
                line_range=(0, 5),
                old_code="old",
                new_code="new",
                reason="test"
            )

    def test_invalid_line_end_before_start(self) -> None:
        """Test that line end < start raises error."""
        with pytest.raises(ValueError, match="line_range end must be >= start"):
            ChangeSpec(
                line_range=(10, 5),
                old_code="old",
                new_code="new",
                reason="test"
            )


class TestFixPlan:
    """Test suite for FixPlan."""

    def test_valid_fix_plan(self) -> None:
        """Test creating a valid FixPlan."""
        change = ChangeSpec(
            line_range=(1, 5),
            old_code="old",
            new_code="new",
            reason="test"
        )

        plan = FixPlan(
            file_path="/path/to/file.py",
            issue_type="COMPLEXITY",
            changes=[change],
            rationale="Reduce complexity",
            risk_level="low",
            validated_by="PlanningAgent"
        )

        assert plan.file_path == "/path/to/file.py"
        assert plan.issue_type == "COMPLEXITY"
        assert len(plan.changes) == 1
        assert plan.risk_level == "low"

    def test_invalid_empty_changes(self) -> None:
        """Test that empty changes list raises error."""
        with pytest.raises(ValueError, match="must have at least one"):
            FixPlan(
                file_path="/path/to/file.py",
                issue_type="COMPLEXITY",
                changes=[],
                rationale="test",
                risk_level="low",
                validated_by="test"
            )

    def test_invalid_risk_level(self) -> None:
        """Test that invalid risk_level raises error."""
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="old",
            new_code="new",
            reason="test"
        )

        with pytest.raises(ValueError, match="risk_level must be low/medium/high"):
            FixPlan(
                file_path="/path/to/file.py",
                issue_type="COMPLEXITY",
                changes=[change],
                rationale="test",
                risk_level="critical",  # Invalid
                validated_by="test"
            )

    def test_estimate_diff_size(self) -> None:
        """Test diff size estimation."""
        changes = [
            ChangeSpec(line_range=(1, 10), old_code="old", new_code="new", reason="test"),
            ChangeSpec(line_range=(20, 30), old_code="old", new_code="new", reason="test"),
        ]

        plan = FixPlan(
            file_path="/path/to/file.py",
            issue_type="TEST",
            changes=changes,
            rationale="test",
            risk_level="low",
            validated_by="test"
        )

        # First change: 10 - 1 + 1 = 10 lines
        # Second change: 30 - 20 + 1 = 11 lines
        # Total: 21 lines
        assert plan.estimate_diff_size() == 21

    def test_is_high_risk(self) -> None:
        """Test high risk detection."""
        high_risk_plan = FixPlan(
            file_path="/path/to/file.py",
            issue_type="TEST",
            changes=[ChangeSpec(line_range=(1, 1), old_code="old", new_code="new", reason="test")],
            rationale="test",
            risk_level="high",
            validated_by="test"
        )

        low_risk_plan = FixPlan(
            file_path="/path/to/file.py",
            issue_type="TEST",
            changes=[ChangeSpec(line_range=(1, 1), old_code="old", new_code="new", reason="test")],
            rationale="test",
            risk_level="low",
            validated_by="test"
        )

        assert high_risk_plan.is_high_risk() is True
        assert low_risk_plan.is_high_risk() is False

    def test_is_acceptable_risk(self) -> None:
        """Test acceptable risk levels."""
        change = ChangeSpec(line_range=(1, 1), old_code="old", new_code="new", reason="test")

        low_plan = FixPlan(
            file_path="/path/to/file.py", issue_type="TEST", changes=[change],
            rationale="test", risk_level="low", validated_by="test"
        )
        medium_plan = FixPlan(
            file_path="/path/to/file.py", issue_type="TEST", changes=[change],
            rationale="test", risk_level="medium", validated_by="test"
        )
        high_plan = FixPlan(
            file_path="/path/to/file.py", issue_type="TEST", changes=[change],
            rationale="test", risk_level="high", validated_by="test"
        )

        # Low risk is always acceptable
        assert low_plan.is_acceptable_risk("low") is True
        assert low_plan.is_acceptable_risk("medium") is True
        assert low_plan.is_acceptable_risk("high") is True

        # Medium risk is acceptable at medium or high
        assert medium_plan.is_acceptable_risk("low") is False
        assert medium_plan.is_acceptable_risk("medium") is True
        assert medium_plan.is_acceptable_risk("high") is True

        # High risk only acceptable at high
        assert high_plan.is_acceptable_risk("low") is False
        assert high_plan.is_acceptable_risk("medium") is False
        assert high_plan.is_acceptable_risk("high") is True
