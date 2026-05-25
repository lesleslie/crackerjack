"""Comprehensive tests for lsp_aware_hook_executor.py module.

Tests the LSPAwareHookExecutor class that handles LSP-optimized hook execution.
"""

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
from crackerjack.executors.hook_executor import HookExecutionResult
from crackerjack.executors.lsp_aware_hook_executor import LSPAwareHookExecutor
from crackerjack.models.task import HookResult


class TestLSPAwareHookExecutor:
    """Tests for LSPAwareHookExecutor class."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        """Create a mock console."""
        console = MagicMock()
        console.print = MagicMock()
        return console

    @pytest.fixture
    def mock_lsp_client(self) -> MagicMock:
        """Create a mock LSP client."""
        lsp = MagicMock()
        lsp.is_server_running.return_value = False
        lsp.get_server_info.return_value = {"pid": 1234}
        lsp.check_project_with_feedback.return_value = ({}, "summary")
        lsp.format_diagnostics.return_value = ""
        lsp.get_project_files.return_value = []
        return lsp

    @pytest.fixture
    def executor(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
        mock_lsp_client: MagicMock,
    ) -> LSPAwareHookExecutor:
        """Create an LSPAwareHookExecutor instance."""
        with patch(
            "crackerjack.executors.lsp_aware_hook_executor.LSPClient",
            return_value=mock_lsp_client,
        ):
            exec = LSPAwareHookExecutor(
                console=mock_console,
                pkg_path=tmp_path,
                verbose=False,
                quiet=False,
                debug=False,
                use_tool_proxy=False,
            )
            exec.lsp_client = mock_lsp_client
            return exec

    def test_init(self, mock_console: MagicMock, tmp_path: Path) -> None:
        """Test LSPAwareHookExecutor initialization."""
        with patch(
            "crackerjack.executors.lsp_aware_hook_executor.LSPClient"
        ) as mock_lsp:
            mock_lsp.return_value = MagicMock()

            exec = LSPAwareHookExecutor(
                console=mock_console,
                pkg_path=tmp_path,
                verbose=True,
                quiet=True,
                debug=True,
                use_tool_proxy=False,
            )

            assert exec.console is mock_console
            assert exec.pkg_path == tmp_path
            assert exec.verbose is True
            assert exec.quiet is True
            assert exec.debug is True

    def test_init_with_tool_proxy(self, mock_console: MagicMock, tmp_path: Path) -> None:
        """Test LSPAwareHookExecutor initialization with tool proxy."""
        with patch(
            "crackerjack.executors.lsp_aware_hook_executor.LSPClient"
        ) as mock_lsp:
            mock_lsp.return_value = MagicMock()

            exec = LSPAwareHookExecutor(
                console=mock_console,
                pkg_path=tmp_path,
                use_tool_proxy=True,
            )

            assert hasattr(exec, "tool_proxy")

    def test_check_lsp_availability(self, executor: LSPAwareHookExecutor) -> None:
        """Test _check_lsp_availability method."""
        executor.lsp_client.is_server_running.return_value = True
        executor.lsp_client.get_server_info.return_value = {"pid": 12345}

        result = executor._check_lsp_availability()

        assert result is True

    def test_check_lsp_availability_not_running(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _check_lsp_availability when server not running."""
        executor.lsp_client.is_server_running.return_value = False

        result = executor._check_lsp_availability()

        assert result is False

    def test_should_use_lsp_for_hook(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _should_use_lsp_for_hook method."""
        hook_zuban = HookDefinition(
            name="zuban",
            command=["uv", "run", "zuban", "check"],
            stage=HookStage.COMPREHENSIVE,
        )
        hook_other = HookDefinition(
            name="ruff-check",
            command=["echo", "test"],
            stage=HookStage.FAST,
        )

        assert executor._should_use_lsp_for_hook(hook_zuban, True) is True
        assert executor._should_use_lsp_for_hook(hook_other, True) is False
        assert executor._should_use_lsp_for_hook(hook_zuban, False) is False

    def test_should_use_tool_proxy(self, executor: LSPAwareHookExecutor) -> None:
        """Test _should_use_tool_proxy method."""
        hook_fragile = HookDefinition(name="zuban", command=[], timeout=5)
        hook_normal = HookDefinition(name="ruff-check", command=[], timeout=5)

        executor.use_tool_proxy = False
        assert executor._should_use_tool_proxy(hook_fragile) is False

        executor.use_tool_proxy = True
        executor.tool_proxy = None
        assert executor._should_use_tool_proxy(hook_fragile) is False

        executor.tool_proxy = MagicMock()
        assert executor._should_use_tool_proxy(hook_normal) is False
        assert executor._should_use_tool_proxy(hook_fragile) is True


class TestLSPAwareHookExecutorExecution:
    """Tests for LSPAwareHookExecutor execution methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> LSPAwareHookExecutor:
        """Create executor for execution tests."""
        mock_console = MagicMock()
        mock_lsp = MagicMock()
        mock_lsp.is_server_running.return_value = False
        mock_lsp.check_project_with_feedback.return_value = ({}, "summary")
        mock_lsp.format_diagnostics.return_value = ""
        mock_lsp.get_project_files.return_value = []

        with patch(
            "crackerjack.executors.lsp_aware_hook_executor.LSPClient",
            return_value=mock_lsp,
        ):
            exec = LSPAwareHookExecutor(
                console=mock_console,
                pkg_path=tmp_path,
                use_tool_proxy=False,
            )
            exec.lsp_client = mock_lsp
            return exec

    def test_execute_strategy(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test execute_strategy method."""
        hook = HookDefinition(name="test-hook", command=["echo", "test"], timeout=5)
        strategy = HookStrategy(name="test", hooks=[hook])

        with patch.object(executor, "_execute_single_hook_with_strategies") as mock_exec:
            mock_exec.return_value = HookResult(
                id="1",
                name="test-hook",
                status="passed",
                duration=1.0,
            )

            result = executor.execute_strategy(strategy)

            assert isinstance(result, HookExecutionResult)
            assert result.strategy_name == "test"

    def test_execute_single_hook_with_strategies_lsp(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _execute_single_hook_with_strategies using LSP."""
        hook = HookDefinition(
            name="zuban",
            command=["uv", "run", "zuban", "check"],
            stage=HookStage.COMPREHENSIVE,
        )

        with patch.object(executor, "_execute_lsp_hook") as mock_lsp:
            mock_lsp.return_value = HookResult(
                id="1",
                name="zuban-lsp",
                status="passed",
                duration=1.0,
            )

            result = executor._execute_single_hook_with_strategies(hook, True)

            mock_lsp.assert_called_once_with(hook)

    def test_execute_single_hook_with_strategies_tool_proxy(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _execute_single_hook_with_strategies using tool proxy."""
        executor.use_tool_proxy = True
        executor.tool_proxy = MagicMock()

        hook = HookDefinition(name="zuban", command=["uv", "run", "zuban"], timeout=5)

        with patch.object(executor, "_execute_hook_with_proxy") as mock_proxy:
            mock_proxy.return_value = HookResult(
                id="1",
                name="zuban-proxy",
                status="passed",
                duration=1.0,
            )

            result = executor._execute_single_hook_with_strategies(hook, False)

            mock_proxy.assert_called_once_with(hook)

    def test_execute_single_hook_with_strategies_fallback(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _execute_single_hook_with_strategies falls back to regular execution."""
        hook = HookDefinition(name="ruff-check", command=["echo", "test"], timeout=5)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = HookResult(
                id="1",
                name="ruff-check",
                status="passed",
                duration=1.0,
            )

            result = executor._execute_single_hook_with_strategies(hook, False)

            mock_exec.assert_called_once_with(hook)


class TestLSPAwareHookExecutorLSP:
    """Tests for LSPAwareHookExecutor LSP-specific methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> LSPAwareHookExecutor:
        """Create executor for LSP tests."""
        mock_console = MagicMock()
        mock_lsp = MagicMock()
        mock_lsp.is_server_running.return_value = False
        mock_lsp.check_project_with_feedback.return_value = ({}, "summary")
        mock_lsp.format_diagnostics.return_value = ""
        mock_lsp.get_project_files.return_value = []

        with patch(
            "crackerjack.executors.lsp_aware_hook_executor.LSPClient",
            return_value=mock_lsp,
        ):
            exec = LSPAwareHookExecutor(
                console=mock_console,
                pkg_path=tmp_path,
                use_tool_proxy=False,
            )
            exec.lsp_client = mock_lsp
            return exec

    def test_execute_lsp_hook(self, executor: LSPAwareHookExecutor) -> None:
        """Test _execute_lsp_hook method."""
        hook = HookDefinition(name="zuban", command=[], timeout=5)

        with patch.object(executor, "_perform_lsp_execution") as mock_perform:
            mock_perform.return_value = HookResult(
                id="1",
                name="zuban-lsp",
                status="passed",
                duration=1.0,
            )

            result = executor._execute_lsp_hook(hook)

            assert result.name == "zuban-lsp"

    def test_execute_lsp_hook_error(self, executor: LSPAwareHookExecutor) -> None:
        """Test _execute_lsp_hook error handling."""
        hook = HookDefinition(name="zuban", command=[], timeout=5)

        with patch.object(executor, "_perform_lsp_execution") as mock_perform:
            mock_perform.side_effect = Exception("LSP error")

            with patch.object(executor, "_handle_lsp_execution_error") as mock_handle:
                mock_handle.return_value = HookResult(
                    id="1",
                    name="zuban",
                    status="failed",
                    duration=0.1,
                )

                result = executor._execute_lsp_hook(hook)

                mock_handle.assert_called_once()

    def test_perform_lsp_execution(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _perform_lsp_execution method."""
        hook = HookDefinition(name="zuban", command=[], timeout=5)
        start_time = time.time()

        executor.lsp_client.check_project_with_feedback.return_value = (
            {"file.py": []},
            "Check completed",
        )
        executor.lsp_client.format_diagnostics.return_value = ""

        with patch.object(executor, "_display_lsp_results"):
            with patch.object(executor, "_create_lsp_hook_result") as mock_create:
                mock_create.return_value = HookResult(
                    id="1",
                    name="zuban-lsp",
                    status="passed",
                    duration=1.0,
                )

                result = executor._perform_lsp_execution(hook, start_time)

                mock_create.assert_called_once()

    def test_create_lsp_hook_result(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _create_lsp_hook_result method."""
        hook = HookDefinition(name="zuban", command=[], timeout=5)
        duration = 1.0
        has_errors = True
        output = "error found"
        diagnostics = {"file.py": ["error"]}

        result = executor._create_lsp_hook_result(
            hook, duration, has_errors, output, diagnostics
        )

        assert result.status == "failed"
        assert result.issues_count >= 1

    def test_create_lsp_hook_result_no_errors(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _create_lsp_hook_result with no errors."""
        hook = HookDefinition(name="zuban", command=[], timeout=5)

        result = executor._create_lsp_hook_result(
            hook, 1.0, False, "", {}
        )

        assert result.status == "passed"

    def test_format_lsp_output(self, executor: LSPAwareHookExecutor) -> None:
        """Test _format_lsp_output method."""
        diagnostics = {"file.py": []}
        duration = 1.5

        executor.lsp_client.format_diagnostics.return_value = "diagnostics output"
        executor.lsp_client.get_project_files.return_value = ["file1.py", "file2.py"]

        result = executor._format_lsp_output(diagnostics, duration)

        assert "LSP-optimized check completed" in result
        assert "2 files" in result

    def test_display_lsp_results_verbose(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _display_lsp_results with verbose mode."""
        hook = HookDefinition(name="zuban", command=[], timeout=5)
        executor.verbose = True

        executor._display_lsp_results(hook, False, "output", "summary")

        executor.console.print.assert_called()

    def test_display_lsp_results_with_errors(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _display_lsp_results when errors found."""
        hook = HookDefinition(name="zuban", command=[], timeout=5)
        executor.verbose = False

        executor._display_lsp_results(hook, True, "error output", "summary")

        executor.console.print.assert_called()

    def test_handle_lsp_execution_error(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _handle_lsp_execution_error method."""
        hook = HookDefinition(name="zuban", command=[], timeout=5)
        error = Exception("LSP error")
        start_time = time.time()

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = HookResult(
                id="1",
                name="zuban",
                status="passed",
                duration=1.0,
            )

            result = executor._handle_lsp_execution_error(hook, start_time, error)

            mock_exec.assert_called_once_with(hook)


class TestLSPAwareHookExecutorProxy:
    """Tests for LSPAwareHookExecutor tool proxy methods."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> LSPAwareHookExecutor:
        """Create executor for proxy tests."""
        mock_console = MagicMock()
        mock_lsp = MagicMock()
        mock_lsp.is_server_running.return_value = False

        with patch(
            "crackerjack.executors.lsp_aware_hook_executor.LSPClient",
            return_value=mock_lsp,
        ):
            exec = LSPAwareHookExecutor(
                console=mock_console,
                pkg_path=tmp_path,
                use_tool_proxy=False,
            )
            exec.lsp_client = mock_lsp
            return exec

    def test_execute_hook_with_proxy(self, executor: LSPAwareHookExecutor) -> None:
        """Test _execute_hook_with_proxy method."""
        executor.use_tool_proxy = True
        executor.tool_proxy = MagicMock()
        executor.tool_proxy.execute_tool.return_value = 0
        executor.tool_proxy.get_tool_status.return_value = {}

        hook = HookDefinition(
            name="zuban",
            command=["uv", "run", "zuban", "check"],
            timeout=5,
        )

        with patch.object(executor, "_perform_proxy_execution") as mock_perform:
            mock_perform.return_value = HookResult(
                id="1",
                name="zuban-proxy",
                status="passed",
                duration=1.0,
            )

            result = executor._execute_hook_with_proxy(hook)

            mock_perform.assert_called_once()

    def test_execute_hook_with_proxy_error(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _execute_hook_with_proxy error handling."""
        executor.use_tool_proxy = True
        executor.tool_proxy = MagicMock()

        hook = HookDefinition(name="zuban", command=[], timeout=5)

        with patch.object(executor, "_perform_proxy_execution") as mock_perform:
            mock_perform.side_effect = Exception("Proxy error")

            with patch.object(executor, "_handle_proxy_execution_error") as mock_handle:
                mock_handle.return_value = HookResult(
                    id="1",
                    name="zuban",
                    status="failed",
                    duration=0.1,
                )

                result = executor._execute_hook_with_proxy(hook)

                mock_handle.assert_called_once()

    def test_perform_proxy_execution(self, executor: LSPAwareHookExecutor) -> None:
        """Test _perform_proxy_execution method."""
        executor.tool_proxy = MagicMock()
        executor.tool_proxy.execute_tool.return_value = 0
        executor.tool_proxy.get_tool_status.return_value = {}

        hook = HookDefinition(
            name="zuban",
            command=["uv", "run", "zuban", "check"],
            timeout=5,
        )

        result = executor._perform_proxy_execution(hook, time.time())

        assert result.status == "passed"

    def test_perform_proxy_execution_failure(self, executor: LSPAwareHookExecutor) -> None:
        """Test _perform_proxy_execution with failure."""
        executor.tool_proxy = MagicMock()
        executor.tool_proxy.execute_tool.return_value = 1
        executor.tool_proxy.get_tool_status.return_value = {}

        hook = HookDefinition(
            name="zuban",
            command=["uv", "run", "zuban", "check"],
            timeout=5,
        )

        result = executor._perform_proxy_execution(hook, time.time())

        assert result.status == "failed"

    def test_parse_hook_entry(self, executor: LSPAwareHookExecutor) -> None:
        """Test _parse_hook_entry method."""
        hook = HookDefinition(
            name="test",
            command=["uv", "run", "zuban", "check", "--arg1", "value1"],
            timeout=5,
        )

        tool_name, args = executor._parse_hook_entry(hook)

        assert tool_name == "zuban"
        assert args == ["check", "--arg1", "value1"]

    def test_parse_hook_entry_simple(self, executor: LSPAwareHookExecutor) -> None:
        """Test _parse_hook_entry with simple command."""
        hook = HookDefinition(
            name="test",
            command=["ruff", "check", "."],
            timeout=5,
        )

        tool_name, args = executor._parse_hook_entry(hook)

        assert tool_name == "ruff"
        assert args == ["check", "."]

    def test_parse_hook_entry_invalid(self, executor: LSPAwareHookExecutor) -> None:
        """Test _parse_hook_entry with invalid format."""
        hook = HookDefinition(
            name="test",
            command=["short"],
            timeout=5,
        )

        with pytest.raises(ValueError, match="Invalid hook entry format"):
            executor._parse_hook_entry(hook)

    def test_format_proxy_output(self, executor: LSPAwareHookExecutor) -> None:
        """Test _format_proxy_output method."""
        tool_name = "zuban"
        tool_status = {
            "circuit_breaker_open": True,
            "is_healthy": False,
            "fallback_tools": ["fallback1", "fallback2"],
        }
        duration = 1.5

        result = executor._format_proxy_output(tool_name, tool_status, duration)

        assert "Circuit breaker: OPEN" in result
        assert "Health check: FAILED" in result
        assert "Fallbacks: fallback1, fallback2" in result

    def test_format_proxy_output_no_issues(self, executor: LSPAwareHookExecutor) -> None:
        """Test _format_proxy_output with no issues."""
        tool_name = "zuban"
        tool_status = {}
        duration = 1.0

        result = executor._format_proxy_output(tool_name, tool_status, duration)

        assert "Resilient execution completed" in result

    def test_handle_proxy_execution_error(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _handle_proxy_execution_error method."""
        hook = HookDefinition(name="zuban", command=[], timeout=5)
        error = Exception("Proxy error")
        start_time = time.time()

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = HookResult(
                id="1",
                name="zuban",
                status="passed",
                duration=1.0,
            )

            result = executor._handle_proxy_execution_error(hook, start_time, error)

            mock_exec.assert_called_once_with(hook)


class TestLSPAwareHookExecutorProgress:
    """Tests for LSPAwareHookExecutor progress callbacks."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> LSPAwareHookExecutor:
        """Create executor for progress tests."""
        mock_console = MagicMock()
        mock_lsp = MagicMock()
        mock_lsp.is_server_running.return_value = False

        with patch(
            "crackerjack.executors.lsp_aware_hook_executor.LSPClient",
            return_value=mock_lsp,
        ):
            exec = LSPAwareHookExecutor(
                console=mock_console,
                pkg_path=tmp_path,
                use_tool_proxy=False,
            )
            exec.lsp_client = mock_lsp
            return exec

    def test_handle_progress_start(self, executor: LSPAwareHookExecutor) -> None:
        """Test _handle_progress_start method."""
        executor._progress_start_callback = MagicMock()
        executor._total_hooks = 5
        executor._started_hooks = 0

        executor._handle_progress_start(3)

        assert executor._started_hooks == 1

    def test_handle_progress_start_no_callback(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _handle_progress_start with no callback."""
        executor._progress_start_callback = None

        executor._handle_progress_start(5)

    def test_handle_progress_completion(self, executor: LSPAwareHookExecutor) -> None:
        """Test _handle_progress_completion method."""
        executor._progress_callback = MagicMock()
        executor._total_hooks = 5
        executor._completed_hooks = 0

        executor._handle_progress_completion(3)

        assert executor._completed_hooks == 1

    def test_handle_progress_completion_no_callback(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test _handle_progress_completion with no callback."""
        executor._progress_callback = None

        executor._handle_progress_completion(5)


class TestLSPAwareHookExecutorSummary:
    """Tests for LSPAwareHookExecutor execution summary."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> LSPAwareHookExecutor:
        """Create executor for summary tests."""
        mock_console = MagicMock()
        mock_lsp = MagicMock()
        mock_lsp.is_server_running.return_value = False
        mock_lsp.get_server_info.return_value = {"pid": 1234}

        with patch(
            "crackerjack.executors.lsp_aware_hook_executor.LSPClient",
            return_value=mock_lsp,
        ):
            exec = LSPAwareHookExecutor(
                console=mock_console,
                pkg_path=tmp_path,
                use_tool_proxy=False,
            )
            exec.lsp_client = mock_lsp
            return exec

    def test_get_execution_mode_summary_lsp_available(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test get_execution_mode_summary when LSP is available."""
        executor.lsp_client.is_server_running.return_value = True

        summary = executor.get_execution_mode_summary()

        assert summary["lsp_server_available"] is True
        assert summary["optimization_enabled"] is True
        assert "zuban" in summary["supported_hooks"]

    def test_get_execution_mode_summary_lsp_unavailable(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test get_execution_mode_summary when LSP is unavailable."""
        executor.lsp_client.is_server_running.return_value = False

        summary = executor.get_execution_mode_summary()

        assert summary["lsp_server_available"] is False
        assert summary["optimization_enabled"] is False
        assert summary["supported_hooks"] == []

    def test_get_execution_mode_summary_with_tool_proxy(
        self,
        executor: LSPAwareHookExecutor,
    ) -> None:
        """Test get_execution_mode_summary with tool proxy enabled."""
        executor.use_tool_proxy = True
        executor.tool_proxy = MagicMock()
        executor.tool_proxy.get_tool_status.return_value = {"zuban": {}}

        summary = executor.get_execution_mode_summary()

        assert summary["tool_proxy_enabled"] is True
        assert "tool_status" in summary