"""Tests for pydantic_models module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from crackerjack.models.pydantic_models import (
    AdvancedConfig,
    AIConfig,
    CleaningConfig,
    CleanupConfig,
    ExecutionConfig,
    ExecutionResult,
    GitConfig,
    HookConfig,
    MCPServerConfig,
    ParallelExecutionResult,
    ProgressConfig,
    PublishConfig,
    TestConfig,
    WorkflowOptions,
    ZubanLSPConfig,
)


class TestCleaningConfig:
    """Tests for CleaningConfig Pydantic model."""

    def test_minimal_cleaning_config(self) -> None:
        """Verify minimal CleaningConfig creation."""
        config = CleaningConfig()
        assert config.clean is True
        assert config.update_docs is False
        assert config.force_update_docs is False
        assert config.compress_docs is False
        assert config.auto_compress_docs is False
        assert config.targets == []

    def test_cleaning_config_full(self) -> None:
        """Verify CleaningConfig with all fields."""
        config = CleaningConfig(
            clean=False,
            update_docs=True,
            force_update_docs=True,
            compress_docs=True,
            auto_compress_docs=True,
            targets=["docs/", "README.md"],
        )
        assert config.clean is False
        assert config.update_docs is True
        assert config.force_update_docs is True
        assert config.compress_docs is True
        assert config.auto_compress_docs is True
        assert config.targets == ["docs/", "README.md"]

    def test_cleaning_config_strip_code_property_getter(self) -> None:
        """Verify strip_code property getter."""
        config = CleaningConfig(clean=True)
        assert config.strip_code is True

    def test_cleaning_config_strip_code_property_setter(self) -> None:
        """Verify strip_code property setter."""
        config = CleaningConfig(clean=True)
        config.strip_code = False
        assert config.clean is False
        assert config.strip_code is False

    def test_cleaning_config_from_settings(self) -> None:
        """Verify CleaningConfig.from_settings()."""
        settings = MagicMock()
        settings.clean = False
        settings.update_docs = True
        settings.force_update_docs = True
        settings.compress_docs = False
        settings.auto_compress_docs = False
        settings.targets = ["file1", "file2"]

        config = CleaningConfig.from_settings(settings)
        assert config.clean is False
        assert config.update_docs is True
        assert config.force_update_docs is True
        assert config.compress_docs is False
        assert config.auto_compress_docs is False
        assert config.targets == ["file1", "file2"]

    def test_cleaning_config_from_settings_missing_attrs(self) -> None:
        """Verify from_settings with missing attributes uses defaults."""
        settings = MagicMock(spec=[])
        config = CleaningConfig.from_settings(settings)
        assert config.clean is True
        assert config.update_docs is False
        assert config.targets == []


class TestHookConfig:
    """Tests for HookConfig Pydantic model."""

    def test_minimal_hook_config(self) -> None:
        """Verify minimal HookConfig creation."""
        config = HookConfig()
        assert config.skip_hooks is False
        assert config.experimental_hooks is False
        assert config.enable_pyrefly is False
        assert config.enable_ty is False
        assert config.enable_lsp_optimization is False

    def test_hook_config_full(self) -> None:
        """Verify HookConfig with all fields."""
        config = HookConfig(
            skip_hooks=True,
            experimental_hooks=True,
            enable_pyrefly=True,
            enable_ty=True,
            enable_lsp_optimization=True,
        )
        assert config.skip_hooks is True
        assert config.experimental_hooks is True
        assert config.enable_pyrefly is True
        assert config.enable_ty is True
        assert config.enable_lsp_optimization is True

    def test_hook_config_coerce_bool_true_strings(self) -> None:
        """Verify bool coercion for truthy strings."""
        for true_val in ["1", "true", "True", "TRUE", "yes", "YES", "y", "Y", "on", "ON"]:
            config = HookConfig(skip_hooks=true_val)  # ty: ignore[invalid-argument-type]
            assert config.skip_hooks is True

    def test_hook_config_coerce_bool_false_strings(self) -> None:
        """Verify bool coercion for falsy strings."""
        for false_val in ["0", "false", "no", "off", ""]:
            config = HookConfig(skip_hooks=false_val)  # ty: ignore[invalid-argument-type]
            assert config.skip_hooks is False

    def test_hook_config_coerce_bool_with_whitespace(self) -> None:
        """Verify bool coercion handles whitespace."""
        config = HookConfig(skip_hooks="  true  ")  # ty: ignore[invalid-argument-type]
        assert config.skip_hooks is True

        config = HookConfig(skip_hooks="  false  ")  # ty: ignore[invalid-argument-type]
        assert config.skip_hooks is False

    def test_hook_config_coerce_bool_from_int(self) -> None:
        """Verify bool coercion from integers."""
        config = HookConfig(skip_hooks=1)  # ty: ignore[invalid-argument-type]
        assert config.skip_hooks is True

        config = HookConfig(skip_hooks=0)  # ty: ignore[invalid-argument-type]
        assert config.skip_hooks is False

    def test_hook_config_from_settings(self) -> None:
        """Verify HookConfig.from_settings()."""
        settings = MagicMock()
        settings.skip_hooks = False
        settings.experimental_hooks = True
        settings.enable_pyrefly = False
        settings.enable_ty = True
        settings.enable_lsp_optimization = False

        config = HookConfig.from_settings(settings)
        assert config.skip_hooks is False
        assert config.experimental_hooks is True
        assert config.enable_pyrefly is False
        assert config.enable_ty is True
        assert config.enable_lsp_optimization is False


class TestTestConfig:
    """Tests for TestConfig Pydantic model."""

    def test_minimal_test_config(self) -> None:
        """Verify minimal TestConfig creation."""
        config = TestConfig()
        assert config.test is False
        assert config.benchmark is False
        assert config.benchmark_regression is False
        assert config.benchmark_regression_threshold == 0.1
        assert config.test_workers == 0
        assert config.test_timeout == 0
        assert config.xcode_tests is False
        assert config.xcode_project == "app/MdInjectApp/MdInjectApp.xcodeproj"
        assert config.xcode_scheme == "MdInjectApp"
        assert config.xcode_configuration == "Debug"
        assert config.xcode_destination == "platform=macOS"

    def test_test_config_full(self) -> None:
        """Verify TestConfig with all fields."""
        config = TestConfig(
            test=True,
            benchmark=True,
            benchmark_regression=True,
            benchmark_regression_threshold=0.5,
            test_workers=4,
            test_timeout=300,
            xcode_tests=True,
            xcode_project="custom.xcodeproj",
            xcode_scheme="CustomScheme",
            xcode_configuration="Release",
            xcode_destination="platform=iOS",
        )
        assert config.test is True
        assert config.benchmark is True
        assert config.benchmark_regression is True
        assert config.benchmark_regression_threshold == 0.5
        assert config.test_workers == 4
        assert config.test_timeout == 300
        assert config.xcode_tests is True
        assert config.xcode_project == "custom.xcodeproj"
        assert config.xcode_scheme == "CustomScheme"
        assert config.xcode_configuration == "Release"
        assert config.xcode_destination == "platform=iOS"

    def test_test_config_run_tests_property_getter(self) -> None:
        """Verify run_tests property getter."""
        config = TestConfig(test=True)
        assert config.run_tests is True

    def test_test_config_run_tests_property_setter(self) -> None:
        """Verify run_tests property setter."""
        config = TestConfig(test=False)
        config.run_tests = True
        assert config.test is True
        assert config.run_tests is True

    def test_test_config_from_settings(self) -> None:
        """Verify TestConfig.from_settings()."""
        settings = MagicMock()
        settings.test = True
        settings.benchmark = False
        settings.benchmark_regression = True
        settings.benchmark_regression_threshold = 0.2
        settings.test_workers = 8
        settings.test_timeout = 600
        settings.xcode_tests = True
        settings.xcode_project = "test.xcodeproj"
        settings.xcode_scheme = "TestScheme"
        settings.xcode_configuration = "Debug"
        settings.xcode_destination = "platform=iOS,name=iPhone"

        config = TestConfig.from_settings(settings)
        assert config.test is True
        assert config.benchmark is False
        assert config.benchmark_regression is True
        assert config.benchmark_regression_threshold == 0.2
        assert config.test_workers == 8
        assert config.test_timeout == 600
        assert config.xcode_tests is True
        assert config.xcode_project == "test.xcodeproj"
        assert config.xcode_scheme == "TestScheme"


class TestPublishConfig:
    """Tests for PublishConfig Pydantic model."""

    def test_minimal_publish_config(self) -> None:
        """Verify minimal PublishConfig creation."""
        config = PublishConfig()
        assert config.publish is None
        assert config.bump is None
        assert config.all is None
        assert config.cleanup_pypi is False
        assert config.keep_releases == 10
        assert config.no_git_tags is False
        assert config.skip_version_check is False

    def test_publish_config_full(self) -> None:
        """Verify PublishConfig with all fields."""
        config = PublishConfig(
            publish="pypi",
            bump="minor",
            all="all",
            cleanup_pypi=True,
            keep_releases=20,
            no_git_tags=True,
            skip_version_check=True,
        )
        assert config.publish == "pypi"
        assert config.bump == "minor"
        assert config.all == "all"
        assert config.cleanup_pypi is True
        assert config.keep_releases == 20
        assert config.no_git_tags is True
        assert config.skip_version_check is True

    def test_publish_config_from_settings(self) -> None:
        """Verify PublishConfig.from_settings()."""
        settings = MagicMock()
        settings.publish = "testpypi"
        settings.bump = "patch"
        settings.all = None
        settings.cleanup_pypi = True
        settings.keep_releases = 15
        settings.no_git_tags = False
        settings.skip_version_check = True

        config = PublishConfig.from_settings(settings)
        assert config.publish == "testpypi"
        assert config.bump == "patch"
        assert config.cleanup_pypi is True
        assert config.keep_releases == 15


class TestGitConfig:
    """Tests for GitConfig Pydantic model."""

    def test_minimal_git_config(self) -> None:
        """Verify minimal GitConfig creation."""
        config = GitConfig()
        assert config.commit is False
        assert config.create_pr is False

    def test_git_config_full(self) -> None:
        """Verify GitConfig with all fields."""
        config = GitConfig(commit=True, create_pr=True)
        assert config.commit is True
        assert config.create_pr is True

    def test_git_config_from_settings(self) -> None:
        """Verify GitConfig.from_settings()."""
        settings = MagicMock()
        settings.commit = True
        settings.create_pr = False

        config = GitConfig.from_settings(settings)
        assert config.commit is True
        assert config.create_pr is False


class TestAIConfig:
    """Tests for AIConfig Pydantic model."""

    def test_minimal_ai_config(self) -> None:
        """Verify minimal AIConfig creation."""
        config = AIConfig()
        assert config.ai_agent is False
        assert config.autofix is True
        assert config.ai_agent_autofix is False
        assert config.start_mcp_server is False
        assert config.max_iterations == 5

    def test_ai_config_full(self) -> None:
        """Verify AIConfig with all fields."""
        config = AIConfig(
            ai_agent=True,
            autofix=False,
            ai_agent_autofix=True,
            start_mcp_server=True,
            max_iterations=10,
        )
        assert config.ai_agent is True
        assert config.autofix is False
        assert config.ai_agent_autofix is True
        assert config.start_mcp_server is True
        assert config.max_iterations == 10

    def test_ai_config_ai_fix_property_getter(self) -> None:
        """Verify ai_fix property getter."""
        config = AIConfig(ai_agent=True)
        assert config.ai_fix is True

    def test_ai_config_ai_fix_property_setter(self) -> None:
        """Verify ai_fix property setter."""
        config = AIConfig(ai_agent=False)
        config.ai_fix = True
        assert config.ai_agent is True
        assert config.ai_fix is True

    def test_ai_config_from_settings(self) -> None:
        """Verify AIConfig.from_settings()."""
        settings = MagicMock()
        settings.ai_agent = False
        settings.autofix = True
        settings.ai_agent_autofix = False
        settings.start_mcp_server = True
        settings.max_iterations = 3

        config = AIConfig.from_settings(settings)
        assert config.ai_agent is False
        assert config.autofix is True
        assert config.ai_agent_autofix is False
        assert config.start_mcp_server is True
        assert config.max_iterations == 3


class TestExecutionConfig:
    """Tests for ExecutionConfig Pydantic model."""

    def test_minimal_execution_config(self) -> None:
        """Verify minimal ExecutionConfig creation."""
        config = ExecutionConfig()
        assert config.interactive is True
        assert config.verbose is False
        assert config.async_mode is False
        assert config.no_config_updates is False
        assert config.dry_run is False

    def test_execution_config_full(self) -> None:
        """Verify ExecutionConfig with all fields."""
        config = ExecutionConfig(
            interactive=False,
            verbose=True,
            async_mode=True,
            no_config_updates=True,
            dry_run=True,
        )
        assert config.interactive is False
        assert config.verbose is True
        assert config.async_mode is True
        assert config.no_config_updates is True
        assert config.dry_run is True

    def test_execution_config_from_settings(self) -> None:
        """Verify ExecutionConfig.from_settings()."""
        settings = MagicMock()
        settings.interactive = False
        settings.verbose = True
        settings.async_mode = True
        settings.no_config_updates = False
        settings.dry_run = True

        config = ExecutionConfig.from_settings(settings)
        assert config.interactive is False
        assert config.verbose is True
        assert config.async_mode is True
        assert config.no_config_updates is False
        assert config.dry_run is True


class TestProgressConfig:
    """Tests for ProgressConfig Pydantic model."""

    def test_minimal_progress_config(self) -> None:
        """Verify minimal ProgressConfig creation."""
        config = ProgressConfig()
        assert config.track_progress is False
        assert config.resume_from is None
        assert config.progress_file is None

    def test_progress_config_full(self) -> None:
        """Verify ProgressConfig with all fields."""
        config = ProgressConfig(
            track_progress=True,
            resume_from="task-5",
            progress_file="/tmp/progress.json",
        )
        assert config.track_progress is True
        assert config.resume_from == "task-5"
        assert config.progress_file == "/tmp/progress.json"

    def test_progress_config_from_settings(self) -> None:
        """Verify ProgressConfig.from_settings() maps enabled to track_progress."""
        settings = MagicMock()
        settings.enabled = True
        settings.resume_from = "checkpoint-1"
        settings.progress_file = "/data/progress.json"

        config = ProgressConfig.from_settings(settings)
        assert config.track_progress is True
        assert config.resume_from == "checkpoint-1"
        assert config.progress_file == "/data/progress.json"


class TestCleanupConfig:
    """Tests for CleanupConfig Pydantic model."""

    def test_minimal_cleanup_config(self) -> None:
        """Verify minimal CleanupConfig creation."""
        config = CleanupConfig()
        assert config.auto_cleanup is True
        assert config.keep_debug_logs == 5
        assert config.keep_coverage_files == 10

    def test_cleanup_config_full(self) -> None:
        """Verify CleanupConfig with all fields."""
        config = CleanupConfig(
            auto_cleanup=False,
            keep_debug_logs=20,
            keep_coverage_files=30,
        )
        assert config.auto_cleanup is False
        assert config.keep_debug_logs == 20
        assert config.keep_coverage_files == 30

    def test_cleanup_config_from_settings(self) -> None:
        """Verify CleanupConfig.from_settings()."""
        settings = MagicMock()
        settings.auto_cleanup = False
        settings.keep_debug_logs = 10
        settings.keep_coverage_files = 15

        config = CleanupConfig.from_settings(settings)
        assert config.auto_cleanup is False
        assert config.keep_debug_logs == 10
        assert config.keep_coverage_files == 15


class TestAdvancedConfig:
    """Tests for AdvancedConfig Pydantic model."""

    def test_minimal_advanced_config(self) -> None:
        """Verify minimal AdvancedConfig creation."""
        config = AdvancedConfig()
        assert config.enabled is False
        assert config.license_key is None
        assert config.organization is None

    def test_advanced_config_full(self) -> None:
        """Verify AdvancedConfig with all fields."""
        config = AdvancedConfig(
            enabled=True,
            license_key="XXXXXX-XXXXXX-XXXXXX",
            organization="acme-corp",
        )
        assert config.enabled is True
        assert config.license_key == "XXXXXX-XXXXXX-XXXXXX"
        assert config.organization == "acme-corp"

    def test_advanced_config_from_settings(self) -> None:
        """Verify AdvancedConfig.from_settings()."""
        settings = MagicMock()
        settings.enabled = True
        settings.license_key = "LIC-KEY-123"
        settings.organization = "myorg"

        config = AdvancedConfig.from_settings(settings)
        assert config.enabled is True
        assert config.license_key == "LIC-KEY-123"
        assert config.organization == "myorg"


class TestMCPServerConfig:
    """Tests for MCPServerConfig Pydantic model."""

    def test_minimal_mcp_server_config(self) -> None:
        """Verify minimal MCPServerConfig creation."""
        config = MCPServerConfig()
        assert config.http_port == 8676
        assert config.http_host == "127.0.0.1"
        assert config.websocket_port == 8675
        assert config.http_enabled is False

    def test_mcp_server_config_full(self) -> None:
        """Verify MCPServerConfig with all fields."""
        config = MCPServerConfig(
            http_port=9000,
            http_host="0.0.0.0",
            websocket_port=9001,
            http_enabled=True,
        )
        assert config.http_port == 9000
        assert config.http_host == "0.0.0.0"
        assert config.websocket_port == 9001
        assert config.http_enabled is True

    def test_mcp_server_config_from_settings(self) -> None:
        """Verify MCPServerConfig.from_settings()."""
        settings = MagicMock()
        settings.http_port = 8080
        settings.http_host = "localhost"
        settings.websocket_port = 8081
        settings.http_enabled = True

        config = MCPServerConfig.from_settings(settings)
        assert config.http_port == 8080
        assert config.http_host == "localhost"
        assert config.websocket_port == 8081
        assert config.http_enabled is True


class TestZubanLSPConfig:
    """Tests for ZubanLSPConfig Pydantic model."""

    def test_minimal_zuban_lsp_config(self) -> None:
        """Verify minimal ZubanLSPConfig creation."""
        config = ZubanLSPConfig()
        assert config.enabled is True
        assert config.auto_start is True
        assert config.port == 8677
        assert config.mode == "stdio"
        assert config.timeout == 30

    def test_zuban_lsp_config_full(self) -> None:
        """Verify ZubanLSPConfig with all fields."""
        config = ZubanLSPConfig(
            enabled=False,
            auto_start=False,
            port=9999,
            mode="tcp",
            timeout=60,
        )
        assert config.enabled is False
        assert config.auto_start is False
        assert config.port == 9999
        assert config.mode == "tcp"
        assert config.timeout == 60

    def test_zuban_lsp_config_from_settings(self) -> None:
        """Verify ZubanLSPConfig.from_settings()."""
        settings = MagicMock()
        settings.enabled = False
        settings.auto_start = True
        settings.port = 7777
        settings.mode = "pipe"
        settings.timeout = 45

        config = ZubanLSPConfig.from_settings(settings)
        assert config.enabled is False
        assert config.auto_start is True
        assert config.port == 7777
        assert config.mode == "pipe"
        assert config.timeout == 45


class TestWorkflowOptions:
    """Tests for WorkflowOptions Pydantic composition model."""

    def test_minimal_workflow_options(self) -> None:
        """Verify minimal WorkflowOptions creation."""
        options = WorkflowOptions()
        assert isinstance(options.cleaning, CleaningConfig)
        assert isinstance(options.hooks, HookConfig)
        assert isinstance(options.testing, TestConfig)
        assert isinstance(options.publishing, PublishConfig)
        assert isinstance(options.git, GitConfig)
        assert isinstance(options.ai, AIConfig)
        assert isinstance(options.execution, ExecutionConfig)
        assert isinstance(options.progress, ProgressConfig)
        assert isinstance(options.cleanup, CleanupConfig)
        assert isinstance(options.advanced, AdvancedConfig)
        assert isinstance(options.mcp_server, MCPServerConfig)
        assert isinstance(options.zuban_lsp, ZubanLSPConfig)

    def test_workflow_options_with_custom_configs(self) -> None:
        """Verify WorkflowOptions with custom config objects."""
        options = WorkflowOptions(
            cleaning=CleaningConfig(clean=False),
            testing=TestConfig(test=True),
            ai=AIConfig(ai_agent=True),
        )
        assert options.cleaning.clean is False
        assert options.testing.test is True
        assert options.ai.ai_agent is True

    def test_workflow_options_clean_property_getter(self) -> None:
        """Verify clean property forwards to cleaning.clean."""
        options = WorkflowOptions()
        options.cleaning.clean = True
        assert options.clean is True

    def test_workflow_options_clean_property_setter(self) -> None:
        """Verify clean property setter updates cleaning.clean."""
        options = WorkflowOptions()
        options.clean = False
        assert options.cleaning.clean is False

    def test_workflow_options_test_property_getter(self) -> None:
        """Verify test property forwards to testing.test."""
        options = WorkflowOptions()
        options.testing.test = True
        assert options.test is True

    def test_workflow_options_test_property_setter(self) -> None:
        """Verify test property setter updates testing.test."""
        options = WorkflowOptions()
        options.test = True
        assert options.testing.test is True

    def test_workflow_options_strip_code_property(self) -> None:
        """Verify strip_code property forwards to cleaning.strip_code."""
        options = WorkflowOptions()
        options.strip_code = False
        assert options.cleaning.clean is False
        assert options.strip_code is False

    def test_workflow_options_run_tests_property(self) -> None:
        """Verify run_tests property forwards to testing.run_tests."""
        options = WorkflowOptions()
        options.run_tests = True
        assert options.testing.test is True
        assert options.run_tests is True

    def test_workflow_options_ai_fix_property(self) -> None:
        """Verify ai_fix property forwards to ai.ai_fix."""
        options = WorkflowOptions()
        options.ai_fix = True
        assert options.ai.ai_agent is True
        assert options.ai_fix is True

    def test_workflow_options_publish_property_getter(self) -> None:
        """Verify publish property forwards to publishing.publish."""
        options = WorkflowOptions()
        options.publishing.publish = "pypi"
        assert options.publish == "pypi"

    def test_workflow_options_publish_property_setter(self) -> None:
        """Verify publish property setter updates publishing.publish."""
        options = WorkflowOptions()
        options.publish = "testpypi"
        assert options.publishing.publish == "testpypi"

    def test_workflow_options_commit_property_getter(self) -> None:
        """Verify commit property forwards to git.commit."""
        options = WorkflowOptions()
        options.git.commit = True
        assert options.commit is True

    def test_workflow_options_commit_property_setter(self) -> None:
        """Verify commit property setter updates git.commit."""
        options = WorkflowOptions()
        options.commit = True
        assert options.git.commit is True

    def test_workflow_options_from_settings(self) -> None:
        """Verify WorkflowOptions.from_settings()."""
        # Use proper objects instead of MagicMock to avoid Pydantic validation issues
        class Settings:
            cleaning = type("obj", (), {"clean": False, "update_docs": True, "force_update_docs": False, "compress_docs": False, "auto_compress_docs": False, "targets": []})()
            hooks = type("obj", (), {"skip_hooks": False, "experimental_hooks": False, "enable_pyrefly": False, "enable_ty": False, "enable_lsp_optimization": False})()
            testing = type("obj", (), {"test": True, "benchmark": False, "benchmark_regression": False, "benchmark_regression_threshold": 0.1, "test_workers": 0, "test_timeout": 0, "xcode_tests": False, "xcode_project": "app/MdInjectApp/MdInjectApp.xcodeproj", "xcode_scheme": "MdInjectApp", "xcode_configuration": "Debug", "xcode_destination": "platform=macOS"})()
            publishing = type("obj", (), {"publish": "pypi", "bump": None, "all": None, "cleanup_pypi": False, "keep_releases": 10, "no_git_tags": False, "skip_version_check": False})()
            git = type("obj", (), {"commit": True, "create_pr": False})()
            ai = type("obj", (), {"ai_agent": False, "autofix": True, "ai_agent_autofix": False, "start_mcp_server": False, "max_iterations": 5})()
            execution = type("obj", (), {"interactive": False, "verbose": False, "async_mode": False, "no_config_updates": False, "dry_run": False})()
            progress = type("obj", (), {"enabled": True, "resume_from": None, "progress_file": None})()
            cleanup = type("obj", (), {"auto_cleanup": True, "keep_debug_logs": 5, "keep_coverage_files": 10})()
            advanced = type("obj", (), {"enabled": False, "license_key": None, "organization": None})()
            mcp_server = type("obj", (), {"http_port": 8676, "http_host": "127.0.0.1", "websocket_port": 8675, "http_enabled": False})()
            zuban_lsp = type("obj", (), {"enabled": True, "auto_start": True, "port": 8677, "mode": "stdio", "timeout": 30})()

        settings = Settings()
        options = WorkflowOptions.from_settings(settings)
        assert isinstance(options.cleaning, CleaningConfig)
        assert isinstance(options.testing, TestConfig)
        assert options.testing.test is True
        assert options.git.commit is True

    def test_workflow_options_to_dict(self) -> None:
        """Verify WorkflowOptions.to_dict() returns model_dump()."""
        options = WorkflowOptions(
            cleaning=CleaningConfig(clean=False),
            testing=TestConfig(test=True),
        )
        result = options.to_dict()

        assert isinstance(result, dict)
        assert "cleaning" in result
        assert "testing" in result
        assert result["cleaning"]["clean"] is False
        assert result["testing"]["test"] is True


class TestExecutionResult:
    """Tests for ExecutionResult Pydantic model."""

    def test_minimal_execution_result(self) -> None:
        """Verify minimal ExecutionResult creation."""
        result = ExecutionResult(
            operation_id="op-1",
            success=True,
            duration_seconds=5.5,
        )
        assert result.operation_id == "op-1"
        assert result.success is True
        assert result.duration_seconds == 5.5
        assert result.output == ""
        assert result.error == ""
        assert result.exit_code == 0
        assert result.metadata == {}

    def test_execution_result_full(self) -> None:
        """Verify ExecutionResult with all fields."""
        result = ExecutionResult(
            operation_id="op-2",
            success=False,
            duration_seconds=2.3,
            output="Some output",
            error="Error occurred",
            exit_code=1,
            metadata={"stage": "test", "worker": "w1"},
        )
        assert result.operation_id == "op-2"
        assert result.success is False
        assert result.duration_seconds == 2.3
        assert result.output == "Some output"
        assert result.error == "Error occurred"
        assert result.exit_code == 1
        assert result.metadata == {"stage": "test", "worker": "w1"}

    def test_execution_result_serialization(self) -> None:
        """Verify ExecutionResult serialization."""
        result = ExecutionResult(
            operation_id="op-3",
            success=True,
            duration_seconds=1.0,
            output="test output",
        )
        data = result.model_dump()
        assert data["operation_id"] == "op-3"
        assert data["success"] is True
        assert data["duration_seconds"] == 1.0


class TestParallelExecutionResult:
    """Tests for ParallelExecutionResult Pydantic model."""

    def test_minimal_parallel_execution_result(self) -> None:
        """Verify minimal ParallelExecutionResult creation."""
        result = ParallelExecutionResult(
            group_name="group-1",
            total_operations=10,
            successful_operations=8,
            failed_operations=2,
            total_duration_seconds=15.5,
            results=[],
        )
        assert result.group_name == "group-1"
        assert result.total_operations == 10
        assert result.successful_operations == 8
        assert result.failed_operations == 2
        assert result.total_duration_seconds == 15.5
        assert result.results == []

    def test_parallel_execution_result_with_results(self) -> None:
        """Verify ParallelExecutionResult with ExecutionResult list."""
        exec_result = ExecutionResult(
            operation_id="op-1",
            success=True,
            duration_seconds=1.0,
        )
        result = ParallelExecutionResult(
            group_name="group-2",
            total_operations=1,
            successful_operations=1,
            failed_operations=0,
            total_duration_seconds=1.0,
            results=[exec_result],
        )
        assert len(result.results) == 1
        assert result.results[0].operation_id == "op-1"

    def test_parallel_execution_result_success_rate_full(self) -> None:
        """Verify success_rate property with 100% success."""
        result = ParallelExecutionResult(
            group_name="group-3",
            total_operations=5,
            successful_operations=5,
            failed_operations=0,
            total_duration_seconds=10.0,
            results=[],
        )
        assert result.success_rate == 1.0

    def test_parallel_execution_result_success_rate_partial(self) -> None:
        """Verify success_rate property with partial success."""
        result = ParallelExecutionResult(
            group_name="group-4",
            total_operations=10,
            successful_operations=7,
            failed_operations=3,
            total_duration_seconds=20.0,
            results=[],
        )
        assert result.success_rate == 0.7

    def test_parallel_execution_result_success_rate_zero(self) -> None:
        """Verify success_rate property with zero total operations."""
        result = ParallelExecutionResult(
            group_name="group-5",
            total_operations=0,
            successful_operations=0,
            failed_operations=0,
            total_duration_seconds=0.0,
            results=[],
        )
        assert result.success_rate == 0.0

    def test_parallel_execution_result_overall_success_true(self) -> None:
        """Verify overall_success property when no failures."""
        result = ParallelExecutionResult(
            group_name="group-6",
            total_operations=5,
            successful_operations=5,
            failed_operations=0,
            total_duration_seconds=10.0,
            results=[],
        )
        assert result.overall_success is True

    def test_parallel_execution_result_overall_success_false(self) -> None:
        """Verify overall_success property when failures exist."""
        result = ParallelExecutionResult(
            group_name="group-7",
            total_operations=5,
            successful_operations=4,
            failed_operations=1,
            total_duration_seconds=10.0,
            results=[],
        )
        assert result.overall_success is False

    def test_parallel_execution_result_serialization(self) -> None:
        """Verify ParallelExecutionResult serialization (properties not in dump)."""
        result = ParallelExecutionResult(
            group_name="group-8",
            total_operations=2,
            successful_operations=1,
            failed_operations=1,
            total_duration_seconds=5.0,
            results=[],
        )
        data = result.model_dump()
        assert data["group_name"] == "group-8"
        assert data["total_operations"] == 2
        assert data["failed_operations"] == 1
        # Properties are not included in model_dump(), but accessible on instance
        assert result.success_rate == 0.5
        assert result.overall_success is False
