"""Unit tests for AutofixCoordinator.

Tests autofix coordination, command execution, validation,
and success pattern detection.
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.core.autofix_coordinator import AutofixCoordinator


@pytest.mark.unit
class TestAutofixCoordinatorInitialization:
    """Test AutofixCoordinator initialization."""

    def test_initialization_default(self):
        """Test default initialization with DI."""
        coordinator = AutofixCoordinator()

        assert coordinator.console is not None
        assert coordinator.pkg_path == Path.cwd()
        assert coordinator.logger is not None

    def test_initialization_with_console(self):
        """Test initialization with provided console."""
        mock_console = Mock()
        coordinator = AutofixCoordinator(console=mock_console)

        assert coordinator.console == mock_console

    def test_initialization_with_pkg_path(self, tmp_path):
        """Test initialization with provided pkg_path."""
        coordinator = AutofixCoordinator(pkg_path=tmp_path)

        assert coordinator.pkg_path == tmp_path

    def test_initialization_with_logger(self):
        """Test initialization with provided logger."""
        mock_logger = Mock()
        coordinator = AutofixCoordinator(logger=mock_logger)

        assert coordinator.logger == mock_logger

    def test_initialization_logger_binding(self):
        """Test logger is bound with context."""
        coordinator = AutofixCoordinator()
        assert coordinator.logger is not None

    def test_initialization_logger_without_bind(self):
        """Test logger initialization when bind method not available."""
        mock_logger = Mock(spec=[])
        coordinator = AutofixCoordinator(logger=mock_logger)

        assert coordinator.logger == mock_logger


@pytest.mark.unit
class TestAutofixCoordinatorValidation:
    """Test validation methods."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(console=mock_console, logger=mock_logger)

    def test_validate_fix_command_valid_ruff(self, coordinator):
        """Test validation of valid ruff command."""
        cmd = ["uv", "run", "ruff", "check", "."]

        result = coordinator.validate_fix_command(cmd)

        assert result is True

    def test_validate_fix_command_valid_bandit(self, coordinator):
        """Test validation of valid bandit command."""
        cmd = ["uv", "run", "bandit", "-r", "."]

        result = coordinator.validate_fix_command(cmd)

        assert result is True

    def test_validate_fix_command_empty_list(self, coordinator):
        """Test validation of empty command."""
        result = coordinator.validate_fix_command([])

        assert result is False

    def test_validate_fix_command_too_short(self, coordinator):
        """Test validation of command too short."""
        result = coordinator.validate_fix_command(["uv"])

        assert result is False

    def test_validate_fix_command_not_uv(self, coordinator):
        """Test validation of command not starting with uv."""
        cmd = ["python", "run", "ruff"]

        result = coordinator.validate_fix_command(cmd)

        assert result is False

    def test_validate_fix_command_not_run(self, coordinator):
        """Test validation of command without run."""
        cmd = ["uv", "exec", "ruff"]

        result = coordinator.validate_fix_command(cmd)

        assert result is False

    def test_validate_fix_command_disallowed_tool(self, coordinator):
        """Test validation of disallowed tool."""
        cmd = ["uv", "run", "pytest", "."]

        result = coordinator.validate_fix_command(cmd)

        assert result is False

    def test_validate_hook_result_valid(self, coordinator):
        """Test validation of valid hook result."""
        result = Mock()
        result.name = "test-hook"
        result.status = "Passed"

        valid = coordinator.validate_hook_result(result)

        assert valid is True

    def test_validate_hook_result_failed_status(self, coordinator):
        """Test validation of hook result with Failed status."""
        result = Mock()
        result.name = "test-hook"
        result.status = "Failed"

        valid = coordinator.validate_hook_result(result)

        assert valid is True

    def test_validate_hook_result_missing_name(self, coordinator):
        """Test validation of hook result without name."""
        result = Mock()
        result.name = None
        result.status = "Passed"

        valid = coordinator.validate_hook_result(result)

        assert valid is False

    def test_validate_hook_result_missing_status(self, coordinator):
        """Test validation of hook result without status."""
        result = Mock()
        result.name = "test-hook"
        result.status = None

        valid = coordinator.validate_hook_result(result)

        assert valid is False

    def test_validate_hook_result_invalid_status(self, coordinator):
        """Test validation of hook result with invalid status."""
        result = Mock()
        result.name = "test-hook"
        result.status = "Unknown"

        valid = coordinator.validate_hook_result(result)

        assert valid is False

    def test_validate_hook_result_non_string_name(self, coordinator):
        """Test validation of hook result with non-string name."""
        result = Mock()
        result.name = 123
        result.status = "Passed"

        valid = coordinator.validate_hook_result(result)

        assert valid is False


@pytest.mark.unit
class TestAutofixCoordinatorSkipLogic:
    """Test skip autofix logic."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(console=mock_console, logger=mock_logger)

    def test_should_skip_autofix_no_errors(self, coordinator):
        """Test should not skip when no import errors."""
        result1 = Mock()
        result1.raw_output = "Everything is fine"

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is False

    def test_should_skip_autofix_import_error(self, coordinator):
        """Test should skip when ImportError present."""
        result1 = Mock()
        result1.raw_output = "ImportError: cannot import name 'foo'"

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is True

    def test_should_skip_autofix_module_not_found_error(self, coordinator):
        """Test should skip when ModuleNotFoundError present."""
        result1 = Mock()
        result1.raw_output = "ModuleNotFoundError: No module named 'bar'"

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is True

    def test_should_skip_autofix_case_insensitive(self, coordinator):
        """Test skip detection is case-insensitive."""
        result1 = Mock()
        result1.raw_output = "IMPORTERROR: Cannot import"

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is True

    def test_should_skip_autofix_no_raw_output(self, coordinator):
        """Test should not skip when no raw_output."""
        result1 = Mock()
        result1.raw_output = None

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is False

    def test_should_skip_autofix_empty_list(self, coordinator):
        """Test should not skip with empty results."""
        should_skip = coordinator.should_skip_autofix([])

        assert should_skip is False


@pytest.mark.unit
class TestAutofixCoordinatorSuccessPatterns:
    """Test success pattern detection."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(console=mock_console, logger=mock_logger)

    def test_check_tool_success_patterns_process_result_success(self, coordinator):
        """Test success pattern with successful process result."""
        result = Mock()
        result.returncode = 0

        success = coordinator.check_tool_success_patterns(["uv", "run", "ruff"], result)

        assert success is True

    def test_check_tool_success_patterns_process_result_with_fixed(self, coordinator):
        """Test success pattern with 'fixed' in output."""
        result = Mock()
        result.returncode = 1
        result.stdout = "2 files fixed"
        result.stderr = ""

        success = coordinator.check_tool_success_patterns(["uv", "run", "ruff"], result)

        assert success is True

    def test_check_tool_success_patterns_string_result(self, coordinator):
        """Test success pattern with string result."""
        success = coordinator.check_tool_success_patterns(
            ["uv", "run", "ruff"], "Files formatted successfully"
        )

        assert success is True

    def test_check_tool_success_patterns_empty_cmd(self, coordinator):
        """Test success pattern with empty command."""
        result = Mock()
        result.returncode = 0

        success = coordinator.check_tool_success_patterns([], result)

        assert success is False

    def test_has_success_patterns_fixed(self, coordinator):
        """Test detecting 'fixed' pattern."""
        result = coordinator._has_success_patterns("2 files fixed")

        assert result is True

    def test_has_success_patterns_formatted(self, coordinator):
        """Test detecting 'formatted' pattern."""
        result = coordinator._has_success_patterns("Files formatted")

        assert result is True

    def test_has_success_patterns_would_reformat(self, coordinator):
        """Test detecting 'would reformat' pattern."""
        result = coordinator._has_success_patterns("Would reformat 3 files")

        assert result is True

    def test_has_success_patterns_no_match(self, coordinator):
        """Test no success pattern detected."""
        result = coordinator._has_success_patterns("Error occurred")

        assert result is False

    def test_has_success_patterns_empty_output(self, coordinator):
        """Test empty output has no patterns."""
        result = coordinator._has_success_patterns("")

        assert result is False


@pytest.mark.unit
class TestAutofixCoordinatorExtractFailedHooks:
    """Test extracting failed hooks."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(console=mock_console, logger=mock_logger)

    def test_extract_failed_hooks_single_failure(self, coordinator):
        """Test extracting single failed hook."""
        result1 = Mock()
        result1.name = "hook1"
        result1.status = "Failed"

        failed = coordinator._extract_failed_hooks([result1])

        assert failed == {"hook1"}

    def test_extract_failed_hooks_multiple_failures(self, coordinator):
        """Test extracting multiple failed hooks."""
        result1 = Mock()
        result1.name = "hook1"
        result1.status = "Failed"

        result2 = Mock()
        result2.name = "hook2"
        result2.status = "Failed"

        failed = coordinator._extract_failed_hooks([result1, result2])

        assert failed == {"hook1", "hook2"}

    def test_extract_failed_hooks_mixed_statuses(self, coordinator):
        """Test extracting only failed hooks from mixed results."""
        result1 = Mock()
        result1.name = "hook1"
        result1.status = "Passed"

        result2 = Mock()
        result2.name = "hook2"
        result2.status = "Failed"

        result3 = Mock()
        result3.name = "hook3"
        result3.status = "Skipped"

        failed = coordinator._extract_failed_hooks([result1, result2, result3])

        assert failed == {"hook2"}

    def test_extract_failed_hooks_empty_list(self, coordinator):
        """Test extracting from empty results."""
        failed = coordinator._extract_failed_hooks([])

        assert failed == set()

    def test_extract_failed_hooks_invalid_results(self, coordinator):
        """Test extracting with invalid hook results."""
        result1 = Mock()
        result1.name = None
        result1.status = "Failed"

        failed = coordinator._extract_failed_hooks([result1])

        assert failed == set()


@pytest.mark.unit
class TestAutofixCoordinatorHookSpecificFixes:
    """Test hook-specific fix generation."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(console=mock_console, logger=mock_logger)

    def test_get_hook_specific_fixes_bandit(self, coordinator):
        """Test getting bandit-specific fixes."""
        fixes = coordinator._get_hook_specific_fixes({"bandit"})

        assert len(fixes) == 1
        assert fixes[0][0] == ["uv", "run", "bandit", "-r", "."]
        assert fixes[0][1] == "bandit analysis"

    def test_get_hook_specific_fixes_no_matches(self, coordinator):
        """Test getting fixes for hooks without specific fixes."""
        fixes = coordinator._get_hook_specific_fixes({"ruff", "trailing-whitespace"})

        assert len(fixes) == 0

    def test_get_hook_specific_fixes_empty_set(self, coordinator):
        """Test getting fixes for empty hook set."""
        fixes = coordinator._get_hook_specific_fixes(set())

        assert len(fixes) == 0


@pytest.mark.unit
class TestAutofixCoordinatorCommandExecution:
    """Test command execution."""

    @pytest.fixture
    def coordinator(self, tmp_path):
        """Create coordinator instance with temp path."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(
            console=mock_console, logger=mock_logger, pkg_path=tmp_path
        )

    def test_run_fix_command_success(self, coordinator):
        """Test running successful fix command."""
        cmd = ["uv", "run", "ruff", "check", "."]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = coordinator.run_fix_command(cmd, "test fix")

            assert result is True
            mock_run.assert_called_once()

    def test_run_fix_command_invalid_command(self, coordinator):
        """Test running invalid command."""
        cmd = ["python", "run", "ruff"]

        result = coordinator.run_fix_command(cmd, "invalid fix")

        assert result is False

    def test_run_fix_command_timeout(self, coordinator):
        """Test command execution with subprocess parameters."""
        cmd = ["uv", "run", "ruff", "check", "."]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            coordinator.run_fix_command(cmd, "test fix")

            # Verify timeout is set
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 300

    def test_run_fix_command_exception(self, coordinator):
        """Test command execution with exception."""
        cmd = ["uv", "run", "ruff", "check", "."]

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd, 300)

            result = coordinator.run_fix_command(cmd, "test fix")

            assert result is False

    def test_run_fix_command_cwd_set(self, coordinator, tmp_path):
        """Test command runs in correct working directory."""
        cmd = ["uv", "run", "ruff", "check", "."]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            coordinator.run_fix_command(cmd, "test fix")

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["cwd"] == tmp_path


@pytest.mark.unit
class TestAutofixCoordinatorCommandResult:
    """Test command result handling."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(console=mock_console, logger=mock_logger)

    def test_handle_command_result_success(self, coordinator):
        """Test handling successful command result."""
        result = Mock(returncode=0, stdout="", stderr="")

        success = coordinator._handle_command_result(result, "test fix")

        assert success is True

    def test_handle_command_result_failure_with_fix_indicator(self, coordinator):
        """Test handling failed command with fix indicator."""
        result = Mock(returncode=1, stdout="2 files fixed", stderr="")

        success = coordinator._handle_command_result(result, "test fix")

        assert success is True

    def test_handle_command_result_failure(self, coordinator):
        """Test handling failed command."""
        result = Mock(returncode=1, stdout="", stderr="Error occurred")

        success = coordinator._handle_command_result(result, "test fix")

        assert success is False

    def test_is_successful_fix_with_fixed(self, coordinator):
        """Test detecting successful fix with 'fixed'."""
        result = Mock(returncode=1, stdout="2 files fixed", stderr="")

        is_success = coordinator._is_successful_fix(result)

        assert is_success is True

    def test_is_successful_fix_with_formatted(self, coordinator):
        """Test detecting successful fix with 'formatted'."""
        result = Mock(returncode=1, stdout="Files formatted", stderr="")

        is_success = coordinator._is_successful_fix(result)

        assert is_success is True

    def test_is_successful_fix_no_indicators(self, coordinator):
        """Test no success indicators found."""
        result = Mock(returncode=1, stdout="No changes", stderr="")

        is_success = coordinator._is_successful_fix(result)

        assert is_success is False

    def test_is_successful_fix_non_string_output(self, coordinator):
        """Test handling non-string stdout/stderr."""
        result = Mock(returncode=1, stdout=123, stderr=456)

        # Should convert to string and check
        is_success = coordinator._is_successful_fix(result)

        assert isinstance(is_success, bool)


@pytest.mark.unit
class TestAutofixCoordinatorApplyFixes:
    """Test applying fixes."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(console=mock_console, logger=mock_logger)

    def test_apply_autofix_for_hooks_fast_mode(self, coordinator):
        """Test applying autofix in fast mode."""
        with patch.object(coordinator, "_apply_fast_stage_fixes") as mock_fast:
            mock_fast.return_value = True

            result = coordinator.apply_autofix_for_hooks("fast", [])

            assert result is True
            mock_fast.assert_called_once()

    def test_apply_autofix_for_hooks_comprehensive_mode(self, coordinator):
        """Test applying autofix in comprehensive mode."""
        # Create hook result without raw_output to avoid triggering skip logic
        hook_results = [Mock(name="hook1", status="Failed", raw_output=None)]

        with patch.object(coordinator, "_apply_comprehensive_stage_fixes") as mock_comp:
            mock_comp.return_value = True

            result = coordinator.apply_autofix_for_hooks("comprehensive", hook_results)

            assert result is True
            mock_comp.assert_called_once_with(hook_results)

    def test_apply_autofix_for_hooks_unknown_mode(self, coordinator):
        """Test applying autofix with unknown mode."""
        result = coordinator.apply_autofix_for_hooks("unknown", [])

        assert result is False

    def test_apply_autofix_for_hooks_should_skip(self, coordinator):
        """Test autofix skipped when should_skip is True."""
        result1 = Mock()
        result1.raw_output = "ImportError: cannot import"

        result = coordinator.apply_autofix_for_hooks("fast", [result1])

        assert result is False

    def test_apply_autofix_for_hooks_exception(self, coordinator):
        """Test autofix handles exceptions."""
        with patch.object(coordinator, "_should_skip_autofix") as mock_skip:
            mock_skip.side_effect = Exception("Test error")

            result = coordinator.apply_autofix_for_hooks("fast", [])

            assert result is False

    def test_execute_fast_fixes_all_successful(self, coordinator):
        """Test executing fast fixes successfully."""
        with patch.object(coordinator, "_run_fix_command") as mock_run:
            mock_run.return_value = True

            result = coordinator._execute_fast_fixes()

            assert result is True
            assert mock_run.call_count == 2  # ruff format + ruff check

    def test_execute_fast_fixes_one_failure(self, coordinator):
        """Test executing fast fixes with one failure."""
        with patch.object(coordinator, "_run_fix_command") as mock_run:
            mock_run.side_effect = [True, False]

            result = coordinator._execute_fast_fixes()

            assert result is False

    def test_apply_comprehensive_stage_fixes_no_failures(self, coordinator):
        """Test comprehensive fixes with no failures."""
        result1 = Mock(name="hook1", status="Passed")

        result = coordinator._apply_comprehensive_stage_fixes([result1])

        assert result is True

    def test_apply_comprehensive_stage_fixes_with_failures(self, coordinator):
        """Test comprehensive fixes with failures."""
        # Create a proper hook result with string attributes
        result1 = Mock()
        result1.name = "bandit"
        result1.status = "Failed"

        with patch.object(coordinator, "_execute_fast_fixes") as mock_fast:
            with patch.object(coordinator, "_run_fix_command") as mock_run:
                mock_fast.return_value = True
                mock_run.return_value = True

                result = coordinator._apply_comprehensive_stage_fixes([result1])

                assert result is True
                mock_run.assert_called_once()

    def test_apply_comprehensive_stage_fixes_fast_fails(self, coordinator):
        """Test comprehensive fixes when fast fixes fail."""
        # Create a proper hook result with string attributes
        result1 = Mock()
        result1.name = "bandit"
        result1.status = "Failed"

        with patch.object(coordinator, "_execute_fast_fixes") as mock_fast:
            mock_fast.return_value = False

            result = coordinator._apply_comprehensive_stage_fixes([result1])

            assert result is False


@pytest.mark.unit
class TestAutofixCoordinatorPublicAPI:
    """Test public API methods."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(console=mock_console, logger=mock_logger)

    def test_apply_fast_stage_fixes_facade(self, coordinator):
        """Test apply_fast_stage_fixes public method."""
        with patch.object(coordinator, "_apply_fast_stage_fixes") as mock_private:
            mock_private.return_value = True

            result = coordinator.apply_fast_stage_fixes()

            assert result is True
            mock_private.assert_called_once()

    def test_apply_comprehensive_stage_fixes_facade(self, coordinator):
        """Test apply_comprehensive_stage_fixes public method."""
        hook_results = [Mock()]

        with patch.object(
            coordinator, "_apply_comprehensive_stage_fixes"
        ) as mock_private:
            mock_private.return_value = True

            result = coordinator.apply_comprehensive_stage_fixes(hook_results)

            assert result is True
            mock_private.assert_called_once_with(hook_results)
