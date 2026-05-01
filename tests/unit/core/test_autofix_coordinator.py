"""Unit tests for autofix coordinator components."""

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
            with patch.object(coordinator, "_execute_fast_fixes", return_value=True):
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

    def test_strict_validation_mode_for_complexity_plan(self) -> None:
        """Complexity plans should not baseline-filter old Ruff findings."""
        coordinator = AutofixCoordinator()
        plan = FixPlan(
            file_path="/tmp/test.py",
            issue_type="COMPLEXITY",
            issue_stage="ruff-check",
            rationale="Reduce complexity",
            risk_level="low",
            validated_by="test",
        )

        assert coordinator._should_compare_validation_to_original(plan) is False

    @pytest.mark.asyncio
    async def test_execute_plan_uses_strict_validation_for_complexity(
        self, tmp_path: Path
    ) -> None:
        """Plan validation should pass strict Ruff mode for complexity fixes."""
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
        fixer.execute_plans = AsyncMock(
            return_value=[FixResult(success=True, files_modified=[str(target)])]
        )
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
        assert validator.validate_fix.await_args.kwargs["compare_to_original"] is False

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

    def test_check_execution_results_requires_all_plans_to_succeed(self) -> None:
        """V2 pipeline success should not hide partial plan failure."""
        coordinator = AutofixCoordinator()

        with patch.object(coordinator, "_display_error_summary"):
            assert coordinator._check_execution_results([FixResult(success=True)])
            assert not coordinator._check_execution_results(
                [FixResult(success=True), FixResult(success=False)]
            )

    @pytest.mark.asyncio
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

        with (
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
            patch.object(coordinator, "_execute_fast_fixes") as fast_fixes,
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await coordinator._apply_ai_agent_fixes_v2(
                [],
                stage="comprehensive",
            )

        assert result is False
        fast_fixes.assert_not_called()
