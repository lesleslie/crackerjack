"""Tests for config module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crackerjack.models.config import (
    AdvancedConfig,
    AIConfig,
    CleaningConfig,
    CleanupConfig,
    ExecutionConfig,
    GitConfig,
    HookConfig,
    MCPServerConfig,
    ProgressConfig,
    PublishConfig,
    TestConfig,
    WorkflowOptions,
    ZubanLSPConfig,
)


class TestCleaningConfig:
    """Tests for CleaningConfig dataclass."""

    def test_minimal_cleaning_config(self) -> None:
        """Verify minimal CleaningConfig creation."""
        config = CleaningConfig()
        assert config.clean is True
        assert config.strip_comments_only is False
        assert config.strip_docstrings_only is False
        assert config.update_docs is False
        assert config.force_update_docs is False
        assert config.compress_docs is False
        assert config.auto_compress_docs is False
        assert config.targets == []

    def test_cleaning_config_with_all_options(self) -> None:
        """Verify CleaningConfig with all options."""
        from pathlib import Path

        targets = [Path("src"), Path("tests")]
        config = CleaningConfig(
            clean=False,
            strip_comments_only=True,
            strip_docstrings_only=True,
            update_docs=True,
            force_update_docs=True,
            compress_docs=True,
            auto_compress_docs=True,
            targets=targets,
        )
        assert config.clean is False
        assert config.strip_comments_only is True
        assert config.strip_docstrings_only is True
        assert config.update_docs is True
        assert config.force_update_docs is True
        assert config.compress_docs is True
        assert config.auto_compress_docs is True
        assert config.targets == targets

    def test_strip_code_property_getter(self) -> None:
        """Verify strip_code property getter."""
        config = CleaningConfig(clean=True)
        assert config.strip_code is True

        config = CleaningConfig(clean=False)
        assert config.strip_code is False

    def test_strip_code_property_setter(self) -> None:
        """Verify strip_code property setter."""
        config = CleaningConfig()
        config.strip_code = False
        assert config.clean is False

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        from pathlib import Path

        settings = MagicMock()
        settings.clean = False
        settings.strip_comments_only = True
        settings.strip_docstrings_only = False
        settings.update_docs = True
        settings.force_update_docs = False
        settings.compress_docs = True
        settings.auto_compress_docs = False
        settings.targets = [Path("src")]

        config = CleaningConfig.from_settings(settings)

        assert config.clean is False
        assert config.strip_comments_only is True
        assert config.strip_docstrings_only is False
        assert config.update_docs is True
        assert config.force_update_docs is False
        assert config.compress_docs is True
        assert config.auto_compress_docs is False
        assert config.targets == [Path("src")]

    def test_from_settings_missing_attributes(self) -> None:
        """Verify from_settings with missing attributes."""
        settings = MagicMock(spec=[])
        settings.clean = True
        settings.update_docs = False
        settings.force_update_docs = False
        settings.compress_docs = False
        settings.auto_compress_docs = False

        config = CleaningConfig.from_settings(settings)

        assert config.clean is True
        assert config.strip_comments_only is False
        assert config.targets == []


class TestHookConfig:
    """Tests for HookConfig dataclass."""

    def test_minimal_hook_config(self) -> None:
        """Verify minimal HookConfig creation."""
        config = HookConfig()
        assert config.skip_hooks is False
        assert config.experimental_hooks is False
        assert config.enable_pyrefly is False
        assert config.enable_ty is False
        assert config.enable_lsp_optimization is False
        assert config.skip_offline_pip_audit is True

    def test_hook_config_with_all_options(self) -> None:
        """Verify HookConfig with all options."""
        config = HookConfig(
            skip_hooks=True,
            experimental_hooks=True,
            enable_pyrefly=True,
            enable_ty=True,
            enable_lsp_optimization=True,
            skip_offline_pip_audit=False,
        )
        assert config.skip_hooks is True
        assert config.experimental_hooks is True
        assert config.enable_pyrefly is True
        assert config.enable_ty is True
        assert config.enable_lsp_optimization is True
        assert config.skip_offline_pip_audit is False

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.skip_hooks = True
        settings.experimental_hooks = False
        settings.enable_pyrefly = True
        settings.enable_ty = False
        settings.enable_lsp_optimization = True
        settings.skip_offline_pip_audit = False

        config = HookConfig.from_settings(settings)

        assert config.skip_hooks is True
        assert config.experimental_hooks is False
        assert config.enable_pyrefly is True
        assert config.enable_ty is False
        assert config.enable_lsp_optimization is True
        assert config.skip_offline_pip_audit is False

    def test_from_settings_missing_pip_audit(self) -> None:
        """Verify from_settings with missing skip_offline_pip_audit."""
        settings = MagicMock(spec=[])
        settings.skip_hooks = False
        settings.experimental_hooks = False
        settings.enable_pyrefly = False
        settings.enable_ty = False
        settings.enable_lsp_optimization = False

        config = HookConfig.from_settings(settings)

        assert config.skip_offline_pip_audit is True


class TestTestConfig:
    """Tests for TestConfig dataclass."""

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

    def test_test_config_with_all_options(self) -> None:
        """Verify TestConfig with all options."""
        config = TestConfig(
            test=True,
            benchmark=True,
            benchmark_regression=True,
            benchmark_regression_threshold=0.2,
            test_workers=4,
            test_timeout=600,
            xcode_tests=True,
            xcode_project="custom/project.xcodeproj",
            xcode_scheme="CustomScheme",
            xcode_configuration="Release",
            xcode_destination="platform=iOS",
        )
        assert config.test is True
        assert config.benchmark is True
        assert config.benchmark_regression is True
        assert config.benchmark_regression_threshold == 0.2
        assert config.test_workers == 4
        assert config.test_timeout == 600
        assert config.xcode_tests is True
        assert config.xcode_project == "custom/project.xcodeproj"
        assert config.xcode_scheme == "CustomScheme"
        assert config.xcode_configuration == "Release"
        assert config.xcode_destination == "platform=iOS"

    def test_run_tests_property_getter(self) -> None:
        """Verify run_tests property getter."""
        config = TestConfig(test=True)
        assert config.run_tests is True

    def test_run_tests_property_setter(self) -> None:
        """Verify run_tests property setter."""
        config = TestConfig()
        config.run_tests = True
        assert config.test is True

    def test_workers_property_getter(self) -> None:
        """Verify workers property getter."""
        config = TestConfig(test_workers=8)
        assert config.workers == 8

    def test_workers_property_setter(self) -> None:
        """Verify workers property setter."""
        config = TestConfig()
        config.workers = 4
        assert config.test_workers == 4

    def test_timeout_property_getter(self) -> None:
        """Verify timeout property getter."""
        config = TestConfig(test_timeout=300)
        assert config.timeout == 300

    def test_timeout_property_setter(self) -> None:
        """Verify timeout property setter."""
        config = TestConfig()
        config.timeout = 600
        assert config.test_timeout == 600

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.test = True
        settings.benchmark = True
        settings.benchmark_regression = True
        settings.benchmark_regression_threshold = 0.15
        settings.test_workers = 2
        settings.test_timeout = 300
        settings.xcode_tests = False
        settings.xcode_project = "custom.xcodeproj"
        settings.xcode_scheme = "CustomScheme"
        settings.xcode_configuration = "Release"
        settings.xcode_destination = "platform=iOS"

        config = TestConfig.from_settings(settings)

        assert config.test is True
        assert config.benchmark is True
        assert config.benchmark_regression is True
        assert config.benchmark_regression_threshold == 0.15
        assert config.test_workers == 2
        assert config.test_timeout == 300
        assert config.xcode_tests is False
        assert config.xcode_project == "custom.xcodeproj"


class TestPublishConfig:
    """Tests for PublishConfig dataclass."""

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

    def test_publish_config_with_all_options(self) -> None:
        """Verify PublishConfig with all options."""
        config = PublishConfig(
            publish="major",
            bump="minor",
            all="all",
            cleanup_pypi=True,
            keep_releases=20,
            no_git_tags=True,
            skip_version_check=True,
        )
        assert config.publish == "major"
        assert config.bump == "minor"
        assert config.all == "all"
        assert config.cleanup_pypi is True
        assert config.keep_releases == 20
        assert config.no_git_tags is True
        assert config.skip_version_check is True

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.publish = "patch"
        settings.bump = "major"
        settings.all = "all"
        settings.cleanup_pypi = True
        settings.keep_releases = 15
        settings.no_git_tags = True
        settings.skip_version_check = False

        config = PublishConfig.from_settings(settings)

        assert config.publish == "patch"
        assert config.bump == "major"
        assert config.all == "all"
        assert config.cleanup_pypi is True
        assert config.keep_releases == 15


class TestGitConfig:
    """Tests for GitConfig dataclass."""

    def test_minimal_git_config(self) -> None:
        """Verify minimal GitConfig creation."""
        config = GitConfig()
        assert config.commit is False
        assert config.create_pr is False
        assert config.auth_fallback is True
        assert config.persist_fallback is False

    def test_git_config_with_all_options(self) -> None:
        """Verify GitConfig with all options."""
        config = GitConfig(
            commit=True,
            create_pr=True,
            auth_fallback=False,
            persist_fallback=True,
        )
        assert config.commit is True
        assert config.create_pr is True
        assert config.auth_fallback is False
        assert config.persist_fallback is True

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.commit = True
        settings.create_pr = False
        settings.auth_fallback = False
        settings.persist_fallback = True

        config = GitConfig.from_settings(settings)

        assert config.commit is True
        assert config.create_pr is False
        assert config.auth_fallback is False
        assert config.persist_fallback is True


class TestAIConfig:
    """Tests for AIConfig dataclass."""

    def test_minimal_ai_config(self) -> None:
        """Verify minimal AIConfig creation."""
        config = AIConfig()
        assert config.ai_agent is False
        assert config.autofix is True
        assert config.ai_agent_autofix is False
        assert config.start_mcp_server is False
        assert config.max_iterations == 5

    def test_ai_config_with_all_options(self) -> None:
        """Verify AIConfig with all options."""
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

    def test_ai_fix_property_getter(self) -> None:
        """Verify ai_fix property getter."""
        config = AIConfig(ai_agent=True)
        assert config.ai_fix is True

    def test_ai_fix_property_setter(self) -> None:
        """Verify ai_fix property setter."""
        config = AIConfig()
        config.ai_fix = True
        assert config.ai_agent is True

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.ai_agent = True
        settings.autofix = False
        settings.ai_agent_autofix = True
        settings.start_mcp_server = True
        settings.max_iterations = 15

        config = AIConfig.from_settings(settings)

        assert config.ai_agent is True
        assert config.autofix is False
        assert config.ai_agent_autofix is True
        assert config.start_mcp_server is True
        assert config.max_iterations == 15


class TestExecutionConfig:
    """Tests for ExecutionConfig dataclass."""

    def test_minimal_execution_config(self) -> None:
        """Verify minimal ExecutionConfig creation."""
        config = ExecutionConfig()
        assert config.interactive is True
        assert config.verbose is False
        assert config.async_mode is False
        assert config.no_config_updates is False
        assert config.dry_run is False

    def test_execution_config_with_all_options(self) -> None:
        """Verify ExecutionConfig with all options."""
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

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
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
    """Tests for ProgressConfig dataclass."""

    def test_minimal_progress_config(self) -> None:
        """Verify minimal ProgressConfig creation."""
        config = ProgressConfig()
        assert config.track_progress is False
        assert config.resume_from is None
        assert config.progress_file is None

    def test_progress_config_with_all_options(self) -> None:
        """Verify ProgressConfig with all options."""
        config = ProgressConfig(
            track_progress=True,
            resume_from="checkpoint_123",
            progress_file="/path/to/progress.json",
        )
        assert config.track_progress is True
        assert config.resume_from == "checkpoint_123"
        assert config.progress_file == "/path/to/progress.json"

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.enabled = True
        settings.resume_from = "checkpoint_456"
        settings.progress_file = "/tmp/progress.json"

        config = ProgressConfig.from_settings(settings)

        assert config.track_progress is True
        assert config.resume_from == "checkpoint_456"
        assert config.progress_file == "/tmp/progress.json"


class TestCleanupConfig:
    """Tests for CleanupConfig dataclass."""

    def test_minimal_cleanup_config(self) -> None:
        """Verify minimal CleanupConfig creation."""
        config = CleanupConfig()
        assert config.auto_cleanup is True
        assert config.keep_debug_logs == 5
        assert config.keep_coverage_files == 10

    def test_cleanup_config_with_all_options(self) -> None:
        """Verify CleanupConfig with all options."""
        config = CleanupConfig(
            auto_cleanup=False,
            keep_debug_logs=20,
            keep_coverage_files=30,
        )
        assert config.auto_cleanup is False
        assert config.keep_debug_logs == 20
        assert config.keep_coverage_files == 30

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.auto_cleanup = False
        settings.keep_debug_logs = 10
        settings.keep_coverage_files = 15

        config = CleanupConfig.from_settings(settings)

        assert config.auto_cleanup is False
        assert config.keep_debug_logs == 10
        assert config.keep_coverage_files == 15


class TestAdvancedConfig:
    """Tests for AdvancedConfig dataclass."""

    def test_minimal_advanced_config(self) -> None:
        """Verify minimal AdvancedConfig creation."""
        config = AdvancedConfig()
        assert config.enabled is False
        assert config.license_key is None
        assert config.organization is None

    def test_advanced_config_with_all_options(self) -> None:
        """Verify AdvancedConfig with all options."""
        config = AdvancedConfig(
            enabled=True,
            license_key="key123",
            organization="org456",
        )
        assert config.enabled is True
        assert config.license_key == "key123"
        assert config.organization == "org456"

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.enabled = True
        settings.license_key = "test_key"
        settings.organization = "test_org"

        config = AdvancedConfig.from_settings(settings)

        assert config.enabled is True
        assert config.license_key == "test_key"
        assert config.organization == "test_org"


class TestMCPServerConfig:
    """Tests for MCPServerConfig dataclass."""

    def test_minimal_mcp_server_config(self) -> None:
        """Verify minimal MCPServerConfig creation."""
        config = MCPServerConfig()
        assert config.http_port == 8676
        assert config.http_host == "127.0.0.1"
        assert config.websocket_port == 8696
        assert config.http_enabled is False

    def test_mcp_server_config_with_all_options(self) -> None:
        """Verify MCPServerConfig with all options."""
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

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.http_port = 8888
        settings.http_host = "localhost"
        settings.websocket_port = 8889
        settings.http_enabled = True

        config = MCPServerConfig.from_settings(settings)

        assert config.http_port == 8888
        assert config.http_host == "localhost"
        assert config.websocket_port == 8889
        assert config.http_enabled is True


class TestZubanLSPConfig:
    """Tests for ZubanLSPConfig dataclass."""

    def test_minimal_zuban_lsp_config(self) -> None:
        """Verify minimal ZubanLSPConfig creation."""
        config = ZubanLSPConfig()
        assert config.enabled is True
        assert config.auto_start is True
        assert config.port == 8685
        assert config.mode == "stdio"
        assert config.timeout == 30

    def test_zuban_lsp_config_with_all_options(self) -> None:
        """Verify ZubanLSPConfig with all options."""
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

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.enabled = False
        settings.auto_start = False
        settings.port = 7777
        settings.mode = "tcp"
        settings.timeout = 45

        config = ZubanLSPConfig.from_settings(settings)

        assert config.enabled is False
        assert config.auto_start is False
        assert config.port == 7777
        assert config.mode == "tcp"
        assert config.timeout == 45


class TestWorkflowOptions:
    """Tests for WorkflowOptions dataclass."""

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
        """Verify WorkflowOptions with custom configs."""
        cleaning = CleaningConfig(clean=False)
        testing = TestConfig(test=True)
        options = WorkflowOptions(cleaning=cleaning, testing=testing)

        assert options.cleaning.clean is False
        assert options.testing.test is True
        assert isinstance(options.git, GitConfig)

    def test_workflow_options_clean_property_getter(self) -> None:
        """Verify clean property getter."""
        options = WorkflowOptions(cleaning=CleaningConfig(clean=True))
        assert options.clean is True

    def test_workflow_options_clean_property_setter(self) -> None:
        """Verify clean property setter."""
        options = WorkflowOptions()
        options.clean = False
        assert options.cleaning.clean is False

    def test_workflow_options_test_property_getter(self) -> None:
        """Verify test property getter."""
        options = WorkflowOptions(testing=TestConfig(test=True))
        assert options.test is True

    def test_workflow_options_test_property_setter(self) -> None:
        """Verify test property setter."""
        options = WorkflowOptions()
        options.test = True
        assert options.testing.test is True

    def test_workflow_options_commit_property_getter(self) -> None:
        """Verify commit property getter."""
        options = WorkflowOptions(git=GitConfig(commit=True))
        assert options.commit is True

    def test_workflow_options_commit_property_setter(self) -> None:
        """Verify commit property setter."""
        options = WorkflowOptions()
        options.commit = True
        assert options.git.commit is True

    def test_workflow_options_ai_agent_property_getter(self) -> None:
        """Verify ai_agent property getter."""
        options = WorkflowOptions(ai=AIConfig(ai_agent=True))
        assert options.ai_agent is True

    def test_workflow_options_ai_fix_property_getter(self) -> None:
        """Verify ai_fix property getter."""
        options = WorkflowOptions(ai=AIConfig(ai_agent=True))
        assert options.ai_fix is True

    def test_workflow_options_interactive_property_getter(self) -> None:
        """Verify interactive property getter."""
        options = WorkflowOptions(execution=ExecutionConfig(interactive=False))
        assert options.interactive is False

    def test_workflow_options_interactive_property_setter(self) -> None:
        """Verify interactive property setter."""
        options = WorkflowOptions()
        options.interactive = False
        assert options.execution.interactive is False

    def test_workflow_options_verbose_property_getter(self) -> None:
        """Verify verbose property getter."""
        options = WorkflowOptions(execution=ExecutionConfig(verbose=True))
        assert options.verbose is True

    def test_workflow_options_verbose_property_setter(self) -> None:
        """Verify verbose property setter."""
        options = WorkflowOptions()
        options.verbose = True
        assert options.execution.verbose is True

    def test_workflow_options_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.cleaning = MagicMock()
        settings.hooks = MagicMock()
        settings.testing = MagicMock()
        settings.publishing = MagicMock()
        settings.git = MagicMock()
        settings.ai = MagicMock()
        settings.execution = MagicMock()
        settings.progress = MagicMock()
        settings.cleanup = MagicMock()
        settings.advanced = MagicMock()
        settings.mcp_server = MagicMock()
        settings.zuban_lsp = MagicMock()

        options = WorkflowOptions.from_settings(settings)

        assert isinstance(options, WorkflowOptions)
        assert isinstance(options.cleaning, CleaningConfig)

    def test_workflow_options_to_settings(self) -> None:
        """Verify to_settings method."""
        options = WorkflowOptions(
            cleaning=CleaningConfig(clean=True),
            hooks=HookConfig(),
            testing=TestConfig(),
            publishing=PublishConfig(),
            git=GitConfig(),
            ai=AIConfig(),
            execution=ExecutionConfig(),
            progress=ProgressConfig(),
            cleanup=CleanupConfig(),
            advanced=AdvancedConfig(),
            mcp_server=MCPServerConfig(),
            zuban_lsp=ZubanLSPConfig(),
        )
        settings = options.to_settings()

        assert hasattr(settings, "cleaning")
        assert hasattr(settings, "hooks")
        assert hasattr(settings, "testing")

    def test_workflow_options_to_dict(self) -> None:
        """Verify to_dict method."""
        options = WorkflowOptions()
        result = options.to_dict()

        assert "cleaning" in result
        assert "hooks" in result
        assert "testing" in result
        assert "publishing" in result
        assert "git" in result
        assert "ai" in result
        assert "execution" in result
        assert "progress" in result
        assert "cleanup" in result
        assert "advanced" in result
        assert "mcp_server" in result
        assert "zuban_lsp" in result

    def test_workflow_options_from_args_minimal(self) -> None:
        """Verify from_args with minimal args."""
        args = MagicMock()
        args.__dict__ = {}

        options = WorkflowOptions.from_args(args)

        assert isinstance(options, WorkflowOptions)

    def test_workflow_options_from_args_with_clean(self) -> None:
        """Verify from_args with clean argument."""
        args = MagicMock()
        args.__dict__ = {"clean": False}

        options = WorkflowOptions.from_args(args)

        assert options.cleaning.clean is False

    def test_workflow_options_from_args_with_strip_code(self) -> None:
        """Verify from_args with strip_code argument."""
        args = MagicMock()
        args.__dict__ = {"strip_code": False}

        options = WorkflowOptions.from_args(args)

        assert options.cleaning.clean is False

    def test_workflow_options_from_args_with_test(self) -> None:
        """Verify from_args with test argument."""
        args = MagicMock()
        args.__dict__ = {"test": True}

        options = WorkflowOptions.from_args(args)

        assert options.testing.test is True

    def test_workflow_options_from_args_with_run_tests(self) -> None:
        """Verify from_args with run_tests argument."""
        args = MagicMock()
        args.__dict__ = {"run_tests": True}

        options = WorkflowOptions.from_args(args)

        assert options.testing.test is True

    def test_workflow_options_from_args_with_commit(self) -> None:
        """Verify from_args with commit argument."""
        args = MagicMock()
        args.__dict__ = {"commit": True}

        options = WorkflowOptions.from_args(args)

        assert options.git.commit is True

    def test_workflow_options_from_args_with_publish(self) -> None:
        """Verify from_args with publish argument."""
        args = MagicMock()
        args.__dict__ = {"publish": "major"}

        options = WorkflowOptions.from_args(args)

        assert options.publishing.publish == "major"

    def test_workflow_options_from_args_with_bump(self) -> None:
        """Verify from_args with bump argument."""
        args = MagicMock()
        args.__dict__ = {"bump": "minor"}

        options = WorkflowOptions.from_args(args)

        assert options.publishing.bump == "minor"

    def test_workflow_options_from_args_with_interactive(self) -> None:
        """Verify from_args with interactive argument."""
        args = MagicMock()
        args.__dict__ = {"interactive": False}

        options = WorkflowOptions.from_args(args)

        assert options.execution.interactive is False

    def test_workflow_options_from_args_with_dry_run(self) -> None:
        """Verify from_args with dry_run argument."""
        args = MagicMock()
        args.__dict__ = {"dry_run": True}

        options = WorkflowOptions.from_args(args)

        assert options.execution.dry_run is True

    def test_workflow_options_from_args_without_dict(self) -> None:
        """Verify from_args with object without __dict__."""
        args = MagicMock(spec=[])

        options = WorkflowOptions.from_args(args)

        assert isinstance(options, WorkflowOptions)

    def test_workflow_options_kwargs_support(self) -> None:
        """Verify WorkflowOptions supports kwargs."""
        options = WorkflowOptions(verbose=True, interactive=False)

        assert options.verbose is True
        assert options.interactive is False

    def test_workflow_options_skip_hooks_property(self) -> None:
        """Verify skip_hooks property."""
        options = WorkflowOptions()
        options.skip_hooks = True
        assert options.hooks.skip_hooks is True

    def test_workflow_options_max_iterations_property(self) -> None:
        """Verify max_iterations property."""
        options = WorkflowOptions()
        options.max_iterations = 10
        assert options.ai.max_iterations == 10

    def test_workflow_options_track_progress_property(self) -> None:
        """Verify track_progress property."""
        options = WorkflowOptions()
        options.track_progress = True
        assert options.progress.track_progress is True

    def test_workflow_options_resume_from_property(self) -> None:
        """Verify resume_from property."""
        options = WorkflowOptions()
        options.resume_from = "checkpoint_123"
        assert options.progress.resume_from == "checkpoint_123"

    def test_workflow_options_progress_file_property(self) -> None:
        """Verify progress_file property."""
        options = WorkflowOptions()
        options.progress_file = "/tmp/progress.json"
        assert options.progress.progress_file == "/tmp/progress.json"

    def test_workflow_options_all_properties_roundtrip(self) -> None:
        """Verify all properties roundtrip correctly."""
        options = WorkflowOptions()

        # Set various properties
        options.clean = False
        options.test = True
        options.commit = True
        options.ai_agent = True
        options.interactive = False
        options.verbose = True
        options.skip_hooks = True
        options.max_iterations = 12

        # Verify they're set
        assert options.clean is False
        assert options.test is True
        assert options.commit is True
        assert options.ai_agent is True
        assert options.interactive is False
        assert options.verbose is True
        assert options.skip_hooks is True
        assert options.max_iterations == 12

    def test_workflow_options_nested_config_update(self) -> None:
        """Verify nested config updates work."""
        options = WorkflowOptions()
        options.cleaning.targets = ["/src"]
        assert options.cleaning.targets == ["/src"]

    def test_workflow_options_to_dict_contains_all_configs(self) -> None:
        """Verify to_dict contains all nested configs."""
        options = WorkflowOptions(
            cleaning=CleaningConfig(clean=False),
            testing=TestConfig(test=True),
        )
        result = options.to_dict()

        assert isinstance(result["cleaning"], dict)
        assert result["cleaning"]["clean"] is False
        assert isinstance(result["testing"], dict)
        assert result["testing"]["test"] is True
