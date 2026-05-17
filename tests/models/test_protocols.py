"""Tests for protocols module - @runtime_checkable Protocol definitions."""

from __future__ import annotations

import asyncio
import subprocess
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from crackerjack.models.protocols import (
    AdapterFactoryProtocol,
    AdapterProtocol,
    AgentCoordinatorProtocol,
    AgentDelegatorProtocol,
    AgentRegistryProtocol,
    AgentTrackerProtocol,
    APIExtractorProtocol,
    AsyncCommandExecutorProtocol,
    AsyncHookExecutorProtocol,
    BoundedStatusOperationsProtocol,
    ChangelogGeneratorProtocol,
    CommandRunner,
    ConfigIntegrityServiceProtocol,
    ConfigManagerProtocol,
    ConfigMergeServiceProtocol,
    ConsoleInterface,
    CoverageBadgeServiceProtocol,
    CoverageRatchetProtocol,
    DebuggerProtocol,
    DocumentationGeneratorProtocol,
    DocumentationServiceProtocol,
    DocumentationValidatorProtocol,
    EnhancedFileSystemServiceProtocol,
    FileSystemInterface,
    FileSystemServiceProtocol,
    GitInterface,
    HookConfigLoaderProtocol,
    HookExecutorProtocol,
    HookLockManagerProtocol,
    HookManager,
    InitializationServiceProtocol,
    LoggerProtocol,
    MCPIntegrationProtocol,
    MemoryOptimizerProtocol,
    OptionsProtocol,
    ParallelHookExecutorProtocol,
    PerformanceCacheProtocol,
    PluginRegistryProtocol,
    PublishManager,
    QualityBaselineProtocol,
    QualityIntelligenceProtocol,
    ReflectionLoopProtocol,
    RegexPatternsProtocol,
    SafeFileModifierProtocol,
    SecurityAwareHookManager,
    SecurityServiceProtocol,
    SecureStatusFormatterProtocol,
    SecureSubprocessExecutorProtocol,
    ServiceProtocol,
    SmartFileFilterProtocol,
    SmartSchedulingServiceProtocol,
    TestManagerProtocol,
    UnifiedConfigurationServiceProtocol,
    VersionAnalyzerProtocol,
)


# ============================================================================
# Base Service Protocol Tests
# ============================================================================


class TestServiceProtocol:
    """Tests for ServiceProtocol base interface."""

    def test_service_protocol_is_runtime_checkable(self) -> None:
        """Verify ServiceProtocol can be checked with isinstance."""
        mock_service = MagicMock()
        mock_service.initialize = MagicMock(return_value=None)
        mock_service.cleanup = MagicMock(return_value=None)
        mock_service.health_check = MagicMock(return_value=True)
        mock_service.shutdown = MagicMock(return_value=None)
        mock_service.metrics = MagicMock(return_value={"uptime": 100})
        mock_service.is_healthy = MagicMock(return_value=True)
        mock_service.register_resource = MagicMock(return_value=None)
        mock_service.cleanup_resource = MagicMock(return_value=None)
        mock_service.record_error = MagicMock(return_value=None)
        mock_service.increment_requests = MagicMock(return_value=None)
        mock_service.get_custom_metric = MagicMock(return_value="value")
        mock_service.set_custom_metric = MagicMock(return_value=None)

        assert isinstance(mock_service, ServiceProtocol)

    def test_service_protocol_minimal_implementation(self) -> None:
        """Verify minimal ServiceProtocol implementation."""

        class MinimalService:
            def initialize(self) -> None:
                pass

            def cleanup(self) -> None:
                pass

            def health_check(self) -> bool:
                return True

            def shutdown(self) -> None:
                pass

            def metrics(self) -> dict[str, t.Any]:
                return {}

            def is_healthy(self) -> bool:
                return True

            def register_resource(self, resource: t.Any) -> None:
                pass

            def cleanup_resource(self, resource: t.Any) -> None:
                pass

            def record_error(self, error: Exception) -> None:
                pass

            def increment_requests(self) -> None:
                pass

            def get_custom_metric(self, name: str) -> t.Any:
                return None

            def set_custom_metric(self, name: str, value: t.Any) -> None:
                pass

        service = MinimalService()
        assert isinstance(service, ServiceProtocol)


class TestCommandRunner:
    """Tests for CommandRunner protocol."""

    def test_command_runner_is_runtime_checkable(self) -> None:
        """Verify CommandRunner can be checked with isinstance."""
        mock_runner = MagicMock()
        completed = subprocess.CompletedProcess(
            args=["echo", "test"], returncode=0, stdout="test", stderr=""
        )
        mock_runner.execute_command = MagicMock(return_value=completed)

        assert isinstance(mock_runner, CommandRunner)

    def test_command_runner_execute_command(self) -> None:
        """Verify execute_command method signature."""

        class SimpleRunner:
            def execute_command(
                self,
                cmd: list[str],
                **kwargs: t.Any,
            ) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="", stderr=""
                )

        runner = SimpleRunner()
        assert isinstance(runner, CommandRunner)

        result = runner.execute_command(["echo", "test"])
        assert result.returncode == 0
        assert result.args == ["echo", "test"]


class TestOptionsProtocol:
    """Tests for OptionsProtocol attribute-based protocol."""

    def test_options_protocol_is_runtime_checkable(self) -> None:
        """Verify OptionsProtocol can be checked with isinstance."""
        mock_options = MagicMock()
        # Set required attributes
        mock_options.test = True
        mock_options.run_tests = True
        mock_options.test_workers = 0
        mock_options.test_timeout = 0
        mock_options.benchmark = False
        mock_options.benchmark_regression = False
        mock_options.benchmark_regression_threshold = 0.1
        mock_options.fast = False
        mock_options.comp = False
        mock_options.skip_hooks = False
        mock_options.tool = None
        mock_options.changed_only = False
        mock_options.advanced_batch = None
        mock_options.ai_agent = False
        mock_options.ai_fix_max_iterations = 10
        mock_options.publish = None
        mock_options.bump = None
        mock_options.all = None
        mock_options.create_pr = False
        mock_options.keep_releases = 10
        mock_options.cleanup_pypi = False
        mock_options.no_git_tags = False
        mock_options.skip_version_check = False
        mock_options.coverage = False
        mock_options.commit = False
        mock_options.interactive = False
        mock_options.no_config_updates = False
        mock_options.skip_config_merge = False
        mock_options.verbose = False
        mock_options.track_progress = False
        mock_options.clean = False
        mock_options.cleanup = None
        mock_options.async_mode = False
        mock_options.experimental_hooks = False
        mock_options.enable_pyrefly = False
        mock_options.enable_ty = False
        mock_options.disable_global_locks = False
        mock_options.global_lock_timeout = 600
        mock_options.global_lock_cleanup = True
        mock_options.global_lock_dir = None
        mock_options.strip_code = False
        mock_options.xcode_tests = False
        mock_options.xcode_project = "app/MdInjectApp/MdInjectApp.xcodeproj"
        mock_options.xcode_scheme = "MdInjectApp"
        mock_options.xcode_configuration = "Debug"
        mock_options.xcode_destination = "platform=macOS"
        mock_options.fast_iteration = False
        mock_options.monitor_dashboard = None
        mock_options.start_mcp_server = False
        mock_options.generate_docs = False
        mock_options.docs_format = "markdown"
        mock_options.validate_docs = False
        mock_options.update_docs_index = False

        assert isinstance(mock_options, OptionsProtocol)

    def test_options_protocol_with_dataclass(self) -> None:
        """Verify OptionsProtocol with dataclass implementation."""
        from dataclasses import dataclass

        @dataclass
        class SimpleOptions:
            test: bool = False
            run_tests: bool = False
            test_workers: int = 0
            test_timeout: int = 0
            benchmark: bool = False
            benchmark_regression: bool = False
            benchmark_regression_threshold: float = 0.1
            fast: bool = False
            comp: bool = False
            skip_hooks: bool = False
            tool: str | None = None
            changed_only: bool = False
            advanced_batch: str | None = None
            ai_agent: bool = False
            ai_fix_max_iterations: int = 10
            publish: t.Any | None = None
            bump: t.Any | None = None
            all: t.Any | None = None
            create_pr: bool = False
            keep_releases: int = 10
            cleanup_pypi: bool = False
            no_git_tags: bool = False
            skip_version_check: bool = False
            coverage: bool = False
            commit: bool = False
            interactive: bool = False
            no_config_updates: bool = False
            skip_config_merge: bool = False
            verbose: bool = False
            track_progress: bool = False
            clean: bool = False
            cleanup: t.Any | None = None
            async_mode: bool = False
            experimental_hooks: bool = False
            enable_pyrefly: bool = False
            enable_ty: bool = False
            disable_global_locks: bool = False
            global_lock_timeout: int = 600
            global_lock_cleanup: bool = True
            global_lock_dir: str | None = None
            strip_code: bool = False
            xcode_tests: bool = False
            xcode_project: str = "app/MdInjectApp/MdInjectApp.xcodeproj"
            xcode_scheme: str = "MdInjectApp"
            xcode_configuration: str = "Debug"
            xcode_destination: str = "platform=macOS"
            fast_iteration: bool = False
            monitor_dashboard: str | None = None
            start_mcp_server: bool = False
            generate_docs: bool = False
            docs_format: str = "markdown"
            validate_docs: bool = False
            update_docs_index: bool = False

        options = SimpleOptions()
        assert isinstance(options, OptionsProtocol)


# ============================================================================
# Console and File System Interface Tests
# ============================================================================


class TestConsoleInterface:
    """Tests for ConsoleInterface protocol."""

    def test_console_interface_is_runtime_checkable(self) -> None:
        """Verify ConsoleInterface can be checked with isinstance."""
        mock_console = MagicMock()
        mock_console.print = MagicMock(return_value=None)
        mock_console.input = MagicMock(return_value="user_input")

        assert isinstance(mock_console, ConsoleInterface)

    def test_console_interface_implementation(self) -> None:
        """Verify ConsoleInterface implementation."""

        class SimpleConsole:
            def print(self, *args: t.Any, **kwargs: t.Any) -> None:
                pass

            def input(self, prompt: str = "") -> str:
                return "test"

        console = SimpleConsole()
        assert isinstance(console, ConsoleInterface)
        assert console.input("Enter: ") == "test"


class TestFileSystemInterface:
    """Tests for FileSystemInterface protocol."""

    def test_file_system_interface_is_runtime_checkable(self) -> None:
        """Verify FileSystemInterface can be checked with isinstance."""
        mock_fs = MagicMock()
        mock_fs.read_file = MagicMock(return_value="content")
        mock_fs.write_file = MagicMock(return_value=None)
        mock_fs.exists = MagicMock(return_value=True)
        mock_fs.mkdir = MagicMock(return_value=None)

        assert isinstance(mock_fs, FileSystemInterface)

    def test_file_system_interface_implementation(self) -> None:
        """Verify FileSystemInterface implementation."""

        class SimpleFileSystem:
            def read_file(self, path: str | t.Any) -> str:
                return "content"

            def write_file(self, path: str | t.Any, content: str) -> None:
                pass

            def exists(self, path: str | t.Any) -> bool:
                return True

            def mkdir(self, path: str | t.Any, parents: bool = False) -> None:
                pass

        fs = SimpleFileSystem()
        assert isinstance(fs, FileSystemInterface)
        assert fs.read_file("test.txt") == "content"
        assert fs.exists("test.txt") is True


class TestGitInterface:
    """Tests for GitInterface protocol."""

    def test_git_interface_is_runtime_checkable(self) -> None:
        """Verify GitInterface can be checked with isinstance."""
        mock_git = MagicMock()
        mock_git.is_git_repo = MagicMock(return_value=True)
        mock_git.get_changed_files = MagicMock(return_value=["file1.py", "file2.py"])
        mock_git.commit = MagicMock(return_value=True)
        mock_git.push = MagicMock(return_value=True)
        mock_git.add_files = MagicMock(return_value=True)
        mock_git.add_all_files = MagicMock(return_value=True)

        assert isinstance(mock_git, GitInterface)

    def test_git_interface_implementation(self) -> None:
        """Verify GitInterface implementation."""

        class SimpleGit:
            def is_git_repo(self) -> bool:
                return True

            def get_changed_files(self) -> list[str]:
                return ["file1.py"]

            def commit(self, message: str) -> bool:
                return True

            def push(self) -> bool:
                return True

            def add_files(self, files: list[str]) -> bool:
                return True

            def add_all_files(self) -> bool:
                return True

        git = SimpleGit()
        assert isinstance(git, GitInterface)
        assert git.is_git_repo() is True
        assert "file1.py" in git.get_changed_files()


# ============================================================================
# Hook Manager Protocol Tests
# ============================================================================


class TestHookManager:
    """Tests for HookManager protocol."""

    def test_hook_manager_is_runtime_checkable(self) -> None:
        """Verify HookManager can be checked with isinstance."""
        mock_manager = MagicMock()
        mock_manager.run_fast_hooks = MagicMock(return_value=[])
        mock_manager.run_comprehensive_hooks = MagicMock(return_value=[])
        mock_manager.install_hooks = MagicMock(return_value=True)
        mock_manager.set_config_path = MagicMock(return_value=None)
        mock_manager.get_hook_summary = MagicMock(return_value={})

        assert isinstance(mock_manager, HookManager)

    def test_hook_manager_implementation(self) -> None:
        """Verify HookManager implementation."""

        class SimpleHookManager:
            def run_fast_hooks(self) -> list[t.Any]:
                return []

            def run_comprehensive_hooks(self) -> list[t.Any]:
                return []

            def install_hooks(self) -> bool:
                return True

            def set_config_path(self, path: str | t.Any) -> None:
                pass

            def get_hook_summary(
                self,
                results: t.Any,
                elapsed_time: float | None = None,
            ) -> t.Any:
                return {}

        manager = SimpleHookManager()
        assert isinstance(manager, HookManager)


class TestSecurityAwareHookManager:
    """Tests for SecurityAwareHookManager protocol (extends HookManager)."""

    def test_security_aware_hook_manager_is_runtime_checkable(self) -> None:
        """Verify SecurityAwareHookManager can be checked with isinstance."""
        mock_manager = MagicMock()
        # HookManager methods
        mock_manager.run_fast_hooks = MagicMock(return_value=[])
        mock_manager.run_comprehensive_hooks = MagicMock(return_value=[])
        mock_manager.install_hooks = MagicMock(return_value=True)
        mock_manager.set_config_path = MagicMock(return_value=None)
        mock_manager.get_hook_summary = MagicMock(return_value={})
        # SecurityAwareHookManager methods
        mock_manager.get_security_critical_failures = MagicMock(return_value=[])
        mock_manager.has_security_critical_failures = MagicMock(return_value=False)
        mock_manager.get_security_audit_report = MagicMock(return_value={})

        assert isinstance(mock_manager, SecurityAwareHookManager)

    def test_security_aware_inherits_hook_manager(self) -> None:
        """Verify SecurityAwareHookManager is also a HookManager."""

        class SecureManager:
            def run_fast_hooks(self) -> list[t.Any]:
                return []

            def run_comprehensive_hooks(self) -> list[t.Any]:
                return []

            def install_hooks(self) -> bool:
                return True

            def set_config_path(self, path: str | t.Any) -> None:
                pass

            def get_hook_summary(
                self,
                results: t.Any,
                elapsed_time: float | None = None,
            ) -> t.Any:
                return {}

            def get_security_critical_failures(
                self, results: list[t.Any]
            ) -> list[t.Any]:
                return []

            def has_security_critical_failures(self, results: list[t.Any]) -> bool:
                return False

            def get_security_audit_report(
                self,
                fast_results: list[t.Any],
                comprehensive_results: list[t.Any],
            ) -> dict[str, t.Any]:
                return {}

        manager = SecureManager()
        assert isinstance(manager, SecurityAwareHookManager)
        assert isinstance(manager, HookManager)


# ============================================================================
# Service Protocol Implementations Tests
# ============================================================================


class TestCoverageRatchetProtocol:
    """Tests for CoverageRatchetProtocol (extends ServiceProtocol)."""

    def test_coverage_ratchet_is_runtime_checkable(self) -> None:
        """Verify CoverageRatchetProtocol can be checked with isinstance."""
        mock_ratchet = MagicMock()
        # ServiceProtocol methods
        mock_ratchet.initialize = MagicMock(return_value=None)
        mock_ratchet.cleanup = MagicMock(return_value=None)
        mock_ratchet.health_check = MagicMock(return_value=True)
        mock_ratchet.shutdown = MagicMock(return_value=None)
        mock_ratchet.metrics = MagicMock(return_value={})
        mock_ratchet.is_healthy = MagicMock(return_value=True)
        mock_ratchet.register_resource = MagicMock(return_value=None)
        mock_ratchet.cleanup_resource = MagicMock(return_value=None)
        mock_ratchet.record_error = MagicMock(return_value=None)
        mock_ratchet.increment_requests = MagicMock(return_value=None)
        mock_ratchet.get_custom_metric = MagicMock(return_value=None)
        mock_ratchet.set_custom_metric = MagicMock(return_value=None)
        # CoverageRatchetProtocol methods
        mock_ratchet.get_baseline_coverage = MagicMock(return_value=0.5)
        mock_ratchet.update_baseline_coverage = MagicMock(return_value=True)
        mock_ratchet.is_coverage_regression = MagicMock(return_value=False)
        mock_ratchet.get_coverage_improvement_needed = MagicMock(return_value=0.1)
        mock_ratchet.get_status_report = MagicMock(return_value={})
        mock_ratchet.get_coverage_report = MagicMock(return_value="Report")
        mock_ratchet.check_and_update_coverage = MagicMock(return_value={})

        assert isinstance(mock_ratchet, CoverageRatchetProtocol)


class TestSecurityServiceProtocol:
    """Tests for SecurityServiceProtocol (extends ServiceProtocol)."""

    def test_security_service_is_runtime_checkable(self) -> None:
        """Verify SecurityServiceProtocol can be checked with isinstance."""
        mock_service = MagicMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_service, method_name, MagicMock())
        # SecurityServiceProtocol methods
        mock_service.validate_file_safety = MagicMock(return_value=True)
        mock_service.check_hardcoded_secrets = MagicMock(return_value=[])
        mock_service.is_safe_subprocess_call = MagicMock(return_value=True)
        mock_service.create_secure_command_env = MagicMock(return_value={})
        mock_service.mask_tokens = MagicMock(return_value="masked")
        mock_service.validate_token_format = MagicMock(return_value=True)

        assert isinstance(mock_service, SecurityServiceProtocol)


class TestTestManagerProtocol:
    """Tests for TestManagerProtocol (extends ServiceProtocol)."""

    def test_test_manager_is_runtime_checkable(self) -> None:
        """Verify TestManagerProtocol can be checked with isinstance."""
        mock_manager = MagicMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_manager, method_name, MagicMock())
        # TestManagerProtocol methods
        mock_manager.run_tests = MagicMock(return_value=True)
        mock_manager.get_test_failures = MagicMock(return_value=[])
        mock_manager.validate_test_environment = MagicMock(return_value=True)
        mock_manager.get_coverage = MagicMock(return_value={})

        assert isinstance(mock_manager, TestManagerProtocol)


# ============================================================================
# Documentation and API Extraction Protocols Tests
# ============================================================================


class TestAPIExtractorProtocol:
    """Tests for APIExtractorProtocol."""

    def test_api_extractor_is_runtime_checkable(self) -> None:
        """Verify APIExtractorProtocol can be checked with isinstance."""
        mock_extractor = MagicMock()
        mock_extractor.extract_from_python_files = MagicMock(return_value={})
        mock_extractor.extract_protocol_definitions = MagicMock(return_value={})
        mock_extractor.extract_service_interfaces = MagicMock(return_value={})
        mock_extractor.extract_cli_commands = MagicMock(return_value={})
        mock_extractor.extract_mcp_tools = MagicMock(return_value={})

        assert isinstance(mock_extractor, APIExtractorProtocol)


class TestDocumentationGeneratorProtocol:
    """Tests for DocumentationGeneratorProtocol."""

    def test_documentation_generator_is_runtime_checkable(self) -> None:
        """Verify DocumentationGeneratorProtocol can be checked with isinstance."""
        mock_gen = MagicMock()
        mock_gen.generate_api_reference = MagicMock(return_value="api_ref")
        mock_gen.generate_user_guide = MagicMock(return_value="guide")
        mock_gen.generate_changelog_update = MagicMock(return_value="changelog")
        mock_gen.render_template = MagicMock(return_value="rendered")
        mock_gen.generate_cross_references = MagicMock(return_value={})

        assert isinstance(mock_gen, DocumentationGeneratorProtocol)


class TestDocumentationValidatorProtocol:
    """Tests for DocumentationValidatorProtocol."""

    def test_documentation_validator_is_runtime_checkable(self) -> None:
        """Verify DocumentationValidatorProtocol can be checked with isinstance."""
        mock_validator = MagicMock()
        mock_validator.validate_links = MagicMock(return_value=[])
        mock_validator.check_documentation_freshness = MagicMock(return_value={})
        mock_validator.validate_cross_references = MagicMock(return_value=[])
        mock_validator.calculate_coverage_metrics = MagicMock(return_value={})

        assert isinstance(mock_validator, DocumentationValidatorProtocol)


# ============================================================================
# Logging and Configuration Protocol Tests
# ============================================================================


class TestLoggerProtocol:
    """Tests for LoggerProtocol."""

    def test_logger_is_runtime_checkable(self) -> None:
        """Verify LoggerProtocol can be checked with isinstance."""
        mock_logger = MagicMock()
        mock_logger.info = MagicMock(return_value=None)
        mock_logger.warning = MagicMock(return_value=None)
        mock_logger.error = MagicMock(return_value=None)
        mock_logger.debug = MagicMock(return_value=None)
        mock_logger.exception = MagicMock(return_value=None)

        assert isinstance(mock_logger, LoggerProtocol)

    def test_logger_implementation(self) -> None:
        """Verify LoggerProtocol implementation."""

        class SimpleLogger:
            def info(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
                pass

            def warning(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
                pass

            def error(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
                pass

            def debug(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
                pass

            def exception(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
                pass

        logger = SimpleLogger()
        assert isinstance(logger, LoggerProtocol)


class TestConfigManagerProtocol:
    """Tests for ConfigManagerProtocol."""

    def test_config_manager_is_runtime_checkable(self) -> None:
        """Verify ConfigManagerProtocol can be checked with isinstance."""
        mock_manager = MagicMock()
        mock_manager.get = MagicMock(return_value="value")
        mock_manager.set = MagicMock(return_value=None)
        mock_manager.save = MagicMock(return_value=True)
        mock_manager.load = MagicMock(return_value=True)

        assert isinstance(mock_manager, ConfigManagerProtocol)


class TestFileSystemServiceProtocol:
    """Tests for FileSystemServiceProtocol."""

    def test_file_system_service_is_runtime_checkable(self) -> None:
        """Verify FileSystemServiceProtocol can be checked with isinstance."""
        mock_fs = MagicMock()
        mock_fs.read_file = MagicMock(return_value="content")
        mock_fs.write_file = MagicMock(return_value=None)
        mock_fs.exists = MagicMock(return_value=True)
        mock_fs.mkdir = MagicMock(return_value=None)
        mock_fs.ensure_directory = MagicMock(return_value=None)

        assert isinstance(mock_fs, FileSystemServiceProtocol)


# ============================================================================
# Adapter Protocols Tests
# ============================================================================


class TestAdapterProtocol:
    """Tests for AdapterProtocol."""

    @pytest.mark.asyncio
    async def test_adapter_protocol_is_runtime_checkable(self) -> None:
        """Verify AdapterProtocol can be checked with isinstance."""
        mock_adapter = AsyncMock()
        mock_adapter.adapter_name = "test-adapter"
        mock_adapter.init = AsyncMock(return_value=None)
        mock_adapter.check = AsyncMock(return_value=MagicMock())
        mock_adapter.health_check = AsyncMock(return_value={})

        assert isinstance(mock_adapter, AdapterProtocol)

    def test_adapter_protocol_with_property(self) -> None:
        """Verify AdapterProtocol with property decorator."""

        class SimpleAdapter:
            @property
            def adapter_name(self) -> str:
                return "test-adapter"

            async def init(self) -> None:
                pass

            async def check(
                self,
                files: list[Path] | None = None,
                config: t.Any | None = None,
            ) -> t.Any:
                return None

            async def health_check(self) -> dict[str, t.Any]:
                return {}

        adapter = SimpleAdapter()
        assert isinstance(adapter, AdapterProtocol)
        assert adapter.adapter_name == "test-adapter"


class TestAdapterFactoryProtocol:
    """Tests for AdapterFactoryProtocol."""

    def test_adapter_factory_is_runtime_checkable(self) -> None:
        """Verify AdapterFactoryProtocol can be checked with isinstance."""
        mock_factory = MagicMock()
        mock_factory.create_adapter = MagicMock(return_value=MagicMock())

        assert isinstance(mock_factory, AdapterFactoryProtocol)


# ============================================================================
# Plugin and Registry Protocol Tests
# ============================================================================


class TestPluginRegistryProtocol:
    """Tests for PluginRegistryProtocol."""

    def test_plugin_registry_is_runtime_checkable(self) -> None:
        """Verify PluginRegistryProtocol can be checked with isinstance."""
        mock_registry = MagicMock()
        mock_registry.register_plugin = MagicMock(return_value=None)
        mock_registry.activate_plugin = MagicMock(return_value=None)
        mock_registry.deactivate_plugin = MagicMock(return_value=None)
        mock_registry.get_plugin = MagicMock(return_value=None)
        mock_registry.get_plugins_by_type = MagicMock(return_value=[])
        mock_registry.list_plugins = MagicMock(return_value=[])

        assert isinstance(mock_registry, PluginRegistryProtocol)


class TestAgentRegistryProtocol:
    """Tests for AgentRegistryProtocol."""

    @pytest.mark.asyncio
    async def test_agent_registry_is_runtime_checkable(self) -> None:
        """Verify AgentRegistryProtocol can be checked with isinstance."""
        mock_registry = AsyncMock()
        mock_registry.register_agent = AsyncMock(return_value=None)
        mock_registry.get_agent = MagicMock(return_value=None)
        mock_registry.list_agents = MagicMock(return_value=[])
        mock_registry.create_agent = AsyncMock(return_value=None)

        assert isinstance(mock_registry, AgentRegistryProtocol)


# ============================================================================
# Async Protocol Tests
# ============================================================================


class TestAsyncCommandExecutorProtocol:
    """Tests for AsyncCommandExecutorProtocol."""

    @pytest.mark.asyncio
    async def test_async_command_executor_is_runtime_checkable(self) -> None:
        """Verify AsyncCommandExecutorProtocol can be checked with isinstance."""
        mock_executor = AsyncMock()
        mock_executor.execute_command = AsyncMock(return_value=MagicMock())

        assert isinstance(mock_executor, AsyncCommandExecutorProtocol)


class TestAsyncHookExecutorProtocol:
    """Tests for AsyncHookExecutorProtocol."""

    @pytest.mark.asyncio
    async def test_async_hook_executor_is_runtime_checkable(self) -> None:
        """Verify AsyncHookExecutorProtocol can be checked with isinstance."""
        mock_executor = AsyncMock()
        mock_executor.execute_strategy = AsyncMock(return_value=MagicMock())

        assert isinstance(mock_executor, AsyncHookExecutorProtocol)


class TestBoundedStatusOperationsProtocol:
    """Tests for BoundedStatusOperationsProtocol."""

    @pytest.mark.asyncio
    async def test_bounded_status_operations_is_runtime_checkable(self) -> None:
        """Verify BoundedStatusOperationsProtocol can be checked with isinstance."""
        mock_ops = AsyncMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_ops, method_name, MagicMock())
        # BoundedStatusOperationsProtocol methods
        mock_ops.execute_bounded_operation = AsyncMock(return_value=None)
        mock_ops.get_operation_status = MagicMock(return_value={})
        mock_ops.reset_circuit_breaker = MagicMock(return_value=True)

        assert isinstance(mock_ops, BoundedStatusOperationsProtocol)


# ============================================================================
# Reflection and Agent Protocols Tests
# ============================================================================


class TestReflectionLoopProtocol:
    """Tests for ReflectionLoopProtocol."""

    @pytest.mark.asyncio
    async def test_reflection_loop_is_runtime_checkable(self) -> None:
        """Verify ReflectionLoopProtocol can be checked with isinstance."""
        mock_loop = AsyncMock()
        mock_loop.start = AsyncMock(return_value=None)
        mock_loop.stop = AsyncMock(return_value=None)
        mock_loop.trigger_reflection = AsyncMock(return_value={})
        mock_loop.get_metrics = MagicMock(return_value={})
        mock_loop.is_running = MagicMock(return_value=False)

        assert isinstance(mock_loop, ReflectionLoopProtocol)


class TestAgentTrackerProtocol:
    """Tests for AgentTrackerProtocol."""

    def test_agent_tracker_is_runtime_checkable(self) -> None:
        """Verify AgentTrackerProtocol can be checked with isinstance."""
        mock_tracker = MagicMock()
        mock_tracker.register_agents = MagicMock(return_value=None)
        mock_tracker.track_agent_processing = MagicMock(return_value=None)
        mock_tracker.track_agent_complete = MagicMock(return_value=None)
        mock_tracker.set_coordinator_status = MagicMock(return_value=None)
        mock_tracker.reset = MagicMock(return_value=None)

        assert isinstance(mock_tracker, AgentTrackerProtocol)


class TestAgentCoordinatorProtocol:
    """Tests for AgentCoordinatorProtocol."""

    @pytest.mark.asyncio
    async def test_agent_coordinator_is_runtime_checkable(self) -> None:
        """Verify AgentCoordinatorProtocol can be checked with isinstance."""
        mock_coordinator = AsyncMock()
        mock_coordinator.handle_issues = AsyncMock(return_value=MagicMock())
        mock_coordinator.initialize_agents = MagicMock(return_value=None)

        assert isinstance(mock_coordinator, AgentCoordinatorProtocol)


# ============================================================================
# Caching and Performance Protocol Tests
# ============================================================================


class TestPerformanceCacheProtocol:
    """Tests for PerformanceCacheProtocol."""

    def test_performance_cache_is_runtime_checkable(self) -> None:
        """Verify PerformanceCacheProtocol can be checked with isinstance."""
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value=None)
        mock_cache.set = MagicMock(return_value=None)

        assert isinstance(mock_cache, PerformanceCacheProtocol)


class TestSmartFileFilterProtocol:
    """Tests for SmartFileFilterProtocol."""

    def test_smart_file_filter_is_runtime_checkable(self) -> None:
        """Verify SmartFileFilterProtocol can be checked with isinstance."""
        mock_filter = MagicMock()
        mock_filter.should_include = MagicMock(return_value=True)
        mock_filter.filter_files = MagicMock(return_value=[])

        assert isinstance(mock_filter, SmartFileFilterProtocol)


class TestSecureSubprocessExecutorProtocol:
    """Tests for SecureSubprocessExecutorProtocol."""

    def test_secure_subprocess_executor_is_runtime_checkable(self) -> None:
        """Verify SecureSubprocessExecutorProtocol can be checked with isinstance."""
        mock_executor = MagicMock()
        mock_executor.allowed_git_patterns = ["git"]
        mock_executor.execute_secure = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=["echo"], returncode=0, stdout="", stderr=""
            )
        )

        assert isinstance(mock_executor, SecureSubprocessExecutorProtocol)


# ============================================================================
# Remaining Protocols Tests
# ============================================================================


class TestPublishManager:
    """Tests for PublishManager protocol."""

    def test_publish_manager_is_runtime_checkable(self) -> None:
        """Verify PublishManager can be checked with isinstance."""
        mock_manager = MagicMock()
        mock_manager.bump_version = MagicMock(return_value="1.0.0")
        mock_manager.publish_package = MagicMock(return_value=True)
        mock_manager.validate_auth = MagicMock(return_value=True)
        mock_manager.create_git_tag = MagicMock(return_value=True)
        mock_manager.create_git_tag_local = MagicMock(return_value=True)
        mock_manager.cleanup_old_releases = MagicMock(return_value=None)

        assert isinstance(mock_manager, PublishManager)


class TestHookLockManagerProtocol:
    """Tests for HookLockManagerProtocol."""

    def test_hook_lock_manager_is_runtime_checkable(self) -> None:
        """Verify HookLockManagerProtocol can be checked with isinstance."""
        mock_manager = MagicMock()
        mock_manager.requires_lock = MagicMock(return_value=True)
        mock_manager.acquire_hook_lock = MagicMock()
        mock_manager.get_lock_stats = MagicMock(return_value={})
        mock_manager.add_hook_to_lock_list = MagicMock(return_value=None)
        mock_manager.remove_hook_from_lock_list = MagicMock(return_value=None)
        mock_manager.is_hook_currently_locked = MagicMock(return_value=False)
        mock_manager.enable_global_lock = MagicMock(return_value=None)
        mock_manager.is_global_lock_enabled = MagicMock(return_value=False)
        mock_manager.get_global_lock_path = MagicMock(return_value=Path("test"))
        mock_manager.cleanup_stale_locks = MagicMock(return_value=0)
        mock_manager.get_global_lock_stats = MagicMock(return_value={})

        assert isinstance(mock_manager, HookLockManagerProtocol)


class TestDebuggerProtocol:
    """Tests for DebuggerProtocol."""

    def test_debugger_protocol_is_runtime_checkable(self) -> None:
        """Verify DebuggerProtocol can be checked with isinstance."""
        mock_debugger = MagicMock()
        mock_debugger.enabled = True
        mock_debugger.debug_operation = MagicMock()
        mock_debugger.log_agent_activity = MagicMock(return_value=None)
        mock_debugger.log_mcp_operation = MagicMock(return_value=None)

        assert isinstance(mock_debugger, DebuggerProtocol)


class TestMemoryOptimizerProtocol:
    """Tests for MemoryOptimizerProtocol."""

    def test_memory_optimizer_is_runtime_checkable(self) -> None:
        """Verify MemoryOptimizerProtocol can be checked with isinstance."""
        mock_optimizer = MagicMock()
        mock_optimizer.optimize_memory = MagicMock(return_value=None)
        mock_optimizer.register_lazy_object = MagicMock(return_value=None)
        mock_optimizer.get_stats = MagicMock(return_value={})

        assert isinstance(mock_optimizer, MemoryOptimizerProtocol)


class TestChangelogGeneratorProtocol:
    """Tests for ChangelogGeneratorProtocol."""

    def test_changelog_generator_is_runtime_checkable(self) -> None:
        """Verify ChangelogGeneratorProtocol can be checked with isinstance."""
        mock_gen = MagicMock()
        mock_gen.generate_changelog_from_commits = MagicMock(return_value=True)
        mock_gen.update_changelog = MagicMock(return_value=None)

        assert isinstance(mock_gen, ChangelogGeneratorProtocol)


class TestRegexPatternsProtocol:
    """Tests for RegexPatternsProtocol."""

    def test_regex_patterns_is_runtime_checkable(self) -> None:
        """Verify RegexPatternsProtocol can be checked with isinstance."""
        mock_patterns = MagicMock()
        mock_patterns.update_pyproject_version = MagicMock(return_value="1.0.0")

        assert isinstance(mock_patterns, RegexPatternsProtocol)


class TestVersionAnalyzerProtocol:
    """Tests for VersionAnalyzerProtocol."""

    @pytest.mark.asyncio
    async def test_version_analyzer_is_runtime_checkable(self) -> None:
        """Verify VersionAnalyzerProtocol can be checked with isinstance."""
        mock_analyzer = AsyncMock()
        mock_analyzer.recommend_version_bump = AsyncMock(return_value=None)
        mock_analyzer.display_recommendation = MagicMock(return_value=None)

        assert isinstance(mock_analyzer, VersionAnalyzerProtocol)


class TestCoverageBadgeServiceProtocol:
    """Tests for CoverageBadgeServiceProtocol."""

    def test_coverage_badge_service_is_runtime_checkable(self) -> None:
        """Verify CoverageBadgeServiceProtocol can be checked with isinstance."""
        mock_service = MagicMock()
        mock_service.update_badge = MagicMock(return_value=True)
        mock_service.should_update_badge = MagicMock(return_value=True)
        mock_service.update_readme_coverage_badge = MagicMock(return_value=True)

        assert isinstance(mock_service, CoverageBadgeServiceProtocol)


class TestHookExecutorProtocol:
    """Tests for HookExecutorProtocol."""

    def test_hook_executor_is_runtime_checkable(self) -> None:
        """Verify HookExecutorProtocol can be checked with isinstance."""
        mock_executor = MagicMock()
        mock_executor.execute_strategy = MagicMock(return_value=MagicMock())
        mock_executor.set_progress_callbacks = MagicMock(return_value=None)

        assert isinstance(mock_executor, HookExecutorProtocol)


class TestHookConfigLoaderProtocol:
    """Tests for HookConfigLoaderProtocol."""

    def test_hook_config_loader_is_runtime_checkable(self) -> None:
        """Verify HookConfigLoaderProtocol can be checked with isinstance."""
        mock_loader = MagicMock()
        mock_loader.load_strategy = MagicMock(return_value=MagicMock())

        assert isinstance(mock_loader, HookConfigLoaderProtocol)


class TestQualityBaselineProtocol:
    """Tests for QualityBaselineProtocol."""

    def test_quality_baseline_is_runtime_checkable(self) -> None:
        """Verify QualityBaselineProtocol can be checked with isinstance."""
        mock_baseline = MagicMock()
        mock_baseline.get_baseline = MagicMock(return_value=0.5)
        mock_baseline.update_baseline = MagicMock(return_value=True)

        assert isinstance(mock_baseline, QualityBaselineProtocol)


class TestQualityIntelligenceProtocol:
    """Tests for QualityIntelligenceProtocol."""

    def test_quality_intelligence_is_runtime_checkable(self) -> None:
        """Verify QualityIntelligenceProtocol can be checked with isinstance."""
        mock_intel = MagicMock()
        mock_intel.analyze_trends = MagicMock(return_value={})

        assert isinstance(mock_intel, QualityIntelligenceProtocol)


class TestSecureStatusFormatterProtocol:
    """Tests for SecureStatusFormatterProtocol."""

    def test_secure_status_formatter_is_runtime_checkable(self) -> None:
        """Verify SecureStatusFormatterProtocol can be checked with isinstance."""
        mock_formatter = MagicMock()
        mock_formatter.format = MagicMock(return_value="formatted")

        assert isinstance(mock_formatter, SecureStatusFormatterProtocol)


class TestEnhancedFileSystemServiceProtocol:
    """Tests for EnhancedFileSystemServiceProtocol (extends ServiceProtocol)."""

    @pytest.mark.asyncio
    async def test_enhanced_file_system_service_is_runtime_checkable(self) -> None:
        """Verify EnhancedFileSystemServiceProtocol can be checked with isinstance."""
        mock_fs = AsyncMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_fs, method_name, MagicMock())
        # EnhancedFileSystemServiceProtocol methods
        mock_fs.read_file = MagicMock(return_value="content")
        mock_fs.write_file = MagicMock(return_value=None)
        mock_fs.read_file_async = AsyncMock(return_value="content")
        mock_fs.write_file_async = AsyncMock(return_value=None)
        mock_fs.read_multiple_files = AsyncMock(return_value={})
        mock_fs.write_multiple_files = AsyncMock(return_value=None)
        mock_fs.file_exists = MagicMock(return_value=True)
        mock_fs.create_directory = MagicMock(return_value=None)
        mock_fs.delete_file = MagicMock(return_value=None)
        mock_fs.list_files = MagicMock(return_value=iter([]))
        mock_fs.flush_operations = AsyncMock(return_value=None)
        mock_fs.get_cache_stats = MagicMock(return_value={})
        mock_fs.clear_cache = MagicMock(return_value=None)
        mock_fs.exists = MagicMock(return_value=True)
        mock_fs.mkdir = MagicMock(return_value=None)

        assert isinstance(mock_fs, EnhancedFileSystemServiceProtocol)


class TestDocumentationServiceProtocol:
    """Tests for DocumentationServiceProtocol (extends ServiceProtocol)."""

    def test_documentation_service_is_runtime_checkable(self) -> None:
        """Verify DocumentationServiceProtocol can be checked with isinstance."""
        mock_service = MagicMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_service, method_name, MagicMock())
        # DocumentationServiceProtocol methods
        mock_service.extract_api_documentation = MagicMock(return_value={})
        mock_service.generate_documentation = MagicMock(return_value="docs")
        mock_service.validate_documentation = MagicMock(return_value=[])
        mock_service.update_documentation_index = MagicMock(return_value=True)
        mock_service.get_documentation_coverage = MagicMock(return_value={})

        assert isinstance(mock_service, DocumentationServiceProtocol)


class TestConfigMergeServiceProtocol:
    """Tests for ConfigMergeServiceProtocol (extends ServiceProtocol)."""

    def test_config_merge_service_is_runtime_checkable(self) -> None:
        """Verify ConfigMergeServiceProtocol can be checked with isinstance."""
        mock_service = MagicMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_service, method_name, MagicMock())
        # ConfigMergeServiceProtocol methods
        mock_service.smart_merge_pyproject = MagicMock(return_value={})
        mock_service.smart_merge_pre_commit_config = MagicMock(return_value={})
        mock_service.smart_append_file = MagicMock(return_value="content")
        mock_service.smart_merge_gitignore = MagicMock(return_value="patterns")
        mock_service.write_pyproject_config = MagicMock(return_value=None)
        mock_service.write_pre_commit_config = MagicMock(return_value=None)

        assert isinstance(mock_service, ConfigMergeServiceProtocol)


class TestSafeFileModifierProtocol:
    """Tests for SafeFileModifierProtocol."""

    def test_safe_file_modifier_is_runtime_checkable(self) -> None:
        """Verify SafeFileModifierProtocol can be checked with isinstance."""
        mock_modifier = MagicMock()
        mock_modifier.modify_file = MagicMock(return_value=None)

        assert isinstance(mock_modifier, SafeFileModifierProtocol)


class TestParallelHookExecutorProtocol:
    """Tests for ParallelHookExecutorProtocol."""

    @pytest.mark.asyncio
    async def test_parallel_hook_executor_is_runtime_checkable(self) -> None:
        """Verify ParallelHookExecutorProtocol can be checked with isinstance."""
        mock_executor = AsyncMock()
        mock_executor.execute_hooks_parallel = AsyncMock(return_value=MagicMock())

        assert isinstance(mock_executor, ParallelHookExecutorProtocol)


class TestUnifiedConfigurationServiceProtocol:
    """Tests for UnifiedConfigurationServiceProtocol (extends ServiceProtocol)."""

    def test_unified_configuration_service_is_runtime_checkable(self) -> None:
        """Verify UnifiedConfigurationServiceProtocol can be checked with isinstance."""
        mock_service = MagicMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_service, method_name, MagicMock())
        # UnifiedConfigurationServiceProtocol methods
        mock_service.get_config = MagicMock(return_value=MagicMock())
        mock_service.get_logging_config = MagicMock(return_value={})
        mock_service.get_hook_execution_config = MagicMock(return_value={})
        mock_service.get_testing_config = MagicMock(return_value={})
        mock_service.get_cache_config = staticmethod(MagicMock(return_value={}))
        mock_service.validate_current_config = MagicMock(return_value=True)

        assert isinstance(mock_service, UnifiedConfigurationServiceProtocol)


class TestConfigIntegrityServiceProtocol:
    """Tests for ConfigIntegrityServiceProtocol (extends ServiceProtocol)."""

    def test_config_integrity_service_is_runtime_checkable(self) -> None:
        """Verify ConfigIntegrityServiceProtocol can be checked with isinstance."""
        mock_service = MagicMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_service, method_name, MagicMock())
        # ConfigIntegrityServiceProtocol methods
        mock_service.check_config_integrity = MagicMock(return_value=True)

        assert isinstance(mock_service, ConfigIntegrityServiceProtocol)


class TestInitializationServiceProtocol:
    """Tests for InitializationServiceProtocol (extends ServiceProtocol)."""

    def test_initialization_service_is_runtime_checkable(self) -> None:
        """Verify InitializationServiceProtocol can be checked with isinstance."""
        mock_service = MagicMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_service, method_name, MagicMock())
        # InitializationServiceProtocol methods
        mock_service.initialize_project = MagicMock(return_value=True)
        mock_service.validate_project_structure = MagicMock(return_value=True)
        mock_service.setup_git_hooks = MagicMock(return_value=True)

        assert isinstance(mock_service, InitializationServiceProtocol)


class TestSmartSchedulingServiceProtocol:
    """Tests for SmartSchedulingServiceProtocol (extends ServiceProtocol)."""

    def test_smart_scheduling_service_is_runtime_checkable(self) -> None:
        """Verify SmartSchedulingServiceProtocol can be checked with isinstance."""
        mock_service = MagicMock()
        # ServiceProtocol methods
        for method_name in [
            "initialize",
            "cleanup",
            "health_check",
            "shutdown",
            "metrics",
            "is_healthy",
            "register_resource",
            "cleanup_resource",
            "record_error",
            "increment_requests",
            "get_custom_metric",
            "set_custom_metric",
        ]:
            setattr(mock_service, method_name, MagicMock())
        # SmartSchedulingServiceProtocol methods
        mock_service.should_scheduled_init = MagicMock(return_value=True)
        mock_service.record_init_timestamp = MagicMock(return_value=None)

        assert isinstance(mock_service, SmartSchedulingServiceProtocol)


class TestAgentDelegatorProtocol:
    """Tests for AgentDelegatorProtocol."""

    def test_agent_delegator_is_runtime_checkable(self) -> None:
        """Verify AgentDelegatorProtocol can be checked with isinstance."""
        mock_delegator = MagicMock()
        mock_delegator.delegate_to_type_specialist = AsyncMock(return_value=MagicMock())
        mock_delegator.delegate_to_dead_code_remover = AsyncMock(
            return_value=MagicMock()
        )
        mock_delegator.delegate_to_refurb_transformer = AsyncMock(
            return_value=MagicMock()
        )
        mock_delegator.delegate_to_performance_optimizer = AsyncMock(
            return_value=MagicMock()
        )
        mock_delegator.delegate_to_security_specialist = AsyncMock(
            return_value=MagicMock()
        )
        mock_delegator.delegate_batch = AsyncMock(return_value=[])
        mock_delegator.get_delegation_metrics = MagicMock(return_value={})

        assert isinstance(mock_delegator, AgentDelegatorProtocol)


class TestMCPIntegrationProtocol:
    """Tests for MCPIntegrationProtocol."""

    @pytest.mark.asyncio
    async def test_mcp_integration_is_runtime_checkable(self) -> None:
        """Verify MCPIntegrationProtocol can be checked with isinstance."""
        mock_mcp = AsyncMock()
        mock_mcp.search_regex = AsyncMock(return_value=[])
        mock_mcp.replace_text_in_file = AsyncMock(return_value=True)
        mock_mcp.get_file_problems = AsyncMock(return_value=[])
        mock_mcp.is_available = MagicMock(return_value=True)

        assert isinstance(mock_mcp, MCPIntegrationProtocol)
