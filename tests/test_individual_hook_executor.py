"""Comprehensive tests for individual_hook_executor.py module.

Tests the IndividualHookExecutor class that handles individual hook execution with streaming.
"""

import asyncio
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from crackerjack.config.hooks import (
    HookDefinition,
    HookStage,
    HookStrategy,
)
from crackerjack.executors.individual_hook_executor import (
    IndividualHookExecutor,
    IndividualExecutionResult,
    HookProgress,
    HookOutputParser,
)
from crackerjack.models.task import HookResult


class TestHookProgress:
    """Tests for HookProgress dataclass."""

    def test_hook_progress_init(self) -> None:
        """Test HookProgress initialization."""
        progress = HookProgress(
            hook_name="test-hook",
            status="pending",
            start_time=time.time(),
        )

        assert progress.hook_name == "test-hook"
        assert progress.status == "pending"
        assert progress.output_lines == []
        assert progress.error_details == []

    def test_hook_progress_post_init(self) -> None:
        """Test HookProgress post_init calculates duration."""
        start = time.time()
        end = start + 1.0

        progress = HookProgress(
            hook_name="test-hook",
            status="running",
            start_time=start,
            end_time=end,
        )

        assert progress.duration == pytest.approx(1.0, rel=0.1)

    def test_hook_progress_to_dict(self) -> None:
        """Test HookProgress to_dict method."""
        progress = HookProgress(
            hook_name="test-hook",
            status="passed",
            start_time=time.time(),
            end_time=time.time() + 1.0,
            errors_found=2,
            warnings_found=1,
            files_processed=5,
        )

        d = progress.to_dict()

        assert d["hook_name"] == "test-hook"
        assert d["status"] == "passed"
        assert d["errors_found"] == 2
        assert d["files_processed"] == 5


class TestIndividualExecutionResult:
    """Tests for IndividualExecutionResult dataclass."""

    def test_result_properties(self) -> None:
        """Test result properties."""
        hook_results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0),
            HookResult(id="2", name="hook2", status="failed", duration=1.0),
        ]

        hook_progress = [
            HookProgress(hook_name="hook1", status="passed", start_time=time.time()),
            HookProgress(hook_name="hook2", status="failed", start_time=time.time()),
        ]

        result = IndividualExecutionResult(
            strategy_name="test",
            hook_results=hook_results,
            hook_progress=hook_progress,
            total_duration=2.0,
            success=False,
            execution_order=["hook1", "hook2"],
        )

        assert result.failed_hooks == ["hook2"]
        assert result.total_errors == 0

    def test_failed_hooks(self) -> None:
        """Test failed_hooks property."""
        hook_progress = [
            HookProgress(hook_name="hook1", status="passed", start_time=time.time()),
            HookProgress(hook_name="hook2", status="failed", start_time=time.time()),
        ]

        result = IndividualExecutionResult(
            strategy_name="test",
            hook_results=[],
            hook_progress=hook_progress,
            total_duration=1.0,
            success=False,
            execution_order=[],
        )

        assert result.failed_hooks == ["hook2"]


class TestHookOutputParser:
    """Tests for HookOutputParser class."""

    @pytest.fixture
    def parser(self) -> HookOutputParser:
        """Create a HookOutputParser instance."""
        return HookOutputParser()

    def test_parser_init(self, parser: HookOutputParser) -> None:
        """Test HookOutputParser initialization."""
        assert "ruff-check" in parser.HOOK_PATTERNS
        assert "pyright" in parser.HOOK_PATTERNS

    def test_parse_hook_output_generic(self, parser: HookOutputParser) -> None:
        """Test generic output parsing."""
        lines = ["Error: something failed", "Warning: check this"]

        result = parser.parse_hook_output("unknown-hook", lines)

        assert "errors" in result
        assert "warnings" in result

    def test_parse_hook_output_ruff_check(self, parser: HookOutputParser) -> None:
        """Test ruff-check output parsing."""
        lines = [
            "src/file.py:10:5: F401 unused import",
        ]

        result = parser.parse_hook_output("ruff-check", lines)

        assert "errors" in result

    def test_parse_hook_output_pyright(self, parser: HookOutputParser) -> None:
        """Test pyright output parsing."""
        lines = [
            "src/file.py:10:5: error: something",
            "src/file.py:20:1: warning: deprecated",
        ]

        result = parser.parse_hook_output("pyright", lines)

        assert "errors" in result
        assert "warnings" in result

    def test_parse_generic_output(self, parser: HookOutputParser) -> None:
        """Test generic output parsing."""
        lines = ["Error: failed", "All checks passed", "Warning: check"]

        result = parser._parse_generic_output(lines)

        assert "errors" in result
        assert "warnings" in result
        assert result["total_lines"] == 3


class TestIndividualHookExecutor:
    """Tests for IndividualHookExecutor class."""

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
        lock_mgr.acquire_hook_lock = MagicMock()
        lock_mgr.acquire_hook_lock.return_value = AsyncMock().__aenter__ = AsyncMock(return_value=None)
        lock_mgr.acquire_hook_lock.return_value.__aexit__ = AsyncMock(return_value=None)
        return lock_mgr

    @pytest.fixture
    def executor(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
        mock_lock_manager: MagicMock,
    ) -> IndividualHookExecutor:
        """Create an IndividualHookExecutor instance."""
        return IndividualHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            hook_lock_manager=mock_lock_manager,
        )

    def test_init(self, mock_console: MagicMock, tmp_path: Path) -> None:
        """Test IndividualHookExecutor initialization."""
        executor = IndividualHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
        )

        assert executor.console is mock_console
        assert executor.pkg_path == tmp_path
        assert executor.parser is not None

    def test_set_progress_callback(self, executor: IndividualHookExecutor) -> None:
        """Test setting progress callback."""
        callback = MagicMock()

        executor.set_progress_callback(callback)

        assert executor.progress_callback is callback

    def test_set_mcp_mode(self, executor: IndividualHookExecutor) -> None:
        """Test setting MCP mode."""
        executor.set_mcp_mode(enable=True)

        assert executor.suppress_realtime_output is True
        assert executor.progress_callback_interval == 10

        executor.set_mcp_mode(enable=False)

        assert executor.suppress_realtime_output is False


class TestIndividualHookExecutorExecution:
    """Tests for IndividualHookExecutor execution methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> IndividualHookExecutor:
        """Create executor for execution tests."""
        mock_console = MagicMock()
        mock_lock_manager = MagicMock()

        lock_context = MagicMock()
        lock_context.__aenter__ = AsyncMock(return_value=None)
        lock_context.__aexit__ = AsyncMock(return_value=None)
        mock_lock_manager.acquire_hook_lock.return_value = lock_context

        return IndividualHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            hook_lock_manager=mock_lock_manager,
        )

    @pytest.mark.asyncio
    async def test_initialize_execution_state(self, executor: IndividualHookExecutor) -> None:
        """Test execution state initialization."""
        state = executor._initialize_execution_state()

        assert "hook_results" in state
        assert "hook_progress" in state
        assert "execution_order" in state
        assert state["hook_results"] == []
        assert state["hook_progress"] == []

    @pytest.mark.asyncio
    async def test_execute_single_hook_in_strategy(
        self,
        executor: IndividualHookExecutor,
    ) -> None:
        """Test executing a single hook in a strategy."""
        hook = HookDefinition(name="test-hook", command=["echo", "test"], timeout=5)

        execution_state = executor._initialize_execution_state()

        await executor._execute_single_hook_in_strategy(hook, execution_state)

        assert len(execution_state["hook_results"]) == 1
        assert len(execution_state["hook_progress"]) == 1
        assert "test-hook" in execution_state["execution_order"]

    @pytest.mark.asyncio
    async def test_execute_individual_hook_success(
        self,
        executor: IndividualHookExecutor,
    ) -> None:
        """Test successful individual hook execution."""
        hook = HookDefinition(
            name="test-hook",
            command=["echo", "success"],
            timeout=5,
        )

        progress = HookProgress(
            hook_name="test-hook",
            status="pending",
            start_time=time.time(),
        )

        with patch.object(executor, "_run_command_with_streaming") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            )

            result = await executor._execute_individual_hook(hook, progress)

            assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_execute_individual_hook_failure(
        self,
        executor: IndividualHookExecutor,
    ) -> None:
        """Test failed individual hook execution."""
        hook = HookDefinition(
            name="test-hook",
            command=["echo", "fail"],
            timeout=5,
        )

        progress = HookProgress(
            hook_name="test-hook",
            status="pending",
            start_time=time.time(),
        )

        with patch.object(executor, "_run_command_with_streaming") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="Error occurred",
            )

            result = await executor._execute_individual_hook(hook, progress)

            assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_execute_individual_hook_timeout(
        self,
        executor: IndividualHookExecutor,
    ) -> None:
        """Test individual hook timeout."""
        hook = HookDefinition(
            name="test-hook",
            command=["sleep", "10"],
            timeout=1,
        )

        progress = HookProgress(
            hook_name="test-hook",
            status="pending",
            start_time=time.time(),
        )

        with patch.object(executor, "_run_command_with_streaming") as mock_run:
            mock_run.side_effect = TimeoutError()

            result = await executor._execute_individual_hook(hook, progress)

            assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_execute_individual_hook_file_not_found(
        self,
        executor: IndividualHookExecutor,
    ) -> None:
        """Test individual hook when command not found."""
        hook = HookDefinition(
            name="test-hook",
            command=["nonexistent-command"],
            timeout=5,
        )

        progress = HookProgress(
            hook_name="test-hook",
            status="pending",
            start_time=time.time(),
        )

        with patch.object(executor, "_run_command_with_streaming") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = await executor._execute_individual_hook(hook, progress)

            assert result.status == "skipped"


class TestIndividualHookExecutorStreaming:
    """Tests for IndividualHookExecutor streaming methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> IndividualHookExecutor:
        """Create executor for streaming tests."""
        mock_console = MagicMock()
        mock_lock_manager = MagicMock()
        return IndividualHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            hook_lock_manager=mock_lock_manager,
        )

    def test_process_stream_line_bytes(self, executor: IndividualHookExecutor) -> None:
        """Test processing bytes from stream."""
        line = b"test output\n"

        result = executor._process_stream_line(line)

        assert result == "test output"

    def test_process_stream_line_str(self, executor: IndividualHookExecutor) -> None:
        """Test processing string from stream."""
        line = "test output"

        result = executor._process_stream_line(line)

        assert result == "test output"

    def test_update_progress_with_line(self, executor: IndividualHookExecutor) -> None:
        """Test updating progress with line."""
        line_str = "test line"
        output_list: list[str] = []
        progress = HookProgress(
            hook_name="test",
            status="running",
            start_time=time.time(),
        )

        executor._update_progress_with_line(line_str, output_list, progress, 0)

        assert "test line" in output_list
        assert "test line" in progress.output_lines

    def test_maybe_print_line(self, executor: IndividualHookExecutor) -> None:
        """Test maybe_print_line method."""
        executor.suppress_realtime_output = False

        executor._maybe_print_line("test line")

        executor.console.print.assert_called()

    def test_maybe_print_line_suppressed(self, executor: IndividualHookExecutor) -> None:
        """Test maybe_print_line when suppressed."""
        executor.suppress_realtime_output = True

        executor._maybe_print_line("test line")

        executor.console.print.assert_not_called()


class TestIndividualHookExecutorAsync:
    """Tests for IndividualHookExecutor async methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> IndividualHookExecutor:
        """Create executor for async tests."""
        mock_console = MagicMock()
        mock_lock_manager = MagicMock()
        return IndividualHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            hook_lock_manager=mock_lock_manager,
        )

    @pytest.mark.asyncio
    async def test_run_command_with_streaming(self, executor: IndividualHookExecutor) -> None:
        """Test _run_command_with_streaming method."""
        cmd = ["echo", "test"]
        timeout = 5
        progress = HookProgress(
            hook_name="test",
            status="running",
            start_time=time.time(),
        )

        with patch.object(executor, "_create_subprocess") as mock_create:
            mock_process = AsyncMock()
            mock_process.wait = AsyncMock(return_value=0)
            mock_process.communicate = AsyncMock(return_value=(b"output", b""))
            mock_process.stdout = AsyncMock()
            mock_process.stderr = AsyncMock()

            async def mock_readline():
                return b""

            mock_process.stdout.readline = mock_readline
            mock_process.stderr.readline = mock_readline

            mock_create.return_value = mock_process

            result = await executor._run_command_with_streaming(cmd, timeout, progress)

            assert isinstance(result, subprocess.CompletedProcess)

    @pytest.mark.asyncio
    async def test_create_subprocess(self, executor: IndividualHookExecutor) -> None:
        """Test _create_subprocess method."""
        cmd = ["echo", "test"]

        process = await executor._create_subprocess(cmd)

        assert isinstance(process, asyncio.subprocess.Process)

        process.kill()
        await process.wait()

    @pytest.mark.asyncio
    async def test_wait_for_process_completion(
        self,
        executor: IndividualHookExecutor,
    ) -> None:
        """Test _wait_for_process_completion static method."""
        mock_process = AsyncMock()
        mock_process.wait = AsyncMock(return_value=0)

        async def dummy_task():
            pass

        mock_tasks = [asyncio.create_task(dummy_task())]

        await IndividualHookExecutor._wait_for_process_completion(
            mock_process, mock_tasks, 5
        )

        mock_process.wait.assert_called_once()

        for task in mock_tasks:
            task.cancel()


class TestIndividualHookExecutorSummary:
    """Tests for IndividualHookExecutor summary methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> IndividualHookExecutor:
        """Create executor for summary tests."""
        mock_console = MagicMock()
        mock_lock_manager = MagicMock()
        return IndividualHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            hook_lock_manager=mock_lock_manager,
        )

    def test_print_strategy_header(self, executor: IndividualHookExecutor) -> None:
        """Test _print_strategy_header method."""
        strategy = HookStrategy(
            name="test",
            hooks=[
                HookDefinition(name="hook1", command=[], timeout=5),
            ],
        )

        executor._print_strategy_header(strategy)

        executor.console.print.assert_called()

    def test_print_hook_summary(self, executor: IndividualHookExecutor) -> None:
        """Test _print_hook_summary method."""
        hook_name = "test-hook"
        result = HookResult(id="1", name="hook1", status="passed", duration=1.0)
        progress = HookProgress(
            hook_name="test",
            status="passed",
            start_time=time.time(),
        )

        executor._print_hook_summary(hook_name, result, progress)

        executor.console.print.assert_called()

    def test_print_individual_summary(self, executor: IndividualHookExecutor) -> None:
        """Test _print_individual_summary method."""
        strategy = HookStrategy(
            name="test",
            hooks=[
                HookDefinition(name="hook1", command=[], timeout=5),
            ],
        )
        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0),
        ]
        progress_list = [
            HookProgress(
                hook_name="hook1",
                status="passed",
                start_time=time.time(),
                end_time=time.time() + 1.0,
                duration=1.0,
            ),
        ]

        executor._print_individual_summary(strategy, results, progress_list)

        executor.console.print.assert_called()

    def test_update_hook_progress_status(
        self,
        executor: IndividualHookExecutor,
    ) -> None:
        """Test _update_hook_progress_status method."""
        progress = HookProgress(
            hook_name="test",
            status="pending",
            start_time=time.time(),
        )
        result = HookResult(id="1", name="test", status="passed", duration=1.0)

        executor._update_hook_progress_status(progress, result)

        assert progress.status == "completed"
        assert progress.end_time is not None
        assert progress.duration is not None


class TestIndividualHookExecutorFinalize:
    """Tests for IndividualHookExecutor finalization methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> IndividualHookExecutor:
        """Create executor for finalization tests."""
        mock_console = MagicMock()
        mock_lock_manager = MagicMock()
        return IndividualHookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            hook_lock_manager=mock_lock_manager,
        )

    def test_finalize_execution_result(self, executor: IndividualHookExecutor) -> None:
        """Test _finalize_execution_result method."""
        strategy = HookStrategy(
            name="test",
            hooks=[
                HookDefinition(name="hook1", command=[], timeout=5),
            ],
        )

        start_time = time.time()
        execution_state = {
            "hook_results": [
                HookResult(id="1", name="hook1", status="passed", duration=1.0),
            ],
            "hook_progress": [
                HookProgress(
                    hook_name="hook1",
                    status="passed",
                    start_time=start_time,
                    end_time=start_time + 1.0,
                    duration=1.0,
                ),
            ],
            "execution_order": ["hook1"],
        }

        result = executor._finalize_execution_result(
            strategy, execution_state, start_time
        )

        assert isinstance(result, IndividualExecutionResult)
        assert result.strategy_name == "test_individual"
        assert result.success is True