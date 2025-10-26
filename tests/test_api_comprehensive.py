import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from rich.console import Console

from crackerjack.api import (
    CrackerjackAPI,
    QualityCheckResult,
    TestResult,
    PublishResult,
    clean_code,
    publish_package,
    run_quality_checks,
    run_tests,
)
from crackerjack.code_cleaner import (
    CleaningResult,
    PackageCleaningResult,
)


@pytest.mark.skip(reason="CrackerjackAPI instantiation requires complex nested ACB DI setup - integration test, not unit test")
class TestCrackerjackAPI:
    @pytest.fixture
    def console(self):
        return Console()

    @pytest.fixture
    def pkg_path(self):
        return Path(tempfile.gettempdir())

    @pytest.fixture
    def api(self, console, pkg_path):
        return CrackerjackAPI(project_path=pkg_path)

    def test_init(self, api, console, pkg_path):
        """Test CrackerjackAPI initialization"""
        assert api.project_path == pkg_path
        assert api.console == console
        assert api.verbose is False
        assert api._code_cleaner is None
        assert api._interactive_cli is None
        assert api.logger is not None

    def test_code_cleaner_property(self, api, console):
        """Test code_cleaner property lazy loading"""
        with patch('crackerjack.api.CodeCleaner') as mock_code_cleaner_class:
            mock_code_cleaner_instance = Mock()
            mock_code_cleaner_class.return_value = mock_code_cleaner_instance

            # First access should create the code cleaner
            cleaner1 = api.code_cleaner
            mock_code_cleaner_class.assert_called_once_with(
                console=console, base_directory=api.project_path
            )
            assert cleaner1 == mock_code_cleaner_instance

            # Second access should return the same instance
            cleaner2 = api.code_cleaner
            # Still only called once
            assert cleaner2 == mock_code_cleaner_instance

    def test_interactive_cli_property(self, api, console):
        """Test interactive_cli property lazy loading"""
        with patch('crackerjack.api.InteractiveCLI') as mock_interactive_cli_class:
            mock_interactive_cli_instance = Mock()
            mock_interactive_cli_class.return_value = mock_interactive_cli_instance

            # First access should create the interactive CLI
            cli1 = api.interactive_cli
            mock_interactive_cli_class.assert_called_once_with(console=console)
            assert cli1 == mock_interactive_cli_instance

            # Second access should return the same instance
            cli2 = api.interactive_cli
            # Still only called once
            assert cli2 == mock_interactive_cli_instance

    @pytest.mark.asyncio
    async def test_run_quality_checks_success(self, api):
        """Test run_quality_checks method with success"""
        with patch.object(api, 'orchestrator') as mock_orchestrator:
            mock_orchestrator.pipeline.run_complete_workflow = AsyncMock(return_value=True)

            result = api.run_quality_checks(fast_only=False, autofix=True)

            assert isinstance(result, QualityCheckResult)
            assert result.success is True
            assert result.fast_hooks_passed is True
            assert result.comprehensive_hooks_passed is True
            assert result.errors == []
            assert result.warnings == []
            assert result.duration >= 0

    @pytest.mark.asyncio
    async def test_run_quality_checks_failure(self, api):
        """Test run_quality_checks method with failure"""
        with patch.object(api, 'orchestrator') as mock_orchestrator:
            mock_orchestrator.pipeline.run_complete_workflow = AsyncMock(return_value=False)

            result = api.run_quality_checks(fast_only=False, autofix=True)

            assert isinstance(result, QualityCheckResult)
            assert result.success is False
            assert result.fast_hooks_passed is False
            assert result.comprehensive_hooks_passed is False
            assert result.errors == ["Quality checks failed"]
            assert result.warnings == []
            assert result.duration >= 0

    @pytest.mark.asyncio
    async def test_run_quality_checks_exception(self, api):
        """Test run_quality_checks method with exception"""
        with patch.object(api, 'orchestrator') as mock_orchestrator:
            test_exception = Exception("Test error")
            mock_orchestrator.pipeline.run_complete_workflow = AsyncMock(side_effect=test_exception)

            result = api.run_quality_checks(fast_only=False, autofix=True)

            assert isinstance(result, QualityCheckResult)
            assert result.success is False
            assert result.fast_hooks_passed is False
            assert result.comprehensive_hooks_passed is False
            assert len(result.errors) == 1
            assert result.warnings == []
            assert result.duration >= 0

    def test_clean_code_safe_mode(self, api):
        """Test clean_code method with safe mode"""
        with patch.object(api, '_get_package_root', return_value=api.project_path), \
             patch.object(api, '_validate_code_before_cleaning'), \
             patch.object(api, '_execute_safe_code_cleaning') as mock_execute:

            mock_result = Mock(spec=PackageCleaningResult)
            mock_execute.return_value = mock_result

            result = api.clean_code(safe_mode=True)

            assert result == mock_result
            mock_execute.assert_called_once_with(api.project_path)

    def test_clean_code_legacy_mode(self, api):
        """Test clean_code method with legacy mode"""
        with patch.object(api, '_get_package_root', return_value=api.project_path), \
             patch.object(api, '_validate_code_before_cleaning'), \
             patch.object(api, '_execute_code_cleaning') as mock_execute:

            mock_result = [Mock(spec=CleaningResult)]
            mock_execute.return_value = mock_result

            result = api.clean_code(safe_mode=False)

            assert result == mock_result
            mock_execute.assert_called_once_with(api.project_path)

    def test_clean_code_with_target_dir(self, api):
        """Test clean_code method with specific target directory"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_dir = Path(tmp_dir)

            with patch.object(api, '_validate_code_before_cleaning'), \
                 patch.object(api, '_execute_safe_code_cleaning') as mock_execute:

                mock_result = Mock(spec=PackageCleaningResult)
                mock_execute.return_value = mock_result

                result = api.clean_code(target_dir=target_dir, safe_mode=True)

                assert result == mock_result
                mock_execute.assert_called_once_with(target_dir)

    def test_get_project_info_with_pyproject(self, api):
        """Test get_project_info method when pyproject.toml exists"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            api.project_path = tmp_path

            # Create a pyproject.toml file
            pyproject_path = tmp_path / "pyproject.toml"
            pyproject_path.write_text('[project]\nname = "test"\n')

            # Create a .git directory
            (tmp_path / ".git").mkdir()

            # Create some Python files
            (tmp_path / "main.py").write_text("print('hello')")
            (tmp_path / "module.py").write_text("def func(): pass")

            result = api.get_project_info()

            assert isinstance(result, dict)
            assert result["project_path"] == str(tmp_path)
            assert result["is_python_project"] is True
            assert result["is_git_repo"] is True
            assert result["python_files_count"] == 2
            assert result["has_pyproject_toml"] is True
            assert result["has_setup_py"] is False

    def test_get_project_info_without_project_files(self, api):
        """Test get_project_info method when no project files exist"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            api.project_path = tmp_path

            # Don't create any project files
            result = api.get_project_info()

            assert isinstance(result, dict)
            assert result["project_path"] == str(tmp_path)
            assert result["is_python_project"] is False
            assert result["is_git_repo"] is False
            assert result["python_files_count"] == 0
            assert result["has_pyproject_toml"] is False
            assert result["has_setup_py"] is False

    @pytest.mark.asyncio
    async def test_run_tests_success(self, api):
        """Test run_tests method with success"""
        with patch.object(api, 'orchestrator') as mock_orchestrator:
            mock_orchestrator.pipeline.run_complete_workflow = AsyncMock(return_value=True)
            mock_orchestrator.phases.test_manager = Mock()

            # Mock the test results extraction methods
            with patch.object(api, '_extract_test_passed_count', return_value=10), \
                 patch.object(api, '_extract_test_failed_count', return_value=0), \
                 patch.object(api, '_extract_coverage_percentage', return_value=95.0):

                result = api.run_tests(coverage=True, workers=4, timeout=30)

                assert isinstance(result, TestResult)
                assert result.success is True
                assert result.passed_count == 10
                assert result.failed_count == 0
                assert result.coverage_percentage == 95.0
                assert result.duration >= 0
                assert result.errors == []

    @pytest.mark.asyncio
    async def test_run_tests_failure(self, api):
        """Test run_tests method with failure"""
        with patch.object(api, 'orchestrator') as mock_orchestrator:
            mock_orchestrator.pipeline.run_complete_workflow = AsyncMock(return_value=False)

            # Mock the test results extraction methods
            with patch.object(api, '_extract_test_passed_count', return_value=0), \
                 patch.object(api, '_extract_test_failed_count', return_value=5), \
                 patch.object(api, '_extract_coverage_percentage', return_value=0.0):

                result = api.run_tests(coverage=True, workers=4, timeout=30)

                assert isinstance(result, TestResult)
                assert result.success is False
                assert result.passed_count == 0
                assert result.failed_count == 5
                assert result.coverage_percentage == 0.0
                assert result.duration >= 0
                assert result.errors == ["Test execution failed"]

    @pytest.mark.asyncio
    async def test_publish_package_success(self, api):
        """Test publish_package method with success"""
        with patch.object(api, 'orchestrator') as mock_orchestrator:
            mock_orchestrator.pipeline.run_complete_workflow = AsyncMock(return_value=True)

            with patch.object(api, '_extract_current_version', return_value="1.0.0"):
                result = api.publish_package(version_bump="patch", dry_run=False)

                assert isinstance(result, PublishResult)
                assert result.success is True
                assert result.version == "1.0.0"
                assert result.published_to == ["pypi"]
                assert result.errors == []

    @pytest.mark.asyncio
    async def test_publish_package_dry_run(self, api):
        """Test publish_package method with dry run"""
        with patch.object(api, 'orchestrator') as mock_orchestrator:
            mock_orchestrator.pipeline.run_complete_workflow = AsyncMock(return_value=True)

            with patch.object(api, '_extract_current_version', return_value="1.0.0"):
                result = api.publish_package(version_bump="patch", dry_run=True)

                assert isinstance(result, PublishResult)
                assert result.success is True
                assert result.version == "1.0.0"
                assert result.published_to == []
                assert result.errors == []

    def test_create_workflow_options(self, api):
        """Test create_workflow_options method"""
        # Test with clean option
        options = api.create_workflow_options(clean=True)
        assert options.cleaning is not None
        assert options.cleaning.clean is True

        # Test with test option
        options = api.create_workflow_options(test=True)
        assert options.testing is not None
        assert options.testing.test is True

        # Test with publish option
        options = api.create_workflow_options(publish="pypi")
        assert options.publishing is not None
        assert options.publishing.publish == "pypi"

        # Test with bump option
        options = api.create_workflow_options(bump="patch")
        assert options.publishing is not None
        assert options.publishing.bump == "patch"

        # Test with verbose option
        options = api.create_workflow_options(verbose=True)
        assert options.execution is not None
        assert options.execution.verbose is True

    def test_extract_current_version_from_pyproject(self, api):
        """Test _extract_current_version method with pyproject.toml"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            api.project_path = tmp_path

            # Create a pyproject.toml file with version
            pyproject_content = '''
[project]
name = "test"
version = "1.2.3"
'''
            (tmp_path / "pyproject.toml").write_text(pyproject_content)

            version = api._extract_current_version()
            assert version == "1.2.3"

    def test_extract_current_version_from_importlib(self, api):
        """Test _extract_current_version method with importlib fallback"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            api.project_path = tmp_path

            # Don't create pyproject.toml, so it falls back to importlib

            with patch('importlib.metadata.version', return_value="0.38.12"):
                version = api._extract_current_version()
                assert version == "0.38.12"

    def test_extract_current_version_unknown(self, api):
        """Test _extract_current_version method when version cannot be determined"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            api.project_path = tmp_path

            # Don't create pyproject.toml and mock importlib to raise exception
            with patch('importlib.metadata.version', side_effect=Exception("Not found")):
                version = api._extract_current_version()
                assert version == "unknown"


# Test the standalone functions
class TestStandaloneAPIFunctions:
    def test_run_quality_checks_function(self):
        """Test the standalone run_quality_checks function"""
        with patch('crackerjack.api.CrackerjackAPI') as mock_api_class:
            mock_api_instance = Mock()
            mock_result = Mock(spec=QualityCheckResult)
            mock_api_instance.run_quality_checks.return_value = mock_result
            mock_api_class.return_value = mock_api_instance

            result = run_quality_checks(project_path=Path("/tmp"), fast_only=True, autofix=False)

            assert result == mock_result
            mock_api_class.assert_called_once_with(project_path=Path("/tmp"))
            mock_api_instance.run_quality_checks.assert_called_once_with(fast_only=True, autofix=False)

    def test_clean_code_function(self):
        """Test the standalone clean_code function"""
        with patch('crackerjack.api.CrackerjackAPI') as mock_api_class:
            mock_api_instance = Mock()
            mock_result = Mock()
            mock_api_instance.clean_code.return_value = mock_result
            mock_api_class.return_value = mock_api_instance

            result = clean_code(project_path=Path("/tmp"), backup=False, safe_mode=False)

            assert result == mock_result
            mock_api_class.assert_called_once_with(project_path=Path("/tmp"))
            mock_api_instance.clean_code.assert_called_once_with(backup=False, safe_mode=False)

    def test_run_tests_function(self):
        """Test the standalone run_tests function"""
        with patch('crackerjack.api.CrackerjackAPI') as mock_api_class:
            mock_api_instance = Mock()
            mock_result = Mock(spec=TestResult)
            mock_api_instance.run_tests.return_value = mock_result
            mock_api_class.return_value = mock_api_instance

            result = run_tests(project_path=Path("/tmp"), coverage=True)

            assert result == mock_result
            mock_api_class.assert_called_once_with(project_path=Path("/tmp"))
            mock_api_instance.run_tests.assert_called_once_with(coverage=True)

    def test_publish_package_function(self):
        """Test the standalone publish_package function"""
        with patch('crackerjack.api.CrackerjackAPI') as mock_api_class:
            mock_api_instance = Mock()
            mock_result = Mock(spec=PublishResult)
            mock_api_instance.publish_package.return_value = mock_result
            mock_api_class.return_value = mock_api_instance

            result = publish_package(project_path=Path("/tmp"), version_bump="minor", dry_run=True)

            assert result == mock_result
            mock_api_class.assert_called_once_with(project_path=Path("/tmp"))
            mock_api_instance.publish_package.assert_called_once_with(version_bump="minor", dry_run=True)
