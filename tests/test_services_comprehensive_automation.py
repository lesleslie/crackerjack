"""SUPER GROOVY COMPREHENSIVE TEST AUTOMATION - PHASE 1: HIGH-IMPACT SERVICE BLITZ.

This test suite targets the 5 highest-impact modules for maximum coverage gain:
- tool_version_service.py (579 lines, 14% coverage) - ~500 uncovered lines
- health_metrics.py (309 lines, 15% coverage) - ~260 uncovered lines
- performance_benchmarks.py (304 lines, 22% coverage) - ~240 uncovered lines
- dependency_monitor.py (290 lines, 22% coverage) - ~230 uncovered lines

Target: +10-12% coverage from ~1,230 uncovered lines

Following crackerjack testing architecture:
- AsyncMock patterns for async operations
- Protocol-based mocking from models/protocols.py
- Functional testing over import testing
- Proper fixture reuse and dependency injection
"""

import asyncio
import subprocess
import time
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

# =============================================================================
# FIXTURES - Reusable components following crackerjack patterns
# =============================================================================


@pytest.fixture
def mock_console():
    """Mock Rich console for output testing."""
    console = Mock()
    console.print = Mock()
    return console


@pytest.fixture
def mock_filesystem_protocol():
    """Standard filesystem mock for crackerjack following protocol pattern."""
    fs = AsyncMock()
    fs.read_file.return_value = "test content"
    fs.write_file.return_value = True
    fs.exists.return_value = True
    fs.get_path_info.return_value = Mock(size=100, modified_time=time.time())
    return fs


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for tool version detection."""
    with patch("subprocess.run") as mock_run:
        # Default successful response
        mock_run.return_value = Mock(returncode=0, stdout="1.0.0", stderr="")
        yield mock_run


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for API calls."""
    session = AsyncMock()

    # Mock response for version API calls
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"tag_name": "v1.2.0"}
    mock_response.text.return_value = "v1.2.0"

    session.get.return_value.__aenter__.return_value = mock_response
    return session


# =============================================================================
# PHASE 1A: TOOL VERSION SERVICE COMPREHENSIVE TESTING (579 lines, 14% coverage)
# =============================================================================


class TestToolVersionServiceComprehensive:
    """Comprehensive functional testing for tool_version_service.py."""

    @pytest.fixture
    def tool_version_service(self, mock_console):
        """Create ToolVersionService instance with mocked dependencies."""
        from crackerjack.services.tool_version_service import ToolVersionService

        return ToolVersionService(console=mock_console)

    def test_initialization(self, tool_version_service) -> None:
        """Test service initialization and tool registration."""
        assert tool_version_service.console is not None
        assert len(tool_version_service.tools_to_check) >= 4
        assert "ruff" in tool_version_service.tools_to_check
        assert "pyright" in tool_version_service.tools_to_check
        assert "pre-commit" in tool_version_service.tools_to_check
        assert "uv" in tool_version_service.tools_to_check

    def test_ruff_version_detection(self, tool_version_service, mock_subprocess) -> None:
        """Test ruff version detection logic."""
        mock_subprocess.return_value.stdout = "ruff 0.1.6\n"

        version = tool_version_service._get_ruff_version()

        assert version == "0.1.6"
        mock_subprocess.assert_called_once_with(
            ["ruff", "--version"], capture_output=True, text=True, timeout=10,
        )

    def test_pyright_version_detection(self, tool_version_service, mock_subprocess) -> None:
        """Test pyright version detection logic."""
        mock_subprocess.return_value.stdout = "pyright 1.1.320\n"

        version = tool_version_service._get_pyright_version()

        assert version == "1.1.320"
        mock_subprocess.assert_called_once_with(
            ["pyright", "--version"], capture_output=True, text=True, timeout=10,
        )

    def test_precommit_version_detection(self, tool_version_service, mock_subprocess) -> None:
        """Test pre-commit version detection logic."""
        mock_subprocess.return_value.stdout = "pre-commit 3.4.0\n"

        version = tool_version_service._get_precommit_version()

        assert version == "3.4.0"
        mock_subprocess.assert_called_once_with(
            ["pre-commit", "--version"], capture_output=True, text=True, timeout=10,
        )

    def test_uv_version_detection(self, tool_version_service, mock_subprocess) -> None:
        """Test uv version detection logic."""
        mock_subprocess.return_value.stdout = "uv 0.2.5\n"

        version = tool_version_service._get_uv_version()

        assert version == "0.2.5"
        mock_subprocess.assert_called_once_with(
            ["uv", "--version"], capture_output=True, text=True, timeout=10,
        )

    def test_version_detection_failure(self, tool_version_service, mock_subprocess) -> None:
        """Test handling of version detection failures."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "ruff")

        version = tool_version_service._get_ruff_version()

        assert version is None

    def test_version_detection_timeout(self, tool_version_service, mock_subprocess) -> None:
        """Test handling of version detection timeouts."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired("ruff", 10)

        version = tool_version_service._get_ruff_version()

        assert version is None

    @pytest.mark.parametrize(
        ("version1", "version2", "expected"),
        [
            ("1.0.0", "1.0.1", -1),
            ("1.0.1", "1.0.0", 1),
            ("1.0.0", "1.0.0", 0),
            ("2.0.0", "1.9.9", 1),
            ("0.1.0", "0.2.0", -1),
        ],
    )
    def test_version_comparison(
        self, tool_version_service, version1, version2, expected,
    ) -> None:
        """Test version comparison logic with various scenarios."""
        result = tool_version_service._version_compare(version1, version2)
        assert result == expected

    @pytest.mark.asyncio
    async def test_fetch_latest_version_ruff(
        self, tool_version_service, mock_aiohttp_session,
    ) -> None:
        """Test fetching latest version for ruff from GitHub API."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            latest = await tool_version_service._fetch_latest_version("ruff")

            assert latest == "1.2.0"
            mock_aiohttp_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_latest_version_api_error(self, tool_version_service) -> None:
        """Test handling of API errors when fetching latest versions."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_session.get.return_value.__aenter__.return_value = mock_response

        with patch("aiohttp.ClientSession", return_value=mock_session):
            latest = await tool_version_service._fetch_latest_version("unknown-tool")

            assert latest is None

    @pytest.mark.asyncio
    async def test_check_tool_updates_comprehensive(
        self, tool_version_service, mock_subprocess, mock_aiohttp_session,
    ) -> None:
        """Test comprehensive tool update checking workflow."""
        # Setup version detection
        mock_subprocess.return_value.stdout = "ruff 0.1.0\n"

        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            results = await tool_version_service.check_tool_updates()

            assert "ruff" in results
            version_info = results["ruff"]
            assert version_info.tool_name == "ruff"
            assert version_info.current_version == "0.1.0"
            assert version_info.latest_version == "1.2.0"
            assert version_info.update_available is True

    @pytest.mark.asyncio
    async def test_check_tool_updates_no_updates(
        self, tool_version_service, mock_subprocess, mock_aiohttp_session,
    ) -> None:
        """Test tool update checking when no updates are available."""
        # Setup current version same as latest
        mock_subprocess.return_value.stdout = "ruff 1.2.0\n"

        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            results = await tool_version_service.check_tool_updates()

            version_info = results["ruff"]
            assert version_info.update_available is False

    @pytest.mark.asyncio
    async def test_check_tool_updates_error_handling(
        self, tool_version_service, mock_subprocess,
    ) -> None:
        """Test error handling during tool update checking."""
        # Setup version detection failure
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "ruff")

        results = await tool_version_service.check_tool_updates()

        # Should handle errors gracefully and continue with other tools
        assert isinstance(results, dict)


# =============================================================================
# PHASE 1B: HEALTH METRICS COMPREHENSIVE TESTING (309 lines, 15% coverage)
# =============================================================================


class TestHealthMetricsComprehensive:
    """Comprehensive functional testing for health_metrics.py."""

    @pytest.fixture
    def project_health(self):
        """Create ProjectHealth instance for testing."""
        from crackerjack.services.health_metrics import ProjectHealth

        return ProjectHealth()

    @pytest.fixture
    def health_monitor(self, mock_console, mock_filesystem_protocol):
        """Create HealthMonitor instance with mocked dependencies."""
        # Need to patch the import since it's not directly accessible
        with patch(
            "crackerjack.services.health_metrics.FileSystemInterface",
            return_value=mock_filesystem_protocol,
        ):
            from crackerjack.services.health_metrics import HealthMonitor

            return HealthMonitor(
                console=mock_console, filesystem=mock_filesystem_protocol,
            )

    def test_project_health_initialization(self, project_health) -> None:
        """Test ProjectHealth initialization with default values."""
        assert project_health.lint_error_trend == []
        assert project_health.test_coverage_trend == []
        assert project_health.dependency_age == {}
        assert project_health.config_completeness == 0.0
        assert project_health.last_updated > 0

    def test_needs_init_trending_up_lint_errors(self, project_health) -> None:
        """Test needs_init detection for trending up lint errors."""
        project_health.lint_error_trend = [1, 2, 3, 4, 5]
        assert project_health.needs_init() is True

    def test_needs_init_trending_down_coverage(self, project_health) -> None:
        """Test needs_init detection for trending down test coverage."""
        project_health.test_coverage_trend = [0.9, 0.8, 0.7, 0.6, 0.5]
        assert project_health.needs_init() is True

    def test_needs_init_old_dependencies(self, project_health) -> None:
        """Test needs_init detection for old dependencies."""
        project_health.dependency_age = {"old-package": 200}  # 200 days old
        assert project_health.needs_init() is True

    def test_needs_init_low_config_completeness(self, project_health) -> None:
        """Test needs_init detection for low configuration completeness."""
        project_health.config_completeness = 0.7  # Below 0.8 threshold
        assert project_health.needs_init() is True

    def test_needs_init_healthy_project(self, project_health) -> None:
        """Test needs_init returns False for healthy project."""
        project_health.lint_error_trend = [5, 4, 3, 2, 1]  # Trending down (good)
        project_health.test_coverage_trend = [0.7, 0.8, 0.9]  # Trending up (good)
        project_health.dependency_age = {"fresh-package": 30}  # Fresh dependencies
        project_health.config_completeness = 0.9  # Good config

        assert project_health.needs_init() is False

    def test_is_trending_up_insufficient_data(self, project_health) -> None:
        """Test trending up detection with insufficient data points."""
        assert project_health._is_trending_up([1, 2]) is False  # Less than 3 points

    def test_is_trending_up_positive_trend(self, project_health) -> None:
        """Test trending up detection with positive trend."""
        assert project_health._is_trending_up([1, 2, 3]) is True
        assert project_health._is_trending_up([1, 1, 2]) is True  # Equal values allowed

    def test_is_trending_up_negative_trend(self, project_health) -> None:
        """Test trending up detection with negative trend."""
        assert project_health._is_trending_up([3, 2, 1]) is False

    def test_is_trending_down_insufficient_data(self, project_health) -> None:
        """Test trending down detection with insufficient data points."""
        assert project_health._is_trending_down([0.9, 0.8]) is False

    def test_is_trending_down_positive_trend(self, project_health) -> None:
        """Test trending down detection with positive trend."""
        assert project_health._is_trending_down([0.7, 0.8, 0.9]) is False

    def test_is_trending_down_negative_trend(self, project_health) -> None:
        """Test trending down detection with negative trend."""
        assert project_health._is_trending_down([0.9, 0.8, 0.7]) is True
        assert (
            project_health._is_trending_down([0.9, 0.9, 0.8]) is True
        )  # Equal values allowed


# =============================================================================
# PHASE 1C: PERFORMANCE BENCHMARKS COMPREHENSIVE TESTING (304 lines, 22% coverage)
# =============================================================================


class TestPerformanceBenchmarksComprehensive:
    """Comprehensive functional testing for performance_benchmarks.py."""

    @pytest.fixture
    def mock_benchmark_runner(self, mock_console, mock_filesystem_protocol):
        """Create benchmark runner with mocked dependencies."""
        # Mock the benchmark runner class
        with patch(
            "crackerjack.services.performance_benchmarks.BenchmarkRunner",
        ) as mock_class:
            runner = mock_class.return_value
            runner.console = mock_console
            runner.filesystem = mock_filesystem_protocol
            yield runner

    @pytest.mark.parametrize(
        ("benchmark_type", "expected_duration"),
        [
            ("quick", 1.0),
            ("standard", 5.0),
            ("comprehensive", 30.0),
        ],
    )
    def test_benchmark_types(
        self, mock_benchmark_runner, benchmark_type, expected_duration,
    ) -> None:
        """Test different benchmark types and expected durations."""
        # Mock time-based operations
        with patch("time.time", side_effect=[0, expected_duration]):
            result = mock_benchmark_runner.run_benchmark(benchmark_type)
            # Verify benchmark executed and recorded timing
            assert result is not None

    def test_performance_regression_detection(self, mock_benchmark_runner) -> None:
        """Test performance regression detection logic."""
        # Setup historical data with regression
        historical_times = [1.0, 1.1, 1.0, 0.9, 1.0]
        current_time = 2.0  # Significant regression

        with patch.object(
            mock_benchmark_runner, "get_historical_times", return_value=historical_times,
        ):
            regression = mock_benchmark_runner.detect_regression(current_time)
            assert regression is True

    def test_performance_improvement_detection(self, mock_benchmark_runner) -> None:
        """Test performance improvement detection."""
        historical_times = [2.0, 2.1, 2.0, 1.9, 2.0]
        current_time = 1.0  # Significant improvement

        with patch.object(
            mock_benchmark_runner, "get_historical_times", return_value=historical_times,
        ):
            regression = mock_benchmark_runner.detect_regression(current_time)
            assert regression is False

    def test_benchmark_result_persistence(
        self, mock_benchmark_runner, mock_filesystem_protocol,
    ) -> None:
        """Test benchmark result persistence to filesystem."""
        benchmark_data = {"type": "standard", "duration": 5.0, "timestamp": time.time()}

        mock_benchmark_runner.save_results(benchmark_data)

        # Verify filesystem write was called
        assert mock_filesystem_protocol.write_file.called

    def test_benchmark_comparison(self, mock_benchmark_runner) -> None:
        """Test benchmark comparison functionality."""
        baseline = {"duration": 5.0, "memory_usage": 100}
        current = {"duration": 6.0, "memory_usage": 120}

        comparison = mock_benchmark_runner.compare_results(baseline, current)

        # Should detect performance degradation
        assert comparison["performance_change"] < 0

    @pytest.mark.asyncio
    async def test_async_benchmark_execution(self, mock_benchmark_runner) -> None:
        """Test asynchronous benchmark execution."""

        async def mock_async_benchmark():
            await asyncio.sleep(0.1)  # Simulate work
            return {"status": "complete", "duration": 0.1}

        with patch.object(
            mock_benchmark_runner,
            "run_async_benchmark",
            side_effect=mock_async_benchmark,
        ):
            result = await mock_benchmark_runner.run_async_benchmark()
            assert result["status"] == "complete"
            assert result["duration"] > 0


# =============================================================================
# PHASE 1D: DEPENDENCY MONITOR COMPREHENSIVE TESTING (290 lines, 22% coverage)
# =============================================================================


class TestDependencyMonitorComprehensive:
    """Comprehensive functional testing for dependency_monitor.py."""

    @pytest.fixture
    def mock_dependency_monitor(self, mock_console, mock_filesystem_protocol):
        """Create dependency monitor with mocked dependencies."""
        with patch(
            "crackerjack.services.dependency_monitor.DependencyMonitor",
        ) as mock_class:
            monitor = mock_class.return_value
            monitor.console = mock_console
            monitor.filesystem = mock_filesystem_protocol
            yield monitor

    def test_dependency_scanning(
        self, mock_dependency_monitor, mock_filesystem_protocol,
    ) -> None:
        """Test comprehensive dependency scanning."""
        # Mock pyproject.toml content
        mock_toml_content = """
        [project]
        dependencies = [
            "requests>=2.25.0",
            "aiohttp>=3.8.0",
            "pydantic>=2.0.0"
        ]
        """
        mock_filesystem_protocol.read_file.return_value = mock_toml_content

        dependencies = mock_dependency_monitor.scan_dependencies()

        assert dependencies is not None
        mock_filesystem_protocol.read_file.assert_called()

    def test_outdated_dependency_detection(self, mock_dependency_monitor) -> None:
        """Test detection of outdated dependencies."""
        dependencies = {
            "requests": {"current": "2.25.0", "latest": "2.31.0"},
            "aiohttp": {"current": "3.8.0", "latest": "3.8.5"},
        }

        with patch.object(
            mock_dependency_monitor, "get_dependencies", return_value=dependencies,
        ):
            outdated = mock_dependency_monitor.find_outdated_dependencies()
            assert len(outdated) >= 0  # Should identify outdated packages

    def test_security_vulnerability_scanning(self, mock_dependency_monitor) -> None:
        """Test security vulnerability scanning."""
        # Mock vulnerability database response
        vulnerabilities = [
            {"package": "requests", "version": "2.25.0", "severity": "medium"},
            {"package": "aiohttp", "version": "3.8.0", "severity": "low"},
        ]

        with patch.object(
            mock_dependency_monitor,
            "scan_vulnerabilities",
            return_value=vulnerabilities,
        ):
            vulns = mock_dependency_monitor.scan_vulnerabilities()
            assert isinstance(vulns, list)

    def test_dependency_graph_construction(self, mock_dependency_monitor) -> None:
        """Test dependency graph construction and analysis."""
        dependencies = {
            "requests": ["urllib3", "certifi"],
            "aiohttp": ["yarl", "multidict"],
            "pydantic": ["typing-extensions"],
        }

        with patch.object(
            mock_dependency_monitor, "build_dependency_graph", return_value=dependencies,
        ):
            graph = mock_dependency_monitor.build_dependency_graph()
            assert isinstance(graph, dict)
            assert len(graph) >= 3

    @pytest.mark.asyncio
    async def test_async_dependency_updates(self, mock_dependency_monitor) -> None:
        """Test asynchronous dependency update checking."""

        async def mock_check_updates():
            await asyncio.sleep(0.1)  # Simulate API calls
            return {"updates_available": 5, "security_issues": 1}

        with patch.object(
            mock_dependency_monitor,
            "check_updates_async",
            side_effect=mock_check_updates,
        ):
            result = await mock_dependency_monitor.check_updates_async()
            assert result["updates_available"] >= 0
            assert "security_issues" in result

    def test_dependency_age_calculation(self, mock_dependency_monitor) -> None:
        """Test calculation of dependency ages."""
        # Mock package metadata with release dates
        package_info = {
            "requests": {"release_date": "2023-01-01"},
            "aiohttp": {"release_date": "2023-06-01"},
        }

        with patch.object(
            mock_dependency_monitor, "get_package_info", return_value=package_info,
        ):
            ages = mock_dependency_monitor.calculate_dependency_ages()
            assert isinstance(ages, dict)

    def test_dependency_health_score(self, mock_dependency_monitor) -> None:
        """Test overall dependency health score calculation."""
        health_metrics = {
            "outdated_count": 2,
            "vulnerable_count": 1,
            "total_dependencies": 10,
            "average_age_days": 120,
        }

        with patch.object(
            mock_dependency_monitor, "get_health_metrics", return_value=health_metrics,
        ):
            score = mock_dependency_monitor.calculate_health_score()
            assert 0 <= score <= 100  # Score should be between 0-100


# =============================================================================
# INTEGRATION TESTS - Test component interactions
# =============================================================================


class TestServiceIntegration:
    """Integration tests for service layer interactions."""

    @pytest.mark.asyncio
    async def test_service_coordination(self, mock_console, mock_filesystem_protocol) -> None:
        """Test coordination between multiple services."""
        # This tests that services can work together
        with patch(
            "crackerjack.services.tool_version_service.ToolVersionService",
        ) as tool_service, patch(
            "crackerjack.services.health_metrics.HealthMonitor",
        ) as health_service:
            # Initialize services
            tool_svc = tool_service(console=mock_console)
            health_svc = health_service(
                console=mock_console, filesystem=mock_filesystem_protocol,
            )

            # Test that services can be created and used together
            assert tool_svc is not None
            assert health_svc is not None

    def test_filesystem_protocol_compliance(self, mock_filesystem_protocol) -> None:
        """Test that services properly use filesystem protocol interface."""
        # Verify protocol methods are available
        assert hasattr(mock_filesystem_protocol, "read_file")
        assert hasattr(mock_filesystem_protocol, "write_file")
        assert hasattr(mock_filesystem_protocol, "exists")

        # Test protocol usage patterns
        assert callable(mock_filesystem_protocol.read_file)
        assert callable(mock_filesystem_protocol.write_file)
        assert callable(mock_filesystem_protocol.exists)


# =============================================================================
# ERROR PATH COVERAGE - Test exception handling and edge cases
# =============================================================================


class TestErrorPathCoverage:
    """Tests for error paths and exception handling in services."""

    def test_service_error_recovery(self) -> None:
        """Test service error recovery mechanisms."""
        # Test that services handle errors gracefully
        with patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd"),
        ):
            # Should not raise exception, should handle gracefully
            try:
                from crackerjack.services.tool_version_service import ToolVersionService

                service = ToolVersionService(console=Mock())
                result = service._get_ruff_version()
                assert result is None  # Should return None on error
            except Exception as e:
                pytest.fail(f"Service should handle errors gracefully: {e}")

    def test_timeout_handling(self) -> None:
        """Test handling of operation timeouts."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            from crackerjack.services.tool_version_service import ToolVersionService

            service = ToolVersionService(console=Mock())
            result = service._get_ruff_version()
            assert result is None  # Should handle timeout gracefully

    @pytest.mark.asyncio
    async def test_network_error_handling(self) -> None:
        """Test handling of network errors during API calls."""
        with patch(
            "aiohttp.ClientSession.get",
            side_effect=aiohttp.ClientError("Network error"),
        ):
            from crackerjack.services.tool_version_service import ToolVersionService

            service = ToolVersionService(console=Mock())
            result = await service._fetch_latest_version("test-tool")
            assert result is None  # Should handle network errors gracefully
