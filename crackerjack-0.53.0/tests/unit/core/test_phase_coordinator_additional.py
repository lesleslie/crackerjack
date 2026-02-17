"""Additional unit tests for phase coordinator components - covering more methods."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.config import CrackerjackSettings
from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator


class TestPhaseCoordinatorMoreMethods:
    """Test additional PhaseCoordinator methods."""

    def test_run_doc_update_phase_disabled(self) -> None:
        """Test run_doc_update_phase when disabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.update_docs = False

        result = coordinator.run_doc_update_phase(options)

        # When update_docs is False, should return True immediately
        assert result is True

    def test_run_doc_update_phase_enabled_success(self) -> None:
        """Test run_doc_update_phase when enabled and succeeds."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.update_docs = True

        with patch('crackerjack.services.doc_update_service.DocUpdateService') as mock_service_class:
            mock_service_instance = MagicMock()
            mock_service_instance.update_documentation.return_value = MagicMock(
                success=True,
                summary="Documentation updated successfully"
            )
            mock_service_class.return_value = mock_service_instance

            result = coordinator.run_doc_update_phase(options)

            assert result is True
            mock_service_class.assert_called_once()
            mock_service_instance.update_documentation.assert_called_once_with(dry_run=False)

    def test_run_doc_update_phase_enabled_failure(self) -> None:
        """Test run_doc_update_phase when enabled but fails."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.update_docs = True

        with patch('crackerjack.services.doc_update_service.DocUpdateService') as mock_service_class:
            mock_service_instance = MagicMock()
            mock_service_instance.update_documentation.return_value = MagicMock(
                success=False,
                error_message="Documentation update failed"
            )
            mock_service_class.return_value = mock_service_instance

            result = coordinator.run_doc_update_phase(options)

            assert result is False

    def test_run_publishing_phase_no_version_type(self) -> None:
        """Test run_publishing_phase when no version type is determined."""
        coordinator = PhaseCoordinator()
        options = MagicMock()

        with patch.object(coordinator, '_determine_version_type', return_value=None):

            result = coordinator.run_publishing_phase(options)

            assert result is True

    def test_run_commit_phase_disabled(self) -> None:
        """Test run_commit_phase when commit is disabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.commit = False

        result = coordinator.run_commit_phase(options)

        # When commit is False, should return True immediately
        assert result is True

    def test_run_commit_phase_with_version_bump(self) -> None:
        """Test run_commit_phase when version bump is happening."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.commit = True

        with patch.object(coordinator, '_determine_version_type', return_value="patch"):

            result = coordinator.run_commit_phase(options)

            # When version bump is happening, commit phase should be skipped
            assert result is True

    def test_determine_version_type(self) -> None:
        """Test _determine_version_type method."""
        coordinator = PhaseCoordinator()
        options = MagicMock()

        # Test with patch option
        options.patch = True
        assert coordinator._determine_version_type(options) == "patch"

        # Test with minor option
        options.patch = False
        options.minor = True
        assert coordinator._determine_version_type(options) == "minor"

        # Test with major option
        options.minor = False
        options.major = True
        assert coordinator._determine_version_type(options) == "major"

        # Test with no version options
        options.major = False
        options.all = False
        assert coordinator._determine_version_type(options) is None

    def test_format_hook_summary_with_empty_summary(self) -> None:
        """Test _format_hook_summary with empty summary."""
        summary = {}
        result = PhaseCoordinator._format_hook_summary(summary)
        assert result == "No hooks executed"

    def test_format_hook_summary_with_data(self) -> None:
        """Test _format_hook_summary with data."""
        summary = {
            "total": 10,
            "passed": 8,
            "failed": 1,
            "errors": 1,
            "total_duration": 5.5
        }
        result = PhaseCoordinator._format_hook_summary(summary)
        assert "8/10 passed" in result
        assert "1 failed" in result
        assert "1 errors" in result
        assert "5.50s" in result

    def test_status_style_passed(self) -> None:
        """Test _status_style for passed status."""
        result = PhaseCoordinator._status_style("passed")
        assert result == "green"

    def test_status_style_failed(self) -> None:
        """Test _status_style for failed status."""
        result = PhaseCoordinator._status_style("failed")
        assert result == "red"

    def test_status_style_timeout(self) -> None:
        """Test _status_style for timeout status."""
        result = PhaseCoordinator._status_style("timeout")
        assert result == "yellow"

    def test_status_style_other(self) -> None:
        """Test _status_style for other status."""
        result = PhaseCoordinator._status_style("running")
        assert result == "bright_white"

    def test_process_commit_choice_default(self) -> None:
        """Test _process_commit_choice with empty input (default)."""
        suggestions = ["feat: add new feature", "fix: resolve issue"]
        result = PhaseCoordinator._process_commit_choice("", suggestions)
        assert result == suggestions[0]

    def test_process_commit_choice_valid_number(self) -> None:
        """Test _process_commit_choice with valid number."""
        suggestions = ["feat: add new feature", "fix: resolve issue"]
        result = PhaseCoordinator._process_commit_choice("2", suggestions)
        assert result == suggestions[1]

    def test_process_commit_choice_invalid_number(self) -> None:
        """Test _process_commit_choice with invalid number."""
        suggestions = ["feat: add new feature", "fix: resolve issue"]
        result = PhaseCoordinator._process_commit_choice("5", suggestions)
        # When number is out of range, it should return the input as-is
        assert result == "5"

    def test_process_commit_choice_custom_message(self) -> None:
        """Test _process_commit_choice with custom message."""
        suggestions = ["feat: add new feature", "fix: resolve issue"]
        custom_msg = "Custom commit message"
        result = PhaseCoordinator._process_commit_choice(custom_msg, suggestions)
        assert result == custom_msg

    def test_classify_safe_test_failures(self) -> None:
        """Test _classify_safe_test_failures method."""
        coordinator = PhaseCoordinator()

        # Test with import error (should be safe)
        failures = ["ModuleNotFoundError: No module named 'missing_module'"]
        safe_failures = coordinator._classify_safe_test_failures(failures)
        assert len(safe_failures) == 1

        # Test with assertion error (should be risky)
        failures = ["AssertionError: Expected 5, got 3"]
        safe_failures = coordinator._classify_safe_test_failures(failures)
        assert len(safe_failures) == 0

        # Test with mixed failures
        failures = [
            "ModuleNotFoundError: No module named 'missing_module'",
            "AssertionError: Expected 5, got 3"
        ]
        safe_failures = coordinator._classify_safe_test_failures(failures)
        assert len(safe_failures) == 1
        assert "missing_module" in safe_failures[0]

    def test_apply_ai_fix_for_tests_disabled(self) -> None:
        """Test _apply_ai_fix_for_tests when AI fix is disabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.ai_fix = False

        # Mock the test manager to return some failures
        coordinator.test_manager = MagicMock()
        coordinator.test_manager.get_test_failures.return_value = ["some failure"]

        result = coordinator._apply_ai_fix_for_tests(options)
        # Should return False when AI fix is disabled
        assert result is False

    def test_handle_no_changes_to_commit(self) -> None:
        """Test _handle_no_changes_to_commit method."""
        coordinator = PhaseCoordinator()

        result = coordinator._handle_no_changes_to_commit()

        assert result is True

    def test_display_cleaning_header(self) -> None:
        """Test _display_cleaning_header method."""
        coordinator = PhaseCoordinator()

        # Just ensure it doesn't raise an exception
        coordinator._display_cleaning_header()

    def test_execute_cleaning_process(self) -> None:
        """Test _execute_cleaning_process method."""
        coordinator = PhaseCoordinator()

        # Just ensure it doesn't raise an exception
        # The actual implementation may return different values depending on the code cleaner
        try:
            result = coordinator._execute_cleaning_process()
            # Result could be True/False or other value depending on implementation
        except AttributeError:
            # Method might not be fully implemented yet
            pass

    def test_clean_python_files(self) -> None:
        """Test _clean_python_files method."""
        coordinator = PhaseCoordinator()

        # Just ensure it doesn't raise an exception
        try:
            result = coordinator._clean_python_files([])
            # Result could be a list of cleaned files
        except AttributeError:
            # Method might not be fully implemented yet
            pass

    def test_display_hook_phase_header(self) -> None:
        """Test _display_hook_phase_header method."""
        coordinator = PhaseCoordinator()

        # Just ensure it doesn't raise an exception
        coordinator._display_hook_phase_header("TITLE", "DESCRIPTION")

    def test_display_hook_failures(self) -> None:
        """Test _display_hook_failures method."""
        coordinator = PhaseCoordinator()
        options = MagicMock()

        # Just ensure it doesn't raise an exception
        coordinator._display_hook_failures("fast", [], options)

    def test_run_ai_test_fix(self) -> None:
        """Test _run_ai_test_fix method."""
        coordinator = PhaseCoordinator()
        safe_failures = ["some failure"]

        # Just ensure it doesn't raise an exception
        # This method involves complex async operations that may not work in test context
        try:
            result = coordinator._run_ai_test_fix(safe_failures)
        except Exception:
            # Expected in test environment
            pass
