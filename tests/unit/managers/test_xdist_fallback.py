"""Unit tests for TestExecutor xdist fallback mechanism.

Tests the intelligent fallback system that detects when pytest-xdist
hangs or times out and automatically falls back to sequential execution.
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

from crackerjack.managers.test_executor import TestExecutor
from crackerjack.managers.test_progress import TestProgress


@pytest.mark.unit
class TestXdistFallbackDetection:
    """Test xdist fallback detection logic."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create TestExecutor instance for testing."""
        from rich.console import Console
        console = Console()
        return TestExecutor(console=console, pkg_path=tmp_path)

    def test_should_try_xdist_fallback_with_xdist_enabled(self, executor) -> None:
        """Test fallback detection when xdist is enabled and settings allow fallback."""
        cmd = ["uv", "run", "python", "-m", "pytest", "-n", "4", "--dist=loadfile"]

        with patch("crackerjack.config.load_settings") as mock_load:
            mock_settings = Mock()
            mock_settings.testing.xdist_fallback_to_sequential = True
            mock_load.return_value = mock_settings

            result = executor._should_try_xdist_fallback(cmd)

            assert result is True

    def test_should_try_xdist_fallback_with_single_worker(self, executor) -> None:
        """Test fallback detection when only 1 worker is specified (no parallelization)."""
        cmd = ["uv", "run", "python", "-m", "pytest", "-n", "1"]

        with patch("crackerjack.config.load_settings") as mock_load:
            mock_settings = Mock()
            mock_settings.testing.xdist_fallback_to_sequential = True
            mock_load.return_value = mock_settings

            result = executor._should_try_xdist_fallback(cmd)

            assert result is False

    def test_should_try_xdist_fallback_disabled_in_settings(self, executor) -> None:
        """Test fallback detection when fallback is disabled in settings."""
        cmd = ["uv", "run", "python", "-m", "pytest", "-n", "4"]

        with patch("crackerjack.config.load_settings") as mock_load:
            mock_settings = Mock()
            mock_settings.testing.xdist_fallback_to_sequential = False
            mock_load.return_value = mock_settings

            result = executor._should_try_xdist_fallback(cmd)

            assert result is False

    def test_should_try_xdist_fallback_no_xdist_flag(self, executor) -> None:
        """Test fallback detection when xdist is not in use."""
        cmd = ["uv", "run", "python", "-m", "pytest", "-v"]

        with patch("crackerjack.config.load_settings") as mock_load:
            mock_settings = Mock()
            mock_settings.testing.xdist_fallback_to_sequential = True
            mock_load.return_value = mock_settings

            result = executor._should_try_xdist_fallback(cmd)

            assert result is False

    def test_should_try_xdist_fallback_with_auto_workers(self, executor) -> None:
        """Test fallback detection when using auto worker detection."""
        cmd = ["uv", "run", "python", "-m", "pytest", "-n", "auto"]

        with patch("crackerjack.config.load_settings") as mock_load:
            mock_settings = Mock()
            mock_settings.testing.xdist_fallback_to_sequential = True
            mock_load.return_value = mock_settings

            result = executor._should_try_xdist_fallback(cmd)

            assert result is True


@pytest.mark.unit
class TestWorkerCountDetection:
    """Test worker count detection from command line."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create TestExecutor instance for testing."""
        from rich.console import Console
        console = Console()
        return TestExecutor(console=console, pkg_path=tmp_path)

    def test_get_worker_count_explicit_number(self, executor) -> None:
        """Test worker count detection with explicit number."""
        cmd = ["pytest", "-n", "4"]
        result = executor._get_optimal_worker_count_from_cmd(cmd)
        assert result == 4

    def test_get_worker_count_auto(self, executor) -> None:
        """Test worker count detection with auto (returns default 4)."""
        cmd = ["pytest", "-n", "auto"]
        result = executor._get_optimal_worker_count_from_cmd(cmd)
        assert result == 4

    def test_get_worker_count_no_xdist_flag(self, executor) -> None:
        """Test worker count detection when no xdist flag present."""
        cmd = ["pytest", "-v"]
        result = executor._get_optimal_worker_count_from_cmd(cmd)
        assert result == 1

    def test_get_worker_count_invalid_value(self, executor) -> None:
        """Test worker count detection with invalid value (defaults to 1)."""
        cmd = ["pytest", "-n", "invalid"]
        result = executor._get_optimal_worker_count_from_cmd(cmd)
        assert result == 1

    def test_get_worker_count_missing_value(self, executor) -> None:
        """Test worker count detection when -n flag has no value."""
        cmd = ["pytest", "-n"]
        result = executor._get_optimal_worker_count_from_cmd(cmd)
        assert result == 1


@pytest.mark.unit
class TestXdistTimeoutDetection:
    """Test xdist timeout detection logic."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create TestExecutor instance for testing."""
        from rich.console import Console
        console = Console()
        return TestExecutor(console=console, pkg_path=tmp_path)

    @pytest.fixture
    def progress(self, tmp_path):
        """Create TestProgress instance for testing."""
        return TestProgress()

    def test_did_timeout_negative_returncode_no_completed(self, executor, progress) -> None:
        """Test timeout detection with negative returncode and no completed tests."""
        result = Mock()
        result.returncode = -9  # SIGKILL
        result.stdout = ""
        result.stderr = ""

        progress.passed = 0
        progress.failed = 0
        progress.skipped = 0
        progress.errors = 0

        assert executor._did_xdist_timeout(result, progress) is True

    def test_did_timeout_worker_crashed_message(self, executor, progress) -> None:
        """Test timeout detection when worker crashed message appears."""
        result = Mock()
        result.returncode = 1
        result.stdout = "worker crashed during test execution"
        result.stderr = ""

        assert executor._did_xdist_timeout(result, progress) is True

    def test_did_timeout_workers_not_finished_message(self, executor, progress) -> None:
        """Test timeout detection when workers did not finish message appears."""
        result = Mock()
        result.returncode = 1
        result.stdout = "workers did not finish in time"
        result.stderr = ""

        assert executor._did_xdist_timeout(result, progress) is True

    def test_did_timeout_worker_crashed_keyword(self, executor, progress) -> None:
        """Test timeout detection when a worker crashes."""
        result = Mock()
        result.returncode = 1
        result.stdout = "worker crashed during initialization"
        result.stderr = ""

        assert executor._did_xdist_timeout(result, progress) is True

    def test_did_timeout_worker_timeout_keyword(self, executor, progress) -> None:
        """Test timeout detection when a worker times out."""
        result = Mock()
        result.returncode = 1
        result.stdout = "*** WORKER TIMEOUT ***"
        result.stderr = ""

        assert executor._did_xdist_timeout(result, progress) is True

    def test_did_timeout_node_down_keyword(self, executor, progress) -> None:
        """Test timeout detection when a node goes down."""
        result = Mock()
        result.returncode = 1
        result.stdout = "node down: gw3"
        result.stderr = ""

        assert executor._did_xdist_timeout(result, progress) is True

    def test_did_timeout_normal_failure(self, executor, progress) -> None:
        """Test timeout detection with normal test failure (no timeout)."""
        result = Mock()
        result.returncode = 1
        result.stdout = "FAILED test_module.py::test_function"
        result.stderr = "AssertionError: Expected 5, got 3"

        progress.passed = 5
        progress.failed = 1

        assert executor._did_xdist_timeout(result, progress) is False

    def test_internal_error_exit_code_triggers_sequential_retry(self, executor) -> None:
        """pytest INTERNALERROR (exit 3) means the run itself failed.

        xdist raises "Unexpectedly no active workers available" when there
        are fewer collected items than workers, which incremental selection
        makes easy to hit: a run that selects a handful of tests cannot fill
        a worker per CPU. The executor already has a sequential fallback,
        but it did not recognise this exit code, so the phase reported
        "test execution failed" with zero tests run.
        """
        calls: list[list[str]] = []

        def fake_execute(cmd, env, prog, cb, timeout, stall_timeout=None):
            calls.append(list(cmd))
            result = Mock()
            result.returncode = 3 if len(calls) == 1 else 1
            result.stdout = ""
            result.stderr = ""
            return result

        with patch.object(
            executor,
            "_execute_test_process_with_progress",
            side_effect=fake_execute,
        ):
            result = executor._run_with_xdist_fallback(
                ["pytest", "-n", "auto", "--dist=loadfile", "tests"],
                TestProgress(),
                None,
                600,
            )

        assert len(calls) == 2, (
            f"an INTERNALERROR must trigger a sequential retry, got {len(calls)} calls"
        )
        assert "-n" not in calls[1], f"the retry must drop xdist: {calls[1]}"
        assert "--dist=loadfile" not in calls[1], (
            f"the retry must drop the distribution mode: {calls[1]}"
        )
        assert result.returncode == 1

    def test_did_timeout_success_case_insensitive(self, executor, progress) -> None:
        """Test timeout detection is case-insensitive."""
        result = Mock()
        result.returncode = 1
        result.stdout = "WORKER CRASHED"  # Uppercase
        result.stderr = ""

        assert executor._did_xdist_timeout(result, progress) is True


@pytest.mark.unit
class TestRemoveXdistFromCommand:
    """Test removal of xdist flags from command."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create TestExecutor instance for testing."""
        from rich.console import Console
        console = Console()
        return TestExecutor(console=console, pkg_path=tmp_path)

    def test_remove_xdist_with_n_flag(self, executor) -> None:
        """Test removing -n flag and its value."""
        cmd = ["pytest", "-n", "4", "--dist=loadfile", "-v"]
        result = executor._remove_xdist_from_cmd(cmd)

        assert "-n" not in result
        assert "4" not in result
        assert "pytest" in result
        assert "-v" in result
        assert "--dist=loadfile" not in result

    def test_remove_xdist_with_dist_flag(self, executor) -> None:
        """Test removing --dist flag."""
        cmd = ["pytest", "-n", "auto", "--dist=each", "-v"]
        result = executor._remove_xdist_from_cmd(cmd)

        assert "--dist=each" not in result
        assert "-n" not in result
        assert "pytest" in result
        assert "-v" in result

    def test_remove_xdist_multiple_dist_flags(self, executor) -> None:
        """Test removing multiple distribution flags."""
        cmd = ["pytest", "-n", "2", "--dist=loadscope", "-v"]
        result = executor._remove_xdist_from_cmd(cmd)

        assert "--dist=loadscope" not in result
        assert "-n" not in result

    def test_remove_xdist_no_xdist_flags(self, executor) -> None:
        """Test command without xdist flags remains unchanged."""
        cmd = ["pytest", "-v", "--tb=short"]
        result = executor._remove_xdist_from_cmd(cmd)

        assert result == cmd

    def test_remove_xdist_preserves_other_flags(self, executor) -> None:
        """Test that other pytest flags are preserved."""
        cmd = ["pytest", "-n", "4", "-v", "--cov=crackerjack", "--tb=long"]
        result = executor._remove_xdist_from_cmd(cmd)

        assert "-v" in result
        assert "--cov=crackerjack" in result
        assert "--tb=long" in result
        assert "-n" not in result


@pytest.mark.unit
class TestXdistFallbackFlow:
    """Test the complete xdist fallback flow."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create TestExecutor instance for testing."""
        from rich.console import Console
        console = Console()
        return TestExecutor(console=console, pkg_path=tmp_path)

    @pytest.fixture
    def progress(self, tmp_path):
        """Create TestProgress instance for testing."""
        progress = TestProgress()
        return progress

    def test_fallback_on_timeout(self, executor, progress) -> None:
        """Test fallback to sequential when xdist times out."""
        cmd = ["pytest", "-n", "4", "-v"]
        timeout = 1800

        # Mock parallel execution to time out
        timeout_result = Mock()
        timeout_result.returncode = -9
        timeout_result.stdout = ""
        timeout_result.stderr = ""

        # Mock sequential execution to succeed
        success_result = Mock()
        success_result.returncode = 0
        success_result.stdout = "10 passed"
        success_result.stderr = ""

        with patch("crackerjack.config.load_settings") as mock_load:
            mock_settings = Mock()
            mock_settings.testing.xdist_stall_timeout_seconds = 10
            mock_load.return_value = mock_settings

            with patch.object(executor, "_execute_test_process_with_progress") as mock_execute:
                # First call (parallel) times out, second call (sequential) succeeds
                mock_execute.side_effect = [timeout_result, success_result]

                result = executor._run_with_xdist_fallback(cmd, progress, None, timeout)

                assert mock_execute.call_count == 2
                # The parallel attempt gets the run's full budget plus a
                # separate stall budget. A slow run is not a hung run,
                # and the old code conflated the two: the parallel
                # attempt was killed at 60s no matter how healthy it was.
                first_call = mock_execute.call_args_list[0]
                # The total budget is the 5th positional argument (index 4)
                assert first_call[0][4] == timeout
                assert first_call[1]["stall_timeout"] == 10

                # Second call should use full timeout (1800s) and sequential command
                second_call = mock_execute.call_args_list[1]
                sequential_cmd = second_call[0][0]
                assert "-n" not in sequential_cmd
                assert second_call[0][4] == timeout
                # The sequential run has no stall budget of its own, so
                # it falls back to the total one.
                assert "stall_timeout" not in second_call[1]

    def test_no_fallback_on_success(self, executor, progress) -> None:
        """Test no fallback when xdist succeeds."""
        cmd = ["pytest", "-n", "4", "-v"]
        timeout = 1800

        # Mock parallel execution to succeed
        success_result = Mock()
        success_result.returncode = 0
        success_result.stdout = "10 passed"
        success_result.stderr = ""

        with patch("crackerjack.config.load_settings") as mock_load:
            mock_settings = Mock()
            mock_settings.testing.xdist_stall_timeout_seconds = 10
            mock_load.return_value = mock_settings

            with patch.object(executor, "_execute_test_process_with_progress") as mock_execute:
                mock_execute.return_value = success_result

                result = executor._run_with_xdist_fallback(cmd, progress, None, timeout)

                # Should only call once (no fallback)
                assert mock_execute.call_count == 1

    def test_fallback_with_error_messages(self, executor, progress) -> None:
        """Test fallback when xdist produces error messages."""
        cmd = ["pytest", "-n", "auto", "-v"]
        timeout = 1800

        # Mock parallel execution with error messages
        error_result = Mock()
        error_result.returncode = 1
        error_result.stdout = "worker crashed during initialization"
        error_result.stderr = ""

        # Mock sequential execution to succeed
        success_result = Mock()
        success_result.returncode = 0
        success_result.stdout = "10 passed"
        success_result.stderr = ""

        with patch("crackerjack.config.load_settings") as mock_load:
            mock_settings = Mock()
            mock_settings.testing.xdist_stall_timeout_seconds = 10
            mock_load.return_value = mock_settings

            with patch.object(executor, "_execute_test_process_with_progress") as mock_execute:
                mock_execute.side_effect = [error_result, success_result]

                result = executor._run_with_xdist_fallback(cmd, progress, None, timeout)

                assert mock_execute.call_count == 2


@pytest.mark.unit
class TestPreCollectionDisabled:
    """Test that pre-collection is disabled to avoid hanging."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create TestExecutor instance for testing."""
        from rich.console import Console
        console = Console()
        return TestExecutor(console=console, pkg_path=tmp_path)

    def test_pre_collection_returns_zero(self, executor) -> None:
        """Test that pre-collection returns 0 (disabled)."""
        cmd = ["pytest", "-v"]
        result = executor._pre_collect_tests(cmd)
        assert result == 0


@pytest.mark.unit
class TestFailureDetectionIsSpecific:
    """The fallback must recognise a failure, not a keyword.

    The detector used to look for the bare word ``"xdist"`` in the
    output. pytest prints its plugin list in its own header -- ``plugins:
    ..., xdist-3.8.0, ...`` -- so the match fired on *every* parallel
    run: the executor threw the parallel result away and re-ran the
    whole suite sequentially. The indicators have to name the failure.
    """

    @pytest.fixture
    def executor(self, tmp_path):
        from rich.console import Console
        console = Console()
        return TestExecutor(console=console, pkg_path=tmp_path)

    def test_a_healthy_run_that_mentions_xdist_is_not_a_failure(self, executor) -> None:
        result = Mock()
        result.returncode = 1
        result.stdout = (
            "============================= test session starts ====================\n"
            "platform darwin -- Python 3.14.10, pytest-9.1.1, pluggy-1.6.0\n"
            "plugins: cov-7.1.0, testmon-2.3.0, xdist-3.8.0, timeout-2.4.0\n"
            "1 failed, 262 passed\n"
        )
        result.stderr = ""

        assert executor._did_xdist_timeout(result, TestProgress()) is False

    def test_a_crashed_worker_is_a_failure(self, executor) -> None:
        result = Mock()
        result.returncode = 1
        result.stdout = "worker crashed during initialization\n"
        result.stderr = ""

        assert executor._did_xdist_timeout(result, TestProgress()) is True


@pytest.mark.unit
class TestOutputStreamIsNotLost:
    """A gap in the output stream is not end-of-stream.

    The executor reads the child's stdout on a non-blocking pipe. On
    such a pipe ``readline()`` returns ``""`` whenever the writer has
    not produced a complete line yet -- which is the normal state
    between two tests. The reader used to treat that as EOF, which ended
    the read loop at the first gap: the per-test counts never arrived,
    the run state was never written, and the still-running process was
    then killed by the completion timeout. A healthy parallel run
    looked exactly like a hung one.
    """

    @pytest.fixture
    def executor(self, tmp_path):
        from rich.console import Console
        console = Console()
        return TestExecutor(console=console, pkg_path=tmp_path)

    def test_output_spanning_a_gap_is_fully_captured(self, executor) -> None:
        """Lines written on both sides of a quiet period are both read."""
        cmd = [
            sys.executable,
            "-c",
            "import time; print('before the gap', flush=True); "
            "time.sleep(1.0); print('after the gap', flush=True)",
        ]

        result = executor._execute_test_process_with_progress(
            cmd,
            os.environ.copy(),
            TestProgress(),
            None,
            timeout=60,
        )

        assert result.returncode == 0
        assert "before the gap" in result.stdout
        assert "after the gap" in result.stdout

    def test_a_silent_process_is_not_mistaken_for_a_finished_one(self, executor) -> None:
        """The run's total budget is separate from its stall budget.

        The parallel attempt used to be killed at the stall timeout even
        when it was perfectly healthy, because the two budgets were the
        same number and the stall timeout was also the completion
        timeout.
        """
        cmd = [
            sys.executable,
            "-c",
            "import time; time.sleep(2.0); print('done', flush=True)",
        ]

        result = executor._execute_test_process_with_progress(
            cmd,
            os.environ.copy(),
            TestProgress(),
            None,
            timeout=60,
            stall_timeout=30,
        )

        assert result.returncode == 0
        assert "done" in result.stdout
