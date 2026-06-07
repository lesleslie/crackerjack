"""Comprehensive tests for hook_executor.py module.

Tests the core HookExecutor class that handles hook execution logic.
"""

import asyncio
import subprocess
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
from crackerjack.executors.hook_executor import HookExecutor, HookExecutionResult
from crackerjack.models.task import HookResult


class TestHookExecutionResult:
    """Tests for HookExecutionResult dataclass."""

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
        ]

        result = HookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=3.0,
            success=False,
            cache_hits=5,
            cache_misses=2,
            performance_gain=25.0,
        )

        assert result.failed_count == 1
        assert result.passed_count == 1
        assert result.cache_hit_rate == pytest.approx(71.43, rel=0.1)

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

        result = HookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=1.0,
            success=True,
        )

        summary = result.performance_summary
        assert summary["total_hooks"] == 1
        assert summary["passed"] == 1
        assert summary["failed"] == 0
        assert summary["concurrent"] is False


class TestHookExecutor:
    """Tests for the main HookExecutor class."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        """Create a mock console."""
        console = MagicMock()
        console.print = MagicMock()
        return console

    @pytest.fixture
    def mock_git_service(self) -> MagicMock:
        """Create a mock git service."""
        git = MagicMock()
        git.get_changed_files_by_extension.return_value = []
        return git

    @pytest.fixture
    def executor(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
        mock_git_service: MagicMock,
    ) -> HookExecutor:
        """Create a HookExecutor instance for testing."""
        return HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            verbose=False,
            quiet=False,
            debug=False,
            git_service=mock_git_service,
        )

    def test_init(self, mock_console: MagicMock, tmp_path: Path) -> None:
        """Test HookExecutor initialization."""
        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
            verbose=True,
            quiet=True,
            debug=True,
        )

        assert executor.console is mock_console
        assert executor.pkg_path == tmp_path
        assert executor.verbose is True
        assert executor.quiet is True
        assert executor.debug is True

    def test_set_progress_callbacks(self, executor: HookExecutor) -> None:
        """Test progress callback setup."""
        started_cb = MagicMock()
        completed_cb = MagicMock()

        executor.set_progress_callbacks(
            started_cb=started_cb,
            completed_cb=completed_cb,
            total=10,
        )

        assert executor._progress_start_callback is started_cb
        assert executor._progress_callback is completed_cb
        assert executor._total_hooks == 10

    @pytest.mark.parametrize("retry_policy,expected", [
        (RetryPolicy.NONE, False),
        (RetryPolicy.FORMATTING_ONLY, True),
        (RetryPolicy.ALL_HOOKS, True),
    ])
    def test_execute_strategy_retries(
        self,
        executor: HookExecutor,
        retry_policy: RetryPolicy,
        expected: bool,
    ) -> None:
        """Test retry policy handling in execute_strategy."""
        hook = HookDefinition(
            name="test-hook",
            command=["echo", "test"],
            timeout=5,
        )
        strategy = HookStrategy(
            name="test",
            hooks=[hook],
            retry_policy=retry_policy,
        )

        with patch.object(executor, "_execute_hooks") as mock_exec:
            mock_exec.return_value = [
                HookResult(id="1", name="test-hook", status="passed", duration=1.0),
            ]
            result = executor.execute_strategy(strategy)

            if retry_policy != RetryPolicy.NONE:
                mock_exec.assert_called_once()

    def test_execute_sequential(self, executor: HookExecutor) -> None:
        """Test sequential execution of hooks."""
        hooks = [
            HookDefinition(name="hook1", command=["echo", "1"], timeout=5),
            HookDefinition(name="hook2", command=["echo", "2"], timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=False)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.side_effect = [
                HookResult(id="1", name="hook1", status="passed", duration=1.0),
                HookResult(id="2", name="hook2", status="passed", duration=1.0),
            ]

            results = executor._execute_sequential(strategy)

            assert len(results) == 2
            assert mock_exec.call_count == 2

    def test_execute_parallel(self, executor: HookExecutor) -> None:
        """Test parallel execution of hooks."""
        hooks = [
            HookDefinition(name="hook1", command=["echo", "1"], timeout=5, is_formatting=False),
            HookDefinition(name="hook2", command=["echo", "2"], timeout=5, is_formatting=False),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, parallel=True)

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = HookResult(id="1", name="hook1", status="passed", duration=1.0)

            executor._execute_parallel(strategy)

    def test_categorize_hooks(self, executor: HookExecutor) -> None:
        """Test hook categorization (enabled vs skipped)."""
        hooks = [
            HookDefinition(name="enabled", command=["echo", "1"], disabled=False),
            HookDefinition(name="disabled", command=["echo", "2"], disabled=True),
        ]
        strategy = HookStrategy(name="test", hooks=hooks)

        enabled, skipped = executor._categorize_hooks(strategy)

        assert len(enabled) == 1
        assert len(skipped) == 1
        assert enabled[0].name == "enabled"
        assert skipped[0].name == "disabled"

    def test_categorize_hooks_with_force_enable(
        self,
        executor: HookExecutor,
    ) -> None:
        """Test force-enabled hooks when disabled but in enable_hooks list."""
        executor.enable_hooks = {"disabled-hook"}

        hooks = [
            HookDefinition(name="disabled-hook", command=["echo", "1"], disabled=True),
        ]
        strategy = HookStrategy(name="test", hooks=hooks)

        enabled, skipped = executor._categorize_hooks(strategy)

        assert len(enabled) == 1
        assert len(skipped) == 0

    def test_execute_single_hook_success(self, executor: HookExecutor) -> None:
        """Test successful hook execution."""
        hook = HookDefinition(
            name="test-hook",
            command=["echo", "success"],
            timeout=5,
        )

        with patch.object(executor, "_run_hook_subprocess") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="",
                stderr="",
            )

            result = executor.execute_single_hook(hook)

            assert result.status == "passed"
            assert result.name == "test-hook"

    def test_execute_single_hook_failure(self, executor: HookExecutor) -> None:
        """Test failed hook execution."""
        hook = HookDefinition(
            name="test-hook",
            command=["echo", "fail"],
            timeout=5,
        )

        with patch.object(executor, "_run_hook_subprocess") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="Error: something went wrong",
            )

            result = executor.execute_single_hook(hook)

            assert result.status == "failed"

    def test_execute_single_hook_timeout(self, executor: HookExecutor) -> None:
        """Test hook timeout handling."""
        hook = HookDefinition(
            name="test-hook",
            command=["sleep", "10"],
            timeout=1,
        )

        with patch.object(executor, "_run_hook_subprocess") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=[],
                timeout=1,
            )

            result = executor.execute_single_hook(hook)

            assert result.status == "timeout"
            assert result.is_timeout is True

    def test_execute_single_hook_error(self, executor: HookExecutor) -> None:
        """Test hook execution error handling."""
        hook = HookDefinition(
            name="test-hook",
            command=["invalid-command"],
            timeout=5,
        )

        with patch.object(executor, "_run_hook_subprocess") as mock_run:
            mock_run.side_effect = Exception("Something broke")

            result = executor.execute_single_hook(hook)

            assert result.status == "error"

    def test_get_changed_files_for_hook_incremental_disabled(
        self,
        executor: HookExecutor,
    ) -> None:
        """Test that _get_changed_files_for_hook returns None when incremental is disabled."""
        hook = HookDefinition(
            name="ruff-check",
            command=["echo", "test"],
            accepts_file_paths=True,
        )
        executor.use_incremental = False

        result = executor._get_changed_files_for_hook(hook)

        assert result is None

    def test_get_changed_files_for_hook_no_git_service(
        self,
        executor: HookExecutor,
    ) -> None:
        """Test that _get_changed_files_for_hook returns None without git service."""
        executor.git_service = None
        executor.use_incremental = True

        hook = HookDefinition(
            name="ruff-check",
            command=["echo", "test"],
            accepts_file_paths=True,
        )

        result = executor._get_changed_files_for_hook(hook)

        assert result is None

    def test_filter_files_by_hook_type(self, executor: HookExecutor) -> None:
        """Test file filtering by hook type."""
        files = [
            Path("test.py"),
            Path("test.md"),
            Path("test.yaml"),
        ]

        result = executor._filter_files_by_hook_type(files, "ruff-check")

        assert len(result) == 1
        assert result[0] == Path("test.py")

    def test_calculate_performance_gain(self, executor: HookExecutor) -> None:
        """Test performance gain calculation."""
        hooks = [
            HookDefinition(name="h1", command=[], timeout=10),
            HookDefinition(name="h2", command=[], timeout=20),
        ]
        strategy = HookStrategy(name="test", hooks=hooks)

        results = [
            HookResult(id="1", name="h1", status="passed", duration=5.0),
            HookResult(id="2", name="h2", status="passed", duration=10.0),
        ]

        gain = executor._calculate_performance_gain(strategy, results, 10.0)

        assert gain > 0

    def test_get_clean_environment(self, executor: HookExecutor) -> None:
        """Test environment cleaning for subprocess execution."""
        env = executor._get_clean_environment()

        assert "HOME" in env
        assert "USER" in env
        assert "LANG" in env

    def test_get_python_vars_to_exclude(self, executor: HookExecutor) -> None:
        """Test Python environment variables to exclude."""
        vars_to_exclude = executor._get_python_vars_to_exclude()

        assert "VIRTUAL_ENV" in vars_to_exclude
        assert "PYTHONPATH" in vars_to_exclude
        assert "PIP_CONFIG_FILE" in vars_to_exclude


class TestHookExecutorRetryLogic:
    """Tests for retry logic in HookExecutor."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> HookExecutor:
        """Create executor for retry tests."""
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
        )

    def test_retry_formatting_hooks_all_pass(self, executor: HookExecutor) -> None:
        """Test no retry needed when all formatting hooks pass."""
        hooks = [
            HookDefinition(name="format1", command=[], is_formatting=True, timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, retry_policy=RetryPolicy.FORMATTING_ONLY)

        results = [
            HookResult(id="1", name="format1", status="passed", duration=1.0),
        ]

        updated = executor._retry_formatting_hooks(strategy, results)

        assert updated[0].status == "passed"

    def test_retry_formatting_hooks_failure(self, executor: HookExecutor) -> None:
        """Test retry of formatting hooks on failure."""
        hooks = [
            HookDefinition(name="format1", command=["echo", "test"], is_formatting=True, timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, retry_policy=RetryPolicy.FORMATTING_ONLY)

        results = [
            HookResult(id="1", name="format1", status="failed", duration=1.0),
        ]

        with patch.object(executor, "execute_single_hook") as mock_exec:
            mock_exec.return_value = HookResult(
                id="1",
                name="format1",
                status="passed",
                duration=1.0,
            )

            updated = executor._retry_formatting_hooks(strategy, results)

            assert updated[0].status == "passed"

    def test_retry_all_hooks_no_failures(self, executor: HookExecutor) -> None:
        """Test no retry when no hooks failed."""
        hooks = [
            HookDefinition(name="hook1", command=[], timeout=5),
        ]
        strategy = HookStrategy(name="test", hooks=hooks, retry_policy=RetryPolicy.ALL_HOOKS)

        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0),
        ]

        updated = executor._retry_all_hooks(strategy, results)

        assert updated == results

    def test_find_failed_hooks(self, executor: HookExecutor) -> None:
        """Test finding failed hook indices."""
        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0),
            HookResult(id="2", name="hook2", status="failed", duration=1.0),
            HookResult(id="3", name="hook3", status="passed", duration=1.0),
        ]

        failed_indices = executor._find_failed_hooks(results)

        assert failed_indices == [1]


class TestHookExecutorOutputParsing:
    """Tests for output parsing in HookExecutor."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> HookExecutor:
        """Create executor for parsing tests."""
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
        )

    def test_parse_semgrep_json_output(self, executor: HookExecutor) -> None:
        """Test semgrep JSON output parsing."""
        output = '{"results": [{"path": "test.py", "start": {"line": 1}}]}'

        with patch.object(executor, "_run_hook_subprocess") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout=output,
                stderr="",
            )

            hook = HookDefinition(name="semgrep", command=[], timeout=5)
            result = executor.execute_single_hook(hook)

            assert result.status == "failed"

    def test_parse_refurb_issues(self, executor: HookExecutor) -> None:
        """Test refurb issue parsing."""
        output = "src/main.py:10:5 [FURB123]: Use dataclass"

        issues = executor._parse_refurb_issues(output)

        assert len(issues) > 0

    def test_parse_gitleaks_issues_found(self, executor: HookExecutor) -> None:
        """Test gitleaks issue parsing when leaks found."""
        output = "Secret detected in file.py: api_key=abc123"

        issues = executor._parse_gitleaks_issues(output)

        assert len(issues) > 0

    def test_parse_gitleaks_no_leaks(self, executor: HookExecutor) -> None:
        """Test gitleaks parsing when no leaks found."""
        output = "No leaks found. scanned 10 files"

        issues = executor._parse_gitleaks_issues(output)

        assert issues == []

    def test_parse_creosote_issues(self, executor: HookExecutor) -> None:
        """Test creosote issue parsing."""
        output = """
        Checking dependencies...
        unused dependencies found:
        - unused-package
        """

        issues = executor._parse_creosote_issues(output)

        assert len(issues) > 0

    def test_parse_creosote_no_issues(self, executor: HookExecutor) -> None:
        """Test creosote parsing when no unused dependencies."""
        output = "No unused dependencies found"

        issues = executor._parse_creosote_issues(output)

        assert issues == []

    def test_parse_pyscn_issues(self, executor: HookExecutor) -> None:
        """Bug: ``extract_issue_lines`` was being used for pyscn (no
        specific dispatch in the executor), and its generic filter
        counted cobra-style help text (``Usage:``, ``Flags:``,
        ``--max-complexity int``, etc.) as issues — inflating the
        count from 1 to 18. ``_parse_pyscn_issues`` now requires
        pyscn's actual finding signatures (``is too complex``,
        ``is a clone of``, etc.) and stitches the file/line/col from
        the previous non-empty line.
        """
        output = (
            "🔍 Running quality check (complexity, deadcode)...\n"
            "crackerjack/agents/type_error_specialist.py:241:5: "
            "TypeErrorSpecialistAgent._fix_literal_mismatch\n"
            "is too complex (26 > 15)\n"
            "❌ Found 1 quality issue(s)\n"
            "Error: found 1 quality issue(s)\n"
            "Usage:\n"
            "  pyscn check\n"
            "\n"
            "Flags:\n"
            "  --allow-circular-deps   Allow circular dependencies (warnings only)\n"
            "  --allow-dead-code       Allow dead code (don't fail)\n"
            "  -c, --config string         Configuration file path\n"
            "  -h, --help                  help for check\n"
            "  --max-complexity int    Maximum allowed complexity (default 10)\n"
            "  --max-cycles int        Maximum allowed circular dependency cycles before failing\n"
            "  -q, --quiet                 Suppress output unless issues found\n"
            "  -s, --select strings        Comma-separated list of analyses to run: complexity, deadcode, clones,\n"
            "deps\n"
            "  --skip-clones           Skip clone detection\n"
            "\n"
            "Global Flags:\n"
            "  -v, --verbose           Enable verbose logging\n"
        )

        issues = executor._parse_pyscn_issues(output)

        assert len(issues) == 1, (
            f"pyscn parser must find exactly 1 real issue (the "
            f"complexity violation), not 18. Found {len(issues)}:\n"
            f"{issues}"
        )
        # The issue must be the actual complexity finding, stitched
        # with the file/line/col from the header line.
        assert "type_error_specialist.py:241" in issues[0]
        assert "is too complex" in issues[0]
        # Help-text sentinels must NOT appear in the issues list.
        for sentry in ("Usage:", "Flags:", "Global Flags:"):
            for issue in issues:
                assert sentry not in issue, (
                    f"pyscn parser leaked help-text sentry {sentry!r} "
                    f"into issues: {issue}"
                )

    def test_parse_pyscn_issues_clone(self, executor: HookExecutor) -> None:
        """``is a clone of`` should also be recognized as a finding."""
        output = (
            "src/module_a.py:10:4: my_function\n"
            "is a clone of src/module_b.py:20:4: other_function\n"
        )
        issues = executor._parse_pyscn_issues(output)
        assert len(issues) == 1
        assert "is a clone of" in issues[0]
        assert "src/module_a.py:10" in issues[0]

    def test_parse_pyscn_issues_empty(self, executor: HookExecutor) -> None:
        """Empty output should produce no issues."""
        assert executor._parse_pyscn_issues("") == []
        assert executor._parse_pyscn_issues("🔍 Running quality check...\n✅ All clean\n") == []

    def test_pyscn_dispatched_through_reporting_tools(
        self, executor: HookExecutor
    ) -> None:
        """Bug: ``pyscn`` was missing from the ``reporting_tools`` set in
        ``_extract_issues_from_process_output`` (the *outer* dispatcher
        that decides which extraction strategy to use). The dispatch
        at line 816 inside ``_extract_issues_for_reporting_tools`` was
        unreachable and the code fell through to
        ``_extract_issues_for_regular_tools`` → ``extract_issue_lines``
        (the loose helper), which counted cobra-style help text
        (``Usage:``, ``Flags:``, ``--max-complexity int`` …) as issues.
        Net effect: the "Details for failing comprehensive hooks" panel
        showed 18 lines of help text instead of 1 real finding.

        This test exercises the *outer* dispatcher
        (``_extract_issues_from_process_output``) so it catches the
        real production routing — not just the inner function's
        dispatch (which was already correct).
        """
        # Realistic pyscn failure output — the "🔍 Running..." banner,
        # the complexity finding, the "Found 1 issue" summary, an
        # "Error: ..." line, and the full cobra help block.
        output = (
            "🔍 Running quality check (complexity, deadcode)...\n"
            "crackerjack/agents/type_error_specialist.py:241:5: "
            "TypeErrorSpecialistAgent._fix_literal_mismatch\n"
            "is too complex (26 > 15)\n"
            "❌ Found 1 quality issue(s)\n"
            "Error: found 1 quality issue(s)\n"
            "Usage:\n"
            "  pyscn check\n"
            "\n"
            "Flags:\n"
            "  --max-complexity int    Maximum allowed complexity (default 10)\n"
            "  --max-cycles int        Maximum allowed circular dependency cycles before failing\n"
            "  -h, --help                  help for check\n"
        )

        # Build a minimal HookDefinition-style object that looks like
        # pyscn. ``_extract_issues_from_process_output`` reads
        # ``hook.name`` and (for formatting hooks) ``hook.is_formatting``,
        # and inspects the CompletedProcess ``result`` for ``stdout``,
        # ``stderr``, and ``returncode``.
        hook = SimpleNamespace(name="pyscn", is_formatting=False)
        process_result = SimpleNamespace(
            stdout=output,
            stderr="",
            returncode=1,
        )

        issues = executor._extract_issues_from_process_output(
            hook, process_result, status="failed"
        )

        # The outer dispatch must route to ``_parse_pyscn_issues`` —
        # so we expect exactly the 1 real finding, not the 18 lines the
        # loose helper would emit.
        assert len(issues) == 1, (
            f"pyscn outer-dispatch must return 1 real issue via "
            f"_parse_pyscn_issues, got {len(issues)}: {issues}"
        )
        assert "type_error_specialist.py:241" in issues[0]
        assert "is too complex" in issues[0]
        # Help-text sentinels must NOT appear in the issues list.
        for sentry in ("Usage:", "Flags:", "--max-complexity", "--help"):
            for issue in issues:
                assert sentry not in issue, (
                    f"pyscn dispatch leaked help-text {sentry!r}: {issue}"
                )


class TestHookExecutorProgressCallbacks:
    """Tests for progress callbacks in HookExecutor."""

    def test_progress_start_callback(self) -> None:
        """Test progress start callback is called."""
        mock_callback = MagicMock()
        mock_console = MagicMock()
        tmp_path = Path("/tmp/test")

        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
        )

        executor.set_progress_callbacks(
            started_cb=mock_callback,
            total=5,
        )

        executor._handle_progress_start(5)

        mock_callback.assert_called_once_with(1, 5)

    def test_progress_completion_callback(self) -> None:
        """Test progress completion callback is called."""
        mock_callback = MagicMock()
        mock_console = MagicMock()
        tmp_path = Path("/tmp/test")

        executor = HookExecutor(
            console=mock_console,
            pkg_path=tmp_path,
        )

        executor.set_progress_callbacks(
            completed_cb=mock_callback,
            total=5,
        )

        executor._handle_progress_completion(5)

        mock_callback.assert_called_once_with(1, 5)


class TestHookExecutorStatusReporting:
    """Tests for status reporting in HookExecutor."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> HookExecutor:
        """Create executor for status tests."""
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
        )

    def test_determine_initial_status_passed(self, executor: HookExecutor) -> None:
        """Test status determination for passed hook."""
        hook = HookDefinition(name="test-hook", command=[], timeout=5)
        result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        status = executor._determine_initial_status(hook, result)

        assert status == "passed"

    def test_determine_initial_status_failed(self, executor: HookExecutor) -> None:
        """Test status determination for failed hook."""
        hook = HookDefinition(name="test-hook", command=[], timeout=5)
        result = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Error")

        status = executor._determine_initial_status(hook, result)

        assert status == "failed"

    def test_determine_initial_status_ruff_format_modified(
        self,
        executor: HookExecutor,
    ) -> None:
        """Test status for ruff-format with modified files."""
        hook = HookDefinition(name="ruff-format", command=[], timeout=5, is_formatting=True)
        result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="files were modified by this hook",
        )

        status = executor._determine_initial_status(hook, result)

        assert status == "passed"

    def test_skip_offline_pip_audit(self, executor: HookExecutor) -> None:
        """Test offline pip-audit skip detection."""
        hook = HookDefinition(name="pip-audit", command=[], timeout=5)
        result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="Could not resolve host",
        )

        should_skip = executor._should_skip_offline_pip_audit(hook, result)

        assert should_skip is True

    def test_skip_offline_pip_audit_network_available(
        self,
        executor: HookExecutor,
    ) -> None:
        """Test pip-audit not skipped when network available."""
        hook = HookDefinition(name="pip-audit", command=[], timeout=5)
        result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="Found 2 vulnerabilities",
            stderr="",
        )

        should_skip = executor._should_skip_offline_pip_audit(hook, result)

        assert should_skip is False
