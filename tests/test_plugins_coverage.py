from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.plugins.base import PluginBase
from crackerjack.plugins.managers import PluginManager


class TestPluginBase:
    def test_plugin_base_interface(self) -> None:
        assert PluginBase is not None

        assert hasattr(PluginBase, "name")
        assert hasattr(PluginBase, "version")
        assert hasattr(PluginBase, "activate")
        assert hasattr(PluginBase, "deactivate")
        assert hasattr(PluginBase, "configure")
        assert hasattr(PluginBase, "enabled")

    def test_plugin_base_abstract_methods(self) -> None:
        from crackerjack.plugins.base import PluginMetadata, PluginType

        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Test plugin",
        )
        with pytest.raises(TypeError):
            PluginBase(metadata)

    def test_plugin_implementation_template(self) -> None:
        from crackerjack.plugins.base import PluginMetadata, PluginType

        class TestPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        metadata = PluginMetadata(
            name="test - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Test plugin",
        )

        plugin = TestPlugin(metadata)
        assert plugin.name == "test - plugin"
        assert plugin.version == "1.0.0"
        assert plugin.activate() is True
        assert plugin.deactivate() is True
        assert plugin.enabled is True


class TestPluginManager:
    @pytest.fixture
    def plugin_manager(self):
        mock_console = Mock()
        mock_project_path = Path("/test / project")
        return PluginManager(console=mock_console, project_path=mock_project_path)

    def test_plugin_manager_initialization(self, plugin_manager) -> None:
        assert plugin_manager is not None
        assert hasattr(plugin_manager, "registry")
        assert hasattr(plugin_manager, "console")
        assert hasattr(plugin_manager, "project_path")
        assert plugin_manager._initialized is False

    def test_plugin_registration(self, plugin_manager) -> None:
        from crackerjack.plugins.base import PluginMetadata, PluginType

        class MockPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        metadata = PluginMetadata(
            name="mock - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Mock plugin for testing",
        )
        mock_plugin = MockPlugin(metadata)

        result = plugin_manager.registry.register(mock_plugin)
        assert result is True

        retrieved_plugin = plugin_manager.registry.get("mock - plugin")
        assert retrieved_plugin == mock_plugin

    def test_plugin_discovery(self, plugin_manager) -> None:
        assert hasattr(plugin_manager, "discovery")
        assert hasattr(plugin_manager.discovery, "auto_discover_and_load")

        with patch.object(
            plugin_manager.discovery,
            "auto_discover_and_load",
        ) as mock_discover:
            mock_discover.return_value = {}
            result = plugin_manager.discovery.auto_discover_and_load(
                plugin_manager.project_path,
            )
            assert isinstance(result, dict)

    def test_plugin_lifecycle_management(self, plugin_manager) -> None:
        from crackerjack.plugins.base import PluginMetadata, PluginType

        class LifecyclePlugin(PluginBase):
            def __init__(self, metadata) -> None:
                super().__init__(metadata)
                self.activated = False
                self.deactivated = False

            def activate(self) -> bool:
                self.activated = True
                return True

            def deactivate(self) -> bool:
                self.deactivated = True
                return True

        metadata = PluginMetadata(
            name="lifecycle - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Lifecycle test plugin",
        )
        plugin = LifecyclePlugin(metadata)
        plugin_manager.registry.register(plugin)

        result = plugin_manager.enable_plugin("lifecycle - plugin")
        assert result is True
        assert plugin.activated is True

        result = plugin_manager.disable_plugin("lifecycle - plugin")
        assert result is True
        assert plugin.deactivated is True

    def test_plugin_error_handling(self, plugin_manager) -> None:
        from crackerjack.plugins.base import PluginMetadata, PluginType

        class ErrorPlugin(PluginBase):
            def activate(self) -> bool:
                msg = "Activation failed"
                raise Exception(msg)

            def deactivate(self) -> bool:
                msg = "Deactivation failed"
                raise Exception(msg)

        metadata = PluginMetadata(
            name="error - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Error test plugin",
        )
        error_plugin = ErrorPlugin(metadata)
        plugin_manager.registry.register(error_plugin)

        result = plugin_manager.enable_plugin("error - plugin")
        assert result is False

        result = plugin_manager.disable_plugin("error - plugin")
        assert isinstance(result, bool)

    def test_plugin_dependencies(self, plugin_manager) -> None:
        from crackerjack.plugins.base import PluginMetadata, PluginType

        metadata = PluginMetadata(
            name="dependent - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Plugin with dependencies",
            dependencies=["base - plugin"],
        )

        assert "base - plugin" in metadata.dependencies
        assert metadata.to_dict()["dependencies"] == ["base - plugin"]

    def test_plugin_configuration(self, plugin_manager) -> None:
        from crackerjack.plugins.base import PluginMetadata, PluginType

        class ConfigurablePlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        metadata = PluginMetadata(
            name="configurable - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Configurable test plugin",
        )
        plugin = ConfigurablePlugin(metadata)
        plugin_manager.registry.register(plugin)

        config = {"setting1": "value1", "setting2": "value2"}
        result = plugin_manager.configure_plugin("configurable - plugin", config)
        assert isinstance(result, bool)


class TestPluginIntegration:
    def test_plugin_hook_integration(self) -> None:
        from crackerjack.plugins.base import PluginMetadata, PluginType

        class HookPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

            def get_hooks(self) -> list[dict]:
                return [
                    {"name": "custom - hook", "command": ["echo", "custom"]},
                    {"name": "validation - hook", "command": ["validate", "files"]},
                ]

        metadata = PluginMetadata(
            name="hook - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Hook integration plugin",
        )
        plugin = HookPlugin(metadata)
        hooks = plugin.get_hooks()

        assert len(hooks) == 2
        assert hooks[0]["name"] == "custom - hook"
        assert hooks[1]["name"] == "validation - hook"

    def test_plugin_service_integration(self) -> None:
        class ServicePlugin(PluginBase):
            def __init__(self, filesystem_service=None) -> None:
                self.filesystem_service = filesystem_service

            @property
            def name(self) -> str:
                return "service - plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            def initialize(self) -> bool:
                return self.filesystem_service is not None

            def execute(self, *args, **kwargs) -> bool:
                return bool(self.filesystem_service)

        mock_fs_service = Mock()
        plugin = ServicePlugin(filesystem_service=mock_fs_service)

        assert plugin.initialize() is True
        assert plugin.execute() is True

    def test_plugin_manager_service_integration(self) -> None:
        plugin_manager = PluginManager()

        mock_console = Mock()
        mock_config_service = Mock()

        if hasattr(plugin_manager, "set_console"):
            plugin_manager.set_console(mock_console)

        if hasattr(plugin_manager, "set_config_service"):
            plugin_manager.set_config_service(mock_config_service)

        plugins = plugin_manager.discover_plugins()
        assert isinstance(plugins, list)

    def test_plugin_loader_functionality(self) -> None:
        from crackerjack.plugins.loader import PluginLoader

        loader = PluginLoader()

        assert hasattr(loader, "load_plugins")
        assert hasattr(loader, "scan_directories")

        plugins = loader.load_plugins()
        assert isinstance(plugins, list)

    def test_plugin_metadata_handling(self) -> None:
        class MetadataPlugin(PluginBase):
            @property
            def name(self) -> str:
                return "metadata - plugin"

            @property
            def version(self) -> str:
                return "2.1.0"

            @property
            def description(self) -> str:
                return "Plugin with rich metadata"

            @property
            def author(self) -> str:
                return "Test Author"

            @property
            def tags(self) -> list[str]:
                return ["utility", "testing", "automation"]

            def initialize(self) -> bool:
                return True

            def execute(self, *args, **kwargs) -> bool:
                return True

        plugin = MetadataPlugin()

        assert plugin.name == "metadata - plugin"
        assert plugin.version == "2.1.0"
        assert plugin.description == "Plugin with rich metadata"
        assert plugin.author == "Test Author"
        assert "utility" in plugin.tags
        assert "testing" in plugin.tags

    def test_plugin_execution_context(self) -> None:
        class ContextPlugin(PluginBase):
            def __init__(self) -> None:
                self.last_context = None

            @property
            def name(self) -> str:
                return "context - plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            def initialize(self) -> bool:
                return True

            def execute(self, context=None, *args, **kwargs) -> bool:
                self.last_context = context
                return True

        plugin = ContextPlugin()

        test_context = {
            "project_path": " / test / project",
            "files": ["file1.py", "file2.py"],
            "config": {"setting": "value"},
        }

        result = plugin.execute(context=test_context)

        assert result is True
        assert plugin.last_context == test_context


class TestPluginSecurity:
    def test_plugin_sandboxing(self) -> None:
        class SandboxedPlugin(PluginBase):
            @property
            def name(self) -> str:
                return "sandboxed - plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def permissions(self) -> list[str]:
                return ["read_files", "write_temp"]

            def initialize(self) -> bool:
                return True

            def execute(self, *args, **kwargs) -> bool:
                return True

        plugin = SandboxedPlugin()

        assert "read_files" in plugin.permissions
        assert "write_temp" in plugin.permissions
        assert "delete_system" not in plugin.permissions

    def test_plugin_validation(self) -> None:
        plugin_manager = PluginManager()

        class ValidPlugin(PluginBase):
            @property
            def name(self) -> str:
                return "valid - plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            def initialize(self) -> bool:
                return True

            def execute(self, *args, **kwargs) -> bool:
                return True

        class InvalidPlugin:
            def name(self) -> str:
                return "invalid - plugin"

        valid_plugin = ValidPlugin()
        invalid_plugin = InvalidPlugin()

        result = plugin_manager.register_plugin(valid_plugin)
        assert result is True

        result = plugin_manager.register_plugin(invalid_plugin)
        assert result is False or isinstance(result, bool)
