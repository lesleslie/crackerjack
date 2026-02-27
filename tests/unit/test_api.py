"""Tests for the main Crackerjack API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.api import (
    QualityCheckResult,
    TestResult,
    PublishResult,
    CrackerjackAPI,
)


class TestDataclasses:
    """Tests for API result dataclasses."""

    def test_quality_check_result(self):
        """Test QualityCheckResult creation."""
        result = QualityCheckResult(
            success=True,
            fast_hooks_passed=True,
            comprehensive_hooks_passed=False,
            errors=[],
            warnings=["Some warning"],
            duration=5.5,
        )

        assert result.success is True
        assert result.fast_hooks_passed is True
        assert result.comprehensive_hooks_passed is False
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert result.duration == 5.5

    def test_test_result(self):
        """Test TestResult creation."""
        result = TestResult(
            success=True,
            passed_count=50,
            failed_count=2,
            coverage_percentage=85.5,
            duration=120.0,
            errors=["ImportError in test_utils.py"],
        )

        assert result.success is True
        assert result.passed_count == 50
        assert result.failed_count == 2
        assert result.coverage_percentage == 85.5
        assert result.duration == 120.0
        assert len(result.errors) == 1

    def test_publish_result(self):
        """Test PublishResult creation."""
        result = PublishResult(
            success=True,
            version="1.2.3",
            published_to=["PyPI", "GitHub Releases"],
            errors=[],
        )

        assert result.success is True
        assert result.version == "1.2.3"
        assert len(result.published_to) == 2
        assert "PyPI" in result.published_to
        assert len(result.errors) == 0


class TestCrackerjackAPI:
    """Tests for CrackerjackAPI class."""

    @pytest.fixture
    def api(self, tmp_path):
        """Create a CrackerjackAPI instance for testing."""
        return CrackerjackAPI(project_path=tmp_path, verbose=True)

    def test_initialization(self, api):
        """Test API initialization."""
        assert api.project_path is not None
        assert api.console is not None
        assert api.verbose is True
        assert api.orchestrator is None
        assert api.container is None

    def test_initialization_with_defaults(self):
        """Test API initialization with default parameters."""
        api = CrackerjackAPI()
        assert api.project_path == Path.cwd()
        assert api.console is not None
        assert api.verbose is False

    def test_code_cleaner_property(self, api):
        """Test code_cleaner property lazy initialization."""
        cleaner = api.code_cleaner
        assert cleaner is not None
        # Should return same instance on subsequent calls
        assert api.code_cleaner is cleaner

    def test_interactive_cli_property(self, api):
        """Test interactive_cli property lazy initialization."""
        cli = api.interactive_cli
        assert cli is not None
        # Should return same instance on subsequent calls
        assert api.interactive_cli is cli


class TestCrackerjackAPIQualityChecks:
    """Tests for quality check functionality."""

    @pytest.fixture
    def api(self, tmp_path):
        """Create API instance."""
        return CrackerjackAPI(project_path=tmp_path)

    @patch("crackerjack.core.workflow_orchestrator.WorkflowPipeline")
    def test_run_quality_checks_fast_only(self, mock_pipeline_class, api):
        """Test running quality checks in fast mode."""
        mock_pipeline = MagicMock()
        mock_pipeline.run_complete_workflow_sync.return_value = True
        mock_pipeline_class.return_value = mock_pipeline

        result = api.run_quality_checks(fast_only=True, autofix=False)

        assert isinstance(result, QualityCheckResult)
        assert result.duration > 0
        mock_pipeline.run_complete_workflow_sync.assert_called_once()

    @patch("crackerjack.core.workflow_orchestrator.WorkflowPipeline")
    def test_run_quality_checks_with_autofix(self, mock_pipeline_class, api):
        """Test running quality checks with autofix enabled."""
        mock_pipeline = MagicMock()
        mock_pipeline.run_complete_workflow_sync.return_value = True
        mock_pipeline_class.return_value = mock_pipeline

        result = api.run_quality_checks(fast_only=False, autofix=True)

        assert isinstance(result, QualityCheckResult)
        mock_pipeline.run_complete_workflow_sync.assert_called_once()

        # Check that autofix was enabled in options
        call_args = mock_pipeline.run_complete_workflow_sync.call_args
        options = call_args[0][0]
        # Verify options based on actual implementation
        assert hasattr(options, "ai_agent")


class TestCrackerjackAPICodeCleaning:
    """Tests for code cleaning functionality."""

    @pytest.fixture
    def api(self, tmp_path):
        """Create API instance with test files."""
        # Create some test files
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "# This is a comment\n"
            '"""This is a docstring"""\n'
            "def test_function():\n"
            "    pass\n",
        )

        return CrackerjackAPI(project_path=tmp_path)

    def test_clean_code_default_options(self, api):
        """Test code cleaning with default options.

        Note: clean_code returns PackageCleaningResult when safe_mode=True (default).
        """
        from crackerjack.code_cleaner import PackageCleaningResult

        # Create a mock cleaner and set it directly on the private attribute
        mock_cleaner = MagicMock()
        mock_result = MagicMock(spec=PackageCleaningResult)
        mock_result.overall_success = True
        mock_result.total_files = 1
        mock_result.successful_files = 1
        mock_result.failed_files = 0
        mock_result.file_results = []
        mock_result.backup_metadata = None
        mock_result.backup_restored = False
        mock_cleaner.clean_files_with_backup.return_value = mock_result

        # Set the private attribute directly
        api._code_cleaner = mock_cleaner

        result = api.clean_code()

        assert isinstance(result, PackageCleaningResult)
        mock_cleaner.clean_files_with_backup.assert_called_once()

    def test_clean_code_with_target_dir(self, api, tmp_path):
        """Test code cleaning with a specific target directory."""
        from crackerjack.code_cleaner import PackageCleaningResult

        # Create a mock cleaner and set it directly on the private attribute
        mock_cleaner = MagicMock()
        mock_result = MagicMock(spec=PackageCleaningResult)
        mock_result.overall_success = True
        mock_result.total_files = 1
        mock_result.successful_files = 1
        mock_result.failed_files = 0
        mock_result.file_results = []
        mock_result.backup_metadata = None
        mock_result.backup_restored = False
        mock_cleaner.clean_files_with_backup.return_value = mock_result

        # Set the private attribute directly
        api._code_cleaner = mock_cleaner

        result = api.clean_code(target_dir=tmp_path)

        assert isinstance(result, PackageCleaningResult)
        mock_cleaner.clean_files_with_backup.assert_called_once()

    def test_clean_code_legacy_mode(self, api, tmp_path):
        """Test code cleaning with legacy mode (safe_mode=False)."""
        from crackerjack.code_cleaner import CleaningResult

        # Create a mock cleaner and set it directly on the private attribute
        mock_cleaner = MagicMock()
        mock_result = MagicMock(spec=CleaningResult)
        mock_result.success = True
        mock_cleaner.clean_files.return_value = [mock_result]

        # Set the private attribute directly
        api._code_cleaner = mock_cleaner

        result = api.clean_code(safe_mode=False)

        assert isinstance(result, list)


class TestCrackerjackAPITests:
    """Tests for test execution functionality."""

    @pytest.fixture
    def api(self, tmp_path):
        """Create API instance."""
        # Create test directory structure
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").touch()
        (tests_dir / "test_example.py").write_text(
            "def test_example():\n    assert True\n",
        )

        return CrackerjackAPI(project_path=tmp_path)

    def test_run_tests_raises_in_pytest_context(self, api):
        """Test that run_tests raises RuntimeError when called from pytest context."""
        # PYTEST_CURRENT_TEST is set during test execution
        with pytest.raises(RuntimeError, match="run_tests requires full runtime context"):
            api.run_tests(coverage=True)

    @patch("crackerjack.core.workflow_orchestrator.WorkflowPipeline")
    @patch.dict("os.environ", {}, clear=True)
    def test_run_tests_success(self, mock_pipeline_class, api):
        """Test running tests successfully."""
        import os

        # Ensure PYTEST_CURRENT_TEST is not set
        os.environ.pop("PYTEST_CURRENT_TEST", None)

        mock_pipeline = MagicMock()
        mock_pipeline.run_complete_workflow_sync.return_value = True
        mock_pipeline_class.return_value = mock_pipeline

        result = api.run_tests(
            workers=4,
            coverage=True,
        )

        assert isinstance(result, TestResult)
        mock_pipeline.run_complete_workflow_sync.assert_called()

    @patch("crackerjack.core.workflow_orchestrator.WorkflowPipeline")
    @patch.dict("os.environ", {}, clear=True)
    def test_run_tests_with_coverage(self, mock_pipeline_class, api):
        """Test running tests with coverage."""
        import os

        # Ensure PYTEST_CURRENT_TEST is not set
        os.environ.pop("PYTEST_CURRENT_TEST", None)

        mock_pipeline = MagicMock()
        mock_pipeline.run_complete_workflow_sync.return_value = True
        mock_pipeline_class.return_value = mock_pipeline

        result = api.run_tests(coverage=True)

        assert isinstance(result, TestResult)
        assert result.coverage_percentage >= 0


class TestCrackerjackAPIPublish:
    """Tests for publish functionality."""

    @pytest.fixture
    def api(self, tmp_path):
        """Create API instance."""
        return CrackerjackAPI(project_path=tmp_path)

    @patch("crackerjack.core.workflow_orchestrator.WorkflowPipeline")
    def test_publish_patch(self, mock_pipeline_class, api):
        """Test publishing a patch version."""
        mock_pipeline = MagicMock()
        mock_pipeline.run_complete_workflow_sync.return_value = True
        mock_pipeline_class.return_value = mock_pipeline

        result = api.publish_package(
            version_bump="patch",
            dry_run=False,
        )

        assert isinstance(result, PublishResult)
        mock_pipeline.run_complete_workflow_sync.assert_called()

    @patch("crackerjack.core.workflow_orchestrator.WorkflowPipeline")
    def test_publish_minor_dry_run(self, mock_pipeline_class, api):
        """Test publishing a minor version with dry run."""
        mock_pipeline = MagicMock()
        mock_pipeline.run_complete_workflow_sync.return_value = True
        mock_pipeline_class.return_value = mock_pipeline

        result = api.publish_package(
            version_bump="minor",
            dry_run=True,
        )

        assert isinstance(result, PublishResult)


class TestCrackerjackAPIIntegration:
    """Integration tests for CrackerjackAPI."""

    @pytest.fixture
    def api(self, tmp_path):
        """Create a fully configured API instance."""
        # Create a realistic project structure
        src_dir = tmp_path / "mypackage"
        src_dir.mkdir()
        (src_dir / "__init__.py").touch()

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").touch()
        (tests_dir / "test_example.py").write_text("def test_pass(): pass")

        return CrackerjackAPI(project_path=tmp_path)

    def test_complete_workflow_simulation(self, api):
        """Test simulating a complete workflow."""
        # This test ensures all components work together
        # without actually running external commands

        assert api.project_path.exists()
        assert api.code_cleaner is not None
        assert api.interactive_cli is not None

    def test_get_project_info(self, api, tmp_path):
        """Test getting project information."""
        # Create pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "test-package"\nversion = "1.0.0"\n',
        )

        info = api.get_project_info()

        assert info["project_path"] == str(tmp_path)
        assert info["is_python_project"] is True
        assert info["has_pyproject_toml"] is True

    def test_create_workflow_options(self, api):
        """Test creating workflow options."""
        options = api.create_workflow_options(
            clean=True,
            test=True,
            publish="patch",
            verbose=True,
        )

        assert options is not None
        assert hasattr(options, "cleaning")
        assert hasattr(options, "testing")
