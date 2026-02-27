"""Tests for PhaseCoordinator methods."""

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.core.phase_coordinator import PhaseCoordinator


@pytest.fixture
def coordinator() -> PhaseCoordinator:
    """Create a PhaseCoordinator instance for testing."""
    return PhaseCoordinator()


@pytest.fixture
def mock_options() -> MagicMock:
    """Create mock options for testing."""
    options = MagicMock()
    options.clean = False
    options.skip_hooks = False
    options.test = False
    options.run_tests = False
    options.no_config_updates = True
    options.configs_dry_run = False
    options.cleanup_docs = False
    options.docs_dry_run = False
    return options


class TestLogger:
    """Test logger property."""

    def test_logger_property(self, coordinator: PhaseCoordinator) -> None:
        """Test logger property getter and setter."""
        new_logger = logging.getLogger("test_logger")
        coordinator.logger = new_logger
        assert coordinator.logger is new_logger


class TestConfigCleanupPhase:
    """Test run_config_cleanup_phase method."""

    def test_run_config_cleanup_phase_basic(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_config_cleanup_phase basic execution."""
        with patch(
            "crackerjack.services.config_cleanup.ConfigCleanupService"
        ) as mock_service_class:
            mock_service_instance = MagicMock()
            mock_service_instance.cleanup_configs.return_value = MagicMock(
                success=True,
                summary="Config cleanup successful",
            )
            mock_service_class.return_value = mock_service_instance

            result = coordinator.run_config_cleanup_phase(mock_options)

            assert result is True


class TestCleaningPhase:
    """Test run_cleaning_phase method."""

    def test_run_cleaning_phase_disabled(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_cleaning_phase when cleaning is disabled."""
        mock_options.clean = False
        result = coordinator.run_cleaning_phase(mock_options)
        assert result is True

    def test_run_cleaning_phase_enabled(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_cleaning_phase when cleaning is enabled."""
        mock_options.clean = True
        with (
            patch.object(coordinator, "_display_cleaning_header"),
            patch.object(coordinator, "_execute_cleaning_process", return_value=True),
        ):
            result = coordinator.run_cleaning_phase(mock_options)
            assert result is True


class TestConfigurationPhase:
    """Test run_configuration_phase method."""

    def test_run_configuration_phase_skip(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_configuration_phase when skipping config updates."""
        mock_options.no_config_updates = True
        result = coordinator.run_configuration_phase(mock_options)
        assert result is True

    def test_run_configuration_phase_enabled(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_configuration_phase when config updates are enabled."""
        mock_options.no_config_updates = False
        result = coordinator.run_configuration_phase(mock_options)
        assert result is True


class TestHooksPhase:
    """Test run_hooks_phase method."""

    @pytest.mark.asyncio
    async def test_run_hooks_phase_skip(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_hooks_phase when skipping hooks."""
        mock_options.skip_hooks = True
        result = await coordinator.run_hooks_phase(mock_options)
        assert result is True

    @pytest.mark.asyncio
    async def test_run_hooks_phase_run_both(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_hooks_phase when running both fast and comprehensive hooks."""
        mock_options.skip_hooks = False
        with (
            patch.object(
                coordinator, "run_fast_hooks_only", new_callable=AsyncMock
            ) as mock_fast,
            patch.object(
                coordinator, "run_comprehensive_hooks_only", new_callable=AsyncMock
            ) as mock_comp,
        ):
            mock_fast.return_value = True
            mock_comp.return_value = True
            result = await coordinator.run_hooks_phase(mock_options)

            mock_fast.assert_called_once_with(mock_options)
            mock_comp.assert_called_once_with(mock_options)
            assert result is True


class TestFastHooksOnly:
    """Test run_fast_hooks_only method."""

    @pytest.mark.asyncio
    async def test_run_fast_hooks_only_skip(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_fast_hooks_only when skipping hooks."""
        mock_options.skip_hooks = True
        result = await coordinator.run_fast_hooks_only(mock_options)
        assert result is True

    @pytest.mark.asyncio
    async def test_run_fast_hooks_only_duplicate_call(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_fast_hooks_only when called twice (duplicate protection)."""
        coordinator._fast_hooks_started = True
        mock_options.skip_hooks = False
        result = await coordinator.run_fast_hooks_only(mock_options)
        assert result is True

    @pytest.mark.asyncio
    async def test_run_fast_hooks_only_normal_flow(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_fast_hooks_only normal execution flow."""
        mock_options.skip_hooks = False
        with patch.object(
            coordinator, "_run_fast_hooks_with_retry", return_value=True
        ) as mock_retry:
            result = await coordinator.run_fast_hooks_only(mock_options)

            mock_retry.assert_called_once_with(mock_options)
            assert result is True
            assert coordinator._fast_hooks_started is True


class TestComprehensiveHooksOnly:
    """Test run_comprehensive_hooks_only method."""

    @pytest.mark.asyncio
    async def test_run_comprehensive_hooks_only_skip(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_comprehensive_hooks_only when skipping hooks."""
        mock_options.skip_hooks = True
        result = await coordinator.run_comprehensive_hooks_only(mock_options)
        assert result is True

    @pytest.mark.asyncio
    async def test_run_comprehensive_hooks_only_normal_flow(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_comprehensive_hooks_only normal execution flow."""
        mock_options.skip_hooks = False
        with patch.object(
            coordinator, "_execute_hooks_once", return_value=True
        ) as mock_execute:
            result = await coordinator.run_comprehensive_hooks_only(mock_options)

            mock_execute.assert_called_once()
            assert result is True


class TestTestingPhase:
    """Test run_testing_phase method."""

    def test_run_testing_phase_disabled(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_testing_phase when testing is disabled."""
        mock_options.test = False
        mock_options.run_tests = False
        result = coordinator.run_testing_phase(mock_options)
        assert result is True

    def test_run_testing_phase_enabled_success(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_testing_phase when testing is enabled and succeeds."""
        mock_options.test = True
        with (
            patch.object(
                coordinator.test_manager, "validate_test_environment", return_value=True
            ),
            patch.object(coordinator.test_manager, "run_tests", return_value=True),
            patch.object(
                coordinator.test_manager,
                "get_coverage",
                return_value={"total_coverage": 95.0},
            ),
        ):
            result = coordinator.run_testing_phase(mock_options)
            assert result is True

    def test_run_testing_phase_enabled_failure(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_testing_phase when testing is enabled and fails."""
        mock_options.test = True
        with (
            patch.object(
                coordinator.test_manager, "validate_test_environment", return_value=True
            ),
            patch.object(coordinator.test_manager, "run_tests", return_value=False),
        ):
            result = coordinator.run_testing_phase(mock_options)
            assert result is False


class TestDocumentationCleanupPhase:
    """Test run_documentation_cleanup_phase method."""

    def test_run_documentation_cleanup_phase_disabled(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_documentation_cleanup_phase when disabled."""
        mock_options.cleanup_docs = False
        result = coordinator.run_documentation_cleanup_phase(mock_options)
        assert result is True

    def test_run_documentation_cleanup_phase_enabled(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test run_documentation_cleanup_phase when enabled."""
        mock_options.cleanup_docs = True
        mock_options.docs_dry_run = False
        with patch(
            "crackerjack.services.documentation_cleanup.DocumentationCleanup"
        ) as mock_service_class:
            mock_service_instance = MagicMock()
            mock_service_instance.cleanup_documentation.return_value = MagicMock(
                success=True,
                summary="Documentation cleanup successful",
            )
            mock_service_class.return_value = mock_service_instance

            result = coordinator.run_documentation_cleanup_phase(mock_options)

            assert result is True
            mock_service_class.assert_called_once()
            mock_service_instance.cleanup_documentation.assert_called_once_with(
                dry_run=False
            )
