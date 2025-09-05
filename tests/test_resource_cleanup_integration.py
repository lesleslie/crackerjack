"""Integration tests for comprehensive resource cleanup patterns.

Tests that all resource cleanup patterns work correctly in error scenarios
and prevent resource leaks across the entire crackerjack system.
"""

import asyncio
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from crackerjack.core.file_lifecycle import (
    SafeFileOperations,
    atomic_file_write,
    batch_file_operations,
    locked_file_access,
    safe_directory_creation,
)
from crackerjack.core.resource_manager import (
    ResourceContext,
    cleanup_all_global_resources,
    enable_leak_detection,
    with_temp_dir,
    with_temp_file,
)
from crackerjack.core.websocket_lifecycle import (
    NetworkResourceManager,
    cleanup_all_network_resources,
)
from crackerjack.mcp.context import MCPServerConfig, MCPServerContext


class TestResourceManagerIntegration:
    """Test basic resource manager functionality."""

    @pytest.mark.asyncio
    async def test_resource_context_cleanup_on_success(self):
        """Test that resources are cleaned up properly on successful completion."""
        cleanup_called = []

        class MockResource:
            async def cleanup(self):
                cleanup_called.append(True)

        async with ResourceContext() as ctx:
            resource = MockResource()
            ctx.resource_manager.register_resource(resource)

        assert len(cleanup_called) == 1

    @pytest.mark.asyncio
    async def test_resource_context_cleanup_on_exception(self):
        """Test that resources are cleaned up properly when exceptions occur."""
        cleanup_called = []

        class MockResource:
            async def cleanup(self):
                cleanup_called.append(True)

        with pytest.raises(ValueError):
            async with ResourceContext() as ctx:
                resource = MockResource()
                ctx.resource_manager.register_resource(resource)
                raise ValueError("Test exception")

        assert len(cleanup_called) == 1

    @pytest.mark.asyncio
    async def test_multiple_resources_cleanup_order(self):
        """Test that multiple resources are cleaned up in proper order."""
        cleanup_order = []

        class MockResource:
            def __init__(self, name):
                self.name = name

            async def cleanup(self):
                cleanup_order.append(self.name)

        async with ResourceContext() as ctx:
            # Resources should be cleaned up in registration order
            for i in range(3):
                resource = MockResource(f"resource_{i}")
                ctx.resource_manager.register_resource(resource)

        assert cleanup_order == ["resource_0", "resource_1", "resource_2"]

    @pytest.mark.asyncio
    async def test_cleanup_continues_despite_errors(self):
        """Test that cleanup continues even if individual resources fail."""
        cleanup_called = []

        class FailingResource:
            def __init__(self, should_fail=False):
                self.should_fail = should_fail

            async def cleanup(self):
                cleanup_called.append(self.should_fail)
                if self.should_fail:
                    raise RuntimeError("Cleanup failed")

        async with ResourceContext() as ctx:
            ctx.resource_manager.register_resource(FailingResource(False))
            ctx.resource_manager.register_resource(
                FailingResource(True)
            )  # This will fail
            ctx.resource_manager.register_resource(FailingResource(False))

        # All three cleanup methods should have been called
        assert len(cleanup_called) == 3
        assert cleanup_called == [False, True, False]


class TestFileLifecycleIntegration:
    """Test file operations with comprehensive error handling."""

    @pytest.mark.asyncio
    async def test_atomic_file_write_success(self):
        """Test successful atomic file writing."""
        async with with_temp_file(suffix=".txt") as temp_file:
            target_path = temp_file.path.parent / "test_atomic.txt"

            async with atomic_file_write(target_path) as writer:
                writer.write("Hello, World!")

            assert target_path.exists()
            assert target_path.read_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_atomic_file_write_rollback_on_error(self):
        """Test that atomic file write rolls back on error."""
        async with with_temp_dir() as temp_dir:
            target_path = temp_dir.path / "test_rollback.txt"

            # Create initial file
            target_path.write_text("Original content")

            with pytest.raises(RuntimeError):
                async with atomic_file_write(target_path, backup=True) as writer:
                    writer.write("New content")
                    # Simulate error before commit
                    raise RuntimeError("Test error")

            # File should still have original content
            assert target_path.read_text() == "Original content"

    @pytest.mark.asyncio
    async def test_locked_file_resource_concurrent_access(self):
        """Test that file locking prevents concurrent access."""
        async with with_temp_file(suffix=".txt") as temp_file:
            temp_file.write_text("Initial content")

            # First process acquires lock
            async with locked_file_access(temp_file.path, timeout=1.0) as file1:
                file1.write("Process 1 content")

                # Second process should timeout
                with pytest.raises(TimeoutError):
                    async with locked_file_access(temp_file.path, timeout=0.5):
                        pass

            # After first process releases, second should succeed
            async with locked_file_access(temp_file.path) as file2:
                assert "Process 1 content" in file2.read()

    @pytest.mark.asyncio
    async def test_safe_directory_creation_cleanup(self):
        """Test safe directory creation with cleanup on error."""
        async with with_temp_dir() as temp_dir:
            nested_path = temp_dir.path / "level1" / "level2" / "level3"

            with pytest.raises(RuntimeError):
                async with safe_directory_creation(nested_path, cleanup_on_error=True):
                    assert nested_path.exists()
                    # Simulate error after creation
                    raise RuntimeError("Test error")

            # Directories should be cleaned up
            assert not nested_path.exists()
            assert not nested_path.parent.exists()

    @pytest.mark.asyncio
    async def test_batch_file_operations_atomic_commit(self):
        """Test batch file operations with atomic commit/rollback."""
        async with with_temp_dir() as temp_dir:
            file1 = temp_dir.path / "file1.txt"
            file2 = temp_dir.path / "file2.txt"
            file3 = temp_dir.path / "file3.txt"

            # Create initial files
            file1.write_text("Original 1")
            file2.write_text("Original 2")

            async with batch_file_operations() as batch:
                batch.add_write_operation(file1, "New content 1")
                batch.add_write_operation(file2, "New content 2")
                batch.add_write_operation(file3, "New content 3")
                # Batch commit happens automatically

            # All operations should have succeeded
            assert file1.read_text() == "New content 1"
            assert file2.read_text() == "New content 2"
            assert file3.read_text() == "New content 3"

    @pytest.mark.asyncio
    async def test_safe_file_operations_encoding_fallback(self):
        """Test safe file operations with encoding fallback."""
        async with with_temp_file() as temp_file:
            # Write binary data that might cause encoding issues
            temp_file.path.write_bytes(b"\xff\xfe\x00H\x00e\x00l\x00l\x00o")

            # Should succeed with fallback encoding
            content = await SafeFileOperations.safe_read_text(
                temp_file.path, encoding="utf-8", fallback_encodings=["utf-16"]
            )
            assert "Hello" in content


class TestWebSocketLifecycleIntegration:
    """Test WebSocket and network resource lifecycle."""

    @pytest.mark.asyncio
    async def test_network_resource_manager_cleanup(self):
        """Test network resource manager cleans up all resources."""
        cleanup_called = []

        class MockHTTPClient:
            def __init__(self):
                self.closed = False

            async def close(self):
                self.closed = True
                cleanup_called.append("http_client")

        async with NetworkResourceManager() as manager:
            # Create mock HTTP client
            session = MockHTTPClient()
            from crackerjack.core.websocket_lifecycle import ManagedHTTPClient

            ManagedHTTPClient(session, manager.resource_manager)

        assert len(cleanup_called) == 1
        assert "http_client" in cleanup_called

    @pytest.mark.asyncio
    async def test_managed_subprocess_cleanup(self):
        """Test managed subprocess cleanup."""
        async with NetworkResourceManager() as manager:
            # Create a long-running process
            process = subprocess.Popen(
                ["sleep", "10"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            managed_proc = manager.create_subprocess(process, timeout=5.0)
            await managed_proc.start_monitoring()

            assert managed_proc.is_running()

        # Process should be cleaned up after context exit
        await asyncio.sleep(0.1)  # Give cleanup time to complete
        assert not managed_proc.is_running()

    @pytest.mark.asyncio
    async def test_port_availability_check(self):
        """Test port availability checking."""
        async with NetworkResourceManager() as manager:
            # Should be available initially
            assert await manager.check_port_available(12345)

            # Start a simple server on the port
            server_process = await asyncio.create_subprocess_exec(
                "python",
                "-c",
                "import socket, time; s=socket.socket(); s.bind(('127.0.0.1', 12345)); s.listen(); time.sleep(5)",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            try:
                # Wait for server to start
                await asyncio.sleep(1)

                # Port should now be unavailable
                assert not await manager.check_port_available(12345)

            finally:
                server_process.terminate()
                await server_process.wait()


class TestMCPContextIntegration:
    """Test MCP server context resource management."""

    @pytest.mark.asyncio
    async def test_mcp_context_cleanup_on_shutdown(self):
        """Test MCP context properly cleans up resources on shutdown."""
        temp_dir = Path(tempfile.mkdtemp())

        config = MCPServerConfig(
            project_path=temp_dir, progress_dir=temp_dir / "progress", stdio_mode=True
        )

        context = MCPServerContext(config)

        try:
            await context.initialize()
            assert context._initialized

            # Context should have resource managers
            assert context.resource_manager is not None
            assert context.network_manager is not None

        finally:
            await context.shutdown()
            assert not context._initialized

        # Clean up temp directory
        import shutil

        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_mcp_context_websocket_process_cleanup(self):
        """Test MCP context WebSocket process cleanup."""
        temp_dir = Path(tempfile.mkdtemp())

        config = MCPServerConfig(project_path=temp_dir, stdio_mode=True)

        context = MCPServerContext(config)

        try:
            await context.initialize()

            # Mock process creation to avoid actually starting WebSocket server
            mock_process = Mock()
            mock_process.poll.return_value = None  # Running
            mock_process.pid = 12345

            context.websocket_server_process = mock_process

            # Shutdown should clean up the process
            await context.shutdown()

            # Process should have been terminated/killed
            assert mock_process.terminate.called or mock_process.kill.called

        finally:
            # Clean up temp directory
            import shutil

            shutil.rmtree(temp_dir)


class TestResourceLeakDetection:
    """Test resource leak detection functionality."""

    def test_leak_detector_tracks_resources(self):
        """Test that leak detector properly tracks resources."""
        detector = enable_leak_detection()

        # Track some resources
        detector.track_file("/tmp/test1.txt")
        detector.track_file("/tmp/test2.txt")
        detector.track_process(1234)
        detector.track_process(5678)

        report = detector.get_leak_report()

        assert len(report["open_files"]) == 2
        assert "/tmp/test1.txt" in report["open_files"]
        assert "/tmp/test2.txt" in report["open_files"]
        assert len(report["active_processes"]) == 2
        assert 1234 in report["active_processes"]
        assert 5678 in report["active_processes"]
        assert detector.has_potential_leaks()

        # Untrack resources
        detector.untrack_file("/tmp/test1.txt")
        detector.untrack_process(1234)

        report = detector.get_leak_report()
        assert len(report["open_files"]) == 1
        assert len(report["active_processes"]) == 1

    def test_leak_detector_clean_shutdown(self):
        """Test leak detector with clean resource shutdown."""
        detector = enable_leak_detection()

        # Track and then untrack all resources
        detector.track_file("/tmp/test.txt")
        detector.track_process(1234)

        detector.untrack_file("/tmp/test.txt")
        detector.untrack_process(1234)

        assert not detector.has_potential_leaks()

        final_report = detector.get_leak_report()
        assert len(final_report["open_files"]) == 0
        assert len(final_report["active_processes"]) == 0


class TestComprehensiveErrorScenarios:
    """Test error scenarios across all resource types."""

    @pytest.mark.asyncio
    async def test_cascading_failures_with_cleanup(self):
        """Test that cascading failures still trigger proper cleanup."""
        cleanup_calls = []

        class FailingResource:
            def __init__(self, name, should_fail_cleanup=False):
                self.name = name
                self.should_fail_cleanup = should_fail_cleanup

            async def cleanup(self):
                cleanup_calls.append(self.name)
                if self.should_fail_cleanup:
                    raise RuntimeError(f"Cleanup failed for {self.name}")

        async with ResourceContext() as ctx:
            # Add multiple resources, some that fail cleanup
            ctx.resource_manager.register_resource(FailingResource("good1"))
            ctx.resource_manager.register_resource(FailingResource("bad1", True))
            ctx.resource_manager.register_resource(FailingResource("good2"))
            ctx.resource_manager.register_resource(FailingResource("bad2", True))

        # All cleanup methods should have been attempted
        assert len(cleanup_calls) == 4
        assert "good1" in cleanup_calls
        assert "bad1" in cleanup_calls
        assert "good2" in cleanup_calls
        assert "bad2" in cleanup_calls

    @pytest.mark.asyncio
    async def test_timeout_scenarios_with_cleanup(self):
        """Test timeout scenarios trigger proper cleanup."""
        async with ResourceContext() as ctx:
            # Create a task that would run forever
            long_task = asyncio.create_task(asyncio.sleep(1000))
            ctx.managed_task(long_task, timeout=0.1)

            # Wait a bit to let timeout trigger
            await asyncio.sleep(0.2)

            # Task should be cancelled due to timeout
            assert long_task.cancelled()

    @pytest.mark.asyncio
    async def test_signal_interruption_cleanup(self):
        """Test that signal interruption triggers cleanup."""
        # This test simulates signal handling - in practice would be harder to test
        cleanup_completed = []

        async def signal_handler():
            cleanup_completed.append("signal_handled")

        # Mock signal scenario
        async with ResourceContext() as ctx:
            ctx.resource_manager.register_cleanup_callback(signal_handler)

        assert "signal_handled" in cleanup_completed

    @pytest.mark.asyncio
    async def test_memory_pressure_cleanup(self):
        """Test cleanup under memory pressure scenarios."""
        large_resources = []

        class MemoryResource:
            def __init__(self, size_mb=10):
                # Simulate memory allocation
                self.data = b"x" * (size_mb * 1024 * 1024)
                large_resources.append(self)

            async def cleanup(self):
                if self in large_resources:
                    large_resources.remove(self)
                self.data = None

        async with ResourceContext() as ctx:
            # Create several large resources
            for i in range(5):
                resource = MemoryResource()
                ctx.resource_manager.register_resource(resource)

        # All resources should be cleaned up
        assert len(large_resources) == 0


class TestGlobalResourceCleanup:
    """Test global resource cleanup functionality."""

    @pytest.mark.asyncio
    async def test_global_cleanup_on_exit(self):
        """Test that global cleanup works properly."""
        from crackerjack.core.resource_manager import _global_managers

        # Clear any existing global managers
        _global_managers.clear()

        cleanup_calls = []

        class MockManager:
            async def cleanup_all(self):
                cleanup_calls.append("manager_cleanup")

        # Register mock manager
        from crackerjack.core.resource_manager import register_global_resource_manager

        mock_manager = MockManager()
        register_global_resource_manager(mock_manager)

        # Trigger global cleanup
        await cleanup_all_global_resources()

        assert "manager_cleanup" in cleanup_calls

    @pytest.mark.asyncio
    async def test_network_global_cleanup(self):
        """Test global network resource cleanup."""
        cleanup_calls = []

        # Mock network managers for testing
        from crackerjack.core.websocket_lifecycle import _global_network_managers

        class MockNetworkManager:
            async def cleanup_all(self):
                cleanup_calls.append("network_cleanup")

        # Add mock manager
        mock_manager = MockNetworkManager()
        _global_network_managers.append(mock_manager)

        try:
            await cleanup_all_network_resources()
            assert "network_cleanup" in cleanup_calls

        finally:
            # Restore original state
            _global_network_managers.clear()


# Performance and stress tests
class TestResourceManagementPerformance:
    """Test resource management performance under load."""

    @pytest.mark.asyncio
    async def test_high_volume_resource_creation(self):
        """Test resource management with high volume of resources."""
        start_time = time.time()
        resource_count = 1000
        cleanup_count = 0

        class QuickResource:
            async def cleanup(self):
                nonlocal cleanup_count
                cleanup_count += 1

        async with ResourceContext() as ctx:
            # Create many resources quickly
            for i in range(resource_count):
                resource = QuickResource()
                ctx.resource_manager.register_resource(resource)

        duration = time.time() - start_time

        # Should complete reasonably quickly and clean up all resources
        assert duration < 5.0  # Should take less than 5 seconds
        assert cleanup_count == resource_count

    @pytest.mark.asyncio
    async def test_concurrent_resource_access(self):
        """Test concurrent access to resource manager."""
        async with ResourceContext() as ctx:
            concurrent_tasks = []
            results = []

            async def create_resources(task_id):
                for i in range(100):
                    resource = Mock()
                    resource.cleanup = AsyncMock()
                    ctx.resource_manager.register_resource(resource)
                results.append(task_id)

            # Create multiple concurrent tasks
            for i in range(10):
                task = asyncio.create_task(create_resources(i))
                concurrent_tasks.append(task)

            await asyncio.gather(*concurrent_tasks)

        # All tasks should have completed
        assert len(results) == 10
        assert sorted(results) == list(range(10))


if __name__ == "__main__":
    # Run a subset of tests for quick validation
    pytest.main(
        [
            __file__
            + "::TestResourceManagerIntegration::test_resource_context_cleanup_on_success",
            "-v",
        ]
    )
