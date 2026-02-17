import abc
import typing as t
from dataclasses import dataclass, field
from enum import Enum


class PluginType(Enum):
    HOOK = "hook"
    WORKFLOW = "workflow"
    INTEGRATION = "integration"
    FORMATTER = "formatter"
    ANALYZER = "analyzer"
    PUBLISHER = "publisher"


@dataclass
class PluginMetadata:
    name: str
    version: str
    plugin_type: PluginType
    description: str
    author: str = ""
    license: str = ""
    requires_python: str = "> = 3.11"
    dependencies: list[str] = field(default_factory=list)
    entry_point: str = ""
    config_schema: dict[str, t.Any] = field(default_factory=dict[str, t.Any])

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "name": self.name,
            "version": self.version,
            "plugin_type": self.plugin_type.value,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "requires_python": self.requires_python,
            "dependencies": self.dependencies,
            "entry_point": self.entry_point,
            "config_schema": self.config_schema,
        }


class PluginBase(abc.ABC):
    def __init__(self, metadata: PluginMetadata) -> None:
        self.metadata = metadata
        self._enabled = True
        self._config: dict[str, t.Any] = {}

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def version(self) -> str:
        return self.metadata.version

    @property
    def plugin_type(self) -> PluginType:
        return self.metadata.plugin_type

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def configure(self, config: dict[str, t.Any]) -> None:
        self._config = config.copy()
        self.validate_config(config)

    @abc.abstractmethod
    def activate(self) -> bool:
        pass

    @abc.abstractmethod
    def deactivate(self) -> bool:
        pass

    def validate_config(self, config: dict[str, t.Any]) -> None:
        schema = self.metadata.config_schema

        if not schema:
            return

        required_keys = schema.get("required", [])
        for key in required_keys:
            if key not in config:
                msg = f"Required config key '{key}' missing for plugin {self.name}"
                raise ValueError(
                    msg,
                )

    def get_config(self, key: str, default: t.Any = None) -> t.Any:
        return self._config.get(key, default)

    def get_info(self) -> dict[str, t.Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "enabled": self.enabled,
            "config": self._config,
        }


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, PluginBase] = {}
        self._plugins_by_type: dict[PluginType, list[PluginBase]] = {}

    def register(self, plugin: PluginBase) -> bool:
        if plugin.name in self._plugins:
            return False

        self._plugins[plugin.name] = plugin

        plugin_type = plugin.plugin_type
        if plugin_type not in self._plugins_by_type:
            self._plugins_by_type[plugin_type] = []
        self._plugins_by_type[plugin_type].append(plugin)

        return True

    def unregister(self, plugin_name: str) -> bool:
        if plugin_name not in self._plugins:
            return False

        plugin = self._plugins.pop(plugin_name)

        plugin_type = plugin.plugin_type
        if plugin_type in self._plugins_by_type:
            self._plugins_by_type[plugin_type] = [
                p for p in self._plugins_by_type[plugin_type] if p.name != plugin_name
            ]

        return True

    def get(self, plugin_name: str) -> PluginBase | None:
        return self._plugins.get(plugin_name)

    def get_by_type(self, plugin_type: PluginType) -> list[PluginBase]:
        return self._plugins_by_type.get(plugin_type, []).copy()

    def get_enabled(self, plugin_type: PluginType | None = None) -> list[PluginBase]:
        if plugin_type:
            plugins = self.get_by_type(plugin_type)
        else:
            plugins = list[t.Any](self._plugins.values())

        return [p for p in plugins if p.enabled]

    def list_all(self) -> dict[str, PluginBase]:
        return self._plugins.copy()

    def activate_all(self) -> dict[str, bool]:
        results = {}
        for plugin in self._plugins.values():
            if plugin.enabled:
                try:
                    results[plugin.name] = plugin.activate()
                except Exception:
                    results[plugin.name] = False

        return results

    def deactivate_all(self) -> dict[str, bool]:
        results = {}
        for plugin in self._plugins.values():
            try:
                results[plugin.name] = plugin.deactivate()
            except Exception:
                results[plugin.name] = False

        return results

    def get_stats(self) -> dict[str, t.Any]:
        by_type = {}
        for plugin_type in PluginType:
            plugins = self.get_by_type(plugin_type)
            by_type[plugin_type.value] = {
                "total": len(plugins),
                "enabled": len([p for p in plugins if p.enabled]),
                "disabled": len([p for p in plugins if not p.enabled]),
            }

        return {
            "total_plugins": len(self._plugins),
            "enabled_plugins": len([p for p in self._plugins.values() if p.enabled]),
            "by_type": by_type,
        }


_registry = PluginRegistry()


def get_plugin_registry() -> PluginRegistry:
    return _registry
