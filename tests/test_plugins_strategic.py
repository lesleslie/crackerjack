import pytest


@pytest.mark.unit
class TestPluginBase:
    def test_plugin_base_import(self) -> None:
        from crackerjack.plugins.base import PluginMetadata, PluginType

        assert PluginMetadata is not None
        assert PluginType is not None


@pytest.mark.unit
class TestPluginHooks:
    def test_plugin_hooks_import(self) -> None:
        import crackerjack.plugins.hooks

        assert crackerjack.plugins.hooks is not None


@pytest.mark.unit
class TestPluginLoader:
    def test_plugin_loader_import(self) -> None:
        from crackerjack.plugins.loader import PluginLoader, PluginLoadError

        assert PluginLoader is not None
        assert PluginLoadError is not None


@pytest.mark.unit
class TestPluginManagers:
    def test_plugin_managers_import(self) -> None:
        from crackerjack.plugins.managers import PluginManager, PluginRegistry

        assert PluginManager is not None
        assert PluginRegistry is not None
