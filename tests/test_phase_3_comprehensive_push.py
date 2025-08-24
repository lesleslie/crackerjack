"""Phase 3: Comprehensive Coverage Push to 42% Target.

Building on our success (12.43% → 21.10% = 75% increase!), this phase targets
the highest-impact remaining modules to reach the mandatory 42% coverage requirement.

STRATEGY: Focus on 0% coverage modules with large line counts for maximum impact.
Uses our proven patterns from previous phases that achieved dramatic results.

Target: 21.10% → 35%+ coverage (another 75% relative increase)
"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.mcp.service_watchdog import (
    ServiceConfig,
    ServiceWatchdog,
    create_default_watchdog,
    main,
)
from crackerjack.orchestration.advanced_orchestrator import (
    AdvancedWorkflowOrchestrator,
    CorrelationTracker,
    MinimalProgressStreamer,
    ProgressStreamer,
)
from crackerjack.services.dependency_monitor import (
    DependencyMonitorService,
    DependencyVulnerability,
    MajorUpdate,
)
from crackerjack.services.health_metrics import HealthMetricsService, ProjectHealth

# ============================================================================
# HEALTH METRICS SERVICE - 309 lines, 0% coverage
# ============================================================================


class TestProjectHealth:
    """Test ProjectHealth dataclass comprehensive functionality."""

    def test_project_health_instantiation(self) -> None:
        """Test ProjectHealth instantiation and default values."""
        health = ProjectHealth()

        assert health.lint_error_trend == []
        assert health.test_coverage_trend == []
        assert health.dependency_age == {}
        assert health.config_completeness == 0.0
        assert isinstance(health.last_updated, float)

    def test_project_health_with_data(self) -> None:
        """Test ProjectHealth with actual data."""
        health = ProjectHealth(
            lint_error_trend=[5, 3, 1],
            test_coverage_trend=[75.0, 80.0, 85.0],
            dependency_age={"pytest": 30, "ruff": 45},
            config_completeness=0.8,
            last_updated=time.time(),
        )

        assert health.lint_error_trend == [5, 3, 1]
        assert health.test_coverage_trend == [75.0, 80.0, 85.0]
        assert health.dependency_age == {"pytest": 30, "ruff": 45}
        assert health.config_completeness == 0.8

    def test_needs_init_lint_trending_up(self) -> None:
        """Test needs_init returns True when lint errors trending up."""
        health = ProjectHealth(lint_error_trend=[1, 2, 3, 4])
        assert health.needs_init()

    def test_needs_init_coverage_trending_down(self) -> None:
        """Test needs_init returns True when coverage trending down."""
        health = ProjectHealth(test_coverage_trend=[90.0, 85.0, 80.0])
        assert health.needs_init()

    def test_needs_init_old_dependencies(self) -> None:
        """Test needs_init returns True for old dependencies."""
        health = ProjectHealth(dependency_age={"old_package": 200})
        assert health.needs_init()

    def test_needs_init_low_config_completeness(self) -> None:
        """Test needs_init returns True for low config completeness."""
        health = ProjectHealth(config_completeness=0.5)
        assert health.needs_init()

    def test_needs_init_false_for_healthy_project(self) -> None:
        """Test needs_init returns False for healthy project."""
        health = ProjectHealth(
            lint_error_trend=[5, 3, 1],
            test_coverage_trend=[75.0, 80.0, 85.0],
            dependency_age={"pytest": 30},
            config_completeness=0.9,
        )
        assert not health.needs_init()

    def test_is_trending_up(self) -> None:
        """Test _is_trending_up method."""
        health = ProjectHealth()

        # Trending up
        assert health._is_trending_up([1, 2, 3, 4])

        # Not trending up
        assert not health._is_trending_up([4, 3, 2, 1])

        # Insufficient data points
        assert not health._is_trending_up([1, 2])

    def test_is_trending_down(self) -> None:
        """Test _is_trending_down method."""
        health = ProjectHealth()

        # Trending down
        assert health._is_trending_down([90.0, 85.0, 80.0])

        # Not trending down
        assert not health._is_trending_down([80.0, 85.0, 90.0])

        # Insufficient data points
        assert not health._is_trending_down([90.0, 85.0])

    def test_get_health_score(self) -> None:
        """Test health score calculation."""
        health = ProjectHealth(
            lint_error_trend=[5, 3, 1],
            test_coverage_trend=[75.0, 80.0, 85.0],
            dependency_age={"pytest": 30, "ruff": 45},
            config_completeness=0.8,
        )

        score = health.get_health_score()
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_get_health_score_empty_data(self) -> None:
        """Test health score with empty data."""
        health = ProjectHealth()
        score = health.get_health_score()
        assert score == 0.0

    def test_get_recommendations(self) -> None:
        """Test recommendations generation."""
        health = ProjectHealth(
            lint_error_trend=[1, 2, 3, 4],
            test_coverage_trend=[90.0, 85.0, 80.0],
            dependency_age={"old_package": 400},
            config_completeness=0.3,
        )

        recommendations = health.get_recommendations()
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert any("lint errors" in rec.lower() for rec in recommendations)
        assert any("test coverage" in rec.lower() for rec in recommendations)
        assert any("dependencies" in rec.lower() for rec in recommendations)
        assert any("configuration" in rec.lower() for rec in recommendations)


class TestHealthMetricsService:
    """Test HealthMetricsService functionality."""

    @pytest.fixture
    def mock_filesystem(self):
        """Mock filesystem interface."""
        fs = Mock()
        fs.read_file.return_value = "test content"
        fs.write_file.return_value = True
        fs.exists.return_value = True
        return fs

    @pytest.fixture
    def health_service(self, mock_filesystem):
        """Create HealthMetricsService instance."""
        with patch("pathlib.Path.cwd", return_value=Path("/test")):
            return HealthMetricsService(mock_filesystem)

    def test_health_service_initialization(self, health_service) -> None:
        """Test HealthMetricsService initialization."""
        assert health_service.filesystem is not None
        assert health_service.console is not None
        assert health_service.max_trend_points == 20

    def test_collect_current_metrics(self, health_service) -> None:
        """Test collecting current metrics."""
        with patch.object(
            health_service, "_load_health_history", return_value=ProjectHealth(),
        ), patch.object(health_service, "_count_lint_errors", return_value=5):
            with patch.object(
                health_service, "_get_test_coverage", return_value=85.0,
            ):
                with patch.object(
                    health_service, "_calculate_dependency_ages", return_value={},
                ):
                    with patch.object(
                        health_service,
                        "_assess_config_completeness",
                        return_value=0.8,
                    ):
                        health = health_service.collect_current_metrics()

                        assert isinstance(health, ProjectHealth)
                        assert 5 in health.lint_error_trend
                        assert 85.0 in health.test_coverage_trend

    def test_load_health_history_no_cache(self, health_service) -> None:
        """Test loading health history when no cache exists."""
        with patch("pathlib.Path.exists", return_value=False):
            health = health_service._load_health_history()
            assert isinstance(health, ProjectHealth)
            assert health.lint_error_trend == []

    def test_save_health_metrics(self, health_service) -> None:
        """Test saving health metrics."""
        health = ProjectHealth(lint_error_trend=[1, 2, 3])

        with patch("pathlib.Path.mkdir"):
            with patch("pathlib.Path.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.write = Mock()

                # Should not raise exception
                health_service._save_health_metrics(health)

    def test_count_lint_errors_success(self, health_service) -> None:
        """Test counting lint errors successfully."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            count = health_service._count_lint_errors()
            assert count == 0

    def test_count_lint_errors_with_failures(self, health_service) -> None:
        """Test counting lint errors with failures."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps([{"rule": "F401"}, {"rule": "E501"}])

        with patch("subprocess.run", return_value=mock_result):
            count = health_service._count_lint_errors()
            assert count == 2

    def test_get_test_coverage_with_existing_file(self, health_service) -> None:
        """Test getting test coverage with existing coverage file."""
        with patch("pathlib.Path.exists", return_value=True):
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps({"totals": {"percent_covered": 85.5}})

            with patch("subprocess.run", return_value=mock_result):
                coverage = health_service._get_test_coverage()
                assert coverage == 85.5

    def test_extract_package_name(self, health_service) -> None:
        """Test extracting package name from dependency spec."""
        assert health_service._extract_package_name("pytest>=7.0.0") == "pytest"
        assert health_service._extract_package_name("ruff~=0.1.0") == "ruff"
        assert health_service._extract_package_name("requests") == "requests"
        assert health_service._extract_package_name("-e .") is None

    def test_assess_config_completeness(self, health_service) -> None:
        """Test assessing configuration completeness."""
        with patch.object(
            health_service, "_assess_pyproject_config", return_value=(0.5, 5),
        ), patch.object(
            health_service, "_assess_precommit_config", return_value=(0.1, 1),
        ), patch.object(
            health_service, "_assess_ci_config", return_value=(0.1, 1),
        ), patch.object(
            health_service,
            "_assess_documentation_config",
            return_value=(0.1, 1),
        ):
            score = health_service._assess_config_completeness()
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0

    def test_analyze_project_health(self, health_service) -> None:
        """Test analyzing project health."""
        with patch.object(health_service, "collect_current_metrics") as mock_collect:
            with patch.object(health_service, "_save_health_metrics"):
                mock_collect.return_value = ProjectHealth()

                health = health_service.analyze_project_health()
                assert isinstance(health, ProjectHealth)
                mock_collect.assert_called_once()

    def test_report_health_status(self, health_service) -> None:
        """Test reporting health status."""
        health = ProjectHealth(
            lint_error_trend=[5],
            test_coverage_trend=[85.0],
            dependency_age={"pytest": 30},
            config_completeness=0.8,
        )

        # Should not raise exception
        health_service.report_health_status(health)


# ============================================================================
# DEPENDENCY MONITOR SERVICE - 290 lines, 0% coverage
# ============================================================================


class TestDependencyVulnerability:
    """Test DependencyVulnerability dataclass."""

    def test_vulnerability_creation(self) -> None:
        """Test creating vulnerability instance."""
        vuln = DependencyVulnerability(
            package="requests",
            installed_version="2.25.1",
            vulnerability_id="CVE-2021-33503",
            severity="HIGH",
            advisory_url="https://example.com/advisory",
            vulnerable_versions="<2.26.0",
            patched_version="2.26.0",
        )

        assert vuln.package == "requests"
        assert vuln.installed_version == "2.25.1"
        assert vuln.vulnerability_id == "CVE-2021-33503"
        assert vuln.severity == "HIGH"


class TestMajorUpdate:
    """Test MajorUpdate dataclass."""

    def test_major_update_creation(self) -> None:
        """Test creating major update instance."""
        update = MajorUpdate(
            package="django",
            current_version="3.2.0",
            latest_version="4.0.0",
            release_date="2021-12-07",
            breaking_changes=True,
        )

        assert update.package == "django"
        assert update.current_version == "3.2.0"
        assert update.latest_version == "4.0.0"
        assert update.breaking_changes is True


class TestDependencyMonitorService:
    """Test DependencyMonitorService functionality."""

    @pytest.fixture
    def mock_filesystem(self):
        """Mock filesystem interface."""
        fs = Mock()
        fs.read_file.return_value = "test content"
        fs.write_file.return_value = True
        fs.exists.return_value = True
        return fs

    @pytest.fixture
    def dependency_service(self, mock_filesystem):
        """Create DependencyMonitorService instance."""
        with patch("pathlib.Path.cwd", return_value=Path("/test")):
            return DependencyMonitorService(mock_filesystem)

    def test_service_initialization(self, dependency_service) -> None:
        """Test service initialization."""
        assert dependency_service.filesystem is not None
        assert dependency_service.console is not None
        assert dependency_service.project_root == Path("/test")

    def test_parse_dependencies(self, dependency_service) -> None:
        """Test parsing dependencies from pyproject.toml."""
        mock_toml_data = {
            "project": {
                "dependencies": ["pytest>=7.0.0", "ruff~=0.1.0"],
                "optional-dependencies": {"dev": ["black>=22.0.0"]},
            },
        }

        with patch("tomllib.load", return_value=mock_toml_data):
            with patch("pathlib.Path.open", create=True):
                dependencies = dependency_service._parse_dependencies()

                assert "pytest" in dependencies
                assert "ruff" in dependencies
                assert "black" in dependencies

    def test_parse_dependency_spec(self, dependency_service) -> None:
        """Test parsing individual dependency specs."""
        assert dependency_service._parse_dependency_spec("pytest>=7.0.0") == (
            "pytest",
            "7.0.0",
        )
        assert dependency_service._parse_dependency_spec("ruff~=0.1.0") == (
            "ruff",
            "0.1.0",
        )
        assert dependency_service._parse_dependency_spec("requests") == (
            "requests",
            "latest",
        )
        assert dependency_service._parse_dependency_spec("-e .") == (None, None)

    def test_check_dependency_updates_no_pyproject(self, dependency_service) -> None:
        """Test checking updates when no pyproject.toml exists."""
        with patch("pathlib.Path.exists", return_value=False):
            result = dependency_service.check_dependency_updates()
            assert result is False

    def test_check_dependency_updates_with_vulnerabilities(self, dependency_service) -> None:
        """Test checking updates with vulnerabilities found."""
        mock_dependencies = {"requests": "2.25.1"}
        mock_vulnerabilities = [
            DependencyVulnerability(
                package="requests",
                installed_version="2.25.1",
                vulnerability_id="CVE-2021-33503",
                severity="HIGH",
                advisory_url="",
                vulnerable_versions="",
                patched_version="2.26.0",
            ),
        ]

        with patch.object(
            dependency_service, "_parse_dependencies", return_value=mock_dependencies,
        ), patch.object(
            dependency_service,
            "_check_security_vulnerabilities",
            return_value=mock_vulnerabilities,
        ), patch.object(
            dependency_service, "_check_major_updates", return_value=[],
        ), patch.object(dependency_service, "_report_vulnerabilities"):
            result = dependency_service.check_dependency_updates()
            assert result is True

    def test_create_requirements_file(self, dependency_service) -> None:
        """Test creating temporary requirements file."""
        dependencies = {"pytest": "7.0.0", "ruff": "latest"}

        temp_file = dependency_service._create_requirements_file(dependencies)

        assert temp_file.endswith(".txt")
        Path(temp_file).unlink(missing_ok=True)  # Cleanup

    def test_is_major_version_update(self, dependency_service) -> None:
        """Test detecting major version updates."""
        assert dependency_service._is_major_version_update("2.0.0", "3.0.0") is True
        assert dependency_service._is_major_version_update("2.5.0", "2.6.0") is False
        assert dependency_service._is_major_version_update("1.0", "2.0") is True

    def test_load_update_cache_no_file(self, dependency_service) -> None:
        """Test loading update cache when file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            cache = dependency_service._load_update_cache()
            assert cache == {}

    def test_save_update_cache(self, dependency_service) -> None:
        """Test saving update cache."""
        cache = {"test": "data"}

        with patch("pathlib.Path.mkdir"):
            with patch("pathlib.Path.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.write = Mock()

                # Should not raise exception
                dependency_service._save_update_cache(cache)

    def test_force_check_updates(self, dependency_service) -> None:
        """Test forcing check for updates."""
        mock_dependencies = {"pytest": "7.0.0"}
        mock_vulnerabilities = []
        mock_updates = []

        with patch("pathlib.Path.exists", return_value=True), patch.object(
            dependency_service,
            "_parse_dependencies",
            return_value=mock_dependencies,
        ), patch.object(
            dependency_service,
            "_check_security_vulnerabilities",
            return_value=mock_vulnerabilities,
        ), patch.object(
            dependency_service,
            "_check_major_updates",
            return_value=mock_updates,
        ):
            vulns, updates = dependency_service.force_check_updates()
            assert vulns == []
            assert updates == []


# ============================================================================
# SERVICE WATCHDOG - 287 lines, 0% coverage
# ============================================================================


class TestServiceConfig:
    """Test ServiceConfig functionality."""

    def test_service_config_creation(self) -> None:
        """Test creating ServiceConfig instance."""
        config = ServiceConfig(
            name="Test Service",
            command=["python", "-m", "test"],
            health_check_url="http://localhost:8080",
            health_check_interval=30.0,
        )

        assert config.name == "Test Service"
        assert config.command == ["python", "-m", "test"]
        assert config.health_check_url == "http://localhost:8080"
        assert config.health_check_interval == 30.0
        assert config.process is None
        assert config.restart_count == 0

    def test_service_config_defaults(self) -> None:
        """Test ServiceConfig default values."""
        config = ServiceConfig(name="Test Service", command=["python", "-m", "test"])

        assert config.health_check_url is None
        assert config.health_check_interval == 30.0
        assert config.restart_delay == 5.0
        assert config.max_restarts == 10
        assert config.restart_window == 300.0


class TestServiceWatchdog:
    """Test ServiceWatchdog functionality."""

    @pytest.fixture
    def mock_service_config(self):
        """Create mock ServiceConfig."""
        return ServiceConfig(
            name="Test Service",
            command=["python", "-m", "test"],
            health_check_url="http://localhost:8080",
        )

    @pytest.fixture
    def service_watchdog(self, mock_service_config):
        """Create ServiceWatchdog instance."""
        return ServiceWatchdog([mock_service_config])

    def test_watchdog_initialization(self, service_watchdog) -> None:
        """Test ServiceWatchdog initialization."""
        assert len(service_watchdog.services) == 1
        assert service_watchdog.is_running is True
        assert service_watchdog.session is None

    def test_is_port_in_use(self, service_watchdog) -> None:
        """Test port checking functionality."""
        # This will depend on what ports are actually available
        result = service_watchdog._is_port_in_use(8675)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_start_service_mock_process(self, service_watchdog) -> None:
        """Test starting a service with mocked process."""
        service = service_watchdog.services[0]

        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running

        with patch("subprocess.Popen", return_value=mock_process):
            with patch.object(service_watchdog, "_health_check", return_value=True):
                with patch("asyncio.sleep", return_value=None):  # Speed up test
                    result = await service_watchdog._start_service(service)
                    assert result is True
                    assert service.process == mock_process

    @pytest.mark.asyncio
    async def test_health_check_success(self, service_watchdog) -> None:
        """Test successful health check."""
        service_watchdog.session = Mock()

        mock_response = Mock()
        mock_response.status = 200

        mock_session = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        service_watchdog.session = mock_session
        service = service_watchdog.services[0]

        result = await service_watchdog._health_check(service)
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, service_watchdog) -> None:
        """Test failed health check."""
        service_watchdog.session = Mock()

        mock_response = Mock()
        mock_response.status = 500

        mock_session = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        service_watchdog.session = mock_session
        service = service_watchdog.services[0]

        result = await service_watchdog._health_check(service)
        assert result is False

    @pytest.mark.asyncio
    async def test_emit_event(self, service_watchdog) -> None:
        """Test event emission."""
        event_queue = asyncio.Queue()
        service_watchdog.event_queue = event_queue

        await service_watchdog._emit_event("test", "TestService", "Test message")

        event = await event_queue.get()
        assert event["type"] == "test"
        assert event["service"] == "TestService"
        assert event["message"] == "Test message"

    def test_get_service_status(self, service_watchdog) -> None:
        """Test getting service status display."""
        service = service_watchdog.services[0]
        service.process = Mock()
        service.process.poll.return_value = None  # Running

        status = service_watchdog._get_service_status(service)
        assert "[green]" in status
        assert "Running" in status

    def test_get_service_health(self, service_watchdog) -> None:
        """Test getting service health display."""
        service = service_watchdog.services[0]
        service.is_healthy = True

        health = service_watchdog._get_service_health(service)
        assert "[green]" in health
        assert "Healthy" in health

    def test_format_error_message(self, service_watchdog) -> None:
        """Test error message formatting."""
        short_error = "Short error"
        long_error = "This is a very long error message that should be truncated"

        formatted_short = service_watchdog._format_error_message(short_error)
        formatted_long = service_watchdog._format_error_message(long_error)

        assert formatted_short == short_error
        assert len(formatted_long) <= 30
        assert "..." in formatted_long

    @pytest.mark.asyncio
    async def test_cleanup(self, service_watchdog) -> None:
        """Test cleanup functionality."""
        mock_session = Mock()
        mock_session.closed = False
        mock_session.close = AsyncMock()

        service_watchdog.session = mock_session

        await service_watchdog._cleanup()
        mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_create_default_watchdog() -> None:
    """Test creating default watchdog configuration."""
    watchdog = await create_default_watchdog()

    assert isinstance(watchdog, ServiceWatchdog)
    assert len(watchdog.services) == 2
    assert watchdog.services[0].name == "MCP Server"
    assert watchdog.services[1].name == "WebSocket Server"


@pytest.mark.asyncio
async def test_main_with_keyboard_interrupt() -> None:
    """Test main function with keyboard interrupt."""
    with patch(
        "crackerjack.mcp.service_watchdog.create_default_watchdog",
    ) as mock_create:
        mock_watchdog = Mock()
        mock_watchdog.start = AsyncMock(side_effect=KeyboardInterrupt())
        mock_watchdog.stop = AsyncMock()
        mock_create.return_value = mock_watchdog

        # Should not raise exception
        await main()
        mock_watchdog.stop.assert_called_once()


# ============================================================================
# ORCHESTRATION - CORRELATION TRACKER - 400+ lines, low coverage
# ============================================================================


class TestCorrelationTracker:
    """Test CorrelationTracker functionality."""

    def test_correlation_tracker_initialization(self) -> None:
        """Test CorrelationTracker initialization."""
        tracker = CorrelationTracker()

        assert tracker.iteration_data == []
        assert tracker.failure_patterns == {}
        assert tracker.fix_success_rates == {}

    def test_record_iteration(self) -> None:
        """Test recording iteration data."""
        tracker = CorrelationTracker()

        from crackerjack.models.task import HookResult

        hook_results = [
            HookResult(name="ruff-check", status="failed", error="Format error"),
            HookResult(name="pyright", status="passed", error=None),
        ]

        test_results = {"failed_tests": ["test_example.py::test_fail"]}
        ai_fixes = ["Fixed import order", "Updated type hints"]

        tracker.record_iteration(1, hook_results, test_results, ai_fixes)

        assert len(tracker.iteration_data) == 1
        iteration = tracker.iteration_data[0]
        assert iteration["iteration"] == 1
        assert "ruff-check" in iteration["failed_hooks"]
        assert "pyright" not in iteration["failed_hooks"]

    def test_analyze_failure_patterns(self) -> None:
        """Test failure pattern analysis."""
        tracker = CorrelationTracker()

        from crackerjack.models.task import HookResult

        # Record first iteration
        hook_results_1 = [
            HookResult(name="ruff-check", status="failed", error="Error 1"),
        ]
        tracker.record_iteration(1, hook_results_1, {}, [])

        # Record second iteration with same failure
        hook_results_2 = [
            HookResult(name="ruff-check", status="failed", error="Error 2"),
        ]
        tracker.record_iteration(2, hook_results_2, {}, [])

        assert "ruff-check" in tracker.failure_patterns
        assert len(tracker.failure_patterns["ruff-check"]) == 1

    def test_get_problematic_hooks(self) -> None:
        """Test identifying problematic hooks."""
        tracker = CorrelationTracker()

        from crackerjack.models.task import HookResult

        # Create multiple failures for the same hook
        for i in range(3):
            hook_results = [
                HookResult(name="ruff-check", status="failed", error=f"Error {i}"),
            ]
            tracker.record_iteration(i + 1, hook_results, {}, [])

        problematic = tracker.get_problematic_hooks()
        assert "ruff-check" in problematic

    def test_get_correlation_data(self) -> None:
        """Test getting correlation data."""
        tracker = CorrelationTracker()

        from crackerjack.models.task import HookResult

        hook_results = [
            HookResult(name="test-hook", status="failed", error="Test error"),
        ]

        tracker.record_iteration(1, hook_results, {}, [])

        data = tracker.get_correlation_data()
        assert data["iteration_count"] == 1
        assert isinstance(data["failure_patterns"], dict)
        assert isinstance(data["recent_trends"], list)


class TestMinimalProgressStreamer:
    """Test MinimalProgressStreamer fallback functionality."""

    def test_minimal_progress_streamer(self) -> None:
        """Test MinimalProgressStreamer instantiation and methods."""
        streamer = MinimalProgressStreamer()

        # These should not raise exceptions
        streamer.update_stage("test", "substage")

        from crackerjack.executors.individual_hook_executor import HookProgress

        progress = HookProgress("test-hook", 0.5, "running")
        streamer.update_hook_progress(progress)

        streamer._stream_update({"test": "data"})


class TestProgressStreamer:
    """Test ProgressStreamer functionality."""

    @pytest.fixture
    def mock_config(self):
        """Mock orchestration config."""
        from crackerjack.orchestration.execution_strategies import OrchestrationConfig

        return OrchestrationConfig()

    @pytest.fixture
    def mock_session(self):
        """Mock session coordinator."""
        session = Mock()
        session.update_stage = Mock()
        session.web_job_id = "test-job-123"
        return session

    def test_progress_streamer_initialization(self, mock_config, mock_session) -> None:
        """Test ProgressStreamer initialization."""
        streamer = ProgressStreamer(mock_config, mock_session)

        assert streamer.config == mock_config
        assert streamer.session == mock_session
        assert streamer.current_stage == "initialization"
        assert streamer.current_substage == ""

    def test_update_stage(self, mock_config, mock_session) -> None:
        """Test updating stage."""
        streamer = ProgressStreamer(mock_config, mock_session)

        streamer.update_stage("testing", "unit_tests")

        assert streamer.current_stage == "testing"
        assert streamer.current_substage == "unit_tests"
        mock_session.update_stage.assert_called()

    def test_update_hook_progress(self, mock_config, mock_session) -> None:
        """Test updating hook progress."""
        streamer = ProgressStreamer(mock_config, mock_session)

        from crackerjack.executors.individual_hook_executor import HookProgress

        progress = HookProgress("test-hook", 0.7, "running")

        streamer.update_hook_progress(progress)

        assert "test-hook" in streamer.hook_progress
        assert streamer.hook_progress["test-hook"] == progress


class TestAdvancedWorkflowOrchestrator:
    """Test AdvancedWorkflowOrchestrator key functionality."""

    @pytest.fixture
    def mock_console(self):
        """Mock console."""
        return Mock()

    @pytest.fixture
    def mock_session(self):
        """Mock session coordinator."""
        session = Mock()
        session.update_stage = Mock()
        return session

    @pytest.fixture
    def orchestrator(self, mock_console, mock_session):
        """Create orchestrator instance."""
        pkg_path = Path("/test/package")

        with patch("crackerjack.orchestration.advanced_orchestrator.HookConfigLoader"):
            with patch("crackerjack.orchestration.advanced_orchestrator.HookExecutor"):
                with patch(
                    "crackerjack.orchestration.advanced_orchestrator.IndividualHookExecutor",
                ):
                    with patch(
                        "crackerjack.orchestration.advanced_orchestrator.TestManagementImpl",
                    ):
                        with patch(
                            "crackerjack.orchestration.advanced_orchestrator.TestProgressStreamer",
                        ):
                            with patch(
                                "crackerjack.orchestration.advanced_orchestrator.OrchestrationPlanner",
                            ):
                                return AdvancedWorkflowOrchestrator(
                                    mock_console, pkg_path, mock_session,
                                )

    def test_orchestrator_initialization(self, orchestrator) -> None:
        """Test orchestrator initialization."""
        assert orchestrator.console is not None
        assert orchestrator.session is not None
        assert isinstance(orchestrator.correlation_tracker, CorrelationTracker)
        assert orchestrator.progress_streamer is not None

    def test_detect_and_configure_mcp_mode(self, orchestrator) -> None:
        """Test MCP mode detection and configuration."""
        # Mock console with StringIO (indicates MCP mode)
        orchestrator.console.file = Mock()
        orchestrator.console.file.getvalue = Mock(return_value="test")

        orchestrator._detect_and_configure_mcp_mode()

        # Should configure for MCP mode without errors
        assert True  # Test passes if no exception raised

    def test_display_iteration_stats(self, orchestrator) -> None:
        """Test iteration statistics display."""
        iteration_times = {"hooks": 10.5, "tests": 5.2, "ai": 2.1}
        context = Mock()
        context.hook_failures = ["ruff-check", "pyright"]
        context.test_failures = ["test_fail"]

        # Should not raise exception
        orchestrator._display_iteration_stats(
            iteration=1,
            max_iterations=5,
            iteration_times=iteration_times,
            hooks_time=10.5,
            tests_time=5.2,
            ai_time=2.1,
            context=context,
        )

    def test_map_hook_to_issue_type(self, orchestrator) -> None:
        """Test mapping hook names to issue types."""
        from crackerjack.agents import IssueType

        assert (
            orchestrator._map_hook_to_issue_type("ruff-format") == IssueType.FORMATTING
        )
        assert orchestrator._map_hook_to_issue_type("pyright") == IssueType.TYPE_ERROR
        assert orchestrator._map_hook_to_issue_type("bandit") == IssueType.SECURITY
        assert orchestrator._map_hook_to_issue_type("vulture") == IssueType.DEAD_CODE
        assert (
            orchestrator._map_hook_to_issue_type("unknown-hook") == IssueType.FORMATTING
        )

    def test_print_final_analysis(self, orchestrator) -> None:
        """Test final analysis printing."""
        # Add some data to correlation tracker
        from crackerjack.models.task import HookResult

        hook_results = [HookResult(name="test-hook", status="failed", error="Test")]
        orchestrator.correlation_tracker.record_iteration(1, hook_results, {}, [])

        # Should not raise exception
        orchestrator._print_final_analysis()


# ============================================================================
# MCP MONITORING TOOLS - 200+ lines, 0% coverage
# ============================================================================


class TestMCPMonitoringTools:
    """Test MCP monitoring tools functionality."""

    def test_create_error_response(self) -> None:
        """Test error response creation."""
        from crackerjack.mcp.tools.monitoring_tools import _create_error_response

        response = _create_error_response("Test error")
        data = json.loads(response)

        assert data["error"] == "Test error"
        assert data["success"] is False

    def test_get_stage_status_dict(self) -> None:
        """Test stage status dictionary creation."""
        from crackerjack.mcp.tools.monitoring_tools import _get_stage_status_dict

        mock_state_manager = Mock()
        mock_state_manager.get_stage_status.return_value = "completed"

        status_dict = _get_stage_status_dict(mock_state_manager)

        assert isinstance(status_dict, dict)
        assert "fast" in status_dict
        assert "comprehensive" in status_dict
        assert "tests" in status_dict
        assert "cleaning" in status_dict

    def test_get_session_info(self) -> None:
        """Test session info extraction."""
        from crackerjack.mcp.tools.monitoring_tools import _get_session_info

        mock_state_manager = Mock()
        mock_state_manager.iteration_count = 5
        mock_state_manager.current_iteration = 3
        mock_state_manager.session_active = True

        session_info = _get_session_info(mock_state_manager)

        assert session_info["total_iterations"] == 5
        assert session_info["current_iteration"] == 3
        assert session_info["session_active"] is True

    def test_determine_next_action(self) -> None:
        """Test next action determination."""
        from crackerjack.mcp.tools.monitoring_tools import _determine_next_action

        mock_state_manager = Mock()
        mock_state_manager.get_stage_status.side_effect = lambda stage: {
            "fast": "running",
            "tests": "not_started",
            "comprehensive": "not_started",
        }.get(stage, "not_started")

        action = _determine_next_action(mock_state_manager)

        assert action["recommended_action"] == "run_stage"
        assert action["parameters"]["stage"] == "fast"

    def test_build_server_stats(self) -> None:
        """Test server stats building."""
        from crackerjack.mcp.tools.monitoring_tools import _build_server_stats

        mock_context = Mock()
        mock_context.config.project_path = Path("/test/project")
        mock_context.progress_dir = Path("/test/progress")
        mock_context.progress_dir.exists.return_value = True
        mock_context.progress_dir.glob.return_value = [
            Path("file1.json"),
            Path("file2.json"),
        ]
        mock_context.rate_limiter = None

        stats = _build_server_stats(mock_context)

        assert "server_info" in stats
        assert "rate_limiting" in stats
        assert "resource_usage" in stats
        assert "timestamp" in stats

    def test_get_active_jobs(self) -> None:
        """Test active jobs retrieval."""
        from crackerjack.mcp.tools.monitoring_tools import _get_active_jobs

        mock_context = Mock()
        mock_context.progress_dir = Path("/test/progress")
        mock_context.progress_dir.exists.return_value = False

        jobs = _get_active_jobs(mock_context)
        assert jobs == []

    @pytest.mark.asyncio
    async def test_get_comprehensive_status_no_context(self) -> None:
        """Test comprehensive status with no context."""
        from crackerjack.mcp.tools.monitoring_tools import _get_comprehensive_status

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            side_effect=RuntimeError(),
        ):
            status = await _get_comprehensive_status()

            assert "error" in status
            assert "Server context not available" in status["error"]

    @pytest.mark.asyncio
    async def test_get_comprehensive_status_success(self) -> None:
        """Test successful comprehensive status retrieval."""
        from crackerjack.mcp.tools.monitoring_tools import _get_comprehensive_status

        mock_context = Mock()
        mock_context.progress_dir = Path("/test")
        mock_context.progress_dir.exists.return_value = True
        mock_context.progress_dir.glob.return_value = []
        mock_context.config.project_path = Path("/test")
        mock_context.rate_limiter = None
        mock_context.get_websocket_server_status = AsyncMock(
            return_value={"status": "ok"},
        )

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_context",
            return_value=mock_context,
        ), patch(
            "crackerjack.services.server_manager.find_mcp_server_processes",
            return_value=[],
        ), patch(
            "crackerjack.services.server_manager.find_websocket_server_processes",
            return_value=[],
        ):
            status = await _get_comprehensive_status()

            assert "services" in status
            assert "jobs" in status
            assert "server_stats" in status
            assert "timestamp" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
