"""Tests for results module (dataclass versions of ExecutionResult models)."""

from __future__ import annotations

import pytest

from crackerjack.models.results import ExecutionResult, ParallelExecutionResult


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_minimal_execution_result(self) -> None:
        """Verify minimal ExecutionResult creation."""
        result = ExecutionResult(
            operation_id="op-1",
            success=True,
            duration_seconds=5.5,
        )
        assert result.operation_id == "op-1"
        assert result.success is True
        assert result.duration_seconds == 5.5
        assert result.output == ""
        assert result.error == ""
        assert result.exit_code == 0
        assert result.metadata == {}

    def test_execution_result_full(self) -> None:
        """Verify ExecutionResult with all fields."""
        result = ExecutionResult(
            operation_id="op-2",
            success=False,
            duration_seconds=2.3,
            output="Some output",
            error="Error occurred",
            exit_code=1,
            metadata={"stage": "test", "worker": "w1"},
        )
        assert result.operation_id == "op-2"
        assert result.success is False
        assert result.duration_seconds == 2.3
        assert result.output == "Some output"
        assert result.error == "Error occurred"
        assert result.exit_code == 1
        assert result.metadata == {"stage": "test", "worker": "w1"}

    def test_execution_result_metadata_default(self) -> None:
        """Verify metadata defaults to empty dict."""
        result = ExecutionResult(
            operation_id="op-3",
            success=True,
            duration_seconds=1.0,
        )
        assert isinstance(result.metadata, dict)
        assert len(result.metadata) == 0

    def test_execution_result_success_flag(self) -> None:
        """Verify success flag captures operation result."""
        success_result = ExecutionResult(
            operation_id="op-4",
            success=True,
            duration_seconds=0.5,
        )
        assert success_result.success is True

        failure_result = ExecutionResult(
            operation_id="op-5",
            success=False,
            duration_seconds=0.5,
            error="Failed",
            exit_code=1,
        )
        assert failure_result.success is False
        assert failure_result.exit_code == 1


class TestParallelExecutionResult:
    """Tests for ParallelExecutionResult dataclass."""

    def test_minimal_parallel_execution_result(self) -> None:
        """Verify minimal ParallelExecutionResult creation."""
        result = ParallelExecutionResult(
            group_name="group-1",
            total_operations=10,
            successful_operations=8,
            failed_operations=2,
            total_duration_seconds=15.5,
            results=[],
        )
        assert result.group_name == "group-1"
        assert result.total_operations == 10
        assert result.successful_operations == 8
        assert result.failed_operations == 2
        assert result.total_duration_seconds == 15.5
        assert result.results == []

    def test_parallel_execution_result_with_results(self) -> None:
        """Verify ParallelExecutionResult with ExecutionResult list."""
        exec_result = ExecutionResult(
            operation_id="op-1",
            success=True,
            duration_seconds=1.0,
        )
        result = ParallelExecutionResult(
            group_name="group-2",
            total_operations=1,
            successful_operations=1,
            failed_operations=0,
            total_duration_seconds=1.0,
            results=[exec_result],
        )
        assert len(result.results) == 1
        assert result.results[0].operation_id == "op-1"
        assert result.results[0].success is True

    def test_parallel_execution_result_multiple_results(self) -> None:
        """Verify ParallelExecutionResult with multiple ExecutionResults."""
        results_list = [
            ExecutionResult(
                operation_id=f"op-{i}",
                success=(i % 2 == 0),
                duration_seconds=float(i),
            )
            for i in range(1, 6)
        ]
        result = ParallelExecutionResult(
            group_name="group-3",
            total_operations=5,
            successful_operations=3,
            failed_operations=2,
            total_duration_seconds=10.0,
            results=results_list,
        )
        assert len(result.results) == 5
        assert result.results[0].operation_id == "op-1"
        assert result.results[4].operation_id == "op-5"

    def test_parallel_execution_result_success_rate_full(self) -> None:
        """Verify success_rate property with 100% success."""
        result = ParallelExecutionResult(
            group_name="group-4",
            total_operations=5,
            successful_operations=5,
            failed_operations=0,
            total_duration_seconds=10.0,
            results=[],
        )
        assert result.success_rate == 1.0

    def test_parallel_execution_result_success_rate_partial(self) -> None:
        """Verify success_rate property with partial success."""
        result = ParallelExecutionResult(
            group_name="group-5",
            total_operations=10,
            successful_operations=7,
            failed_operations=3,
            total_duration_seconds=20.0,
            results=[],
        )
        assert result.success_rate == 0.7

    def test_parallel_execution_result_success_rate_zero(self) -> None:
        """Verify success_rate property with zero total operations."""
        result = ParallelExecutionResult(
            group_name="group-6",
            total_operations=0,
            successful_operations=0,
            failed_operations=0,
            total_duration_seconds=0.0,
            results=[],
        )
        assert result.success_rate == 0.0

    def test_parallel_execution_result_success_rate_none(self) -> None:
        """Verify success_rate with no failures."""
        result = ParallelExecutionResult(
            group_name="group-7",
            total_operations=8,
            successful_operations=8,
            failed_operations=0,
            total_duration_seconds=8.0,
            results=[],
        )
        assert result.success_rate == 1.0

    def test_parallel_execution_result_overall_success_true(self) -> None:
        """Verify overall_success property when no failures."""
        result = ParallelExecutionResult(
            group_name="group-8",
            total_operations=5,
            successful_operations=5,
            failed_operations=0,
            total_duration_seconds=10.0,
            results=[],
        )
        assert result.overall_success is True

    def test_parallel_execution_result_overall_success_false(self) -> None:
        """Verify overall_success property when failures exist."""
        result = ParallelExecutionResult(
            group_name="group-9",
            total_operations=5,
            successful_operations=4,
            failed_operations=1,
            total_duration_seconds=10.0,
            results=[],
        )
        assert result.overall_success is False

    def test_parallel_execution_result_overall_success_any_failure(self) -> None:
        """Verify overall_success checks for any failures."""
        # Even one failure makes overall_success False
        result = ParallelExecutionResult(
            group_name="group-10",
            total_operations=100,
            successful_operations=99,
            failed_operations=1,
            total_duration_seconds=100.0,
            results=[],
        )
        assert result.overall_success is False
