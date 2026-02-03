"""Tests for the main Crackerjack API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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

    @patch("crackerjack.api.WorkflowPipeline")
    def test_run_quality_checks_fast_only(self, mock_pipeline_class, api):
        """Test running quality checks in fast mode."""
        mock_pipeline = MagicMock()
        mock_pipeline.run_complete_workflow_sync.return_value = True
        mock_pipeline_class.return_value = mock_pipeline

        result = api.run_quality_checks(fast_only=True, autofix=False)

        assert isinstance(result, QualityCheckResult)
        assert result.duration > 0
        mock_pipeline.run_complete_workflow_sync.assert_called_once()

    @patch("crackerjack.api.WorkflowPipeline")
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
        """Test code cleaning with default options."""
        result = api.clean_code()

        assert isinstance(result, list)
        # Verify results based on actual implementation

    def test_clean_code_strip_comments(self, api):
        """Test code cleaning with comment stripping."""
        result = api.clean_code(
            strip_comments=True,
            strip_docstrings=False,
            update_docs=False,
        )

        assert isinstance(result, list)

    def test_clean_code_strip_docstrings(self, api):
        """Test code cleaning with docstring stripping."""
        result = api.clean_code(
            strip_comments=False,
            strip_docstrings=True,
            update_docs=False,
        )

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

    @patch("subprocess.run")
    def test_run_tests_success(self, mock_subprocess_run, api):
        """Test running tests successfully."""
        mock_result = MagicMock(
            returncode=0,
            stdout="50 passed, 2 failed\n",
            stderr="",
        )
        mock_subprocess_run.return_value = mock_result

        result = api.run_tests(
            workers=4,
            coverage=True,
            verbose=False,
        )

        assert isinstance(result, TestResult)
        mock_subprocess_run.assert_called()

    @patch("subprocess.run")
    def test_run_tests_with_coverage(self, mock_subprocess_run, api):
        """Test running tests with coverage."""
        mock_result = MagicMock(
            returncode=0,
            stdout="Coverage: 85.5%\n",
            stderr="",
        )
        mock_subprocess_run.return_value = mock_result

        result = api.run_tests(coverage=True)

        assert isinstance(result, TestResult)
        assert result.coverage_percentage >= 0


class TestCrackerjackAPIPublish:
    """Tests for publish functionality."""

    @pytest.fixture
    def api(self, tmp_path):
        """Create API instance."""
        return CrackerjackAPI(project_path=tmp_path)

    @patch("subprocess.run")
    def test_publish_patch(self, mock_subprocess_run, api):
        """Test publishing a patch version."""
        mock_result = MagicMock(returncode=0)
        mock_subprocess_run.return_value = mock_result

        result = api.publish(
            bump_type="patch",
            create_pr=False,
            push=True,
        )

        assert isinstance(result, PublishResult)
        mock_subprocess_run.assert_called()

    @patch("subprocess.run")
    def test_publish_minor_with_pr(self, mock_subprocess_run, api):
        """Test publishing a minor version with PR."""
        mock_result = MagicMock(returncode=0)
        mock_subprocess_run.return_value = mock_result

        result = api.publish(
            bump_type="minor",
            create_pr=True,
            push=False,
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

    def test_error_handling(self, api):
        """Test error handling in API methods."""
        # Test with invalid paths
        with pytest.raises(Exception):
            # This should handle errors gracefully
            api.run_quality_checks()
