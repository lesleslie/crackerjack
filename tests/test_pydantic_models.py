"""Tests for Pydantic models that replace dataclasses."""

import pytest
from crackerjack.models.pydantic_models import (
    CleaningConfig,
    HookConfig,
    TestConfig,
    PublishConfig,
    GitConfig,
    AIConfig,
    ExecutionConfig,
    ProgressConfig,
    CleanupConfig,
    AdvancedConfig,
    MCPServerConfig,
    ZubanLSPConfig,
    WorkflowOptions,
    ExecutionResult,
    ParallelExecutionResult
)


class TestPydanticModels:
    """Test cases for Pydantic models."""

    def test_cleaning_config_creation(self):
        """Test CleaningConfig creation."""
        config = CleaningConfig(
            clean=True,
            update_docs=False,
            targets=["path1", "path2"]
        )
        assert config.clean == True
        assert config.update_docs == False
        assert config.targets == ["path1", "path2"]

    def test_hook_config_creation(self):
        """Test HookConfig creation."""
        config = HookConfig(
            skip_hooks=True,
            enable_pyrefly=False
        )
        assert config.skip_hooks == True
        assert config.enable_pyrefly == False

    def test_test_config_creation(self):
        """Test TestConfig creation."""
        config = TestConfig(
            test=True,
            benchmark=True,
            test_workers=4
        )
        assert config.test == True
        assert config.benchmark == True
        assert config.test_workers == 4

    def test_publish_config_creation(self):
        """Test PublishConfig creation."""
        config = PublishConfig(
            publish="minor",
            cleanup_pypi=True
        )
        assert config.publish == "minor"
        assert config.cleanup_pypi == True

    def test_git_config_creation(self):
        """Test GitConfig creation."""
        config = GitConfig(
            commit=True,
            create_pr=False
        )
        assert config.commit == True
        assert config.create_pr == False

    def test_ai_config_creation(self):
        """Test AIConfig creation."""
        config = AIConfig(
            ai_agent=True,
            max_iterations=10
        )
        assert config.ai_agent == True
        assert config.max_iterations == 10

    def test_execution_config_creation(self):
        """Test ExecutionConfig creation."""
        config = ExecutionConfig(
            interactive=False,
            verbose=True
        )
        assert config.interactive == False
        assert config.verbose == True

    def test_progress_config_creation(self):
        """Test ProgressConfig creation."""
        config = ProgressConfig(
            track_progress=True,
            resume_from="step2"
        )
        assert config.track_progress == True
        assert config.resume_from == "step2"

    def test_cleanup_config_creation(self):
        """Test CleanupConfig creation."""
        config = CleanupConfig(
            auto_cleanup=False,
            keep_debug_logs=10
        )
        assert config.auto_cleanup == False
        assert config.keep_debug_logs == 10

    def test_advanced_config_creation(self):
        """Test AdvancedConfig creation."""
        config = AdvancedConfig(
            enabled=True,
            license_key="test-key"
        )
        assert config.enabled == True
        assert config.license_key == "test-key"

    def test_mcp_server_config_creation(self):
        """Test MCPServerConfig creation."""
        config = MCPServerConfig(
            http_port=9999,
            http_enabled=True
        )
        assert config.http_port == 9999
        assert config.http_enabled == True

    def test_zuban_lsp_config_creation(self):
        """Test ZubanLSPConfig creation."""
        config = ZubanLSPConfig(
            enabled=False,
            port=7777
        )
        assert config.enabled == False
        assert config.port == 7777

    def test_workflow_options_creation(self):
        """Test WorkflowOptions creation."""
        options = WorkflowOptions()
        assert options.cleaning.clean == True  # default value
        assert options.testing.test == False   # default value
        assert isinstance(options.hooks, HookConfig)

    def test_workflow_options_property_access(self):
        """Test WorkflowOptions property access."""
        options = WorkflowOptions()
        assert options.clean == options.cleaning.clean

        # Test property setters
        options.clean = False
        assert options.cleaning.clean == False

    def test_execution_result_creation(self):
        """Test ExecutionResult creation."""
        result = ExecutionResult(
            operation_id="test-op",
            success=True,
            duration_seconds=1.5
        )
        assert result.operation_id == "test-op"
        assert result.success == True
        assert result.duration_seconds == 1.5

    def test_parallel_execution_result_creation(self):
        """Test ParallelExecutionResult creation."""
        execution_result = ExecutionResult(
            operation_id="test-op",
            success=True,
            duration_seconds=1.5
        )

        parallel_result = ParallelExecutionResult(
            group_name="test-group",
            total_operations=5,
            successful_operations=4,
            failed_operations=1,
            total_duration_seconds=10.0,
            results=[execution_result]
        )

        assert parallel_result.group_name == "test-group"
        assert parallel_result.success_rate == 0.8  # 4/5
        assert parallel_result.overall_success == False  # has 1 failure

    def test_model_validation(self):
        """Test Pydantic model validation."""
        # Test basic validation (Pydantic will validate types automatically)
        config = HookConfig(
            skip_hooks="not_a_bool"  # This should be converted or raise an error depending on settings
        )
        # With strict validation, this would fail, but Pydantic tries to convert types
        assert isinstance(config.skip_hooks, bool)

    def test_model_dump(self):
        """Test model serialization."""
        config = CleaningConfig(
            clean=True,
            targets=["path1", "path2"]
        )
        data = config.model_dump()
        assert "clean" in data
        assert "targets" in data
        assert data["clean"] == True
        assert data["targets"] == ["path1", "path2"]

    def test_workflow_options_to_dict(self):
        """Test WorkflowOptions to_dict method."""
        options = WorkflowOptions()
        data = options.to_dict()

        assert "cleaning" in data
        assert "hooks" in data
        assert isinstance(data["cleaning"], dict)
        assert isinstance(data["hooks"], dict)
