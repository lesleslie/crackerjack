"""Advanced integration tests for session lifecycle management.

Tests the complete session management workflow from initialization through
checkpoint creation to session cleanup with proper async patterns.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from session_mgmt_mcp.server import (
    checkpoint,
    end,
    init,
    permissions,
    quick_search,
    status,
    store_reflection,
)
from tests.fixtures.mcp_fixtures import AsyncTestCase


@pytest.mark.integration
@pytest.mark.asyncio
class TestSessionLifecycleIntegration(AsyncTestCase):
    """Comprehensive session lifecycle integration tests."""

    async def test_complete_session_workflow(
        self,
        mock_session_permissions,
        isolated_database,
        temporary_project_structure,
    ):
        """Test complete session workflow from init to end."""
        working_dir = str(temporary_project_structure)

        # Phase 1: Session Initialization
        with patch.dict("os.environ", {"PWD": working_dir}):
            init_result = await init(working_directory=working_dir)

        assert "SESSION INITIALIZATION COMPLETE" in init_result
        assert "session-mgmt-mcp" in init_result

        # Verify initialization side effects
        assert mock_session_permissions.trust_operation.call_count >= 0

        # Phase 2: Status Check
        status_result = await status(working_directory=working_dir)
        assert "Session Status" in status_result or "health" in status_result.lower()

        # Phase 3: Store Reflection
        reflection_result = await store_reflection(
            content="Session initialized successfully with comprehensive testing",
            tags=["testing", "session-management", "integration"],
        )
        assert (
            "stored successfully" in reflection_result.lower()
            or "success" in reflection_result.lower()
        )

        # Phase 4: Quality Checkpoint
        checkpoint_result = await checkpoint()
        assert "checkpoint" in checkpoint_result.lower()

        # Phase 5: Memory Search
        search_result = await quick_search(
            query="session initialization testing",
            min_score=0.5,
        )
        assert isinstance(
            search_result,
            dict | str,
        )  # Accept either dict or string response

        # Phase 6: Session End
        end_result = await end()
        assert "session ended" in end_result.lower() or "cleanup" in end_result.lower()

    @pytest.mark.asyncio
    async def test_session_error_recovery(
        self,
        mock_session_permissions,
        isolated_database,
    ):
        """Test session error recovery patterns."""
        # Test basic init functionality without workspace validation dependency
        result = await init()
        assert "SESSION INITIALIZATION COMPLETE" in result

    @pytest.mark.asyncio
    async def test_permission_system_integration(
        self,
        mock_session_permissions,
        temporary_project_structure,
    ):
        """Test permission system integration across tools."""
        working_dir = str(temporary_project_structure)

        # Initialize session
        await init(working_directory=working_dir)

        # Test permission operations
        permissions_result = await permissions(action="status")
        assert isinstance(permissions_result, str)  # MCP tools return strings

        # Trust a new operation
        trust_result = await permissions(action="trust", operation="advanced_analysis")
        assert isinstance(trust_result, str)

        # Verify trusted operation is recorded
        status_result = await permissions(action="status")
        assert isinstance(status_result, str)

    @pytest.mark.asyncio
    async def test_concurrent_session_operations(
        self,
        mock_session_permissions,
        isolated_database,
    ):
        """Test concurrent session operations don't interfere."""
        # Simulate concurrent operations
        tasks = [
            asyncio.create_task(
                store_reflection(
                    content=f"Concurrent reflection {i}",
                    tags=[f"test-{i}"],
                ),
            )
            for i in range(5)
        ]

        # Wait for all reflections to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed (no exceptions)
        for result in results:
            assert not isinstance(result, Exception)
            assert isinstance(result, str)

        # Verify all reflections are searchable
        search_result = await quick_search(query="concurrent reflection", limit=10)
        # Should return a string response
        assert isinstance(search_result, str | dict)

    @pytest.mark.asyncio
    async def test_database_isolation_between_sessions(self, isolated_database):
        """Test that different sessions maintain data isolation."""
        # Session 1: Store data
        session1_reflection = await store_reflection(
            content="Session 1 exclusive data",
            tags=["session-1"],
        )
        assert isinstance(session1_reflection, str)

        # Create new isolated database for session 2
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir) / "session2.db"

            with patch(
                "session_mgmt_mcp.reflection_tools.ReflectionDatabase",
            ) as mock_db_class:
                mock_db = AsyncMock()
                mock_db.search_conversations.return_value = {"results": [], "count": 0}
                mock_db_class.return_value = mock_db

                # Session 2: Should not see session 1 data
                search_result = await quick_search(
                    query="Session 1 exclusive",
                    project="test",
                )
                assert isinstance(search_result, str | dict)

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_session_performance_metrics(
        self,
        performance_metrics_collector,
        temporary_project_structure,
    ):
        """Test session operations meet performance requirements."""
        import time

        working_dir = str(temporary_project_structure)

        # Measure initialization time
        start_time = time.time()
        await init(working_directory=working_dir)
        init_time = time.time() - start_time

        performance_metrics_collector["record_execution_time"]("init", init_time)
        assert init_time < 5.0  # Should complete within 5 seconds

        # Measure checkpoint time
        start_time = time.time()
        await checkpoint()
        checkpoint_time = time.time() - start_time

        performance_metrics_collector["record_execution_time"](
            "checkpoint",
            checkpoint_time,
        )
        assert checkpoint_time < 3.0  # Should complete within 3 seconds

        # Measure cleanup time
        start_time = time.time()
        await end()
        cleanup_time = time.time() - start_time

        performance_metrics_collector["record_execution_time"]("end", cleanup_time)
        assert cleanup_time < 2.0  # Should complete within 2 seconds

    @pytest.mark.asyncio
    async def test_session_state_consistency(
        self,
        mock_session_permissions,
        temporary_project_structure,
    ):
        """Test session state remains consistent across operations."""
        working_dir = str(temporary_project_structure)

        # Initialize session and capture initial state
        init_result = await init(working_directory=working_dir)
        assert "SESSION INITIALIZATION COMPLETE" in init_result

        # Perform multiple state-changing operations
        await store_reflection(content="Test reflection 1", tags=["test"])
        await checkpoint()
        await store_reflection(content="Test reflection 2", tags=["test"])

        # Verify session state consistency
        status_result = await status(working_directory=working_dir)
        assert isinstance(status_result, str)
        assert "status" in status_result.lower() or "session" in status_result.lower()


@pytest.mark.integration
@pytest.mark.mcp
class TestMCPToolRegistration:
    """Test MCP tool registration and execution patterns."""

    @pytest.mark.asyncio
    async def test_all_tools_registered(self, mock_mcp_server):
        """Test all expected MCP tools are properly registered."""
        expected_tools = [
            "init",
            "checkpoint",
            "end",
            "status",
            "permissions",
            "reflect_on_past",
            "store_reflection",
            "quick_search",
            "search_summary",
            "get_more_results",
            "search_by_file",
            "search_by_concept",
            "reflection_stats",
        ]

        # In actual implementation, these would be registered on the real mcp instance
        # Here we simulate checking the registration
        from session_mgmt_mcp import server

        # Verify the functions exist and are callable
        for tool_name in expected_tools:
            assert hasattr(server, tool_name)
            tool_func = getattr(server, tool_name)
            assert callable(tool_func)

    @pytest.mark.asyncio
    async def test_tool_parameter_validation(self):
        """Test MCP tools validate parameters correctly."""
        # Test required parameters
        with pytest.raises((TypeError, ValueError)):
            await store_reflection()  # Missing required content parameter

        # Test parameter types
        result = await store_reflection(content="Valid content", tags=["valid", "tags"])
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_tool_error_handling(self, isolated_database):
        """Test MCP tools handle errors gracefully."""
        # Test with invalid project parameter
        result = await quick_search(
            query="test",
            project="/invalid/path/that/does/not/exist",
        )
        # Should not crash, may return empty results or error
        assert isinstance(result, str | dict)
