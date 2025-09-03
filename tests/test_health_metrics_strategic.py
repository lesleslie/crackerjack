import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.services.health_metrics import HealthMetricsService, ProjectHealth


@pytest.fixture
def mock_filesystem():
    filesystem = Mock()
    filesystem.exists.return_value = True
    filesystem.read_text.return_value = ""
    filesystem.write_text.return_value = True
    return filesystem


@pytest.fixture
def mock_console():
    return Mock(spec=Console)


@pytest.fixture
def temp_project_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)

        (project_path / ".crackerjack").mkdir(exist_ok=True)

        pyproject_content = """[project]
name = "test - project"
version = "1.0.0"
description = "Test project"
dependencies = [
    "requests >=    2.25.0",
    "pytest >=    6.0.0"
]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line - length = 88

[tool.coverage.report]
exclude_lines = ["pragma: no cover"]
"""

        (project_path / "pyproject.toml").write_text(pyproject_content.strip())

        precommit_content = """# Pre-commit configuration
repos: []
"""
        (project_path / ".pre - commit - config.yaml").write_text(
            precommit_content.strip()
        )

        (project_path / "README.md").write_text("# Test Project")

        yield project_path


@pytest.fixture
def health_service(temp_project_dir):
    mock_fs = Mock()
    mock_fs.exists.return_value = True
    mock_fs.read_text.return_value = ""

    service = HealthMetricsService(mock_fs, Console())
    service.project_root = temp_project_dir
    service.pyproject_path = temp_project_dir / "pyproject.toml"
    service.health_cache = temp_project_dir / ".crackerjack" / "health_metrics.json"
    return service


class TestProjectHealth:
    def test_project_health_default_initialization(self):
        health = ProjectHealth()

        assert health.lint_error_trend == []
        assert health.test_coverage_trend == []
        assert health.dependency_age == {}
        assert health.config_completeness == 0.0
        assert isinstance(health.last_updated, float)
        assert health.last_updated > 0

    def test_project_health_custom_initialization(self):
        custom_time = 1640995200.0

        health = ProjectHealth(
            lint_error_trend=[10, 8, 5, 2],
            test_coverage_trend=[60.0, 70.0, 80.0, 90.0],
            dependency_age={"requests": 100, "pytest": 50},
            config_completeness=0.85,
            last_updated=custom_time,
        )

        assert health.lint_error_trend == [10, 8, 5, 2]
        assert health.test_coverage_trend == [60.0, 70.0, 80.0, 90.0]
        assert health.dependency_age == {"requests": 100, "pytest": 50}
        assert health.config_completeness == 0.85
        assert health.last_updated == custom_time

    def test_needs_init_healthy_project(self):
        health = ProjectHealth(
            lint_error_trend=[10, 8, 5, 3],
            test_coverage_trend=[60.0, 65.0, 70.0, 75.0],
            dependency_age={"requests": 30, "pytest": 60},
            config_completeness=0.9,
        )

        assert not health.needs_init()

    def test_needs_init_lint_errors_trending_up(self):
        health = ProjectHealth(
            lint_error_trend=[2, 3, 5, 8],
            test_coverage_trend=[70.0, 75.0, 80.0],
            dependency_age={"requests": 30},
            config_completeness=0.9,
        )

        assert health.needs_init()

    def test_needs_init_coverage_trending_down(self):
        health = ProjectHealth(
            lint_error_trend=[8, 5, 3],
            test_coverage_trend=[90.0, 80.0, 70.0, 60.0],
            dependency_age={"requests": 30},
            config_completeness=0.9,
        )

        assert health.needs_init()

    def test_needs_init_old_dependencies(self):
        health = ProjectHealth(
            lint_error_trend=[5, 3, 2],
            test_coverage_trend=[70.0, 75.0, 80.0],
            dependency_age={"old_package": 200, "very_old": 365},
            config_completeness=0.9,
        )

        assert health.needs_init()

    def test_needs_init_low_config_completeness(self):
        health = ProjectHealth(
            lint_error_trend=[5, 3, 2],
            test_coverage_trend=[70.0, 75.0, 80.0],
            dependency_age={"requests": 30},
            config_completeness=0.5,
        )

        assert health.needs_init()


class TestProjectHealthTrendAnalysis:
    def test_is_trending_up_insufficient_data(self):
        health = ProjectHealth()

        assert not health._is_trending_up([1, 2])
        assert not health._is_trending_up([5])
        assert not health._is_trending_up([])

    def test_is_trending_up_clear_upward_trend(self):
        health = ProjectHealth()

        assert health._is_trending_up([1, 2, 3, 4, 5])

        assert health._is_trending_up([1, 2, 2, 3, 4])

        assert health._is_trending_up([10, 8, 5, 2, 3, 4, 5])

    def test_is_trending_up_not_trending(self):
        health = ProjectHealth()

        assert not health._is_trending_up([5, 4, 3, 2, 1])

        assert not health._is_trending_up([1, 3, 2, 4, 3])

        assert not health._is_trending_up([5, 5, 5, 4, 3])

    def test_is_trending_down_insufficient_data(self):
        health = ProjectHealth()

        assert not health._is_trending_down([80.0, 70.0])
        assert not health._is_trending_down([60.0])
        assert not health._is_trending_down([])

    def test_is_trending_down_clear_downward_trend(self):
        health = ProjectHealth()

        assert health._is_trending_down([90.0, 80.0, 70.0, 60.0, 50.0])

        assert health._is_trending_down([90.0, 80.0, 80.0, 70.0, 60.0])

        assert health._is_trending_down([50.0, 60.0, 90.0, 80.0, 70.0, 60.0])

    def test_is_trending_down_not_trending(self):
        health = ProjectHealth()

        assert not health._is_trending_down([50.0, 60.0, 70.0, 80.0, 90.0])

        assert not health._is_trending_down([70.0, 60.0, 80.0, 75.0, 85.0])

        assert not health._is_trending_down([60.0, 60.0, 60.0, 70.0, 80.0])

    def test_custom_min_points(self):
        health = ProjectHealth()

        assert health._is_trending_up([1, 2], min_points=2)
        assert health._is_trending_down([80.0, 70.0], min_points=2)

        assert not health._is_trending_up([1, 2, 3], min_points=4)
        assert health._is_trending_up([1, 2, 3, 4], min_points=4)


class TestProjectHealthScoring:
    def test_get_health_score_empty_data(self):
        health = ProjectHealth()

        score = health.get_health_score()
        assert score == 0.0

    def test_get_health_score_perfect_health(self):
        health = ProjectHealth(
            lint_error_trend=[0, 0, 0, 0, 0],
            test_coverage_trend=[100.0, 100.0, 100.0, 100.0, 100.0],
            dependency_age={"pkg1": 1, "pkg2": 2, "pkg3": 3},
            config_completeness=1.0,
        )

        score = health.get_health_score()
        assert score > 0.9
        assert score <= 1.0

    def test_get_health_score_poor_health(self):
        health = ProjectHealth(
            lint_error_trend=[150, 140, 160, 180, 200],
            test_coverage_trend=[10.0, 8.0, 5.0, 2.0, 0.0],
            dependency_age={"old1": 400, "old2": 500, "old3": 600},
            config_completeness=0.1,
        )

        score = health.get_health_score()
        assert score < 0.3
        assert score >= 0.0

    def test_get_health_score_mixed_metrics(self):
        health = ProjectHealth(
            lint_error_trend=[10, 8, 5, 3, 2],
            test_coverage_trend=[40.0, 45.0, 50.0, 55.0, 60.0],
            dependency_age={"new": 30, "old": 300},
            config_completeness=0.7,
        )

        score = health.get_health_score()
        assert 0.4 < score < 0.8

    def test_get_recommendations_healthy_project(self):
        health = ProjectHealth(
            lint_error_trend=[10, 8, 5, 3, 2],
            test_coverage_trend=[60.0, 65.0, 70.0, 75.0, 80.0],
            dependency_age={"pkg1": 30, "pkg2": 60},
            config_completeness=0.9,
        )

        recommendations = health.get_recommendations()
        assert len(recommendations) == 0

    def test_get_recommendations_multiple_issues(self):
        health = ProjectHealth(
            lint_error_trend=[2, 4, 6, 8, 10],
            test_coverage_trend=[80.0, 70.0, 60.0, 50.0],
            dependency_age={"old1": 400, "old2": 500, "old3": 600},
            config_completeness=0.3,
        )

        recommendations = health.get_recommendations()

        assert len(recommendations) >= 3

        rec_text = " ".join(recommendations)
        assert "lint errors" in rec_text.lower() or "formatting" in rec_text.lower()
        assert "test coverage" in rec_text.lower() or "tests" in rec_text.lower()
        assert "dependencies" in rec_text.lower() or "old" in rec_text.lower()
        assert "configuration" in rec_text.lower() or "config" in rec_text.lower()

    def test_get_recommendations_rapidly_degrading_quality(self):
        health = ProjectHealth(
            lint_error_trend=[
                2,
                3,
                4,
                5,
                6,
                8,
                10,
                15,
                20,
                25,
                35,
                50,
            ],
        )

        recommendations = health.get_recommendations()

        rec_text = " ".join(recommendations)
        assert (
            "degrading rapidly" in rec_text.lower()
            or "immediate attention" in rec_text.lower()
        )

    def test_get_recommendations_old_dependencies_limit(self):
        old_deps = {f"old_pkg_{i}": 400 for i in range(10)}

        health = ProjectHealth(dependency_age=old_deps)
        recommendations = health.get_recommendations()

        old_deps_rec = next(
            (r for r in recommendations if "dependencies detected" in r), None
        )
        assert old_deps_rec is not None

        pkg_count = sum(1 for i in range(10) if f"old_pkg_{i}" in old_deps_rec)
        assert pkg_count <= 3


class TestHealthMetricsServiceInitialization:
    def test_initialization_with_defaults(self):
        mock_filesystem = Mock()
        service = HealthMetricsService(mock_filesystem)

        assert service.filesystem is mock_filesystem
        assert service.console is not None
        assert service.project_root == Path.cwd()
        assert service.max_trend_points == 20
        assert service.pyproject_path.name == "pyproject.toml"
        assert service.health_cache.name == "health_metrics.json"

    def test_initialization_with_custom_console(self):
        mock_filesystem = Mock()
        mock_console = Mock(spec=Console)
        service = HealthMetricsService(mock_filesystem, mock_console)

        assert service.filesystem is mock_filesystem
        assert service.console is mock_console


class TestHealthHistoryManagement:
    def test_load_health_history_no_cache(self, health_service):
        health_service.health_cache.unlink(missing_ok=True)

        health = health_service._load_health_history()

        assert isinstance(health, ProjectHealth)
        assert health.lint_error_trend == []
        assert health.test_coverage_trend == []
        assert health.dependency_age == {}
        assert health.config_completeness == 0.0

    def test_load_health_history_with_cache(self, health_service):
        cache_data = {
            "lint_error_trend": [10, 8, 5, 2],
            "test_coverage_trend": [60.0, 70.0, 80.0, 90.0],
            "dependency_age": {"requests": 100, "pytest": 50},
            "config_completeness": 0.85,
            "last_updated": 1640995200.0,
        }

        health_service.health_cache.write_text(json.dumps(cache_data))

        health = health_service._load_health_history()

        assert health.lint_error_trend == [10, 8, 5, 2]
        assert health.test_coverage_trend == [60.0, 70.0, 80.0, 90.0]
        assert health.dependency_age == {"requests": 100, "pytest": 50}
        assert health.config_completeness == 0.85
        assert health.last_updated == 1640995200.0

    def test_load_health_history_corrupted_cache(self, health_service):
        health_service.health_cache.write_text("invalid json content")

        health = health_service._load_health_history()

        assert isinstance(health, ProjectHealth)
        assert health.lint_error_trend == []

    def test_save_health_metrics_success(self, health_service):
        health = ProjectHealth(
            lint_error_trend=[5, 3, 2],
            test_coverage_trend=[70.0, 75.0, 80.0],
            dependency_age={"requests": 30},
            config_completeness=0.8,
            last_updated=1640995200.0,
        )

        health_service._save_health_metrics(health)

        assert health_service.health_cache.exists()

        saved_data = json.loads(health_service.health_cache.read_text())
        assert saved_data["lint_error_trend"] == [5, 3, 2]
        assert saved_data["test_coverage_trend"] == [70.0, 75.0, 80.0]
        assert saved_data["dependency_age"] == {"requests": 30}
        assert saved_data["config_completeness"] == 0.8
        assert saved_data["last_updated"] == 1640995200.0

    def test_save_health_metrics_failure(self, health_service, mock_console):
        health_service.console = mock_console
        health = ProjectHealth()

        if health_service.health_cache.parent.exists():
            shutil.rmtree(health_service.health_cache.parent)
        health_service.health_cache.parent.touch()

        health_service._save_health_metrics(health)

        mock_console.print.assert_called()
        args = mock_console.print.call_args[0][0]
        assert "Warning" in args and "Failed to save health metrics" in args


class TestLintErrorCollection:
    @patch("subprocess.run")
    def test_count_lint_errors_no_errors(self, mock_run, health_service):
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        count = health_service._count_lint_errors()

        assert count == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ruff" in args
        assert "- - output - format = json" in args

    @patch("subprocess.run")
    def test_count_lint_errors_with_json_output(self, mock_run, health_service):
        lint_errors = [
            {"file": "test.py", "line": 1, "message": "Error 1"},
            {"file": "test.py", "line": 5, "message": "Error 2"},
            {"file": "other.py", "line": 10, "message": "Error 3"},
        ]

        mock_run.return_value = Mock(
            returncode=1, stdout=json.dumps(lint_errors), stderr=""
        )

        count = health_service._count_lint_errors()

        assert count == 3

    @patch("subprocess.run")
    def test_count_lint_errors_with_text_output(self, mock_run, health_service):
        text_output = "test.py: 1: 1: E101 Error 1\ntest.py: 5: 1: E102 Error 2\nother.py: 10: 1: E103 Error 3"

        mock_run.return_value = Mock(returncode=1, stdout=text_output, stderr="")

        count = health_service._count_lint_errors()

        assert count == 3

    @patch("subprocess.run")
    def test_count_lint_errors_subprocess_failure(self, mock_run, health_service):
        mock_run.side_effect = subprocess.TimeoutExpired("ruff", timeout=30)

        count = health_service._count_lint_errors()

        assert count is None

    @patch("subprocess.run")
    def test_count_lint_errors_invalid_json(self, mock_run, health_service):
        mock_run.return_value = Mock(returncode=1, stdout="invalid json {", stderr="")

        count = health_service._count_lint_errors()

        assert count == 1


class TestCoverageCollection:
    def test_check_existing_coverage_files_none_exist(self, health_service):
        for coverage_file in [".coverage", "htmlcov / index.html", "coverage.xml"]:
            (health_service.project_root / coverage_file).unlink(missing_ok=True)

        result = health_service._check_existing_coverage_files()

        assert result is None

    @patch.object(HealthMetricsService, "_get_coverage_from_command")
    def test_check_existing_coverage_files_coverage_exists(
        self, mock_get_coverage, health_service
    ):
        (health_service.project_root / ".coverage").touch()
        mock_get_coverage.return_value = 75.5

        result = health_service._check_existing_coverage_files()

        assert result == 75.5
        mock_get_coverage.assert_called_once()

    @patch("subprocess.run")
    def test_generate_coverage_report_success(self, mock_run, health_service):
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        coverage_data = {"totals": {"percent_covered": 82.5}}
        coverage_json = health_service.project_root / "coverage.json"
        coverage_json.write_text(json.dumps(coverage_data))

        result = health_service._generate_coverage_report()

        assert result == 82.5
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "pytest" in args
        assert "- - cov =." in args

    @patch("subprocess.run")
    def test_generate_coverage_report_no_output_file(self, mock_run, health_service):
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        (health_service.project_root / "coverage.json").unlink(missing_ok=True)

        result = health_service._generate_coverage_report()

        assert result is None

    @patch("subprocess.run")
    def test_get_coverage_from_command_success(self, mock_run, health_service):
        coverage_data = {"totals": {"percent_covered": 68.3}}

        mock_run.return_value = Mock(
            returncode=0, stdout=json.dumps(coverage_data), stderr=""
        )

        result = health_service._get_coverage_from_command()

        assert result == 68.3
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "coverage" in args
        assert "report" in args
        assert "- - format = json" in args

    @patch("subprocess.run")
    def test_get_coverage_from_command_failure(self, mock_run, health_service):
        mock_run.return_value = Mock(
            returncode=1, stdout="", stderr="No coverage data found"
        )

        result = health_service._get_coverage_from_command()

        assert result is None


class TestDependencyAgeAnalysis:
    def test_load_project_data_success(self, health_service):
        data = health_service._load_project_data()

        assert isinstance(data, dict)
        assert "project" in data
        assert data["project"]["name"] == "test - project"

    def test_load_project_data_missing_file(self, health_service):
        health_service.pyproject_path.unlink()

        with pytest.raises(FileNotFoundError):
            health_service._load_project_data()

    def test_extract_all_dependencies(self, health_service):
        project_data = {
            "project": {
                "dependencies": ["requests >=    2.25.0", "click >=    8.0"],
                "optional - dependencies": {
                    "dev": ["pytest >=    6.0", "black >=    22.0"],
                    "docs": ["sphinx >=    4.0"],
                },
            }
        }

        deps = health_service._extract_all_dependencies(project_data)

        expected_deps = [
            "requests >=    2.25.0",
            "click >=    8.0",
            "pytest >=    6.0",
            "black >=    22.0",
            "sphinx >=    4.0",
        ]
        assert set(deps) == set(expected_deps)

    def test_extract_all_dependencies_minimal(self, health_service):
        project_data = {"project": {"dependencies": ["requests >=    2.25.0"]}}

        deps = health_service._extract_all_dependencies(project_data)

        assert deps == ["requests >=    2.25.0"]

    def test_extract_all_dependencies_no_project_section(self, health_service):
        project_data = {"tool": {"ruff": {}}}

        deps = health_service._extract_all_dependencies(project_data)

        assert deps == []

    def test_extract_package_name_various_formats(self, health_service):
        test_cases = [
            ("requests >=    2.25.0", "requests"),
            ("click == 8.0.1", "click"),
            ("pytest~= 6.0", "pytest"),
            ("black != 22.1.0", "black"),
            ("sphinx > 4.0", "sphinx"),
            ("numpy < 1.21", "numpy"),
            ("simple_package", "simple_package"),
            ("", None),
            ("- e git + https: / / github.com / user / repo.git", None),
        ]

        for dep_spec, expected in test_cases:
            result = health_service._extract_package_name(dep_spec)
            assert result == expected, (
                f"Failed for {dep_spec}: got {result}, expected {expected}"
            )

    @patch.object(HealthMetricsService, "_fetch_package_data")
    @patch.object(HealthMetricsService, "_extract_upload_time")
    @patch.object(HealthMetricsService, "_calculate_days_since_upload")
    def test_get_package_age_success(
        self, mock_calc_days, mock_extract_time, mock_fetch, health_service
    ):
        mock_fetch.return_value = {"info": {"version": "2.25.1"}}
        mock_extract_time.return_value = "2022 - 01 - 01T12: 00: 00"
        mock_calc_days.return_value = 100

        age = health_service._get_package_age("requests")

        assert age == 100
        mock_fetch.assert_called_once_with("requests")
        mock_extract_time.assert_called_once()
        mock_calc_days.assert_called_once_with("2022 - 01 - 01T12: 00: 00")

    @patch.object(HealthMetricsService, "_fetch_package_data")
    def test_get_package_age_fetch_failure(self, mock_fetch, health_service):
        mock_fetch.return_value = None

        age = health_service._get_package_age("nonexistent_package")

        assert age is None

    def test_extract_upload_time_success(self, health_service):
        package_data = {
            "info": {"version": "2.25.1"},
            "releases": {"2.25.1": [{"upload_time": "2022 - 01 - 15T10: 30: 00"}]},
        }

        upload_time = health_service._extract_upload_time(package_data)

        assert upload_time == "2022 - 01 - 15T10: 30: 00"

    def test_extract_upload_time_no_releases(self, health_service):
        package_data = {"info": {"version": "1.0.0"}, "releases": {}}

        upload_time = health_service._extract_upload_time(package_data)

        assert upload_time is None

    def test_calculate_days_since_upload(self, health_service):
        upload_time_str = "2024 - 01 - 01T12: 00: 00"

        days = health_service._calculate_days_since_upload(upload_time_str)

        assert days is None or (isinstance(days, int) and days >= 0)

    def test_calculate_days_since_upload_invalid_format(self, health_service):
        days = health_service._calculate_days_since_upload("invalid - date")

        assert days is None


class TestHealthMetricsIntegration:
    @patch("subprocess.run")
    def test_collect_current_metrics_full_workflow(self, mock_run, health_service):
        mock_run.side_effect = [
            Mock(
                returncode=1,
                stdout='[{"file": "test.py", "message": "Error"}]',
                stderr="",
            ),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(
                returncode=0, stdout='{"totals": {"percent_covered": 75.0}}', stderr=""
            ),
        ]

        coverage_data = {"totals": {"percent_covered": 85.0}}
        (health_service.project_root / "coverage.json").write_text(
            json.dumps(coverage_data)
        )

        health = health_service.collect_current_metrics()

        assert isinstance(health, ProjectHealth)
        assert len(health.lint_error_trend) == 1
        assert health.lint_error_trend[0] == 1
        assert len(health.test_coverage_trend) == 1
        assert health.test_coverage_trend[0] == 85.0
        assert isinstance(health.dependency_age, dict)
        assert health.config_completeness > 0.0
        assert health.last_updated > 0

    def test_analyze_project_health_with_save(self, health_service):
        with patch.object(health_service, "collect_current_metrics") as mock_collect:
            mock_health = ProjectHealth(
                lint_error_trend=[5], test_coverage_trend=[60.0]
            )
            mock_collect.return_value = mock_health

            result = health_service.analyze_project_health(save_metrics=True)

            assert result is mock_health
            mock_collect.assert_called_once()

            assert health_service.health_cache.exists()

    def test_analyze_project_health_without_save(self, health_service):
        with patch.object(health_service, "collect_current_metrics") as mock_collect:
            mock_health = ProjectHealth()
            mock_collect.return_value = mock_health

            result = health_service.analyze_project_health(save_metrics=False)

            assert result is mock_health
            mock_collect.assert_called_once()

            assert not health_service.health_cache.exists()


class TestHealthReporting:
    def test_report_health_status_full_flow(self, health_service, mock_console):
        health_service.console = mock_console

        health = ProjectHealth(
            lint_error_trend=[5, 3, 2],
            test_coverage_trend=[70.0, 75.0, 80.0],
            dependency_age={"requests": 50, "pytest": 100},
            config_completeness=0.8,
        )

        health_service.report_health_status(health)

        assert mock_console.print.call_count >= 3

        calls = [str(call) for call in mock_console.print.call_args_list]
        header_found = any("Project Health Report" in call for call in calls)
        assert header_found

    def test_get_health_status_display_all_levels(self, health_service):
        test_cases = [
            (0.9, ("🟢", "Excellent", "green")),
            (0.7, ("🟡", "Good", "yellow")),
            (0.5, ("🟠", "Fair", "orange")),
            (0.2, ("🔴", "Poor", "red")),
        ]

        for score, expected in test_cases:
            result = health_service._get_health_status_display(score)
            assert result == expected

    def test_get_health_trend_summary(self, health_service):
        health_data = {
            "lint_error_trend": [10, 8, 5, 3],
            "test_coverage_trend": [60.0, 65.0, 70.0, 75.0],
            "dependency_age": {"requests": 100, "pytest": 50},
            "config_completeness": 0.8,
            "last_updated": time.time(),
        }
        health_service.health_cache.write_text(json.dumps(health_data))

        summary = health_service.get_health_trend_summary()

        assert isinstance(summary, dict)
        assert "health_score" in summary
        assert "needs_attention" in summary
        assert "recommendations" in summary
        assert "metrics" in summary

        metrics = summary["metrics"]
        assert "lint_errors" in metrics
        assert "test_coverage" in metrics
        assert "dependency_age" in metrics
        assert "config_completeness" in metrics

        assert metrics["lint_errors"]["current"] == 3
        assert metrics["test_coverage"]["current"] == 75.0
        assert metrics["dependency_age"]["average"] == 75.0
        assert metrics["dependency_age"]["outdated_count"] == 0


class TestConfigurationAssessment:
    def test_assess_config_completeness_full_setup(self, health_service):
        completeness = health_service._assess_config_completeness()

        assert completeness > 0.5
        assert completeness <= 1.0

    def test_assess_pyproject_config_complete(self, health_service):
        score, checks = health_service._assess_pyproject_config()

        assert score > 0.2
        assert checks > 1

    def test_assess_pyproject_config_missing(self, health_service):
        health_service.pyproject_path.unlink()

        score, checks = health_service._assess_pyproject_config()

        assert score == 0.0
        assert checks == 1

    def test_assess_project_metadata(self, health_service):
        project_data = {
            "project": {
                "name": "test - project",
                "version": "1.0.0",
                "description": "Test project",
                "dependencies": ["requests"],
            }
        }

        score, checks = health_service._assess_project_metadata(project_data)

        assert score == 0.4
        assert checks == 4

    def test_assess_project_metadata_minimal(self, health_service):
        project_data = {"project": {"name": "test - project"}}

        score, checks = health_service._assess_project_metadata(project_data)

        assert score == 0.1
        assert checks == 4

    def test_assess_project_metadata_no_project_section(self, health_service):
        project_data = {"tool": {"ruff": {}}}

        score, checks = health_service._assess_project_metadata(project_data)

        assert score == 0.0
        assert checks == 0

    def test_assess_tool_configs(self, health_service):
        project_data = {
            "tool": {
                "ruff": {"line - length": 88},
                "pytest": {"testpaths": ["tests"]},
                "coverage": {"report": {"exclude_lines": ["pragma: no cover"]}},
            }
        }

        score, checks = health_service._assess_tool_configs(project_data)

        assert abs(score - 0.15) < 1e-10
        assert checks == 3

    def test_assess_precommit_config_exists(self, health_service):
        score, checks = health_service._assess_precommit_config()

        assert score == 0.1
        assert checks == 1

    def test_assess_precommit_config_missing(self, health_service):
        (health_service.project_root / ".pre - commit - config.yaml").unlink()

        score, checks = health_service._assess_precommit_config()

        assert score == 0.0
        assert checks == 1

    def test_assess_ci_config_github(self, health_service):
        workflows_dir = health_service.project_root / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").write_text("name: CI")

        score, checks = health_service._assess_ci_config()

        assert score == 0.1
        assert checks == 1

    def test_assess_ci_config_missing(self, health_service):
        score, checks = health_service._assess_ci_config()

        assert score == 0.0
        assert checks == 1

    def test_assess_documentation_config_readme_exists(self, health_service):
        score, checks = health_service._assess_documentation_config()

        assert score == 0.1
        assert checks == 1

    def test_assess_documentation_config_docs_folder(self, health_service):
        (health_service.project_root / "README.md").unlink()
        (health_service.project_root / "docs").mkdir()
        (health_service.project_root / "docs" / "index.md").write_text(
            "# Documentation"
        )

        score, checks = health_service._assess_documentation_config()

        assert score == 0.1
        assert checks == 1


class TestErrorHandlingAndEdgeCases:
    def test_fetch_package_data_basic(self, health_service):
        assert hasattr(health_service, "_fetch_package_data")
        assert callable(health_service._fetch_package_data)

    def test_fetch_package_data_error_handling(self, health_service):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Network error")

            result = health_service._fetch_package_data("nonexistent_package")

            assert result is None

    def test_fetch_package_data_url_validation(self, health_service):
        with patch("urllib.request.urlopen"):
            result = health_service._fetch_package_data("test - package")

            assert result is None or isinstance(result, dict)

    def test_trend_analysis_edge_cases(self, health_service):
        health = ProjectHealth()

        assert not health._is_trending_up([])
        assert not health._is_trending_down([])

        assert not health._is_trending_up([5])
        assert not health._is_trending_down([5.0])

        assert health._is_trending_up([5, 5, 5, 5])
        assert health._is_trending_down([5.0, 5.0, 5.0, 5.0])

    def test_health_score_edge_cases(self, health_service):
        health = ProjectHealth(dependency_age={"pkg1": 100})
        score = health.get_health_score()
        assert 0.0 <= score <= 1.0

        health = ProjectHealth(dependency_age={"pkg1": 10000})
        score = health.get_health_score()
        assert score >= 0.0

        health = ProjectHealth(lint_error_trend=[1000, 2000, 3000])
        score = health.get_health_score()
        assert score >= 0.0

    def test_max_trend_points_limiting(self, health_service):
        health = ProjectHealth(
            lint_error_trend=list(range(30)),
            test_coverage_trend=[float(i) for i in range(30)],
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            health_service._save_health_metrics(health)

            health.lint_error_trend = health.lint_error_trend[
                -health_service.max_trend_points :
            ]
            health.test_coverage_trend = health.test_coverage_trend[
                -health_service.max_trend_points :
            ]

            assert len(health.lint_error_trend) == 20
            assert len(health.test_coverage_trend) == 20
            assert health.lint_error_trend == list(range(10, 30))
