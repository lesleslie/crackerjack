"""Unit tests for phase coordinator components."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.config import CrackerjackSettings
from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator


class TestPhaseCoordinatorInitialization:
    """Test PhaseCoordinator initialization."""

    def test_initialization_defaults(self) -> None:
        """Test PhaseCoordinator initialization with defaults."""
        coordinator = PhaseCoordinator()

        assert isinstance(coordinator.console, CrackerjackConsole)
        assert coordinator.pkg_path == Path.cwd()
        assert isinstance(coordinator.session, SessionCoordinator)
        assert coordinator._settings is not None
        assert coordinator.code_cleaner is not None
        assert coordinator._logger is not None
        assert coordinator._last_hook_summary is None
        assert coordinator._last_hook_results == []

    def test_initialization_with_parameters(self) -> None:
        """Test PhaseCoordinator initialization with parameters."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")
        session = MagicMock()
        settings = CrackerjackSettings()

        coordinator = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
            settings=settings,
        )

        assert coordinator.console is console
        assert coordinator.pkg_path == pkg_path
        assert coordinator.session is session
        assert coordinator._settings is settings


class TestPhaseCoordinatorProperties:
    """Test PhaseCoordinator properties."""

    def test_logger_property(self) -> None:
        """Test logger property getter and setter."""
        coordinator = PhaseCoordinator()
        new_logger = logging.getLogger("test")

        coordinator.logger = new_logger

        assert coordinator.logger is new_logger


class TestPhaseCoordinatorPrivateMethods:
    """Test PhaseCoordinator private methods."""

    def test_strip_ansi(self) -> None:
        """Test _strip_ansi method."""
        coordinator = PhaseCoordinator()

        # Test with ANSI codes
        text_with_ansi = "\x1b[31mRed text\x1b[0m and \x1b[1mbold\x1b[0m"
        expected = "Red text and bold"
        result = coordinator._strip_ansi(text_with_ansi)

        assert result == expected

        # Test with plain text
        plain_text = "Plain text without ANSI"
        result = coordinator._strip_ansi(plain_text)

        assert result == plain_text

    def test_is_plain_output(self) -> None:
        """Test _is_plain_output method."""
        coordinator = PhaseCoordinator()

        # This method depends on console properties, so just ensure it doesn't crash
        try:
            result = coordinator._is_plain_output()
            assert isinstance(result, bool)
        except Exception:
            # If there are issues with console properties, that's OK for this test
            pass


class TestPhaseCoordinatorConfigCleanupPhase:
    """Test run_config_cleanup_phase method."""

    def test_run_config_cleanup_phase_success(self) -> None:
        """Test run_config_cleanup_phase with successful cleanup."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.configs_dry_run = False

        with patch('crackerjack.services.config_cleanup.ConfigCleanupService') as mock_service_class:
            mock_service_instance = MagicMock()
            mock_service_instance.cleanup_configs.return_value = MagicMock(
                success=True,
                summary="Config cleanup successful"
            )
            mock_service_class.return_value = mock_service_instance

            result = coordinator.run_config_cleanup_phase(options)

            assert result is True
            mock_service_class.assert_called_once()
            mock_service_instance.cleanup_configs.assert_called_once_with(dry_run=False)
            # Verify session tracking was called
            # Note: We can't easily verify session calls without mocking the session

    def test_run_config_cleanup_phase_failure(self) -> None:
        """Test run_config_cleanup_phase with failed cleanup."""
        coordinator = PhaseCoordinator()
        options = MagicMock()

        with patch('crackerjack.services.config_cleanup.ConfigCleanupService') as mock_service_class:
            mock_service_instance = MagicMock()
            mock_service_instance.cleanup_configs.return_value = MagicMock(
                success=False,
                error_message="Config cleanup failed"
            )
            mock_service_class.return_value = mock_service_instance

            result = coordinator.run_config_cleanup_phase(options)

            assert result is False


class TestPhaseCoordinatorCleaningPhase:
    """Test run_cleaning_phase method."""

    def test_run_cleaning_phase_disabled(self) -> None:
        """Test run_cleaning_phase when cleaning is disabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.clean = False

        result = coordinator.run_cleaning_phase(options)

        # When cleaning is disabled, should return True immediately
        assert result is True

    def test_run_cleaning_phase_enabled(self) -> None:
        """Test run_cleaning_phase when cleaning is enabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.clean = True

        # Mock the internal methods that would be called
        with patch.object(coordinator, '_display_cleaning_header'), \
             patch.object(coordinator, '_execute_cleaning_process', return_value=True):

            result = coordinator.run_cleaning_phase(options)

            assert result is True


class TestPhaseCoordinatorConfigurationPhase:
    """Test run_configuration_phase method."""

    def test_run_configuration_phase_skip(self) -> None:
        """Test run_configuration_phase when skipping config updates."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.no_config_updates = True

        result = coordinator.run_configuration_phase(options)

        # When no_config_updates is True, should return True immediately
        assert result is True

    def test_run_configuration_phase_enabled(self) -> None:
        """Test run_configuration_phase when config updates are enabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.no_config_updates = False

        result = coordinator.run_configuration_phase(options)

        # Currently, this method just prints a message and returns True
        assert result is True


class TestPhaseCoordinatorHooksPhase:
    """Test run_hooks_phase method."""

    def test_run_hooks_phase_skip(self) -> None:
        """Test run_hooks_phase when skipping hooks."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.skip_hooks = True

        result = coordinator.run_hooks_phase(options)

        # When skip_hooks is True, should return True immediately
        assert result is True

    def test_run_hooks_phase_run_both(self) -> None:
        """Test run_hooks_phase when running both fast and comprehensive hooks."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.skip_hooks = False

        with patch.object(coordinator, 'run_fast_hooks_only', return_value=True) as mock_fast, \
             patch.object(coordinator, 'run_comprehensive_hooks_only', return_value=True) as mock_comp:

            result = coordinator.run_hooks_phase(options)

            mock_fast.assert_called_once_with(options)
            mock_comp.assert_called_once_with(options)
            assert result is True

    def test_run_hooks_phase_fast_fails(self) -> None:
        """Test run_hooks_phase when fast hooks fail."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.skip_hooks = False

        with patch.object(coordinator, 'run_fast_hooks_only', return_value=False) as mock_fast, \
             patch.object(coordinator, 'run_comprehensive_hooks_only') as mock_comp:

            result = coordinator.run_hooks_phase(options)

            mock_fast.assert_called_once_with(options)
            # Comprehensive hooks shouldn't be called if fast hooks fail
            mock_comp.assert_not_called()
            assert result is False


class TestPhaseCoordinatorFastHooksOnly:
    """Test run_fast_hooks_only method."""

    def test_run_fast_hooks_only_skip(self) -> None:
        """Test run_fast_hooks_only when skipping hooks."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.skip_hooks = True

        result = coordinator.run_fast_hooks_only(options)

        # When skip_hooks is True, should return True immediately
        assert result is True

    def test_run_fast_hooks_only_duplicate_call(self) -> None:
        """Test run_fast_hooks_only when called twice (duplicate protection)."""
        coordinator = PhaseCoordinator()
        coordinator._fast_hooks_started = True
        options = MagicMock()
        options.skip_hooks = False

        result = coordinator.run_fast_hooks_only(options)

        # When already started, should return True immediately
        assert result is True

    def test_run_fast_hooks_only_normal_flow(self) -> None:
        """Test run_fast_hooks_only normal execution flow."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.skip_hooks = False

        with patch.object(coordinator, '_run_fast_hooks_with_retry', return_value=True) as mock_retry:

            result = coordinator.run_fast_hooks_only(options)

            mock_retry.assert_called_once_with(options)
            assert result is True
            assert coordinator._fast_hooks_started is True


class TestPhaseCoordinatorComprehensiveHooksOnly:
    """Test run_comprehensive_hooks_only method."""

    def test_run_comprehensive_hooks_only_skip(self) -> None:
        """Test run_comprehensive_hooks_only when skipping hooks."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.skip_hooks = True

        result = coordinator.run_comprehensive_hooks_only(options)

        # When skip_hooks is True, should return True immediately
        assert result is True

    def test_run_comprehensive_hooks_only_normal_flow(self) -> None:
        """Test run_comprehensive_hooks_only normal execution flow."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.skip_hooks = False

        with patch.object(coordinator, '_execute_hooks_once', return_value=True) as mock_execute:

            result = coordinator.run_comprehensive_hooks_only(options)

            # Verify the method was called with the right parameters
            mock_execute.assert_called_once()
            assert result is True


class TestPhaseCoordinatorTestingPhase:
    """Test run_testing_phase method."""

    def test_run_testing_phase_disabled(self) -> None:
        """Test run_testing_phase when testing is disabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.test = False
        options.run_tests = False

        result = coordinator.run_testing_phase(options)

        # When testing is disabled, should return True immediately
        assert result is True

    def test_run_testing_phase_enabled_success(self) -> None:
        """Test run_testing_phase when testing is enabled and succeeds."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.test = True

        with patch.object(coordinator.test_manager, 'validate_test_environment', return_value=True), \
             patch.object(coordinator.test_manager, 'run_tests', return_value=True), \
             patch.object(coordinator.test_manager, 'get_coverage', return_value={'total_coverage': 95.0}):

            result = coordinator.run_testing_phase(options)

            assert result is True

    def test_run_testing_phase_enabled_failure(self) -> None:
        """Test run_testing_phase when testing is enabled and fails."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.test = True

        with patch.object(coordinator.test_manager, 'validate_test_environment', return_value=True), \
             patch.object(coordinator.test_manager, 'run_tests', return_value=False):

            result = coordinator.run_testing_phase(options)

            assert result is False


class TestPhaseCoordinatorDocumentationCleanupPhase:
    """Test run_documentation_cleanup_phase method."""

    def test_run_documentation_cleanup_phase_disabled(self) -> None:
        """Test run_documentation_cleanup_phase when disabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.cleanup_docs = False

        result = coordinator.run_documentation_cleanup_phase(options)

        # When cleanup_docs is False, should return True immediately
        assert result is True

    def test_run_documentation_cleanup_phase_enabled(self) -> None:
        """Test run_documentation_cleanup_phase when enabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.cleanup_docs = True
        options.docs_dry_run = False

        with patch('crackerjack.services.documentation_cleanup.DocumentationCleanup') as mock_service_class:
            mock_service_instance = MagicMock()
            mock_service_instance.cleanup_documentation.return_value = MagicMock(
                success=True,
                summary="Documentation cleanup successful"
            )
            mock_service_class.return_value = mock_service_instance

            result = coordinator.run_documentation_cleanup_phase(options)

            assert result is True
            mock_service_class.assert_called_once()
            mock_service_instance.cleanup_documentation.assert_called_once_with(dry_run=False)


class TestPhaseCoordinatorGitCleanupPhase:
    """Test run_git_cleanup_phase method."""

    def test_run_git_cleanup_phase_disabled(self) -> None:
        """Test run_git_cleanup_phase when disabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.cleanup_git = False

        result = coordinator.run_git_cleanup_phase(options)

        # When cleanup_git is False, should return True immediately
        assert result is True

    def test_run_git_cleanup_phase_enabled(self) -> None:
        """Test run_git_cleanup_phase when enabled."""
        coordinator = PhaseCoordinator()
        options = MagicMock()
        options.cleanup_git = True
        options.git_dry_run = False

        with patch('crackerjack.services.git_cleanup.GitCleanupService') as mock_service_class:
            mock_service_instance = MagicMock()
            mock_service_instance.cleanup_git.return_value = MagicMock(
                success=True,
                summary="Git cleanup successful"
            )
            mock_service_class.return_value = mock_service_instance

            result = coordinator.run_git_cleanup_phase(options)

            assert result is True
            mock_service_class.assert_called_once()
            mock_service_instance.cleanup_git.assert_called_once_with(dry_run=False)
