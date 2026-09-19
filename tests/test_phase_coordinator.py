"""Tests for PhaseCoordinator methods."""

import io
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.models.task import HookResult


@pytest.fixture
def coordinator() -> PhaseCoordinator:
    """Create a PhaseCoordinator instance for testing."""
    return PhaseCoordinator()


@pytest.fixture
def capturing_coordinator() -> PhaseCoordinator:
    """PhaseCoordinator with a console backed by an in-memory StringIO.

    Lets tests assert on captured Rich output via .console.file.getvalue().
    """
    buffer = io.StringIO()
    console = CrackerjackConsole(
        file=buffer,
        force_terminal=False,
        no_color=True,
        width=200,
    )
    return PhaseCoordinator(console=console)


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
                return_value={"coverage_percent": 95.0},
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
        with (
            patch(
                "crackerjack.core.phase_coordinator.DocumentationCleanup"
            ) as mock_service_class,
            patch(
                "crackerjack.core.phase_coordinator.FrontmatterValidator"
            ) as mock_validator_class,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.cleanup_documentation.return_value = MagicMock(
                success=True,
                summary="Documentation cleanup successful",
            )
            mock_service_class.return_value = mock_service_instance
            mock_validator_class.return_value.validate.return_value = MagicMock(
                success=True,
                files_scanned=0,
                errors=[],
                warnings=[],
                duration_ms=0,
                error_count=0,
                warning_count=0,
            )

            result = coordinator.run_documentation_cleanup_phase(mock_options)

            assert result is True
            mock_service_class.assert_called_once()
            mock_service_instance.cleanup_documentation.assert_called_once_with(
                dry_run=False
            )

    def test_run_documentation_cleanup_phase_failure(
        self,
        coordinator: PhaseCoordinator,
        mock_options: MagicMock,
    ) -> None:
        """Test documentation cleanup failures are propagated to the session."""
        mock_options.cleanup_docs = True
        mock_options.docs_dry_run = False
        with (
            patch(
                "crackerjack.core.phase_coordinator.DocumentationCleanup"
            ) as mock_service_class,
            patch(
                "crackerjack.core.phase_coordinator.FrontmatterValidator"
            ) as mock_validator_class,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.cleanup_documentation.return_value = MagicMock(
                success=False,
                error_message="Documentation cleanup failed",
            )
            mock_service_class.return_value = mock_service_instance
            mock_validator_class.return_value.validate.return_value = MagicMock(
                success=True,
                files_scanned=0,
                errors=[],
                warnings=[],
                duration_ms=0,
                error_count=0,
                warning_count=0,
            )

            result = coordinator.run_documentation_cleanup_phase(mock_options)

            assert result is False
            mock_service_instance.cleanup_documentation.assert_called_once_with(
                dry_run=False
            )

    def test_run_documentation_cleanup_phase_with_missing_frontmatter(
        self,
        tmp_path: Path,
    ) -> None:
        """End-to-end: cleanup phase succeeds when a missing-frontmatter file exists.

        Regression: the documentation_cleanup phase must not be blocked by
        MISSING_FRONTMATTER errors. Uses real services (no MagicMock) to
        exercise the in-process validator path.
        """
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        # Create a repo with a missing-frontmatter file in docs/plans/.
        plans = tmp_path / "docs" / "plans"
        plans.mkdir(parents=True)
        (plans / "legacy.md").write_text(
            "# Legacy doc\n\nNo frontmatter here.\n",
            encoding="utf-8",
        )

        coordinator = PhaseCoordinator(pkg_path=tmp_path)

        options = MagicMock()
        options.cleanup_docs = True
        options.docs_dry_run = True

        result = coordinator.run_documentation_cleanup_phase(options)
        assert result is True, (
            "cleanup phase must succeed despite missing-frontmatter"
        )


class TestExecuteHooksOnceFailFirst:
    """Tests for the --fail-first bail-on-first-failure flag.

    The flag is plumbed via Options.fail_first (boolean). When set,
    _execute_hooks_once must return False after the FIRST failing hook,
    print that hook's details via the existing _format_failing_hooks
    + _print_single_hook_failure helpers, and skip the full results
    table rendering.

    Distinct from TimeoutStrategy.FAIL_FAST (timeout_manager.py:52),
    which is an internal timeout-failure strategy.
    """

    @staticmethod
    def _make_hook_result(
        name: str,
        status: str,
        *,
        exit_code: int | None = None,
        issues_found: list[str] | None = None,
    ) -> HookResult:
        return HookResult(
            name=name,
            status=status,
            exit_code=exit_code,
            issues_found=issues_found or [],
        )

    def test_bails_on_first_failure_when_fail_first_true(
        self,
        capturing_coordinator: PhaseCoordinator,
    ) -> None:
        """--fail-first bails on the first failing hook and prints its details."""
        options = MagicMock()
        options.fail_first = True
        options.verbose = False
        options.ai_debug = False

        first_failure = self._make_hook_result(
            "ruff-check",
            "failed",
            exit_code=1,
            issues_found=[
                "/path/to/file.py:45: N818 Exception name should end with Error",
            ],
        )
        hook_runner = MagicMock(return_value=[first_failure])

        def populate_results(*args: object, **kwargs: object) -> float:
            # _run_hooks_with_progress normally sets self._last_hook_results
            # from the runner; the mock bypasses that, so we populate here.
            capturing_coordinator._last_hook_results = [first_failure]
            return 1.0

        with (
            patch.object(
                capturing_coordinator,
                "_run_hooks_with_progress",
                side_effect=populate_results,
            ),
            patch.object(
                capturing_coordinator,
                "_process_hook_results",
                return_value=False,
            ) as mock_process,
        ):
            result = capturing_coordinator._execute_hooks_once(
                "fast",
                hook_runner,
                options,
                attempt=1,
            )

        assert result is False, "should bail with False on first failure"
        mock_process.assert_not_called(), (
            "full results table must NOT render in bail mode"
        )
        output = capturing_coordinator.console.file.getvalue()
        assert "Details for failing fast hooks" in output, (
            f"expected failure-details header in output, got:\n{output}"
        )
        assert "ruff-check" in output, (
            f"expected failing hook name in output, got:\n{output}"
        )

    def test_no_bail_when_all_hooks_pass(
        self,
        capturing_coordinator: PhaseCoordinator,
    ) -> None:
        """--fail-first does not bail when every hook passes."""
        options = MagicMock()
        options.fail_first = True
        options.verbose = False
        options.ai_debug = False

        passing = self._make_hook_result("ruff-check", "passed", exit_code=0)
        hook_runner = MagicMock(return_value=[passing])

        def populate_results(*args: object, **kwargs: object) -> float:
            capturing_coordinator._last_hook_results = [passing]
            return 1.0

        with (
            patch.object(
                capturing_coordinator,
                "_run_hooks_with_progress",
                side_effect=populate_results,
            ),
            patch.object(
                capturing_coordinator,
                "_process_hook_results",
                return_value=True,
            ) as mock_process,
        ):
            result = capturing_coordinator._execute_hooks_once(
                "fast",
                hook_runner,
                options,
                attempt=1,
            )

        assert result is True
        mock_process.assert_called_once(), (
            "normal results table must render when no hooks fail"
        )
        output = capturing_coordinator.console.file.getvalue()
        assert "Details for failing" not in output, (
            f"no failure panel expected when all hooks pass, got:\n{output}"
        )

    def test_no_bail_when_fail_first_false(
        self,
        capturing_coordinator: PhaseCoordinator,
    ) -> None:
        """Without --fail-first, existing behavior is preserved (full table on failure)."""
        options = MagicMock()
        options.fail_first = False
        options.verbose = False
        options.ai_debug = False

        failing = self._make_hook_result(
            "ruff-check",
            "failed",
            exit_code=1,
            issues_found=["some issue"],
        )
        hook_runner = MagicMock(return_value=[failing])

        with (
            patch.object(
                capturing_coordinator,
                "_run_hooks_with_progress",
                return_value=1.0,
            ),
            patch.object(
                capturing_coordinator,
                "_process_hook_results",
                return_value=False,
            ) as mock_process,
        ):
            result = capturing_coordinator._execute_hooks_once(
                "fast",
                hook_runner,
                options,
                attempt=1,
            )

        assert result is False
        mock_process.assert_called_once(), (
            "without --fail-first, full results table must still render"
        )

    def test_bail_skips_results_after_first_failure_even_if_more_fail(
        self,
        capturing_coordinator: PhaseCoordinator,
    ) -> None:
        """--fail-first reports ONLY the first failing hook, not subsequent ones."""
        options = MagicMock()
        options.fail_first = True
        options.verbose = False
        options.ai_debug = False

        first = self._make_hook_result(
            "ruff-check",
            "failed",
            exit_code=1,
            issues_found=["first issue"],
        )
        second = self._make_hook_result(
            "mypy",
            "failed",
            exit_code=1,
            issues_found=["second issue"],
        )
        hook_runner = MagicMock(return_value=[first, second])

        def populate_results(*args: object, **kwargs: object) -> float:
            capturing_coordinator._last_hook_results = [first, second]
            return 1.0

        with (
            patch.object(
                capturing_coordinator,
                "_run_hooks_with_progress",
                side_effect=populate_results,
            ),
            patch.object(
                capturing_coordinator,
                "_process_hook_results",
                return_value=False,
            ) as mock_process,
        ):
            capturing_coordinator._execute_hooks_once(
                "fast",
                hook_runner,
                options,
                attempt=1,
            )

        output = capturing_coordinator.console.file.getvalue()
        assert "ruff-check" in output
        assert "first issue" in output
        mock_process.assert_not_called(), (
            "second hook should not be reported in bail mode"
        )

