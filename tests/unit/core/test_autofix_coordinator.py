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

    def test_initialization_default(self) -> None:
        """Test default initialization with DI."""
        coordinator = AutofixCoordinator()

        assert coordinator.console is not None
        assert coordinator.pkg_path == Path.cwd()
        assert coordinator.logger is not None

    def test_initialization_with_console(self) -> None:
        """Test initialization with provided console."""
        mock_console = Mock()
        coordinator = AutofixCoordinator(console=mock_console)

        assert coordinator.console == mock_console

    def test_initialization_with_pkg_path(self, tmp_path) -> None:
        """Test initialization with provided pkg_path."""
        coordinator = AutofixCoordinator(pkg_path=tmp_path)

        assert coordinator.pkg_path == tmp_path

    def test_initialization_with_logger(self) -> None:
        """Test initialization with provided logger."""
        mock_logger = Mock()
        coordinator = AutofixCoordinator(logger=mock_logger)

        assert coordinator.logger == mock_logger

    def test_initialization_logger_binding(self) -> None:
        """Test logger is bound with context."""
        coordinator = AutofixCoordinator()
        assert coordinator.logger is not None

    def test_initialization_logger_without_bind(self) -> None:
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

    def test_validate_fix_command_valid_ruff(self, coordinator) -> None:
        """Test validation of valid ruff command."""
        cmd = ["uv", "run", "ruff", "check", "."]

        result = coordinator.validate_fix_command(cmd)

        assert result is True

    def test_validate_fix_command_valid_bandit(self, coordinator) -> None:
        """Test validation of valid bandit command."""
        cmd = ["uv", "run", "bandit", "-r", "."]

        result = coordinator.validate_fix_command(cmd)

        assert result is True

    def test_validate_fix_command_empty_list(self, coordinator) -> None:
        """Test validation of empty command."""
        result = coordinator.validate_fix_command([])

        assert result is False

    def test_validate_fix_command_too_short(self, coordinator) -> None:
        """Test validation of command too short."""
        result = coordinator.validate_fix_command(["uv"])

        assert result is False

    def test_validate_fix_command_not_uv(self, coordinator) -> None:
        """Test validation of command not starting with uv."""
        cmd = ["python", "run", "ruff"]

        result = coordinator.validate_fix_command(cmd)

        assert result is False

    def test_validate_fix_command_not_run(self, coordinator) -> None:
        """Test validation of command without run."""
        cmd = ["uv", "exec", "ruff"]

        result = coordinator.validate_fix_command(cmd)

        assert result is False

    def test_validate_fix_command_disallowed_tool(self, coordinator) -> None:
        """Test validation of disallowed tool."""
        cmd = ["uv", "run", "pytest", "."]

        result = coordinator.validate_fix_command(cmd)

        assert result is False

    def test_validate_hook_result_valid(self, coordinator) -> None:
        """Test validation of valid hook result."""
        result = Mock()
        result.name = "test-hook"
        result.status = "Passed"

        valid = coordinator.validate_hook_result(result)

        assert valid is True

    def test_validate_hook_result_failed_status(self, coordinator) -> None:
        """Test validation of hook result with Failed status."""
        result = Mock()
        result.name = "test-hook"
        result.status = "Failed"

        valid = coordinator.validate_hook_result(result)

        assert valid is True

    def test_validate_hook_result_missing_name(self, coordinator) -> None:
        """Test validation of hook result without name."""
        result = Mock()
        result.name = None
        result.status = "Passed"

        valid = coordinator.validate_hook_result(result)

        assert valid is False

    def test_validate_hook_result_missing_status(self, coordinator) -> None:
        """Test validation of hook result without status."""
        result = Mock()
        result.name = "test-hook"
        result.status = None

        valid = coordinator.validate_hook_result(result)

        assert valid is False

    def test_validate_hook_result_invalid_status(self, coordinator) -> None:
        """Test validation of hook result with invalid status."""
        result = Mock()
        result.name = "test-hook"
        result.status = "Unknown"

        valid = coordinator.validate_hook_result(result)

        assert valid is False

    def test_validate_hook_result_non_string_name(self, coordinator) -> None:
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

    def test_should_skip_autofix_no_errors(self, coordinator) -> None:
        """Test should not skip when no import errors."""
        result1 = Mock()
        result1.output = "Everything is fine"
        result1.error = ""
        result1.error_message = ""

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is False

    def test_should_skip_autofix_import_error(self, coordinator) -> None:
        """Test should skip when ImportError present."""
        result1 = Mock()
        result1.output = "ImportError: cannot import name 'foo'"
        result1.error = ""
        result1.error_message = ""

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is True

    def test_should_skip_autofix_module_not_found_error(self, coordinator) -> None:
        """Test should skip when ModuleNotFoundError present."""
        result1 = Mock()
        result1.output = "ModuleNotFoundError: No module named 'bar'"
        result1.error = ""
        result1.error_message = ""

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is True

    def test_should_skip_autofix_case_insensitive(self, coordinator) -> None:
        """Test skip detection is case-insensitive."""
        result1 = Mock()
        result1.output = "IMPORTERROR: Cannot import"
        result1.error = ""
        result1.error_message = ""

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is True

    def test_should_skip_autofix_no_output(self, coordinator) -> None:
        """Test should not skip when no output."""
        result1 = Mock()
        result1.output = None
        result1.error = None
        result1.error_message = None

        should_skip = coordinator.should_skip_autofix([result1])

        assert should_skip is False

    def test_should_skip_autofix_empty_list(self, coordinator) -> None:
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

    def test_check_tool_success_patterns_process_result_success(self, coordinator) -> None:
        """Test success pattern with successful process result."""
        result = Mock()
        result.returncode = 0

        success = coordinator.check_tool_success_patterns(["uv", "run", "ruff"], result)

        assert success is True

    def test_check_tool_success_patterns_process_result_with_fixed(self, coordinator) -> None:
        """Test success pattern with 'fixed' in output."""
        result = Mock()
        result.returncode = 1
        result.stdout = "2 files fixed"
        result.stderr = ""

        success = coordinator.check_tool_success_patterns(["uv", "run", "ruff"], result)

        assert success is True

    def test_check_tool_success_patterns_string_result(self, coordinator) -> None:
        """Test success pattern with string result."""
        success = coordinator.check_tool_success_patterns(
            ["uv", "run", "ruff"], "Files formatted successfully",
        )

        assert success is True

    def test_check_tool_success_patterns_empty_cmd(self, coordinator) -> None:
        """Test success pattern with empty command."""
        result = Mock()
        result.returncode = 0

        success = coordinator.check_tool_success_patterns([], result)

        assert success is False

    def test_has_success_patterns_fixed(self, coordinator) -> None:
        """Test detecting 'fixed' pattern."""
        result = coordinator._has_success_patterns("2 files fixed")

        assert result is True

    def test_has_success_patterns_formatted(self, coordinator) -> None:
        """Test detecting 'formatted' pattern."""
        result = coordinator._has_success_patterns("Files formatted")

        assert result is True

    def test_has_success_patterns_would_reformat(self, coordinator) -> None:
        """Test detecting 'would reformat' pattern."""
        result = coordinator._has_success_patterns("Would reformat 3 files")

        assert result is True

    def test_has_success_patterns_no_match(self, coordinator) -> None:
        """Test no success pattern detected."""
        result = coordinator._has_success_patterns("Error occurred")

        assert result is False

    def test_has_success_patterns_empty_output(self, coordinator) -> None:
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

    def test_extract_failed_hooks_single_failure(self, coordinator) -> None:
        """Test extracting single failed hook."""
        result1 = Mock()
        result1.name = "hook1"
        result1.status = "Failed"

        failed = coordinator._extract_failed_hooks([result1])

        assert failed == {"hook1"}

    def test_extract_failed_hooks_multiple_failures(self, coordinator) -> None:
        """Test extracting multiple failed hooks."""
        result1 = Mock()
        result1.name = "hook1"
        result1.status = "Failed"

        result2 = Mock()
        result2.name = "hook2"
        result2.status = "Failed"

        failed = coordinator._extract_failed_hooks([result1, result2])

        assert failed == {"hook1", "hook2"}

    def test_extract_failed_hooks_mixed_statuses(self, coordinator) -> None:
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

    def test_extract_failed_hooks_empty_list(self, coordinator) -> None:
        """Test extracting from empty results."""
        failed = coordinator._extract_failed_hooks([])

        assert failed == set()

    def test_extract_failed_hooks_invalid_results(self, coordinator) -> None:
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

    def test_get_hook_specific_fixes_bandit(self, coordinator) -> None:
        """Test getting bandit-specific fixes."""
        fixes = coordinator._get_hook_specific_fixes({"bandit"})

        assert len(fixes) == 1
        assert fixes[0][0] == ["uv", "run", "bandit", "-r", "."]
        assert fixes[0][1] == "bandit analysis"

    def test_get_hook_specific_fixes_no_matches(self, coordinator) -> None:
        """Test getting fixes for hooks without specific fixes."""
        fixes = coordinator._get_hook_specific_fixes({"ruff", "trailing-whitespace"})

        assert len(fixes) == 0

    def test_get_hook_specific_fixes_empty_set(self, coordinator) -> None:
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
            console=mock_console, logger=mock_logger, pkg_path=tmp_path,
        )

    def test_run_fix_command_success(self, coordinator) -> None:
        """Test running successful fix command."""
        cmd = ["uv", "run", "ruff", "check", "."]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = coordinator.run_fix_command(cmd, "test fix")

            assert result is True
            mock_run.assert_called_once()

    def test_run_fix_command_invalid_command(self, coordinator) -> None:
        """Test running invalid command."""
        cmd = ["python", "run", "ruff"]

        result = coordinator.run_fix_command(cmd, "invalid fix")

        assert result is False

    def test_run_fix_command_timeout(self, coordinator) -> None:
        """Test command execution with subprocess parameters."""
        cmd = ["uv", "run", "ruff", "check", "."]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            coordinator.run_fix_command(cmd, "test fix")

            # Verify timeout is set
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 300

    def test_run_fix_command_exception(self, coordinator) -> None:
        """Test command execution with exception."""
        cmd = ["uv", "run", "ruff", "check", "."]

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd, 300)

            result = coordinator.run_fix_command(cmd, "test fix")

            assert result is False

    def test_run_fix_command_cwd_set(self, coordinator, tmp_path) -> None:
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

    def test_handle_command_result_success(self, coordinator) -> None:
        """Test handling successful command result."""
        result = Mock(returncode=0, stdout="", stderr="")

        success = coordinator._handle_command_result(result, "test fix")

        assert success is True

    def test_handle_command_result_failure_with_fix_indicator(self, coordinator) -> None:
        """Test handling failed command with fix indicator."""
        result = Mock(returncode=1, stdout="2 files fixed", stderr="")

        success = coordinator._handle_command_result(result, "test fix")

        assert success is True

    def test_handle_command_result_failure(self, coordinator) -> None:
        """Test handling failed command."""
        result = Mock(returncode=1, stdout="", stderr="Error occurred")

        success = coordinator._handle_command_result(result, "test fix")

        assert success is False

    def test_is_successful_fix_with_fixed(self, coordinator) -> None:
        """Test detecting successful fix with 'fixed'."""
        result = Mock(returncode=1, stdout="2 files fixed", stderr="")

        is_success = coordinator._is_successful_fix(result)

        assert is_success is True

    def test_is_successful_fix_with_formatted(self, coordinator) -> None:
        """Test detecting successful fix with 'formatted'."""
        result = Mock(returncode=1, stdout="Files formatted", stderr="")

        is_success = coordinator._is_successful_fix(result)

        assert is_success is True

    def test_is_successful_fix_no_indicators(self, coordinator) -> None:
        """Test no success indicators found."""
        result = Mock(returncode=1, stdout="No changes", stderr="")

        is_success = coordinator._is_successful_fix(result)

        assert is_success is False

    def test_is_successful_fix_non_string_output(self, coordinator) -> None:
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

    def test_apply_autofix_for_hooks_fast_mode(self, coordinator) -> None:
        """Test applying autofix in fast mode."""
        with patch.object(coordinator, "_apply_fast_stage_fixes") as mock_fast:
            mock_fast.return_value = True

            result = coordinator.apply_autofix_for_hooks("fast", [])

            assert result is True
            mock_fast.assert_called_once()

    def test_apply_autofix_for_hooks_comprehensive_mode(self, coordinator) -> None:
        """Test applying autofix in comprehensive mode."""
        # Create hook result without import errors to avoid triggering skip logic
        hook_result = Mock()
        hook_result.name = "hook1"
        hook_result.status = "Failed"
        hook_result.output = "Some error"
        hook_result.error = ""
        hook_result.error_message = ""

        hook_results = [hook_result]

        with patch.object(coordinator, "_apply_comprehensive_stage_fixes") as mock_comp:
            mock_comp.return_value = True

            result = coordinator.apply_autofix_for_hooks("comprehensive", hook_results)

            assert result is True
            mock_comp.assert_called_once_with(hook_results)

    def test_apply_autofix_for_hooks_unknown_mode(self, coordinator) -> None:
        """Test applying autofix with unknown mode."""
        result = coordinator.apply_autofix_for_hooks("unknown", [])

        assert result is False

    def test_apply_autofix_for_hooks_should_skip(self, coordinator) -> None:
        """Test autofix skipped when should_skip is True."""
        result1 = Mock()
        result1.output = "ImportError: cannot import"
        result1.error = ""
        result1.error_message = ""

        result = coordinator.apply_autofix_for_hooks("fast", [result1])

        assert result is False

    def test_apply_autofix_for_hooks_exception(self, coordinator) -> None:
        """Test autofix handles exceptions."""
        with patch.object(coordinator, "_should_skip_autofix") as mock_skip:
            mock_skip.side_effect = Exception("Test error")

            result = coordinator.apply_autofix_for_hooks("fast", [])

            assert result is False

    def test_execute_fast_fixes_all_successful(self, coordinator) -> None:
        """Test executing fast fixes successfully."""
        with patch.object(coordinator, "_run_fix_command") as mock_run:
            mock_run.return_value = True

            result = coordinator._execute_fast_fixes()

            assert result is True
            assert mock_run.call_count == 2  # ruff format + ruff check

    def test_execute_fast_fixes_one_failure(self, coordinator) -> None:
        """Test executing fast fixes with one failure."""
        with patch.object(coordinator, "_run_fix_command") as mock_run:
            mock_run.side_effect = [True, False]

            result = coordinator._execute_fast_fixes()

            assert result is False

    def test_apply_comprehensive_stage_fixes_no_failures(self, coordinator) -> None:
        """Test comprehensive fixes with no failures."""
        result1 = Mock(name="hook1", status="Passed")

        result = coordinator._apply_comprehensive_stage_fixes([result1])

        assert result is True

    def test_apply_comprehensive_stage_fixes_with_failures(self, coordinator) -> None:
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

    def test_apply_comprehensive_stage_fixes_fast_fails(self, coordinator) -> None:
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

    def test_apply_fast_stage_fixes_facade(self, coordinator) -> None:
        """Test apply_fast_stage_fixes public method."""
        with patch.object(coordinator, "_apply_fast_stage_fixes") as mock_private:
            mock_private.return_value = True

            result = coordinator.apply_fast_stage_fixes()

            assert result is True
            mock_private.assert_called_once()

    def test_apply_comprehensive_stage_fixes_facade(self, coordinator) -> None:
        """Test apply_comprehensive_stage_fixes public method."""
        hook_results = [Mock()]

        with patch.object(
            coordinator, "_apply_comprehensive_stage_fixes",
        ) as mock_private:
            mock_private.return_value = True

            result = coordinator.apply_comprehensive_stage_fixes(hook_results)

            assert result is True
            mock_private.assert_called_once_with(hook_results)


@pytest.mark.unit
class TestAutofixCoordinatorRuffParsing:
    """Test ruff output parsing with intelligent issue type detection."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        mock_logger = Mock()
        mock_logger.bind.return_value = mock_logger
        return AutofixCoordinator(console=mock_console, logger=mock_logger)

    def test_parse_ruff_output_c901_complexity(self, coordinator) -> None:
        """Test parsing C901 complexity errors."""
        from crackerjack.agents.base import IssueType, Priority

        raw_output = (
            "session_buddy/tools/search_tools.py:756:5: "
            "C901 `register_search_tools` is too complex (16 > 15)"
        )

        issues = coordinator._parse_ruff_output(raw_output)

        assert len(issues) == 1
        issue = issues[0]
        assert issue.type == IssueType.COMPLEXITY
        assert issue.severity == Priority.HIGH
        assert issue.file_path == "session_buddy/tools/search_tools.py"
        assert issue.line_number == 756
        assert "C901" in issue.message
        assert "too complex" in issue.message

    def test_parse_ruff_output_e501_line_too_long(self, coordinator) -> None:
        """Test parsing E501 line too long errors."""
        from crackerjack.agents.base import IssueType, Priority

        raw_output = "src/main.py:42:10: E501 Line too long (88 > 79 characters)"

        issues = coordinator._parse_ruff_output(raw_output)

        assert len(issues) == 1
        issue = issues[0]
        assert issue.type == IssueType.FORMATTING
        assert issue.severity == Priority.LOW
        assert issue.file_path == "src/main.py"
        assert issue.line_number == 42

    def test_parse_ruff_output_f401_unused_import(self, coordinator) -> None:
        """Test parsing F401 unused import errors."""
        from crackerjack.agents.base import IssueType, Priority

        raw_output = "crackerjack/core.py:123:5: F401 'os' imported but unused"

        issues = coordinator._parse_ruff_output(raw_output)

        assert len(issues) == 1
        issue = issues[0]
        assert issue.type == IssueType.IMPORT_ERROR
        assert issue.severity == Priority.MEDIUM
        assert issue.file_path == "crackerjack/core.py"
        assert issue.line_number == 123

    def test_parse_ruff_output_security_code(self, coordinator) -> None:
        """Test parsing S101 security errors (bandit)."""
        from crackerjack.agents.base import IssueType, Priority

        raw_output = "tests/test_main.py:10:5: S101 Use of assert detected"

        issues = coordinator._parse_ruff_output(raw_output)

        assert len(issues) == 1
        issue = issues[0]
        assert issue.type == IssueType.SECURITY
        assert issue.severity == Priority.HIGH
        assert issue.file_path == "tests/test_main.py"

    def test_parse_ruff_output_multiple_errors(self, coordinator) -> None:
        """Test parsing multiple errors in one output."""
        raw_output = """session_buddy/tools/search_tools.py:756:5: C901 `func` is too complex (16 > 15)
src/main.py:42:10: E501 Line too long (88 > 79 characters)
Found 2 errors."""

        issues = coordinator._parse_ruff_output(raw_output)

        assert len(issues) == 2  # Summary line should be skipped

    def test_parse_ruff_output_skips_summary_lines(self, coordinator) -> None:
        """Test that summary lines are skipped."""
        raw_output = """src/main.py:42:10: E501 Line too long
Found 8 errors (7 fixed, 1 remaining).
Checked 100 files."""

        issues = coordinator._parse_ruff_output(raw_output)

        assert len(issues) == 1  # Only the actual error

    def test_parse_ruff_output_empty_string(self, coordinator) -> None:
        """Test parsing empty output."""
        issues = coordinator._parse_ruff_output("")

        assert issues == []

    def test_parse_ruff_output_no_errors(self, coordinator) -> None:
        """Test parsing output with no errors."""
        raw_output = "All checks passed!"

        issues = coordinator._parse_ruff_output(raw_output)

        assert issues == []

    def test_get_ruff_issue_type_complexity(self, coordinator) -> None:
        """Test issue type detection for complexity codes."""
        from crackerjack.agents.base import IssueType

        assert coordinator._get_ruff_issue_type("C901") == IssueType.COMPLEXITY

    def test_get_ruff_issue_type_security(self, coordinator) -> None:
        """Test issue type detection for security codes."""
        from crackerjack.agents.base import IssueType

        assert coordinator._get_ruff_issue_type("S101") == IssueType.SECURITY
        assert coordinator._get_ruff_issue_type("S501") == IssueType.SECURITY

    def test_get_ruff_issue_type_import_error(self, coordinator) -> None:
        """Test issue type detection for import codes."""
        from crackerjack.agents.base import IssueType

        assert coordinator._get_ruff_issue_type("F401") == IssueType.IMPORT_ERROR
        assert coordinator._get_ruff_issue_type("F403") == IssueType.IMPORT_ERROR

    def test_get_ruff_issue_type_formatting(self, coordinator) -> None:
        """Test issue type detection for formatting codes."""
        from crackerjack.agents.base import IssueType

        assert coordinator._get_ruff_issue_type("E501") == IssueType.FORMATTING
        assert coordinator._get_ruff_issue_type("W291") == IssueType.FORMATTING
        assert coordinator._get_ruff_issue_type("F841") == IssueType.FORMATTING

    def test_get_ruff_severity_high_priority(self, coordinator) -> None:
        """Test severity detection for high priority codes."""
        from crackerjack.agents.base import Priority

        assert coordinator._get_ruff_severity("C901") == Priority.HIGH
        assert coordinator._get_ruff_severity("S101") == Priority.HIGH

    def test_get_ruff_severity_medium_priority(self, coordinator) -> None:
        """Test severity detection for medium priority codes."""
        from crackerjack.agents.base import Priority

        assert coordinator._get_ruff_severity("F401") == Priority.MEDIUM

    def test_get_ruff_severity_low_priority(self, coordinator) -> None:
        """Test severity detection for low priority codes."""
        from crackerjack.agents.base import Priority

        assert coordinator._get_ruff_severity("E501") == Priority.LOW
        assert coordinator._get_ruff_severity("W291") == Priority.LOW

    def test_parse_hook_to_issues_routes_ruff_check(self, coordinator) -> None:
        """Test that ruff-check is properly routed to _parse_ruff_output."""
        from crackerjack.agents.base import IssueType

        raw_output = "src/main.py:10:5: C901 `func` is too complex (16 > 15)"

        issues = coordinator._parse_hook_to_issues("ruff-check", raw_output)

        assert len(issues) == 1
        assert issues[0].type == IssueType.COMPLEXITY

    def test_parse_hook_to_issues_routes_ruff(self, coordinator) -> None:
        """Test that plain ruff is also properly routed."""
        from crackerjack.agents.base import IssueType

        raw_output = "src/main.py:10:5: E501 Line too long"

        issues = coordinator._parse_hook_to_issues("ruff", raw_output)

        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING
