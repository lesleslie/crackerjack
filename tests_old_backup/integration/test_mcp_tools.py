"""Integration tests for MCP tools in session-mgmt-mcp.

Tests the complete workflow of session management tools including:
- Session initialization
- Checkpoint creation
- Session end and cleanup
- Status reporting
- Reflection management
"""

import asyncio

import pytest
from tests.mcp.test_helpers import (
    MCPTestClient,
    MCPTestEnvironment,
    MockMCPServer,
    assert_successful_tool_call,
    assert_tool_call_made,
    simulate_session_workflow,
)


@pytest.mark.integration
class TestMCPSessionTools:
    """Integration tests for session management MCP tools."""

    @pytest.fixture
    async def mcp_test_environment(self):
        """Setup complete MCP test environment."""
        env = MCPTestEnvironment()

        # Setup temporary workspace
        workspace = env.setup_temp_workspace()

        # Create test project
        test_project = workspace / "Projects" / "test-project"
        test_project.mkdir(parents=True)
        env.setup_mock_git_repo(test_project)

        # Mock environment variables
        env.add_mock_patch(
            "os.environ.get",
            side_effect=lambda key, default=None: {
                "PWD": str(test_project),
                "HOME": str(workspace),
                "TESTING": "true",
            }.get(key, default),
        )

        yield env, workspace, test_project

        env.cleanup()

    @pytest.fixture
    async def mock_mcp_server(self):
        """Create mock MCP server for testing."""
        return MockMCPServer()

    @pytest.fixture
    async def mcp_client(self, mock_mcp_server):
        """Create MCP test client."""
        return MCPTestClient(mock_mcp_server)

    @pytest.mark.asyncio
    async def test_session_init_tool(self, mcp_client, mcp_test_environment):
        """Test session initialization tool."""
        env, workspace, test_project = mcp_test_environment

        # Call init tool
        result = await mcp_client.call_tool(
            "init",
            {"working_directory": str(test_project)},
        )

        # Verify successful initialization
        assert result["success"] is True
        assert "working_directory" in result
        assert "quality_score" in result
        assert "health_checks" in result

        # Verify tool call was recorded
        assert_tool_call_made(
            mcp_client,
            "init",
            {"working_directory": str(test_project)},
        )
        assert_successful_tool_call(mcp_client, "init")

    @pytest.mark.asyncio
    async def test_session_checkpoint_tool(self, mcp_client):
        """Test session checkpoint tool."""
        # Initialize session first
        await mcp_client.call_tool("init", {"working_directory": "/tmp/test"})

        # Create checkpoint
        result = await mcp_client.call_tool("checkpoint", {})

        # Verify checkpoint creation
        assert result["success"] is True
        assert result["checkpoint_created"] is True
        assert "quality_score" in result

        assert_successful_tool_call(mcp_client, "checkpoint")

    @pytest.mark.asyncio
    async def test_session_end_tool(self, mcp_client):
        """Test session end tool."""
        # Initialize session first
        await mcp_client.call_tool("init", {"working_directory": "/tmp/test"})

        # End session
        result = await mcp_client.call_tool("end", {})

        # Verify session ended
        assert result["success"] is True
        assert result["session_ended"] is True
        assert "final_score" in result

        assert_successful_tool_call(mcp_client, "end")

    @pytest.mark.asyncio
    async def test_session_status_tool(self, mcp_client):
        """Test session status tool."""
        # Initialize session
        await mcp_client.call_tool("init", {"working_directory": "/tmp/test"})

        # Check status
        result = await mcp_client.call_tool("status", {})

        # Verify status information
        assert "session_active" in result
        assert "health_status" in result

        assert_successful_tool_call(mcp_client, "status")

    @pytest.mark.asyncio
    async def test_complete_session_workflow(self, mcp_client, mcp_test_environment):
        """Test complete session management workflow."""
        env, workspace, test_project = mcp_test_environment

        # Run complete workflow simulation
        workflow_results = await simulate_session_workflow(
            mcp_client,
            str(test_project),
        )

        # Verify no errors occurred
        assert len(workflow_results["errors"]) == 0

        # Verify all steps completed successfully
        assert workflow_results["init"] is not None
        assert workflow_results["init"]["success"] is True

        assert workflow_results["checkpoint"] is not None
        assert workflow_results["checkpoint"]["success"] is True

        assert workflow_results["end"] is not None
        assert workflow_results["end"]["success"] is True

        # Verify status was checked
        assert len(workflow_results["status_checks"]) >= 2

    @pytest.mark.asyncio
    async def test_reflection_storage_integration(self, mcp_client):
        """Test reflection storage and retrieval integration."""
        # Store a reflection
        reflection_content = "Implemented comprehensive testing framework"
        tags = ["testing", "framework", "implementation"]

        store_result = await mcp_client.call_tool(
            "store_reflection",
            {"content": reflection_content, "tags": tags},
        )

        assert store_result["success"] is True

        # Search for the reflection
        search_result = await mcp_client.call_tool(
            "reflect_on_past",
            {"query": "testing framework"},
        )

        assert "results" in search_result
        assert len(search_result["results"]) >= 1

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, mcp_client):
        """Test concurrent MCP tool calls."""
        # Initialize session
        await mcp_client.call_tool("init", {"working_directory": "/tmp/test"})

        # Create multiple concurrent tool calls
        tasks = []

        # Multiple status checks
        for i in range(5):
            task = mcp_client.call_tool("status", {})
            tasks.append(task)

        # Multiple reflection storage
        for i in range(3):
            task = mcp_client.call_tool(
                "store_reflection",
                {"content": f"Concurrent reflection {i}", "tags": [f"concurrent-{i}"]},
            )
            tasks.append(task)

        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no exceptions occurred
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Unexpected exceptions: {exceptions}"

        # Verify all calls succeeded
        successes = [r for r in results if isinstance(r, dict) and r.get("success")]
        assert len(successes) == len(tasks)


@pytest.mark.integration
class TestMCPReflectionTools:
    """Integration tests for reflection management tools."""

    @pytest.fixture
    async def reflection_environment(self, mcp_test_environment):
        """Setup environment with reflection database."""
        env, workspace, test_project = mcp_test_environment

        # Create reflection database directory
        reflection_dir = workspace / ".claude" / "data"
        reflection_dir.mkdir(parents=True, exist_ok=True)

        return env, workspace, test_project, reflection_dir

    @pytest.fixture
    async def mcp_client_with_reflections(self, reflection_environment):
        """MCP client with reflection test data."""
        env, workspace, test_project, reflection_dir = reflection_environment

        server = MockMCPServer()
        client = MCPTestClient(server)

        # Pre-populate with test reflections
        test_reflections = [
            {
                "content": "Implemented user authentication with OAuth2",
                "tags": ["authentication", "oauth2", "security"],
                "project": "test-app",
            },
            {
                "content": "Optimized database queries for better performance",
                "tags": ["database", "performance", "optimization"],
                "project": "test-app",
            },
            {
                "content": "Created comprehensive test suite for API endpoints",
                "tags": ["testing", "api", "endpoints"],
                "project": "api-service",
            },
        ]

        for reflection in test_reflections:
            await client.call_tool("store_reflection", reflection)

        return client

    @pytest.mark.asyncio
    async def test_reflection_search_by_content(self, mcp_client_with_reflections):
        """Test searching reflections by content."""
        client = mcp_client_with_reflections

        # Search for authentication-related reflections
        result = await client.call_tool("reflect_on_past", {"query": "authentication"})

        assert "results" in result
        assert len(result["results"]) >= 1

        # Verify result contains authentication content
        auth_result = result["results"][0]
        assert (
            "oauth2" in auth_result["content"].lower()
            or "authentication" in auth_result["content"].lower()
        )

    @pytest.mark.asyncio
    async def test_reflection_search_by_project(self, mcp_client_with_reflections):
        """Test searching reflections filtered by project."""
        client = mcp_client_with_reflections

        # Search within specific project
        result = await client.call_tool(
            "reflect_on_past",
            {"query": "test", "project": "test-app"},
        )

        assert "results" in result
        for reflection_result in result["results"]:
            # All results should be from test-app project
            assert reflection_result["project"] == "test-app"

    @pytest.mark.asyncio
    async def test_reflection_search_with_limits(self, mcp_client_with_reflections):
        """Test reflection search with result limits."""
        client = mcp_client_with_reflections

        # Search with specific limit
        result = await client.call_tool(
            "reflect_on_past",
            {"query": "test", "limit": 2},
        )

        assert "results" in result
        assert len(result["results"]) <= 2

    @pytest.mark.asyncio
    async def test_reflection_storage_with_tags(self, mcp_client_with_reflections):
        """Test storing reflection with multiple tags."""
        client = mcp_client_with_reflections

        # Store reflection with complex tags
        result = await client.call_tool(
            "store_reflection",
            {
                "content": "Implemented real-time WebSocket communication for chat feature",
                "tags": ["websocket", "real-time", "chat", "communication", "feature"],
            },
        )

        assert result["success"] is True

        # Search for the stored reflection
        search_result = await client.call_tool(
            "reflect_on_past",
            {"query": "websocket real-time"},
        )

        assert len(search_result["results"]) >= 1
        websocket_result = next(
            (
                r
                for r in search_result["results"]
                if "websocket" in r["content"].lower()
            ),
            None,
        )
        assert websocket_result is not None

    @pytest.mark.asyncio
    async def test_reflection_search_empty_results(self, mcp_client_with_reflections):
        """Test reflection search with no matching results."""
        client = mcp_client_with_reflections

        # Search for something that doesn't exist
        result = await client.call_tool(
            "reflect_on_past",
            {"query": "nonexistent-technology-xyz"},
        )

        assert "results" in result
        assert len(result["results"]) == 0

    @pytest.mark.asyncio
    async def test_reflection_search_case_insensitive(
        self,
        mcp_client_with_reflections,
    ):
        """Test case-insensitive reflection search."""
        client = mcp_client_with_reflections

        # Search with different cases
        queries = ["DATABASE", "database", "Database", "dataBase"]

        for query in queries:
            result = await client.call_tool("reflect_on_past", {"query": query})

            assert "results" in result
            assert len(result["results"]) >= 1, f"No results for query: {query}"


@pytest.mark.integration
class TestMCPErrorHandling:
    """Integration tests for MCP tool error handling."""

    @pytest.fixture
    async def error_prone_server(self):
        """Create MCP server that simulates errors."""
        server = MockMCPServer()

        # Override some methods to simulate errors
        original_init = server._mock_init

        async def failing_init(args):
            if args.get("should_fail"):
                return {"error": "Simulated initialization failure"}
            return await original_init(args)

        server._mock_init = failing_init
        return server

    @pytest.mark.asyncio
    async def test_tool_error_handling(self, error_prone_server):
        """Test proper error handling in MCP tools."""
        client = MCPTestClient(error_prone_server)

        # Call tool with error trigger
        result = await client.call_tool(
            "init",
            {"working_directory": "/tmp/test", "should_fail": True},
        )

        # Should receive error response
        assert "error" in result
        assert result["error"] == "Simulated initialization failure"

    @pytest.mark.asyncio
    async def test_invalid_tool_call(self):
        """Test calling non-existent tool."""
        server = MockMCPServer()
        client = MCPTestClient(server)

        # Call non-existent tool
        result = await client.call_tool("nonexistent_tool", {})

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_malformed_arguments(self):
        """Test tool calls with malformed arguments."""
        server = MockMCPServer()
        client = MCPTestClient(server)

        # Call init with missing required arguments - should handle gracefully
        result = await client.call_tool("init", {})

        # Should succeed with default values or provide appropriate error
        assert isinstance(result, dict)
        # Either success or appropriate error message
        assert "error" in result or result.get("success") is True


@pytest.mark.integration
@pytest.mark.slow
class TestMCPPerformanceIntegration:
    """Integration tests for MCP performance under load."""

    @pytest.mark.asyncio
    async def test_high_volume_reflections(self, performance_monitor):
        """Test performance with high volume of reflections."""
        server = MockMCPServer()
        client = MCPTestClient(server)

        performance_monitor.start_monitoring()

        # Store many reflections
        tasks = []
        for i in range(100):
            task = client.call_tool(
                "store_reflection",
                {
                    "content": f"Performance test reflection number {i}",
                    "tags": [f"performance-{i % 10}", "load-test"],
                    "project": f"test-project-{i % 5}",
                },
            )
            tasks.append(task)

        # Execute all storage operations
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        successes = [r for r in results if r.get("success")]
        assert len(successes) == 100

        # Perform search operations
        search_tasks = []
        for i in range(20):
            task = client.call_tool(
                "reflect_on_past",
                {"query": f"performance-{i % 10}", "limit": 5},
            )
            search_tasks.append(task)

        search_results = await asyncio.gather(*search_tasks)

        metrics = performance_monitor.stop_monitoring()

        # Performance assertions
        assert metrics["duration"] < 30.0  # Should complete within 30 seconds
        assert len(search_results) == 20

    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self):
        """Test concurrent session operations."""
        server = MockMCPServer()

        # Create multiple clients simulating concurrent users
        clients = [MCPTestClient(server) for _ in range(5)]

        async def session_workflow(client, client_id):
            """Run session workflow for one client."""
            # Initialize
            init_result = await client.call_tool(
                "init",
                {"working_directory": f"/tmp/test-{client_id}"},
            )

            # Multiple operations
            operations = []
            for i in range(3):
                operations.append(client.call_tool("status", {}))
                operations.append(
                    client.call_tool(
                        "store_reflection",
                        {
                            "content": f"Client {client_id} reflection {i}",
                            "project": f"project-{client_id}",
                        },
                    ),
                )

            await asyncio.gather(*operations)

            # Checkpoint and end
            await client.call_tool("checkpoint", {})
            end_result = await client.call_tool("end", {})

            return {
                "client_id": client_id,
                "init_success": init_result.get("success"),
                "end_success": end_result.get("success"),
            }

        # Run all client workflows concurrently
        workflow_tasks = [session_workflow(clients[i], i) for i in range(len(clients))]

        results = await asyncio.gather(*workflow_tasks)

        # Verify all workflows completed successfully
        for result in results:
            assert result["init_success"] is True
            assert result["end_success"] is True

    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, performance_monitor):
        """Test memory usage stability over extended operations."""
        server = MockMCPServer()
        client = MCPTestClient(server)

        performance_monitor.start_monitoring()

        # Initialize session
        await client.call_tool("init", {"working_directory": "/tmp/test"})

        # Perform many operations
        for batch in range(10):
            # Create batch of operations
            batch_tasks = []

            # Mix different types of operations
            for i in range(20):
                if i % 4 == 0:
                    batch_tasks.append(client.call_tool("status", {}))
                elif i % 4 == 1:
                    batch_tasks.append(
                        client.call_tool(
                            "store_reflection",
                            {
                                "content": f"Batch {batch} reflection {i}",
                                "project": "memory-test",
                            },
                        ),
                    )
                elif i % 4 == 2:
                    batch_tasks.append(
                        client.call_tool(
                            "reflect_on_past",
                            {"query": f"batch {batch % 3}", "limit": 3},
                        ),
                    )
                else:
                    batch_tasks.append(client.call_tool("checkpoint", {}))

            # Execute batch
            await asyncio.gather(*batch_tasks)

            # Small delay between batches
            await asyncio.sleep(0.1)

        # End session
        await client.call_tool("end", {})

        metrics = performance_monitor.stop_monitoring()

        # Memory should not grow excessively
        assert metrics["memory_delta"] < 100  # Less than 100MB growth
        assert metrics["duration"] < 60  # Should complete within 1 minute
