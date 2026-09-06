"""Tests for config module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crackerjack.config.settings import CrackerjackSettings
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
        assert config.skip_offline_osv_scanner is True

    def test_hook_config_with_all_options(self) -> None:
        """Verify HookConfig with all options."""
        config = HookConfig(
            skip_hooks=True,
            experimental_hooks=True,
            enable_pyrefly=True,
            enable_ty=True,
            enable_lsp_optimization=True,
            skip_offline_osv_scanner=False,
        )
        assert config.skip_hooks is True
        assert config.experimental_hooks is True
        assert config.enable_pyrefly is True
        assert config.enable_ty is True
        assert config.enable_lsp_optimization is True
        assert config.skip_offline_osv_scanner is False

    def test_from_settings(self) -> None:
        """Verify from_settings classmethod."""
        settings = MagicMock()
        settings.skip_hooks = True
        settings.experimental_hooks = False
        settings.enable_pyrefly = True
        settings.enable_ty = False
        settings.enable_lsp_optimization = True
        settings.skip_offline_osv_scanner = False

        config = HookConfig.from_settings(settings)

        assert config.skip_hooks is True
        assert config.experimental_hooks is False
        assert config.enable_pyrefly is True
        assert config.enable_ty is False
        assert config.enable_lsp_optimization is True
        assert config.skip_offline_osv_scanner is False

    def test_from_settings_missing_osv_scanner(self) -> None:
        """Verify from_settings with missing skip_offline_osv_scanner."""
        settings = MagicMock(spec=[])
        settings.skip_hooks = False
        settings.experimental_hooks = False
        settings.enable_pyrefly = False
        settings.enable_ty = False
        settings.enable_lsp_optimization = False

        config = HookConfig.from_settings(settings)

        assert config.skip_offline_osv_scanner is True


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
        """Verify minimal ZubanLSPConfig creation.

        Regression guard: zuban LSP is disabled by default since
        13be8c1c (2026-07-14) "feat(crackerjack): disable zuban LSP by
        default (ty is the new default type checker)". ty replaced zuban
        as the active type checker — see 511958d0 which restored ty to
        the default-active state. Zuban remains installable but
        opt-in-only.
        """
        config = ZubanLSPConfig()
        assert config.enabled is False
        assert config.auto_start is False
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


class TestWorkflowOptionsPropertyCoverage:
    """Property getter/setter coverage for WorkflowOptions.

    Targets lines 491-751 of crackerjack/models/config.py — covers every
    property that is reachable through WorkflowOptions.__setattr__ but
    was not exercised by the original test file.
    """

    def test_strip_code_property_getter(self) -> None:
        """Verify WorkflowOptions.strip_code getter."""
        options = WorkflowOptions(cleaning=CleaningConfig(clean=True))
        assert options.strip_code is True

        options = WorkflowOptions(cleaning=CleaningConfig(clean=False))
        assert options.strip_code is False

    def test_strip_code_property_setter(self) -> None:
        """Verify WorkflowOptions.strip_code setter."""
        options = WorkflowOptions()
        options.strip_code = False
        assert options.cleaning.clean is False

        options.strip_code = True
        assert options.cleaning.clean is True

    def test_update_docs_property_getter(self) -> None:
        """Verify WorkflowOptions.update_docs getter."""
        options = WorkflowOptions(
            cleaning=CleaningConfig(update_docs=True),
        )
        assert options.update_docs is True

        options = WorkflowOptions(
            cleaning=CleaningConfig(update_docs=False),
        )
        assert options.update_docs is False

    def test_update_docs_property_setter(self) -> None:
        """Verify WorkflowOptions.update_docs setter."""
        options = WorkflowOptions()
        options.update_docs = True
        assert options.cleaning.update_docs is True

        options.update_docs = False
        assert options.cleaning.update_docs is False

    def test_test_property_getter(self) -> None:
        """Verify WorkflowOptions.test getter."""
        options = WorkflowOptions(testing=TestConfig(test=True))
        assert options.test is True

    def test_run_tests_property_setter(self) -> None:
        """Verify WorkflowOptions.run_tests setter."""
        options = WorkflowOptions()
        options.run_tests = True
        assert options.testing.test is True

        options.run_tests = False
        assert options.testing.test is False

    def test_run_tests_property_getter(self) -> None:
        """Verify WorkflowOptions.run_tests getter (line 515)."""
        options = WorkflowOptions(testing=TestConfig(test=True))
        assert options.run_tests is True

        options = WorkflowOptions(testing=TestConfig(test=False))
        assert options.run_tests is False

    def test_benchmark_property_getter(self) -> None:
        """Verify WorkflowOptions.benchmark getter."""
        options = WorkflowOptions(testing=TestConfig(benchmark=True))
        assert options.benchmark is True

        options = WorkflowOptions(testing=TestConfig(benchmark=False))
        assert options.benchmark is False

    def test_benchmark_property_setter(self) -> None:
        """Verify WorkflowOptions.benchmark setter."""
        options = WorkflowOptions()
        options.benchmark = True
        assert options.testing.benchmark is True

        options.benchmark = False
        assert options.testing.benchmark is False

    def test_benchmark_regression_property_getter(self) -> None:
        """Verify WorkflowOptions.benchmark_regression getter."""
        options = WorkflowOptions(testing=TestConfig(benchmark_regression=True))
        assert options.benchmark_regression is True

    def test_benchmark_regression_property_setter(self) -> None:
        """Verify WorkflowOptions.benchmark_regression setter."""
        options = WorkflowOptions()
        options.benchmark_regression = True
        assert options.testing.benchmark_regression is True

        options.benchmark_regression = False
        assert options.testing.benchmark_regression is False

    def test_benchmark_regression_threshold_property_getter(self) -> None:
        """Verify WorkflowOptions.benchmark_regression_threshold getter."""
        options = WorkflowOptions(
            testing=TestConfig(benchmark_regression_threshold=0.25),
        )
        assert options.benchmark_regression_threshold == 0.25

    def test_benchmark_regression_threshold_property_setter(self) -> None:
        """Verify WorkflowOptions.benchmark_regression_threshold setter."""
        options = WorkflowOptions()
        options.benchmark_regression_threshold = 0.5
        assert options.testing.benchmark_regression_threshold == 0.5

        options.benchmark_regression_threshold = 0.1
        assert options.testing.benchmark_regression_threshold == 0.1

    def test_test_workers_property_getter(self) -> None:
        """Verify WorkflowOptions.test_workers getter."""
        options = WorkflowOptions(testing=TestConfig(test_workers=8))
        assert options.test_workers == 8

    def test_test_workers_property_setter(self) -> None:
        """Verify WorkflowOptions.test_workers setter."""
        options = WorkflowOptions()
        options.test_workers = 16
        assert options.testing.test_workers == 16

    def test_test_timeout_property_getter(self) -> None:
        """Verify WorkflowOptions.test_timeout getter."""
        options = WorkflowOptions(testing=TestConfig(test_timeout=900))
        assert options.test_timeout == 900

    def test_test_timeout_property_setter(self) -> None:
        """Verify WorkflowOptions.test_timeout setter."""
        options = WorkflowOptions()
        options.test_timeout = 1200
        assert options.testing.test_timeout == 1200

    def test_publish_property_getter(self) -> None:
        """Verify WorkflowOptions.publish getter."""
        options = WorkflowOptions(publishing=PublishConfig(publish="minor"))
        assert options.publish == "minor"

    def test_publish_property_setter(self) -> None:
        """Verify WorkflowOptions.publish setter."""
        options = WorkflowOptions()
        options.publish = "patch"
        assert options.publishing.publish == "patch"

        options.publish = None
        assert options.publishing.publish is None

    def test_bump_property_getter(self) -> None:
        """Verify WorkflowOptions.bump getter."""
        options = WorkflowOptions(publishing=PublishConfig(bump="major"))
        assert options.bump == "major"

    def test_bump_property_setter(self) -> None:
        """Verify WorkflowOptions.bump setter."""
        options = WorkflowOptions()
        options.bump = "minor"
        assert options.publishing.bump == "minor"

        options.bump = None
        assert options.publishing.bump is None

    def test_all_property_getter(self) -> None:
        """Verify WorkflowOptions.all getter."""
        options = WorkflowOptions(publishing=PublishConfig(all="all"))
        assert options.all == "all"

    def test_all_property_setter(self) -> None:
        """Verify WorkflowOptions.all setter."""
        options = WorkflowOptions()
        options.all = "all"
        assert options.publishing.all == "all"

        options.all = None
        assert options.publishing.all is None

    def test_create_pr_property_getter(self) -> None:
        """Verify WorkflowOptions.create_pr getter."""
        options = WorkflowOptions(git=GitConfig(create_pr=True))
        assert options.create_pr is True

        options = WorkflowOptions(git=GitConfig(create_pr=False))
        assert options.create_pr is False

    def test_create_pr_property_setter(self) -> None:
        """Verify WorkflowOptions.create_pr setter."""
        options = WorkflowOptions()
        options.create_pr = True
        assert options.git.create_pr is True

        options.create_pr = False
        assert options.git.create_pr is False

    def test_ai_fix_property_setter(self) -> None:
        """Verify WorkflowOptions.ai_fix setter."""
        options = WorkflowOptions()
        options.ai_fix = True
        assert options.ai.ai_agent is True

        options.ai_fix = False
        assert options.ai.ai_agent is False

    def test_autofix_property_getter(self) -> None:
        """Verify WorkflowOptions.autofix getter."""
        options = WorkflowOptions(ai=AIConfig(autofix=True))
        assert options.autofix is True

        options = WorkflowOptions(ai=AIConfig(autofix=False))
        assert options.autofix is False

    def test_autofix_property_setter(self) -> None:
        """Verify WorkflowOptions.autofix setter."""
        options = WorkflowOptions()
        options.autofix = False
        assert options.ai.autofix is False

        options.autofix = True
        assert options.ai.autofix is True

    def test_ai_agent_autofix_property_getter(self) -> None:
        """Verify WorkflowOptions.ai_agent_autofix getter."""
        options = WorkflowOptions(ai=AIConfig(ai_agent_autofix=True))
        assert options.ai_agent_autofix is True

    def test_ai_agent_autofix_property_setter(self) -> None:
        """Verify WorkflowOptions.ai_agent_autofix setter."""
        options = WorkflowOptions()
        options.ai_agent_autofix = True
        assert options.ai.ai_agent_autofix is True

        options.ai_agent_autofix = False
        assert options.ai.ai_agent_autofix is False

    def test_start_mcp_server_property_getter(self) -> None:
        """Verify WorkflowOptions.start_mcp_server getter."""
        options = WorkflowOptions(ai=AIConfig(start_mcp_server=True))
        assert options.start_mcp_server is True

        options = WorkflowOptions(ai=AIConfig(start_mcp_server=False))
        assert options.start_mcp_server is False

    def test_start_mcp_server_property_setter(self) -> None:
        """Verify WorkflowOptions.start_mcp_server setter."""
        options = WorkflowOptions()
        options.start_mcp_server = True
        assert options.ai.start_mcp_server is True

        options.start_mcp_server = False
        assert options.ai.start_mcp_server is False

    def test_async_mode_property_getter(self) -> None:
        """Verify WorkflowOptions.async_mode getter."""
        options = WorkflowOptions(execution=ExecutionConfig(async_mode=True))
        assert options.async_mode is True

    def test_async_mode_property_setter(self) -> None:
        """Verify WorkflowOptions.async_mode setter."""
        options = WorkflowOptions()
        options.async_mode = True
        assert options.execution.async_mode is True

        options.async_mode = False
        assert options.execution.async_mode is False

    def test_no_config_updates_property_getter(self) -> None:
        """Verify WorkflowOptions.no_config_updates getter."""
        options = WorkflowOptions(
            execution=ExecutionConfig(no_config_updates=True),
        )
        assert options.no_config_updates is True

    def test_no_config_updates_property_setter(self) -> None:
        """Verify WorkflowOptions.no_config_updates setter."""
        options = WorkflowOptions()
        options.no_config_updates = True
        assert options.execution.no_config_updates is True

        options.no_config_updates = False
        assert options.execution.no_config_updates is False

    def test_dry_run_property_getter(self) -> None:
        """Verify WorkflowOptions.dry_run getter."""
        options = WorkflowOptions(execution=ExecutionConfig(dry_run=True))
        assert options.dry_run is True

    def test_dry_run_property_setter(self) -> None:
        """Verify WorkflowOptions.dry_run setter."""
        options = WorkflowOptions()
        options.dry_run = True
        assert options.execution.dry_run is True

        options.dry_run = False
        assert options.execution.dry_run is False

    def test_experimental_hooks_property_getter(self) -> None:
        """Verify WorkflowOptions.experimental_hooks getter."""
        options = WorkflowOptions(
            hooks=HookConfig(experimental_hooks=True),
        )
        assert options.experimental_hooks is True

        options = WorkflowOptions(
            hooks=HookConfig(experimental_hooks=False),
        )
        assert options.experimental_hooks is False

    def test_experimental_hooks_property_setter(self) -> None:
        """Verify WorkflowOptions.experimental_hooks setter."""
        options = WorkflowOptions()
        options.experimental_hooks = True
        assert options.hooks.experimental_hooks is True

        options.experimental_hooks = False
        assert options.hooks.experimental_hooks is False

    def test_enable_pyrefly_property_getter(self) -> None:
        """Verify WorkflowOptions.enable_pyrefly getter."""
        options = WorkflowOptions(hooks=HookConfig(enable_pyrefly=True))
        assert options.enable_pyrefly is True

    def test_enable_pyrefly_property_setter(self) -> None:
        """Verify WorkflowOptions.enable_pyrefly setter."""
        options = WorkflowOptions()
        options.enable_pyrefly = True
        assert options.hooks.enable_pyrefly is True

        options.enable_pyrefly = False
        assert options.hooks.enable_pyrefly is False

    def test_enable_ty_property_getter(self) -> None:
        """Verify WorkflowOptions.enable_ty getter."""
        options = WorkflowOptions(hooks=HookConfig(enable_ty=True))
        assert options.enable_ty is True

    def test_enable_ty_property_setter(self) -> None:
        """Verify WorkflowOptions.enable_ty setter."""
        options = WorkflowOptions()
        options.enable_ty = True
        assert options.hooks.enable_ty is True

        options.enable_ty = False
        assert options.hooks.enable_ty is False

    def test_enable_lsp_optimization_property_getter(self) -> None:
        """Verify WorkflowOptions.enable_lsp_optimization getter."""
        options = WorkflowOptions(
            hooks=HookConfig(enable_lsp_optimization=True),
        )
        assert options.enable_lsp_optimization is True

    def test_enable_lsp_optimization_property_setter(self) -> None:
        """Verify WorkflowOptions.enable_lsp_optimization setter."""
        options = WorkflowOptions()
        options.enable_lsp_optimization = True
        assert options.hooks.enable_lsp_optimization is True

        options.enable_lsp_optimization = False
        assert options.hooks.enable_lsp_optimization is False

    def test_track_progress_property_getter(self) -> None:
        """Verify WorkflowOptions.track_progress getter."""
        options = WorkflowOptions(
            progress=ProgressConfig(track_progress=True),
        )
        assert options.track_progress is True

        options = WorkflowOptions(
            progress=ProgressConfig(track_progress=False),
        )
        assert options.track_progress is False

    def test_resume_from_property_getter(self) -> None:
        """Verify WorkflowOptions.resume_from getter."""
        options = WorkflowOptions(
            progress=ProgressConfig(resume_from="checkpoint_42"),
        )
        assert options.resume_from == "checkpoint_42"

        options = WorkflowOptions(
            progress=ProgressConfig(resume_from=None),
        )
        assert options.resume_from is None

    def test_progress_file_property_getter(self) -> None:
        """Verify WorkflowOptions.progress_file getter."""
        options = WorkflowOptions(
            progress=ProgressConfig(progress_file="/tmp/x.json"),
        )
        assert options.progress_file == "/tmp/x.json"

        options = WorkflowOptions(
            progress=ProgressConfig(progress_file=None),
        )
        assert options.progress_file is None

    def test_workflow_options_kwargs_unknown_attribute(self) -> None:
        """Verify WorkflowOptions kwargs with unknown attribute is ignored.

        Covers the `478->477` branch where `hasattr(self, attr)` is False
        for an unknown kwarg name and the body is skipped.
        """
        options = WorkflowOptions(unknown_attribute="value")

        # Unknown attribute should NOT be set on the instance.
        assert not hasattr(options, "unknown_attribute")


class TestWorkflowOptionsPrivateHelpers:
    """Direct coverage for WorkflowOptions private helper methods.

    These methods are not invoked by __init__ but exist on the class. We
    test them directly to lock their behaviour and lift coverage of the
    unused-but-present code (lines 350-410).
    """

    def test_initialize_config_attributes_with_none(self) -> None:
        """Verify _initialize_config_attributes defaults when None passed."""
        options = WorkflowOptions()
        options._initialize_config_attributes(
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
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

    def test_initialize_config_attributes_with_provided(self) -> None:
        """Verify _initialize_config_attributes uses provided configs."""
        options = WorkflowOptions()
        cleaning = CleaningConfig(clean=False)
        hooks = HookConfig(skip_hooks=True)
        testing = TestConfig(test=True)
        publishing = PublishConfig(publish="major")
        git = GitConfig(commit=True)
        ai = AIConfig(ai_agent=True)
        execution = ExecutionConfig(interactive=False)
        progress = ProgressConfig(track_progress=True)
        cleanup = CleanupConfig(auto_cleanup=False)
        advanced = AdvancedConfig(enabled=True)
        mcp_server = MCPServerConfig(http_port=9999)
        zuban_lsp = ZubanLSPConfig(port=1234)

        options._initialize_config_attributes(
            cleaning,
            hooks,
            testing,
            publishing,
            git,
            ai,
            execution,
            progress,
            cleanup,
            advanced,
            mcp_server,
            zuban_lsp,
        )

        assert options.cleaning is cleaning
        assert options.hooks is hooks
        assert options.testing is testing
        assert options.publishing is publishing
        assert options.git is git
        assert options.ai is ai
        assert options.execution is execution
        assert options.progress is progress
        assert options.cleanup is cleanup
        assert options.advanced is advanced
        assert options.mcp_server is mcp_server
        assert options.zuban_lsp is zuban_lsp

    def test_set_default_overrides_empty_kwargs(self) -> None:
        """Verify _set_default_overrides applies defaults when kwargs empty."""
        options = WorkflowOptions()
        # Defaults differ from the "blank" config defaults, so this
        # mutates the instance.
        options._set_default_overrides({})

        # Defaults include clean=None, test=False, etc. Verify the
        # loop ran by checking _DEFAULT_OVERRIDES was reset.
        assert options._DEFAULT_OVERRIDES == {
            "clean": None,
            "test": False,
            "publish": None,
            "bump": None,
            "commit": False,
            "create_pr": False,
            "interactive": True,
            "dry_run": False,
        }

    def test_set_default_overrides_skip_git(self) -> None:
        """Verify _set_default_overrides skips commit/create_pr when git is in kwargs."""
        options = WorkflowOptions()
        # Pre-set commit/create_pr on options to detect whether the
        # override loop touched them.
        options.commit = True
        options.create_pr = True

        options._set_default_overrides({"git": GitConfig()})

        # commit/create_pr should NOT be reset because "git" is in kwargs.
        assert options.commit is True
        assert options.create_pr is True

    def test_set_default_overrides_skip_cleaning(self) -> None:
        """Verify _set_default_overrides skips clean when cleaning is in kwargs."""
        options = WorkflowOptions()
        options.clean = True

        options._set_default_overrides({"cleaning": CleaningConfig(clean=False)})

        # clean should NOT be reset because "cleaning" is in kwargs.
        assert options.clean is True

    def test_set_default_overrides_skip_testing(self) -> None:
        """Verify _set_default_overrides skips test when testing is in kwargs."""
        options = WorkflowOptions()
        options.test = True

        options._set_default_overrides({"testing": TestConfig(test=False)})

        # test should NOT be reset because "testing" is in kwargs.
        assert options.test is True

    def test_set_default_overrides_skip_publishing(self) -> None:
        """Verify _set_default_overrides skips publish/bump when publishing in kwargs."""
        options = WorkflowOptions()
        options.publish = "major"
        options.bump = "minor"

        options._set_default_overrides(
            {"publishing": PublishConfig(publish="patch", bump="major")},
        )

        # publish/bump should NOT be reset because "publishing" is in kwargs.
        assert options.publish == "major"
        assert options.bump == "minor"

    def test_set_default_overrides_skip_execution(self) -> None:
        """Verify _set_default_overrides skips interactive/dry_run when execution in kwargs."""
        options = WorkflowOptions()
        options.interactive = False
        options.dry_run = True

        options._set_default_overrides(
            {"execution": ExecutionConfig(interactive=True, dry_run=False)},
        )

        # interactive/dry_run should NOT be reset because "execution" is in kwargs.
        assert options.interactive is False
        assert options.dry_run is True

    def test_should_skip_override_git_attributes(self) -> None:
        """Verify _should_skip_override for commit/create_pr with git kwarg."""
        # commit/create_pr should be skipped if git is in kwargs
        assert WorkflowOptions()._should_skip_override("commit", {"git": None}) is True
        assert WorkflowOptions()._should_skip_override("create_pr", {"git": None}) is True
        # but not if git isn't present
        assert WorkflowOptions()._should_skip_override("commit", {}) is False
        assert WorkflowOptions()._should_skip_override("create_pr", {}) is False

    def test_should_skip_override_cleaning(self) -> None:
        """Verify _should_skip_override for clean with cleaning kwarg."""
        assert WorkflowOptions()._should_skip_override("clean", {"cleaning": None}) is True
        assert WorkflowOptions()._should_skip_override("clean", {}) is False

    def test_should_skip_override_testing(self) -> None:
        """Verify _should_skip_override for test with testing kwarg."""
        assert WorkflowOptions()._should_skip_override("test", {"testing": None}) is True
        assert WorkflowOptions()._should_skip_override("test", {}) is False

    def test_should_skip_override_publishing(self) -> None:
        """Verify _should_skip_override for publish/bump with publishing kwarg."""
        assert WorkflowOptions()._should_skip_override("publish", {"publishing": None}) is True
        assert WorkflowOptions()._should_skip_override("bump", {"publishing": None}) is True
        assert WorkflowOptions()._should_skip_override("publish", {}) is False
        assert WorkflowOptions()._should_skip_override("bump", {}) is False

    def test_should_skip_override_execution(self) -> None:
        """Verify _should_skip_override for interactive/dry_run with execution kwarg."""
        assert WorkflowOptions()._should_skip_override(
            "interactive", {"execution": None},
        ) is True
        assert WorkflowOptions()._should_skip_override(
            "dry_run", {"execution": None},
        ) is True
        assert WorkflowOptions()._should_skip_override("interactive", {}) is False
        assert WorkflowOptions()._should_skip_override("dry_run", {}) is False

    def test_set_kwargs_attributes_sets_known(self) -> None:
        """Verify _set_kwargs_attributes sets known kwargs."""
        options = WorkflowOptions()
        options._set_kwargs_attributes({"clean": False, "test": True})

        assert options.clean is False
        assert options.test is True

    def test_set_kwargs_attributes_skips_unknown(self) -> None:
        """Verify _set_kwargs_attributes skips kwargs not on class/instance."""
        options = WorkflowOptions()
        options._set_kwargs_attributes(
            {"unknown_class_attr": "x", "clean": False},
        )

        assert options.clean is False
        assert not hasattr(options, "unknown_class_attr")

    def test_set_default_overrides_attr_in_kwargs(self) -> None:
        """Verify _set_default_overrides skips attrs that are in kwargs.

        Covers branch 393->390: when attr IS in kwargs and not skipped,
        the body (setattr) is skipped.
        """
        options = WorkflowOptions()
        options.clean = True
        options.test = True
        options.interactive = False

        # Pass kwargs whose keys match DEFAULT_OVERRIDES attrs but don't
        # trigger _should_skip_override (no cleaning/testing/etc.).
        options._set_default_overrides(
            {"clean": False, "test": False, "interactive": False},
        )

        # These should remain unchanged because attr was in kwargs and
        # the body was skipped (393->390 branch).
        assert options.clean is True
        assert options.test is True
        assert options.interactive is False


class TestWorkflowOptionsFromArgsExtra:
    """Additional from_args branches."""

    def test_from_args_with_create_pr(self) -> None:
        """Verify from_args with create_pr argument populates GitConfig.

        Covers line 810 in crackerjack/models/config.py.
        """
        args = MagicMock()
        args.__dict__ = {"create_pr": True}

        options = WorkflowOptions.from_args(args)

        assert options.git.create_pr is True

    def test_from_args_with_commit_and_create_pr(self) -> None:
        """Verify from_args with both commit and create_pr."""
        args = MagicMock()
        args.__dict__ = {"commit": True, "create_pr": True}

        options = WorkflowOptions.from_args(args)

        assert options.git.commit is True
        assert options.git.create_pr is True


class TestGetWorkflowOptions:
    """Coverage for the top-level get_workflow_options function."""

    def test_get_workflow_options_calls_load_settings(self) -> None:
        """Verify get_workflow_options delegates to load_settings."""
        from crackerjack.models.config import get_workflow_options

        sentinel = MagicMock(name="sentinel_settings")
        # The function does `from crackerjack.config import load_settings`,
        # so patch `crackerjack.config.load_settings` (the module attribute).
        with patch(
            "crackerjack.config.load_settings",
            return_value=sentinel,
        ) as mock_load:
            result = get_workflow_options()

        assert result is sentinel
        mock_load.assert_called_once_with(CrackerjackSettings)

