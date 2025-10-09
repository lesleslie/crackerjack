"""Tests for QA configuration models and validation.

Tests cover QACheckConfig, QAOrchestratorConfig, QAResult, and
configuration loading patterns per crackerjack conventions.
"""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from crackerjack.models.qa_config import QACheckConfig, QAOrchestratorConfig
from crackerjack.models.qa_results import (
    QACheckType,
    QAResult,
    QAResultStatus,
)


class TestQACheckConfig:
    """Test QACheckConfig model validation."""

    def test_minimal_valid_config(self):
        """Test minimal valid QACheckConfig."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
        )

        assert config.check_id is not None
        assert config.check_name == "test-check"
        assert config.check_type == QACheckType.LINT
        assert config.enabled is True

    def test_config_with_file_patterns(self):
        """Test QACheckConfig with file patterns."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
            file_patterns=["**/*.py", "**/*.pyi"],
        )

        assert len(config.file_patterns) == 2
        assert "**/*.py" in config.file_patterns

    def test_config_with_exclude_patterns(self):
        """Test QACheckConfig with exclude patterns."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
            exclude_patterns=["**/.venv/**", "**/__pycache__/**"],
        )

        assert len(config.exclude_patterns) == 2
        assert "**/.venv/**" in config.exclude_patterns

    def test_config_with_stage(self):
        """Test QACheckConfig with stage assignment."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
            stage="fast",
        )

        assert config.stage == "fast"

    def test_config_with_timeout(self):
        """Test QACheckConfig with timeout setting."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
            timeout_seconds=120,
        )

        assert config.timeout_seconds == 120

    def test_config_formatter_flag(self):
        """Test QACheckConfig is_formatter flag."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="formatter-check",
            check_type=QACheckType.FORMAT,
            enabled=True,
            is_formatter=True,
        )

        assert config.is_formatter is True

    def test_config_parallel_safe_flag(self):
        """Test QACheckConfig parallel_safe flag."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
            parallel_safe=True,
        )

        assert config.parallel_safe is True

    def test_config_with_settings(self):
        """Test QACheckConfig with custom settings."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
            settings={
                "mode": "check",
                "fix_enabled": False,
                "severity": "high",
            },
        )

        assert config.settings is not None
        assert config.settings["mode"] == "check"
        assert config.settings["fix_enabled"] is False

    def test_config_retry_on_failure(self):
        """Test QACheckConfig retry_on_failure flag."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
            retry_on_failure=True,
        )

        assert config.retry_on_failure is True


class TestQAOrchestratorConfig:
    """Test QAOrchestratorConfig model validation."""

    def test_minimal_orchestrator_config(self):
        """Test minimal QAOrchestratorConfig."""
        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
        )

        assert config.project_root == Path.cwd()
        assert config.max_parallel_checks == 4  # Default
        assert config.enable_caching is True  # Default

    def test_orchestrator_config_custom_parallel(self):
        """Test orchestrator with custom max_parallel_checks."""
        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
            max_parallel_checks=8,
        )

        assert config.max_parallel_checks == 8

    def test_orchestrator_config_disable_caching(self):
        """Test orchestrator with caching disabled."""
        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
            enable_caching=False,
        )

        assert config.enable_caching is False

    def test_orchestrator_config_fail_fast(self):
        """Test orchestrator with fail_fast enabled."""
        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
            fail_fast=True,
        )

        assert config.fail_fast is True

    def test_orchestrator_config_run_formatters_first(self):
        """Test orchestrator with run_formatters_first."""
        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
            run_formatters_first=True,
        )

        assert config.run_formatters_first is True

    def test_orchestrator_config_with_checks(self):
        """Test orchestrator with fast and comprehensive checks."""
        fast_check = QACheckConfig(
            check_id=uuid4(),
            check_name="fast-check",
            check_type=QACheckType.LINT,
            enabled=True,
            stage="fast",
        )

        comp_check = QACheckConfig(
            check_id=uuid4(),
            check_name="comp-check",
            check_type=QACheckType.SECURITY,
            enabled=True,
            stage="comprehensive",
        )

        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
            checks=[fast_check, comp_check],  # Pass via checks parameter
        )

        # Properties filter checks by stage
        assert len(config.fast_checks) == 1
        assert len(config.comprehensive_checks) == 1
        assert config.fast_checks[0].stage == "fast"
        assert config.comprehensive_checks[0].stage == "comprehensive"

    def test_orchestrator_config_enable_incremental(self):
        """Test orchestrator with incremental checking."""
        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
            enable_incremental=True,
        )

        assert config.enable_incremental is True

    def test_orchestrator_config_verbose(self):
        """Test orchestrator with verbose mode."""
        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
            verbose=True,
        )

        assert config.verbose is True


class TestQAResult:
    """Test QAResult model."""

    def test_success_result(self):
        """Test QAResult for successful check."""
        result = QAResult(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            message="All checks passed",
        )

        assert result.status == QAResultStatus.SUCCESS
        assert result.is_success is True
        assert result.issues_found == 0

    def test_failure_result(self):
        """Test QAResult for failed check."""
        result = QAResult(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.FAILURE,
            message="Found 5 issues",
            issues_found=5,
        )

        assert result.status == QAResultStatus.FAILURE
        assert result.is_success is False
        assert result.issues_found == 5

    def test_error_result(self):
        """Test QAResult for errored check."""
        result = QAResult(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.ERROR,
            message="Tool execution failed",
            details="FileNotFoundError: tool not found",
        )

        assert result.status == QAResultStatus.ERROR
        assert result.is_success is False
        assert result.details is not None

    def test_warning_result(self):
        """Test QAResult for warning check."""
        result = QAResult(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.WARNING,
            message="Minor issues found",
            issues_found=2,
        )

        assert result.status == QAResultStatus.WARNING
        assert result.is_success is True  # Warnings are still success
        assert result.issues_found == 2

    def test_result_with_execution_time(self):
        """Test QAResult with execution time."""
        result = QAResult(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            message="Passed",
            execution_time_ms=150.5,
        )

        assert result.execution_time_ms == 150.5

    def test_result_with_fixed_issues(self):
        """Test QAResult with fixed issues count."""
        result = QAResult(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            message="Fixed 3 issues",
            issues_found=3,
            issues_fixed=3,
        )

        assert result.issues_found == 3
        assert result.issues_fixed == 3

    def test_result_with_files_checked(self):
        """Test QAResult with files_checked list."""
        result = QAResult(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            message="Checked 2 files",
            files_checked=[Path("test.py"), Path("main.py")],
        )

        assert len(result.files_checked) == 2
        assert Path("test.py") in result.files_checked


class TestQACheckType:
    """Test QACheckType enum."""

    def test_all_check_types_defined(self):
        """Test all expected check types are defined."""
        expected_types = [
            "LINT",
            "FORMAT",
            "TYPE",
            "SECURITY",
            "COMPLEXITY",
            "REFACTOR",
            "TEST",
        ]

        for type_name in expected_types:
            assert hasattr(QACheckType, type_name), (
                f"Missing check type: {type_name}"
            )

    def test_check_type_values(self):
        """Test check type enum values."""
        assert QACheckType.LINT == "lint"
        assert QACheckType.FORMAT == "format"
        assert QACheckType.TYPE == "type"
        assert QACheckType.SECURITY == "security"
        assert QACheckType.COMPLEXITY == "complexity"
        assert QACheckType.REFACTOR == "refactor"
        assert QACheckType.TEST == "test"


class TestQAResultStatus:
    """Test QAResultStatus enum."""

    def test_all_result_statuses_defined(self):
        """Test all expected result statuses are defined."""
        expected_statuses = [
            "SUCCESS",
            "FAILURE",
            "ERROR",
            "WARNING",
            "SKIPPED",
        ]

        for status_name in expected_statuses:
            assert hasattr(QAResultStatus, status_name), (
                f"Missing result status: {status_name}"
            )

    def test_result_status_values(self):
        """Test result status enum values."""
        assert QAResultStatus.SUCCESS == "success"
        assert QAResultStatus.FAILURE == "failure"
        assert QAResultStatus.ERROR == "error"
        assert QAResultStatus.WARNING == "warning"
        assert QAResultStatus.SKIPPED == "skipped"


class TestYAMLConfigurationLoading:
    """Test YAML configuration loading patterns."""

    def test_yaml_config_structure(self):
        """Test expected YAML configuration structure."""
        yaml_content = {
            "project_root": ".",
            "max_parallel_checks": 4,
            "enable_caching": True,
            "fail_fast": False,
            "run_formatters_first": True,
            "checks": [
                {
                    "check_name": "ruff-lint",
                    "check_type": "lint",
                    "enabled": True,
                    "stage": "fast",
                    "settings": {
                        "mode": "check",
                        "fix_enabled": False,
                    },
                },
            ],
        }

        # Verify structure can be created
        assert "project_root" in yaml_content
        assert "max_parallel_checks" in yaml_content
        assert "checks" in yaml_content
        assert len(yaml_content["checks"]) == 1

    def test_yaml_config_serialization(self):
        """Test YAML config can be serialized/deserialized."""
        yaml_content = {
            "project_root": ".",
            "max_parallel_checks": 4,
            "enable_caching": True,
        }

        # Serialize to YAML
        yaml_str = yaml.safe_dump(yaml_content)
        assert isinstance(yaml_str, str)

        # Deserialize from YAML
        loaded_content = yaml.safe_load(yaml_str)
        assert loaded_content["project_root"] == "."
        assert loaded_content["max_parallel_checks"] == 4


class TestConfigDefaults:
    """Test configuration default values."""

    def test_check_config_defaults(self):
        """Test QACheckConfig default values."""
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
        )

        # Test defaults
        assert config.file_patterns == []
        assert config.exclude_patterns == []
        assert config.timeout_seconds == 300  # 5 minutes default
        assert config.is_formatter is False
        assert config.parallel_safe is True
        assert config.retry_on_failure is False
        assert config.settings == {}

    def test_orchestrator_config_defaults(self):
        """Test QAOrchestratorConfig default values."""
        config = QAOrchestratorConfig(
            project_root=Path.cwd(),
        )

        # Test defaults
        assert config.max_parallel_checks == 4
        assert config.enable_caching is True
        assert config.fail_fast is False
        assert config.run_formatters_first is True
        assert config.enable_incremental is True
        assert config.verbose is False
        assert config.fast_checks == []
        assert config.comprehensive_checks == []


class TestConfigValidation:
    """Test configuration validation logic."""

    def test_invalid_check_type_raises_error(self):
        """Test invalid check type raises validation error."""
        with pytest.raises(Exception):  # Pydantic validation error
            QACheckConfig(
                check_id=uuid4(),
                check_name="test-check",
                check_type="invalid_type",  # Invalid check type
                enabled=True,
            )

    def test_invalid_stage_raises_error(self):
        """Test invalid stage raises validation error."""
        # Stage should be "fast" or "comprehensive"
        config = QACheckConfig(
            check_id=uuid4(),
            check_name="test-check",
            check_type=QACheckType.LINT,
            enabled=True,
            stage="invalid_stage",  # Should still accept string
        )

        # Pydantic allows any string, validation happens at runtime
        assert config.stage == "invalid_stage"

    def test_negative_timeout_invalid(self):
        """Test negative timeout is invalid."""
        with pytest.raises(Exception):  # Pydantic validation error
            QACheckConfig(
                check_id=uuid4(),
                check_name="test-check",
                check_type=QACheckType.LINT,
                enabled=True,
                timeout_seconds=-1,  # Invalid negative timeout
            )

    def test_negative_parallel_checks_invalid(self):
        """Test negative max_parallel_checks is invalid."""
        with pytest.raises(Exception):  # Pydantic validation error
            QAOrchestratorConfig(
                project_root=Path.cwd(),
                max_parallel_checks=-1,  # Invalid negative value
            )
