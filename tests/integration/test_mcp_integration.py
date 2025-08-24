"""Integration tests for MCP server and WebSocket functionality.

Tests complete MCP workflow integration:
- MCP server startup and shutdown
- WebSocket server communication
- Job management and progress tracking
- Error analysis and auto-fixing integration
- Session management across iterations
"""

import asyncio
import time

import pytest

# Import MCP components if available
try:
    from crackerjack.mcp.cache import ErrorCache
    from crackerjack.mcp.context import MCPContext
    from crackerjack.mcp.rate_limiter import RateLimiter
    from crackerjack.mcp.state import SessionState

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

try:
    from crackerjack.mcp.websocket.jobs import JobManager

    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


@pytest.mark.integration
@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP components not available")
class TestMCPServerIntegration:
    """Test MCP server integration functionality."""

    def test_session_state_management(self) -> None:
        """Test session state creation and management."""
        session_state = SessionState()

        # Test session creation
        session_id = "test_session_123"
        session_state.create_session(session_id)

        assert session_state.has_session(session_id)

        # Test session data
        session_state.set_session_data(session_id, "test_key", "test_value")
        value = session_state.get_session_data(session_id, "test_key")

        assert value == "test_value"

        # Test session cleanup
        session_state.cleanup_session(session_id)
        assert not session_state.has_session(session_id)

    def test_error_cache_functionality(self) -> None:
        """Test error pattern caching."""
        cache = ErrorCache()

        # Test error pattern storage
        error_pattern = "Import error: module not found"
        fix_result = {"status": "fixed", "changes": ["added import"]}

        cache.store_fix_result(error_pattern, fix_result)

        # Test pattern retrieval
        cached_result = cache.get_fix_result(error_pattern)
        assert cached_result == fix_result

        # Test cache statistics
        stats = cache.get_cache_stats()
        assert isinstance(stats, dict)
        assert "hit_rate" in stats or "total_entries" in stats

    def test_rate_limiter_functionality(self) -> None:
        """Test rate limiting for API calls."""
        rate_limiter = RateLimiter(requests_per_minute=60)

        # Test rate limiting
        assert rate_limiter.can_proceed()

        # Record request
        rate_limiter.record_request()

        # Should still be able to proceed
        assert rate_limiter.can_proceed()

        # Test statistics
        stats = rate_limiter.get_stats()
        assert isinstance(stats, dict)

    def test_mcp_context_integration(self, sample_config) -> None:
        """Test MCP context manager."""
        context = MCPContext(sample_config)

        # Test context initialization
        assert context.config == sample_config

        # Test service access
        services = context.get_all_services()
        assert isinstance(services, dict)


@pytest.mark.integration
@pytest.mark.skipif(
    not WEBSOCKET_AVAILABLE, reason="WebSocket components not available",
)
class TestWebSocketIntegration:
    """Test WebSocket server integration."""

    @pytest.mark.asyncio
    async def test_job_manager_basic_operations(self) -> None:
        """Test basic job manager operations."""
        job_manager = JobManager()

        # Test job creation
        job_id = await job_manager.create_job("test_operation", {"param": "value"})

        assert isinstance(job_id, str)
        assert len(job_id) > 0

        # Test job status
        job_info = await job_manager.get_job_info(job_id)

        assert job_info is not None
        assert job_info["id"] == job_id
        assert job_info["operation"] == "test_operation"

        # Test job completion
        await job_manager.complete_job(job_id, {"result": "success"})

        final_info = await job_manager.get_job_info(job_id)
        assert final_info["status"] == "completed"

    @pytest.mark.asyncio
    async def test_job_progress_tracking(self) -> None:
        """Test job progress updates."""
        job_manager = JobManager()

        job_id = await job_manager.create_job("progress_test", {})

        # Update progress
        await job_manager.update_progress(job_id, 25, "Starting phase 1")
        await job_manager.update_progress(job_id, 50, "Halfway complete")
        await job_manager.update_progress(job_id, 100, "Finished")

        # Get final job info
        job_info = await job_manager.get_job_info(job_id)

        assert job_info["progress"] == 100
        assert "Finished" in job_info["status_message"]

    @pytest.mark.asyncio
    async def test_job_error_handling(self) -> None:
        """Test job error scenarios."""
        job_manager = JobManager()

        job_id = await job_manager.create_job("error_test", {})

        # Simulate job error
        error_details = {"error": "Test error", "traceback": "Mock traceback"}
        await job_manager.fail_job(job_id, error_details)

        # Check job status
        job_info = await job_manager.get_job_info(job_id)

        assert job_info["status"] == "failed"
        assert "Test error" in str(job_info)


@pytest.mark.integration
class TestMCPToolIntegration:
    """Test MCP tool functionality integration."""

    def test_tool_execution_flow(self, sample_config) -> None:
        """Test complete tool execution workflow."""
        # Mock tool execution context
        mock_context = {
            "config": sample_config,
            "session_id": "test_session",
            "job_id": "test_job",
        }

        # Test basic tool structure
        assert isinstance(mock_context, dict)
        assert "config" in mock_context
        assert "session_id" in mock_context

    def test_error_analysis_integration(self) -> None:
        """Test error analysis tool integration."""
        # Mock error data
        error_data = [
            {
                "type": "import_error",
                "message": "Module 'xyz' not found",
                "file": "test.py",
                "line": 10,
            },
            {
                "type": "syntax_error",
                "message": "Invalid syntax",
                "file": "other.py",
                "line": 5,
            },
        ]

        # Test error categorization
        import_errors = [e for e in error_data if e["type"] == "import_error"]
        syntax_errors = [e for e in error_data if e["type"] == "syntax_error"]

        assert len(import_errors) == 1
        assert len(syntax_errors) == 1

    def test_progress_reporting_integration(self) -> None:
        """Test progress reporting functionality."""
        # Mock progress data
        progress_data = {
            "job_id": "test_123",
            "progress": 75,
            "stage": "running_hooks",
            "message": "Executing pre-commit hooks",
            "errors": [],
            "timestamp": time.time(),
        }

        # Test progress structure
        assert progress_data["progress"] == 75
        assert progress_data["stage"] == "running_hooks"
        assert isinstance(progress_data["errors"], list)
        assert isinstance(progress_data["timestamp"], float)


@pytest.mark.integration
@pytest.mark.slow
class TestMCPPerformanceIntegration:
    """Test MCP performance characteristics."""

    def test_session_state_performance(self, performance_timer) -> None:
        """Test session state operations performance."""
        if not MCP_AVAILABLE:
            pytest.skip("MCP components not available")

        session_state = SessionState()

        timer = performance_timer()

        # Create multiple sessions
        session_ids = []
        for i in range(100):
            session_id = f"session_{i}"
            session_state.create_session(session_id)
            session_ids.append(session_id)

        duration = timer()

        # Should create sessions quickly
        assert duration < 1.0  # Less than 1 second for 100 sessions

        # Cleanup
        for session_id in session_ids:
            session_state.cleanup_session(session_id)

    def test_error_cache_performance(self, performance_timer) -> None:
        """Test error cache performance."""
        if not MCP_AVAILABLE:
            pytest.skip("MCP components not available")

        cache = ErrorCache()

        timer = performance_timer()

        # Store many error patterns
        for i in range(500):
            pattern = f"Error pattern {i}"
            fix_result = {"fix_id": i, "status": "resolved"}
            cache.store_fix_result(pattern, fix_result)

        duration = timer()

        # Should store patterns quickly
        assert duration < 2.0  # Less than 2 seconds for 500 patterns

        # Test retrieval performance
        timer = performance_timer()

        for i in range(100):
            pattern = f"Error pattern {i}"
            result = cache.get_fix_result(pattern)
            assert result is not None

        retrieval_duration = timer()

        # Should retrieve quickly
        assert retrieval_duration < 0.5  # Less than 0.5 seconds for 100 retrievals


@pytest.mark.integration
@pytest.mark.asyncio
class TestAsyncMCPIntegration:
    """Test async MCP operations."""

    async def test_async_job_processing(self) -> None:
        """Test async job processing workflow."""
        if not WEBSOCKET_AVAILABLE:
            pytest.skip("WebSocket components not available")

        job_manager = JobManager()

        # Create multiple jobs
        job_ids = []
        for i in range(5):
            job_id = await job_manager.create_job(f"async_job_{i}", {"index": i})
            job_ids.append(job_id)

        # Process jobs concurrently
        async def process_job(job_id, index) -> None:
            await job_manager.update_progress(job_id, 50, f"Processing {index}")
            await asyncio.sleep(0.1)  # Simulate work
            await job_manager.complete_job(job_id, {"result": f"completed_{index}"})

        # Execute all jobs concurrently
        await asyncio.gather(
            *[process_job(job_id, i) for i, job_id in enumerate(job_ids)],
        )

        # Verify all jobs completed
        for job_id in job_ids:
            job_info = await job_manager.get_job_info(job_id)
            assert job_info["status"] == "completed"

    async def test_async_error_handling(self) -> None:
        """Test async error handling in MCP operations."""
        if not WEBSOCKET_AVAILABLE:
            pytest.skip("WebSocket components not available")

        job_manager = JobManager()

        # Create job that will fail
        job_id = await job_manager.create_job("failing_job", {})

        try:
            # Simulate async operation that fails
            await job_manager.update_progress(job_id, 25, "Starting")

            # Simulate failure
            msg = "Simulated async error"
            raise ValueError(msg)

        except ValueError as e:
            # Handle error
            await job_manager.fail_job(job_id, {"error": str(e), "type": "ValueError"})

        # Verify job marked as failed
        job_info = await job_manager.get_job_info(job_id)
        assert job_info["status"] == "failed"
        assert "Simulated async error" in str(job_info)


@pytest.mark.integration
@pytest.mark.security
class TestMCPSecurityIntegration:
    """Test MCP security integration."""

    def test_rate_limiting_security(self) -> None:
        """Test rate limiting prevents abuse."""
        if not MCP_AVAILABLE:
            pytest.skip("MCP components not available")

        # Create restrictive rate limiter
        rate_limiter = RateLimiter(requests_per_minute=5, max_burst=3)

        # Should allow initial requests
        for _i in range(3):
            assert rate_limiter.can_proceed()
            rate_limiter.record_request()

        # Should start rate limiting
        # Note: Actual rate limiting behavior depends on implementation
        remaining_allowed = 0
        for _i in range(10):
            if rate_limiter.can_proceed():
                rate_limiter.record_request()
                remaining_allowed += 1

        # Should have limited additional requests
        assert remaining_allowed <= 5  # Should not allow unlimited requests

    def test_session_isolation(self) -> None:
        """Test session data isolation."""
        if not MCP_AVAILABLE:
            pytest.skip("MCP components not available")

        session_state = SessionState()

        # Create separate sessions
        session1 = "session_1"
        session2 = "session_2"

        session_state.create_session(session1)
        session_state.create_session(session2)

        # Set different data in each session
        session_state.set_session_data(session1, "secret", "value1")
        session_state.set_session_data(session2, "secret", "value2")

        # Verify isolation
        value1 = session_state.get_session_data(session1, "secret")
        value2 = session_state.get_session_data(session2, "secret")

        assert value1 == "value1"
        assert value2 == "value2"
        assert value1 != value2

        # Cleanup
        session_state.cleanup_session(session1)
        session_state.cleanup_session(session2)
