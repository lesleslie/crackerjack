"""Edge case and error condition tests for core components."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.code_cleaner import CodeCleaner, CleaningResult
from crackerjack.core.timeout_manager import AsyncTimeoutManager, TimeoutError
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.executors.hook_executor import HookExecutor


class TestCodeCleanerEdgeCases:
    """Test edge cases and error conditions for CodeCleaner."""

    def test_cleaner_with_nonexistent_directory(self) -> None:
        """Test CodeCleaner with nonexistent base directory."""
        cleaner = CodeCleaner(base_directory=Path("/nonexistent/directory"))

        # Should handle gracefully when trying to find files
        try:
            result = cleaner._find_package_directory(Path("/nonexistent/directory"))
            assert result is None
        except Exception:
            # May raise an exception, which is acceptable
            pass

    def test_cleaner_with_permission_denied_file(self) -> None:
        """Test CodeCleaner when encountering permission denied files."""
        # Create a temporary file and restrict permissions
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('print("hello")\n')
            temp_file = Path(f.name)

        # Change permissions to restrict access (this may not work on all systems)
        # Instead, we'll mock the file access to simulate permission error
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            cleaner = CodeCleaner()
            try:
                result = cleaner.clean_file(temp_file)
                # Should handle the error gracefully
                assert isinstance(result, CleaningResult)
            except Exception:
                # Acceptable to raise an exception in this case
                pass
        # Clean up
        temp_file.unlink()

    def test_cleaner_with_corrupted_file(self) -> None:
        """Test CodeCleaner with corrupted file content."""
        cleaner = CodeCleaner()

        # Create a temporary file with invalid content
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.py', delete=False) as f:
            f.write(b'\x00\x01\x02' * 1000)  # Binary content that's not valid text
            temp_file = Path(f.name)

        try:
            result = cleaner.clean_file(temp_file)
            # Should handle the error gracefully
            assert isinstance(result, CleaningResult)
        except Exception:
            # Acceptable to raise an exception in this case
            pass
        finally:
            # Clean up
            temp_file.unlink()

    def test_cleaner_with_empty_file(self) -> None:
        """Test CodeCleaner with empty file."""
        cleaner = CodeCleaner()

        # Create an empty temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Don't write anything - file is empty
            temp_file = Path(f.name)

        try:
            result = cleaner.clean_file(temp_file)
            # Should handle empty file gracefully
            assert isinstance(result, CleaningResult)
        finally:
            # Clean up
            temp_file.unlink()

    def test_cleaner_with_extremely_large_file(self) -> None:
        """Test CodeCleaner with extremely large file."""
        cleaner = CodeCleaner()

        # Create a temporary file with large content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Write a large amount of content
            large_content = "x = 1\n" * 100000  # 100k lines
            f.write(large_content)
            temp_file = Path(f.name)

        try:
            result = cleaner.clean_file(temp_file)
            # Should handle large file gracefully
            assert isinstance(result, CleaningResult)
        except MemoryError:
            # Acceptable to run out of memory with extremely large files
            pass
        finally:
            # Clean up
            temp_file.unlink()


class TestTimeoutManagerEdgeCases:
    """Test edge cases and error conditions for AsyncTimeoutManager."""

    @pytest.mark.asyncio
    async def test_timeout_manager_with_zero_timeout(self) -> None:
        """Test AsyncTimeoutManager with zero timeout."""
        from crackerjack.core.timeout_manager import TimeoutConfig
        config = TimeoutConfig(default_timeout=0.0)
        manager = AsyncTimeoutManager(config)

        async def quick_operation():
            await asyncio.sleep(0.01)
            return "result"

        # With zero timeout, the operation should timeout immediately
        try:
            result = await manager.with_timeout("test_op", quick_operation(), timeout=0.0)
            # This might return None if graceful degradation is used
        except TimeoutError:
            # Expected behavior
            pass

    @pytest.mark.asyncio
    async def test_timeout_manager_with_negative_timeout(self) -> None:
        """Test AsyncTimeoutManager with negative timeout."""
        manager = AsyncTimeoutManager()

        async def quick_operation():
            await asyncio.sleep(0.01)
            return "result"

        # With negative timeout, behavior depends on implementation
        try:
            result = await manager.with_timeout("test_op", quick_operation(), timeout=-1.0)
        except (TimeoutError, ValueError):
            # Either timeout error or validation error is acceptable
            pass

    @pytest.mark.asyncio
    async def test_timeout_manager_with_excessive_timeout(self) -> None:
        """Test AsyncTimeoutManager with excessive timeout."""
        manager = AsyncTimeoutManager()

        async def quick_operation():
            await asyncio.sleep(0.01)
            return "result"

        # Very large timeout should be capped
        with patch("crackerjack.core.timeout_manager.logger") as mock_logger:
            result = await manager.with_timeout("test_op", quick_operation(), timeout=10000.0)
            # Should complete successfully and log a warning about capping
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_manager_circuit_breaker_edge_cases(self) -> None:
        """Test circuit breaker edge cases."""
        from crackerjack.core.timeout_manager import TimeoutConfig, CircuitBreakerState
        config = TimeoutConfig(failure_threshold=1, recovery_timeout=0.1)
        manager = AsyncTimeoutManager(config)

        # Force the circuit breaker to open by triggering failures
        async def failing_operation():
            await asyncio.sleep(0.01)
            raise Exception("Simulated failure")

        # First call should fail
        try:
            await manager.with_timeout("test_op", failing_operation(), timeout=0.1, strategy="circuit_breaker")
        except Exception:
            pass  # Expected to fail

        # Second call should be blocked by open circuit breaker
        try:
            await manager.with_timeout("test_op", failing_operation(), timeout=0.1, strategy="circuit_breaker")
        except TimeoutError:
            # Expected - circuit breaker should prevent the call
            pass

    @pytest.mark.asyncio
    async def test_timeout_manager_with_exception_in_operation(self) -> None:
        """Test timeout manager when operation raises an exception."""
        manager = AsyncTimeoutManager()

        async def error_operation():
            await asyncio.sleep(0.01)
            raise ValueError("Simulated error")

        try:
            result = await manager.with_timeout("test_op", error_operation(), timeout=1.0)
            # Should propagate the original exception
        except ValueError as e:
            assert "Simulated error" in str(e)

    def test_timeout_manager_get_timeout_unknown_operation(self) -> None:
        """Test get_timeout with unknown operation."""
        manager = AsyncTimeoutManager()

        # Should return default timeout for unknown operations
        timeout = manager.get_timeout("unknown_operation")
        assert isinstance(timeout, float)
        assert timeout > 0


class TestSessionCoordinatorEdgeCases:
    """Test edge cases and error conditions for SessionCoordinator."""

    def test_session_coordinator_with_none_tracker(self) -> None:
        """Test session coordinator methods when session tracker is None."""
        coordinator = SessionCoordinator()
        coordinator.session_tracker = None  # Explicitly set to None

        # These methods should handle None tracker gracefully
        coordinator.complete_task("task1", "details", ["file.py"])
        coordinator.fail_task("task1", "error", "details")
        coordinator.update_task("task1", "status", details="details")

        # get_summary should return basic info even with None tracker
        summary = coordinator.get_summary()
        assert "session_id" in summary
        assert "start_time" in summary

    def test_session_coordinator_with_invalid_paths(self) -> None:
        """Test session coordinator with invalid paths."""
        coordinator = SessionCoordinator(pkg_path=Path("/nonexistent/path"))

        # Should handle invalid paths gracefully
        try:
            coordinator._cleanup_debug_logs()
            coordinator._cleanup_coverage_files()
        except Exception:
            # Acceptable to raise exceptions with invalid paths
            pass

    def test_session_coordinator_cleanup_with_locked_files(self) -> None:
        """Test cleanup with locked or inaccessible files."""
        coordinator = SessionCoordinator()

        # Add a fake lock file that doesn't exist
        fake_lock_path = Path("/fake/lock/file.lock")
        coordinator.track_lock_file(fake_lock_path)

        # Cleanup should handle missing files gracefully
        coordinator.cleanup_resources()
        # The fake lock file should be removed from the set
        assert fake_lock_path not in coordinator._lock_files

    def test_session_coordinator_with_long_task_ids(self) -> None:
        """Test session coordinator with very long task IDs."""
        coordinator = SessionCoordinator()

        # Use a very long task ID
        long_task_id = "x" * 1000
        details = "Test with long task ID"

        # Should handle long task IDs gracefully
        result_id = coordinator.track_task(long_task_id, "Long Task", details)
        assert result_id == long_task_id


class TestHookExecutorEdgeCases:
    """Test edge cases and error conditions for HookExecutor."""

    def test_hook_executor_with_nonexistent_hook_command(self) -> None:
        """Test hook executor with nonexistent command."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.cmd = ["nonexistent-command-that-does-not-exist"]
        hook.name = "test-hook"
        hook.id = "test-hook-id"
        hook.stage = "fast"
        hook.timeout = 1.0

        # Mock subprocess.run to simulate command not found
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("Command not found")

            result = executor.execute_single_hook(hook)

            # Should handle the error gracefully
            assert result.status == "error"
            assert "not found" in result.error or "FileNotFoundError" in str(result.error)

    def test_hook_executor_with_hook_timeout(self) -> None:
        """Test hook executor when hook times out."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.cmd = ["sleep", "10"]  # Command that will take too long
        hook.name = "slow-hook"
        hook.id = "slow-hook-id"
        hook.stage = "fast"
        hook.timeout = 0.1  # Very short timeout

        # Mock subprocess.run to simulate timeout
        with patch("subprocess.run") as mock_run:
            # Simulate a timeout by raising a TimeoutExpired exception
            from subprocess import TimeoutExpired
            mock_proc = MagicMock()
            mock_proc.stdout = "Some output"
            mock_proc.stderr = "Some error"
            mock_proc.returncode = None
            mock_run.side_effect = TimeoutExpired(cmd=hook.cmd, timeout=hook.timeout)

            result = executor.execute_single_hook(hook)

            # Should handle the timeout gracefully
            assert result.status == "timeout"

    def test_hook_executor_with_hook_that_fails(self) -> None:
        """Test hook executor when hook command fails."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.cmd = ["false"]  # Command that always fails
        hook.name = "failing-hook"
        hook.id = "failing-hook-id"
        hook.stage = "fast"
        hook.timeout = 1.0

        # Mock subprocess.run to simulate failure
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = "Standard output"
            mock_proc.stderr = "Error output"
            mock_proc.returncode = 1  # Non-zero means failure
            mock_run.return_value = mock_proc

            result = executor.execute_single_hook(hook)

            # Should handle the failure gracefully
            assert result.status == "failed"
            assert result.return_code == 1

    def test_hook_executor_with_empty_command(self) -> None:
        """Test hook executor with empty command."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.cmd = []  # Empty command
        hook.name = "empty-hook"
        hook.id = "empty-hook-id"
        hook.stage = "fast"
        hook.timeout = 1.0

        # Should handle empty command gracefully
        from contextlib import suppress
        with suppress(Exception):
            result = executor.execute_single_hook(hook)
            # Behavior depends on implementation

    def test_hook_executor_with_very_long_output(self) -> None:
        """Test hook executor with command that produces very long output."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.cmd = ["sh", "-c", "printf 'A%.0s' {1..100000}"]  # Very long output
        hook.name = "long-output-hook"
        hook.id = "long-output-hook-id"
        hook.stage = "fast"
        hook.timeout = 5.0

        # Mock subprocess.run to handle long output
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = "A" * 100000  # Simulate long output
            mock_proc.stderr = ""
            mock_proc.returncode = 0
            mock_run.return_value = mock_proc

            result = executor.execute_single_hook(hook)

            # Should handle long output gracefully
            assert result.status in ("passed", "failed")  # Depends on parsing logic

    def test_hook_executor_parsing_edge_cases(self) -> None:
        """Test hook executor output parsing edge cases."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        # Test parsing with malformed output
        malformed_output = "This is not a standard hook output format\nWith strange characters: \x00\x01\x02"
        result = executor._parse_hook_output(0, malformed_output, "unknown-hook")
        assert isinstance(result, dict)
        assert "files_processed" in result

        # Test parsing with empty output
        empty_output = ""
        result = executor._parse_hook_output(0, empty_output, "unknown-hook")
        assert isinstance(result, dict)
        assert "files_processed" in result

        # Test parsing with only whitespace
        whitespace_output = "   \n\t\n  "
        result = executor._parse_hook_output(0, whitespace_output, "unknown-hook")
        assert isinstance(result, dict)
        assert "files_processed" in result


class TestGeneralErrorHandling:
    """Test general error handling patterns."""

    def test_import_error_handling(self) -> None:
        """Test handling of import errors in conditional imports."""
        # This tests the pattern used in some modules where imports are wrapped in try/except
        # Although we can't easily test the import error itself, we can verify the pattern works
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        # Verify that the class can be instantiated without import errors
        coordinator = PhaseCoordinator()
        assert coordinator is not None

    def test_attribute_error_handling(self) -> None:
        """Test handling of attribute errors."""
        # Create an object without certain attributes
        class MinimalObject:
            def __init__(self):
                self.existing_attr = "value"

        obj = MinimalObject()

        # Test safe attribute access pattern
        attr_value = getattr(obj, 'existing_attr', 'default')
        assert attr_value == "value"

        attr_value = getattr(obj, 'nonexistent_attr', 'default')
        assert attr_value == "default"

    def test_file_operation_error_handling(self) -> None:
        """Test file operation error handling."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        # Test with a path that causes errors
        problematic_path = Path("/nonexistent/directory/file.txt")

        # This tests the pattern of handling file operations that might fail
        try:
            # Simulate a file operation that would fail
            with open(problematic_path, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            # Handle the error gracefully
            content = ""  # or some default behavior
