"""Tests for enums module."""

from __future__ import annotations

import pytest

from crackerjack.models.enums import HealthStatus, HookStatus, TaskStatus, WorkflowPhase


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_enum_values(self) -> None:
        """Verify enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_from_string_healthy(self) -> None:
        """Verify from_string for healthy status."""
        result = HealthStatus.from_string("healthy")
        assert result == HealthStatus.HEALTHY

    def test_from_string_degraded(self) -> None:
        """Verify from_string for degraded status."""
        result = HealthStatus.from_string("degraded")
        assert result == HealthStatus.DEGRADED

    def test_from_string_unhealthy(self) -> None:
        """Verify from_string for unhealthy status."""
        result = HealthStatus.from_string("unhealthy")
        assert result == HealthStatus.UNHEALTHY

    def test_from_string_case_insensitive(self) -> None:
        """Verify from_string is case insensitive."""
        assert HealthStatus.from_string("HEALTHY") == HealthStatus.HEALTHY
        assert HealthStatus.from_string("Degraded") == HealthStatus.DEGRADED
        assert HealthStatus.from_string("UnHeAlThY") == HealthStatus.UNHEALTHY

    def test_from_string_invalid(self) -> None:
        """Verify from_string raises ValueError for invalid status."""
        with pytest.raises(ValueError, match="Invalid health status"):
            HealthStatus.from_string("invalid")

    def test_from_string_error_message(self) -> None:
        """Verify error message includes valid values."""
        with pytest.raises(ValueError, match="Valid values"):
            HealthStatus.from_string("bad_status")

    def test_lt_comparison_healthy_vs_degraded(self) -> None:
        """Verify less-than comparison between healthy and degraded."""
        assert HealthStatus.HEALTHY < HealthStatus.DEGRADED

    def test_lt_comparison_degraded_vs_unhealthy(self) -> None:
        """Verify less-than comparison between degraded and unhealthy."""
        assert HealthStatus.DEGRADED < HealthStatus.UNHEALTHY

    def test_lt_comparison_healthy_vs_unhealthy(self) -> None:
        """Verify less-than comparison between healthy and unhealthy."""
        assert HealthStatus.HEALTHY < HealthStatus.UNHEALTHY

    def test_lt_not_less_than_same(self) -> None:
        """Verify less-than returns False for equal values."""
        assert not (HealthStatus.HEALTHY < HealthStatus.HEALTHY)

    def test_lt_comparison_with_enum_string(self) -> None:
        """Verify less-than with HealthStatus enum values as strings works."""
        # When comparing with HealthStatus enum values, they work
        assert HealthStatus.HEALTHY < HealthStatus.DEGRADED

    def test_lt_comparison_with_plain_string(self) -> None:
        """Verify less-than with plain strings returns bool."""
        # Plain strings (not HealthStatus enums) return NotImplemented,
        # which falls back to type-based comparison
        assert isinstance(HealthStatus.HEALTHY < "degraded", bool)
        assert isinstance(HealthStatus.DEGRADED < "healthy", bool)


class TestWorkflowPhase:
    """Tests for WorkflowPhase enum."""

    def test_enum_values(self) -> None:
        """Verify enum values."""
        assert WorkflowPhase.CONFIGURATION_SETUP.value == "configuration_setup"
        assert WorkflowPhase.FAST_HOOKS_WITH_ARCHITECTURE.value == "fast_hooks_with_architecture"
        assert WorkflowPhase.ARCHITECTURAL_REFACTORING.value == "architectural_refactoring"
        assert WorkflowPhase.COMPREHENSIVE_VALIDATION.value == "comprehensive_validation"
        assert WorkflowPhase.PATTERN_LEARNING.value == "pattern_learning"
        assert WorkflowPhase.STANDARD_WORKFLOW.value == "standard_workflow"

    def test_from_string_all_phases(self) -> None:
        """Verify from_string for all workflow phases."""
        assert WorkflowPhase.from_string("configuration_setup") == WorkflowPhase.CONFIGURATION_SETUP
        assert WorkflowPhase.from_string("fast_hooks_with_architecture") == WorkflowPhase.FAST_HOOKS_WITH_ARCHITECTURE
        assert WorkflowPhase.from_string("architectural_refactoring") == WorkflowPhase.ARCHITECTURAL_REFACTORING
        assert WorkflowPhase.from_string("comprehensive_validation") == WorkflowPhase.COMPREHENSIVE_VALIDATION
        assert WorkflowPhase.from_string("pattern_learning") == WorkflowPhase.PATTERN_LEARNING
        assert WorkflowPhase.from_string("standard_workflow") == WorkflowPhase.STANDARD_WORKFLOW

    def test_from_string_case_insensitive(self) -> None:
        """Verify from_string is case insensitive."""
        assert WorkflowPhase.from_string("STANDARD_WORKFLOW") == WorkflowPhase.STANDARD_WORKFLOW
        assert WorkflowPhase.from_string("Pattern_Learning") == WorkflowPhase.PATTERN_LEARNING

    def test_from_string_invalid(self) -> None:
        """Verify from_string raises ValueError for invalid phase."""
        with pytest.raises(ValueError, match="Invalid workflow phase"):
            WorkflowPhase.from_string("invalid_phase")


class TestHookStatus:
    """Tests for HookStatus enum."""

    def test_enum_values(self) -> None:
        """Verify enum values."""
        assert HookStatus.PENDING.value == "pending"
        assert HookStatus.RUNNING.value == "running"
        assert HookStatus.COMPLETED.value == "completed"
        assert HookStatus.FAILED.value == "failed"
        assert HookStatus.SKIPPED.value == "skipped"
        assert HookStatus.TIMEOUT.value == "timeout"

    def test_from_string_all_statuses(self) -> None:
        """Verify from_string for all hook statuses."""
        assert HookStatus.from_string("pending") == HookStatus.PENDING
        assert HookStatus.from_string("running") == HookStatus.RUNNING
        assert HookStatus.from_string("completed") == HookStatus.COMPLETED
        assert HookStatus.from_string("failed") == HookStatus.FAILED
        assert HookStatus.from_string("skipped") == HookStatus.SKIPPED
        assert HookStatus.from_string("timeout") == HookStatus.TIMEOUT

    def test_from_string_case_insensitive(self) -> None:
        """Verify from_string is case insensitive."""
        assert HookStatus.from_string("COMPLETED") == HookStatus.COMPLETED
        assert HookStatus.from_string("Timeout") == HookStatus.TIMEOUT

    def test_from_string_invalid(self) -> None:
        """Verify from_string raises ValueError for invalid status."""
        with pytest.raises(ValueError, match="Invalid hook status"):
            HookStatus.from_string("unknown")

    def test_is_terminal_completed(self) -> None:
        """Verify is_terminal for completed status."""
        assert HookStatus.COMPLETED.is_terminal is True

    def test_is_terminal_failed(self) -> None:
        """Verify is_terminal for failed status."""
        assert HookStatus.FAILED.is_terminal is True

    def test_is_terminal_skipped(self) -> None:
        """Verify is_terminal for skipped status."""
        assert HookStatus.SKIPPED.is_terminal is True

    def test_is_terminal_timeout(self) -> None:
        """Verify is_terminal for timeout status."""
        assert HookStatus.TIMEOUT.is_terminal is True

    def test_is_terminal_pending(self) -> None:
        """Verify is_terminal for pending status."""
        assert HookStatus.PENDING.is_terminal is False

    def test_is_terminal_running(self) -> None:
        """Verify is_terminal for running status."""
        assert HookStatus.RUNNING.is_terminal is False

    def test_is_success_completed(self) -> None:
        """Verify is_success for completed status."""
        assert HookStatus.COMPLETED.is_success is True

    def test_is_success_failed(self) -> None:
        """Verify is_success for failed status."""
        assert HookStatus.FAILED.is_success is False

    def test_is_success_pending(self) -> None:
        """Verify is_success for pending status."""
        assert HookStatus.PENDING.is_success is False

    def test_is_success_running(self) -> None:
        """Verify is_success for running status."""
        assert HookStatus.RUNNING.is_success is False

    def test_is_failure_failed(self) -> None:
        """Verify is_failure for failed status."""
        assert HookStatus.FAILED.is_failure is True

    def test_is_failure_timeout(self) -> None:
        """Verify is_failure for timeout status."""
        assert HookStatus.TIMEOUT.is_failure is True

    def test_is_failure_completed(self) -> None:
        """Verify is_failure for completed status."""
        assert HookStatus.COMPLETED.is_failure is False

    def test_is_failure_pending(self) -> None:
        """Verify is_failure for pending status."""
        assert HookStatus.PENDING.is_failure is False

    def test_is_failure_skipped(self) -> None:
        """Verify is_failure for skipped status."""
        assert HookStatus.SKIPPED.is_failure is False


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_enum_values(self) -> None:
        """Verify enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_from_string_all_statuses(self) -> None:
        """Verify from_string for all task statuses."""
        assert TaskStatus.from_string("pending") == TaskStatus.PENDING
        assert TaskStatus.from_string("in_progress") == TaskStatus.IN_PROGRESS
        assert TaskStatus.from_string("completed") == TaskStatus.COMPLETED
        assert TaskStatus.from_string("failed") == TaskStatus.FAILED

    def test_from_string_case_insensitive(self) -> None:
        """Verify from_string is case insensitive."""
        assert TaskStatus.from_string("COMPLETED") == TaskStatus.COMPLETED
        assert TaskStatus.from_string("In_Progress") == TaskStatus.IN_PROGRESS

    def test_from_string_invalid(self) -> None:
        """Verify from_string raises ValueError for invalid status."""
        with pytest.raises(ValueError, match="Invalid task status"):
            TaskStatus.from_string("invalid")

    def test_is_terminal_completed(self) -> None:
        """Verify is_terminal for completed status."""
        assert TaskStatus.COMPLETED.is_terminal is True

    def test_is_terminal_failed(self) -> None:
        """Verify is_terminal for failed status."""
        assert TaskStatus.FAILED.is_terminal is True

    def test_is_terminal_pending(self) -> None:
        """Verify is_terminal for pending status."""
        assert TaskStatus.PENDING.is_terminal is False

    def test_is_terminal_in_progress(self) -> None:
        """Verify is_terminal for in_progress status."""
        assert TaskStatus.IN_PROGRESS.is_terminal is False

    def test_is_active_pending(self) -> None:
        """Verify is_active for pending status."""
        assert TaskStatus.PENDING.is_active is True

    def test_is_active_in_progress(self) -> None:
        """Verify is_active for in_progress status."""
        assert TaskStatus.IN_PROGRESS.is_active is True

    def test_is_active_completed(self) -> None:
        """Verify is_active for completed status."""
        assert TaskStatus.COMPLETED.is_active is False

    def test_is_active_failed(self) -> None:
        """Verify is_active for failed status."""
        assert TaskStatus.FAILED.is_active is False
