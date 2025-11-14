import typing as t
from pathlib import Path

from acb import console as acb_console
from acb.console import Console

from crackerjack.models.protocols import (
    FileSystemInterface,
    GitInterface,
    HookManager,
    PublishManager,
    TestManagerProtocol,
)


class DependencyContainer:
    def __init__(self) -> None:
        self._services: dict[str, t.Any] = {}
        self._singletons: dict[str, t.Any] = {}

    def register_singleton(self, interface: type, implementation: t.Any) -> None:
        self._singletons[interface.__name__] = implementation

    def register_transient(
        self,
        interface: type,
        factory: t.Callable[[], t.Any],
    ) -> None:
        self._services[interface.__name__] = factory

    def get(self, interface: type) -> t.Any:
        name = interface.__name__
        if name in self._singletons:
            return self._singletons[name]
        if name in self._services:
            return self._services[name]()
        msg = f"Service {name} not registered"
        raise ValueError(msg)

    def create_default_container(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> "DependencyContainer":
        if console is None:
            console = acb_console

        if pkg_path is None:
            pkg_path = Path.cwd()

        from crackerjack.services.filesystem import FileSystemService

        self.register_singleton(FileSystemInterface, FileSystemService())

        from crackerjack.services.git import GitService

        self.register_transient(
            GitInterface,
            lambda: GitService(pkg_path=pkg_path),
        )

        from crackerjack.managers.hook_manager import HookManagerImpl

        self.register_transient(
            HookManager,
            lambda: HookManagerImpl(
                console=console, pkg_path=pkg_path, verbose=verbose, quiet=True
            ),
        )

        from crackerjack.managers.test_manager import TestManagementImpl

        self.register_transient(
            TestManagerProtocol,
            lambda: TestManagementImpl(console=console, pkg_path=pkg_path),
        )

        from crackerjack.managers.publish_manager import PublishManagerImpl

        # Use factory without parameters to trigger @depends.inject decorator
        # The decorator will inject all dependencies from the DI container
        self.register_transient(
            PublishManager,
            PublishManagerImpl,
        )

        return self


def create_container(
    console: Console | None = None,  # defaults to acb_console if None
    pkg_path: Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> DependencyContainer:
    if console is None:
        console = acb_console
    return DependencyContainer().create_default_container(
        console=console,
        pkg_path=pkg_path,
        dry_run=dry_run,
        verbose=verbose,
    )
