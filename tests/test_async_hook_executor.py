"""Comprehensive tests for async_hook_executor.py module.

Tests the AsyncHookExecutor class that handles async hook execution.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from crackerjack.config.hooks import (
    HookDefinition,
    HookStage,
    HookStrategy,
    RetryPolicy,
)
from crackerjack.executors.async_hook_executor import (
    AsyncHookExecutor,
    AsyncHookExecutionResult,
)
from crackerjack.models.task import HookResult


class TestAsyncHookExecutionResult:
    """Tests for AsyncHookExecutionResult dataclass."""

    def test_result_properties(self) -> None:
        """Test basic result properties."""
        results = [
            HookResult(
                id="1",
                name="hook1",
                status="passed",
                duration=1.0,
                issues_found=[],
                stage="fast",
            ),
            HookResult(
                id="2",
                name="hook2",
                status="failed",
                duration=2.0,
                issues_found=["error"],
                stage="fast",
            ),
            HookResult(
                id="3",
                name="hook3",
                status="timeout",
                duration=3.0,
                issues_found=["timeout"],
                stage="fast",
            ),
        ]

        result = AsyncHookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=6.0,
            success=False,
            cache_hits=5,
            cache_misses=3,
            performance_gain=25.0,
        )

        assert result.passed_count == 1
        assert result.failed_count == 1
        assert result.cache_hit_rate == pytest.approx(62.5, rel=0.1)

    def test_cache_hit_rate_no_requests(self) -> None:
        """Test cache hit rate with no requests."""
        result = AsyncHookExecutionResult(
            strategy_name="test",
            results=[],
            total_duration=1.0,
            success=True,
            cache_hits=0,
            cache_misses=0,
        )

        assert result.cache_hit_rate == 0.0

    def test_performance_summary(self) -> None:
        """Test performance summary property."""
        results = [
            HookResult(
                id="1",
                name="hook1",
                status="passed",
                duration=1.0,
                issues_found=[],
                stage="fast",
            ),
        ]

        result = AsyncHookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=1.0,
            success=True,
            performance_gain=10.0,
        )

        summary = result.performance_summary
        assert summary["total_hooks"] == 1
        assert summary["passed"] == 1
        assert summary["failed"] == 0
        assert summary["performance_gain_percent"] == 10.0


class TestAsyncHookExecutor:
    """Tests for the AsyncHookExecutor class."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        """Create a mock console."""
        console = MagicMock()
        console.print = MagicMock()
        return console

    @pytest.fixture
    def mock_lock_manager(self) -> MagicMock:
        """Create a mock lock manager."""
        lock_mgr = MagicMock()
        lock_mgr.requires_lock.return_value = False
        lock_mgr.acquire_hook_lock = MagicMock()
        lock_mgr.get_lock_stats.return_value = {}
        return lock_mgr

    @pytest.fixture
    def executor(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
        mock_lock_manager: MagicMock,
    ) -> AsyncHookExecutor:
        """Create an AsyncHookExecutor instance for testing."""
        logger = logging.getLogger(__name__)
        return AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            max_concurrent=4,
            timeout=300,
            quiet=False,
            logger=logger,
            hook_lock_manager=mock_lock_manager,
        )

    def test_init(self, mock_console: MagicMock, tmp_path: Path) -> None:
        """Test AsyncHookExecutor initialization."""
        logger = logging.getLogger(__name__)
        executor = AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            max_concurrent=8,
            timeout=120,
            quiet=True,
            logger=logger,
        )

        assert executor.console is mock_console
        assert executor.pkg_path == tmp_path
        assert executor.max_concurrent == 8
        assert executor.timeout == 120
        assert executor.quiet is True

    def test_get_lock_statistics(self, executor: AsyncHookExecutor) -> None:
        """Test get_lock_statistics delegates to lock manager."""
        expected_stats = {"hook1": {"acquisitions": 5}}
        executor.hook_lock_manager.get_lock_stats.return_value = expected_stats

        stats = executor.get_lock_statistics()

        assert stats == expected_stats
        executor.hook_lock_manager.get_lock_stats.assert_called_once()

    def test_get_comprehensive_status(self, executor: AsyncHookExecutor) -> None:
        """Test get_comprehensive_status returns executor and lock info."""
        executor.hook_lock_manager.get_lock_stats.return_value = {}

        status = executor.get_comprehensive_status()

        assert "executor_config" in status
        assert "lock_manager_status" in status
        assert status["executor_config"]["max_concurrent"] == 4

    def test_semaphore_initialization(self, mock_console: MagicMock, tmp_path: Path) -> None:
        """Test semaphore is properly initialized."""
        logger = logging.getLogger(__name__)
        executor = AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            max_concurrent=3,
        )

        assert executor._semaphore._value == 3


class TestAsyncHookExecutorExecution:
    """Tests for AsyncHookExecutor execution methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> AsyncHookExecutor:
        """Create executor for execution tests."""
        mock_console = MagicMock()
        mock_lock_manager = MagicMock()
        mock_lock_manager.requires_lock.return_value = False
        mock_lock_manager.acquire_hook_lock = MagicMock()

        logger = logging.getLogger(__name__)
        return AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            max_concurrent=4,
            timeout=60,
            hook_lock_manager=mock_lock_manager,
        )

    @pytest.mark.asyncio
    async def test_execute_sequential(self, executor: AsyncHookExecutor) -> None:
        """Test sequential hook execution."""
        hooks = [
            HookDefinition(name="hook1", command=["echo", "1"], timeout=5),
            HookDefinition(name="hook2", command=["echo", "2"], timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=False)

        with patch.object(executor, "_execute_single_hook") as mock_exec:
            mock_exec.return_value = HookResult(
                id="1",
                name="hook1",
                status="passed",
                duration=0.1,
            )

            results = await executor._execute_sequential(strategy)

            assert len(results) == 2
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_parallel(self, executor: AsyncHookExecutor) -> None:
        """Test parallel hook execution."""
        hooks = [
            HookDefinition(name="hook1", command=["echo", "1"], timeout=5, is_formatting=False),
            HookDefinition(name="hook2", command=["echo", "2"], timeout=5, is_formatting=False),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True)

        with patch.object(executor, "_execute_single_hook") as mock_exec:
            mock_exec.return_value = HookResult(
                id="1",
                name="hook1",
                status="passed",
                duration=0.1,
            )

            results = await executor._execute_parallel(strategy)

            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_execute_strategy_parallel(self, executor: AsyncHookExecutor) -> None:
        """Test execute_strategy with parallel=True and multiple hooks."""
        hooks = [
            HookDefinition(name="hook1", command=["echo", "test"], timeout=5),
            HookDefinition(name="hook2", command=["echo", "test"], timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True)

        with patch.object(executor, "_execute_parallel") as mock_parallel:
            mock_parallel.return_value = [
                HookResult(id="1", name="hook1", status="passed", duration=0.1),
                HookResult(id="2", name="hook2", status="passed", duration=0.1),
            ]

            result = await executor.execute_strategy(strategy)

            assert result.strategy_name == "test"
            mock_parallel.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_strategy_sequential(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test execute_strategy with parallel=False."""
        hook = HookDefinition(name="test-hook", command=["echo", "test"], timeout=5)
        strategy = HookStrategy(name="test", hooks=[hook], parallel=False)

        with patch.object(executor, "_execute_sequential") as mock_seq:
            mock_seq.return_value = [
                HookResult(id="1", name="test-hook", status="passed", duration=0.1),
            ]

            result = await executor.execute_strategy(strategy)

            assert result.strategy_name == "test"
            mock_seq.assert_called_once()


class TestAsyncHookExecutorLocking:
    """Tests for AsyncHookExecutor lock management."""

    @pytest.mark.asyncio
    async def test_execute_single_hook_requires_lock(
        self,
        tmp_path: Path,
    ) -> None:
        """Test hook execution when lock is required."""
        mock_lock_manager = MagicMock()
        mock_lock_manager.requires_lock.return_value = True

        lock_context = MagicMock()
        lock_context.__aenter__ = AsyncMock(return_value=None)
        lock_context.__aexit__ = AsyncMock(return_value=None)
        mock_lock_manager.acquire_hook_lock.return_value = lock_context

        mock_console = MagicMock()
        logger = logging.getLogger(__name__)

        executor = AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            hook_lock_manager=mock_lock_manager,
        )

        hook = HookDefinition(name="complexipy", command=["echo", "test"], timeout=5)

        with patch.object(executor, "_run_hook_subprocess") as mock_run:
            mock_run.return_value = HookResult(
                id="complexipy",
                name="complexipy",
                status="passed",
                duration=0.1,
            )

            await executor._execute_single_hook(hook)

            mock_lock_manager.acquire_hook_lock.assert_called_once_with("complexipy")


class TestAsyncHookExecutorSubprocess:
    """Tests for AsyncHookExecutor subprocess handling."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> AsyncHookExecutor:
        """Create executor for subprocess tests."""
        mock_console = MagicMock()
        mock_lock_manager = MagicMock()
        mock_lock_manager.requires_lock.return_value = False

        logger = logging.getLogger(__name__)
        return AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            max_concurrent=4,
            timeout=60,
            hook_lock_manager=mock_lock_manager,
        )

    @pytest.mark.asyncio
    async def test_execute_process_with_timeout_success(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test successful process execution."""
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"output", b""))
        mock_process.returncode = 0

        result = await executor._execute_process_with_timeout(
            mock_process,
            MagicMock(name="test-hook"),
            5,
            time.time(),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_process_with_timeout_expired(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test process timeout handling."""
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_code=124)

        hook = HookDefinition(name="test-hook", command=[], timeout=1)

        result = await executor._execute_process_with_timeout(
            mock_process,
            hook,
            1,
            time.time(),
        )

        assert result is not None
        assert result.status == "timeout"
        assert result.is_timeout is True

    @pytest.mark.asyncio
    async def test_build_success_result(self, executor: AsyncHookExecutor) -> None:
        """Test building success result from process."""
        mock_process = MagicMock()
        mock_process.returncode = 0

        executor._last_stdout = b"All checks passed"
        executor._last_stderr = b""

        hook = HookDefinition(name="test-hook", command=[], timeout=5, stage=HookStage.FAST)

        result = await executor._build_success_result(mock_process, hook, 1.0)

        assert result.status == "passed"
        assert result.name == "test-hook"

    @pytest.mark.asyncio
    async def test_build_success_result_with_errors(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test building result when hook has errors."""
        mock_process = MagicMock()
        mock_process.returncode = 1

        executor._last_stdout = b"Error found"
        executor._last_stderr = b""

        hook = HookDefinition(name="test-hook", command=[], timeout=5, stage=HookStage.FAST)

        result = await executor._build_success_result(mock_process, hook, 1.0)

        assert result.status == "failed"
        assert len(result.issues_found) > 0


class TestAsyncHookExecutorRetry:
    """Tests for AsyncHookExecutor retry logic."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> AsyncHookExecutor:
        """Create executor for retry tests."""
        mock_console = MagicMock()
        mock_lock_manager = MagicMock()
        mock_lock_manager.requires_lock.return_value = False

        logger = logging.getLogger(__name__)
        return AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            hook_lock_manager=mock_lock_manager,
        )

    @pytest.mark.asyncio
    async def test_handle_retries_none(self, executor: AsyncHookExecutor) -> None:
        """Test no retry when retry policy is NONE."""
        strategy = HookStrategy(
            name="test",
            hooks=[],
            retry_policy=RetryPolicy.NONE,
        )
        results = []

        updated = await executor._handle_retries(strategy, results)

        assert updated == results

    @pytest.mark.asyncio
    async def test_handle_retries_formatting_only(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test retry with FORMATTING_ONLY policy."""
        hooks = [
            HookDefinition(name="format1", command=[], is_formatting=True, timeout=5),
        ]
        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            retry_policy=RetryPolicy.FORMATTING_ONLY,
        )
        results = [
            HookResult(id="1", name="format1", status="failed", duration=1.0),
        ]

        with patch.object(executor, "_execute_single_hook") as mock_exec:
            mock_exec.return_value = HookResult(
                id="1",
                name="format1",
                status="passed",
                duration=1.0,
            )

            updated = await executor._handle_retries(strategy, results)

            mock_exec.assert_called()

    @pytest.mark.asyncio
    async def test_handle_retries_all_hooks(self, executor: AsyncHookExecutor) -> None:
        """Test retry with ALL_HOOKS policy."""
        hooks = [
            HookDefinition(name="hook1", command=[], timeout=5),
        ]
        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            retry_policy=RetryPolicy.ALL_HOOKS,
        )
        results = [
            HookResult(id="1", name="hook1", status="failed", duration=1.0),
        ]

        with patch.object(executor, "_execute_single_hook") as mock_exec:
            mock_exec.return_value = HookResult(
                id="1",
                name="hook1",
                status="passed",
                duration=1.0,
            )

            updated = await executor._handle_retries(strategy, results)

            mock_exec.assert_called()


class TestAsyncHookExecutorOutputParsing:
    """Tests for AsyncHookExecutor output parsing."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> AsyncHookExecutor:
        """Create executor for parsing tests."""
        mock_console = MagicMock()
        logger = logging.getLogger(__name__)
        return AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
        )

    def test_parse_semgrep_text_patterns(self, executor: AsyncHookExecutor) -> None:
        """Test semgrep text pattern parsing."""
        output = "found 5 issues in 3 files"

        count = executor._parse_semgrep_text_patterns(output)

        assert count == 3

    def test_parse_semgrep_text_patterns_no_issues(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test semgrep text pattern with no issues."""
        output = "found no issues"

        count = executor._parse_semgrep_text_patterns(output)

        assert count == 0

    def test_parse_semgrep_json(self, executor: AsyncHookExecutor) -> None:
        """Test semgrep JSON parsing."""
        output = '{"results": [{"path": "a.py"}, {"path": "b.py"}]}'

        count = executor._parse_semgrep_output_async(output)

        assert count == 2

    def test_parse_large_files_all_under_limit(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test large files check when all files are under limit."""
        output = "All files are under size limit"
        returncode = 0

        count = executor._parse_large_files_output(output, returncode)

        assert count == 0

    def test_extract_file_count_from_output(self, executor: AsyncHookExecutor) -> None:
        """Test file count extraction from output."""
        output = "Checked 10 files"

        count = executor._extract_file_count_from_output(output)

        assert count == 10

    def test_extract_file_count_multiple_patterns(self, executor: AsyncHookExecutor) -> None:
        """Test file count extraction with multiple patterns."""
        output = "Found 5 issues in 10 files checked"

        count = executor._extract_file_count_from_output(output)

        assert count == 10


class TestAsyncHookExecutorCleanup:
    """Tests for AsyncHookExecutor cleanup methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> AsyncHookExecutor:
        """Create executor for cleanup tests."""
        mock_console = MagicMock()
        logger = logging.getLogger(__name__)
        return AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
        )

    @pytest.mark.asyncio
    async def test_cleanup_running_processes(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test cleanup of running processes via cleanup() method."""
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.wait = AsyncMock()
        executor._running_processes.add(mock_process)

        await executor.cleanup()

        mock_process.kill.assert_called_once()
        assert len(executor._running_processes) == 0

    @pytest.mark.asyncio
    async def test_cleanup_empty_processes(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test cleanup when no running processes."""
        await executor._cleanup_running_processes()

        assert len(executor._running_processes) == 0

    @pytest.mark.asyncio
    async def test_cleanup_pending_tasks(
        self,
        executor: AsyncHookExecutor,
    ) -> None:
        """Test cleanup of pending tasks."""
        await executor._cleanup_pending_tasks()


class TestAsyncHookExecutorErrorHandling:
    """Tests for AsyncHookExecutor error handling."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> AsyncHookExecutor:
        """Create executor for error tests."""
        mock_console = MagicMock()
        logger = logging.getLogger(__name__)
        return AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
        )

    def test_handle_runtime_error_loop_closed(self, executor: AsyncHookExecutor) -> None:
        """Test handling RuntimeError when event loop is closed."""
        error = RuntimeError("Event loop is closed")
        hook = HookDefinition(name="test-hook", command=[], timeout=5, stage=HookStage.FAST)

        result = executor._handle_runtime_error(error, hook, time.time())

        assert result.status == "error"
        assert "Event loop closed" in result.issues_found[0]

    def test_handle_runtime_error_other(self, executor: AsyncHookExecutor) -> None:
        """Test handling RuntimeError that should be raised."""
        error = RuntimeError("Some other error")
        hook = HookDefinition(name="test-hook", command=[], timeout=5, stage=HookStage.FAST)

        with pytest.raises(RuntimeError):
            executor._handle_runtime_error(error, hook, time.time())

    def test_handle_general_error(self, executor: AsyncHookExecutor) -> None:
        """Test handling general exceptions."""
        error = ValueError("Something went wrong")
        hook = HookDefinition(name="test-hook", command=[], timeout=5, stage=HookStage.FAST)

        result = executor._handle_general_error(error, hook, time.time())

        assert result.status == "error"
        assert result.name == "test-hook"
        assert result.exit_code == 1


class TestAsyncHookExecutorLogging:
    """Tests for AsyncHookExecutor logging methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> AsyncHookExecutor:
        """Create executor for logging tests."""
        mock_console = MagicMock()
        logger = logging.getLogger(__name__)
        return AsyncHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
        )

    def test_format_log_no_fields(self, executor: AsyncHookExecutor) -> None:
        """Test _format_log with no fields."""
        result = executor._format_log("test message", {})

        assert result == "test message"

    def test_format_log_with_fields(self, executor: AsyncHookExecutor) -> None:
        """Test _format_log with fields."""
        result = executor._format_log("test message", {"key": "value", "num": 42})

        assert "test message" in result
        assert "key=value" in result
        assert "num=42" in result

    def test_log_info(self, executor: AsyncHookExecutor) -> None:
        """Test _log_info method."""
        executor.logger = MagicMock()

        executor._log_info("test message", key="value")

        executor.logger.info.assert_called_once()

    def test_log_warning(self, executor: AsyncHookExecutor) -> None:
        """Test _log_warning method."""
        executor.logger = MagicMock()

        executor._log_warning("test warning", key="value")

        executor.logger.warning.assert_called_once()

    def test_log_debug(self, executor: AsyncHookExecutor) -> None:
        """Test _log_debug method."""
        executor.logger = MagicMock()

        executor._log_debug("test debug", key="value")

        executor.logger.debug.assert_called_once()

    def test_log_exception(self, executor: AsyncHookExecutor) -> None:
        """Test _log_exception method."""
        executor.logger = MagicMock()

        executor._log_exception("test exception", key="value")

        executor.logger.exception.assert_called_once()
