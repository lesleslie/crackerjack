"""Comprehensive tests for BatchProcessor.

Tests all public methods and edge cases including:
- Batch processing with parallel/sequential execution
- Retry logic
- Agent coordination
- Result aggregation
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority, SubAgent
from crackerjack.services.batch_processor import (
    BatchIssueResult,
    BatchProcessingResult,
    BatchProcessor,
    BatchStatus,
    get_batch_processor,
)


class TestBatchStatus:
    """Test BatchStatus enum."""

    def test_batch_status_values(self) -> None:
        """Test all batch status values exist."""
        assert BatchStatus.PENDING == "pending"
        assert BatchStatus.IN_PROGRESS == "in_progress"
        assert BatchStatus.COMPLETED == "completed"
        assert BatchStatus.FAILED == "failed"
        assert BatchStatus.PARTIAL == "partial"


class TestBatchIssueResult:
    """Test BatchIssueResult dataclass."""

    def test_create_batch_issue_result(self) -> None:
        """Test creating a batch issue result."""
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test issue", file_path="/test.py", line_number=1)
        result = BatchIssueResult(issue=issue, success=True)

        assert result.issue == issue
        assert result.success is True
        assert result.confidence == 0.0
        assert result.attempted is False

    def test_batch_issue_result_defaults(self) -> None:
        """Test default values for batch issue result."""
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test", file_path="/test.py", line_number=1)
        result = BatchIssueResult(issue=issue, success=False)

        assert result.error is None
        assert result.files_modified == []
        assert result.retry_count == 0
        assert result.agent_used is None


class TestBatchProcessingResult:
    """Test BatchProcessingResult dataclass."""

    def test_create_batch_processing_result(self) -> None:
        """Test creating a batch processing result."""
        result = BatchProcessingResult(
            batch_id="test_batch",
            status=BatchStatus.PENDING,
            total_issues=5,
        )

        assert result.batch_id == "test_batch"
        assert result.status == BatchStatus.PENDING
        assert result.total_issues == 5

    def test_completion_percentage_zero_issues(self) -> None:
        """Test completion percentage with zero issues."""
        result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.COMPLETED,
            total_issues=0,
        )

        assert result.completion_percentage == 100.0

    def test_completion_percentage_calculation(self) -> None:
        """Test completion percentage calculation."""
        result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.IN_PROGRESS,
            total_issues=10,
            successful=3,
            failed=2,
            skipped=1,
        )

        assert result.completion_percentage == 60.0


class TestBatchProcessorInit:
    """Test BatchProcessor initialization."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()

        processor = BatchProcessor(context, console)

        assert processor.context is context
        assert processor.console is console
        assert processor.max_parallel == 3

    def test_init_custom_max_parallel(self) -> None:
        """Test initialization with custom max_parallel."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()

        processor = BatchProcessor(context, console, max_parallel=5)

        assert processor.max_parallel == 5


class TestGetAgent:
    """Test _get_agent method."""

    def test_get_agent_caches(self) -> None:
        """Test _get_agent caches created agents."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console)

        with patch.dict("crackerjack.services.batch_processor._AGENT_REGISTRY"):
            agent1 = processor._get_agent("FormattingAgent")
            agent2 = processor._get_agent("FormattingAgent")

            assert agent1 is agent2

    def test_get_agent_unknown_raises(self) -> None:
        """Test _get_agent raises for unknown agent."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console)

        with pytest.raises(ValueError, match="Unknown agent"):
            processor._get_agent("NonExistentAgent")


class TestGenerateBatchId:
    """Test _generate_batch_id method."""

    def test_generate_batch_id_custom(self) -> None:
        """Test custom batch ID is returned."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        result = processor._generate_batch_id("my_batch")

        assert result == "my_batch"

    def test_generate_batch_id_auto_generated(self) -> None:
        """Test auto-generated batch ID format."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        result = processor._generate_batch_id(None)

        assert result.startswith("batch_")
        assert "_" in result


class TestInitializeBatchResult:
    """Test _initialize_batch_result method."""

    def test_initialize_batch_result(self) -> None:
        """Test batch result initialization."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        result = processor._initialize_batch_result("test_batch", 10)

        assert result.batch_id == "test_batch"
        assert result.status == BatchStatus.IN_PROGRESS
        assert result.total_issues == 10
        assert result.start_time is not None


class TestProcessBatch:
    """Test process_batch method."""

    @pytest.mark.asyncio
    async def test_process_batch_empty_issues(self) -> None:
        """Test processing empty issue list."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console)

        result = await processor.process_batch([])

        assert result.status == BatchStatus.COMPLETED
        assert result.total_issues == 0
        assert result.successful == 0

    @pytest.mark.asyncio
    async def test_process_batch_parallel(self) -> None:
        """Test parallel batch processing."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console, max_parallel=3)

        issues = [
            Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message=f"Issue {i}", file_path="/test.py", line_number=i)
            for i in range(3)
        ]

        # Mock the issue processing
        async def mock_process(issue, retries):
            return BatchIssueResult(issue=issue, success=True, attempted=True)

        processor._process_single_issue = mock_process

        result = await processor.process_batch(issues, parallel=True)

        assert result.total_issues == 3

    @pytest.mark.asyncio
    async def test_process_batch_sequential(self) -> None:
        """Test sequential batch processing."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console, max_parallel=1)

        issues = [
            Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Issue 1", file_path="/test1.py", line_number=1),
            Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Issue 2", file_path="/test2.py", line_number=2),
        ]

        async def mock_process(issue, retries):
            return BatchIssueResult(issue=issue, success=True, attempted=True)

        processor._process_single_issue = mock_process

        result = await processor.process_batch(issues, parallel=False)

        assert result.total_issues == 2


class TestAggregateResults:
    """Test _aggregate_results method."""

    def test_aggregate_empty_results(self) -> None:
        """Test aggregating empty results."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        batch_result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.IN_PROGRESS,
            total_issues=0,
        )

        processor._aggregate_results(batch_result, [])

        assert batch_result.results == []

    def test_aggregate_skips_exceptions(self) -> None:
        """Test aggregating skips exceptions."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        batch_result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.IN_PROGRESS,
            total_issues=2,
        )

        issue = Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test", file_path="/test.py", line_number=1)
        issue_results = [
            Exception("Error"),
            BatchIssueResult(issue=issue, success=True, attempted=True),
        ]

        processor._aggregate_results(batch_result, issue_results)

        assert len(batch_result.results) == 1
        assert batch_result.successful == 1

    def test_aggregate_updates_counters(self) -> None:
        """Test aggregating updates success/failure counters."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        batch_result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.IN_PROGRESS,
            total_issues=3,
        )

        issue1 = Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Issue 1", file_path="/test.py", line_number=1)
        issue2 = Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Issue 2", file_path="/test.py", line_number=2)
        issue3 = Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Issue 3", file_path="/test.py", line_number=3)

        issue_results = [
            BatchIssueResult(issue=issue1, success=True, attempted=True),
            BatchIssueResult(issue=issue2, success=False, attempted=True),
            BatchIssueResult(issue=issue3, success=False, attempted=False),
        ]

        processor._aggregate_results(batch_result, issue_results)

        assert batch_result.successful == 1
        assert batch_result.failed == 1
        assert batch_result.skipped == 1


class TestFinalizeBatchMetrics:
    """Test _finalize_batch_metrics method."""

    def test_finalize_calculates_duration(self) -> None:
        """Test duration calculation."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        batch_result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.IN_PROGRESS,
            total_issues=1,
            start_time=datetime.now(),
        )
        batch_result.start_time = datetime.now()
        # Manually set end_time slightly after start_time
        batch_result.end_time = batch_result.start_time

        processor._finalize_batch_metrics(batch_result)

        assert batch_result.duration_seconds >= 0

    def test_finalize_determines_status_completed(self) -> None:
        """Test status determined as completed."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        batch_result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.IN_PROGRESS,
            total_issues=5,
            successful=5,
        )

        processor._finalize_batch_metrics(batch_result)

        assert batch_result.status == BatchStatus.COMPLETED

    def test_finalize_determines_status_partial(self) -> None:
        """Test status determined as partial."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        batch_result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.IN_PROGRESS,
            total_issues=5,
            successful=3,
            failed=2,
        )

        processor._finalize_batch_metrics(batch_result)

        assert batch_result.status == BatchStatus.PARTIAL

    def test_finalize_determines_status_failed(self) -> None:
        """Test status determined as failed."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        batch_result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.IN_PROGRESS,
            total_issues=5,
            successful=0,
            failed=5,
        )

        processor._finalize_batch_metrics(batch_result)

        assert batch_result.status == BatchStatus.FAILED


class TestCalculateSuccessRate:
    """Test _calculate_success_rate method."""

    def test_calculate_success_rate(self) -> None:
        """Test success rate calculation."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        batch_result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.COMPLETED,
            total_issues=10,
            successful=8,
        )

        rate = processor._calculate_success_rate(batch_result)

        assert rate == 0.8

    def test_calculate_success_rate_zero_issues(self) -> None:
        """Test success rate with zero issues."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        batch_result = BatchProcessingResult(
            batch_id="test",
            status=BatchStatus.COMPLETED,
            total_issues=0,
        )

        rate = processor._calculate_success_rate(batch_result)

        assert rate == 0.0


class TestProcessSingleIssue:
    """Test _process_single_issue method."""

    @pytest.mark.asyncio
    async def test_process_single_issue_returns_batch_issue_result(self) -> None:
        """Test _process_single_issue returns BatchIssueResult."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console)

        issue = Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test", file_path="/test.py", line_number=1)

        # Mock _try_fix_with_agents to avoid agent infrastructure
        with patch.object(
            processor,
            "_try_fix_with_agents",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await processor._process_single_issue(issue, max_retries=2)

            # Should return a BatchIssueResult
            assert isinstance(result, BatchIssueResult)
            assert result.issue == issue


class TestTryFixWithAgents:
    """Test _try_fix_with_agents method."""

    @pytest.mark.asyncio
    async def test_try_fix_with_agents_no_agents_for_type(self) -> None:
        """Test _try_fix_with_agents sets error when no agents available for issue type."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console)

        issue = Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test", file_path="/test.py", line_number=1)
        issue_result = BatchIssueResult(issue=issue, success=False)

        # Patch the import at the source module where _try_fix_with_agents imports from
        with patch(
            "crackerjack.agents.coordinator.ISSUE_TYPE_TO_AGENTS",
            {},
        ):
            result = await processor._try_fix_with_agents(issue, issue_result)

            # Returns True because no agents available, sets error
            assert result is True
            assert issue_result.error is not None
            assert "No agents available" in issue_result.error


class TestShouldRetry:
    """Test _should_retry method."""

    def test_should_retry_under_limit(self) -> None:
        """Test should_retry returns True under limit."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        issue_result = BatchIssueResult(
            issue=Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test", file_path="/test.py", line_number=1),
            success=False,
            retry_count=0,
        )

        result = processor._should_retry(issue_result, attempt=0, max_retries=2)

        assert result is True
        assert issue_result.retry_count == 1

    def test_should_retry_at_limit(self) -> None:
        """Test should_retry returns False at limit."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        issue_result = BatchIssueResult(
            issue=Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test", file_path="/test.py", line_number=1),
            success=False,
            retry_count=2,
        )

        result = processor._should_retry(issue_result, attempt=2, max_retries=2)

        assert result is False


class TestHandleRetryError:
    """Test _handle_retry_error method."""

    def test_handle_retry_error_at_max_retries(self) -> None:
        """Test error handling at max retries."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        issue_result = BatchIssueResult(
            issue=Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test", file_path="/test.py", line_number=1),
            success=False,
        )

        result = processor._handle_retry_error(
            issue_result,
            attempt=2,
            max_retries=2,
            error=Exception("Error"),
        )

        assert result is False
        assert issue_result.error is not None

    def test_handle_retry_error_continues(self) -> None:
        """Test error handling continues retry."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        issue_result = BatchIssueResult(
            issue=Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test", file_path="/test.py", line_number=1),
            success=False,
            retry_count=0,
        )

        result = processor._handle_retry_error(
            issue_result,
            attempt=0,
            max_retries=2,
            error=Exception("Error"),
        )

        assert result is True
        assert issue_result.retry_count == 1


class TestGetBatchProcessor:
    """Test get_batch_processor function."""

    def test_get_batch_processor_returns_processor(self) -> None:
        """Test get_batch_processor returns BatchProcessor."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()

        processor = get_batch_processor(context, console)

        assert isinstance(processor, BatchProcessor)

    def test_get_batch_processor_custom_max_parallel(self) -> None:
        """Test get_batch_processor with custom max_parallel."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()

        processor = get_batch_processor(context, console, max_parallel=5)

        assert processor.max_parallel == 5


class TestPrintSummary:
    """Test _print_summary method."""

    def test_print_summary_calls_console(self) -> None:
        """Test print_summary calls console methods."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console)

        batch_result = BatchProcessingResult(
            batch_id="test_batch",
            status=BatchStatus.COMPLETED,
            total_issues=5,
            successful=4,
            failed=1,
            skipped=0,
            success_rate=0.8,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_seconds=1.5,
        )

        processor._print_summary(batch_result)

        # Verify console.print was called multiple times
        assert console.print.called


class TestExecuteBatchProcessing:
    """Test _execute_batch_processing method."""

    @pytest.mark.asyncio
    async def test_execute_parallel_when_enabled(self) -> None:
        """Test parallel execution when enabled."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console, max_parallel=3)

        issues = [
            Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message=f"Issue {i}", file_path="/test.py", line_number=i)
            for i in range(3)
        ]

        async def mock_process(issue, retries):
            return BatchIssueResult(issue=issue, success=True, attempted=True)

        processor._process_single_issue = mock_process

        results = await processor._execute_batch_processing(issues, max_retries=2, parallel=True)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_execute_sequential_when_disabled(self) -> None:
        """Test sequential execution when disabled."""
        context = MagicMock(spec=AgentContext)
        console = MagicMock()
        processor = BatchProcessor(context, console, max_parallel=1)

        issues = [
            Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Issue 1", file_path="/test1.py", line_number=1),
            Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Issue 2", file_path="/test2.py", line_number=2),
        ]

        async def mock_process(issue, retries):
            return BatchIssueResult(issue=issue, success=True, attempted=True)

        processor._process_single_issue = mock_process

        results = await processor._execute_batch_processing(issues, max_retries=2, parallel=False)

        assert len(results) == 2


class TestIsValidResult:
    """Test _is_valid_result method."""

    def test_is_valid_result_exception(self) -> None:
        """Test exception is not valid result."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        result = processor._is_valid_result(Exception("Error"))

        assert result is False

    def test_is_valid_result_wrong_type(self) -> None:
        """Test wrong type is not valid result."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        result = processor._is_valid_result("not a BatchIssueResult")

        assert result is False

    def test_is_valid_result_valid(self) -> None:
        """Test valid BatchIssueResult."""
        processor = BatchProcessor(MagicMock(), MagicMock())
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.MEDIUM, message="Test", file_path="/test.py", line_number=1)
        result = processor._is_valid_result(
            BatchIssueResult(issue=issue, success=True, attempted=True)
        )

        assert result is True
