import abc
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from crackerjack.config.hooks import HookDefinition, HookStage
from crackerjack.models.protocols import OptionsProtocol
from crackerjack.models.task import HookResult

from .base import PluginBase, PluginMetadata, PluginType


@dataclass
class CustomHookDefinition:
    name: str
    description: str
    command: list[str] | None = None
    file_patterns: list[str] = field(default_factory=list)
    timeout: int = 60
    stage: HookStage = HookStage.COMPREHENSIVE
    requires_files: bool = True
    parallel_safe: bool = True

    def to_hook_definition(self) -> HookDefinition:
        cmd = self.command or []
        return HookDefinition(
            name=self.name,
            command=cmd,
            timeout=self.timeout,
            stage=self.stage,
            manual_stage=self.stage == HookStage.COMPREHENSIVE,
        )


class HookPluginBase(PluginBase, abc.ABC):
    def __init__(self, metadata: PluginMetadata) -> None:
        super().__init__(metadata)
        assert metadata.plugin_type == PluginType.HOOK
        self.console: Console | None = None
        self.pkg_path: Path | None = None

    def initialize(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path

    @abc.abstractmethod
    def get_hook_definitions(self) -> list[CustomHookDefinition]:
        pass

    @abc.abstractmethod
    def execute_hook(
        self,
        hook_name: str,
        files: list[Path],
        options: OptionsProtocol,
    ) -> HookResult:
        pass

    def should_run_hook(self, hook_name: str, files: list[Path]) -> bool:
        hook_def = self._get_hook_definition(hook_name)
        if not hook_def or not hook_def.requires_files:
            return True

        if not hook_def.file_patterns:
            return bool(files)

        for file_path in files:
            for pattern in hook_def.file_patterns:
                if file_path.match(pattern):
                    return True

        return False

    def _get_hook_definition(self, hook_name: str) -> CustomHookDefinition | None:
        for hook_def in self.get_hook_definitions():
            if hook_def.name == hook_name:
                return hook_def
        return None


class CustomHookPlugin(HookPluginBase):
    def __init__(
        self,
        metadata: PluginMetadata,
        hook_definitions: list[CustomHookDefinition],
    ) -> None:
        super().__init__(metadata)
        self._hook_definitions = hook_definitions

    def get_hook_definitions(self) -> list[CustomHookDefinition]:
        return self._hook_definitions.copy()

    def execute_hook(
        self,
        hook_name: str,
        files: list[Path],
        options: OptionsProtocol,
    ) -> HookResult:
        hook_def = self._get_hook_definition(hook_name)
        if not hook_def:
            return HookResult(
                id=hook_name,
                name=hook_name,
                status="error",
                duration=0.0,
                issues_found=[f"Hook definition not found: {hook_name}"],
            )

        if not hook_def.command:
            return HookResult(
                id=hook_name,
                name=hook_name,
                status="error",
                duration=0.0,
                issues_found=[f"No command defined for hook: {hook_name}"],
            )

        return self._execute_command_hook(hook_def, files)

    def _execute_command_hook(
        self,
        hook_def: CustomHookDefinition,
        files: list[Path],
    ) -> HookResult:
        import time

        start_time = time.time()

        try:
            if hook_def.command is None:
                return HookResult(
                    id=f"hook_{hook_def.name}",
                    name=hook_def.name,
                    status="failed",
                    issues_found=["Hook command is None"],
                    duration=0.0,
                )
            cmd = hook_def.command.copy()
            if hook_def.requires_files and files:
                cmd.extend(str(f) for f in files)

            result = subprocess.run(
                cmd,
                check=False,
                cwd=self.pkg_path,
                capture_output=True,
                text=True,
                timeout=hook_def.timeout,
            )

            duration = time.time() - start_time
            status = "passed" if result.returncode == 0 else "failed"

            issues = [result.stderr] if result.returncode != 0 and result.stderr else []
            return HookResult(
                id=hook_def.name,
                name=hook_def.name,
                status=status,
                duration=duration,
                issues_found=issues,
            )

        except subprocess.TimeoutExpired:
            return HookResult(
                id=hook_def.name,
                name=hook_def.name,
                status="timeout",
                duration=time.time() - start_time,
                issues_found=[f"Hook timed out after {hook_def.timeout}s"],
            )
        except Exception as e:
            return HookResult(
                id=hook_def.name,
                name=hook_def.name,
                status="error",
                duration=time.time() - start_time,
                issues_found=[f"Execution error: {e}"],
            )

    def activate(self) -> bool:
        return True

    def deactivate(self) -> bool:
        return True


class HookPluginRegistry:
    def __init__(self) -> None:
        self._hook_plugins: dict[str, HookPluginBase] = {}

    def register_hook_plugin(self, plugin: HookPluginBase) -> bool:
        if plugin.name in self._hook_plugins:
            return False

        self._hook_plugins[plugin.name] = plugin
        return True

    def unregister_hook_plugin(self, plugin_name: str) -> bool:
        return self._hook_plugins.pop(plugin_name, None) is not None

    def get_all_custom_hooks(self) -> dict[str, CustomHookDefinition]:
        hooks = {}

        for plugin in self._hook_plugins.values():
            if not plugin.enabled:
                continue

            for hook_def in plugin.get_hook_definitions():
                if hook_def.name not in hooks:
                    hooks[hook_def.name] = hook_def

        return hooks

    def execute_custom_hook(
        self,
        hook_name: str,
        files: list[Path],
        options: OptionsProtocol,
    ) -> HookResult | None:
        for plugin in self._hook_plugins.values():
            if not plugin.enabled:
                continue

            hook_defs = plugin.get_hook_definitions()
            if any(h.name == hook_name for h in hook_defs):
                return plugin.execute_hook(hook_name, files, options)

        return None

    def get_hooks_for_files(self, files: list[Path]) -> list[str]:
        applicable_hooks = []

        for plugin in self._hook_plugins.values():
            if not plugin.enabled:
                continue

            for hook_def in plugin.get_hook_definitions():
                if plugin.should_run_hook(hook_def.name, files):
                    applicable_hooks.append(hook_def.name)

        return applicable_hooks

    def initialize_all_plugins(self, console: Console, pkg_path: Path) -> None:
        for plugin in self._hook_plugins.values():
            plugin.initialize(console, pkg_path)


_hook_registry = HookPluginRegistry()


def get_hook_plugin_registry() -> HookPluginRegistry:
    return _hook_registry
