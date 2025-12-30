import inspect
import subprocess
import tempfile
import typing as t
from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console

from crackerjack.core.container import DependencyContainer, create_container
from crackerjack.models.protocols import (
    CommandRunner,
    ConsoleInterface,
    FileSystemInterface,
    GitInterface,
    HookManager,
    OptionsProtocol,
    PublishManager,
    TestManagerProtocol,
)


class TestProtocolCompliance:
    def test_filesystem_interface_compliance(self) -> None:
        from crackerjack.services.filesystem import FileSystemService

        service = FileSystemService()

        assert isinstance(service, FileSystemInterface)

        assert hasattr(service, "read_file")
        assert hasattr(service, "write_file")
        assert hasattr(service, "exists")
        assert hasattr(service, "mkdir")

        read_sig = inspect.signature(service.read_file)
        assert len(read_sig.parameters) == 1
        assert read_sig.return_annotation is str

        write_sig = inspect.signature(service.write_file)
        assert len(write_sig.parameters) == 2
        assert write_sig.return_annotation in (None, type(None))

        exists_sig = inspect.signature(service.exists)
        assert len(exists_sig.parameters) == 1
        assert exists_sig.return_annotation is bool

        mkdir_sig = inspect.signature(service.mkdir)
        assert len(mkdir_sig.parameters) >= 1

    def test_git_interface_compliance(self) -> None:
        from crackerjack.services.git import GitService

        console = Console()
        pkg_path = Path("/ tmp / test")
        service = GitService(console=console, pkg_path=pkg_path)

        assert isinstance(service, GitInterface)

        required_methods = [
            "is_git_repo",
            "get_changed_files",
            "commit",
            "push",
            "add_files",
            "get_commit_message_suggestions",
        ]
        for method in required_methods:
            assert hasattr(service, method), f"Missing method: {method}"

        is_git_repo_sig = inspect.signature(service.is_git_repo)
        assert len(is_git_repo_sig.parameters) == 0
        assert is_git_repo_sig.return_annotation is bool

        get_changed_files_sig = inspect.signature(service.get_changed_files)
        assert len(get_changed_files_sig.parameters) == 0
        assert get_changed_files_sig.return_annotation in (list[str], list)

        commit_sig = inspect.signature(service.commit)
        assert len(commit_sig.parameters) == 1
        assert commit_sig.return_annotation is bool

    def test_hook_manager_compliance(self) -> None:
        from crackerjack.managers.hook_manager import HookManagerImpl

        console = Console()
        pkg_path = Path("/ tmp / test")
        manager = HookManagerImpl(console=console, pkg_path=pkg_path)

        assert isinstance(manager, HookManager)

        required_methods = [
            "run_fast_hooks",
            "run_comprehensive_hooks",
            "install_hooks",
            "set_config_path",
            "get_hook_summary",
        ]
        for method in required_methods:
            assert hasattr(manager, method), f"Missing method: {method}"

        run_fast_sig = inspect.signature(manager.run_fast_hooks)
        assert len(run_fast_sig.parameters) == 0

        run_comp_sig = inspect.signature(manager.run_comprehensive_hooks)
        assert len(run_comp_sig.parameters) == 0

        set_config_sig = inspect.signature(manager.set_config_path)
        assert len(set_config_sig.parameters) == 1

    def test_test_manager_protocol_compliance(self) -> None:
        from crackerjack.managers.test_manager import TestManagementImpl

        console = Console()
        pkg_path = Path("/ tmp / test")
        manager = TestManagementImpl(console=console, pkg_path=pkg_path)

        assert isinstance(manager, TestManagerProtocol)

        required_methods = [
            "run_tests",
            "get_coverage",
            "validate_test_environment",
            "get_test_failures",
        ]
        for method in required_methods:
            assert hasattr(manager, method), f"Missing method: {method}"

        run_tests_sig = inspect.signature(manager.run_tests)
        assert len(run_tests_sig.parameters) == 1
        assert run_tests_sig.return_annotation is bool

        get_coverage_sig = inspect.signature(manager.get_coverage)
        assert len(get_coverage_sig.parameters) == 0

        validate_env_sig = inspect.signature(manager.validate_test_environment)
        assert len(validate_env_sig.parameters) == 0
        assert validate_env_sig.return_annotation is bool

    def test_publish_manager_compliance(self) -> None:
        from crackerjack.managers.publish_manager import PublishManagerImpl

        console = Console()
        pkg_path = Path("/ tmp / test")
        manager = PublishManagerImpl(console=console, pkg_path=pkg_path, dry_run=True)

        assert isinstance(manager, PublishManager)

        required_methods = [
            "bump_version",
            "publish_package",
            "validate_auth",
            "create_git_tag",
            "cleanup_old_releases",
        ]
        for method in required_methods:
            assert hasattr(manager, method), f"Missing method: {method}"

        bump_version_sig = inspect.signature(manager.bump_version)
        assert len(bump_version_sig.parameters) == 1
        assert bump_version_sig.return_annotation is str

        publish_sig = inspect.signature(manager.publish_package)
        assert len(publish_sig.parameters) == 0
        assert publish_sig.return_annotation is bool

        validate_auth_sig = inspect.signature(manager.validate_auth)
        assert len(validate_auth_sig.parameters) == 0
        assert validate_auth_sig.return_annotation is bool


class TestDependencyContainer:
    def test_container_creation(self) -> None:
        container = DependencyContainer()
        assert container._services == {}
        assert container._singletons == {}

    def test_register_singleton(self) -> None:
        container = DependencyContainer()
        mock_service = Mock()

        container.register_singleton(FileSystemInterface, mock_service)

        assert "FileSystemInterface" in container._singletons
        assert container._singletons["FileSystemInterface"] is mock_service

    def test_register_transient(self) -> None:
        container = DependencyContainer()

        def factory():
            return Mock()

        container.register_transient(GitInterface, factory)

        assert "GitInterface" in container._services
        assert callable(container._services["GitInterface"])

    def test_get_singleton(self) -> None:
        container = DependencyContainer()
        mock_service = Mock()

        container.register_singleton(FileSystemInterface, mock_service)
        retrieved = container.get(FileSystemInterface)

        assert retrieved is mock_service

        assert container.get(FileSystemInterface) is mock_service

    def test_get_transient(self) -> None:
        container = DependencyContainer()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return Mock(id=call_count)

        container.register_transient(GitInterface, factory)

        first = container.get(GitInterface)
        second = container.get(GitInterface)

        assert first is not second
        assert first.id == 1
        assert second.id == 2

    def test_get_unregistered_service_raises_error(self) -> None:
        container = DependencyContainer()

        with pytest.raises(
            ValueError,
            match="Service TestManagerProtocol not registered",
        ):
            container.get(TestManagerProtocol)

    def test_create_default_container(self) -> None:
        container = create_container()

        assert "FileSystemInterface" in container._singletons
        assert "GitInterface" in container._services
        assert "HookManager" in container._services
        assert "TestManagerProtocol" in container._services
        assert "PublishManager" in container._services

    def test_container_service_resolution(self) -> None:
        container = create_container()

        fs1 = container.get(FileSystemInterface)
        fs2 = container.get(FileSystemInterface)
        assert fs1 is fs2
        assert isinstance(fs1, FileSystemInterface)

        git1 = container.get(GitInterface)
        git2 = container.get(GitInterface)
        assert git1 is not git2
        assert isinstance(git1, GitInterface)
        assert isinstance(git2, GitInterface)

        hook1 = container.get(HookManager)
        hook2 = container.get(HookManager)
        assert hook1 is not hook2
        assert isinstance(hook1, HookManager)

        test1 = container.get(TestManagerProtocol)
        test2 = container.get(TestManagerProtocol)
        assert test1 is not test2
        assert isinstance(test1, TestManagerProtocol)

        pub1 = container.get(PublishManager)
        pub2 = container.get(PublishManager)
        assert pub1 is not pub2
        assert isinstance(pub1, PublishManager)


class TestProtocolSubstitutability:
    def test_filesystem_substitutability(self) -> None:
        from crackerjack.services.filesystem import FileSystemService

        class MockFileSystem:
            def read_file(self, path: str | t.Any) -> str:
                return "mock content"

            def write_file(self, path: str | t.Any, content: str) -> None:
                pass

            def exists(self, path: str | t.Any) -> bool:
                return True

            def mkdir(self, path: str | t.Any, parents: bool = False) -> None:
                pass

        real_service = FileSystemService()
        mock_service = MockFileSystem()

        assert isinstance(real_service, FileSystemInterface)
        assert isinstance(mock_service, FileSystemInterface)

        for service in [real_service, mock_service]:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                f.write("test")
                temp_path = f.name

            try:
                exists = service.exists(temp_path)
                assert isinstance(exists, bool)

                if isinstance(
                    service,
                    FileSystemService,
                ):
                    content = service.read_file(temp_path)
                    assert isinstance(content, str)
            finally:
                Path(temp_path).unlink(missing_ok=True)

    def test_hook_manager_substitutability(self) -> None:
        from crackerjack.managers.hook_manager import HookManagerImpl

        class MockHookManager:
            def run_fast_hooks(self) -> list[t.Any]:
                return []

            def run_comprehensive_hooks(self) -> list[t.Any]:
                return []

            def install_hooks(self) -> bool:
                return True

            def set_config_path(self, path: str | t.Any) -> None:
                pass

            def get_hook_summary(self, results: t.Any) -> t.Any:
                return {"summary": "mock"}

        console = Console()
        pkg_path = Path("/ tmp / test")
        real_manager = HookManagerImpl(console=console, pkg_path=pkg_path)
        mock_manager = MockHookManager()

        assert isinstance(real_manager, HookManager)
        assert isinstance(mock_manager, HookManager)

        for manager in [real_manager, mock_manager]:
            assert callable(manager.run_fast_hooks)
            assert callable(manager.run_comprehensive_hooks)
            assert callable(manager.install_hooks)
            assert callable(manager.set_config_path)
            assert callable(manager.get_hook_summary)


class TestProtocolMethodSignatures:
    def test_options_protocol_attributes(self) -> None:
        try:
            from crackerjack.cli.options import Options

            options = Options()
        except ImportError:

            class MockOptions:
                def __init__(self) -> None:
                    self.commit = False
                    self.interactive = False
                    self.no_config_updates = False
                    self.verbose = False
                    self.clean = False
                    self.test = False
                    self.benchmark = False
                    self.benchmark_regression = False
                    self.benchmark_regression_threshold = 0.1
                    self.test_workers = 0
                    self.test_timeout = 0
                    self.publish = None
                    self.bump = None
                    self.all = None
                    self.ai_agent = False
                    self.start_mcp_server = False
                    self.create_pr = False
                    self.skip_hooks = False
                    self.async_mode = False
                    self.experimental_hooks = False
                    self.enable_pyrefly = False
                    self.enable_ty = False
                    self.cleanup = None
                    self.no_git_tags = False
                    self.skip_version_check = False
                    self.cleanup_pypi = False
                    self.keep_releases = 10
                    self.track_progress = False
                    self.fast = False
                    self.comp = False

            options = MockOptions()

        assert isinstance(options, OptionsProtocol)

        required_attrs = [
            "commit",
            "interactive",
            "no_config_updates",
            "verbose",
            "clean",
            "test",
            "benchmark",
            "benchmark_regression",
            "benchmark_regression_threshold",
            "test_workers",
            "test_timeout",
            "publish",
            "bump",
            "all",
            "ai_agent",
            "start_mcp_server",
            "create_pr",
            "skip_hooks",
            "async_mode",
            "experimental_hooks",
            "enable_pyrefly",
            "enable_ty",
            "cleanup",
            "no_git_tags",
            "skip_version_check",
            "cleanup_pypi",
            "keep_releases",
            "track_progress",
            "fast",
            "comp",
        ]

        for attr in required_attrs:
            assert hasattr(options, attr), f"Missing attribute: {attr}"

    def test_console_interface_methods(self) -> None:
        class MockConsole:
            def print(self, *args: t.Any, **kwargs: t.Any) -> None:
                pass

            def input(self, prompt: str = "") -> str:
                return "mock input"

        console = MockConsole()

        assert isinstance(console, ConsoleInterface)

        print_method = console.print
        assert callable(print_method)

        input_method = console.input
        assert callable(input_method)

    def test_command_runner_protocol(self) -> None:
        class MockCommandRunner:
            def execute_command(
                self,
                cmd: list[str],
                **kwargs: t.Any,
            ) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(cmd, 0, "output", "")

        runner = MockCommandRunner()
        assert isinstance(runner, CommandRunner)

        sig = inspect.signature(runner.execute_command)
        params = list(sig.parameters.keys())
        assert "cmd" in params
        assert "kwargs" in params
        assert sig.return_annotation == subprocess.CompletedProcess[str]


class TestMockProtocolImplementations:
    def test_filesystem_error_handling(self) -> None:
        class FailingFileSystem:
            def read_file(self, path: str | t.Any) -> str:
                msg = "File not found"
                raise FileNotFoundError(msg)

            def write_file(self, path: str | t.Any, content: str) -> None:
                msg = "Permission denied"
                raise PermissionError(msg)

            def exists(self, path: str | t.Any) -> bool:
                return False

            def mkdir(self, path: str | t.Any, parents: bool = False) -> None:
                msg = "Disk full"
                raise OSError(msg)

        failing_fs = FailingFileSystem()
        assert isinstance(failing_fs, FileSystemInterface)

        with pytest.raises(FileNotFoundError):
            failing_fs.read_file("/ nonexistent")

        with pytest.raises(PermissionError):
            failing_fs.write_file("/ readonly", "content")

        assert failing_fs.exists("/ anything") is False

        with pytest.raises(OSError):
            failing_fs.mkdir("/ newdir")

    def test_git_interface_edge_cases(self) -> None:
        class EdgeCaseGit:
            def is_git_repo(self) -> bool:
                return False

            def get_changed_files(self) -> list[str]:
                return []

            def commit(self, message: str) -> bool:
                return False

            def push(self) -> bool:
                return False

            def add_files(self, files: list[str]) -> bool:
                return len(files) == 0

            def add_all_files(self) -> bool:
                return False

            def get_commit_message_suggestions(
                self,
                changed_files: list[str],
            ) -> list[str]:
                return ["No suggestions available"]

            def get_unpushed_commit_count(self) -> int:
                return 0

        edge_git = EdgeCaseGit()
        assert isinstance(edge_git, GitInterface)

        assert edge_git.is_git_repo() is False
        assert edge_git.get_changed_files() == []
        assert edge_git.commit("test") is False
        assert edge_git.push() is False
        assert edge_git.add_files([]) is True
        assert edge_git.add_files(["file.py"]) is False
        suggestions = edge_git.get_commit_message_suggestions([])
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

    def test_container_with_mock_services(self) -> None:
        container = DependencyContainer()

        mock_fs = Mock(spec=FileSystemInterface)
        mock_git = Mock(spec=GitInterface)

        container.register_singleton(FileSystemInterface, mock_fs)
        container.register_singleton(GitInterface, mock_git)

        retrieved_fs = container.get(FileSystemInterface)
        retrieved_git = container.get(GitInterface)

        assert retrieved_fs is mock_fs
        assert retrieved_git is mock_git

        assert hasattr(retrieved_fs, "read_file")
        assert hasattr(retrieved_git, "is_git_repo")
