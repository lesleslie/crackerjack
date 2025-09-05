from pathlib import Path
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

    def test_apply_autofix_for_hooks_fast_mode(self, coordinator) -> None:
        hook_results = [Mock(name="test_hook", status="Failed")]

        with (
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
            patch.object(coordinator, "_apply_fast_stage_fixes", return_value=True),
        ):
            result = coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is True

    def test_apply_autofix_for_hooks_comprehensive_mode(self, coordinator) -> None:
        hook_results = [Mock(name="test_hook", status="Failed")]

        with (
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
            patch.object(
                coordinator,
                "_apply_comprehensive_stage_fixes",
                return_value=True,
            ),
        ):
            result = coordinator.apply_autofix_for_hooks("comprehensive", hook_results)

            assert result is True

    def test_apply_autofix_for_hooks_skip_when_should_skip(self, coordinator) -> None:
        hook_results = [Mock()]

        with patch.object(coordinator, "_should_skip_autofix", return_value=True):
            result = coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is False

    def test_apply_autofix_for_hooks_unknown_mode(self, coordinator) -> None:
        hook_results = []

        with patch.object(coordinator, "_should_skip_autofix", return_value=False):
            result = coordinator.apply_autofix_for_hooks("unknown", hook_results)

            assert result is False

    def test_apply_autofix_for_hooks_exception_handling(self, coordinator) -> None:
        hook_results = []

        with patch.object(
            coordinator,
            "_should_skip_autofix",
            side_effect=Exception("Test error"),
        ):
            result = coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is False

    def test_public_interface_methods(self, coordinator) -> None:
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
            assert coordinator.apply_fast_stage_fixes() is True
            mock_fast.assert_called_once()

            assert coordinator.apply_comprehensive_stage_fixes(hook_results) is True
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

    def test_apply_comprehensive_stage_fixes(self, coordinator) -> None:
        hook_results = [Mock(name="bandit", status="Failed")]

        with (
            patch.object(coordinator, "_apply_fast_stage_fixes", return_value=True),
            patch.object(coordinator, "_extract_failed_hooks", return_value={"bandit"}),
            patch.object(coordinator, "_get_hook_specific_fixes", return_value=[]),
            patch.object(coordinator, "_run_fix_command", return_value=True),
        ):
            result = coordinator._apply_comprehensive_stage_fixes(hook_results)

            assert result is True

    def test_extract_failed_hooks(self, coordinator) -> None:
        ruff_result = Mock()
        ruff_result.name = "ruff"
        ruff_result.status = "Failed"

        bandit_result = Mock()
        bandit_result.name = "bandit"
        bandit_result.status = "Passed"

        pyright_result = Mock()
        pyright_result.name = "pyright"
        pyright_result.status = "Failed"

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
        assert (
            coordinator._validate_fix_command(["uv", "run", "ruff", "format"]) is True
        )
        assert (
            coordinator._validate_fix_command(["uv", "run", "bandit", "- ll"]) is True
        )

        assert coordinator._validate_fix_command([]) is False
        assert coordinator._validate_fix_command(["uv"]) is False
        assert coordinator._validate_fix_command(["python", "run", "ruff"]) is False
        assert coordinator._validate_fix_command(["uv", "run", "invalid_tool"]) is False

    def test_validate_hook_result(self, coordinator) -> None:
        valid_result = Mock()
        valid_result.name = "test_hook"
        valid_result.status = "Failed"
        assert coordinator._validate_hook_result(valid_result) is True

        invalid_result1 = object()
        assert coordinator._validate_hook_result(invalid_result1) is False

        invalid_result2 = Mock()
        invalid_result2.name = ""
        invalid_result2.status = "Failed"
        assert coordinator._validate_hook_result(invalid_result2) is False

        invalid_result3 = Mock()
        invalid_result3.name = "test"
        invalid_result3.status = "Invalid"
        assert coordinator._validate_hook_result(invalid_result3) is False

    def test_should_skip_autofix(self, coordinator) -> None:
        normal_result = Mock(raw_output="Some normal output")
        assert coordinator._should_skip_autofix([normal_result]) is False

        import_error_result = Mock(
            raw_output="ModuleNotFoundError: No module named 'test'",
        )
        assert coordinator._should_skip_autofix([import_error_result]) is True

        import_error_result2 = Mock(raw_output="ImportError: cannot import name 'test'")
        assert coordinator._should_skip_autofix([import_error_result2]) is True

        no_output_result = Mock()
        if hasattr(no_output_result, "raw_output"):
            delattr(no_output_result, "raw_output")
        assert coordinator._should_skip_autofix([no_output_result]) is False


class TestAutofixCoordinatorIntegration:
    @pytest.fixture
    def coordinator(self):
        console = Mock(spec=Console)
        pkg_path = Path("/ test")
        return AutofixCoordinator(console=console, pkg_path=pkg_path)

    def test_full_fast_workflow(self, coordinator) -> None:
        hook_results = []

        with patch.object(
            coordinator,
            "_run_fix_command",
            return_value=True,
        ) as mock_run:
            result = coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is True

            assert mock_run.call_count == 2

    def test_full_comprehensive_workflow(self, coordinator) -> None:
        ruff_result = Mock()
        ruff_result.name = "ruff"
        ruff_result.status = "Failed"
        ruff_result.raw_output = "Some ruff error output"

        bandit_result = Mock()
        bandit_result.name = "bandit"
        bandit_result.status = "Failed"
        bandit_result.raw_output = "Some bandit error output"

        hook_results = [ruff_result, bandit_result]

        with patch.object(
            coordinator,
            "_run_fix_command",
            return_value=True,
        ) as mock_run:
            result = coordinator.apply_autofix_for_hooks("comprehensive", hook_results)

            assert result is True

            assert mock_run.call_count >= 2

    def test_error_recovery(self, coordinator) -> None:
        hook_results = []

        with patch.object(
            coordinator,
            "_run_fix_command",
            side_effect=Exception("Test error"),
        ):
            result = coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is False
