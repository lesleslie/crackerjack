import importlib
import importlib.util
import json
import logging
import typing as t
from pathlib import Path

from crackerjack.config.hooks import HookStage

from .base import (
    PluginBase,
    PluginMetadata,
    PluginRegistry,
    PluginType,
    get_plugin_registry,
)
from .hooks import CustomHookDefinition, CustomHookPlugin


class PluginLoadError(Exception):
    pass


class PluginLoader:
    def __init__(self, registry: PluginRegistry | None = None) -> None:
        self.registry = registry or get_plugin_registry()
        self.logger = logging.getLogger("crackerjack.plugin_loader")

    def load_plugin_from_file(self, plugin_file: Path) -> PluginBase:
        if not plugin_file.exists():
            msg = f"Plugin file not found: {plugin_file}"
            raise PluginLoadError(msg)

        if plugin_file.suffix != ".py":
            msg = f"Plugin file must be .py: {plugin_file}"
            raise PluginLoadError(msg)

        spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
        if not spec or not spec.loader:
            msg = f"Could not create module spec for: {plugin_file}"
            raise PluginLoadError(msg)

        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            msg = f"Failed to execute plugin module {plugin_file}: {e}"
            raise PluginLoadError(msg)

        plugin = self._extract_plugin_from_module(module, plugin_file)

        if not isinstance(plugin, PluginBase):
            msg = f"Plugin {plugin_file} does not provide a PluginBase instance"
            raise PluginLoadError(
                msg,
            )

        return plugin

    def load_plugin_from_config(self, config_file: Path) -> PluginBase:
        if not config_file.exists():
            msg = f"Plugin config file not found: {config_file}"
            raise PluginLoadError(msg)

        try:
            if config_file.suffix == ".json":
                with config_file.open() as f:
                    config = json.load(f)
            elif config_file.suffix in (".yaml", ".yml"):
                import yaml

                with config_file.open() as f:
                    config = yaml.safe_load(f)
            else:
                msg = f"Unsupported config format: {config_file.suffix}"
                raise PluginLoadError(
                    msg,
                )
        except Exception as e:
            msg = f"Failed to parse config file {config_file}: {e}"
            raise PluginLoadError(msg)

        return self._create_plugin_from_config(config, config_file)

    def _extract_plugin_from_module(
        self,
        module: t.Any,
        plugin_file: Path,
    ) -> PluginBase:
        plugin = self._try_standard_entry_points(module)
        if plugin:
            return plugin

        plugin = self._try_plugin_subclasses(module, plugin_file)
        if plugin:
            return plugin

        msg = f"No valid plugin found in {plugin_file}"
        raise PluginLoadError(msg)

    def _try_standard_entry_points(self, module: t.Any) -> PluginBase | None:
        entry_points = [
            "plugin",
            "create_plugin",
            "PLUGIN",
        ]

        for entry_point in entry_points:
            plugin = self._try_single_entry_point(module, entry_point)
            if plugin:
                return plugin

        return None

    def _try_single_entry_point(
        self,
        module: t.Any,
        entry_point: str,
    ) -> PluginBase | None:
        if not hasattr(module, entry_point):
            return None

        obj = getattr(module, entry_point)

        if isinstance(obj, PluginBase):
            return obj
        if callable(obj):
            return self._try_factory_function(obj, entry_point)

        return None

    def _try_factory_function(
        self,
        factory: t.Callable[..., t.Any],
        name: str,
    ) -> PluginBase | None:
        try:
            result = factory()
            if isinstance(result, PluginBase):
                return result
        except Exception as e:
            self.logger.warning(f"Plugin factory {name} failed: {e}")
        return None

    def _try_plugin_subclasses(
        self,
        module: t.Any,
        plugin_file: Path,
    ) -> PluginBase | None:
        for name, obj in vars(module).items():
            if self._is_valid_plugin_class(obj):
                plugin = self._try_instantiate_plugin_class(obj, name, plugin_file)
                if plugin:
                    return plugin
        return None

    def _is_valid_plugin_class(self, obj: t.Any) -> bool:
        return (
            isinstance(obj, type)
            and issubclass(obj, PluginBase)
            and obj is not PluginBase
        )

    def _try_instantiate_plugin_class(
        self,
        plugin_class: type[PluginBase],
        name: str,
        plugin_file: Path,
    ) -> PluginBase | None:
        try:
            metadata = PluginMetadata(
                name=plugin_file.stem,
                version="1.0.0",
                plugin_type=PluginType.HOOK,
                description="Custom plugin",
            )
            return plugin_class(metadata)
        except Exception as e:
            self.logger.warning(f"Failed to instantiate plugin class {name}: {e}")
            return None

    def _create_plugin_from_config(
        self,
        config: dict[str, t.Any],
        config_file: Path,
    ) -> PluginBase:
        metadata = PluginMetadata(
            name=config.get("name", config_file.stem),
            version=config.get("version", "1.0.0"),
            plugin_type=PluginType(config.get("type", "hook")),
            description=config.get("description", "Custom plugin"),
            author=config.get("author", ""),
            license=config.get("license", ""),
            dependencies=config.get("dependencies", []),
        )

        if metadata.plugin_type == PluginType.HOOK:
            return self._create_hook_plugin_from_config(metadata, config)
        msg = f"Unsupported plugin type: {metadata.plugin_type}"
        raise PluginLoadError(msg)

    def _create_hook_plugin_from_config(
        self,
        metadata: PluginMetadata,
        config: dict[str, t.Any],
    ) -> CustomHookPlugin:
        hooks_config = config.get("hooks", [])
        hook_definitions = []

        for hook_config in hooks_config:
            hook_def = CustomHookDefinition(
                name=hook_config["name"],
                description=hook_config.get("description", ""),
                command=hook_config.get("command", []),
                file_patterns=hook_config.get("file_patterns", []),
                timeout=hook_config.get("timeout", 60),
                stage=HookStage(hook_config.get("stage", "comprehensive")),
                requires_files=hook_config.get("requires_files", True),
                parallel_safe=hook_config.get("parallel_safe", True),
            )
            hook_definitions.append(hook_def)

        return CustomHookPlugin(metadata, hook_definitions)

    def load_and_register(self, plugin_source: Path) -> bool:
        try:
            if plugin_source.suffix == ".py":
                plugin = self.load_plugin_from_file(plugin_source)
            elif plugin_source.suffix in (".json", ".yaml", ".yml"):
                plugin = self.load_plugin_from_config(plugin_source)
            else:
                self.logger.error(f"Unsupported plugin file type: {plugin_source}")
                return False

            success = self.registry.register(plugin)
            if success:
                self.logger.info(f"Successfully loaded plugin: {plugin.name}")
            else:
                self.logger.warning(f"Plugin already registered: {plugin.name}")

            return success

        except PluginLoadError as e:
            self.logger.exception(f"Failed to load plugin from {plugin_source}: {e}")
            return False
        except Exception as e:
            self.logger.exception(
                f"Unexpected error loading plugin {plugin_source}: {e}"
            )
            return False


class PluginDiscovery:
    def __init__(self, loader: PluginLoader | None = None) -> None:
        self.loader = loader or PluginLoader()
        self.logger = logging.getLogger("crackerjack.plugin_discovery")

    def discover_in_directory(
        self,
        directory: Path,
        recursive: bool = False,
    ) -> list[Path]:
        if not directory.exists() or not directory.is_dir():
            return []

        plugin_files: list[Path] = []

        patterns = ["*.py", "*.json", "*.yaml", "*.yml"]

        for pattern in patterns:
            if recursive:
                plugin_files.extend(directory.rglob(pattern))
            else:
                plugin_files.extend(directory.glob(pattern))

        return [f for f in plugin_files if self._looks_like_plugin_file(f)]

    def discover_in_project(self, project_path: Path) -> list[Path]:
        plugin_files: list[Path] = []

        plugin_dirs = [
            project_path / "plugins",
            project_path / ".cache" / "crackerjack" / "plugins",
            project_path / "tools" / "crackerjack",
        ]

        for plugin_dir in plugin_dirs:
            if plugin_dir.exists():
                plugin_files.extend(
                    self.discover_in_directory(plugin_dir, recursive=True),
                )

        return plugin_files

    def load_discovered_plugins(self, plugin_files: list[Path]) -> dict[str, bool]:
        results = {}

        for plugin_file in plugin_files:
            self.logger.info(f"Loading plugin: {plugin_file}")
            success = self.loader.load_and_register(plugin_file)
            results[str(plugin_file)] = success

        return results

    def auto_discover_and_load(self, project_path: Path) -> dict[str, bool]:
        plugin_files = self.discover_in_project(project_path)

        if plugin_files:
            self.logger.info(f"Found {len(plugin_files)} potential plugin files")
            return self.load_discovered_plugins(plugin_files)
        self.logger.info("No plugin files found")
        return {}

    def _looks_like_plugin_file(self, file_path: Path) -> bool:
        name_lower = file_path.name.lower()

        if name_lower.startswith(("test_", "__", ".")):
            return False

        if name_lower in ("__init__.py", "setup.py", "conftest.py"):
            return False

        plugin_indicators = [
            "plugin",
            "hook",
            "extension",
            "addon",
            "crackerjack",
            "check",
            "lint",
            "format",
        ]

        return any(indicator in name_lower for indicator in plugin_indicators)
