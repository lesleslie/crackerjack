"""Unit tests for agent error middleware.

Tests the agent_error_boundary decorator that wraps agent execution
with error handling and recovery logic.
"""

from unittest.mock import MagicMock, Mock

import pytest

from crackerjack.agents.base import FixResult, Issue, IssueType, Priority, SubAgent
from crackerjack.agents.error_middleware import agent_error_boundary


@pytest.mark.unit
class TestAgentErrorBoundary:
    """Test agent_error_boundary decorator."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with all required attributes."""
        coordinator = Mock()
        coordinator.context = Mock()
        coordinator.context.console = None  # No console by default
        coordinator.logger = MagicMock()
        coordinator.logger.exception = MagicMock()
        return coordinator

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent."""
        agent = Mock(spec=SubAgent)
        agent.name = "TestAgent"
        return agent

    @pytest.fixture
    def sample_issue(self):
        """Create sample issue for testing."""
        return Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test issue",
            file_path="test.py",
            line_number=10,
        )

    @pytest.fixture
    def sample_fix_result(self):
        """Create sample successful fix result."""
        return FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["Fix 1"],
            files_modified=["test.py"],
        )

    def test_decorator_preserves_function_name(self, mock_coordinator):
        """Test that decorator preserves original function name."""

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            return FixResult(success=True, confidence=0.5)

        assert process_issue.__name__ == "process_issue"

    def test_decorator_wraps_async_function(self):
        """Test that decorator properly wraps async functions."""
        # Test that decorated function is coroutine
        @agent_error_boundary
        async def process_issue(self, agent, issue):
            return FixResult(success=True)

        import inspect

        assert inspect.iscoroutinefunction(process_issue)

    @pytest.mark.asyncio
    async def test_success_path_returns_fix_result(
        self, mock_coordinator, mock_agent, sample_issue, sample_fix_result
    ):
        """Test that successful agent execution returns FixResult unchanged."""

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            return sample_fix_result

        result = await process_issue(mock_coordinator, mock_agent, sample_issue)

        assert result is sample_fix_result
        assert result.success is True
        assert result.confidence == 0.9
        # Verify logger not called on success
        mock_coordinator.logger.exception.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_returns_failure_result(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test that agent exception returns failure FixResult."""

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            raise ValueError("Agent failed")

        result = await process_issue(mock_coordinator, mock_agent, sample_issue)

        assert result.success is False
        assert result.confidence == 0.0
        assert len(result.remaining_issues) > 0
        assert "TestAgent" in result.remaining_issues[0]
        assert "test-001" in result.remaining_issues[0]
        assert "Agent failed" in result.remaining_issues[0]

    @pytest.mark.asyncio
    async def test_exception_logs_to_logger(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test that exception is logged to coordinator logger."""

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            raise RuntimeError("Test error")

        await process_issue(mock_coordinator, mock_agent, sample_issue)

        # Verify logger.exception was called
        mock_coordinator.logger.exception.assert_called_once()
        call_args = mock_coordinator.logger.exception.call_args[0][0]
        assert "TestAgent" in call_args
        assert "test-001" in call_args
        assert "Test error" in call_args

    @pytest.mark.asyncio
    async def test_exception_with_console(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test that exception prints to console if available."""
        # Add console to context
        mock_console = Mock()
        mock_console.print = Mock()
        mock_coordinator.context.console = mock_console

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            raise ValueError("Console test error")

        await process_issue(mock_coordinator, mock_agent, sample_issue)

        # Verify console.print was called
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "[red]" in call_args
        assert "TestAgent" in call_args

    @pytest.mark.asyncio
    async def test_exception_without_console(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test that missing console doesn't cause errors."""
        # Ensure console is None
        assert mock_coordinator.context.console is None

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            raise ValueError("No console error")

        # Should not raise
        result = await process_issue(mock_coordinator, mock_agent, sample_issue)

        assert result.success is False
        # Console should not be accessed
        assert not hasattr(mock_coordinator.context.console, "print")

    @pytest.mark.asyncio
    async def test_exception_includes_recommendations(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test that exception result includes helpful recommendations."""

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            raise KeyError("Missing key")

        result = await process_issue(mock_coordinator, mock_agent, sample_issue)

        assert len(result.recommendations) > 0
        assert any("logs" in rec.lower() for rec in result.recommendations)
        assert any("--debug" in rec for rec in result.recommendations)

    @pytest.mark.asyncio
    async def test_different_exception_types(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test handling of various exception types."""
        exceptions_to_test = [
            ValueError("value error"),
            KeyError("key error"),
            AttributeError("attribute error"),
            RuntimeError("runtime error"),
            IOError("io error"),
            OSError("os error"),
        ]

        for exc in exceptions_to_test:
            @agent_error_boundary
            async def process_issue(self, agent, issue):
                raise exc

            result = await process_issue(mock_coordinator, mock_agent, sample_issue)

            assert result.success is False
            assert result.confidence == 0.0
            assert len(result.remaining_issues) > 0

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(
        self, mock_coordinator, mock_agent, sample_issue, sample_fix_result
    ):
        """Test that decorator properly passes additional arguments."""

        @agent_error_boundary
        async def process_issue(self, agent, issue, extra_arg, kwarg=None):
            assert extra_arg == "extra"
            assert kwarg == "value"
            return sample_fix_result

        result = await process_issue(
            mock_coordinator, mock_agent, sample_issue, "extra", kwarg="value"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_exception_includes_full_context(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test that exception message includes full context."""

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            raise IndexError("Index out of range")

        result = await process_issue(mock_coordinator, mock_agent, sample_issue)

        error_message = result.remaining_issues[0]
        # Check all context is present
        assert "TestAgent" in error_message
        assert "test-001" in error_message
        assert "Index out of range" in error_message
        assert "encountered an error" in error_message.lower()

    @pytest.mark.asyncio
    async def test_preserves_fix_result_on_exception_edge_case(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test that exception handling doesn't modify successful results."""
        original_result = FixResult(
            success=True,
            confidence=0.95,
            fixes_applied=["Fix A", "Fix B"],
            remaining_issues=["Issue 1"],
            recommendations=["Rec 1"],
            files_modified=["file1.py"],
        )

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            return original_result

        result = await process_issue(mock_coordinator, mock_agent, sample_issue)

        # Verify exact same result returned
        assert result is original_result
        assert result.success is True
        assert result.confidence == 0.95
        assert len(result.fixes_applied) == 2
        assert len(result.remaining_issues) == 1

    @pytest.mark.asyncio
    async def test_multiple_sequential_calls(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test that decorator works correctly across multiple calls."""
        call_count = 0

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First failure")
            return FixResult(success=True, confidence=0.8)

        # First call fails
        result1 = await process_issue(mock_coordinator, mock_agent, sample_issue)
        assert result1.success is False

        # Second call succeeds
        result2 = await process_issue(mock_coordinator, mock_agent, sample_issue)
        assert result2.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_exception_with_complex_issue(
        self, mock_coordinator, mock_agent
    ):
        """Test exception handling with complex issue object."""
        complex_issue = Issue(
            id="complex-001",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Complex security vulnerability",
            file_path="/path/to/security/module.py",
            line_number=42,
            details=["Detail 1", "Detail 2", "Detail 3"],
            stage="analysis",
        )

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            raise SecurityError("Security check failed")

        result = await process_issue(mock_coordinator, mock_agent, complex_issue)

        assert result.success is False
        assert "complex-001" in result.remaining_issues[0]
        assert "SecurityError" in result.remaining_issues[0] or "Security check failed" in result.remaining_issues[0]

    @pytest.mark.asyncio
    async def test_decorator_with_async_context_manager(
        self, mock_coordinator, mock_agent, sample_issue
    ):
        """Test decorator works with async context managers in wrapped function."""

        @agent_error_boundary
        async def process_issue(self, agent, issue):
            # Simulate async context manager usage
            async def inner_operation():
                return FixResult(success=True, confidence=0.85)

            return await inner_operation()

        result = await process_issue(mock_coordinator, mock_agent, sample_issue)

        assert result.success is True
        assert result.confidence == 0.85


# Custom exception for testing
class SecurityError(Exception):
    """Custom security exception for testing."""

    pass
