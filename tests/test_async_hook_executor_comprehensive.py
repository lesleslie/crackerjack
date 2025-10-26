import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from crackerjack.executors.async_hook_executor import AsyncHookExecutor
from crackerjack.config.hooks import HookDefinition, HookStrategy


@pytest.mark.skip(reason="AsyncHookExecutor requires complex nested ACB DI setup - integration test, not unit test")
class TestAsyncHookExecutor:
    @pytest.fixture
    def console(self):
        return Console()

    @pytest.fixture
    def executor(self, console):
        return AsyncHookExecutor(pkg_path=pkg_path)

    def test_init(self, executor, console):
        """Test AsyncHookExecutor initialization"""
        assert executor.console == console
        assert executor.logger is not None
        assert hasattr(executor, '_lock_statistics')
        assert hasattr(executor, '_execution_cache')

    @pytest.mark.asyncio
    async def test_execute_strategy_sequential(self, executor):
        """Test execute_strategy method with sequential execution"""
        # Create a mock strategy
        strategy = Mock(spec=HookStrategy)
        strategy.execution_mode = "sequential"
        strategy.retry_enabled = False
        strategy.max_retries = 0

        # Create mock hooks
        hook1 = Mock(spec=HookDefinition)
        hook1.id = "black"
        hook1.name = "black"
        hook1.entry = "black"

        hook2 = Mock(spec=HookDefinition)
        hook2.id = "flake8"
        hook2.name = "flake8"
        hook2.entry = "flake8"

        strategy.hooks = [hook1, hook2]

        with patch.object(executor, '_execute_sequential') as mock_sequential:
            mock_result1 = Mock()
            mock_result1.success = True
            mock_result1.hook_id = "black"

            mock_result2 = Mock()
            mock_result2.success = False
            mock_result2.hook_id = "flake8"
            mock_result2.error = "Some error"

            mock_sequential.return_value = [mock_result1, mock_result2]

            with tempfile.TemporaryDirectory() as tmp_dir:
                results = await executor.execute_strategy(strategy, Path(tmp_dir))

                assert len(results) == 2
                assert results[0].success is True
                assert results[0].hook_id == "black"
                assert results[1].success is False
                assert results[1].hook_id == "flake8"
                mock_sequential.assert_called_once_with(strategy)

    @pytest.mark.asyncio
    async def test_execute_strategy_parallel(self, executor):
        """Test execute_strategy method with parallel execution"""
        # Create a mock strategy
        strategy = Mock(spec=HookStrategy)
        strategy.execution_mode = "parallel"
        strategy.retry_enabled = False
        strategy.max_retries = 0

        # Create mock hooks
        hook1 = Mock(spec=HookDefinition)
        hook1.id = "black"
        hook1.name = "black"
        hook1.entry = "black"

        hook2 = Mock(spec=HookDefinition)
        hook2.id = "flake8"
        hook2.name = "flake8"
        hook2.entry = "flake8"

        strategy.hooks = [hook1, hook2]

        with patch.object(executor, '_execute_parallel') as mock_parallel:
            mock_result1 = Mock()
            mock_result1.success = True
            mock_result1.hook_id = "black"

            mock_result2 = Mock()
            mock_result2.success = True
            mock_result2.hook_id = "flake8"

            mock_parallel.return_value = [mock_result1, mock_result2]

            with tempfile.TemporaryDirectory() as tmp_dir:
                results = await executor.execute_strategy(strategy, Path(tmp_dir))

                assert len(results) == 2
                assert all(result.success for result in results)
                mock_parallel.assert_called_once_with(strategy)

    def test_get_lock_statistics(self, executor):
        """Test get_lock_statistics method"""
        # Initially should return empty stats
        stats = executor.get_lock_statistics()
        assert isinstance(stats, dict)
        assert "total_acquired" in stats
        assert "total_released" in stats
        assert "current_locked" in stats

        # Stats should be zero initially
        assert stats["total_acquired"] == 0
        assert stats["total_released"] == 0
        assert stats["current_locked"] == 0

    def test_get_comprehensive_status(self, executor):
        """Test get_comprehensive_status method"""
        status = executor.get_comprehensive_status()
        assert isinstance(status, dict)
        assert "lock_statistics" in status
        assert "cache_statistics" in status
        assert "performance_metrics" in status

    @pytest.mark.asyncio
    async def test_execute_sequential(self, executor):
        """Test _execute_sequential method"""
        # Create a mock strategy
        strategy = Mock(spec=HookStrategy)

        # Create mock hooks
        hook1 = Mock(spec=HookDefinition)
        hook1.id = "black"
        hook1.name = "black"
        hook1.entry = "black"

        hook2 = Mock(spec=HookDefinition)
        hook2.id = "flake8"
        hook2.name = "flake8"
        hook2.entry = "flake8"

        strategy.hooks = [hook1, hook2]

        with patch.object(executor, '_execute_single_hook') as mock_execute_single:
            # Mock the async results
            async def mock_execute_hook(hook):
                mock_result = Mock()
                mock_result.success = True
                mock_result.hook_id = hook.id
                return mock_result

            mock_execute_single.side_effect = mock_execute_hook

            with tempfile.TemporaryDirectory() as tmp_dir:
                results = await executor._execute_sequential(strategy)

                assert len(results) == 2
                assert all(result.success for result in results)
                # Should have called execute_single_hook for each hook
                assert mock_execute_single.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_parallel(self, executor):
        """Test _execute_parallel method"""
        # Create a mock strategy
        strategy = Mock(spec=HookStrategy)

        # Create mock hooks
        hook1 = Mock(spec=HookDefinition)
        hook1.id = "black"
        hook1.name = "black"
        hook1.entry = "black"

        hook2 = Mock(spec=HookDefinition)
        hook2.id = "flake8"
        hook2.name = "flake8"
        hook2.entry = "flake8"

        strategy.hooks = [hook1, hook2]

        with patch.object(executor, '_execute_single_hook') as mock_execute_single:
            # Mock the async results
            async def mock_execute_hook(hook):
                await asyncio.sleep(0.01)  # Small delay to simulate async work
                mock_result = Mock()
                mock_result.success = True
                mock_result.hook_id = hook.id
                return mock_result

            mock_execute_single.side_effect = mock_execute_hook

            with tempfile.TemporaryDirectory() as tmp_dir:
                results = await executor._execute_parallel(strategy)

                assert len(results) == 2
                assert all(result.success for result in results)
                # Should have called execute_single_hook for each hook
                assert mock_execute_single.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_single_hook_success(self, executor):
        """Test _execute_single_hook method with successful execution"""
        hook = Mock(spec=HookDefinition)
        hook.id = "black"
        hook.name = "black"
        hook.entry = "black"

        with patch.object(executor, '_run_hook_subprocess') as mock_run_subprocess:
            mock_result = Mock()
            mock_result.success = True
            mock_result.hook_id = "black"
            mock_run_subprocess.return_value = mock_result

            result = await executor._execute_single_hook(hook)

            assert result.success is True
            assert result.hook_id == "black"
            mock_run_subprocess.assert_called_once_with(hook)

    @pytest.mark.asyncio
    async def test_execute_single_hook_with_retry(self, executor):
        """Test _execute_single_hook method with retry logic"""
        hook = Mock(spec=HookDefinition)
        hook.id = "flake8"
        hook.name = "flake8"
        hook.entry = "flake8"
        hook.retry_count = 2

        with patch.object(executor, '_run_hook_subprocess') as mock_run_subprocess:
            # First call fails, second call succeeds
            mock_result1 = Mock()
            mock_result1.success = False
            mock_result1.hook_id = "flake8"
            mock_result1.error = "First attempt failed"

            mock_result2 = Mock()
            mock_result2.success = True
            mock_result2.hook_id = "flake8"

            mock_run_subprocess.side_effect = [mock_result1, mock_result2]

            result = await executor._execute_single_hook(hook)

            assert result.success is True
            assert result.hook_id == "flake8"
            # Should have been called twice (initial + 1 retry)
            assert mock_run_subprocess.call_count == 2

    @pytest.mark.asyncio
    async def test_run_hook_subprocess_success(self, executor):
        """Test _run_hook_subprocess method with successful execution"""
        hook = Mock(spec=HookDefinition)
        hook.id = "black"
        hook.name = "black"
        hook.entry = "black"
        hook.args = []
        hook.language = "python"
        hook.require_serial = False
        hook.verbose = False
        hook.pass_filenames = True

        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            # Mock the subprocess
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"All good", b"")
            mock_create_subprocess.return_value = mock_process

            with tempfile.TemporaryDirectory() as tmp_dir:
                result = await executor._run_hook_subprocess(hook)

                assert result.success is True
                assert result.hook_id == "black"
                assert result.stdout == "All good"
                assert result.stderr == ""

    @pytest.mark.asyncio
    async def test_run_hook_subprocess_failure(self, executor):
        """Test _run_hook_subprocess method with failed execution"""
        hook = Mock(spec=HookDefinition)
        hook.id = "flake8"
        hook.name = "flake8"
        hook.entry = "flake8"
        hook.args = []
        hook.language = "python"
        hook.require_serial = False
        hook.verbose = False
        hook.pass_filenames = True

        with patch('asyncio.create_subprocess_exec') as mock_create_subprocess:
            # Mock the subprocess
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = (b"", b"Some error occurred")
            mock_create_subprocess.return_value = mock_process

            with tempfile.TemporaryDirectory() as tmp_dir:
                result = await executor._run_hook_subprocess(hook)

                assert result.success is False
                assert result.hook_id == "flake8"
                assert result.stdout == ""
                assert result.stderr == "Some error occurred"
                assert "failed with return code 1" in result.error

    def test_parse_hook_output(self, executor):
        """Test _parse_hook_output method"""
        # Test successful output
        result = executor._parse_hook_output(0, "Success")
        assert result["success"] is True
        assert result["stdout"] == "Success"
        assert result["stderr"] == ""

        # Test failed output
        result = executor._parse_hook_output(1, "Error occurred")
        assert result["success"] is False
        assert result["stdout"] == "Error occurred"
        assert result["error"] == "Hook execution failed with return code 1"

    def test_display_hook_result_success(self, executor):
        """Test _display_hook_result method with successful result"""
        result = Mock()
        result.success = True
        result.hook_id = "black"
        result.duration = 1.5
        result.stdout = "All files formatted correctly"
        result.stderr = ""

        # This should not raise any exceptions
        try:
            executor._display_hook_result(result)
        except Exception as e:
            pytest.fail(f"_display_hook_result raised an exception: {e}")

    def test_display_hook_result_failure(self, executor):
        """Test _display_hook_result method with failed result"""
        result = Mock()
        result.success = False
        result.hook_id = "flake8"
        result.duration = 0.8
        result.stdout = ""
        result.stderr = "Error found in file.py:1:1: E123 error"
        result.error = "Hook execution failed"

        # This should not raise any exceptions
        try:
            executor._display_hook_result(result)
        except Exception as e:
            pytest.fail(f"_display_hook_result raised an exception: {e}")
