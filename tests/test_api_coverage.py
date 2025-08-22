import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

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
from crackerjack.code_cleaner import CleaningResult, CodeCleaner
from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.errors import CrackerjackError, ErrorCode
from crackerjack.interactive import InteractiveCLI
from crackerjack.interactive import WorkflowOptions as InteractiveWorkflowOptions
from crackerjack.models.config import WorkflowOptions


class TestQualityCheckResult:
    def test_quality_check_result_creation(self) -> None:
        result = QualityCheckResult(
            success=True,
            fast_hooks_passed=True,
            comprehensive_hooks_passed=False,
            errors=["Error 1"],
            warnings=["Warning 1", "Warning 2"],
            duration=12.5,
        )

        assert result.success is True
        assert result.fast_hooks_passed is True
        assert result.comprehensive_hooks_passed is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 2
        assert result.duration == 12.5


class TestTestResult:
    def test_test_result_creation(self) -> None:
        result = TestResult(
            success=True,
            passed_count=25,
            failed_count=3,
            coverage_percentage=85.2,
            duration=45.7,
            errors=[],
        )

        assert result.success is True
        assert result.passed_count == 25
        assert result.failed_count == 3
        assert result.coverage_percentage == 85.2
        assert result.duration == 45.7
        assert len(result.errors) == 0


class TestPublishResult:
    def test_publish_result_creation(self) -> None:
        result = PublishResult(
            success=True, version="1.2.3", published_to=["pypi", "testpypi"], errors=[]
        )

        assert result.success is True
        assert result.version == "1.2.3"
        assert len(result.published_to) == 2
        assert "pypi" in result.published_to
        assert len(result.errors) == 0


class TestCrackerjackAPIInitialization:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_init_defaults(self) -> None:
        api = CrackerjackAPI()

        assert api.project_path == Path.cwd()
        assert isinstance(api.console, Console)
        assert api.verbose is False
        assert isinstance(api.orchestrator, WorkflowOrchestrator)
        assert api.container is not None
        assert api.logger is not None
        assert api._code_cleaner is None
        assert api._interactive_cli is None

    def test_init_with_parameters(self, temp_dir) -> None:
        console = Mock(spec=Console)

        api = CrackerjackAPI(project_path=temp_dir, console=console, verbose=True)

        assert api.project_path == temp_dir
        assert api.console == console
        assert api.verbose is True
        assert isinstance(api.orchestrator, WorkflowOrchestrator)

    def test_init_sets_logger(self) -> None:
        api = CrackerjackAPI()

        assert api.logger is not None
        assert api.logger.name == "crackerjack.api"

    def test_code_cleaner_property_lazy_creation(self) -> None:
        api = CrackerjackAPI()

        assert api._code_cleaner is None
        cleaner = api.code_cleaner
        assert isinstance(cleaner, CodeCleaner)
        assert api._code_cleaner is cleaner

        assert api.code_cleaner is cleaner

    def test_interactive_cli_property_lazy_creation(self) -> None:
        api = CrackerjackAPI()

        assert api._interactive_cli is None
        cli = api.interactive_cli
        assert isinstance(cli, InteractiveCLI)
        assert api._interactive_cli is cli

        assert api.interactive_cli is cli


class TestCrackerjackAPIQualityChecks:
    @pytest.fixture
    def api(self):
        console = Mock(spec=Console)
        api = CrackerjackAPI(console=console)
        api.orchestrator = Mock(spec=WorkflowOrchestrator)
        api.orchestrator.pipeline = Mock()
        api.orchestrator.pipeline.run_complete_workflow = AsyncMock()
        return api

    def test_run_quality_checks_success(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.run_quality_checks()

        assert isinstance(result, QualityCheckResult)
        assert result.success is True
        assert result.fast_hooks_passed is True
        assert result.comprehensive_hooks_passed is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert result.duration > 0

        api.orchestrator.pipeline.run_complete_workflow.assert_called_once()

    def test_run_quality_checks_failure(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = False

        result = api.run_quality_checks()

        assert isinstance(result, QualityCheckResult)
        assert result.success is False
        assert result.fast_hooks_passed is False
        assert result.comprehensive_hooks_passed is False
        assert len(result.errors) == 1
        assert "Quality checks failed" in result.errors[0]
        assert result.duration > 0

    def test_run_quality_checks_fast_only(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.run_quality_checks(fast_only=True)

        assert result.success is True
        assert result.comprehensive_hooks_passed is True

    def test_run_quality_checks_no_autofix(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.run_quality_checks(autofix=False)

        assert result.success is True

        call_args = api.orchestrator.pipeline.run_complete_workflow.call_args[0][0]
        assert call_args.autofix is False

    def test_run_quality_checks_exception(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.side_effect = ValueError(
            "Test error"
        )

        result = api.run_quality_checks()

        assert result.success is False
        assert result.fast_hooks_passed is False
        assert result.comprehensive_hooks_passed is False
        assert len(result.errors) == 1
        assert "Test error" in result.errors[0]
        assert result.duration > 0


class TestCrackerjackAPICodeCleaning:
    @pytest.fixture
    def api(self, temp_dir):
        console = Mock(spec=Console)
        api = CrackerjackAPI(project_path=temp_dir, console=console)
        return api

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_clean_code_success(self, api, temp_dir) -> None:
        mock_results = [
            CleaningResult(
                file_path=temp_dir / "file1.py",
                success=True,
                steps_completed=["step1"],
                steps_failed=[],
                warnings=[],
                original_size=100,
                cleaned_size=80,
            ),
            CleaningResult(
                file_path=temp_dir / "file2.py",
                success=True,
                steps_completed=["step1"],
                steps_failed=[],
                warnings=[],
                original_size=150,
                cleaned_size=120,
            ),
        ]

        mock_cleaner = Mock()
        api._code_cleaner = mock_cleaner
        mock_cleaner.clean_files.return_value = mock_results

        results = api.clean_code()

        assert len(results) == 2
        assert all(isinstance(r, CleaningResult) for r in results)
        mock_cleaner.clean_files.assert_called_once_with(temp_dir)

        api.console.print.assert_called()
        console_calls = [str(call) for call in api.console.print.call_args_list]
        success_messages = [
            call for call in console_calls if "Successfully cleaned 2 files" in call
        ]
        assert len(success_messages) == 1

    def test_clean_code_with_failures(self, api, temp_dir) -> None:
        mock_results = [
            CleaningResult(
                file_path=temp_dir / "file1.py",
                success=True,
                steps_completed=["step1"],
                steps_failed=[],
                warnings=[],
                original_size=100,
                cleaned_size=80,
            ),
            CleaningResult(
                file_path=temp_dir / "file2.py",
                success=False,
                steps_completed=[],
                steps_failed=["step1"],
                warnings=[],
                original_size=150,
                cleaned_size=150,
            ),
        ]

        mock_cleaner = Mock()
        api._code_cleaner = mock_cleaner
        mock_cleaner.clean_files.return_value = mock_results

        results = api.clean_code()

        assert len(results) == 2

        assert api.console.print.call_count >= 2

    def test_clean_code_custom_target_dir(self, api, temp_dir) -> None:
        custom_dir = temp_dir / "custom"
        custom_dir.mkdir()

        mock_cleaner = Mock()
        api._code_cleaner = mock_cleaner
        mock_cleaner.clean_files.return_value = []

        api.clean_code(target_dir=custom_dir)

        mock_cleaner.clean_files.assert_called_once_with(custom_dir)

    def test_clean_code_with_backup_false(self, api, temp_dir) -> None:
        mock_cleaner = Mock()
        api._code_cleaner = mock_cleaner
        mock_cleaner.clean_files.return_value = []

        api.clean_code(backup=False)

        console_calls = [str(call) for call in api.console.print.call_args_list]
        backup_messages = [call for call in console_calls if "Backup" in call]
        assert len(backup_messages) == 0

    def test_clean_code_exception(self, api) -> None:
        mock_cleaner = Mock()
        api._code_cleaner = mock_cleaner
        mock_cleaner.clean_files.side_effect = ValueError("Test error")

        with pytest.raises(CrackerjackError) as exc_info:
            api.clean_code()

        assert exc_info.value.error_code == ErrorCode.CODE_CLEANING_ERROR
        assert "Test error" in str(exc_info.value)


class TestCrackerjackAPITesting:
    @pytest.fixture
    def api(self):
        console = Mock(spec=Console)
        api = CrackerjackAPI(console=console)
        api.orchestrator = Mock(spec=WorkflowOrchestrator)
        api.orchestrator.pipeline = Mock()
        api.orchestrator.pipeline.run_complete_workflow = AsyncMock()
        return api

    def test_run_tests_success(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.run_tests()

        assert isinstance(result, TestResult)
        assert result.success is True
        assert result.passed_count == 0
        assert result.failed_count == 0
        assert result.coverage_percentage == 0.0
        assert len(result.errors) == 0
        assert result.duration > 0

    def test_run_tests_with_coverage(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.run_tests(coverage=True)

        assert result.success is True
        api.orchestrator.pipeline.run_complete_workflow.assert_called_once()

    def test_run_tests_with_workers(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.run_tests(workers=4)

        assert result.success is True

        call_args = api.orchestrator.pipeline.run_complete_workflow.call_args[0][0]
        assert call_args.test_workers == 4

    def test_run_tests_with_timeout(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.run_tests(timeout=600)

        assert result.success is True

        call_args = api.orchestrator.pipeline.run_complete_workflow.call_args[0][0]
        assert call_args.test_timeout == 600

    def test_run_tests_failure(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = False

        result = api.run_tests()

        assert result.success is False
        assert len(result.errors) == 1
        assert "Test execution failed" in result.errors[0]

    def test_run_tests_exception(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.side_effect = RuntimeError(
            "Test error"
        )

        result = api.run_tests()

        assert result.success is False
        assert len(result.errors) == 1
        assert "Test error" in result.errors[0]


class TestCrackerjackAPIPublishing:
    @pytest.fixture
    def api(self):
        console = Mock(spec=Console)
        api = CrackerjackAPI(console=console)
        api.orchestrator = Mock(spec=WorkflowOrchestrator)
        api.orchestrator.pipeline = Mock()
        return api

    def test_publish_package_success(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.publish_package()

        assert isinstance(result, PublishResult)
        assert result.success is True
        assert result.version == ""
        assert len(result.published_to) == 1
        assert len(result.errors) == 0

    def test_publish_package_with_version_bump(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.publish_package(version_bump="patch")

        assert result.success is True

        call_args = api.orchestrator.pipeline.run_complete_workflow.call_args[0][0]
        assert call_args.bump == "patch"

    def test_publish_package_dry_run(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.publish_package(dry_run=True)

        assert result.success is True

        call_args = api.orchestrator.pipeline.run_complete_workflow.call_args[0][0]
        assert call_args.publish is None

    def test_publish_package_real_publish(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = True

        result = api.publish_package(version_bump="minor", dry_run=False)

        assert result.success is True
        assert result.published_to == ["pypi"]

        call_args = api.orchestrator.pipeline.run_complete_workflow.call_args[0][0]
        assert call_args.publish == "pypi"

    def test_publish_package_failure(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.return_value = False

        result = api.publish_package()

        assert result.success is False
        assert len(result.errors) == 1
        assert "Publishing failed" in result.errors[0]

    def test_publish_package_exception(self, api) -> None:
        api.orchestrator.pipeline.run_complete_workflow.side_effect = ValueError(
            "Publish error"
        )

        result = api.publish_package()

        assert result.success is False
        assert len(result.errors) == 1
        assert "Publish error" in result.errors[0]


class TestCrackerjackAPIInteractive:
    @pytest.fixture
    def api(self):
        console = Mock(spec=Console)
        return CrackerjackAPI(console=console)

    def test_run_interactive_workflow_success(self, api) -> None:
        mock_cli = Mock()
        api._interactive_cli = mock_cli
        mock_cli.run_interactive_workflow.return_value = True

        result = api.run_interactive_workflow()

        assert result is True
        mock_cli.run_interactive_workflow.assert_called_once_with(
            InteractiveWorkflowOptions()
        )

    def test_run_interactive_workflow_with_options(self, api) -> None:
        options = InteractiveWorkflowOptions(clean=True, test=True)

        mock_cli = Mock()
        api._interactive_cli = mock_cli
        mock_cli.run_interactive_workflow.return_value = True

        result = api.run_interactive_workflow(options)

        assert result is True
        mock_cli.run_interactive_workflow.assert_called_once_with(options)

    def test_run_interactive_workflow_failure(self, api) -> None:
        mock_cli = Mock()
        api._interactive_cli = mock_cli
        mock_cli.run_interactive_workflow.return_value = False

        result = api.run_interactive_workflow()

        assert result is False

    def test_run_interactive_workflow_exception(self, api) -> None:
        mock_cli = Mock()
        api._interactive_cli = mock_cli
        mock_cli.run_interactive_workflow.side_effect = RuntimeError(
            "Interactive error"
        )

        result = api.run_interactive_workflow()

        assert result is False
        api.console.print.assert_called()
        assert "Interactive workflow failed" in str(api.console.print.call_args)


class TestCrackerjackAPIWorkflowOptions:
    @pytest.fixture
    def api(self):
        return CrackerjackAPI()

    def test_create_workflow_options_defaults(self, api) -> None:
        options = api.create_workflow_options()

        assert isinstance(options, WorkflowOptions)
        assert options.clean is True
        assert options.test is False
        assert options.publish is None
        assert options.bump is None
        assert options.commit is False
        assert options.create_pr is False

    def test_create_workflow_options_custom(self, api) -> None:
        options = api.create_workflow_options(
            clean=True,
            test=True,
            publish="pypi",
            bump="patch",
            commit=True,
            create_pr=True,
        )

        assert options.clean is True
        assert options.test is True
        assert options.publish == "pypi"
        assert options.bump == "patch"
        assert options.commit is True
        assert options.create_pr is True

    def test_create_workflow_options_with_kwargs(self, api) -> None:
        options = api.create_workflow_options(
            clean=True, verbose=True, custom_flag=True
        )

        assert options.clean is True
        assert hasattr(options, "verbose")
        assert hasattr(options, "custom_flag")


class TestCrackerjackAPIProjectInfo:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_get_project_info_python_project(self, temp_dir) -> None:
        (temp_dir / "pyproject.toml").write_text("[tool.poetry]")
        (temp_dir / "src").mkdir()
        (temp_dir / "src" / "module.py").write_text("print('hello')")
        (temp_dir / "test_example.py").write_text("def test_example(): pass")
        (temp_dir / ".git").mkdir()

        api = CrackerjackAPI(project_path=temp_dir)
        info = api.get_project_info()

        assert info["project_path"] == str(temp_dir)
        assert info["is_python_project"] is True
        assert info["is_git_repo"] is True
        assert info["python_files_count"] == 2
        assert info["has_pyproject_toml"] is True
        assert info["has_setup_py"] is False
        assert info["has_requirements_txt"] is False
        assert info["has_tests"] is True

    def test_get_project_info_setup_py_project(self, temp_dir) -> None:
        (temp_dir / "setup.py").write_text("from setuptools import setup")
        (temp_dir / "requirements.txt").write_text("requests == 2.28.0")

        api = CrackerjackAPI(project_path=temp_dir)
        info = api.get_project_info()

        assert info["is_python_project"] is True
        assert info["has_pyproject_toml"] is False
        assert info["has_setup_py"] is True
        assert info["has_requirements_txt"] is True

    def test_get_project_info_non_python_project(self, temp_dir) -> None:
        (temp_dir / "README.md").write_text("# Project")

        api = CrackerjackAPI(project_path=temp_dir)
        info = api.get_project_info()

        assert info["is_python_project"] is False
        assert info["is_git_repo"] is False
        assert info["python_files_count"] == 0
        assert info["has_tests"] is False

    def test_get_project_info_exception(self, temp_dir) -> None:
        api = CrackerjackAPI(project_path=temp_dir)

        with patch.object(Path, "rglob", side_effect=OSError("Error")):
            info = api.get_project_info()

            assert "error" in info
            assert "Error" in info["error"]


class TestCrackerjackAPICreateOptions:
    @pytest.fixture
    def api(self):
        return CrackerjackAPI()

    def test_create_options_defaults(self, api) -> None:
        options = api._create_options()

        assert options.commit is False
        assert options.interactive is False
        assert options.no_config_updates is False
        assert options.verbose is False
        assert options.clean is False
        assert options.test is False
        assert options.autofix is True
        assert options.publish is None
        assert options.bump is None
        assert options.test_workers == 0
        assert options.test_timeout == 0

    def test_create_options_custom(self, api) -> None:
        options = api._create_options(
            commit=True,
            test=True,
            autofix=False,
            publish="pypi",
            bump="minor",
            test_workers=4,
            test_timeout=300,
        )

        assert options.commit is True
        assert options.test is True
        assert options.autofix is False
        assert options.publish == "pypi"
        assert options.bump == "minor"
        assert options.test_workers == 4
        assert options.test_timeout == 300

    def test_create_options_arbitrary_kwargs(self, api) -> None:
        options = api._create_options(
            custom_flag=True, custom_value="test", custom_number=42
        )

        assert options.custom_flag is True
        assert options.custom_value == "test"
        assert options.custom_number == 42


class TestConvenienceFunctions:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_run_quality_checks_convenience(self, temp_dir) -> None:
        with patch("crackerjack.api.CrackerjackAPI") as mock_api_class:
            mock_api = Mock()
            mock_api.run_quality_checks.return_value = QualityCheckResult(
                success=True,
                fast_hooks_passed=True,
                comprehensive_hooks_passed=True,
                errors=[],
                warnings=[],
                duration=5.0,
            )
            mock_api_class.return_value = mock_api

            result = run_quality_checks(
                project_path=temp_dir, fast_only=True, autofix=False
            )

            assert isinstance(result, QualityCheckResult)
            mock_api_class.assert_called_once_with(project_path=temp_dir)
            mock_api.run_quality_checks.assert_called_once_with(
                fast_only=True, autofix=False
            )

    def test_clean_code_convenience(self, temp_dir) -> None:
        with patch("crackerjack.api.CrackerjackAPI") as mock_api_class:
            mock_api = Mock()
            mock_api.clean_code.return_value = []
            mock_api_class.return_value = mock_api

            result = clean_code(project_path=temp_dir, backup=False)

            assert isinstance(result, list)
            mock_api_class.assert_called_once_with(project_path=temp_dir)
            mock_api.clean_code.assert_called_once_with(backup=False)

    def test_run_tests_convenience(self, temp_dir) -> None:
        with patch("crackerjack.api.CrackerjackAPI") as mock_api_class:
            mock_api = Mock()
            mock_api.run_tests.return_value = TestResult(
                success=True,
                passed_count=10,
                failed_count=0,
                coverage_percentage=85.0,
                duration=30.0,
                errors=[],
            )
            mock_api_class.return_value = mock_api

            result = run_tests(project_path=temp_dir, coverage=True)

            assert isinstance(result, TestResult)
            mock_api_class.assert_called_once_with(project_path=temp_dir)
            mock_api.run_tests.assert_called_once_with(coverage=True)

    def test_publish_package_convenience(self, temp_dir) -> None:
        with patch("crackerjack.api.CrackerjackAPI") as mock_api_class:
            mock_api = Mock()
            mock_api.publish_package.return_value = PublishResult(
                success=True, version="1.2.3", published_to=["pypi"], errors=[]
            )
            mock_api_class.return_value = mock_api

            result = publish_package(
                project_path=temp_dir, version_bump="patch", dry_run=True
            )

            assert isinstance(result, PublishResult)
            mock_api_class.assert_called_once_with(project_path=temp_dir)
            mock_api.publish_package.assert_called_once_with(
                version_bump="patch", dry_run=True
            )
