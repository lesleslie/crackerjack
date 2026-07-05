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

    def test_ty_dispatched_through_reporting_tools(
        self, executor: HookExecutor
    ) -> None:
        """Bug: ``ty`` was missing from the outer ``reporting_tools`` set in
        ``_extract_issues_from_process_output``. The code fell through to
        ``_extract_issues_for_regular_tools`` → ``extract_issue_lines``,
        which counted the ratchet's structured
        ``ty ratchet [split] prod: FAIL (24/50)`` and
        ``ty ratchet [split] test: FAIL (679/30)`` summary lines plus the
        test-tail diagnostics as 24 (in oneiric) instead of routing to
        the dedicated ``_parse_ty_ratchet_issues`` parser.

        This test exercises the OUTER dispatcher so it catches the real
        production routing — not just the inner function's dispatch.
        """
        # Realistic ty ratchet --split output: structured prod+test
        # summaries, the advisory banner, the test-tail (concise
        # diagnostic format), and the ratchet's own "Found N" summary.
        output = (
            "ty ratchet [split] prod: FAIL (24/50)\n"
            "ty ratchet [split] test: FAIL (679/30)\n"
            "⚠️  ty: test ratchet FAIL (679/30) — advisory only; "
            "prod gate FAIL (24/50) controls the exit code.\n"
            "crackerjack/agents/foo.py:10:5: error[invalid-argument-type] "
            "Argument to ...\n"
            "crackerjack/agents/bar.py:42:9: warning[unused-type-ignore] "
            "Unused type ignore comment ...\n"
            "Found 679 diagnostics\n"
        )

        hook = SimpleNamespace(name="ty", is_formatting=False)
        process_result = SimpleNamespace(
            stdout=output, stderr="", returncode=1
        )

        issues = executor._extract_issues_from_process_output(
            hook, process_result, status="failed"
        )

        # The outer dispatch must route to ``_parse_ty_ratchet_issues`` —
        # which returns ONLY the concise-diagnostic lines, NOT the
        # 24 the loose helper would emit.
        assert len(issues) == 2, (
            f"ty outer-dispatch must return 2 prod diagnostics via "
            f"_parse_ty_ratchet_issues, got {len(issues)}: {issues}"
        )
        assert "agents/foo.py:10:5" in issues[0]
        assert "agents/bar.py:42:9" in issues[1]
        # Structured summary lines, advisory banner, and "Found N" must
        # NOT appear in the issues list.
        for sentry in (
            "ty ratchet [split] prod:",
            "ty ratchet [split] test:",
            "⚠️  ty:",
            "Found 679",
        ):
            for issue in issues:
                assert sentry not in issue, (
                    f"ty dispatch leaked structured line {sentry!r}: {issue}"
                )


class TestParseTyRatchetIssues:
    """Tests for ``HookExecutor._parse_ty_ratchet_issues``.

    Mirrors the ``TestParsePyscnIssues`` shape (see line ~562).
    """

    @pytest.fixture
    def executor(self, tmp_path: Path) -> HookExecutor:
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
        )

    def test_extracts_only_concise_diagnostics(
        self, executor: HookExecutor
    ) -> None:
        output = (
            "ty ratchet [split] prod: FAIL (24/50)\n"
            "ty ratchet [split] test: FAIL (679/30)\n"
            "⚠️  ty: test ratchet FAIL (679/30) — advisory only; "
            "prod gate FAIL (24/50) controls the exit code.\n"
            "crackerjack/agents/foo.py:10:5: error[invalid-argument-type] "
            "Argument to ...\n"
            "crackerjack/agents/bar.py:42:9: warning[unused-type-ignore] "
            "Unused type ignore comment ...\n"
            "Found 679 diagnostics\n"
        )
        issues = executor._parse_ty_ratchet_issues(output)
        assert len(issues) == 2
        assert issues[0].startswith("crackerjack/agents/foo.py:10:5:")
        assert issues[1].startswith("crackerjack/agents/bar.py:42:9:")

    def test_clean_run_returns_empty(self, executor: HookExecutor) -> None:
        output = (
            "ty ratchet [split] prod: PASS (0/50)\n"
            "ty ratchet [split] test: PASS (0/30)\n"
        )
        assert executor._parse_ty_ratchet_issues(output) == []

    def test_empty_output_returns_empty(self, executor: HookExecutor) -> None:
        assert executor._parse_ty_ratchet_issues("") == []

    def test_filters_advisory_banner(self, executor: HookExecutor) -> None:
        # Advisory banner and "Found N" summary are NOT findings.
        # The test-tail ``tests/*`` line IS filtered by the test-dir
        # prefix rule (filter is unconditional — see module-level
        # ``parse_ty_ratchet_issues`` docstring). The PASS/FAIL banner
        # already surfaces test-gate status elsewhere.
        output = (
            "ty ratchet [split] prod: PASS (0/50)\n"
            "ty ratchet [split] test: FAIL (5/30)\n"
            "⚠️  ty: test ratchet FAIL (5/30) — advisory only; "
            "prod gate PASS (0/50) controls the exit code.\n"
            "tests/test_foo.py:1:1: error[unused-ignore-comment] ...\n"
            "Found 5 diagnostics\n"
        )
        issues = executor._parse_ty_ratchet_issues(output)
        # tests/* line dropped → 0 issues remain.
        assert len(issues) == 0, (
            f"filter must drop tests/* diagnostics unconditionally; "
            f"got {len(issues)}: {issues}"
        )
        # Sentinel exclusion: the structured lines must NEVER appear,
        # regardless of how many concise diagnostics survive.
        for sentry in (
            "ty ratchet [split]",
            "⚠️",
            "Found 5",
        ):
            for issue in issues:
                assert sentry not in issue, (
                    f"parser leaked structured line {sentry!r}: {issue}"
                )


class TestTyActualCountExtraction:
    """``HookExecutor._ty_actual_count`` recovers the TRUE diagnostic count
    from ty_ratchet output, decoupled from the truncated tail (``[-20:]``).

    The user's bug: ``crakerjack run -c`` invokes ``ty_ratchet --split``,
    which discards all but the last 20 concise lines per failing dir before
    writing to stderr. The crackerjack panel derives ``issues_count`` from
    ``len(parsed lines)`` and ends up showing 38 (or 40) instead of 200+.
    The count is recoverable from ty's own ``Found N diagnostics`` summary
    lines (preferred) or the parenthesised ``(N/M)`` in the wrapper's
    summary lines (fallback). Verification: the count matches reality.
    """

    @pytest.fixture
    def executor(self, tmp_path: Path) -> HookExecutor:
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
        )

    def test_extracts_count_from_found_diagnostics_lines(
        self, executor: HookExecutor
    ) -> None:
        """Prefer the ``Found N diagnostics`` lines emitted by ``ty`` itself."""
        output = (
            "ty ratchet [split] prod: FAIL (200/150)\n"
            "ty ratchet [split] test: FAIL (679/30)\n"
            "crackerjack/agents/foo.py:10:5: error[E001] x\n"
            "... (tail truncated by [-20:] in the wrapper) ...\n"
            "Found 200 diagnostics\n"
            "Found 679 diagnostics\n"
        )
        assert executor._ty_actual_count(output) == 200 + 679

    def test_falls_back_to_summary_line_counts(
        self, executor: HookExecutor
    ) -> None:
        """When ``Found N`` lines are absent, sum parenthesised counts."""
        output = (
            "ty ratchet [split] prod: FAIL (200/150)\n"
            "ty ratchet [split] test: FAIL (679/30)\n"
        )
        assert executor._ty_actual_count(output) == 200 + 679

    def test_returns_zero_when_nothing_parseable(
        self, executor: HookExecutor
    ) -> None:
        """Empty / clean-run output yields 0 — caller falls back to len()."""
        assert executor._ty_actual_count("") == 0
        assert executor._ty_actual_count(
            "ty ratchet [split] prod: PASS (0/50)\n"
            "ty ratchet [split] test: PASS (0/30)\n"
        ) == 0

    def test_only_prod_found_diagnostics_when_test_is_clean(
        self, executor: HookExecutor
    ) -> None:
        """When ``Found N`` appears only for prod (test under budget),
        the count reflects what was emitted — partial signal is still
        useful and the caller must not silently include zero."""
        output = (
            "ty ratchet [split] prod: FAIL (45/150)\n"
            "ty ratchet [split] test: PASS (0/30)\n"
            "Found 45 diagnostics\n"
        )
        assert executor._ty_actual_count(output) == 45


class TestTyVerboseFiltersTestDir:
    """``_parse_ty_ratchet_issues`` filters the test directory from the
    concise diagnostic lines emitted by ``ty_ratchet --split``. The filter
    applies unconditionally — ``self.verbose`` is intentionally NOT consulted.

    The test-gate PASS/FAIL banner and warning are still informative on
    their own; only the per-line detail noise under ``test_dir`` is dropped
    so the per-issue details panel stays focused on production failures.

    User intent (2026-07-04): "we want crackerjack's issues reporting
    for ty (with -v) to ignore all of the issues it exposes in the
    tests/ dir. It's nice to know where the tests are at, and the
    warning gives us that, but we only want the failures from
    production/package dir reported verbosely in the detailed issues
    of crackerjack."

    The ``verbose`` parameter exists in the executor constructor for
    parity / future plumbing, but it does NOT gate this filter. See the
    module-level ``parse_ty_ratchet_issues`` docstring for the rationale.
    """

    @pytest.fixture
    def executor(self, tmp_path: Path) -> HookExecutor:
        # verbose=True — fixture represents the verbose execution mode.
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
            verbose=True,
            test_dir="tests",
        )

    @pytest.fixture
    def quiet_executor(self, tmp_path: Path) -> HookExecutor:
        # verbose=False (default) — fixture represents normal mode.
        # Filter is unconditional; this fixture verifies that even with
        # verbose=False, test-dir diagnostics are still dropped.
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
            test_dir="tests",
        )

    @pytest.fixture
    def mixed_output(self) -> str:
        """Simulated ty_ratchet --split output mixing prod + test diagnostics."""
        return (
            "ty ratchet [split] prod: FAIL (5/150)\n"
            "ty ratchet [split] test: FAIL (12/30)\n"
            "crackerjack/agents/foo.py:1:1: error[E001] x\n"
            "crackerjack/agents/bar.py:2:2: error[E001] y\n"
            "crackerjack/agents/baz.py:3:3: error[E001] z\n"
            "crackerjack/agents/qux.py:4:4: error[E001] w\n"
            "crackerjack/agents/quux.py:5:5: error[E001] v\n"
            "tests/test_alpha.py:1:1: error[E001] test1\n"
            "tests/test_beta.py:2:2: error[E001] test2\n"
            "tests/test_gamma.py:3:3: error[E001] test3\n"
            "tests/test_delta.py:4:4: error[E001] test4\n"
            "tests/test_epsilon.py:5:5: error[E001] test5\n"
            "tests/test_zeta.py:6:6: error[E001] test6\n"
            "tests/test_eta.py:7:7: error[E001] test7\n"
            "tests/test_theta.py:8:8: error[E001] test8\n"
            "tests/test_iota.py:9:9: error[E001] test9\n"
            "tests/test_kappa.py:10:10: error[E001] test10\n"
            "tests/test_lambda.py:11:11: error[E001] test11\n"
            "tests/test_mu.py:12:12: error[E001] test12\n"
            "Found 5 diagnostics\n"
            "Found 12 diagnostics\n"
        )

    def test_verbose_skips_tests_prefix_diagnostics(
        self, executor: HookExecutor, mixed_output: str
    ) -> None:
        """Filter drops lines starting with the configured test dir."""
        issues = executor._parse_ty_ratchet_issues(mixed_output)
        # 5 prod dir diagnostics remain; 12 test dir diagnostics gone.
        assert len(issues) == 5, (
            f"filter must drop tests/* diagnostics; got {len(issues)}: {issues}"
        )
        for issue in issues:
            assert issue.startswith("crackerjack/") or issue.startswith(
                ("session_buddy/", "src/", "pkg/", "package/")
            ) or "/" not in issue.split(":")[0], (
                f"filter leaked test-dir line: {issue!r}"
            )
            assert not issue.startswith("tests/"), (
                f"filter leaked tests/ prefix: {issue!r}"
            )

    def test_filter_applies_even_when_verbose_false(
        self, quiet_executor: HookExecutor
    ) -> None:
        """The filter applies unconditionally — ``verbose=False`` does NOT
        re-enable test-dir diagnostics. This pins the intentional contract;
        see ``parse_ty_ratchet_issues`` docstring for rationale.
        """
        output = (
            "crackerjack/foo.py:1:1: error[E001] prod\n"
            "tests/unit/test_x.py:1:1: error[E100] test\n"
        )
        issues = quiet_executor._parse_ty_ratchet_issues(output)
        assert len(issues) == 1
        assert "prod" in issues[0]
        assert not any("tests/" in i for i in issues)

    def test_verbose_respects_custom_test_dir(
        self, executor: HookExecutor, mixed_output: str
    ) -> None:
        """When ``test_dir`` is overridden, the prefix filter uses the new dir."""
        executor._ty_test_dir = "tests_unit"
        rewritten = mixed_output.replace("tests/", "tests_unit/")
        issues = executor._parse_ty_ratchet_issues(rewritten)
        # All prod diagnostics remain; tests_unit/* dropped.
        assert len(issues) == 5
        for issue in issues:
            assert not issue.startswith("tests_unit/")


class TestTyIssuesCountUsesActual:
    """Integration test: ``_create_hook_result_from_process`` returns a
    HookResult whose ``issues_count`` reflects ACTUAL diagnostics for ty
    instead of the truncated tail-line count.

    This is the user's reported symptom: ``Issues: 38`` when ty actually
    found 200+. The fix routes through ``_ty_actual_count`` so the cell
    in the rich Hook Results panel reflects reality.
    """

    @pytest.fixture
    def executor(self, tmp_path: Path) -> HookExecutor:
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
        )

    def test_ty_hook_result_issues_count_reflects_actual(
        self, executor: HookExecutor
    ) -> None:
        """Simulated ty_ratchet --split output: 200 prod + 38 test, but
        wrapper only emits last 20 of each → 38 concise lines visible."""
        hook = SimpleNamespace(
            name="ty", is_formatting=False, timeout=120, stage=HookStage.COMPREHENSIVE
        )
        # Real prod has 200 diagnostics; tail captured is 20.
        # Real test has 38 diagnostics; tail captured is 20 (all 38
        # fit in test since 38 < 20 ... wait, test has 38 not 20 —
        # adjust: test has 38 which exceeds 20 so tail is also 20).
        # For testability, both prod and test are 200 but tail shows
        # 20 each → concise_lines = 40, but Found N says 200+200.
        stdout = (
            "ty ratchet [split] prod: FAIL (200/150)\n"
            "ty ratchet [split] test: FAIL (200/30)\n"
            "crackerjack/a.py:1:1: error[E001] x\n"
        )
        # Add 19 more concise prod lines so we have 20 prod tail lines
        stdout += "\n".join(
            f"crackerjack/file{i}.py:{i}:1: error[E001] y" for i in range(2, 21)
        ) + "\n"
        # Add 20 concise test tail lines
        stdout += "\n".join(
            f"tests/test_{i}.py:1:1: error[E001] y" for i in range(1, 21)
        ) + "\n"
        # Add Found N lines (ty's own summary, normally at end)
        stdout += "Found 200 diagnostics\n"
        # (The tail is taken from stdout+stderr; for the simulator we
        # put both prod Found and test Found into stderr.)
        stderr = "Found 200 diagnostics\n"

        # Stub out subprocess result
        result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=stdout, stderr=stderr
        )

        # The current path uses _parse_ty_ratchet_issues which would
        # return concise_lines only. We assert that AFTER the fix,
        # _create_hook_result_from_process exposes the actual count
        # (400) instead of the tail-line count (40).
        hook_result = executor._create_hook_result_from_process(
            hook=hook,
            result=result,
            duration=9.65,
        )

        # The fix: issues_count reflects 200 + 200 = 400, not 40.
        assert hook_result.issues_count == 400, (
            f"ty issues_count must reflect actual diagnostics "
            f"(200+200=400), not the tail-line count "
            f"({len(hook_result.issues_found)}); "
            f"panel currently shows {hook_result.issues_count}"
        )


class TestParseHookOutputTyDispatch:
    """The ``_parse_hook_output`` dispatch path for ``hook_name == "ty"``
    must route to the FILTERED parser (``_parse_ty_ratchet_issues``),
    NOT the old unfiltered ``_parse_ty_ratchet``. In verbose mode this
    drops ``tests/*`` diagnostics from the per-issue details panel.

    Regression coverage for the wiring gap where the dispatch went to
    the old parser and leaked ``tests/*`` diagnostics into the panel
    even when ``crackerjack run -v`` was used.
    """

    @pytest.fixture
    def verbose_executor(self, tmp_path: Path) -> HookExecutor:
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
            verbose=True,
            test_dir="tests",
        )

    @pytest.fixture
    def quiet_executor(self, tmp_path: Path) -> HookExecutor:
        return HookExecutor(
            console=MagicMock(),
            pkg_path=tmp_path,
            test_dir="tests",
        )

    @pytest.fixture
    def mixed_output(self) -> str:
        return (
            "ty ratchet [split] prod: FAIL (3/150)\n"
            "ty ratchet [split] test: FAIL (5/30)\n"
            "crackerjack/foo.py:1:1: error[E001] prod one\n"
            "crackerjack/bar.py:2:2: error[E002] prod two\n"
            "crackerjack/baz.py:3:3: error[E003] prod three\n"
            "tests/unit/test_alpha.py:10:1: error[E100] test one\n"
            "tests/unit/test_beta.py:20:2: error[E101] test two\n"
            "tests/unit/test_gamma.py:30:3: error[E102] test three\n"
            "tests/unit/test_delta.py:40:4: error[E103] test four\n"
            "tests/unit/test_epsilon.py:50:5: error[E104] test five\n"
            "Found 3 diagnostics\n"
            "Found 5 diagnostics\n"
        )

    def test_verbose_dispatch_drops_tests_prefix(
        self, verbose_executor: HookExecutor, mixed_output: str
    ) -> None:
        """The full dispatch path with verbose=True must filter tests/*."""
        result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=mixed_output, stderr=""
        )

        parsed = verbose_executor._parse_hook_output(result, "ty")

        assert parsed["hook_id"] is None
        assert parsed["exit_code"] == 1
        assert parsed["files_processed"] == 0
        issues = parsed["advisory_issues"]
        assert len(issues) == 3, (
            f"verbose dispatch must drop tests/* diagnostics and keep "
            f"only 3 prod issues; got {len(issues)}: {issues}"
        )
        for issue in issues:
            assert not issue.startswith("tests/"), (
                f"verbose dispatch leaked tests/ prefix: {issue!r}"
            )
        # The structured summary lines, advisory banner, and "Found N"
        # counters must NOT appear in the advisory_issues list.
        for sentry in (
            "ty ratchet [split]",
            "⚠️",
            "Found ",
        ):
            for issue in issues:
                assert sentry not in issue, (
                    f"ty dispatch leaked structured line {sentry!r}: "
                    f"{issue!r}"
                )

    def test_quiet_dispatch_drops_tests_prefix(
        self, quiet_executor: HookExecutor, mixed_output: str
    ) -> None:
        """Non-verbose dispatch ALSO drops ``tests/*`` — the filter is
        unconditional (see module-level ``parse_ty_ratchet_issues``
        docstring). This pins the new contract for the dispatch path.
        """
        result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=mixed_output, stderr=""
        )

        parsed = quiet_executor._parse_hook_output(result, "ty")

        issues = parsed["advisory_issues"]
        # Filter is unconditional — tests/* always dropped, regardless of verbose.
        assert len(issues) == 3, (
            f"non-verbose dispatch must drop tests/* diagnostics too "
            f"(filter is unconditional); got {len(issues)}: {issues}"
        )
        for issue in issues:
            assert not issue.startswith("tests/"), (
                f"non-verbose dispatch leaked tests/ prefix: {issue!r}"
            )

    def test_verbose_dispatch_does_not_leak_test_dir_lines(
        self, verbose_executor: HookExecutor
    ) -> None:
        """Simulates the user-reported symptom: with -v, the panel must
        not show tests/* diagnostics in ``advisory_issues``.
        """
        output = (
            "ty ratchet [split] prod: FAIL (2/150)\n"
            "ty ratchet [split] test: FAIL (2/30)\n"
            "crackerjack/foo.py:1:1: error[E001] prod one\n"
            "crackerjack/bar.py:2:2: error[E002] prod two\n"
            "tests/unit/test_alpha.py:10:1: error[E100] test one\n"
            "tests/unit/test_beta.py:20:2: error[E101] test two\n"
            "Found 2 diagnostics\n"
            "Found 2 diagnostics\n"
        )
        result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=output, stderr=""
        )

        parsed = verbose_executor._parse_hook_output(result, "ty")

        issues = parsed["advisory_issues"]
        assert len(issues) == 2, (
            f"verbose dispatch must yield 2 prod issues (0 test leaks); "
            f"got {len(issues)}: {issues}"
        )
        # No test-dir diagnostics should survive the filter.
        test_leaks = [i for i in issues if i.startswith("tests/")]
        assert test_leaks == [], (
            f"verbose dispatch leaked {len(test_leaks)} tests/* "
            f"diagnostic(s): {test_leaks}"
        )


class TestReportingToolsConstant:
    """The unified ``_REPORTING_TOOLS`` frozenset is the single source
    of truth for the three dispatch sites. Adding ``ty`` here is the
    whole point of E.1.
    """

    def test_reporting_tools_constant_includes_ty(self) -> None:
        from crackerjack.executors.hook_executor import HookExecutor
        expected = {
            "complexipy",
            "refurb",
            "pyscn",
            "gitleaks",
            "creosote",
            "pip-audit",
            "lychee",
            "ty",
        }
        assert expected.issubset(HookExecutor._REPORTING_TOOLS)

    def test_status_flipping_tools_excludes_ty(self) -> None:
        """``ty`` must NOT be in the status-flip subset so the test-gate
        failing alone does not flip the hook from ``passed`` to
        ``failed``. The prod gate's exit code is authoritative.
        """
        from crackerjack.executors.hook_executor import HookExecutor
        assert "ty" in HookExecutor._REPORTING_TOOLS
        # The runtime subset is built from the class constant via
        # ``self._REPORTING_TOOLS - {"ty"}`` in
        # ``_update_status_for_reporting_tools``. Verify the invariant
        # at the class level: ty must NOT trigger status-flip in any
        # future refactor of the carve-out.
        status_flipping = HookExecutor._REPORTING_TOOLS - {"ty"}
        assert "ty" not in status_flipping


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


class TestHookResultAdvisoryIssuesField:
    """``HookResult.advisory_issues`` carries per-tool advisory diagnostics.

    Currently used by the ty hook for test-ratchet diagnostics that are
    surfaced as a post-stage warning but don't flip the hook status.
    Default is an empty list — each instance gets its own list via
    ``field(default_factory=list)``.
    """

    def test_advisory_issues_default_is_empty_list(self) -> None:
        """A bare HookResult() has advisory_issues == []."""
        from crackerjack.models.task import HookResult

        result = HookResult()
        assert result.advisory_issues == []

    def test_advisory_issues_default_factory_not_shared_between_instances(
        self,
    ) -> None:
        """Mutating one instance's list doesn't affect another."""
        from crackerjack.models.task import HookResult

        a = HookResult()
        b = HookResult()
        a.advisory_issues.append("crackerjack/foo.py:10:5: error")
        assert b.advisory_issues == []

    def test_advisory_issues_field_preserved_through_construction(
        self,
    ) -> None:
        """Explicit construction preserves the list reference."""
        from crackerjack.models.task import HookResult

        adv = ["crackerjack/foo.py:10:5: error[invalid-argument-type] x"]
        result = HookResult(name="ty", advisory_issues=adv)
        assert result.advisory_issues is adv


class TestAdvisoryBannerEndToEnd:
    """The ⚠️ warning banner fires when HookResult.advisory_issues is set.

    Tests the full pipeline: ratchet stdout/stderr -> parse -> HookResult
    construction -> display -> console output. Locks in the E.3 contract.
    """

    def test_warning_banner_prints_advisory_count(
        self, tmp_path: Path
    ) -> None:
        """When ty hook has advisory_issues and status=passed, banner prints."""
        from crackerjack.executors.hook_executor import HookExecutor
        from crackerjack.models.task import HookResult

        console = MagicMock()
        executor = HookExecutor(console=console, pkg_path=tmp_path)

        result = HookResult(
            id="ty",
            name="ty",
            status="passed",
            duration=1.0,
            files_processed=0,
            issues_found=[],
            issues_count=0,
            stage="comp",
            exit_code=0,
            advisory_issues=[
                "crackerjack/foo.py:10:5: error[invalid-argument-type] x is wrong",
                "crackerjack/bar.py:42:9: warning[unused-type-ignore-comment] ...",
            ],
        )

        executor._display_hook_result(result)

        # Find the call that printed the warning banner.
        banner_calls = [
            call_args
            for call_args in console.print.call_args_list
            if call_args.args
            and "ty test ratchet FAIL" in str(call_args.args[0])
        ]
        assert len(banner_calls) == 1, (
            f"Expected exactly 1 warning banner; got {len(banner_calls)}. "
            f"All console.print calls: {console.print.call_args_list}"
        )
        banner_text = str(banner_calls[0].args[0])
        assert "2 diagnostic(s)" in banner_text
        assert "tests/" in banner_text
        assert "advisory only" in banner_text

    def test_no_banner_when_advisory_issues_empty(
        self, tmp_path: Path
    ) -> None:
        """When advisory_issues is empty, no warning banner prints."""
        from crackerjack.executors.hook_executor import HookExecutor
        from crackerjack.models.task import HookResult

        console = MagicMock()
        executor = HookExecutor(console=console, pkg_path=tmp_path)

        result = HookResult(
            id="ty",
            name="ty",
            status="passed",
            duration=1.0,
            files_processed=0,
            issues_found=[],
            issues_count=0,
            stage="comp",
            exit_code=0,
            advisory_issues=[],
        )

        executor._display_hook_result(result)

        banner_calls = [
            call_args
            for call_args in console.print.call_args_list
            if call_args.args
            and "ty test ratchet FAIL" in str(call_args.args[0])
        ]
        assert len(banner_calls) == 0

    def test_no_banner_when_status_failed(
        self, tmp_path: Path
    ) -> None:
        """When the hook status is 'failed', no advisory banner (gate is the signal)."""
        from crackerjack.executors.hook_executor import HookExecutor
        from crackerjack.models.task import HookResult

        console = MagicMock()
        executor = HookExecutor(console=console, pkg_path=tmp_path)

        result = HookResult(
            id="ty",
            name="ty",
            status="failed",
            duration=1.0,
            files_processed=0,
            issues_found=["some prod error"],
            issues_count=1,
            stage="comp",
            exit_code=1,
            advisory_issues=[
                "crackerjack/foo.py:10:5: error ...",  # would be advisory
            ],
        )

        executor._display_hook_result(result)

        banner_calls = [
            call_args
            for call_args in console.print.call_args_list
            if call_args.args
            and "ty test ratchet FAIL" in str(call_args.args[0])
        ]
        assert len(banner_calls) == 0, (
            "Banner must not fire when status=failed (gate is the visible signal)."
        )
