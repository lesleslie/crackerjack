"""Unit tests for AutofixCoordinator live public/private methods.

Restored 2026-08-10 after the AI-fix subsystem wholesale deletion.
Only tests for LIVE methods are kept — methods consumed solely by the
removed `_apply_ai_agent_fixes*` entry points are deleted with their tests.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.core.autofix_coordinator import (
    AutofixCoordinator,
    _FileChangeTracker,
)
from crackerjack.models.issues import Issue, IssueType, Priority


class TestAutofixCoordinatorInitialization:
    """Test AutofixCoordinator initialization."""

    def test_initialization_defaults(self) -> None:
        """Test AutofixCoordinator initialization with defaults."""
        coordinator = AutofixCoordinator()

        assert coordinator.console is not None
        assert coordinator.pkg_path == Path.cwd()
        assert coordinator.logger is not None
        assert coordinator._max_iterations is None
        assert coordinator._coordinator_factory is None

    def test_initialization_with_parameters(self) -> None:
        """Test AutofixCoordinator initialization with parameters."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")
        logger = logging.getLogger("test")
        max_iterations = 5

        coordinator = AutofixCoordinator(
            console=console,
            pkg_path=pkg_path,
            logger=logger,
            max_iterations=max_iterations,
        )

        assert coordinator.console is console
        assert coordinator.pkg_path == pkg_path
        assert coordinator.logger is logger
        assert coordinator._max_iterations == max_iterations


class TestAutofixCoordinatorPublicMethods:
    """Test AutofixCoordinator public methods."""

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_unknown_mode(self) -> None:
        """Test apply_autofix_for_hooks with unknown mode."""
        coordinator = AutofixCoordinator()
        hook_results: list = []

        result = await coordinator.apply_autofix_for_hooks("unknown_mode", hook_results)

        # Should return False for unknown mode
        assert result is False

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_should_skip(self) -> None:
        """Test apply_autofix_for_hooks when skipping autofix."""
        coordinator = AutofixCoordinator()

        # Mock the _should_skip_autofix method to return True
        with patch.object(coordinator, "_should_skip_autofix", return_value=True):
            result = await coordinator.apply_autofix_for_hooks("fast", [])

        # Should return False when skipping
        assert result is False

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_fast_passes_hook_results(self) -> None:
        """Fast hook autofix should retain hook results for AI fix mode."""
        coordinator = AutofixCoordinator()
        hook_results = [MagicMock()]

        with (
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
            patch.object(
                coordinator,
                "_apply_fast_stage_fixes",
                new_callable=AsyncMock,
                return_value=True,
            ) as fast_fixes,
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

        assert result is True
        fast_fixes.assert_awaited_once_with(hook_results)

    @pytest.mark.asyncio
    async def test_apply_fast_stage_fixes(self) -> None:
        """Test apply_fast_stage_fixes method."""
        coordinator = AutofixCoordinator()
        hook_results: list = []

        # Mock the internal async method
        with patch.object(
            coordinator,
            "_apply_fast_stage_fixes",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await coordinator.apply_fast_stage_fixes(hook_results)

        assert result is True

    @pytest.mark.asyncio
    async def test_apply_comprehensive_stage_fixes(self) -> None:
        """Test apply_comprehensive_stage_fixes method."""
        coordinator = AutofixCoordinator()
        hook_results: list = []

        # Mock the internal async method
        with patch.object(
            coordinator,
            "_apply_comprehensive_stage_fixes",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await coordinator.apply_comprehensive_stage_fixes(hook_results)

        assert result is True

    def test_run_fix_command(self) -> None:
        """Test run_fix_command method."""
        coordinator = AutofixCoordinator()
        cmd = ["echo", "test"]
        description = "Test command"

        # Mock the internal method
        with patch.object(coordinator, "_run_fix_command", return_value=True):
            result = coordinator.run_fix_command(cmd, description)

        assert result is True

    def test_check_tool_success_patterns(self) -> None:
        """Test check_tool_success_patterns method."""
        coordinator = AutofixCoordinator()
        cmd = ["echo", "test"]
        result_obj = MagicMock()

        # Mock the internal method
        with patch.object(
            coordinator, "_check_tool_success_patterns", return_value=True
        ):
            result = coordinator.check_tool_success_patterns(cmd, result_obj)

        assert result is True

    def test_validate_fix_command(self) -> None:
        """Test validate_fix_command method."""
        coordinator = AutofixCoordinator()
        cmd = ["echo", "test"]

        # Mock the internal method
        with patch.object(coordinator, "_validate_fix_command", return_value=True):
            result = coordinator.validate_fix_command(cmd)

        assert result is True

    def test_validate_hook_result(self) -> None:
        """Test validate_hook_result method."""
        coordinator = AutofixCoordinator()
        result_obj = MagicMock()

        # Mock the internal method
        with patch.object(coordinator, "_validate_hook_result", return_value=True):
            result = coordinator.validate_hook_result(result_obj)

        assert result is True

    def test_should_skip_autofix(self) -> None:
        """Test should_skip_autofix method."""
        coordinator = AutofixCoordinator()
        hook_results: list = []

        # Mock the internal method
        with patch.object(coordinator, "_should_skip_autofix", return_value=False):
            result = coordinator.should_skip_autofix(hook_results)

        assert result is False

    @pytest.mark.asyncio
    async def test_apply_error_handling(self) -> None:
        """Test error handling in apply_autofix_for_hooks."""
        coordinator = AutofixCoordinator()

        # Mock the internal method to raise an exception
        with patch.object(
            coordinator, "_should_skip_autofix", side_effect=Exception("Test error")
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", [])

        # Should return False when an exception occurs
        assert result is False


class TestAutofixCoordinatorPrivateMethods:
    """Test AutofixCoordinator private methods that are still live."""

    def test_should_skip_autofix_empty_results(self) -> None:
        """Test _should_skip_autofix with empty results."""
        coordinator = AutofixCoordinator()
        hook_results: list = []

        result = coordinator._should_skip_autofix(hook_results)

        # With empty results, should probably skip
        assert isinstance(result, bool)

    def test_should_skip_autofix_with_results(self) -> None:
        """Test _should_skip_autofix with results."""
        coordinator = AutofixCoordinator()
        hook_results = [MagicMock()]  # Mock objects representing hook results

        # Mock the validation method to return True
        with patch.object(coordinator, "_validate_hook_result", return_value=True):
            result = coordinator._should_skip_autofix(hook_results)

        assert isinstance(result, bool)

    def test_should_skip_autofix_only_when_all_failed_hooks_are_import_errors(
        self,
    ) -> None:
        """Import errors should not suppress unrelated fixable hook failures."""
        coordinator = AutofixCoordinator()
        import_error = SimpleNamespace(
            name="zuban",
            status="failed",
            output="ModuleNotFoundError: No module named 'missing'",
            error="",
            error_message="",
        )
        ruff_error = SimpleNamespace(
            name="ruff-check",
            status="failed",
            output="C901 `target` is too complex (17 > 15)",
            error="",
            error_message="",
        )

        assert coordinator._should_skip_autofix([import_error]) is True
        assert coordinator._should_skip_autofix([import_error, ruff_error]) is False

    def test_run_fix_command_internal(self) -> None:
        """Test _run_fix_command internal logic."""
        coordinator = AutofixCoordinator()
        # Use a valid command that passes _validate_fix_command
        # Allowed tools are: bandit, trailing-whitespace
        cmd = ["uv", "run", "bandit", "-r", "."]
        description = "Test command"

        # Mock subprocess.run to avoid actually running commands
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = coordinator._run_fix_command(cmd, description)

            # Verify subprocess.run was called
            mock_run.assert_called_once()
            assert isinstance(result, bool)

    def test_validate_fix_command_bandit(self) -> None:
        """Test _validate_fix_command method with bandit."""
        coordinator = AutofixCoordinator()
        cmd = ["uv", "run", "bandit", "-r", "."]

        result = coordinator._validate_fix_command(cmd)
        assert result is True

    def test_validate_fix_command_trailing_whitespace(self) -> None:
        """Test _validate_fix_command with trailing-whitespace tool."""
        coordinator = AutofixCoordinator()
        cmd = ["uv", "run", "trailing-whitespace", "--fix", "."]

        result = coordinator._validate_fix_command(cmd)
        assert result is True

    def test_validate_fix_command_ruff_format(self) -> None:
        """Test _validate_fix_command with a Ruff autofix command."""
        coordinator = AutofixCoordinator()
        cmd = ["uv", "run", "ruff", "format", "."]

        result = coordinator._validate_fix_command(cmd)
        assert result is True

    def test_validate_fix_command_too_short(self) -> None:
        """Test _validate_fix_command with too short command."""
        coordinator = AutofixCoordinator()
        cmd = ["uv"]

        result = coordinator._validate_fix_command(cmd)
        assert result is False

    def test_missing_import_spec(self) -> None:
        """Test deterministic import mappings for undefined names."""
        coordinator = AutofixCoordinator()

        assert coordinator._missing_import_spec("suppress") == (
            "contextlib",
            "suppress",
            "from contextlib import suppress",
        )
        assert coordinator._missing_import_spec("operator") == (
            "operator",
            None,
            "import operator",
        )
        assert coordinator._missing_import_spec("unknown") is None

    def test_validate_fix_command_wrong_first_arg(self) -> None:
        """Test _validate_fix_command with wrong first argument."""
        coordinator = AutofixCoordinator()
        cmd = ["python", "run", "bandit"]

        result = coordinator._validate_fix_command(cmd)
        assert result is False

    def test_validate_fix_command_missing_run(self) -> None:
        """Test _validate_fix_command missing 'run' argument."""
        coordinator = AutofixCoordinator()
        cmd = ["uv", "bandit", "-r", "."]

        result = coordinator._validate_fix_command(cmd)
        assert result is False

    def test_validate_hook_result(self) -> None:
        """Test _validate_hook_result method."""
        coordinator = AutofixCoordinator()
        result_obj = MagicMock()
        result_obj.name = "test_hook"
        result_obj.status = "passed"

        result = coordinator._validate_hook_result(result_obj)
        assert isinstance(result, bool)
        # With valid name and status, should return True
        assert result is True

    @pytest.mark.asyncio
    async def test_pycharm_reformat_prepass_uses_adapter_for_python_files(self) -> None:
        """PyCharm reformat prepass should touch each unique Python file once."""
        adapter = MagicMock()
        adapter.reformat_file = AsyncMock(side_effect=[True, True])
        coordinator = AutofixCoordinator(pycharm_adapter=adapter)
        issues = [
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="type issue",
                file_path="/tmp/first.py",
            ),
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="duplicate path",
                file_path="/tmp/first.py",
            ),
            Issue(
                type=IssueType.IMPORT_ERROR,
                severity=Priority.MEDIUM,
                message="another issue",
                file_path="/tmp/second.py",
            ),
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="ignore non-python",
                file_path="/tmp/notes.txt",
            ),
        ]

        result = await coordinator._apply_pycharm_reformat_prepass(issues)

        assert result is True
        assert adapter.reformat_file.await_count == 2
        adapter.reformat_file.assert_any_await(Path("/tmp/first.py"))
        adapter.reformat_file.assert_any_await(Path("/tmp/second.py"))

    @pytest.mark.asyncio
    async def test_pycharm_diagnostics_context_enriches_type_issues(self) -> None:
        """PyCharm diagnostics should be appended to type issue details."""
        adapter = MagicMock()
        adapter.get_file_problems = AsyncMock(
            return_value=[
                {"message": "missing import", "severity": "error", "line": 4},
                {"message": "type mismatch", "severity": "warning", "line": 7},
            ]
        )
        coordinator = AutofixCoordinator(pycharm_adapter=adapter)
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="typing problem",
            file_path="/tmp/example.py",
        )

        issues = await coordinator._apply_pycharm_diagnostics_context([issue])

        assert issues[0].details
        assert any(
            "PyCharm diagnostics found 2 problem(s)" in line
            for line in issues[0].details
        )
        assert any("missing import" in line for line in issues[0].details)

    @pytest.mark.asyncio
    async def test_pycharm_hook_diagnostics_skips_fast_stage(self) -> None:
        """PyCharm diagnostics should stay out of the fast hook path."""
        coordinator = AutofixCoordinator()
        issues = [MagicMock()]

        with patch.object(
            coordinator,
            "_apply_pycharm_diagnostics_context",
            new_callable=AsyncMock,
        ) as diagnostics:
            result = await coordinator._apply_pycharm_hook_diagnostics_context(
                issues,
                stage="fast",
            )

        assert result is issues
        diagnostics.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pycharm_hook_diagnostics_runs_comprehensive_stage(
        self,
    ) -> None:
        """PyCharm diagnostics should enrich comprehensive hook failures."""
        coordinator = AutofixCoordinator()
        issues = [MagicMock()]

        with patch.object(
            coordinator,
            "_apply_pycharm_diagnostics_context",
            new_callable=AsyncMock,
            return_value=issues,
        ) as diagnostics:
            result = await coordinator._apply_pycharm_hook_diagnostics_context(
                issues,
                stage="comprehensive",
            )

        assert result is issues
        diagnostics.assert_awaited_once_with(issues)


class TestFileChangeTracker:
    """`_FileChangeTracker` snapshot primitive."""

    def test_capture_then_delta_no_changes(self, tmp_path: Path) -> None:
        """After capture, delta is 0 when nothing has changed."""
        (tmp_path / "a.py").write_text("x = 1")
        tracker = _FileChangeTracker(tmp_path)
        tracker.capture()
        assert tracker.delta() == 0

    def test_capture_then_delta_detects_change(self, tmp_path: Path) -> None:
        """delta reports the number of files whose mtime changed since capture."""
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        tracker = _FileChangeTracker(tmp_path)
        tracker.capture()
        f.write_text("x = 2")
        assert tracker.delta() == 1

    def test_capture_resets_baseline(self, tmp_path: Path) -> None:
        """Calling capture() a second time moves the baseline forward."""
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        tracker = _FileChangeTracker(tmp_path)
        tracker.capture()
        f.write_text("x = 2")
        assert tracker.delta() == 1
        tracker.capture()
        assert tracker.delta() == 0

    def test_delta_before_capture_returns_zero(self, tmp_path: Path) -> None:
        """delta() before capture() returns 0 (no baseline to compare against)."""
        (tmp_path / "a.py").write_text("x = 1")
        tracker = _FileChangeTracker(tmp_path)
        assert tracker.delta() == 0