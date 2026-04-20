import subprocess
from pathlib import Path
from shutil import copy2 as real_copy2
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.autofix_coordinator import AutofixCoordinator


class TestAutofixCoordinator:
    @pytest.fixture
    def mock_console(self):
        return Mock(spec=Console)

    @pytest.fixture
    def coordinator(self, mock_console):
        pkg_path = Path("/ test / path")
        return AutofixCoordinator(console=mock_console, pkg_path=pkg_path)

    def test_coordinator_initialization(self, mock_console) -> None:
        pkg_path = Path("/ test / path")
        coordinator = AutofixCoordinator(console=mock_console, pkg_path=pkg_path)

        assert coordinator.console is mock_console
        assert coordinator.pkg_path == pkg_path
        assert coordinator.logger.name == "crackerjack.autofix"

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_fast_mode(self, coordinator) -> None:
        hook_results = [Mock(name="test_hook", status="failed")]

        with (
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
            patch.object(
                coordinator, "_apply_fast_stage_fixes", return_value=True
            ) as mock_fast,
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is True
            mock_fast.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_comprehensive_mode(self, coordinator) -> None:
        hook_results = [Mock(name="test_hook", status="failed")]

        with (
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
            patch.object(
                coordinator,
                "_apply_comprehensive_stage_fixes",
                return_value=True,
            ) as mock_comp,
        ):
            result = await coordinator.apply_autofix_for_hooks(
                "comprehensive", hook_results
            )

            assert result is True
            mock_comp.assert_called_once_with(hook_results)

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_skip_when_should_skip(
        self, coordinator
    ) -> None:
        hook_results = [Mock()]

        with patch.object(coordinator, "_should_skip_autofix", return_value=True):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is False

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_unknown_mode(self, coordinator) -> None:
        hook_results = []

        with patch.object(coordinator, "_should_skip_autofix", return_value=False):
            result = await coordinator.apply_autofix_for_hooks("unknown", hook_results)

            assert result is False

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_exception_handling(
        self, coordinator
    ) -> None:
        hook_results = []

        with patch.object(
            coordinator,
            "_should_skip_autofix",
            side_effect=Exception("Test error"),
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is False

    @pytest.mark.asyncio
    async def test_public_interface_methods(self, coordinator) -> None:
        hook_results = [Mock()]
        cmd = ["uv", "run", "ruff", "format", "."]
        result_mock = Mock()

        with (
            patch.object(
                coordinator,
                "_apply_fast_stage_fixes",
                return_value=True,
            ) as mock_fast,
            patch.object(
                coordinator,
                "_apply_comprehensive_stage_fixes",
                return_value=True,
            ) as mock_comp,
            patch.object(
                coordinator,
                "_run_fix_command",
                return_value=True,
            ) as mock_run,
            patch.object(
                coordinator,
                "_check_tool_success_patterns",
                return_value=True,
            ) as mock_check,
            patch.object(
                coordinator,
                "_validate_fix_command",
                return_value=True,
            ) as mock_validate_cmd,
            patch.object(
                coordinator,
                "_validate_hook_result",
                return_value=True,
            ) as mock_validate_hook,
            patch.object(
                coordinator,
                "_should_skip_autofix",
                return_value=False,
            ) as mock_skip,
        ):
            assert await coordinator.apply_fast_stage_fixes() is True
            mock_fast.assert_called_once()

            assert await coordinator.apply_comprehensive_stage_fixes(hook_results) is True
            mock_comp.assert_called_once_with(hook_results)

            assert coordinator.run_fix_command(cmd, "test") is True
            mock_run.assert_called_once_with(cmd, "test")

            assert coordinator.check_tool_success_patterns(cmd, result_mock) is True
            mock_check.assert_called_once_with(cmd, result_mock)

            assert coordinator.validate_fix_command(cmd) is True
            mock_validate_cmd.assert_called_once_with(cmd)

            assert coordinator.validate_hook_result(result_mock) is True
            mock_validate_hook.assert_called_once_with(result_mock)

            assert coordinator.should_skip_autofix(hook_results) is False
            mock_skip.assert_called_once_with(hook_results)

    def test_execute_fast_fixes(self, coordinator) -> None:
        with patch.object(
            coordinator,
            "_run_fix_command",
            return_value=True,
        ) as mock_run:
            result = coordinator._execute_fast_fixes()

            assert result is True
            assert mock_run.call_count == 2

    def test_execute_fast_fixes_no_fixes_applied(self, coordinator) -> None:
        with patch.object(coordinator, "_run_fix_command", return_value=False):
            result = coordinator._execute_fast_fixes()

            assert result is False

    @pytest.mark.asyncio
    async def test_apply_comprehensive_stage_fixes(self, coordinator) -> None:
        hook_results = [Mock(name="bandit", status="failed")]

        with (
            patch.object(
                coordinator, "_execute_fast_fixes", return_value=True
            ) as mock_fast,
            patch.object(coordinator, "_extract_failed_hooks", return_value={"bandit"}),
            patch.object(coordinator, "_get_hook_specific_fixes", return_value=[]),
            patch.object(coordinator, "_run_fix_command", return_value=True),
        ):
            result = await coordinator._apply_comprehensive_stage_fixes(hook_results)

            assert result is True
            mock_fast.assert_called_once()

    def test_extract_failed_hooks(self, coordinator) -> None:
        ruff_result = Mock()
        ruff_result.name = "ruff"
        ruff_result.status = "failed"

        bandit_result = Mock()
        bandit_result.name = "bandit"
        bandit_result.status = "passed"

        pyright_result = Mock()
        pyright_result.name = "pyright"
        pyright_result.status = "failed"

        hook_results = [ruff_result, bandit_result, pyright_result]

        failed_hooks = coordinator._extract_failed_hooks(hook_results)

        assert failed_hooks == {"ruff", "pyright"}

    def test_extract_failed_hooks_invalid_results(self, coordinator) -> None:
        hook_results = [Mock(), Mock()]

        with patch.object(coordinator, "_validate_hook_result", return_value=False):
            failed_hooks = coordinator._extract_failed_hooks(hook_results)

            assert failed_hooks == set()

    def test_get_hook_specific_fixes(self, coordinator) -> None:
        failed_hooks = {"bandit", "ruff"}

        fixes = coordinator._get_hook_specific_fixes(failed_hooks)

        assert len(fixes) == 1
        assert fixes[0][1] == "bandit analysis"

    def test_get_hook_specific_fixes_no_matches(self, coordinator) -> None:
        failed_hooks = {"ruff", "pyright"}

        fixes = coordinator._get_hook_specific_fixes(failed_hooks)

        assert fixes == []

    @patch("subprocess.run")
    def test_run_fix_command_success(self, mock_subprocess, coordinator) -> None:
        cmd = ["uv", "run", "ruff", "format", "."]
        mock_result = Mock(returncode=0, stdout="", stderr="")
        mock_subprocess.return_value = mock_result

        with patch.object(coordinator, "_validate_fix_command", return_value=True):
            result = coordinator._run_fix_command(cmd, "test")

            assert result is True
            mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_run_fix_command_uses_repo_uv_cache(
        self, mock_subprocess, tmp_path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        cmd = ["uv", "run", "bandit", "-r", "."]
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        with patch.object(coordinator, "_validate_fix_command", return_value=True):
            result = coordinator._run_fix_command(cmd, "test")

        assert result is True
        env = mock_subprocess.call_args.kwargs["env"]
        assert env["UV_CACHE_DIR"] == str(tmp_path / ".crackerjack" / "uv" / "cache")
        assert env["RUFF_CACHE_DIR"] == str(
            tmp_path / ".crackerjack" / "uv" / "cache" / "ruff",
        )
        assert env["PIP_CACHE_DIR"] == str(
            tmp_path / ".crackerjack" / "uv" / "cache" / "pip",
        )
        assert Path(env["UV_CACHE_DIR"]).exists()

    def test_create_backup_falls_back_to_writable_backup_dir(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        source_file = tmp_path / "example.py"
        source_file.write_text("print('hello')\n", encoding="utf-8")

        def fake_copy2(src: Path, dst: Path) -> None:
            if dst.parent == source_file.parent:
                raise OSError("Operation not permitted")
            real_copy2(src, dst)

        with patch("crackerjack.core.autofix_coordinator.shutil.copy2", side_effect=fake_copy2):
            backup_path = coordinator._create_backup(str(source_file))

        backup_file = Path(backup_path)
        assert backup_file.exists()
        assert backup_file.parent != source_file.parent
        assert backup_file.with_suffix(backup_file.suffix + ".json").exists()

        source_file.write_text("print('changed')\n", encoding="utf-8")
        coordinator._restore_backup(backup_path)

        assert source_file.read_text(encoding="utf-8") == "print('hello')\n"
        assert not backup_file.exists()

    @pytest.mark.asyncio
    async def test_execute_single_plan_stops_on_non_retryable_write_failure(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        plan = Mock()
        plan.file_path = str(tmp_path / "example.py")
        plan.changes = [Mock(line_range=(1, 1))]

        plan_results = [
            Mock(
                success=False,
                remaining_issues=["Failed to write refactored file: example.py"],
            )
        ]

        with (
            patch.object(
                coordinator,
                "_execute_plan_with_validation",
                return_value=(False, plan_results, "Fix failed: failed to write"),
            ),
            patch.object(
                coordinator,
                "_regenerate_plan_with_feedback",
                side_effect=AssertionError("should not retry"),
            ) as mock_regenerate,
        ):
            result = await coordinator._execute_single_plan_with_retry(
                plan=plan,
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                analysis_coordinator=Mock(),
                plan_to_issue={},
                plan_key="example",
                bar=None,
            )

        assert result.success is False
        assert "Fix failed: failed to write" in result.remaining_issues[0]
        mock_regenerate.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_single_plan_stops_when_target_is_not_writable(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        plan = Mock()
        plan.file_path = str(tmp_path / "example.py")
        plan.changes = [Mock(line_range=(1, 1))]

        with (
            patch.object(coordinator, "_is_writable_target", return_value=False),
            patch.object(
                coordinator,
                "_execute_plan_with_validation",
                side_effect=AssertionError("should not run"),
            ),
            patch.object(
                coordinator,
                "_regenerate_plan_with_feedback",
                side_effect=AssertionError("should not retry"),
            ),
        ):
            result = await coordinator._execute_single_plan_with_retry(
                plan=plan,
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                analysis_coordinator=Mock(),
                plan_to_issue={},
                plan_key="example",
                bar=None,
            )

        assert result.success is False
        assert result.remaining_issues == [f"Workspace is not writable: {plan.file_path}"]

    @patch("subprocess.run")
    def test_run_fix_command_invalid(self, mock_subprocess, coordinator) -> None:
        cmd = ["invalid", "command"]

        with patch.object(coordinator, "_validate_fix_command", return_value=False):
            result = coordinator._run_fix_command(cmd, "test")

            assert result is False
            mock_subprocess.assert_not_called()

    @patch("subprocess.run")
    def test_run_fix_command_exception(self, mock_subprocess, coordinator) -> None:
        cmd = ["uv", "run", "ruff", "format", "."]
        mock_subprocess.side_effect = Exception("Test error")

        with patch.object(coordinator, "_validate_fix_command", return_value=True):
            result = coordinator._run_fix_command(cmd, "test")

            assert result is False

    def test_handle_command_result_success(self, coordinator) -> None:
        result = Mock(returncode=0, stdout="", stderr="")

        handled = coordinator._handle_command_result(result, "test")

        assert handled is True

    def test_handle_command_result_successful_fix(self, coordinator) -> None:
        result = Mock(returncode=1, stdout="Fixed 5 files", stderr="")

        with patch.object(coordinator, "_is_successful_fix", return_value=True):
            handled = coordinator._handle_command_result(result, "test")

            assert handled is True

    def test_handle_command_result_failure(self, coordinator) -> None:
        result = Mock(returncode=1, stdout="", stderr="")

        with patch.object(coordinator, "_is_successful_fix", return_value=False):
            handled = coordinator._handle_command_result(result, "test")

            assert handled is False

    def test_is_successful_fix(self, coordinator) -> None:
        result = Mock(stdout="Fixed 3 files")
        assert coordinator._is_successful_fix(result) is True

        result = Mock(stdout="Reformatted code")
        assert coordinator._is_successful_fix(result) is True

        result = Mock(stdout="No changes made")
        assert coordinator._is_successful_fix(result) is False

    def test_check_tool_success_patterns(self, coordinator) -> None:
        assert coordinator._check_tool_success_patterns([], None) is False
        assert coordinator._check_tool_success_patterns(["uv"], None) is False

        cmd = ["uv", "run", "ruff"]
        result = Mock(returncode=0)
        assert coordinator._check_tool_success_patterns(cmd, result) is True

        cmd = ["uv", "run", "ruff"]
        assert coordinator._check_tool_success_patterns(cmd, "Fixed 5 files") is True
        assert (
            coordinator._check_tool_success_patterns(cmd, "would reformat 3 files")
            is True
        )

        cmd = ["uv", "run", "trailing-whitespace"]
        assert (
            coordinator._check_tool_success_patterns(cmd, "Fixing whitespace") is True
        )

    def test_validate_fix_command(self, coordinator) -> None:
        # Valid commands with allowed tools
        assert (
            coordinator._validate_fix_command(["uv", "run", "bandit", "-r", "."])
            is True
        )

        # Invalid commands
        assert coordinator._validate_fix_command([]) is False
        assert coordinator._validate_fix_command(["uv"]) is False
        assert coordinator._validate_fix_command(["python", "run", "ruff"]) is False
        assert coordinator._validate_fix_command(["uv", "run", "invalid_tool"]) is False
        # ruff is not in the allowed_tools list
        assert (
            coordinator._validate_fix_command(["uv", "run", "ruff", "format"]) is False
        )

    def test_validate_hook_result(self, coordinator) -> None:
        valid_result = Mock()
        valid_result.name = "test_hook"
        valid_result.status = "failed"
        assert coordinator._validate_hook_result(valid_result) is True

        invalid_result1 = object()
        assert coordinator._validate_hook_result(invalid_result1) is False

        invalid_result2 = Mock()
        invalid_result2.name = ""
        invalid_result2.status = "failed"
        assert coordinator._validate_hook_result(invalid_result2) is False

        invalid_result3 = Mock()
        invalid_result3.name = "test"
        invalid_result3.status = "Invalid"
        assert coordinator._validate_hook_result(invalid_result3) is False

    def test_should_skip_autofix(self, coordinator) -> None:
        normal_result = Mock()
        normal_result.output = "Some normal output"
        normal_result.error = ""
        normal_result.error_message = ""
        assert coordinator._should_skip_autofix([normal_result]) is False

        import_error_result = Mock()
        import_error_result.output = "ModuleNotFoundError: No module named 'test'"
        import_error_result.error = ""
        import_error_result.error_message = ""
        assert coordinator._should_skip_autofix([import_error_result]) is True

        import_error_result2 = Mock()
        import_error_result2.output = "ImportError: cannot import name 'test'"
        import_error_result2.error = ""
        import_error_result2.error_message = ""
        assert coordinator._should_skip_autofix([import_error_result2]) is True

        no_output_result = Mock()
        no_output_result.output = None
        no_output_result.error = None
        no_output_result.error_message = None
        assert coordinator._should_skip_autofix([no_output_result]) is False


class TestAutofixCoordinatorIntegration:
    @pytest.fixture
    def coordinator(self):
        console = Mock(spec=Console)
        pkg_path = Path("/ test")
        return AutofixCoordinator(console=console, pkg_path=pkg_path)

    @pytest.mark.asyncio
    async def test_full_fast_workflow(self, coordinator) -> None:
        hook_results = []

        with (
            patch.object(
                coordinator,
                "_run_fix_command",
                return_value=True,
            ) as mock_run,
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is True

            assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_full_comprehensive_workflow(self, coordinator) -> None:
        ruff_result = Mock()
        ruff_result.name = "ruff"
        ruff_result.status = "failed"
        ruff_result.output = "Some ruff error output"
        ruff_result.error = ""
        ruff_result.error_message = ""

        bandit_result = Mock()
        bandit_result.name = "bandit"
        bandit_result.status = "failed"
        bandit_result.output = "Some bandit error output"
        bandit_result.error = ""
        bandit_result.error_message = ""

        hook_results = [ruff_result, bandit_result]

        with (
            patch.object(
                coordinator,
                "_run_fix_command",
                return_value=True,
            ) as mock_run,
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
        ):
            result = await coordinator.apply_autofix_for_hooks(
                "comprehensive", hook_results
            )

            assert result is True

            assert mock_run.call_count >= 2

    @pytest.mark.asyncio
    async def test_error_recovery(self, coordinator) -> None:
        hook_results = []

        with (
            patch.object(
                coordinator,
                "_run_fix_command",
                side_effect=Exception("Test error"),
            ),
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is False
