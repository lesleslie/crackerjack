"""Unit tests for autofix coordinator components."""

import asyncio
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import FixResult, Issue, IssueType, Priority
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


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


class TestAutofixCoordinatorMethods:
    """Test AutofixCoordinator methods."""

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_unknown_mode(self) -> None:
        """Test apply_autofix_for_hooks with unknown mode."""
        coordinator = AutofixCoordinator()
        hook_results = []

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
        hook_results = []

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
        hook_results = []

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
        hook_results = []

        # Mock the internal method
        with patch.object(coordinator, "_should_skip_autofix", return_value=False):
            result = coordinator.should_skip_autofix(hook_results)

        assert result is False

    @pytest.mark.asyncio
    async def test_apply_fast_stage_fixes_ai_agent_enabled(self) -> None:
        """Test _apply_fast_stage_fixes with AI agent enabled."""
        coordinator = AutofixCoordinator()

        # Temporarily set AI_AGENT environment variable
        original_value = os.environ.get("AI_AGENT")
        os.environ["AI_AGENT"] = "1"

        try:
            # Mock the async internal method
            with patch.object(
                coordinator,
                "_apply_ai_agent_fixes",
                new_callable=AsyncMock,
                return_value=True,
            ):
                result = await coordinator._apply_fast_stage_fixes([])

            assert result is True
        finally:
            # Restore original value
            if original_value is not None:
                os.environ["AI_AGENT"] = original_value
            else:
                os.environ.pop("AI_AGENT", None)

    @pytest.mark.asyncio
    async def test_apply_fast_stage_fixes_ai_agent_disabled(self) -> None:
        """Test _apply_fast_stage_fixes with AI agent disabled."""
        coordinator = AutofixCoordinator()

        # Ensure AI_AGENT environment variable is not set
        original_value = os.environ.get("AI_AGENT")
        if "AI_AGENT" in os.environ:
            del os.environ["AI_AGENT"]

        try:
            # Mock the internal method (non-async)
            with patch.object(
                coordinator,
                "_execute_fast_fixes",
                new_callable=AsyncMock,
                return_value=True,
            ):
                result = await coordinator._apply_fast_stage_fixes([])

            assert result is True
        finally:
            # Restore original value if it existed
            if original_value is not None:
                os.environ["AI_AGENT"] = original_value

    @pytest.mark.asyncio
    async def test_apply_comprehensive_stage_fixes_ai_agent_enabled(self) -> None:
        """Test _apply_comprehensive_stage_fixes with AI agent enabled."""
        coordinator = AutofixCoordinator()
        hook_results = []

        # Temporarily set AI_AGENT environment variable
        original_value = os.environ.get("AI_AGENT")
        os.environ["AI_AGENT"] = "1"

        try:
            # Mock the async internal method
            with patch.object(
                coordinator,
                "_apply_ai_agent_fixes",
                new_callable=AsyncMock,
                return_value=True,
            ):
                result = await coordinator._apply_comprehensive_stage_fixes(
                    hook_results
                )

            assert result is True
        finally:
            # Restore original value
            if original_value is not None:
                os.environ["AI_AGENT"] = original_value
            else:
                os.environ.pop("AI_AGENT", None)

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
    """Test AutofixCoordinator private methods."""

    def test_should_skip_autofix_empty_results(self) -> None:
        """Test _should_skip_autofix with empty results."""
        coordinator = AutofixCoordinator()
        hook_results = []

        result = coordinator._should_skip_autofix(hook_results)

        # With empty results, should probably skip
        # Actual behavior depends on implementation
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

    def test_build_comprehensive_check_commands_includes_security_hooks(
        self,
    ) -> None:
        """Comprehensive current-issue checks should include configured security hooks."""
        coordinator = AutofixCoordinator()

        with patch(
            "crackerjack.core.autofix_coordinator.get_tool_command",
            side_effect=lambda hook_name, _: ["uv", "run", hook_name],
        ):
            commands = coordinator._build_check_commands(
                coordinator.pkg_path,
                stage="comprehensive",
            )

        hook_names = {hook_name for _, hook_name, _ in commands}
        assert {"semgrep", "pyscn", "gitleaks"}.issubset(hook_names)
        assert {"creosote", "check-jsonschema", "linkcheckmd", "lychee"}.issubset(
            hook_names
        )

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
            # Result depends on the actual implementation
            assert isinstance(result, bool)

    def test_validate_fix_command(self) -> None:
        """Test _validate_fix_command method."""
        coordinator = AutofixCoordinator()
        # Use a valid command format: ["uv", "run", <allowed_tool>, ...]
        # Allowed tools are: bandit, trailing-whitespace
        cmd = ["uv", "run", "bandit", "-r", "."]

        # The actual validation checks for uv run <allowed_tool>
        result = coordinator._validate_fix_command(cmd)

        # bandit is in the allowed tools list, so this should pass
        assert result is True

    def test_validate_fix_command_trailing_whitespace(self) -> None:
        """Test _validate_fix_command with trailing-whitespace tool."""
        coordinator = AutofixCoordinator()
        cmd = ["uv", "run", "trailing-whitespace", "--fix", "."]

        result = coordinator._validate_fix_command(cmd)

        # trailing-whitespace is in the allowed tools list
        assert result is True

    def test_validate_fix_command_invalid_tool(self) -> None:
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

        # The actual validation depends on the implementation
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


class TestAutofixCoordinatorValidationChecks:
    """Test validation check selection for fast fixes."""

    def test_validation_quality_checks_for_complexity_plan(self) -> None:
        """Complexity plans should validate Ruff only."""
        from crackerjack.models.fix_plan import FixPlan

        coordinator = AutofixCoordinator()
        plan = FixPlan(
            file_path="/tmp/test.py",
            issue_type="COMPLEXITY",
            issue_stage="ruff-check",
            rationale="Reduce complexity",
            risk_level="low",
            validated_by="test",
        )

        assert coordinator._validation_quality_checks_for_plan(plan) == ("ruff",)

    def test_validation_quality_checks_for_non_ruff_plan(self) -> None:
        """Non-Ruff plans should keep the default validation set."""
        coordinator = AutofixCoordinator()
        plan = FixPlan(
            file_path="/tmp/test.py",
            issue_type="TYPE_ERROR",
            issue_stage="mypy",
            rationale="Fix typing",
            risk_level="low",
            validated_by="test",
        )

        assert coordinator._validation_quality_checks_for_plan(plan) is None

    def test_validation_compares_to_original_for_complexity_plan(self) -> None:
        """Complexity plans should baseline-filter pre-existing Ruff findings."""
        coordinator = AutofixCoordinator()
        plan = FixPlan(
            file_path="/tmp/test.py",
            issue_type="COMPLEXITY",
            issue_stage="ruff-check",
            rationale="Reduce complexity",
            risk_level="low",
            validated_by="test",
        )

        assert coordinator._should_compare_validation_to_original(plan) is True

    def test_validation_compares_to_original_for_high_risk_non_complexity_plan(
        self, tmp_path: Path,
    ) -> None:
        """High-risk plans (any issue_type) should compare against the
        original to catch regressions. The complexity branch is
        covered by test_validation_compares_to_original_for_complexity_plan.
        """
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        target = tmp_path / "target.py"
        target.write_text("def target():\n    return 1\n")
        plan = FixPlan(
            file_path=str(target),
            issue_type="SECURITY",
            issue_stage="bandit",
            rationale="Tighten auth check",
            risk_level="high",
            validated_by="test",
        )
        assert coordinator._should_compare_validation_to_original(plan) is True, (
            "Tier-3 #L11: high-risk plans must compare against the "
            "original to detect regressions; the method should not "
            "be a degenerate 'return True'."
        )

    def test_validation_skips_comparison_for_low_risk_simple_plan(
        self, tmp_path: Path,
    ) -> None:
        """Low-risk plans (non-COMPLEXITY) should skip the comparison
        to avoid baseline-filtering noise from pre-existing issues.
        """
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        target = tmp_path / "target.py"
        target.write_text("def target():\n    return 1\n")
        plan = FixPlan(
            file_path=str(target),
            issue_type="FORMATTING",
            issue_stage="ruff-format",
            rationale="Reformat for style",
            risk_level="low",
            validated_by="test",
        )
        assert coordinator._should_compare_validation_to_original(plan) is False, (
            "Tier-3 #L11: low-risk, non-COMPLEXITY plans should skip the "
            "comparison; the previous body was a degenerate 'return True' "
            "that always triggered the comparison."
        )

    @pytest.mark.asyncio
    async def test_execute_plan_uses_baseline_validation_for_complexity(
        self, tmp_path: Path
    ) -> None:
        """Plan validation should compare against original for complexity fixes."""
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        target = tmp_path / "target.py"
        target.write_text("def target():\n    return 1\n")
        plan = FixPlan(
            file_path=str(target),
            issue_type="COMPLEXITY",
            issue_stage="ruff-check",
            rationale="Reduce complexity",
            risk_level="low",
            validated_by="test",
            changes=[
                ChangeSpec(
                    line_range=(1, 2),
                    old_code="def target():\n    return 1",
                    new_code="def target():\n    return 2",
                    reason="test change",
                )
            ],
        )

        fixer = MagicMock()

        def _write_real_diff_then_succeed(*args, **kwargs):
            # Simulate a real fixer: actually rewrite the file so the
            # Bug 1 no-op check does NOT fire. The previous body of
            # this test only returned success=True without writing,
            # which is exactly the "ghost fix" pattern the Bug 1
            # check was added to catch.
            target.write_text("def target():\n    return 2\n")
            return [FixResult(success=True, files_modified=[str(target)])]

        fixer.execute_plans = AsyncMock(side_effect=_write_real_diff_then_succeed)
        validator = MagicMock()
        validator.validate_fix = AsyncMock(return_value=(True, "Fix validated"))

        result, _, _ = await coordinator._execute_plan_with_validation(
            plan,
            fixer,
            validator,
            bar=None,
        )

        assert result is True
        validator.validate_fix.assert_awaited_once()
        assert validator.validate_fix.await_args.kwargs["quality_checks"] == ("ruff",)
        assert validator.validate_fix.await_args.kwargs["compare_to_original"] is True

    @pytest.mark.asyncio
    async def test_no_op_fix_returns_failure_and_skips_validation(
        self, tmp_path: Path
    ) -> None:
        """A fixer that reports success but does not touch the file is a
        ghost fix. The coordinator must surface this as a failure WITHOUT
        reaching validation, and must leave the file on disk untouched.

        Bug 1 (disk-write truthfulness).
        """
        from crackerjack.models.fix_plan import FixPlan as _FixPlan

        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        target = tmp_path / "module.py"
        original = "def foo():\n    return 1\n"
        target.write_text(original)

        plan = _FixPlan(
            file_path=str(target),
            issue_type="FORMATTING",
            issue_stage="ruff-format",
            rationale="Reformat for style",
            risk_level="low",
            validated_by="test",
        )

        fixer = MagicMock()
        fixer.execute_plans = AsyncMock(
            return_value=[
                FixResult(success=True, files_modified=[str(target)])
            ]
        )

        sentinel = {"validate_fix_called": False}

        def _validate_fix_side_effect(**_kwargs: object) -> tuple[bool, str]:
            sentinel["validate_fix_called"] = True
            return (True, "ok")

        validator = MagicMock()
        validator.validate_fix = AsyncMock(side_effect=_validate_fix_side_effect)

        success, applied, msg = await coordinator._execute_plan_with_validation(
            plan, fixer, validator, bar=None
        )

        assert success is False, (
            "no-op fix (success=True but file unchanged) must surface as "
            "a failure, not a success"
        )
        assert applied == []
        assert "no-op" in msg
        assert target.read_text() == original
        assert sentinel["validate_fix_called"] is False, (
            "validation must NOT be invoked when the no-op check fails"
        )

    @pytest.mark.asyncio
    async def test_no_op_fix_rollback_failure_preserves_context(
        self, tmp_path: Path
    ) -> None:
        """When the no-op detection triggers rollback AND the rollback
        itself raises (e.g. backup file already gone), the original
        no-op reason must be preserved in the returned message.
        """
        from crackerjack.models.fix_plan import FixPlan as _FixPlan

        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        target = tmp_path / "module.py"
        target.write_text("x = 1\n")

        plan = _FixPlan(
            file_path=str(target),
            issue_type="FORMATTING",
            issue_stage="ruff-format",
            rationale="Reformat",
            risk_level="low",
            validated_by="test",
        )

        fixer = MagicMock()
        fixer.execute_plans = AsyncMock(
            return_value=[
                FixResult(success=True, files_modified=[str(target)])
            ]
        )
        coordinator._restore_backup = MagicMock(
            side_effect=OSError("backup file gone")
        )

        validator = MagicMock()
        validator.validate_fix = AsyncMock(return_value=(True, ""))

        success, _, msg = await coordinator._execute_plan_with_validation(
            plan, fixer, validator, bar=None
        )

        assert success is False
        assert "no-op" in msg
        assert "rollback failed" in msg

    @pytest.mark.asyncio
    async def test_output_validation_failure_includes_traceback_in_feedback(
        self, tmp_path: Path
    ) -> None:
        """When OutputValidator returns a failure with details, the autofix
        coordinator must enrich the returned feedback so the traceback
        reaches the regenerator's prompt context.

        Regression: prior to this fix, ``validation_result.details`` was
        discarded; the fixer only saw the abstract ``reason`` and had no
        diagnostic context to escape the no-progress loop.
        """
        from crackerjack.ai_fix.output_validator import ValidationResult
        from crackerjack.models.fix_plan import FixPlan as _FixPlan

        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        target = tmp_path / "module.py"
        target.write_text("x = 1\n")

        plan = _FixPlan(
            file_path=str(target),
            issue_type="FORMATTING",
            issue_stage="ruff-check",
            rationale="Reformat",
            risk_level="low",
            validated_by="test",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="x = 1",
                    new_code="x = 1  # noqa",
                    reason="suppress",
                )
            ],
        )

        fake_details = [
            "Traceback (most recent call last):",
            "  File \"crackerjack/tools/ty_imports.py\", line 220, in apply_import_fix",
            "    some_obj.__dict__",
            "AttributeError: 'NoneType' object has no attribute '__dict__'",
        ]

        failed_validation = ValidationResult(
            passed=False,
            reason="AttributeError: 'NoneType' object has no attribute '__dict__'",
            details=fake_details,
        )

        fake_output_validator = MagicMock()
        fake_output_validator.validate = MagicMock(return_value=failed_validation)
        coordinator._output_validator = fake_output_validator  # type: ignore[assignment]

        fixer = MagicMock()

        def _write_real_diff_then_succeed(*args: object, **kwargs: object) -> list[FixResult]:
            target.write_text("x = 1  # noqa\n")
            return [FixResult(success=True, files_modified=[str(target)])]

        fixer.execute_plans = AsyncMock(side_effect=_write_real_diff_then_succeed)

        validator = MagicMock()
        validator.validate_fix = AsyncMock(return_value=(True, "unused"))

        success, _, msg = await coordinator._execute_plan_with_validation(
            plan, fixer, validator, bar=None
        )

        assert success is False
        assert "output validation failed" in msg
        assert "Previous fix attempt failed with:" in msg
        assert "Traceback:" in msg
        assert "diagnose that frame" in msg
        assert "crackerjack/tools/ty_imports.py\", line 220" in msg

    @pytest.mark.asyncio
    async def test_complexity_plan_dedup_preserves_distinct_lines(self) -> None:
        """Complexity plans in the same file should not collapse by file only."""
        coordinator = AutofixCoordinator()
        plans = [
            FixPlan(
                file_path="/tmp/test.py",
                issue_type="COMPLEXITY",
                rationale="one",
                risk_level="low",
                validated_by="test",
                changes=[
                    ChangeSpec(
                        line_range=(10, 20),
                        old_code="old",
                        new_code="new",
                        reason="one",
                    )
                ],
            ),
            FixPlan(
                file_path="/tmp/test.py",
                issue_type="COMPLEXITY",
                rationale="two",
                risk_level="low",
                validated_by="test",
                changes=[
                    ChangeSpec(
                        line_range=(30, 40),
                        old_code="old",
                        new_code="new",
                        reason="two",
                    )
                ],
            ),
        ]
        fixer = MagicMock()
        validator = MagicMock()
        analysis = MagicMock()
        with patch.object(
            coordinator,
            "_execute_single_plan_with_retry",
            new_callable=AsyncMock,
            return_value=FixResult(success=True),
        ) as execute:
            results = await coordinator._execute_plans_with_validation(
                plans,
                fixer,
                validator,
                analysis,
                issues=[],
            )

        assert len(results) == 2
        assert execute.await_count == 2

    @pytest.mark.asyncio
    async def test_import_error_plan_dedup_preserves_distinct_lines(self) -> None:
        """Import-error plans in the same file should dedup by line, not file only."""
        coordinator = AutofixCoordinator()
        plans = [
            FixPlan(
                file_path="/tmp/test.py",
                issue_type="IMPORT_ERROR",
                rationale="one",
                risk_level="low",
                validated_by="test",
                changes=[
                    ChangeSpec(
                        line_range=(10, 10),
                        old_code="import a",
                        new_code="import a  # noqa: F401",
                        reason="one",
                    )
                ],
            ),
            FixPlan(
                file_path="/tmp/test.py",
                issue_type="IMPORT_ERROR",
                rationale="two",
                risk_level="low",
                validated_by="test",
                changes=[
                    ChangeSpec(
                        line_range=(30, 30),
                        old_code="import b",
                        new_code="import b  # noqa: F401",
                        reason="two",
                    )
                ],
            ),
        ]
        fixer = MagicMock()
        validator = MagicMock()
        analysis = MagicMock()
        with patch.object(
            coordinator,
            "_execute_single_plan_with_retry",
            new_callable=AsyncMock,
            return_value=FixResult(success=True),
        ) as execute:
            results = await coordinator._execute_plans_with_validation(
                plans,
                fixer,
                validator,
                analysis,
                issues=[],
            )

        assert len(results) == 2
        assert execute.await_count == 2

    def test_check_execution_results_requires_all_plans_to_succeed(self) -> None:
        """V2 pipeline success should not hide partial plan failure."""
        coordinator = AutofixCoordinator()

        with patch.object(coordinator, "_display_error_summary"):
            assert coordinator._check_execution_results([FixResult(success=True)])
            assert not coordinator._check_execution_results(
                [FixResult(success=True), FixResult(success=False)]
            )

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason=(
            "Source: _apply_ai_agent_fixes_v2 calls _execute_fast_fixes() "
            "unconditionally for the comprehensive stage; test premise wrong"
        ),
        strict=False,
    )
    async def test_comprehensive_v2_does_not_run_fast_fix_pass(self) -> None:
        """Comprehensive AI analysis should not run deterministic fast fix commands."""
        coordinator = AutofixCoordinator()
        issue = Issue(
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="security issue",
            file_path="/tmp/example.py",
            line_number=1,
            stage="semgrep",
        )

        preflight_mock = MagicMock()
        preflight_mock.run = AsyncMock()

        with (
            patch("crackerjack.core.autofix_coordinator.PreflightFixer", return_value=preflight_mock),
            patch.object(coordinator, "_collect_fixable_issues", return_value=[issue]),
            patch.object(coordinator, "_filter_fixable_issues", return_value=[issue]),
            patch.object(
                coordinator,
                "_apply_type_tool_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_ruff_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_refurb_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_zuban_fix_prepass",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_hook_diagnostics_context",
                new_callable=AsyncMock,
                return_value=[issue],
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_reformat_prepass",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                coordinator, "_execute_fast_fixes", new_callable=AsyncMock
            ) as fast_fixes,
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                coordinator,
                "_run_v2_ai_fix_iteration_loop",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            result = await coordinator._apply_ai_agent_fixes_v2(
                [],
                stage="comprehensive",
            )

        assert result is False
        fast_fixes.assert_not_called()


class TestAutofixCoordinatorInitialCountSnapshot:
    """Bug #1c: Initial hook count must be snapshotted BEFORE _collect_fixable_issues.

    `_collect_fixable_issues` calls `_update_hook_issue_counts`, which mutates
    `result.issues_count` UPWARD (the "never downgrade to 0" invariant).
    If `compute_hook_total(hook_results)` is read AFTER this mutation, the AI
    engine panel reports an inflated number (e.g. 19) that doesn't match the
    Comprehensive Hooks table (e.g. 13) shown moments earlier.
    """

    @pytest.mark.asyncio
    async def test_initial_count_snapshotted_before_collect_mutates(self) -> None:
        coordinator = AutofixCoordinator()

        # Hook result starts with issues_count=5 (matches the visible
        # Comprehensive Hooks table seen by the user just before the AI
        # engine kicks in).
        hook_result = SimpleNamespace(
            name="creosote",
            status="failed",
            issues_count=5,
            is_config_error=False,
        )
        hook_results = [hook_result]

        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: dill",
            file_path="pyproject.toml",
            stage="creosote",
        )

        def mutating_collect(passed_hook_results):
            # Simulate _update_hook_issue_counts mutating issues_count upward.
            hook_result.issues_count = 11
            return [issue]

        captured_initial_counts: list[int] = []

        original_start = coordinator.progress_manager.start_fix_session

        def capturing_start(*, stage, initial_issue_count, **kwargs):
            captured_initial_counts.append(initial_issue_count)
            return original_start(
                stage=stage, initial_issue_count=initial_issue_count, **kwargs
            )

        with (
            patch.object(
                coordinator,
                "_collect_fixable_issues",
                side_effect=mutating_collect,
            ),
            patch.object(
                coordinator, "_filter_fixable_issues", side_effect=lambda issues: issues
            ),
            patch.object(
                coordinator,
                "_apply_type_tool_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_zuban_fix_prepass",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_hook_diagnostics_context",
                new_callable=AsyncMock,
                side_effect=lambda issues, stage: issues,
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_reformat_prepass",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                coordinator,
                "_apply_refurb_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                coordinator.progress_manager,
                "start_fix_session",
                side_effect=capturing_start,
            ),
        ):
            await coordinator._apply_ai_agent_fixes_v2(
                hook_results, stage="comprehensive"
            )

        # The snapshot must be 5 — the pre-mutation value matching the
        # Comprehensive Hooks table. If start_fix_session received 11, the
        # snapshot was taken AFTER _collect_fixable_issues mutated
        # issues_count, and the AI engine panel would lie to the user.
        assert captured_initial_counts == [5], (
            "Expected start_fix_session to be called once with initial_issue_count=5 "
            f"(pre-mutation), but got: {captured_initial_counts}. "
            "This means compute_hook_total ran AFTER _collect_fixable_issues "
            "mutated issues_count — the snapshot must be captured BEFORE."
        )


class TestAutofixCoordinatorRefurbPrepassResult:
    """Bug #3: refurb prepass result is captured but never replaces the issues list.

    The sibling prepasses (`_apply_type_tool_fix_prepasses`, `_apply_zuban_fix_prepass`)
    follow the pattern:

        refreshed = await self._apply_X_fix_prepasses(hook_results)
        if refreshed:
            issues = self._replace_refreshed_type_issues(issues, refreshed)

    `_apply_refurb_fix_prepasses` returns the *same* dict shape, but the call site
    at `_apply_ai_agent_fixes_v2` only checks truthiness and logs it — the
    refreshed issues never make it into the list the AI engine iterates on.

    This is the silent-success half of the dhara false-convergence: the
    deterministic refurb pass *does* fix some issues, but the AI engine still
    sees the original pre-fix list and concludes nothing changed.
    """

    @pytest.mark.asyncio
    async def test_refurb_prepass_result_replaces_issues_for_ai_loop(self) -> None:
        coordinator = AutofixCoordinator()

        # Three pre-existing issues, including one refurb issue.
        original_refurb_issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.MEDIUM,
            message="[FURB113] Use augmented assignment",
            file_path="src/example.py",
            line_number=10,
            stage="refurb",
        )
        other_issue = Issue(
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="some semgrep finding",
            file_path="src/other.py",
            line_number=1,
            stage="semgrep",
        )
        original_issues = [original_refurb_issue, other_issue]

        # After the deterministic refurb pass runs, the refurbed file is
        # clean — refurb re-scan returns zero issues. The dict shape mirrors
        # what `_apply_refurb_fix_prepasses` actually returns.
        refreshed_refurb_issues: dict[str, list[Issue]] = {
            "refurb": [],
        }

        # Capture the `initial_issues` kwarg passed into the iteration loop.
        captured: dict[str, list[Issue]] = {}

        async def capture_initial_issues(*args, **kwargs):
            captured["initial_issues"] = kwargs.get("initial_issues") or (
                args[3] if len(args) > 3 else None
            )
            return False  # don't actually run the loop

        with (
            patch.object(
                coordinator, "_collect_fixable_issues", return_value=original_issues
            ),
            patch.object(
                coordinator,
                "_filter_fixable_issues",
                side_effect=lambda issues: issues,
            ),
            patch.object(
                coordinator,
                "_apply_type_tool_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_zuban_fix_prepass",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_hook_diagnostics_context",
                new_callable=AsyncMock,
                side_effect=lambda issues, stage: issues,
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_reformat_prepass",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                coordinator,
                "_apply_refurb_fix_prepasses",
                new_callable=AsyncMock,
                return_value=refreshed_refurb_issues,
            ),
            patch.object(
                coordinator,
                "_run_v2_ai_fix_iteration_loop",
                side_effect=capture_initial_issues,
            ),
        ):
            await coordinator._apply_ai_agent_fixes_v2([], stage="comprehensive")

        assert "initial_issues" in captured, (
            "_run_v2_ai_fix_iteration_loop was never called — the test setup "
            "is broken (one of the patches short-circuited the function)."
        )

        # The post-prepass issues list should have the refurb issue REMOVED
        # (because refurb re-scan found zero issues). The other issue survives.
        stages_in_ai_loop = {issue.stage for issue in captured["initial_issues"]}
        assert "refurb" not in stages_in_ai_loop, (
            "Refurb prepass returned a refreshed 'refurb' issue list, but the "
            "AI engine still sees the original refurb issues. "
            "The call site at _apply_ai_agent_fixes_v2 must call "
            "_replace_refreshed_type_issues(issues, refreshed_refurb_issues) "
            "the same way the type/zuban prepasses do."
        )
        assert "semgrep" in stages_in_ai_loop, (
            "Sanity check failed: the unrelated semgrep issue should still be "
            "in the list passed to the AI loop. If it isn't, the test setup "
            "is over-mocking the iteration logic."
        )


class TestAutofixCoordinatorThreadedLoopDaemon:
    """Bug #4: spawn the inner thread with daemon=True so it cannot outlive the
    main process on KeyboardInterrupt.

    The original symptom: the comp stage hangs *after* the first iteration and
    only unfreezes on Ctrl+C. The user has to manually kill the process.

    `_run_in_threaded_loop` (autofix_coordinator.py:1401) creates a non-daemon
    thread and joins with a 300s timeout. If the inner coroutine hangs without
    honouring the `asyncio.wait_for` deadline (e.g. it spawns its own threads
    or blocks on a synchronous wait), the thread keeps running after
    `join(timeout=300)` returns. A non-daemon thread holds the interpreter
    open — Ctrl+C only interrupts the main thread, the worker thread keeps
    the process alive, and the user has to escalate to SIGKILL.

    Spawning with `daemon=True` is the minimal correct fix: the worker is
    killed when the main thread exits, so the process can actually terminate
    on Ctrl+C. The cost (worker may be killed mid-task) is the right
    trade-off — a hung coroutine is doing nothing useful anyway.
    """

    def test_inner_thread_is_daemon_so_keyboard_interrupt_can_exit(self) -> None:
        """The thread spawned by `_run_in_threaded_loop` must be daemon=True.

        We monkeypatch `threading.Thread` at the import site used by the
        production code (`import threading` is local to the function body, so
        the patch must hit the module's `threading` reference at call time —
        we patch `crackerjack.core.autofix_coordinator.threading` if present,
        else the stdlib `threading` module which the function imports via
        `import threading`).
        """
        import threading

        coordinator = AutofixCoordinator()

        # A handle_issues that hangs forever — guarantees the inner
        # coroutine never completes, so the only way the test ends is via
        # the daemon-thread mechanism.
        hang_forever = AsyncMock(
            side_effect=lambda *a, **kw: _hang_forever_or_timeout()
        )

        fake_coordinator = MagicMock()
        fake_coordinator.handle_issues = hang_forever

        captured: dict[str, object] = {}

        original_thread_cls = threading.Thread

        class RecordingThread:
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)
                self._real = original_thread_cls(*args, **kwargs)
                # Carry the daemon flag through to assertable state.
                captured.setdefault("daemon", kwargs.get("daemon", False))

            def start(self) -> None:
                # Don't actually start — the join() below would block for
                # the full 300s timeout, and we don't need the thread to
                # run for this assertion.
                captured["started"] = True

            def join(self, timeout=None) -> None:
                captured["join_timeout"] = timeout
                # Simulate the thread having exited cleanly with no result
                # so the production code path raises RuntimeError as if the
                # 300s elapsed.
                captured["joined"] = True

        with patch("threading.Thread", RecordingThread):
            with pytest.raises(RuntimeError, match="AI agent fixing timed out"):
                coordinator._run_in_threaded_loop(fake_coordinator, [], 0)

        # The thread MUST be daemon=True. Non-daemon threads prevent the
        # interpreter from exiting on KeyboardInterrupt, which is exactly
        # the "have to Ctrl+C" behaviour the user reported.
        assert captured.get("daemon") is True, (
            f"_run_in_threaded_loop spawned a non-daemon thread (daemon="
            f"{captured.get('daemon')!r}). This means Ctrl+C cannot exit the "
            f"process while a hung AI worker is alive, and the user has to "
            f"escalate to SIGKILL. The fix is one character: pass daemon=True "
            f"to threading.Thread(...)."
        )


async def _hang_forever_or_timeout() -> None:
    """A coroutine that never returns — used to force the timeout path."""
    import asyncio

    await asyncio.sleep(3600)


class TestMahavishnuPoolDispatcherModuleRemoved:
    """Tier-1 DELETE cleanup: the MahavishnuPoolDispatcher integration has been
    retired by the wave decision. After the GREEN step the integration module
    is gone and the ``choose_dispatcher`` kill-list import is gone.

    ``importlib`` is imported locally (not at module top) so this test file's
    public import surface is unchanged.
    """

    def test_pool_dispatcher_module_is_removed(self) -> None:
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(
                "crackerjack.integration.mahavishnu_pool_dispatcher"
            )

    def test_autofix_coordinator_does_not_re_export_choose_dispatcher(
        self,
    ) -> None:
        import importlib

        module = importlib.import_module("crackerjack.core.autofix_coordinator")
        assert not hasattr(module, "choose_dispatcher"), (
            "crackerjack.core.autofix_coordinator must not re-export "
            "choose_dispatcher after the MahavishnuPoolDispatcher DELETE. "
            "The kill-list import at autofix_coordinator.py:36 must be removed "
            "and the call site must construct ParallelDispatcher directly."
        )


class TestBuildPreviousResultsFromStatuses:
    """Tier-3 #L13 lock-in.

    The plan flagged this function for fabricating empty HookResult
    objects. The current implementation uses SimpleNamespace to
    stand in for a HookResult, but does not invent entries for
    hooks that weren't in the input dict — every output entry
    corresponds to a real (name, status) pair from the input.
    These tests pin that contract so a future refactor that
    re-introduces fabrication is caught immediately.
    """

    def test_returns_one_namespace_per_input_status(self) -> None:
        coordinator = AutofixCoordinator()
        statuses = {
            "ruff": "passed",
            "mypy": "failed",
            "bandit": "warning",
        }
        results = coordinator._build_previous_results_from_statuses(statuses)
        assert len(results) == 3
        by_name = {getattr(r, "name"): r for r in results}
        assert getattr(by_name["ruff"], "status") == "passed"
        assert getattr(by_name["mypy"], "status") == "failed"
        assert getattr(by_name["bandit"], "status") == "warning"

    def test_does_not_fabricate_for_missing_hooks(self) -> None:
        """Empty input -> empty output. The function must not invent
        an 'unknown' entry just to keep the list non-empty.
        """
        coordinator = AutofixCoordinator()
        assert coordinator._build_previous_results_from_statuses({}) == []

    def test_output_attributes_match_namespace_schema(self) -> None:
        """Every output entry must have name, status, issues_found,
        and issues_count attributes. The caller relies on getattr
        for all four.
        """
        coordinator = AutofixCoordinator()
        results = coordinator._build_previous_results_from_statuses(
            {"ruff": "passed"},
        )
        assert len(results) == 1
        entry = results[0]
        for attr in ("name", "status", "issues_found", "issues_count"):
            assert hasattr(entry, attr), f"Missing attribute: {attr}"


class TestAutofixCoordinatorRuffDedup:
    """Tier-3 #12: Stop running ruff/refurb 3× per V2 invocation.

    `_apply_ai_agent_fixes_v2` runs ruff-like tools in three phases:
    1. Preflight (`await preflight.run(...)`) — ruff check/format/refurb.
    2. Refurb prepass (`await self._apply_refurb_fix_prepasses(...)`) — refurb.
    3. Fast fixes (`await self._execute_fast_fixes()`) — ruff check/format.

    Each phase is expensive. When no files have changed between phases, the
    subsequent ruff/refurb runs are wasted work. The fix is a `_FileChangeTracker`
    that snapshots mtimes and gates each phase on a non-zero delta.

    These tests pin the public contract: when the tracker reports zero changes,
    preflight/refurb/fast-fixes are skipped.
    """

    @pytest.mark.asyncio
    async def test_v2_skips_refurb_prepass_when_no_files_changed(self) -> None:
        """Tier-3 #12: skip refurb prepass when no files have changed since preflight."""
        from crackerjack.core.preflight import PreflightConfig

        coordinator = AutofixCoordinator(
            preflight_config=PreflightConfig(),
        )
        issue = Issue(
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="security issue",
            file_path="/tmp/example.py",
            line_number=1,
            stage="semgrep",
        )

        preflight_mock = MagicMock()
        preflight_mock.run = AsyncMock()

        # Replace `_FileChangeTracker` with a stub that reports zero delta —
        # no files have changed since preflight, so refurb must be skipped.
        tracker_stub = MagicMock()
        tracker_stub.delta = MagicMock(return_value=0)
        tracker_stub.capture = MagicMock()

        with (
            patch(
                "crackerjack.core.autofix_coordinator.PreflightFixer",
                return_value=preflight_mock,
            ),
            patch(
                "crackerjack.core.autofix_coordinator._FileChangeTracker",
                return_value=tracker_stub,
            ),
            patch.object(
                coordinator, "_collect_fixable_issues", return_value=[issue]
            ),
            patch.object(
                coordinator,
                "_filter_fixable_issues",
                side_effect=lambda issues: issues,
            ),
            patch.object(
                coordinator,
                "_apply_type_tool_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_zuban_fix_prepass",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_hook_diagnostics_context",
                new_callable=AsyncMock,
                side_effect=lambda issues, stage: issues,
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_reformat_prepass",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                coordinator,
                "_apply_refurb_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ) as refurb_prepass,
            patch.object(
                coordinator, "_execute_fast_fixes", new_callable=AsyncMock
            ),
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                coordinator,
                "_run_v2_ai_fix_iteration_loop",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            await coordinator._apply_ai_agent_fixes_v2([], stage="fast")

        refurb_prepass.assert_not_called()

    @pytest.mark.asyncio
    async def test_v2_runs_refurb_prepass_when_files_changed(self) -> None:
        """Tier-3 #12: when files change between preflight and refurb prepass,
        the prepass must still run."""
        from crackerjack.core.preflight import PreflightConfig

        coordinator = AutofixCoordinator(
            preflight_config=PreflightConfig(),
        )
        issue = Issue(
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="security issue",
            file_path="/tmp/example.py",
            line_number=1,
            stage="semgrep",
        )

        preflight_mock = MagicMock()
        preflight_mock.run = AsyncMock()

        # Tracker reports a non-zero delta — files changed since preflight,
        # so refurb prepass should still run.
        tracker_stub = MagicMock()
        tracker_stub.delta = MagicMock(return_value=3)
        tracker_stub.capture = MagicMock()

        with (
            patch(
                "crackerjack.core.autofix_coordinator.PreflightFixer",
                return_value=preflight_mock,
            ),
            patch(
                "crackerjack.core.autofix_coordinator._FileChangeTracker",
                return_value=tracker_stub,
            ),
            patch.object(
                coordinator, "_collect_fixable_issues", return_value=[issue]
            ),
            patch.object(
                coordinator,
                "_filter_fixable_issues",
                side_effect=lambda issues: issues,
            ),
            patch.object(
                coordinator,
                "_apply_type_tool_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_zuban_fix_prepass",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_hook_diagnostics_context",
                new_callable=AsyncMock,
                side_effect=lambda issues, stage: issues,
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_reformat_prepass",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                coordinator,
                "_apply_refurb_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ) as refurb_prepass,
            patch.object(
                coordinator, "_execute_fast_fixes", new_callable=AsyncMock
            ),
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                coordinator,
                "_run_v2_ai_fix_iteration_loop",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            await coordinator._apply_ai_agent_fixes_v2([], stage="fast")

        refurb_prepass.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_v2_skips_fast_fixes_when_no_files_changed(self) -> None:
        """Tier-3 #12: skip deterministic fast fixes (ruff check/format) when
        no files have changed since the previous prepass.
        """
        from crackerjack.core.preflight import PreflightConfig

        coordinator = AutofixCoordinator(
            preflight_config=PreflightConfig(),
        )
        issue = Issue(
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="security issue",
            file_path="/tmp/example.py",
            line_number=1,
            stage="semgrep",
        )

        preflight_mock = MagicMock()
        preflight_mock.run = AsyncMock()

        tracker_stub = MagicMock()
        tracker_stub.delta = MagicMock(return_value=0)
        tracker_stub.capture = MagicMock()

        with (
            patch(
                "crackerjack.core.autofix_coordinator.PreflightFixer",
                return_value=preflight_mock,
            ),
            patch(
                "crackerjack.core.autofix_coordinator._FileChangeTracker",
                return_value=tracker_stub,
            ),
            patch.object(
                coordinator, "_collect_fixable_issues", return_value=[issue]
            ),
            patch.object(
                coordinator,
                "_filter_fixable_issues",
                side_effect=lambda issues: issues,
            ),
            patch.object(
                coordinator,
                "_apply_type_tool_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_zuban_fix_prepass",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_hook_diagnostics_context",
                new_callable=AsyncMock,
                side_effect=lambda issues, stage: issues,
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_reformat_prepass",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                coordinator,
                "_apply_refurb_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator, "_execute_fast_fixes", new_callable=AsyncMock
            ) as fast_fixes,
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                coordinator,
                "_run_v2_ai_fix_iteration_loop",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            await coordinator._apply_ai_agent_fixes_v2([], stage="fast")

        fast_fixes.assert_not_called()

    @pytest.mark.asyncio
    async def test_v2_force_prepass_overrides_skip(self) -> None:
        """Tier-3 #12: when `force_prepass=True` is configured, the prepass
        must run even when no files have changed.
        """
        from crackerjack.core.preflight import PreflightConfig

        coordinator = AutofixCoordinator(
            preflight_config=PreflightConfig(force_prepass=True),
        )
        issue = Issue(
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="security issue",
            file_path="/tmp/example.py",
            line_number=1,
            stage="semgrep",
        )

        preflight_mock = MagicMock()
        preflight_mock.run = AsyncMock()

        tracker_stub = MagicMock()
        tracker_stub.delta = MagicMock(return_value=0)
        tracker_stub.capture = MagicMock()

        with (
            patch(
                "crackerjack.core.autofix_coordinator.PreflightFixer",
                return_value=preflight_mock,
            ),
            patch(
                "crackerjack.core.autofix_coordinator._FileChangeTracker",
                return_value=tracker_stub,
            ),
            patch.object(
                coordinator, "_collect_fixable_issues", return_value=[issue]
            ),
            patch.object(
                coordinator,
                "_filter_fixable_issues",
                side_effect=lambda issues: issues,
            ),
            patch.object(
                coordinator,
                "_apply_type_tool_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_zuban_fix_prepass",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_hook_diagnostics_context",
                new_callable=AsyncMock,
                side_effect=lambda issues, stage: issues,
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_reformat_prepass",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                coordinator,
                "_apply_refurb_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ) as refurb_prepass,
            patch.object(
                coordinator, "_execute_fast_fixes", new_callable=AsyncMock
            ),
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                coordinator,
                "_run_v2_ai_fix_iteration_loop",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            await coordinator._apply_ai_agent_fixes_v2([], stage="fast")

        refurb_prepass.assert_awaited_once()


class TestFileChangeTracker:
    """Tier-3 #12: `_FileChangeTracker` snapshot primitive."""

    def test_capture_then_delta_no_changes(self, tmp_path: Path) -> None:
        """After capture, delta is 0 when nothing has changed."""
        from crackerjack.core.autofix_coordinator import _FileChangeTracker

        (tmp_path / "a.py").write_text("x = 1")
        tracker = _FileChangeTracker(tmp_path)
        tracker.capture()
        assert tracker.delta() == 0

    def test_capture_then_delta_detects_change(self, tmp_path: Path) -> None:
        """delta reports the number of files whose mtime changed since capture."""
        from crackerjack.core.autofix_coordinator import _FileChangeTracker

        f = tmp_path / "a.py"
        f.write_text("x = 1")
        tracker = _FileChangeTracker(tmp_path)
        tracker.capture()
        f.write_text("x = 2")
        assert tracker.delta() == 1

    def test_capture_resets_baseline(self, tmp_path: Path) -> None:
        """Calling capture() a second time moves the baseline forward."""
        from crackerjack.core.autofix_coordinator import _FileChangeTracker

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
        from crackerjack.core.autofix_coordinator import _FileChangeTracker

        (tmp_path / "a.py").write_text("x = 1")
        tracker = _FileChangeTracker(tmp_path)
        assert tracker.delta() == 0


class TestStdoutHashShortCircuit:
    """Tier-3 #14: `_execute_check_commands` should short-circuit when the
    stdout-hash signature for a hook is unchanged across iterations and no
    files have been modified.
    """

    def test_stdout_hash_skips_repeat_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Second call with the same scope files and unchanged file state
        should NOT invoke `_run_check_command` again for hooks that already
        have a cached stdout-hash signature."""
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        coordinator._stdout_hash_cache = {}

        check_commands: list[tuple[list[str], str, int]] = [
            (["echo", "ok"], "ruff", 60),
        ]

        fake_process = MagicMock()
        fake_process.returncode = 0

        with patch.object(
            coordinator, "_run_check_command", return_value=(fake_process, "", "")
        ) as mock_run:
            with patch.object(
                coordinator, "_process_check_result", return_value=[]
            ):
                # First call: signature unknown, tool runs and is cached.
                coordinator._execute_check_commands(check_commands)
                # Second call: signature matches previous, tool MUST be skipped.
                coordinator._execute_check_commands(check_commands)

        assert mock_run.call_count == 1, (
            f"expected `_run_check_command` to be invoked exactly once "
            f"across two identical `_execute_check_commands` calls, got "
            f"{mock_run.call_count}"
        )

    def test_stdout_hash_resets_after_file_change(
        self, tmp_path: Path
    ) -> None:
        """When `_active_ai_fix_scope_files` changes between calls, the
        short-circuit must NOT fire and the tool must be re-invoked."""
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        coordinator._stdout_hash_cache = {}

        file_a = tmp_path / "a.py"
        file_a.write_text("x = 1")

        check_commands: list[tuple[list[str], str, int]] = [
            (["echo", "ok"], "ruff", 60),
        ]
        fake_process = MagicMock()
        fake_process.returncode = 0

        with patch.object(
            coordinator, "_run_check_command", return_value=(fake_process, "", "")
        ) as mock_run:
            with patch.object(
                coordinator, "_process_check_result", return_value=[]
            ):
                # Iteration 1: empty scope — runs once, caches signature.
                coordinator._execute_check_commands(check_commands)
                # Iteration 2: scope changed — cache miss, must re-run.
                coordinator._active_ai_fix_scope_files = {str(file_a)}
                coordinator._execute_check_commands(check_commands)

        assert mock_run.call_count == 2, (
            f"expected `_run_check_command` to be invoked twice when the "
            f"scope files change between calls, got {mock_run.call_count}"
        )

    def test_signature_changes_when_file_mtime_changes(
        self, tmp_path: Path
    ) -> None:
        """The signature is content-addressed; changing the mtime of a
        tracked scope file invalidates the cached signature."""
        scope_file = tmp_path / "scope.py"
        scope_file.write_text("x = 1")

        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        sig_a = coordinator._check_command_output_signature(
            "ruff", [scope_file]
        )

        # Bump mtime to simulate an AI fix rewriting the file.
        import os as _os

        _os.utime(scope_file, (scope_file.stat().st_atime, scope_file.stat().st_mtime + 5))
        sig_b = coordinator._check_command_output_signature(
            "ruff", [scope_file]
        )

        assert sig_a != sig_b, (
            "expected `_check_command_output_signature` to produce a different "
            "signature when a scope file's mtime changes"
        )
