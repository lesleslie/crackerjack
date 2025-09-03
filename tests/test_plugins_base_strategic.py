import pytest

from crackerjack.plugins.base import (
    PluginBase,
    PluginMetadata,
    PluginRegistry,
    PluginType,
    get_plugin_registry,
)


class TestPluginType:
    def test_plugin_type_enum_values(self) -> None:
        assert PluginType.HOOK.value == "hook"
        assert PluginType.WORKFLOW.value == "workflow"
        assert PluginType.INTEGRATION.value == "integration"
        assert PluginType.FORMATTER.value == "formatter"
        assert PluginType.ANALYZER.value == "analyzer"
        assert PluginType.PUBLISHER.value == "publisher"

    def test_plugin_type_enum_membership(self) -> None:
        all_types = list(PluginType)
        assert len(all_types) == 6
        assert PluginType.HOOK in all_types
        assert PluginType.WORKFLOW in all_types
        assert PluginType.INTEGRATION in all_types
        assert PluginType.FORMATTER in all_types
        assert PluginType.ANALYZER in all_types
        assert PluginType.PUBLISHER in all_types


class TestPluginMetadata:
    def test_metadata_required_fields(self) -> None:
        metadata = PluginMetadata(
            name="test - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="A test plugin",
        )

        assert metadata.name == "test - plugin"
        assert metadata.version == "1.0.0"
        assert metadata.plugin_type == PluginType.HOOK
        assert metadata.description == "A test plugin"

    def test_metadata_optional_fields_defaults(self) -> None:
        metadata = PluginMetadata(
            name="test - plugin",
            version="1.0.0",
            plugin_type=PluginType.ANALYZER,
            description="Test description",
        )

        assert metadata.author == ""
        assert metadata.license == ""
        assert metadata.requires_python == ">=    3.11"
        assert metadata.dependencies == []
        assert metadata.entry_point == ""
        assert metadata.config_schema == {}

    def test_metadata_all_fields_custom(self) -> None:
        dependencies = ["requests", "pydantic"]
        config_schema = {
            "required": ["api_key"],
            "properties": {"api_key": {"type": "string"}},
        }

        metadata = PluginMetadata(
            name="advanced - plugin",
            version="2.1.0",
            plugin_type=PluginType.INTEGRATION,
            description="Advanced integration plugin",
            author="Test Author",
            license="MIT",
            requires_python=">=    3.12",
            dependencies=dependencies,
            entry_point="advanced_plugin: main",
            config_schema=config_schema,
        )

        assert metadata.name == "advanced - plugin"
        assert metadata.version == "2.1.0"
        assert metadata.plugin_type == PluginType.INTEGRATION
        assert metadata.description == "Advanced integration plugin"
        assert metadata.author == "Test Author"
        assert metadata.license == "MIT"
        assert metadata.requires_python == ">=    3.12"
        assert metadata.dependencies == dependencies
        assert metadata.entry_point == "advanced_plugin: main"
        assert metadata.config_schema == config_schema

    def test_metadata_to_dict(self) -> None:
        metadata = PluginMetadata(
            name="dict - plugin",
            version="0.5.0",
            plugin_type=PluginType.FORMATTER,
            description="Plugin for dict testing",
            author="Dict Author",
            license="Apache - 2.0",
            requires_python=">=    3.11",
            dependencies=["black", "ruff"],
            entry_point="dict_plugin.main: run",
            config_schema={"type": "object"},
        )

        result = metadata.to_dict()
        expected = {
            "name": "dict - plugin",
            "version": "0.5.0",
            "plugin_type": "formatter",
            "description": "Plugin for dict testing",
            "author": "Dict Author",
            "license": "Apache - 2.0",
            "requires_python": ">=    3.11",
            "dependencies": ["black", "ruff"],
            "entry_point": "dict_plugin.main: run",
            "config_schema": {"type": "object"},
        }

        assert result == expected
        assert isinstance(result["plugin_type"], str)

    def test_metadata_mutable_defaults_isolation(self) -> None:
        metadata1 = PluginMetadata("plugin1", "1.0.0", PluginType.HOOK, "desc1")
        metadata2 = PluginMetadata("plugin2", "1.0.0", PluginType.HOOK, "desc2")

        metadata1.dependencies.append("dep1")
        metadata1.config_schema["key1"] = "value1"

        assert metadata2.dependencies == []
        assert metadata2.config_schema == {}


class TestPluginBase:
    @pytest.fixture
    def sample_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Test plugin for base class testing",
        )

    @pytest.fixture
    def concrete_plugin_class(self):
        class ConcretePlugin(PluginBase):
            def __init__(self, metadata: PluginMetadata) -> None:
                super().__init__(metadata)
                self.activate_called = False
                self.deactivate_called = False

            def activate(self) -> bool:
                self.activate_called = True
                return True

            def deactivate(self) -> bool:
                self.deactivate_called = True
                return True

        return ConcretePlugin

    def test_plugin_base_abstract_instantiation(self, sample_metadata) -> None:
        with pytest.raises(
            TypeError, match="Can't instantiate abstract class PluginBase"
        ):
            PluginBase(sample_metadata)

    def test_plugin_base_concrete_instantiation(
        self, concrete_plugin_class, sample_metadata
    ) -> None:
        plugin = concrete_plugin_class(sample_metadata)

        assert plugin.metadata == sample_metadata
        assert plugin._enabled is True
        assert plugin._config == {}

    def test_plugin_properties(self, concrete_plugin_class, sample_metadata) -> None:
        plugin = concrete_plugin_class(sample_metadata)

        assert plugin.name == "test - plugin"
        assert plugin.version == "1.0.0"
        assert plugin.plugin_type == PluginType.HOOK
        assert plugin.enabled is True

    def test_plugin_enable_disable(
        self, concrete_plugin_class, sample_metadata
    ) -> None:
        plugin = concrete_plugin_class(sample_metadata)

        assert plugin.enabled is True

        plugin.disable()
        assert plugin.enabled is False

        plugin.enable()
        assert plugin.enabled is True

    def test_plugin_configure_basic(
        self, concrete_plugin_class, sample_metadata
    ) -> None:
        plugin = concrete_plugin_class(sample_metadata)
        config = {"setting1": "value1", "setting2": 42}

        plugin.configure(config)

        assert plugin._config == config
        assert plugin.get_config("setting1") == "value1"
        assert plugin.get_config("setting2") == 42

    def test_plugin_configure_with_schema_validation(
        self, concrete_plugin_class
    ) -> None:
        metadata = PluginMetadata(
            name="validated - plugin",
            version="1.0.0",
            plugin_type=PluginType.WORKFLOW,
            description="Plugin with validation",
            config_schema={"required": ["api_key", "endpoint"]},
        )
        plugin = concrete_plugin_class(metadata)

        valid_config = {"api_key": "secret", "endpoint": "https: / / api.example.com"}
        plugin.configure(valid_config)

        invalid_config = {"api_key": "secret"}
        with pytest.raises(ValueError, match="Required config key 'endpoint' missing"):
            plugin.configure(invalid_config)

    def test_plugin_configure_no_schema(
        self, concrete_plugin_class, sample_metadata
    ) -> None:
        plugin = concrete_plugin_class(sample_metadata)
        config = {"any_key": "any_value"}

        plugin.configure(config)
        assert plugin._config == config

    def test_plugin_get_config_with_default(
        self, concrete_plugin_class, sample_metadata
    ) -> None:
        plugin = concrete_plugin_class(sample_metadata)
        plugin.configure({"existing_key": "existing_value"})

        assert plugin.get_config("existing_key") == "existing_value"
        assert plugin.get_config("missing_key") is None
        assert plugin.get_config("missing_key", "default") == "default"

    def test_plugin_get_info(self, concrete_plugin_class) -> None:
        metadata = PluginMetadata(
            name="info - plugin",
            version="2.0.0",
            plugin_type=PluginType.PUBLISHER,
            description="Plugin for info testing",
            author="Info Author",
        )
        plugin = concrete_plugin_class(metadata)
        config = {"key": "value"}
        plugin.configure(config)
        plugin.disable()

        info = plugin.get_info()

        assert "metadata" in info
        assert "enabled" in info
        assert "config" in info

        assert info["metadata"] == metadata.to_dict()
        assert info["enabled"] is False
        assert info["config"] == config

    def test_plugin_config_copy_isolation(
        self, concrete_plugin_class, sample_metadata
    ) -> None:
        plugin = concrete_plugin_class(sample_metadata)
        original_config = {"key1": "value1", "key2": "value2"}

        plugin.configure(original_config)

        original_config["new_key"] = "new_value"
        original_config["key1"] = "modified_value"

        assert plugin._config == {"key1": "value1", "key2": "value2"}
        assert "new_key" not in plugin._config

        original_config_with_nested = {"mutable_list": [1, 2, 3], "string": "test"}
        plugin.configure(original_config_with_nested)

        original_config_with_nested["new_top_level"] = "new"
        assert "new_top_level" not in plugin._config

        original_config_with_nested["mutable_list"].append(4)
        assert plugin._config["mutable_list"] == [
            1,
            2,
            3,
            4,
        ]

    def test_plugin_abstract_methods_implementation(
        self, concrete_plugin_class, sample_metadata
    ) -> None:
        plugin = concrete_plugin_class(sample_metadata)

        result = plugin.activate()
        assert result is True
        assert plugin.activate_called is True

        result = plugin.deactivate()
        assert result is True
        assert plugin.deactivate_called is True


class TestPluginRegistry:
    @pytest.fixture
    def registry(self) -> PluginRegistry:
        return PluginRegistry()

    @pytest.fixture
    def sample_plugin(self) -> PluginBase:
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
        return TestPlugin(metadata)

    @pytest.fixture
    def multiple_plugins(self) -> list[PluginBase]:
        class TestPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        plugins = []
        plugin_configs = [
            ("hook - plugin", PluginType.HOOK),
            ("workflow - plugin", PluginType.WORKFLOW),
            ("analyzer - plugin", PluginType.ANALYZER),
            ("formatter - plugin", PluginType.FORMATTER),
        ]

        for name, plugin_type in plugin_configs:
            metadata = PluginMetadata(
                name=name,
                version="1.0.0",
                plugin_type=plugin_type,
                description=f"Test {plugin_type.value} plugin",
            )
            plugins.append(TestPlugin(metadata))

        return plugins

    def test_registry_initialization(self, registry) -> None:
        assert registry._plugins == {}
        assert registry._plugins_by_type == {}

    def test_register_plugin_success(self, registry, sample_plugin) -> None:
        result = registry.register(sample_plugin)

        assert result is True
        assert "test - plugin" in registry._plugins
        assert registry._plugins["test - plugin"] == sample_plugin
        assert PluginType.HOOK in registry._plugins_by_type
        assert sample_plugin in registry._plugins_by_type[PluginType.HOOK]

    def test_register_plugin_duplicate_name(self, registry, sample_plugin) -> None:
        result1 = registry.register(sample_plugin)
        assert result1 is True

        result2 = registry.register(sample_plugin)
        assert result2 is False

        assert len(registry._plugins) == 1
        assert len(registry._plugins_by_type[PluginType.HOOK]) == 1

    def test_register_multiple_plugins_same_type(
        self, registry, multiple_plugins
    ) -> None:
        hook_plugins = [p for p in multiple_plugins if p.plugin_type == PluginType.HOOK]

        for plugin in hook_plugins:
            result = registry.register(plugin)
            assert result is True

        registered_hooks = registry._plugins_by_type.get(PluginType.HOOK, [])
        assert len(registered_hooks) == len(hook_plugins)

    def test_unregister_plugin_success(self, registry, sample_plugin) -> None:
        registry.register(sample_plugin)
        assert "test - plugin" in registry._plugins

        result = registry.unregister("test - plugin")
        assert result is True
        assert "test - plugin" not in registry._plugins
        assert sample_plugin not in registry._plugins_by_type.get(PluginType.HOOK, [])

    def test_unregister_nonexistent_plugin(self, registry) -> None:
        result = registry.unregister("nonexistent - plugin")
        assert result is False

    def test_get_plugin_success(self, registry, sample_plugin) -> None:
        registry.register(sample_plugin)

        retrieved = registry.get("test - plugin")
        assert retrieved == sample_plugin

    def test_get_plugin_nonexistent(self, registry) -> None:
        result = registry.get("nonexistent - plugin")
        assert result is None

    def test_get_by_type(self, registry, multiple_plugins) -> None:
        for plugin in multiple_plugins:
            registry.register(plugin)

        hook_plugins = registry.get_by_type(PluginType.HOOK)
        workflow_plugins = registry.get_by_type(PluginType.WORKFLOW)

        assert len(hook_plugins) == 1
        assert len(workflow_plugins) == 1
        assert hook_plugins[0].plugin_type == PluginType.HOOK
        assert workflow_plugins[0].plugin_type == PluginType.WORKFLOW

    def test_get_by_type_empty(self, registry) -> None:
        result = registry.get_by_type(PluginType.INTEGRATION)
        assert result == []

    def test_get_by_type_returns_copy(self, registry, multiple_plugins) -> None:
        for plugin in multiple_plugins:
            registry.register(plugin)

        hook_plugins = registry.get_by_type(PluginType.HOOK)
        hook_plugins.clear()

        assert len(registry._plugins_by_type[PluginType.HOOK]) == 1

    def test_get_enabled_all_types(self, registry, multiple_plugins) -> None:
        for plugin in multiple_plugins:
            registry.register(plugin)

        enabled = registry.get_enabled()
        assert len(enabled) == len(multiple_plugins)

    def test_get_enabled_with_disabled_plugins(
        self, registry, multiple_plugins
    ) -> None:
        for plugin in multiple_plugins:
            registry.register(plugin)

        multiple_plugins[0].disable()

        enabled = registry.get_enabled()
        assert len(enabled) == len(multiple_plugins) - 1
        assert multiple_plugins[0] not in enabled

    def test_get_enabled_by_type(self, registry, multiple_plugins) -> None:
        for plugin in multiple_plugins:
            registry.register(plugin)

        hook_plugin = next(
            p for p in multiple_plugins if p.plugin_type == PluginType.HOOK
        )
        hook_plugin.disable()

        enabled_hooks = registry.get_enabled(PluginType.HOOK)
        assert len(enabled_hooks) == 0

        enabled_workflows = registry.get_enabled(PluginType.WORKFLOW)
        assert len(enabled_workflows) == 1

    def test_list_all(self, registry, multiple_plugins) -> None:
        for plugin in multiple_plugins:
            registry.register(plugin)

        all_plugins = registry.list_all()
        assert len(all_plugins) == len(multiple_plugins)

        all_plugins.clear()
        assert len(registry._plugins) == len(multiple_plugins)

    def test_activate_all_success(self, registry) -> None:
        class ActivatablePlugin(PluginBase):
            def __init__(self, name: str) -> None:
                metadata = PluginMetadata(name, "1.0.0", PluginType.HOOK, "Test")
                super().__init__(metadata)
                self.activated = False

            def activate(self) -> bool:
                self.activated = True
                return True

            def deactivate(self) -> bool:
                return True

        plugins = [ActivatablePlugin(f"plugin -{i}") for i in range(3)]
        for plugin in plugins:
            registry.register(plugin)

        results = registry.activate_all()

        assert len(results) == 3
        assert all(results.values())
        assert all(p.activated for p in plugins)

    def test_activate_all_with_failures(self, registry) -> None:
        class ProblematicPlugin(PluginBase):
            def __init__(self, name: str, should_fail: bool = False) -> None:
                metadata = PluginMetadata(name, "1.0.0", PluginType.HOOK, "Test")
                super().__init__(metadata)
                self.should_fail = should_fail

            def activate(self) -> bool:
                if self.should_fail:
                    raise Exception("Activation failed")
                return True

            def deactivate(self) -> bool:
                return True

        good_plugin = ProblematicPlugin("good - plugin", False)
        bad_plugin = ProblematicPlugin("bad - plugin", True)

        registry.register(good_plugin)
        registry.register(bad_plugin)

        results = registry.activate_all()

        assert results["good - plugin"] is True
        assert results["bad - plugin"] is False

    def test_activate_all_disabled_plugins_skipped(self, registry) -> None:
        class TestPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        enabled_plugin = TestPlugin(
            PluginMetadata("enabled", "1.0.0", PluginType.HOOK, "Test")
        )
        disabled_plugin = TestPlugin(
            PluginMetadata("disabled", "1.0.0", PluginType.HOOK, "Test")
        )
        disabled_plugin.disable()

        registry.register(enabled_plugin)
        registry.register(disabled_plugin)

        results = registry.activate_all()

        assert "enabled" in results
        assert "disabled" not in results

    def test_deactivate_all(self, registry) -> None:
        class DeactivatablePlugin(PluginBase):
            def __init__(self, name: str) -> None:
                metadata = PluginMetadata(name, "1.0.0", PluginType.HOOK, "Test")
                super().__init__(metadata)
                self.deactivated = False

            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                self.deactivated = True
                return True

        plugins = [DeactivatablePlugin(f"plugin -{i}") for i in range(2)]
        for plugin in plugins:
            registry.register(plugin)

        results = registry.deactivate_all()

        assert len(results) == 2
        assert all(results.values())
        assert all(p.deactivated for p in plugins)

    def test_deactivate_all_with_failures(self, registry) -> None:
        class ProblematicPlugin(PluginBase):
            def __init__(self, name: str, should_fail: bool = False) -> None:
                metadata = PluginMetadata(name, "1.0.0", PluginType.HOOK, "Test")
                super().__init__(metadata)
                self.should_fail = should_fail

            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                if self.should_fail:
                    raise Exception("Deactivation failed")
                return True

        good_plugin = ProblematicPlugin("good - plugin", False)
        bad_plugin = ProblematicPlugin("bad - plugin", True)

        registry.register(good_plugin)
        registry.register(bad_plugin)

        results = registry.deactivate_all()

        assert results["good - plugin"] is True
        assert results["bad - plugin"] is False

    def test_get_stats(self, registry, multiple_plugins) -> None:
        for plugin in multiple_plugins:
            registry.register(plugin)

        multiple_plugins[0].disable()

        stats = registry.get_stats()

        assert stats["total_plugins"] == len(multiple_plugins)
        assert stats["enabled_plugins"] == len(multiple_plugins) - 1
        assert "by_type" in stats

        by_type = stats["by_type"]
        assert "hook" in by_type
        assert "workflow" in by_type
        assert "analyzer" in by_type
        assert "formatter" in by_type

        hook_stats = by_type["hook"]
        assert hook_stats["total"] == 1
        assert hook_stats["enabled"] == 0
        assert hook_stats["disabled"] == 1

    def test_get_stats_empty_registry(self, registry) -> None:
        stats = registry.get_stats()

        assert stats["total_plugins"] == 0
        assert stats["enabled_plugins"] == 0

        by_type = stats["by_type"]
        for plugin_type in PluginType:
            type_stats = by_type[plugin_type.value]
            assert type_stats["total"] == 0
            assert type_stats["enabled"] == 0
            assert type_stats["disabled"] == 0


class TestGlobalRegistry:
    def test_get_plugin_registry_returns_singleton(self) -> None:
        registry1 = get_plugin_registry()
        registry2 = get_plugin_registry()

        assert registry1 is registry2
        assert isinstance(registry1, PluginRegistry)

    def test_global_registry_persistence(self) -> None:
        registry = get_plugin_registry()

        class PersistentPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        metadata = PluginMetadata("persistent", "1.0.0", PluginType.HOOK, "Test")
        plugin = PersistentPlugin(metadata)

        registry.register(plugin)

        registry2 = get_plugin_registry()
        assert registry2.get("persistent") == plugin


class TestPluginIntegration:
    def test_end_to_end_plugin_lifecycle(self) -> None:
        class LifecyclePlugin(PluginBase):
            def __init__(self) -> None:
                metadata = PluginMetadata(
                    name="lifecycle - plugin",
                    version="1.0.0",
                    plugin_type=PluginType.INTEGRATION,
                    description="Full lifecycle test plugin",
                    config_schema={"required": ["key"]},
                )
                super().__init__(metadata)
                self.state = "created"

            def activate(self) -> bool:
                self.state = "activated"
                return True

            def deactivate(self) -> bool:
                self.state = "deactivated"
                return True

        registry = get_plugin_registry()
        plugin = LifecyclePlugin()

        assert registry.register(plugin) is True
        assert plugin.state == "created"

        plugin.configure({"key": "value"})
        assert plugin.get_config("key") == "value"

        results = registry.activate_all()
        assert results["lifecycle - plugin"] is True
        assert plugin.state == "activated"

        stats = registry.get_stats()
        assert stats["total_plugins"] >= 1

        results = registry.deactivate_all()
        assert results["lifecycle - plugin"] is True
        assert plugin.state == "deactivated"

        assert registry.unregister("lifecycle - plugin") is True
        assert registry.get("lifecycle - plugin") is None

    def test_plugin_type_filtering_and_management(self) -> None:
        registry = PluginRegistry()

        class MultiTypePlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        plugin_types = [PluginType.HOOK, PluginType.FORMATTER, PluginType.ANALYZER]
        plugins = []

        for i, plugin_type in enumerate(plugin_types):
            metadata = PluginMetadata(
                name=f"{plugin_type.value}- plugin -{i}",
                version="1.0.0",
                plugin_type=plugin_type,
                description=f"Test {plugin_type.value} plugin",
            )
            plugin = MultiTypePlugin(metadata)
            plugins.append(plugin)
            registry.register(plugin)

        hook_plugins = registry.get_by_type(PluginType.HOOK)
        formatter_plugins = registry.get_by_type(PluginType.FORMATTER)
        analyzer_plugins = registry.get_by_type(PluginType.ANALYZER)

        assert len(hook_plugins) == 1
        assert len(formatter_plugins) == 1
        assert len(analyzer_plugins) == 1

        plugins[0].disable()
        enabled_all = registry.get_enabled()
        enabled_hooks = registry.get_enabled(PluginType.HOOK)
        enabled_formatters = registry.get_enabled(PluginType.FORMATTER)

        assert len(enabled_all) == 2
        assert len(enabled_hooks) == 0
        assert len(enabled_formatters) == 1

        stats = registry.get_stats()
        assert stats["total_plugins"] == 3
        assert stats["enabled_plugins"] == 2

        hook_stats = stats["by_type"]["hook"]
        assert hook_stats["total"] == 1
        assert hook_stats["enabled"] == 0
        assert hook_stats["disabled"] == 1
