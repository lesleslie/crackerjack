import logging
import typing as t
from pathlib import Path

from acb.console import Console

from crackerjack.models.protocols import OptionsProtocol

from .base import PluginRegistry, PluginType, get_plugin_registry
from .hooks import HookPluginBase, HookPluginRegistry, get_hook_plugin_registry
from .loader import PluginDiscovery, PluginLoader


class PluginManager:
    def __init__(
        self,
        console: Console,
        project_path: Path,
        registry: PluginRegistry | None = None,
        hook_registry: HookPluginRegistry | None = None,
    ) -> None:
        self.console = console
        self.project_path = project_path
        self.registry = registry or get_plugin_registry()
        self.hook_registry = hook_registry or get_hook_plugin_registry()

        self.loader = PluginLoader(self.registry)
        self.discovery = PluginDiscovery(self.loader)
        self.logger = logging.getLogger("crackerjack.plugin_manager")

        self._initialized = False

    def initialize(self) -> bool:
        if self._initialized:
            return True

        self.logger.info("Initializing plugin system")

        try:
            results = self.discovery.auto_discover_and_load(self.project_path)

            loaded_count = sum(1 for success in results.values() if success)
            total_count = len(results)

            if total_count > 0:
                self.console.print(
                    f"[green]✅[/ green] Loaded {loaded_count} / {total_count} plugins",
                )

            activation_results = self.registry.activate_all()
            activated_count = sum(
                1 for success in activation_results.values() if success
            )

            if activated_count > 0:
                self.console.print(
                    f"[green]✅[/ green] Activated {activated_count} plugins",
                )

            hook_plugins = self.registry.get_enabled(PluginType.HOOK)
            for plugin in hook_plugins:
                if isinstance(plugin, HookPluginBase):
                    if hasattr(plugin, "initialize"):
                        plugin.initialize(self.console, self.project_path)
                    self.hook_registry.register_hook_plugin(plugin)

            self._initialized = True
            return True

        except Exception as e:
            self.logger.exception(f"Failed to initialize plugin system: {e}")
            self.console.print(
                f"[red]❌[/ red] Plugin system initialization failed: {e}",
            )
            return False

    def shutdown(self) -> None:
        if not self._initialized:
            return

        self.logger.info("Shutting down plugin system")

        try:
            results = self.registry.deactivate_all()
            deactivated_count = sum(1 for success in results.values() if success)

            if deactivated_count > 0:
                self.console.print(
                    f"[yellow]⏹️[/ yellow] Deactivated {deactivated_count} plugins",
                )

            self._initialized = False

        except Exception as e:
            self.logger.exception(f"Error during plugin system shutdown: {e}")

    def list_plugins(self, plugin_type: PluginType | None = None) -> dict[str, t.Any]:
        if plugin_type:
            plugins = self.registry.get_by_type(plugin_type)
        else:
            plugins = list[t.Any](self.registry.list_all().values())

        plugin_info = []
        for plugin in plugins:
            info = plugin.get_info()
            info["active"] = plugin.enabled
            plugin_info.append(info)

        return {
            "plugins": plugin_info,
            "total": len(plugin_info),
            "enabled": len([p for p in plugins if p.enabled]),
        }

    def get_plugin_stats(self) -> dict[str, t.Any]:
        stats = self.registry.get_stats()

        hook_plugins = self.registry.get_enabled(PluginType.HOOK)
        custom_hooks = self.hook_registry.get_all_custom_hooks()

        stats["hook_plugins"] = {
            "active_plugins": len(hook_plugins),
            "total_custom_hooks": len(custom_hooks),
            "hook_names": list[t.Any](custom_hooks.keys()),
        }

        return stats

    def enable_plugin(self, plugin_name: str) -> bool:
        plugin = self.registry.get(plugin_name)
        if not plugin:
            self.console.print(f"[red]❌[/ red] Plugin not found: {plugin_name}")
            return False

        if plugin.enabled:
            self.console.print(
                f"[yellow]⚠️[/ yellow] Plugin already enabled: {plugin_name}",
            )
            return True

        try:
            plugin.enable()
            success = plugin.activate()

            if success:
                self.console.print(f"[green]✅[/ green] Enabled plugin: {plugin_name}")

                if plugin.plugin_type == PluginType.HOOK and isinstance(
                    plugin, HookPluginBase
                ):
                    self.hook_registry.register_hook_plugin(plugin)

                return True
            plugin.disable()
            self.console.print(
                f"[red]❌[/ red] Failed to activate plugin: {plugin_name}",
            )
            return False

        except Exception as e:
            self.console.print(
                f"[red]❌[/ red] Error enabling plugin {plugin_name}: {e}",
            )
            return False

    def disable_plugin(self, plugin_name: str) -> bool:
        plugin = self.registry.get(plugin_name)
        if not plugin:
            self.console.print(f"[red]❌[/ red] Plugin not found: {plugin_name}")
            return False

        if not plugin.enabled:
            self.console.print(
                f"[yellow]⚠️[/ yellow] Plugin already disabled: {plugin_name}",
            )
            return True

        try:
            success = plugin.deactivate()
            plugin.disable()

            if plugin.plugin_type == PluginType.HOOK:
                self.hook_registry.unregister_hook_plugin(plugin_name)

            if success:
                self.console.print(
                    f"[yellow]⏹️[/ yellow] Disabled plugin: {plugin_name}"
                )
            else:
                self.console.print(
                    f"[yellow]⚠️[/ yellow] Plugin disabled with warnings: {plugin_name}",
                )

            return True

        except Exception as e:
            self.console.print(
                f"[red]❌[/ red] Error disabling plugin {plugin_name}: {e}",
            )
            return False

    def reload_plugin(self, plugin_name: str) -> bool:
        if not self.disable_plugin(plugin_name):
            return False

        return self.enable_plugin(plugin_name)

    def configure_plugin(self, plugin_name: str, config: dict[str, t.Any]) -> bool:
        plugin = self.registry.get(plugin_name)
        if not plugin:
            self.console.print(f"[red]❌[/ red] Plugin not found: {plugin_name}")
            return False

        try:
            plugin.configure(config)
            self.console.print(f"[green]✅[/ green] Configured plugin: {plugin_name}")
            return True
        except Exception as e:
            self.console.print(
                f"[red]❌[/ red] Error configuring plugin {plugin_name}: {e}",
            )
            return False

    def install_plugin_from_file(self, plugin_file: Path) -> bool:
        try:
            success = self.loader.load_and_register(plugin_file)

            if success:
                self.console.print(
                    f"[green]✅[/ green] Installed plugin from: {plugin_file}",
                )

                if self._initialized:
                    plugins = self.registry.list_all()
                    if plugins:
                        latest_plugin_name = max(
                            plugins.keys(),
                            key=lambda k: id(plugins[k]),
                        )
                        self.enable_plugin(latest_plugin_name)
            else:
                self.console.print(
                    f"[red]❌[/ red] Failed to install plugin from: {plugin_file}",
                )

            return success

        except Exception as e:
            self.console.print(
                f"[red]❌[/ red] Error installing plugin {plugin_file}: {e}",
            )
            return False

    def get_available_custom_hooks(self) -> list[str]:
        custom_hooks = self.hook_registry.get_all_custom_hooks()
        return list[t.Any](custom_hooks.keys())

    def execute_custom_hook(
        self,
        hook_name: str,
        files: list[Path],
        options: OptionsProtocol,
    ) -> t.Any:
        return self.hook_registry.execute_custom_hook(hook_name, files, options)
