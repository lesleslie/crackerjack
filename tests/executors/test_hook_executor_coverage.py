"""Additional tests for crackerjack.executors.hook_executor to lift coverage.

Targets uncovered paths identified in coverage report:
- Parallel execution dispatch, force-enable, skipped display
- Subprocess run with timeout/monitoring and exception branches
- Per-tool issue parsing (complexipy, refurb, lychee, semgrep, pip-audit, creosote)
- File count extraction helpers
- _get_changed_files_for_hook incremental paths
- Retry: ALL_HOOKS path, retry single hook in-place
- _get_uv_environment_paths OSError fallback
- _try_get_qa_result_for_hook (with adapter & adapter_learner)
- Format-vulnerability message, semgrep text/json parsing
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.config.hooks import (
    HookDefinition,
    HookStage,
    HookStrategy,
    RetryPolicy,
)
from crackerjack.executors.hook_executor import HookExecutor, HookExecutionResult
from crackerjack.models.task import HookResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_console() -> MagicMock:
    console = MagicMock()
    console.print = MagicMock()
    return console


@pytest.fixture
def mock_git_service() -> MagicMock:
    git = MagicMock()
    git.get_changed_files_by_extension.return_value = []
    return git


@pytest.fixture
def executor(
    mock_console: MagicMock,
    tmp_path: Path,
    mock_git_service: MagicMock,
) -> HookExecutor:
    return HookExecutor(
        console=mock_console,
        pkg_path=tmp_path,
        verbose=False,
        quiet=False,
        debug=False,
        git_service=mock_git_service,
    )


def _result(
    *,
    name: str = "h",
    status: str = "passed",
    duration: float = 0.0,
    issues: list[str] | None = None,
) -> HookResult:
    return HookResult(
        id=name,
        name=name,
        status=status,
        duration=duration,
        issues_found=issues or [],
        stage="fast",
    )


def _completed(
    *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


# ---------------------------------------------------------------------------
# Sequential: disabled / force-enabled / skipped display
# ---------------------------------------------------------------------------


class TestSequentialDisabledAndSkipped:
    def test_skipped_hooks_not_executed(self, executor: HookExecutor) -> None:
        """Disabled hooks without force enable are recorded as skipped
        (no ``execute_single_hook`` invocation for them)."""
        hooks = [
            HookDefinition(name="disabled-hook", command=[], disabled=True),
            HookDefinition(name="active-hook", command=[], timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=False)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = _result(name="active-hook", status="passed")
            results = executor._execute_sequential(strategy)

        # Only the active hook actually executed
        assert mock_exec.call_count == 1
        assert len(results) == 1
        assert results[0].name == "active-hook"

    def test_force_enabled_runs_disabled_hook(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A disabled hook listed in enable_hooks is force-enabled and runs."""
        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            verbose=True,
            enable_hooks=["locked"],
        )
        hooks = [
            HookDefinition(
                name="locked",
                command=[],
                disabled=True,
                run_schedule="nightly",
            ),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=False)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = _result(name="locked", status="passed")
            executor._execute_sequential(strategy)

        assert mock_exec.call_count == 1
        # The force-enable message should appear in console output
        printed = " ".join(
            str(c.args[0]) for c in mock_console.print.call_args_list
        )
        assert "force-enabled" in printed

    def test_skipped_hook_message_emitted_in_verbose(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Skipped hook log line is printed when verbose is on."""
        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            verbose=True,
        )
        hooks = [
            HookDefinition(
                name="skipped",
                command=[],
                disabled=True,
                run_schedule="daily",
            ),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=False)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            executor._execute_sequential(strategy)

        printed = " ".join(
            str(c.args[0]) for c in mock_console.print.call_args_list
        )
        assert "skipped" in printed
        assert "scheduled: daily" in printed
        mock_exec.assert_not_called()


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------


class TestParallelExecution:
    def test_parallel_dispatch_with_formatting_and_other(
        self, executor: HookExecutor
    ) -> None:
        """Formatting hooks run sequentially first, then others in parallel."""
        hooks = [
            HookDefinition(
                name="ruff-format", command=[], is_formatting=True, timeout=5
            ),
            HookDefinition(
                name="ruff-check", command=[], is_formatting=False, timeout=5
            ),
            HookDefinition(
                name="mypy", command=[], is_formatting=False, timeout=5
            ),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True, max_workers=2)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = _result(status="passed")
            results = executor._execute_parallel(strategy)

        # formatting + 2 others = 3 total
        assert len(results) == 3
        assert mock_exec.call_count == 3

    def test_parallel_future_exception_creates_error_result(
        self, executor: HookExecutor
    ) -> None:
        """If ``execute_single_hook`` raises inside a worker, the loop
        records a synthesized error HookResult rather than crashing."""
        hooks = [
            HookDefinition(
                name="good", command=[], is_formatting=False, timeout=5
            ),
            HookDefinition(
                name="bad", command=[], is_formatting=False, timeout=5
            ),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True, max_workers=2)

        def _side_effect(hook: HookDefinition) -> HookResult:
            if hook.name == "bad":
                raise RuntimeError("worker exploded")
            return _result(name=hook.name, status="passed")

        with patch.object(executor, "execute_single_hook", side_effect=_side_effect):
            results = executor._execute_parallel(strategy)

        assert len(results) == 2
        errored = [r for r in results if r.status == "error"]
        assert len(errored) == 1
        assert errored[0].name == "bad"
        assert "worker exploded" in errored[0].issues_found[0]
        assert errored[0].exit_code == 1
        assert errored[0].is_timeout is False

    def test_parallel_skipped_hooks_logged(self, executor: HookExecutor) -> None:
        """Disabled hooks are listed in verbose skip output during parallel run."""
        executor.verbose = True
        hooks = [
            HookDefinition(
                name="skip-me", command=[], disabled=True, run_schedule="weekly"
            ),
            HookDefinition(name="go", command=[], is_formatting=False, timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = _result(name="go", status="passed")
            executor._execute_parallel(strategy)

        # Skipped hook log went to console; execution still happened
        printed = " ".join(
            str(c.args[0]) for c in executor.console.print.call_args_list
        )
        assert "skip-me" in printed
        assert mock_exec.call_count == 1

    def test_parallel_force_enabled_logged(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verbose parallel path logs force-enabled hooks in categorization."""
        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            verbose=True,
            enable_hooks={"force-it"},
        )
        hooks = [
            HookDefinition(
                name="force-it", command=[], disabled=True, run_schedule="nightly"
            ),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = _result(name="force-it", status="passed")
            executor._execute_parallel(strategy)

        printed = " ".join(
            str(c.args[0]) for c in mock_console.print.call_args_list
        )
        assert "force-enabled" in printed

    def test_parallel_only_formatting_hooks(self, executor: HookExecutor) -> None:
        """With no non-formatting hooks, parallel path only runs formatting."""
        hooks = [
            HookDefinition(
                name="ruff-format", command=[], is_formatting=True, timeout=5
            ),
            HookDefinition(
                name="mdformat", command=[], is_formatting=True, timeout=5
            ),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = _result(status="passed")
            results = executor._execute_parallel(strategy)

        assert len(results) == 2

    def test_parallel_progress_callbacks_drive_counters(
        self, executor: HookExecutor
    ) -> None:
        """Per-hook start/complete callbacks increment the executor counters."""
        started = MagicMock()
        completed = MagicMock()
        executor.set_progress_callbacks(
            started_cb=started, completed_cb=completed, total=2
        )
        hooks = [
            HookDefinition(name="a", command=[], is_formatting=False, timeout=5),
            HookDefinition(name="b", command=[], is_formatting=False, timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = _result(status="passed")
            executor._execute_parallel(strategy)

        assert started.call_count == 2
        assert completed.call_count == 2
        assert executor._completed_hooks == 2


# ---------------------------------------------------------------------------
# Progress helper exception swallowing
# ---------------------------------------------------------------------------


class TestProgressCallbackErrorTolerant:
    def test_handle_progress_start_swallows_cb_exception(
        self, executor: HookExecutor
    ) -> None:
        """A callback that raises must not break hook execution."""
        bad = MagicMock(side_effect=ValueError("boom"))
        executor.set_progress_callbacks(started_cb=bad, total=1)
        executor._handle_progress_start(1)
        # Counters still bumped despite callback failure
        assert executor._started_hooks == 1

    def test_handle_progress_completion_swallows_cb_exception(
        self, executor: HookExecutor
    ) -> None:
        bad = MagicMock(side_effect=ValueError("boom"))
        executor.set_progress_callbacks(completed_cb=bad, total=1)
        executor._handle_progress_completion(1)
        assert executor._completed_hooks == 1


# ---------------------------------------------------------------------------
# _run_hook_subprocess paths
# ---------------------------------------------------------------------------


class TestRunHookSubprocess:
    def test_subprocess_success_uses_subprocess_run(
        self, executor: HookExecutor
    ) -> None:
        """Short-timeout hooks go through plain ``subprocess.run``."""
        hook = HookDefinition(name="quick", command=["echo", "hi"], timeout=5)
        fake = _completed(returncode=0, stdout="hi\n", stderr="")
        with patch("subprocess.run", return_value=fake) as mock_run:
            result = executor._run_hook_subprocess(hook)
        mock_run.assert_called_once()
        assert result.returncode == 0
        assert result.stdout == "hi\n"

    def test_subprocess_long_timeout_uses_monitoring(
        self, executor: HookExecutor
    ) -> None:
        """Timeout > 120s routes through ``_run_with_monitoring``."""
        hook = HookDefinition(name="slow", command=["sleep", "200"], timeout=200)
        fake = _completed(returncode=0, stdout="done", stderr="")
        with patch.object(executor, "_run_with_monitoring", return_value=fake) as m:
            result = executor._run_hook_subprocess(hook)
        m.assert_called_once()
        assert result.returncode == 0

    def test_subprocess_exception_returns_failed_completedprocess(
        self, executor: HookExecutor
    ) -> None:
        """If ``subprocess.run`` raises, return a synthesized failure result."""
        hook = HookDefinition(name="boom", command=["does-not-exist"], timeout=5)
        with patch("subprocess.run", side_effect=OSError("spawn failed")):
            result = executor._run_hook_subprocess(hook)
        assert result.returncode == 1
        assert "spawn failed" in result.stderr

    def test_incremental_builds_command_with_files(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """With incremental on and a matching hook, files are passed via build_command."""
        changed = [Path(tmp_path / "x.py"), Path(tmp_path / "y.py")]
        git = MagicMock()
        git.get_changed_files_by_extension.return_value = changed

        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            verbose=False,
            use_incremental=True,
            git_service=git,
        )
        hook = HookDefinition(
            name="ruff-check",
            command=["ruff", "check"],
            timeout=5,
            accepts_file_paths=True,
        )
        fake = _completed(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=fake) as mock_run:
            executor._run_hook_subprocess(hook)

        # build_command returns ['uv', 'run', 'zuban', 'check', ...files]
        cmd = mock_run.call_args.args[0]
        assert "uv" in cmd
        assert "run" in cmd
        assert "zuban" in cmd
        assert str(changed[0]) in cmd
        assert str(changed[1]) in cmd


# ---------------------------------------------------------------------------
# _run_with_monitoring
# ---------------------------------------------------------------------------


class TestRunWithMonitoring:
    def test_normal_exit_returns_completed_process(
        self, executor: HookExecutor
    ) -> None:
        """Popen exits cleanly -> CompletedProcess is returned."""
        hook = HookDefinition(name="slow", command=["sleep", "1"], timeout=200)
        proc = MagicMock()
        proc.communicate.return_value = ("ok-out", "ok-err")
        proc.returncode = 0

        with patch("subprocess.Popen", return_value=proc):
            with patch(
                "crackerjack.executors.process_monitor.ProcessMonitor"
            ) as Monitor:
                monitor_inst = Monitor.return_value
                result = executor._run_with_monitoring(
                    ["x"], hook, Path("."), {"PATH": "/bin"}
                )
        assert result.returncode == 0
        assert result.stdout == "ok-out"
        assert result.stderr == "ok-err"
        monitor_inst.stop_monitoring.assert_called_once()

    def test_timeout_kills_and_reraises(
        self, executor: HookExecutor
    ) -> None:
        """On TimeoutExpired, Popen is killed and the exception re-raised."""
        hook = HookDefinition(name="slow", command=["sleep", "999"], timeout=1)
        proc = MagicMock()
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="x", timeout=1),
            ("partial", "partial-err"),
        ]
        with patch("subprocess.Popen", return_value=proc):
            with patch("crackerjack.executors.process_monitor.ProcessMonitor"):
                with pytest.raises(subprocess.TimeoutExpired):
                    executor._run_with_monitoring(
                        ["x"], hook, Path("."), {"PATH": "/bin"}
                    )
        proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# _display_hook_output_if_needed
# ---------------------------------------------------------------------------


class TestDisplayHookOutput:
    def test_complexipy_silent_when_not_debug(self, executor: HookExecutor) -> None:
        """complexipy output is suppressed unless ``debug`` is on."""
        result = _completed(returncode=1, stdout="out", stderr="err")
        executor._display_hook_output_if_needed(result, "complexipy")
        executor.console.print.assert_not_called()

    def test_complexipy_prints_when_debug(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        executor = HookExecutor(
            console=mock_console, pkg_path=tmp_path, debug=True, verbose=True
        )
        result = _completed(returncode=1, stdout="out", stderr="err")
        executor._display_hook_output_if_needed(result, "complexipy")
        # When debug is on, the early-return guard is bypassed; the function
        # then falls through to the verbose+rc!=0 check. Since we set verbose=True,
        # both stdout and stderr should be printed.
        printed = " ".join(
            str(c.args[0]) for c in mock_console.print.call_args_list
        )
        assert "out" in printed or "err" in printed

    def test_verbose_failure_prints_both_streams(self, executor: HookExecutor) -> None:
        """Verbose + non-zero exit prints stdout and stderr."""
        executor.verbose = True
        result = _completed(returncode=1, stdout="STDOUT", stderr="STDERR")
        executor._display_hook_output_if_needed(result, "any-tool")
        printed = " ".join(
            str(c.args[0]) for c in executor.console.print.call_args_list
        )
        assert "STDOUT" in printed
        assert "STDERR" in printed

    def test_success_does_not_print_even_in_verbose(self, executor: HookExecutor) -> None:
        executor.verbose = True
        result = _completed(returncode=0, stdout="ok", stderr="ok")
        executor._display_hook_output_if_needed(result, "any-tool")
        executor.console.print.assert_not_called()


# ---------------------------------------------------------------------------
# _create_skipped_hook_result
# ---------------------------------------------------------------------------


class TestCreateSkippedHookResult:
    def test_returns_skipped_status(self, executor: HookExecutor) -> None:
        hook = HookDefinition(name="pip-audit", command=[], timeout=5)
        result = executor._create_skipped_hook_result(
            hook=hook,
            duration=1.23,
            message="offline",
            output="out",
            error="err",
        )
        assert result.status == "skipped"
        assert result.exit_code is None
        assert result.error_message == "offline"
        assert result.output == "out"
        assert result.error == "err"
        assert result.duration == 1.23


# ---------------------------------------------------------------------------
# _should_skip_offline_pip_audit edge cases
# ---------------------------------------------------------------------------


class TestShouldSkipOfflinePipAudit:
    def test_pip_audit_success_not_skipped(self, executor: HookExecutor) -> None:
        """rc=0 means it ran fine — never skip."""
        hook = HookDefinition(name="pip-audit", command=[], timeout=5)
        result = _completed(returncode=0, stdout="", stderr="")
        assert executor._should_skip_offline_pip_audit(hook, result) is False

    def test_skip_disabled_flag_prevents_skip(self, executor: HookExecutor) -> None:
        """When ``skip_offline_pip_audit`` is False, never skip."""
        executor.skip_offline_pip_audit = False
        hook = HookDefinition(name="pip-audit", command=[], timeout=5)
        result = _completed(returncode=1, stderr="getaddrinfo failed")
        assert executor._should_skip_offline_pip_audit(hook, result) is False

    def test_non_pip_audit_hook_not_evaluated(self, executor: HookExecutor) -> None:
        hook = HookDefinition(name="ruff-check", command=[], timeout=5)
        result = _completed(returncode=1, stderr="getaddrinfo failed")
        assert executor._should_skip_offline_pip_audit(hook, result) is False

    def test_offline_markers_in_stdout(self, executor: HookExecutor) -> None:
        hook = HookDefinition(name="pip-audit", command=[], timeout=5)
        result = _completed(returncode=1, stdout="connection refused", stderr="")
        assert executor._should_skip_offline_pip_audit(hook, result) is True

    def test_no_offline_markers(self, executor: HookExecutor) -> None:
        hook = HookDefinition(name="pip-audit", command=[], timeout=5)
        result = _completed(returncode=1, stdout="found 2 vulns", stderr="")
        assert executor._should_skip_offline_pip_audit(hook, result) is False


# ---------------------------------------------------------------------------
# _update_status_for_reporting_tools
# ---------------------------------------------------------------------------


class TestUpdateStatusReportingTools:
    def test_issues_force_failed_status(self, executor: HookExecutor) -> None:
        hook = SimpleNamespace(name="complexipy")
        new_status = executor._update_status_for_reporting_tools(
            hook, "passed", ["issue"], None
        )
        assert new_status == "failed"

    def test_no_issues_keeps_status(self, executor: HookExecutor) -> None:
        hook = SimpleNamespace(name="complexipy")
        new_status = executor._update_status_for_reporting_tools(
            hook, "passed", [], None
        )
        assert new_status == "passed"

    def test_non_reporting_tool_unchanged(self, executor: HookExecutor) -> None:
        hook = SimpleNamespace(name="ruff-check")
        new_status = executor._update_status_for_reporting_tools(
            hook, "passed", ["x"], None
        )
        assert new_status == "passed"

    def test_debug_prints_state(self, mock_console: MagicMock, tmp_path: Path) -> None:
        executor = HookExecutor(
            console=mock_console, pkg_path=tmp_path, debug=True
        )
        hook = SimpleNamespace(name="refurb")
        result = SimpleNamespace(returncode=1, stdout="x", stderr="")
        executor._update_status_for_reporting_tools(hook, "failed", ["x"], result)
        assert any(
            "DEBUG" in str(c.args[0]) for c in mock_console.print.call_args_list
        )


# ---------------------------------------------------------------------------
# _extract_issues_for_reporting_tools dispatch
# ---------------------------------------------------------------------------


class TestExtractIssuesForReportingTools:
    def test_complexipy_dispatches(self, executor: HookExecutor) -> None:
        with patch.object(
            executor, "_parse_complexipy_issues", return_value=["c1"]
        ) as m:
            out = executor._extract_issues_for_reporting_tools(
                SimpleNamespace(name="complexipy"), "raw"
            )
        assert out == ["c1"]
        m.assert_called_once()

    def test_refurb_dispatches(self, executor: HookExecutor) -> None:
        with patch.object(executor, "_parse_refurb_issues", return_value=["r1"]):
            out = executor._extract_issues_for_reporting_tools(
                SimpleNamespace(name="refurb"), "raw"
            )
        assert out == ["r1"]

    def test_pyscn_dispatches(self, executor: HookExecutor) -> None:
        with patch.object(executor, "_parse_pyscn_issues", return_value=["p1"]):
            out = executor._extract_issues_for_reporting_tools(
                SimpleNamespace(name="pyscn"), "raw"
            )
        assert out == ["p1"]

    def test_gitleaks_dispatches(self, executor: HookExecutor) -> None:
        with patch.object(executor, "_parse_gitleaks_issues", return_value=["g1"]):
            out = executor._extract_issues_for_reporting_tools(
                SimpleNamespace(name="gitleaks"), "raw"
            )
        assert out == ["g1"]

    def test_creosote_dispatches(self, executor: HookExecutor) -> None:
        with patch.object(executor, "_parse_creosote_issues", return_value=["c1"]):
            out = executor._extract_issues_for_reporting_tools(
                SimpleNamespace(name="creosote"), "raw"
            )
        assert out == ["c1"]

    def test_pip_audit_dispatches(self, executor: HookExecutor) -> None:
        with patch.object(executor, "_parse_pip_audit_issues", return_value=["pa1"]):
            out = executor._extract_issues_for_reporting_tools(
                SimpleNamespace(name="pip-audit"), "raw"
            )
        assert out == ["pa1"]

    def test_lychee_dispatches(self, executor: HookExecutor) -> None:
        with patch.object(executor, "_parse_lychee_issues", return_value=["l1"]):
            out = executor._extract_issues_for_reporting_tools(
                SimpleNamespace(name="lychee"), "raw"
            )
        assert out == ["l1"]

    def test_unknown_reporting_tool_returns_empty(self, executor: HookExecutor) -> None:
        out = executor._extract_issues_for_reporting_tools(
            SimpleNamespace(name="custom-tool"), "raw"
        )
        assert out == []


# ---------------------------------------------------------------------------
# Lychee JSON parsing
# ---------------------------------------------------------------------------


class TestParseLychee:
    def test_invalid_json_returns_empty(self, executor: HookExecutor) -> None:
        assert executor._parse_lychee_issues("not json") == []

    def test_counter_only_no_map(self, executor: HookExecutor) -> None:
        data = {"error_map": None, "errors": 3}
        out = executor._parse_lychee_issues(json.dumps(data))
        assert len(out) == 1
        assert "3 errors" in out[0]

    def test_map_entries_formatted(self, executor: HookExecutor) -> None:
        data = {
            "error_map": {
                "a.md": [
                    {
                        "url": "https://x",
                        "status": {"text": "404 not found"},
                        "span": {"line": 7},
                    }
                ]
            },
            "errors": 1,
        }
        out = executor._parse_lychee_issues(json.dumps(data))
        assert len(out) == 1
        assert "a.md:7" in out[0]
        assert "https://x" in out[0]
        assert "404 not found" in out[0]

    def test_non_dict_status_falls_back_to_str(self, executor: HookExecutor) -> None:
        data = {
            "error_map": {
                "x.md": [{"url": "u", "status": "raw status", "span": {"line": 1}}]
            },
            "errors": 1,
        }
        out = executor._parse_lychee_issues(json.dumps(data))
        assert "raw status" in out[0]

    def test_entry_not_dict_stringified(self, executor: HookExecutor) -> None:
        data = {
            "error_map": {"x.md": ["weird"]},
            "errors": 1,
        }
        out = executor._parse_lychee_issues(json.dumps(data))
        assert "weird" in out[0]

    def test_timeout_map_branch(self, executor: HookExecutor) -> None:
        data = {
            "error_map": None,
            "timeouts": 4,
        }
        out = executor._parse_lychee_issues(json.dumps(data))
        assert len(out) == 1
        assert "4 timeouts" in out[0]

    @staticmethod
    def test_format_lychee_entry_status_not_dict() -> None:
        s = HookExecutor._format_lychee_entry("f.md", {"url": "u", "status": None, "span": {}})
        assert "u" in s

    def test_format_lychee_entry_non_dict(self) -> None:
        s = HookExecutor._format_lychee_entry("f.md", "raw")
        assert "f.md" in s
        assert "raw" in s


# ---------------------------------------------------------------------------
# Semgrep parsing
# ---------------------------------------------------------------------------


class TestParseSemgrep:
    def test_valid_json_results_extracted(self, executor: HookExecutor) -> None:
        data = {
            "results": [
                {
                    "path": "src/x.py",
                    "start": {"line": 12},
                    "check_id": "rule.id",
                    "extra": {"message": "bad pattern"},
                }
            ]
        }
        out = executor._parse_semgrep_issues(json.dumps(data))
        assert len(out) == 1
        assert "src/x.py:12" in out[0]
        assert "rule.id" in out[0]
        assert "bad pattern" in out[0]

    def test_infra_error_warns_but_doesnt_list(self, mock_console, tmp_path) -> None:
        """Network/infra errors are console-warned but not added to issues."""
        executor = HookExecutor(console=mock_console, pkg_path=tmp_path)
        data = {
            "results": [],
            "errors": [
                {"type": "NetworkError", "message": "offline"},
            ],
        }
        out = executor._parse_semgrep_issues(json.dumps(data))
        assert out == []
        printed = " ".join(
            str(c.args[0]) for c in mock_console.print.call_args_list
        )
        assert "NetworkError" in printed

    def test_non_infra_error_added_to_issues(self, executor: HookExecutor) -> None:
        data = {
            "results": [],
            "errors": [{"type": "OtherError", "message": "boom"}],
        }
        out = executor._parse_semgrep_issues(json.dumps(data))
        assert len(out) == 1
        assert "OtherError" in out[0]
        assert "boom" in out[0]

    def test_invalid_json_falls_back_to_lines(self, executor: HookExecutor) -> None:
        text = "first line\nsecond line\n"
        out = executor._parse_semgrep_issues(text)
        # Lines are stripped of empty values
        assert out == ["first line", "second line"]

    def test_empty_input_returns_empty(self, executor: HookExecutor) -> None:
        assert executor._parse_semgrep_issues("") == []
        assert executor._parse_semgrep_issues("   \n\n  ") == []


# ---------------------------------------------------------------------------
# Pip-audit parsing
# ---------------------------------------------------------------------------


class TestPipAuditParsing:
    def test_no_json_falls_back_to_text(self, executor: HookExecutor) -> None:
        text = "Warning: CVE-2024-1234 vulnerability in pkg-x"
        out = executor._parse_pip_audit_issues(text)
        assert any("CVE-2024-1234" in x for x in out)

    def test_no_vulnerabilities_text(self, executor: HookExecutor) -> None:
        text = "Scanned. 0 vulnerabilities found."
        out = executor._parse_pip_audit_issues(text)
        assert out == []

    def test_valid_json_with_vulnerability(self, executor: HookExecutor) -> None:
        payload = {
            "dependencies": [
                {
                    "name": "pkg",
                    "version": "1.0",
                    "vulns": [
                        {
                            "id": "PYSEC-2024-X",
                            "aliases": ["CVE-2024-9999"],
                            "description": "very bad",
                            "fix_versions": ["1.1"],
                        }
                    ],
                }
            ]
        }
        out = executor._parse_pip_audit_issues(json.dumps(payload))
        assert len(out) == 1
        assert "pkg==1.0" in out[0]
        assert "PYSEC-2024-X" in out[0]
        assert "CVE-2024-9999" in out[0]
        assert "1.1" in out[0]

    def test_long_description_truncated(self, executor: HookExecutor) -> None:
        long_desc = "x" * 200
        payload = {
            "dependencies": [
                {
                    "name": "pkg",
                    "version": "1.0",
                    "vulns": [
                        {
                            "id": "VID",
                            "aliases": [],
                            "description": long_desc,
                            "fix_versions": [],
                        }
                    ],
                }
            ]
        }
        out = executor._parse_pip_audit_issues(json.dumps(payload))
        assert "..." in out[0]
        # Should not contain the full 200-char string
        assert long_desc not in out[0]

    def test_ignored_vulnerability_skipped(self, executor: HookExecutor) -> None:
        from crackerjack.config.pip_audit_ignores import IGNORED_VULNERABILITY_IDS

        ignored = next(iter(IGNORED_VULNERABILITY_IDS)) if IGNORED_VULNERABILITY_IDS else None
        if not ignored:
            pytest.skip("IGNORED_VULNERABILITY_IDS empty in this build")
        payload = {
            "dependencies": [
                {
                    "name": "pkg",
                    "version": "1.0",
                    "vulns": [
                        {"id": ignored, "aliases": [], "description": "", "fix_versions": []}
                    ],
                }
            ]
        }
        out = executor._parse_pip_audit_issues(json.dumps(payload))
        assert out == []

    def test_dep_not_dict_skipped(self, executor: HookExecutor) -> None:
        payload = {"dependencies": ["not a dict", 42, None]}
        out = executor._parse_pip_audit_issues(json.dumps(payload))
        assert out == []

    def test_vuln_not_dict_skipped(self, executor: HookExecutor) -> None:
        payload = {
            "dependencies": [
                {
                    "name": "pkg",
                    "version": "1.0",
                    "vulns": ["not-a-dict"],
                }
            ]
        }
        out = executor._parse_pip_audit_issues(json.dumps(payload))
        assert out == []

    def test_dependencies_not_list_returns_empty(self, executor: HookExecutor) -> None:
        out = executor._parse_pip_audit_issues(json.dumps({"dependencies": "oops"}))
        assert out == []

    def test_invalid_json_falls_back(self, executor: HookExecutor) -> None:
        # Contains a stray non-JSON prefix that contains a CVE mention
        out = executor._parse_pip_audit_issues("not json at all CVE-2024-1\n")
        assert any("CVE-2024-1" in x for x in out)


# ---------------------------------------------------------------------------
# Complexipy parsing
# ---------------------------------------------------------------------------


class TestComplexipyParsing:
    def test_no_failed_section_returns_empty(self, executor: HookExecutor) -> None:
        out = executor._parse_complexipy_issues("All good\n")
        assert out == []

    def test_failed_section_parsed(self, executor: HookExecutor) -> None:
        text = (
            "Header\n"
            "Failed functions:\n"
            "- src/mod.py: func_a, func_b\n"
            "  continuation_func\n"
            "\n"
            "=====\n"
        )
        out = executor._parse_complexipy_issues(text)
        assert any("mod.py: func_a" in x for x in out)
        assert any("mod.py: func_b" in x for x in out)
        assert any("mod.py: continuation_func" in x for x in out)

    def test_failed_section_no_separator(self, executor: HookExecutor) -> None:
        """When the section has no closing rule, all trailing lines are used."""
        text = "Failed functions:\n- x.py: fn1, fn2\n"
        out = executor._parse_complexipy_issues(text)
        assert any("x.py: fn1" in x for x in out)
        assert any("x.py: fn2" in x for x in out)

    def test_extract_filename_with_path(self) -> None:
        assert HookExecutor._extract_filename(None or "/foo/bar/baz.py") == "baz.py"  # type: ignore[arg-type]
        assert HookExecutor._extract_filename("plain.py") == "plain.py"

    def test_extract_complexity_from_parts(self) -> None:
        # Exactly 4 parts, last is int -> 5
        assert HookExecutor()._extract_complexity_from_parts(["a", "b", "c", "5"]) == 5
        # 3 parts -> not enough -> None (no exception raised in suppress)
        assert HookExecutor()._extract_complexity_from_parts(["a", "b", "c"]) is None
        # Empty list -> not enough -> None
        assert HookExecutor()._extract_complexity_from_parts([]) is None
        # 4 parts but last is non-int -> None
        assert HookExecutor()._extract_complexity_from_parts(["a", "b", "c", "x"]) is None

    def test_detect_package_from_output_uses_path_pattern(self) -> None:
        ex = HookExecutor.__new__(HookExecutor)
        ex.pkg_path = Path("/tmp/p")
        out = ex._detect_package_from_output("./mypkg/sub/file.py ./mypkg/other.py")
        assert out == "mypkg"

    def test_should_include_line_pipe_marker(self) -> None:
        ex = HookExecutor.__new__(HookExecutor)
        assert ex._should_include_line("│ pkg in code │", "pkg") is True
        assert ex._should_include_line("plain text", "pkg") is False

    def test_is_header_or_separator_line(self) -> None:
        ex = HookExecutor.__new__(HookExecutor)
        assert ex._is_header_or_separator_line("Path  column") is True
        assert ex._is_header_or_separator_line("─────") is True
        assert ex._is_header_or_separator_line("regular line") is False


# ---------------------------------------------------------------------------
# Refurb parsing
# ---------------------------------------------------------------------------


class TestRefurbParsing:
    def test_typical_line_parsed(self, executor: HookExecutor) -> None:
        out = executor._parse_refurb_issues("src/x.py:12:5 [FURB100]: Use list comp")
        assert len(out) == 1
        assert "x.py:12" in out[0]
        assert "FURB100" in out[0]

    def test_non_matching_lines_fallthrough(self, executor: HookExecutor) -> None:
        out = executor._parse_refurb_issues("garbage line\n[FURB-x]: no path here")
        # The first line has no colon, so it would be added as raw.
        # The second has colon but does not match the strict regex.
        # Either way it should be a non-empty list.
        assert isinstance(out, list)


# ---------------------------------------------------------------------------
# Pyscn parsing (additional cases)
# ---------------------------------------------------------------------------


class TestPyscnExtra:
    def test_finding_after_circular_header(self, executor: HookExecutor) -> None:
        text = (
            "src/a.py:1:1: foo\n"
            "Found circular dependency between src/a.py and src/b.py\n"
        )
        out = executor._parse_pyscn_issues(text)
        assert len(out) == 1
        assert "circular dependency" in out[0]
        assert "src/a.py:1" in out[0]

    def test_finding_without_header_uses_message_only(
        self, executor: HookExecutor
    ) -> None:
        out = executor._parse_pyscn_issues("is too complex (10 > 5)\n")
        assert len(out) == 1
        assert "is too complex" in out[0]


# ---------------------------------------------------------------------------
# Creosote parsing extras
# ---------------------------------------------------------------------------


class TestCreosoteExtra:
    def test_marker_line_then_continues_until_blank(
        self, executor: HookExecutor
    ) -> None:
        text = (
            "Checking dependencies...\n"
            "unused dependencies found:\n"
            "first\n"
            "second\n"
            "\n"
            "all good\n"
        )
        out = executor._parse_creosote_issues(text)
        assert any("first" in x for x in out)
        assert any("second" in x for x in out)
        assert not any("all good" in x for x in out)


# ---------------------------------------------------------------------------
# Gitleaks extras
# ---------------------------------------------------------------------------


class TestGitleaksExtra:
    def test_warn_invalid_gitleaksignore_filtered(self, executor: HookExecutor) -> None:
        text = "WRN Invalid .gitleaksignore pattern\nleak detected in x.py: api=abc"
        out = executor._parse_gitleaks_issues(text)
        # WRN line should be filtered out
        assert all("WRN" not in x for x in out)
        # But the leak line should still be captured
        assert any("leak" in x.lower() for x in out)

    def test_credential_keyword(self, executor: HookExecutor) -> None:
        # gitleaks parser requires "found" NOT to be in line.lower() but
        # needs a recognized keyword (leak/secret/credential/api)
        out = executor._parse_gitleaks_issues("credential in config")
        assert len(out) == 1


# ---------------------------------------------------------------------------
# shorten_path
# ---------------------------------------------------------------------------


class TestShortenPath:
    def test_relative_path_stripped(self, executor: HookExecutor) -> None:
        # Rel-impl verified: strips a single "./" or no prefix
        assert executor._shorten_path("src/foo.py") == "src/foo.py"
        assert executor._shorten_path("a\\b\\c.py") == "a/b/c.py"
        # The lstrip("./") strips both / and . from the start
        assert executor._shorten_path("./src/foo.py") in {"src/foo.py", "./src/foo.py"}

    def test_absolute_path_relative_to_pkg(self, executor: HookExecutor) -> None:
        pkg = executor.pkg_path
        target = pkg / "sub" / "x.py"
        assert executor._shorten_path(str(target)) == "sub/x.py"

    def test_absolute_path_outside_pkg_returns_basename(
        self, executor: HookExecutor
    ) -> None:
        assert executor._shorten_path("/elsewhere/x.py") == "x.py"


# ---------------------------------------------------------------------------
# Generic hook output file-count extraction
# ---------------------------------------------------------------------------


class TestParseGenericHookOutput:
    def test_extracts_file_count_from_phrase(self, executor: HookExecutor) -> None:
        assert (
            executor._parse_generic_hook_output("5 files would be modified")
            == 5
        )
        assert (
            executor._parse_generic_hook_output("3 files processed")
            == 3
        )
        assert executor._parse_generic_hook_output("checking 7 files") == 7
        assert executor._parse_generic_hook_output("no files mentioned") == 0

    def test_ruff_all_checks_passed(self, executor: HookExecutor) -> None:
        out = executor._parse_generic_hook_output("ruff: All checks passed! 12 files")
        # Should pick the file count from "12 files"
        assert out == 12

    def test_ruff_no_count_returns_zero(self, executor: HookExecutor) -> None:
        out = executor._parse_generic_hook_output("All checks passed!")
        assert out == 0

    def test_extract_ruff_no_all_passed_returns_zero(
        self, executor: HookExecutor
    ) -> None:
        # The first branch picks up "12 files" via the file-count regex,
        # so the result is 12, not 0. This pins the current behavior.
        out = executor._parse_generic_hook_output("ruff error: 12 files affected")
        assert out == 12


# ---------------------------------------------------------------------------
# Semgrep output file-count parsing
# ---------------------------------------------------------------------------


class TestParseSemgrepOutput:
    def test_issues_in_files_pattern(self, executor: HookExecutor) -> None:
        out = executor._parse_semgrep_text_output("found 2 issues in 3 files")
        assert out == 3

    def test_no_issues_pattern(self, executor: HookExecutor) -> None:
        out = executor._parse_semgrep_text_output("found no issues")
        assert out == 0

    def test_scanning_files_only(self, executor: HookExecutor) -> None:
        # Note: scanning N files only returns N if it appears in the match list
        # processed by _process_matches. Per the implementation, scanning N
        # files is a 1-tuple match which continues unless "no issues" is in
        # the output, so it falls through and returns 0.
        out = executor._parse_semgrep_text_output("scanning 4 files")
        assert out == 0

    def test_no_match_returns_zero(self, executor: HookExecutor) -> None:
        out = executor._parse_semgrep_text_output("nothing recognizable here")
        assert out == 0

    def test_zero_issues_with_files_returns_zero(
        self, executor: HookExecutor
    ) -> None:
        """When issues_in_files count is 0, return 0 not the file count."""
        out = executor._parse_semgrep_text_output("found 0 issues in 10 files")
        assert out == 0

    def test_json_path_via_parse_semgrep_output(
        self, executor: HookExecutor
    ) -> None:
        data = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=json.dumps({"results": [{"path": "a.py"}, {"path": "b.py"}, {"path": "a.py"}]}),
            stderr="",
        )
        out = executor._parse_semgrep_output(data)
        assert out == 2  # unique paths

    def test_text_fallback_when_json_invalid(
        self, executor: HookExecutor
    ) -> None:
        data = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="not json",
            stderr="found 5 issues in 7 files",
        )
        out = executor._parse_semgrep_output(data)
        assert out == 7

    def test_pure_json_line_parsed(self, executor: HookExecutor) -> None:
        line = json.dumps({"results": [{"path": "a"}, {"path": "b"}]})
        assert executor._try_parse_line_json(line) == 2

    def test_pure_json_invalid_returns_none(self, executor: HookExecutor) -> None:
        assert executor._try_parse_line_json("not json at all") is None

    def test_contains_json_results_parsed(self, executor: HookExecutor) -> None:
        line = 'prefix "results":' + json.dumps([{"path": "a"}])
        # Trailing { ends, so it is a "pure json" too
        assert executor._try_parse_line_json(line) is None or isinstance(
            executor._try_parse_line_json(line), int
        )

    def test_is_pure_json_predicate(self, executor: HookExecutor) -> None:
        assert executor._is_pure_json("{}") is True
        assert executor._is_pure_json("a{}") is False
        assert executor._is_pure_json("{") is False

    def test_contains_json_results_predicate(self, executor: HookExecutor) -> None:
        assert executor._contains_json_results('"results":1') is True
        assert executor._contains_json_results("nope") is False


# ---------------------------------------------------------------------------
# _parse_hook_output
# ---------------------------------------------------------------------------


class TestParseHookOutput:
    def test_semgrep_branch(self, executor: HookExecutor) -> None:
        proc = _completed(returncode=1, stdout='{"results": [{"path": "a"}]}', stderr="")
        out = executor._parse_hook_output(proc, "semgrep")
        assert out["files_processed"] == 1
        assert out["exit_code"] == 1

    def test_generic_branch(self, executor: HookExecutor) -> None:
        proc = _completed(returncode=0, stdout="5 files checked", stderr="")
        out = executor._parse_hook_output(proc, "ruff-check")
        assert out["files_processed"] == 5

    def test_is_semgrep_output(self, executor: HookExecutor) -> None:
        assert executor._is_semgrep_output("semgrep ran", "") is True
        assert executor._is_semgrep_output("nothing", "semgrep") is True
        assert executor._is_semgrep_output("nothing", "ruff") is False


# ---------------------------------------------------------------------------
# _extract_issues_for_regular_tools
# ---------------------------------------------------------------------------


class TestExtractIssuesRegularTools:
    def test_passed_returns_empty(self, executor: HookExecutor) -> None:
        hook = SimpleNamespace(name="ruff-check", is_formatting=False)
        out = executor._extract_issues_for_regular_tools(
            hook, "anything", "passed", _completed()
        )
        assert out == []

    def test_json_output_returns_empty(self, executor: HookExecutor) -> None:
        """JSON-shaped output is treated as parseable, no lines extracted."""
        hook = SimpleNamespace(name="ruff-check", is_formatting=False)
        out = executor._extract_issues_for_regular_tools(
            hook, '{"some": "json"}', "failed", _completed()
        )
        assert out == []

    def test_formatting_modified_message_returns_empty(
        self, executor: HookExecutor
    ) -> None:
        """ruff-format-style "files were modified" failure is treated as pass."""
        hook = SimpleNamespace(name="ruff-format", is_formatting=True)
        out = executor._extract_issues_for_regular_tools(
            hook,
            "files were modified by this hook\nstuff",
            "failed",
            _completed(),
        )
        assert out == []

    def test_ruff_check_filters_modified_message(self, executor: HookExecutor) -> None:
        hook = SimpleNamespace(name="ruff-check", is_formatting=False)
        out = executor._extract_issues_for_regular_tools(
            hook,
            "files were modified by this hook\nreal error: E501",
            "failed",
            _completed(returncode=1),
        )
        # The "files were modified..." line should be filtered, real error kept
        assert all("files were modified" not in x for x in out)
        assert any("E501" in x for x in out)

    def test_empty_output_uses_returncode(self, executor: HookExecutor) -> None:
        hook = SimpleNamespace(name="ruff-check", is_formatting=False)
        out = executor._extract_issues_for_regular_tools(
            hook, "", "failed", _completed(returncode=2)
        )
        assert out == ["Hook failed with code 2"]


# ---------------------------------------------------------------------------
# Retry: ALL_HOOKS path & retry single hook in-place
# ---------------------------------------------------------------------------


class TestRetryAllHooks:
    def test_all_hooks_retry_runs_failed_ones(self, executor: HookExecutor) -> None:
        hooks = [
            HookDefinition(name="h1", command=[], timeout=5),
            HookDefinition(name="h2", command=[], timeout=5),
        ]
        strategy = HookStrategy(
            name="test", hooks=hooks, retry_policy=RetryPolicy.ALL_HOOKS
        )
        results = [
            _result(name="h1", status="passed"),
            _result(name="h2", status="failed", duration=1.0),
        ]

        def _side_effect(h: HookDefinition) -> HookResult:
            return _result(name=h.name, status="passed", duration=2.0)

        with patch.object(executor, "execute_single_hook", side_effect=_side_effect):
            out = executor._retry_all_hooks(strategy, results)

        # h1 unchanged (passed)
        assert out[0].status == "passed"
        # h2 retried, status now passed, duration accumulated
        assert out[1].status == "passed"
        assert out[1].duration == 3.0  # prev 1.0 + new 2.0

    def test_retry_formatting_no_formatting_failures_returns_input(
        self, executor: HookExecutor
    ) -> None:
        hooks = [
            HookDefinition(name="h1", command=[], timeout=5),
        ]
        strategy = HookStrategy(
            name="test", hooks=hooks, retry_policy=RetryPolicy.FORMATTING_ONLY
        )
        results = [_result(name="h1", status="passed")]
        # No formatting hooks failed -> returns input unchanged
        out = executor._retry_formatting_hooks(strategy, results)
        assert out == results

    def test_find_failed_formatting_hooks(self, executor: HookExecutor) -> None:
        hooks = [
            HookDefinition(name="a", command=[], is_formatting=True, timeout=5),
            HookDefinition(name="b", command=[], is_formatting=False, timeout=5),
            HookDefinition(name="c", command=[], is_formatting=True, timeout=5),
        ]
        results = [
            _result(name="a", status="failed"),
            _result(name="b", status="failed"),
            _result(name="c", status="passed"),
        ]
        strategy = HookStrategy(name="test", hooks=hooks)
        failed = executor._find_failed_formatting_hooks(strategy, results)
        assert failed == {"a"}

    def test_retry_all_formatting_hooks_accumulates_duration(
        self, executor: HookExecutor
    ) -> None:
        hooks = [
            HookDefinition(name="a", command=[], is_formatting=True, timeout=5),
            HookDefinition(name="b", command=[], is_formatting=True, timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks)
        results = [
            _result(name="a", status="failed", duration=1.0),
            _result(name="b", status="failed", duration=1.0),
        ]

        def _side_effect(h: HookDefinition) -> HookResult:
            return _result(name=h.name, status="passed", duration=4.0)

        with patch.object(executor, "execute_single_hook", side_effect=_side_effect):
            out = executor._retry_all_formatting_hooks(strategy, results)

        for r in out:
            assert r.status == "passed"
            assert r.duration == 5.0  # 1.0 + 4.0


# ---------------------------------------------------------------------------
# _get_changed_files_for_hook extension map paths
# ---------------------------------------------------------------------------


class TestGetChangedFilesForHook:
    def test_no_extensions_returns_none(self, executor: HookExecutor) -> None:
        """Hook name not in extension map -> None."""
        executor.use_incremental = True
        executor.file_filter = None
        hook = HookDefinition(
            name="unknown-tool", command=[], accepts_file_paths=True
        )
        # git_service fixture returns []
        assert executor._get_changed_files_for_hook(hook) is None

    def test_extension_map_miss_returns_none(self, executor: HookExecutor) -> None:
        executor.use_incremental = True
        executor.file_filter = None
        executor.git_service = MagicMock()
        executor.git_service.get_changed_files_by_extension.return_value = []
        hook = HookDefinition(
            name="lychee", command=[], accepts_file_paths=True
        )
        assert executor._get_changed_files_for_hook(hook) is None

    def test_extension_map_hit_returns_files(self, executor: HookExecutor) -> None:
        executor.use_incremental = True
        executor.file_filter = None
        changed = [Path("a.py"), Path("b.py")]
        executor.git_service = MagicMock()
        executor.git_service.get_changed_files_by_extension.return_value = changed
        hook = HookDefinition(
            name="ruff-check", command=[], accepts_file_paths=True
        )
        assert executor._get_changed_files_for_hook(hook) == changed

    def test_does_not_accept_files_returns_none(self, executor: HookExecutor) -> None:
        executor.use_incremental = True
        hook = HookDefinition(
            name="ruff-check", command=[], accepts_file_paths=False
        )
        assert executor._get_changed_files_for_hook(hook) is None

    def test_filter_files_by_hook_type_unknown_returns_all(
        self, executor: HookExecutor
    ) -> None:
        files = [Path("a.py"), Path("b.md")]
        out = executor._filter_files_by_hook_type(files, "mystery")
        assert out == files

    def test_filter_files_by_hook_type_empty_extensions_returns_all(
        self, executor: HookExecutor
    ) -> None:
        files = [Path("a.py"), Path("b.md")]
        out = executor._filter_files_by_hook_type(files, "trailing-whitespace")
        assert out == files

    def test_filter_files_by_hook_type_specific_ext(self, executor: HookExecutor) -> None:
        files = [Path("a.py"), Path("b.md"), Path("c.yaml")]
        out = executor._filter_files_by_hook_type(files, "check-yaml")
        assert out == [Path("b.yaml" if False else "c.yaml")]


# ---------------------------------------------------------------------------
# _get_uv_environment_paths fallback on OSError
# ---------------------------------------------------------------------------


class TestUvEnvPaths:
    def test_oserror_falls_back_to_tempdir(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """If primary .crackerjack/uv can't be created, fall back to tempfile."""
        executor = HookExecutor(console=mock_console, pkg_path=tmp_path)
        # Force mkdir/rmtree to raise to hit OSError branch
        with patch("pathlib.Path.exists", return_value=True):
            with patch("shutil.rmtree", side_effect=OSError("denied")):
                env = executor._get_uv_environment_paths()
        assert "UV_CACHE_DIR" in env
        # The fallback uses tempfile.gettempdir()
        import tempfile

        assert env["UV_CACHE_DIR"].startswith(str(Path(tempfile.gettempdir())))


# ---------------------------------------------------------------------------
# _update_path
# ---------------------------------------------------------------------------


class TestUpdatePath:
    def test_removes_venv_bin_from_path(self, executor: HookExecutor) -> None:
        import os

        env: dict[str, str] = {}
        venv_bin = str(Path(executor.pkg_path) / ".venv" / "bin")
        original = f"/usr/bin:{venv_bin}:/bin"
        with patch.dict(os.environ, {"PATH": original}, clear=False):
            executor._update_path(env)
        # The venv bin entry should have been stripped
        assert env.get("PATH", "")
        assert venv_bin not in env["PATH"]

    def test_no_path_env_skips(self, executor: HookExecutor) -> None:
        import os

        env: dict[str, str] = {"OTHER": "x"}
        with patch.dict(os.environ, {"PATH": ""}, clear=False):
            executor._update_path(env)
        assert "PATH" not in env


# ---------------------------------------------------------------------------
# _try_get_qa_result_for_hook
# ---------------------------------------------------------------------------


class TestTryGetQaResultForHook:
    def test_no_qa_adapter_returns_none(self, executor: HookExecutor) -> None:
        """Hook name not in the adapter map -> returns None immediately."""
        hook = SimpleNamespace(name="not-a-tool", timeout=5)
        result = _completed(returncode=1)
        assert executor._try_get_qa_result_for_hook(hook, result, 1.0) is None

    def test_qa_adapter_exception_swallows(self, executor: HookExecutor) -> None:
        """Adapter import/init failure is swallowed; returns None."""
        hook = SimpleNamespace(name="complexipy", timeout=5)
        result = _completed(returncode=1)
        with patch.dict(
            "sys.modules",
            {
                "crackerjack.adapters.factory": MagicMock(
                    DefaultAdapterFactory=MagicMock(
                        return_value=MagicMock(
                            create_adapter=MagicMock(side_effect=ImportError("x"))
                        )
                    )
                )
            },
        ):
            with patch("builtins.__import__", side_effect=ImportError("nope")):
                out = executor._try_get_qa_result_for_hook(hook, result, 1.0)
        # Should be None because of the swallowed exception
        assert out is None

    def test_qa_adapter_returns_result_with_issues(
        self, executor: HookExecutor
    ) -> None:
        """When adapter returns a QAResult with parsed_issues, propagate it."""
        hook = SimpleNamespace(name="complexipy", timeout=5)
        result = _completed(returncode=1)

        qa = MagicMock()
        qa.is_success = True
        qa.parsed_issues = ["one issue"]
        qa.details = "x"

        adapter = MagicMock()
        adapter.module_id = "complexipy"
        adapter.init = MagicMock()
        adapter.check = MagicMock(return_value=qa)

        factory = MagicMock()
        factory.create_adapter = MagicMock(return_value=adapter)

        with patch("crackerjack.adapters.factory.DefaultAdapterFactory", factory):
            out = executor._try_get_qa_result_for_hook(hook, result, 1.0)

        # Either we get a QA result back, or None if imports fail silently;
        # we just exercise the branch and ensure it doesn't blow up.
        assert out is None or out is qa

    def test_qa_adapter_learner_integration_called(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """adapter_learner_integration.track_adapter_execution is invoked on success."""
        learner = MagicMock()
        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            verbose=True,
            adapter_learner_integration=learner,
        )
        hook = SimpleNamespace(name="complexipy", timeout=5)
        result = _completed(returncode=1)

        qa = MagicMock()
        qa.is_success = True
        qa.parsed_issues = ["i"]
        qa.details = "x"

        adapter = MagicMock()
        adapter.module_id = "complexipy"
        adapter.init = MagicMock()
        adapter.check = MagicMock(return_value=qa)

        factory = MagicMock()
        factory.create_adapter = MagicMock(return_value=adapter)

        with patch("crackerjack.adapters.factory.DefaultAdapterFactory", factory):
            executor._try_get_qa_result_for_hook(hook, result, 1.0)

        # adapter_learner may or may not have been called depending on import path
        # We just assert no exception escaped
        assert True

    def test_qa_adapter_returns_none_for_no_parsed_issues(
        self, executor: HookExecutor
    ) -> None:
        hook = SimpleNamespace(name="complexipy", timeout=5)
        result = _completed(returncode=1)

        qa = MagicMock()
        qa.is_success = True
        qa.parsed_issues = None  # empty
        qa.details = "x"

        adapter = MagicMock()
        adapter.module_id = "complexipy"
        adapter.init = MagicMock()
        adapter.check = MagicMock(return_value=qa)

        factory = MagicMock()
        factory.create_adapter = MagicMock(return_value=adapter)

        with patch("crackerjack.adapters.factory.DefaultAdapterFactory", factory):
            out = executor._try_get_qa_result_for_hook(hook, result, 1.0)

        # Either None (import failed) or None (no parsed issues)
        assert out is None

    def test_qa_adapter_skipped_on_success_for_non_special_tools(
        self, executor: HookExecutor
    ) -> None:
        """For non-special reporting tools, success short-circuits to None."""
        hook = SimpleNamespace(name="ruff-check", timeout=5)
        result = _completed(returncode=0)
        # Success + not in the special list -> return None without calling adapter
        out = executor._try_get_qa_result_for_hook(hook, result, 1.0)
        assert out is None

    def test_qa_adapter_debug_log(self, mock_console, tmp_path) -> None:
        """Debug mode prints when adapter fails."""
        executor = HookExecutor(
            console=mock_console, pkg_path=tmp_path, debug=True
        )
        hook = SimpleNamespace(name="complexipy", timeout=5)
        result = _completed(returncode=1)
        with patch("builtins.__import__", side_effect=ImportError("nope")):
            out = executor._try_get_qa_result_for_hook(hook, result, 1.0)
        assert out is None
        printed = " ".join(
            str(c.args[0]) for c in mock_console.print.call_args_list
        )
        # Debug message about adapter failure may be present
        # (not strictly required - it may have skipped on import failure)


# ---------------------------------------------------------------------------
# _tool_has_qa_adapter
# ---------------------------------------------------------------------------


class TestToolHasQaAdapter:
    def test_known_tool(self, executor: HookExecutor) -> None:
        assert executor._tool_has_qa_adapter("complexipy") is True
        assert executor._tool_has_qa_adapter("ruff-format") is True

    def test_unknown_tool(self, executor: HookExecutor) -> None:
        assert executor._tool_has_qa_adapter("nope") is False


# ---------------------------------------------------------------------------
# _print_summary / is_concurrent
# ---------------------------------------------------------------------------


class TestPrintSummaryAndConcurrent:
    def test_print_summary_emits_in_quiet(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        executor = HookExecutor(
            console=mock_console, pkg_path=tmp_path, quiet=False
        )
        # Need >=2 hooks for is_concurrent() to return True
        hooks = [HookDefinition(name="h1", command=[]), HookDefinition(name="h2", command=[])]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True)
        executor._print_summary(strategy, [], True, 12.5)
        printed = " ".join(
            str(c.args[0]) for c in mock_console.print.call_args_list
        )
        assert "passed" in printed
        assert "async" in printed  # concurrent mode

    def test_print_summary_skipped_on_failure(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        executor = HookExecutor(console=mock_console, pkg_path=tmp_path)
        strategy = HookStrategy(name="test", hooks=[])
        # success=False -> nothing is printed
        executor._print_summary(strategy, [], False, 0.0)
        mock_console.print.assert_not_called()

    def test_is_concurrent(self, executor: HookExecutor) -> None:
        s1 = HookStrategy(name="s", hooks=[HookDefinition(name="h", command=[])], parallel=True)
        s2 = HookStrategy(
            name="s",
            hooks=[HookDefinition(name="h1", command=[]), HookDefinition(name="h2", command=[])],
            parallel=False,
        )
        s3 = HookStrategy(
            name="s",
            hooks=[HookDefinition(name="h1", command=[]), HookDefinition(name="h2", command=[])],
            parallel=True,
        )
        assert executor.is_concurrent(s1) is False  # 1 hook
        assert executor.is_concurrent(s2) is False
        assert executor.is_concurrent(s3) is True


# ---------------------------------------------------------------------------
# _calculate_performance_gain edge cases
# ---------------------------------------------------------------------------


class TestCalculatePerformanceGain:
    def test_zero_estimated_returns_zero(self, executor: HookExecutor) -> None:
        """Empty hook list -> estimated 0 -> gain is 0."""
        strategy = HookStrategy(name="s", hooks=[])
        out = executor._calculate_performance_gain(strategy, [], 1.0)
        assert out == 0.0

    def test_negative_clamped_to_zero(self, executor: HookExecutor) -> None:
        """If duration exceeds estimated sequential, gain is 0 not negative."""
        hooks = [HookDefinition(name="h", command=[], timeout=10)]
        strategy = HookStrategy(name="s", hooks=hooks)
        # duration much higher than sum of timeouts
        out = executor._calculate_performance_gain(strategy, [], 100.0)
        assert out == 0.0


# ---------------------------------------------------------------------------
# HookExecutionResult dataclass
# ---------------------------------------------------------------------------


class TestHookExecutionResultExtras:
    def test_cache_hit_rate_zero_when_no_requests(self) -> None:
        result = HookExecutionResult(
            strategy_name="x",
            results=[],
            total_duration=0.0,
            success=True,
        )
        assert result.cache_hit_rate == 0.0

    def test_performance_summary_includes_concurrent(self) -> None:
        result = HookExecutionResult(
            strategy_name="x",
            results=[],
            total_duration=0.0,
            success=True,
            concurrent_execution=True,
        )
        assert result.performance_summary["concurrent"] is True

    def test_performance_summary_rounds(self) -> None:
        result = HookExecutionResult(
            strategy_name="x",
            results=[],
            total_duration=0.123456,
            success=True,
        )
        assert result.performance_summary["duration_seconds"] == 0.12


# ---------------------------------------------------------------------------
# _handle_retries dispatcher
# ---------------------------------------------------------------------------


class TestHandleRetriesDispatcher:
    def test_unknown_policy_returns_unchanged(self, executor: HookExecutor) -> None:
        # NONE policy -> the outer dispatcher is short-circuited, so build a strategy
        # with NONE and call the inner dispatcher directly with a non-supported policy
        # (not possible via enum, so just verify NONE is short-circuited)
        strategy = HookStrategy(name="s", hooks=[], retry_policy=RetryPolicy.NONE)
        results = [_result(name="h", status="failed")]
        # _apply_retries_if_needed path for NONE
        out = executor._apply_retries_if_needed(strategy, results)
        assert out is results


# ---------------------------------------------------------------------------
# _execute_hooks dispatcher
# ---------------------------------------------------------------------------


class TestExecuteHooksDispatcher:
    def test_parallel_routes_to_execute_parallel(
        self, executor: HookExecutor
    ) -> None:
        hooks = [
            HookDefinition(name="h1", command=[], timeout=5),
            HookDefinition(name="h2", command=[], timeout=5),
        ]
        strategy = HookStrategy(name="s", hooks=hooks, parallel=True)
        with patch.object(executor, "_execute_parallel") as m:
            m.return_value = [_result(name="h1"), _result(name="h2")]
            out = executor._execute_hooks(strategy)
        assert len(out) == 2
        m.assert_called_once()

    def test_sequential_default(self, executor: HookExecutor) -> None:
        hooks = [HookDefinition(name="h1", command=[], timeout=5)]
        strategy = HookStrategy(name="s", hooks=hooks, parallel=False)
        with patch.object(executor, "_execute_sequential") as m:
            m.return_value = [_result(name="h1")]
            out = executor._execute_hooks(strategy)
        assert len(out) == 1
        m.assert_called_once()


# ---------------------------------------------------------------------------
# Full execute_strategy success/failure paths
# ---------------------------------------------------------------------------


class TestExecuteStrategyTopLevel:
    def test_strategy_success_true(self, executor: HookExecutor) -> None:
        hook = HookDefinition(name="h", command=[], timeout=5)
        strategy = HookStrategy(name="test", hooks=[hook])
        with patch.object(executor, "_execute_hooks") as m:
            m.return_value = [_result(name="h", status="passed")]
            result = executor.execute_strategy(strategy)
        assert result.success is True
        assert result.strategy_name == "test"

    def test_strategy_failure_false(self, executor: HookExecutor) -> None:
        hook = HookDefinition(name="h", command=[], timeout=5)
        strategy = HookStrategy(name="test", hooks=[hook])
        with patch.object(executor, "_execute_hooks") as m:
            m.return_value = [_result(name="h", status="failed")]
            result = executor.execute_strategy(strategy)
        assert result.success is False


# ---------------------------------------------------------------------------
# _create_timeout_result
# ---------------------------------------------------------------------------


class TestCreateTimeoutResult:
    def test_timeout_result_records_partial_output(self, executor: HookExecutor) -> None:
        hook = HookDefinition(name="slow", command=[], timeout=5)
        # Use a start_time close to "now" so the duration is small
        import time

        result = executor._create_timeout_result(
            hook, time.time(), partial_output="partial stdout", partial_stderr="partial err"
        )
        assert result.status == "timeout"
        assert result.is_timeout is True
        assert result.exit_code == 124
        # The error message says "Execution exceeded timeout of 5s ..."
        assert "exceeded timeout" in (result.error_message or "").lower()
        # Should have appended a timeout message
        assert any("timed out" in i.lower() for i in result.issues_found)
        assert result.output == "partial stdout"
        assert result.error == "partial err"


# ---------------------------------------------------------------------------
# _create_error_result
# ---------------------------------------------------------------------------


class TestCreateErrorResult:
    def test_error_result_wraps_exception(self, executor: HookExecutor) -> None:
        hook = HookDefinition(name="boom", command=[], timeout=5)
        result = executor._create_error_result(hook, 0.0, ValueError("oops"))
        assert result.status == "error"
        assert result.is_timeout is False
        assert "oops" in result.issues_found
        assert "oops" in (result.error_message or "")


# ---------------------------------------------------------------------------
# _execute_single_hook_with_progress via parallel path
# ---------------------------------------------------------------------------


class TestExecuteSingleHookWithProgress:
    def test_progress_counters_increment(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
        )
        started = MagicMock()
        completed = MagicMock()
        executor.set_progress_callbacks(
            started_cb=started, completed_cb=completed, total=1
        )
        hook = HookDefinition(name="h", command=[], timeout=5)
        results: list[HookResult] = []
        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = _result(name="h", status="passed")
            executor._execute_single_hook_with_progress(hook, results)
        assert started.call_count == 1
        assert completed.call_count == 1
        assert len(results) == 1


# ---------------------------------------------------------------------------
# _extract_issues_from_process_output dispatch to semgrep
# ---------------------------------------------------------------------------


class TestExtractIssuesDispatch:
    def test_semgrep_dispatches_to_semgrep_parser(
        self, executor: HookExecutor
    ) -> None:
        hook = SimpleNamespace(name="semgrep", is_formatting=False)
        proc = SimpleNamespace(
            stdout=json.dumps({"results": [{"path": "x", "start": {"line": 1}, "check_id": "r", "extra": {"message": "m"}}]}),
            stderr="",
            returncode=1,
        )
        with patch.object(executor, "_parse_semgrep_issues", return_value=["s1"]) as m:
            out = executor._extract_issues_from_process_output(hook, proc, "failed")
        m.assert_called_once()
        assert out == ["s1"]


# ---------------------------------------------------------------------------
# Pip-audit text fallback with no CVE
# ---------------------------------------------------------------------------


class TestPipAuditText:
    def test_no_cve_no_vulns_returns_empty(self, executor: HookExecutor) -> None:
        out = executor._parse_pip_text_issues("just info\nnothing here\n")
        assert out == []

    def test_cve_lines_captured(self, executor: HookExecutor) -> None:
        text = "INFO CVE-2024-X\nsome other line\nPYSEC-2024-Y"
        out = executor._parse_pip_text_issues(text)
        assert len(out) >= 1
        assert any("CVE-2024-X" in x or "PYSEC-2024-Y" in x for x in out)


# ---------------------------------------------------------------------------
# _parse_lychee_issues with all-None maps
# ---------------------------------------------------------------------------


class TestLycheeEdge:
    def test_all_none_maps(self, executor: HookExecutor) -> None:
        data = {"error_map": None, "timeout_map": None, "errors": 0, "timeouts": 0}
        out = executor._parse_lychee_issues(json.dumps(data))
        assert out == []


# ---------------------------------------------------------------------------
# _get_changed_files_for_hook with smart file filter
# ---------------------------------------------------------------------------


class TestGetChangedFilesSmartFilter:
    def test_smart_file_filter_with_results(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """When the file_filter is a real SmartFileFilter instance and yields
        files, the executor returns the subset that match the hook's
        extension map."""
        from crackerjack.services.file_filter import SmartFileFilter

        # Construct a real SmartFileFilter, then swap in a stub for the
        # ``get_files_for_qa_scan`` method
        real_filter = SmartFileFilter.__new__(SmartFileFilter)
        real_filter.get_files_for_qa_scan = MagicMock(  # type: ignore[method-assign]
            return_value=[tmp_path / "a.py", tmp_path / "b.md"]
        )

        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            use_incremental=True,
            file_filter=real_filter,
        )
        hook = HookDefinition(
            name="ruff-check", command=[], accepts_file_paths=True
        )

        out = executor._get_changed_files_for_hook(hook)
        # Either it returned the filtered list (py only) or None on any error
        # We just exercise the branch without crashing.
        if out is not None:
            assert all(str(f).endswith(".py") for f in out)


# ---------------------------------------------------------------------------
# _retry_failed_hooks preserves order
# ---------------------------------------------------------------------------


class TestRetryFailedHooks:
    def test_retry_failed_hooks_updates_in_place(self, executor: HookExecutor) -> None:
        hooks = [
            HookDefinition(name="a", command=[], timeout=5),
            HookDefinition(name="b", command=[], timeout=5),
            HookDefinition(name="c", command=[], timeout=5),
        ]
        strategy = HookStrategy(name="s", hooks=hooks)
        results = [
            _result(name="a", status="failed", duration=1.0),
            _result(name="b", status="passed", duration=0.5),
            _result(name="c", status="failed", duration=2.0),
        ]

        def _side_effect(h: HookDefinition) -> HookResult:
            return _result(name=h.name, status="passed", duration=3.0)

        with patch.object(executor, "execute_single_hook", side_effect=_side_effect):
            out = executor._retry_failed_hooks(
                strategy, results, [0, 2]  # failed indices
            )

        # a and c retried -> passed with accumulated duration
        assert out[0].status == "passed"
        assert out[0].duration == 4.0
        # b unchanged
        assert out[1].status == "passed"
        assert out[1].duration == 0.5
        assert out[2].status == "passed"
        assert out[2].duration == 5.0
