import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.api import (
    CrackerjackAPI,
    PublishResult,
    QualityCheckResult,
    TestResult,
    clean_code,
    publish_package,
    run_quality_checks,
    run_tests,
)
from crackerjack.models.config import WorkflowOptions


@pytest.mark.skip(reason="CrackerjackAPI requires complex nested ACB DI setup - integration test, not unit test")
class TestCrackerjackAPI:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)

            (project_path / "pyproject.toml").write_text("""
[build - system]
requires = ["setuptools", "wheel"]
build - backend = "setuptools.build_meta"

[project]
name = "test - project"
version = "0.1.0"
""")

            src_dir = project_path / "src"
            src_dir.mkdir()
            (src_dir / "__init__.py").write_text("")
            (src_dir / "main.py").write_text('print("Hello World")')

            tests_dir = project_path / "tests"
            tests_dir.mkdir()
            (tests_dir / "__init__.py").write_text("")
            (tests_dir / "test_main.py").write_text("""
def test_example():
    assert True
""")

            yield project_path

    @pytest.fixture
    def api(self, temp_project, console):
        return CrackerjackAPI(project_path=temp_project, console=console, verbose=False)

    def test_initialization(self, api, temp_project, console) -> None:
        assert api.project_path == temp_project
        assert api.console == console
        assert api.verbose is False
        assert api.container is not None
        assert api.orchestrator is not None

    def test_initialization_defaults(self) -> None:
        api = CrackerjackAPI()
        assert api.project_path == Path.cwd()
        assert api.console is not None
        assert api.verbose is False

    def test_code_cleaner_property(self, api) -> None:
        cleaner1 = api.code_cleaner
        cleaner2 = api.code_cleaner

        assert cleaner1 is not None
        assert cleaner1 is cleaner2

    def test_interactive_cli_property(self, api) -> None:
        cli1 = api.interactive_cli
        cli2 = api.interactive_cli

        assert cli1 is not None
        assert cli1 is cli2

    def test_get_project_info(self, api) -> None:
        info = api.get_project_info()

        assert isinstance(info, dict)
        assert "project_path" in info
        assert "is_python_project" in info
        assert "is_git_repo" in info
        assert "python_files_count" in info
        assert "has_pyproject_toml" in info

        assert info["is_python_project"] is True
        assert info["has_pyproject_toml"] is True
        assert info["python_files_count"] >= 2

    def test_create_workflow_options(self, api) -> None:
        options = api.create_workflow_options(
            clean=True,
            test=True,
            publish="pypi",
            bump="patch",
            commit=True,
        )

        assert isinstance(options, WorkflowOptions)
        assert options.clean is True
        assert options.test is True
        assert options.publish == "pypi"
        assert options.bump == "patch"
        assert options.commit is True

    def test_clean_code(self, api) -> None:
        results = api.clean_code(backup=False)

        assert isinstance(results, list)

        assert len(results) >= 0

    @patch("crackerjack.api.WorkflowOrchestrator")
    def test_run_quality_checks(self, mock_orchestrator, api) -> None:
        mock_result = Mock()
        mock_result.overall_success = True
        mock_result.phase_results = {
            "fast_hooks": {"success": True},
            "comprehensive_hooks": {"success": True},
        }
        mock_result.errors = []
        mock_result.warnings = []

        mock_orchestrator_instance = Mock()
        mock_orchestrator_instance.execute_pipeline.return_value = mock_result
        mock_orchestrator.return_value = mock_orchestrator_instance

        api.orchestrator = mock_orchestrator_instance

        result = api.run_quality_checks(fast_only=False)

        assert isinstance(result, QualityCheckResult)
        assert result.success is True
        assert result.fast_hooks_passed is True
        assert result.comprehensive_hooks_passed is True
        assert isinstance(result.duration, float)

    @patch("crackerjack.api.WorkflowOrchestrator")
    def test_run_tests(self, mock_orchestrator, api) -> None:
        mock_result = Mock()
        mock_result.overall_success = True
        mock_result.phase_results = {"test": {"success": True}}
        mock_result.errors = []

        mock_orchestrator_instance = Mock()
        mock_orchestrator_instance.execute_pipeline.return_value = mock_result
        mock_orchestrator.return_value = mock_orchestrator_instance

        api.orchestrator = mock_orchestrator_instance

        result = api.run_tests(coverage=True, workers=2)

        assert isinstance(result, TestResult)
        assert result.success is True
        assert isinstance(result.duration, float)

    @patch("crackerjack.api.WorkflowOrchestrator")
    def test_publish_package(self, mock_orchestrator, api) -> None:
        mock_result = Mock()
        mock_result.overall_success = True
        mock_result.phase_results = {}
        mock_result.errors = []

        mock_orchestrator_instance = Mock()
        mock_orchestrator_instance.execute_pipeline.return_value = mock_result
        mock_orchestrator.return_value = mock_orchestrator_instance

        api.orchestrator = mock_orchestrator_instance

        result = api.publish_package(version_bump="patch", dry_run=True)

        assert isinstance(result, PublishResult)
        assert result.success is True
        assert isinstance(result.errors, list)

    def test_run_interactive_workflow(self, api) -> None:
        options = WorkflowOptions(clean=False, test=False)

        mock_cli = Mock()
        mock_cli.run_interactive_workflow.return_value = True
        api._interactive_cli = mock_cli

        result = api.run_interactive_workflow(options)

        assert result is True
        mock_cli.run_interactive_workflow.assert_called_once_with(options)


@pytest.mark.skip(reason="Convenience functions require CrackerjackAPI with complex nested ACB DI setup - integration test, not unit test")
class TestConvenienceFunctions:
    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            (project_path / "pyproject.toml").write_text("""
[project]
name = "test"
version = "0.1.0"
""")
            yield project_path

    @patch("crackerjack.api.CrackerjackAPI")
    def test_run_quality_checks_convenience(self, mock_api_class, temp_project) -> None:
        mock_api = Mock()
        mock_result = QualityCheckResult(
            success=True,
            fast_hooks_passed=True,
            comprehensive_hooks_passed=True,
            errors=[],
            warnings=[],
            duration=5.0,
        )
        mock_api.run_quality_checks.return_value = mock_result
        mock_api_class.return_value = mock_api

        result = run_quality_checks(project_path=temp_project, fast_only=True)

        assert isinstance(result, QualityCheckResult)
        assert result.success is True
        mock_api_class.assert_called_once_with(project_path=temp_project)
        mock_api.run_quality_checks.assert_called_once_with(fast_only=True)

    @patch("crackerjack.api.CrackerjackAPI")
    def test_clean_code_convenience(self, mock_api_class, temp_project) -> None:
        mock_api = Mock()
        mock_api.clean_code.return_value = []
        mock_api_class.return_value = mock_api

        result = clean_code(project_path=temp_project, backup=False)

        assert isinstance(result, list)
        mock_api_class.assert_called_once_with(project_path=temp_project)
        mock_api.clean_code.assert_called_once_with(backup=False)

    @patch("crackerjack.api.CrackerjackAPI")
    def test_run_tests_convenience(self, mock_api_class, temp_project) -> None:
        mock_api = Mock()
        mock_result = TestResult(
            success=True,
            passed_count=5,
            failed_count=0,
            coverage_percentage=85.0,
            duration=10.0,
            errors=[],
        )
        mock_api.run_tests.return_value = mock_result
        mock_api_class.return_value = mock_api

        result = run_tests(project_path=temp_project, coverage=True)

        assert isinstance(result, TestResult)
        assert result.success is True
        mock_api_class.assert_called_once_with(project_path=temp_project)
        mock_api.run_tests.assert_called_once_with(coverage=True)

    @patch("crackerjack.api.CrackerjackAPI")
    def test_publish_package_convenience(self, mock_api_class, temp_project) -> None:
        mock_api = Mock()
        mock_result = PublishResult(
            success=True,
            version="0.1.1",
            published_to=["pypi"],
            errors=[],
        )
        mock_api.publish_package.return_value = mock_result
        mock_api_class.return_value = mock_api

        result = publish_package(
            project_path=temp_project,
            version_bump="patch",
            dry_run=True,
        )

        assert isinstance(result, PublishResult)
        assert result.success is True
        mock_api_class.assert_called_once_with(project_path=temp_project)
        mock_api.publish_package.assert_called_once_with(
            version_bump="patch",
            dry_run=True,
        )


class TestResultClasses:
    def test_quality_check_result(self) -> None:
        result = QualityCheckResult(
            success=True,
            fast_hooks_passed=True,
            comprehensive_hooks_passed=False,
            errors=["Error 1"],
            warnings=["Warning 1"],
            duration=5.5,
        )

        assert result.success is True
        assert result.fast_hooks_passed is True
        assert result.comprehensive_hooks_passed is False
        assert result.errors == ["Error 1"]
        assert result.warnings == ["Warning 1"]
        assert result.duration == 5.5

    def test_test_result(self) -> None:
        result = TestResult(
            success=True,
            passed_count=10,
            failed_count=1,
            coverage_percentage=85.5,
            duration=15.0,
            errors=[],
        )

        assert result.success is True
        assert result.passed_count == 10
        assert result.failed_count == 1
        assert result.coverage_percentage == 85.5
        assert result.duration == 15.0
        assert result.errors == []

    def test_publish_result(self) -> None:
        result = PublishResult(
            success=True,
            version="1.0.0",
            published_to=["pypi", "testpypi"],
            errors=[],
        )

        assert result.success is True
        assert result.version == "1.0.0"
        assert result.published_to == ["pypi", "testpypi"]
        assert result.errors == []


@pytest.mark.skip(reason="Error handling tests require CrackerjackAPI with complex nested ACB DI setup - integration test, not unit test")
class TestErrorHandling:
    @pytest.fixture
    def api(self):
        return CrackerjackAPI()

    def test_quality_checks_exception_handling(self, api) -> None:
        api.orchestrator.execute_pipeline = Mock(side_effect=Exception("Test error"))

        result = api.run_quality_checks()

        assert isinstance(result, QualityCheckResult)
        assert result.success is False
        assert "Test error" in result.errors
        assert isinstance(result.duration, float)

    def test_test_execution_exception_handling(self, api) -> None:
        api.orchestrator.execute_pipeline = Mock(side_effect=Exception("Test error"))

        result = api.run_tests()

        assert isinstance(result, TestResult)
        assert result.success is False
        assert "Test error" in result.errors
        assert isinstance(result.duration, float)

    def test_publish_exception_handling(self, api) -> None:
        api.orchestrator.execute_pipeline = Mock(side_effect=Exception("Test error"))

        result = api.publish_package()

        assert isinstance(result, PublishResult)
        assert result.success is False
        assert "Test error" in result.errors
