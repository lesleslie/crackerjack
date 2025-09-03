import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.config.hooks import HookStage
from crackerjack.models.protocols import OptionsProtocol
from crackerjack.models.task import HookResult
from crackerjack.plugins.base import (
    PluginBase,
    PluginMetadata,
    PluginRegistry,
    PluginType,
    get_plugin_registry,
)
from crackerjack.plugins.hooks import (
    CustomHookDefinition,
    CustomHookPlugin,
    HookPluginRegistry,
    get_hook_plugin_registry,
)
from crackerjack.plugins.loader import PluginLoader, PluginLoadError
from crackerjack.plugins.managers import PluginManager


class ConcreteTestPlugin(PluginBase):
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


class FailingTestPlugin(PluginBase):
    def activate(self) -> bool:
        return False

    def deactivate(self) -> bool:
        return False


class ExceptionTestPlugin(PluginBase):
    def activate(self) -> bool:
        msg = "Activation failed"
        raise RuntimeError(msg)

    def deactivate(self) -> bool:
        msg = "Deactivation failed"
        raise RuntimeError(msg)


@pytest.fixture
def test_metadata() -> PluginMetadata:
    return PluginMetadata(
        name="test - plugin",
        version="1.0.0",
        plugin_type=PluginType.HOOK,
        description="Test plugin for unit tests",
        author="Test Author",
        license="MIT",
        requires_python=">=    3.11",
        dependencies=["pytest", "mock"],
        entry_point="test_plugin.create_plugin",
        config_schema={
            "required": ["api_key"],
            "properties": {
                "api_key": {"type": "string"},
                "timeout": {"type": "integer", "default": 30},
            },
        },
    )


@pytest.fixture
def mock_options() -> OptionsProtocol:
    options = Mock(spec=OptionsProtocol)
    options.verbose = False
    options.dry_run = False
    return options


@pytest.fixture
def mock_console() -> Console:
    return Mock(spec=Console)


class TestPluginMetadata:
    def test_metadata_creation(self, test_metadata: PluginMetadata) -> None:
        assert test_metadata.name == "test - plugin"
        assert test_metadata.version == "1.0.0"
        assert test_metadata.plugin_type == PluginType.HOOK
        assert test_metadata.description == "Test plugin for unit tests"
        assert test_metadata.author == "Test Author"
        assert test_metadata.license == "MIT"
        assert test_metadata.requires_python == ">=    3.11"
        assert test_metadata.dependencies == ["pytest", "mock"]
        assert test_metadata.entry_point == "test_plugin.create_plugin"
        assert "required" in test_metadata.config_schema

    def test_metadata_defaults(self) -> None:
        metadata = PluginMetadata(
            name="simple - plugin",
            version="1.0.0",
            plugin_type=PluginType.FORMATTER,
            description="Simple test plugin",
        )
        assert metadata.author == ""
        assert metadata.license == ""
        assert metadata.requires_python == ">=    3.11"
        assert metadata.dependencies == []
        assert metadata.entry_point == ""
        assert metadata.config_schema == {}

    def test_metadata_to_dict(self, test_metadata: PluginMetadata) -> None:
        data = test_metadata.to_dict()

        assert data["name"] == "test - plugin"
        assert data["version"] == "1.0.0"
        assert data["plugin_type"] == "hook"
        assert data["description"] == "Test plugin for unit tests"
        assert data["author"] == "Test Author"
        assert data["license"] == "MIT"
        assert data["requires_python"] == ">=    3.11"
        assert data["dependencies"] == ["pytest", "mock"]
        assert data["entry_point"] == "test_plugin.create_plugin"
        assert "required" in data["config_schema"]


class TestPluginType:
    def test_plugin_types(self) -> None:
        assert PluginType.HOOK.value == "hook"
        assert PluginType.WORKFLOW.value == "workflow"
        assert PluginType.INTEGRATION.value == "integration"
        assert PluginType.FORMATTER.value == "formatter"
        assert PluginType.ANALYZER.value == "analyzer"
        assert PluginType.PUBLISHER.value == "publisher"

    def test_plugin_type_from_string(self) -> None:
        assert PluginType("hook") == PluginType.HOOK
        assert PluginType("workflow") == PluginType.WORKFLOW
        assert PluginType("integration") == PluginType.INTEGRATION


class TestPluginBase:
    def test_plugin_base_is_abstract(self, test_metadata: PluginMetadata) -> None:
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PluginBase(test_metadata)

    def test_concrete_plugin_properties(self, test_metadata: PluginMetadata) -> None:
        plugin = ConcreteTestPlugin(test_metadata)

        assert plugin.name == "test - plugin"
        assert plugin.version == "1.0.0"
        assert plugin.plugin_type == PluginType.HOOK
        assert plugin.enabled is True
        assert plugin.metadata == test_metadata

    def test_plugin_enable_disable(self, test_metadata: PluginMetadata) -> None:
        plugin = ConcreteTestPlugin(test_metadata)

        assert plugin.enabled is True

        plugin.disable()
        assert plugin.enabled is False

        plugin.enable()
        assert plugin.enabled is True

    def test_plugin_configuration(self, test_metadata: PluginMetadata) -> None:
        plugin = ConcreteTestPlugin(test_metadata)

        config = {"api_key": "test - key", "timeout": 60}
        plugin.configure(config)

        assert plugin.get_config("api_key") == "test - key"
        assert plugin.get_config("timeout") == 60
        assert plugin.get_config("missing", "default") == "default"

    def test_plugin_config_validation_success(
        self,
        test_metadata: PluginMetadata,
    ) -> None:
        plugin = ConcreteTestPlugin(test_metadata)

        config = {"api_key": "test - key", "timeout": 30}
        plugin.configure(config)

    def test_plugin_config_validation_failure(
        self,
        test_metadata: PluginMetadata,
    ) -> None:
        plugin = ConcreteTestPlugin(test_metadata)

        config = {"timeout": 30}
        with pytest.raises(ValueError, match="Required config key 'api_key' missing"):
            plugin.configure(config)

    def test_plugin_config_validation_no_schema(self) -> None:
        metadata = PluginMetadata(
            name="no - schema",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Plugin without config schema",
        )
        plugin = ConcreteTestPlugin(metadata)

        plugin.configure({"anything": "goes"})

    def test_plugin_get_info(self, test_metadata: PluginMetadata) -> None:
        plugin = ConcreteTestPlugin(test_metadata)
        plugin.configure({"api_key": "test - key"})

        info = plugin.get_info()

        assert "metadata" in info
        assert "enabled" in info
        assert "config" in info
        assert info["enabled"] is True
        assert info["config"]["api_key"] == "test - key"
        assert info["metadata"]["name"] == "test - plugin"


class TestPluginRegistry:
    @pytest.fixture
    def registry(self) -> PluginRegistry:
        return PluginRegistry()

    @pytest.fixture
    def test_plugin(self, test_metadata: PluginMetadata) -> ConcreteTestPlugin:
        return ConcreteTestPlugin(test_metadata)

    def test_registry_initialization(self, registry: PluginRegistry) -> None:
        assert len(registry.list_all()) == 0
        assert len(registry.get_by_type(PluginType.HOOK)) == 0

    def test_plugin_registration(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        result = registry.register(test_plugin)
        assert result is True

        retrieved = registry.get("test - plugin")
        assert retrieved == test_plugin

    def test_duplicate_plugin_registration(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        registry.register(test_plugin)

        result = registry.register(test_plugin)
        assert result is False

    def test_plugin_unregistration(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        registry.register(test_plugin)

        result = registry.unregister("test - plugin")
        assert result is True

        assert registry.get("test - plugin") is None

    def test_plugin_unregistration_not_found(self, registry: PluginRegistry) -> None:
        result = registry.unregister("non - existent")
        assert result is False

    def test_get_by_type(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        hook_plugin = ConcreteTestPlugin(test_metadata)

        formatter_metadata = PluginMetadata(
            name="formatter - plugin",
            version="1.0.0",
            plugin_type=PluginType.FORMATTER,
            description="Formatter plugin",
        )
        formatter_plugin = ConcreteTestPlugin(formatter_metadata)

        registry.register(hook_plugin)
        registry.register(formatter_plugin)

        hook_plugins = registry.get_by_type(PluginType.HOOK)
        formatter_plugins = registry.get_by_type(PluginType.FORMATTER)

        assert len(hook_plugins) == 1
        assert len(formatter_plugins) == 1
        assert hook_plugins[0] == hook_plugin
        assert formatter_plugins[0] == formatter_plugin

    def test_get_enabled_plugins(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        registry.register(test_plugin)

        enabled = registry.get_enabled()
        assert len(enabled) == 1
        assert enabled[0] == test_plugin

        test_plugin.disable()
        enabled = registry.get_enabled()
        assert len(enabled) == 0

    def test_get_enabled_by_type(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        hook_plugin = ConcreteTestPlugin(test_metadata)

        formatter_metadata = PluginMetadata(
            name="formatter - plugin",
            version="1.0.0",
            plugin_type=PluginType.FORMATTER,
            description="Formatter plugin",
        )
        formatter_plugin = ConcreteTestPlugin(formatter_metadata)

        registry.register(hook_plugin)
        registry.register(formatter_plugin)

        hook_plugin.disable()

        enabled_hooks = registry.get_enabled(PluginType.HOOK)
        enabled_formatters = registry.get_enabled(PluginType.FORMATTER)

        assert len(enabled_hooks) == 0
        assert len(enabled_formatters) == 1
        assert enabled_formatters[0] == formatter_plugin

    def test_activate_all(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        plugin1 = ConcreteTestPlugin(test_metadata)

        plugin2_metadata = PluginMetadata(
            name="plugin2",
            version="1.0.0",
            plugin_type=PluginType.FORMATTER,
            description="Second plugin",
        )
        plugin2 = ConcreteTestPlugin(plugin2_metadata)

        registry.register(plugin1)
        registry.register(plugin2)

        results = registry.activate_all()

        assert results["test - plugin"] is True
        assert results["plugin2"] is True
        assert plugin1.activate_called is True
        assert plugin2.activate_called is True

    def test_activate_all_with_disabled(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        test_plugin.disable()
        registry.register(test_plugin)

        results = registry.activate_all()

        assert len(results) == 0
        assert test_plugin.activate_called is False

    def test_activate_all_with_failure(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        failing_plugin = FailingTestPlugin(test_metadata)
        registry.register(failing_plugin)

        results = registry.activate_all()

        assert results["test - plugin"] is False

    def test_activate_all_with_exception(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        exception_plugin = ExceptionTestPlugin(test_metadata)
        registry.register(exception_plugin)

        results = registry.activate_all()

        assert results["test - plugin"] is False

    def test_deactivate_all(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        registry.register(test_plugin)

        results = registry.deactivate_all()

        assert results["test - plugin"] is True
        assert test_plugin.deactivate_called is True

    def test_deactivate_all_with_exception(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        exception_plugin = ExceptionTestPlugin(test_metadata)
        registry.register(exception_plugin)

        results = registry.deactivate_all()

        assert results["test - plugin"] is False

    def test_get_stats(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        hook_plugin = ConcreteTestPlugin(test_metadata)

        formatter_metadata = PluginMetadata(
            name="formatter - plugin",
            version="1.0.0",
            plugin_type=PluginType.FORMATTER,
            description="Formatter plugin",
        )
        formatter_plugin = ConcreteTestPlugin(formatter_metadata)

        registry.register(hook_plugin)
        registry.register(formatter_plugin)

        hook_plugin.disable()

        stats = registry.get_stats()

        assert stats["total_plugins"] == 2
        assert stats["enabled_plugins"] == 1
        assert stats["by_type"]["hook"]["total"] == 1
        assert stats["by_type"]["hook"]["enabled"] == 0
        assert stats["by_type"]["hook"]["disabled"] == 1
        assert stats["by_type"]["formatter"]["total"] == 1
        assert stats["by_type"]["formatter"]["enabled"] == 1
        assert stats["by_type"]["formatter"]["disabled"] == 0


class TestGlobalPluginRegistry:
    def test_get_plugin_registry(self) -> None:
        registry1 = get_plugin_registry()
        registry2 = get_plugin_registry()

        assert registry1 is registry2


class TestCustomHookDefinition:
    def test_hook_definition_creation(self) -> None:
        hook_def = CustomHookDefinition(
            name="test - hook",
            description="Test hook for validation",
            command=["echo", "test"],
            file_patterns=["*.py", "*.js"],
            timeout=120,
            stage=HookStage.FAST,
            requires_files=True,
            parallel_safe=False,
        )

        assert hook_def.name == "test - hook"
        assert hook_def.description == "Test hook for validation"
        assert hook_def.command == ["echo", "test"]
        assert hook_def.file_patterns == ["*.py", "*.js"]
        assert hook_def.timeout == 120
        assert hook_def.stage == HookStage.FAST
        assert hook_def.requires_files is True
        assert hook_def.parallel_safe is False

    def test_hook_definition_defaults(self) -> None:
        hook_def = CustomHookDefinition(
            name="simple - hook",
            description="Simple test hook",
        )

        assert hook_def.command is None
        assert hook_def.file_patterns == []
        assert hook_def.timeout == 60
        assert hook_def.stage == HookStage.COMPREHENSIVE
        assert hook_def.requires_files is True
        assert hook_def.parallel_safe is True

    def test_to_hook_definition(self) -> None:
        hook_def = CustomHookDefinition(
            name="convert - hook",
            description="Hook for conversion test",
            command=["ruff", "check"],
            timeout=90,
            stage=HookStage.FAST,
        )

        hook_definition = hook_def.to_hook_definition()

        assert hook_definition.name == "convert - hook"
        assert hook_definition.command == ["ruff", "check"]
        assert hook_definition.timeout == 90
        assert hook_definition.stage == HookStage.FAST
        assert hook_definition.manual_stage is False

    def test_to_hook_definition_comprehensive(self) -> None:
        hook_def = CustomHookDefinition(
            name="comprehensive - hook",
            description="Comprehensive hook test",
            stage=HookStage.COMPREHENSIVE,
        )

        hook_definition = hook_def.to_hook_definition()

        assert hook_definition.manual_stage is True


class TestCustomHookPlugin:
    @pytest.fixture
    def hook_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="custom - hook - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Custom hook plugin for testing",
        )

    @pytest.fixture
    def hook_definitions(self) -> list[CustomHookDefinition]:
        return [
            CustomHookDefinition(
                name="test - hook - 1",
                description="First test hook",
                command=["echo", "test1"],
                file_patterns=["*.py"],
            ),
            CustomHookDefinition(
                name="test - hook - 2",
                description="Second test hook",
                command=["echo", "test2"],
                file_patterns=["*.js"],
            ),
        ]

    def test_custom_hook_plugin_creation(
        self,
        hook_metadata: PluginMetadata,
        hook_definitions: list[CustomHookDefinition],
    ) -> None:
        plugin = CustomHookPlugin(hook_metadata, hook_definitions)

        assert plugin.name == "custom - hook - plugin"
        assert plugin.plugin_type == PluginType.HOOK

        retrieved_hooks = plugin.get_hook_definitions()
        assert len(retrieved_hooks) == 2
        assert retrieved_hooks[0].name == "test - hook - 1"
        assert retrieved_hooks[1].name == "test - hook - 2"

    def test_should_run_hook_with_patterns(
        self,
        hook_metadata: PluginMetadata,
        hook_definitions: list[CustomHookDefinition],
    ) -> None:
        plugin = CustomHookPlugin(hook_metadata, hook_definitions)

        py_files = [Path("test.py"), Path("module.py")]
        js_files = [Path("app.js"), Path("utils.js")]
        other_files = [Path("readme.txt"), Path("config.yaml")]

        assert plugin.should_run_hook("test - hook - 1", py_files) is True
        assert plugin.should_run_hook("test - hook - 1", js_files) is False
        assert plugin.should_run_hook("test - hook - 1", other_files) is False

        assert plugin.should_run_hook("test - hook - 2", py_files) is False
        assert plugin.should_run_hook("test - hook - 2", js_files) is True
        assert plugin.should_run_hook("test - hook - 2", other_files) is False

    def test_should_run_hook_no_patterns(self, hook_metadata: PluginMetadata) -> None:
        hook_def = CustomHookDefinition(
            name="no - pattern - hook",
            description="Hook without file patterns",
            command=["echo", "test"],
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])

        files = [Path("any.file")]
        assert plugin.should_run_hook("no - pattern - hook", files) is True

        assert plugin.should_run_hook("no - pattern - hook", []) is False

    def test_should_run_hook_no_files_required(
        self,
        hook_metadata: PluginMetadata,
    ) -> None:
        hook_def = CustomHookDefinition(
            name="no - files - hook",
            description="Hook that doesn't require files",
            command=["echo", "test"],
            requires_files=False,
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])

        assert plugin.should_run_hook("no - files - hook", []) is True
        assert plugin.should_run_hook("no - files - hook", [Path("file.py")]) is True

    def test_execute_hook_success(
        self,
        hook_metadata: PluginMetadata,
        mock_console: Console,
    ) -> None:
        hook_def = CustomHookDefinition(
            name="success - hook",
            description="Hook that succeeds",
            command=["echo", "success"],
            timeout=10,
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])
        plugin.initialize(mock_console, Path("/ test"))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="", stdout="success")

            result = plugin.execute_hook("success - hook", [Path("test.py")], Mock())

            assert result.status == "passed"
            assert result.name == "success - hook"
            assert result.issues_found == []
            mock_run.assert_called_once()

    def test_execute_hook_failure(
        self,
        hook_metadata: PluginMetadata,
        mock_console: Console,
    ) -> None:
        hook_def = CustomHookDefinition(
            name="fail - hook",
            description="Hook that fails",
            command=["false"],
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])
        plugin.initialize(mock_console, Path("/ test"))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stderr="Error occurred",
                stdout="",
            )

            result = plugin.execute_hook("fail - hook", [], Mock())

            assert result.status == "failed"
            assert result.name == "fail - hook"
            assert result.issues_found == ["Error occurred"]

    def test_execute_hook_timeout(
        self,
        hook_metadata: PluginMetadata,
        mock_console: Console,
    ) -> None:
        hook_def = CustomHookDefinition(
            name="timeout - hook",
            description="Hook that times out",
            command=["sleep", "100"],
            timeout=1,
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])
        plugin.initialize(mock_console, Path("/ test"))

        with patch("subprocess.run") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired("sleep", 1)

            result = plugin.execute_hook("timeout - hook", [], Mock())

            assert result.status == "timeout"
            assert "timed out" in result.issues_found[0]

    def test_execute_hook_exception(
        self,
        hook_metadata: PluginMetadata,
        mock_console: Console,
    ) -> None:
        hook_def = CustomHookDefinition(
            name="exception - hook",
            description="Hook that raises exception",
            command=["invalid - command"],
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])
        plugin.initialize(mock_console, Path("/ test"))

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("Command not found")

            result = plugin.execute_hook("exception - hook", [], Mock())

            assert result.status == "error"
            assert "Execution error" in result.issues_found[0]

    def test_execute_hook_not_found(self, hook_metadata: PluginMetadata) -> None:
        plugin = CustomHookPlugin(hook_metadata, [])

        result = plugin.execute_hook("non - existent", [], Mock())

        assert result.status == "error"
        assert "Hook definition not found" in result.issues_found[0]

    def test_execute_hook_no_command(self, hook_metadata: PluginMetadata) -> None:
        hook_def = CustomHookDefinition(
            name="no - command - hook",
            description="Hook without command",
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])

        result = plugin.execute_hook("no - command - hook", [], Mock())

        assert result.status == "error"
        assert "No command defined" in result.issues_found[0]

    def test_activate_deactivate(self, hook_metadata: PluginMetadata) -> None:
        plugin = CustomHookPlugin(hook_metadata, [])

        assert plugin.activate() is True
        assert plugin.deactivate() is True


class TestHookPluginRegistry:
    @pytest.fixture
    def hook_registry(self) -> HookPluginRegistry:
        return HookPluginRegistry()

    @pytest.fixture
    def test_hook_plugin(self) -> CustomHookPlugin:
        metadata = PluginMetadata(
            name="test - hook - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Test hook plugin",
        )
        hook_def = CustomHookDefinition(
            name="test - hook",
            description="Test hook",
            command=["echo", "test"],
        )
        return CustomHookPlugin(metadata, [hook_def])

    def test_register_hook_plugin(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        result = hook_registry.register_hook_plugin(test_hook_plugin)
        assert result is True

    def test_register_duplicate_hook_plugin(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        hook_registry.register_hook_plugin(test_hook_plugin)

        result = hook_registry.register_hook_plugin(test_hook_plugin)
        assert result is False

    def test_unregister_hook_plugin(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        hook_registry.register_hook_plugin(test_hook_plugin)

        result = hook_registry.unregister_hook_plugin("test - hook - plugin")
        assert result is True

        result = hook_registry.unregister_hook_plugin("non - existent")
        assert result is False

    def test_get_all_custom_hooks(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        hook_registry.register_hook_plugin(test_hook_plugin)

        hooks = hook_registry.get_all_custom_hooks()

        assert "test - hook" in hooks
        assert hooks["test - hook"].name == "test - hook"

    def test_get_all_custom_hooks_disabled(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        test_hook_plugin.disable()
        hook_registry.register_hook_plugin(test_hook_plugin)

        hooks = hook_registry.get_all_custom_hooks()

        assert len(hooks) == 0

    def test_execute_custom_hook(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
        mock_options: OptionsProtocol,
    ) -> None:
        hook_registry.register_hook_plugin(test_hook_plugin)

        with patch.object(test_hook_plugin, "execute_hook") as mock_execute:
            mock_execute.return_value = HookResult(
                id="test - hook",
                name="test - hook",
                status="passed",
                duration=1.0,
                issues_found=[],
            )

            result = hook_registry.execute_custom_hook(
                "test - hook",
                [Path("test.py")],
                mock_options,
            )

            assert result is not None
            assert result.status == "passed"
            mock_execute.assert_called_once()

    def test_execute_custom_hook_not_found(
        self,
        hook_registry: HookPluginRegistry,
        mock_options: OptionsProtocol,
    ) -> None:
        result = hook_registry.execute_custom_hook("non - existent", [], mock_options)
        assert result is None

    def test_get_hooks_for_files(self, hook_registry: HookPluginRegistry) -> None:
        metadata = PluginMetadata(
            name="multi - hook - plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Plugin with multiple hooks",
        )

        hook_defs = [
            CustomHookDefinition(
                name="python - hook",
                description="Python hook",
                command=["python", "- m", "flake8"],
                file_patterns=["*.py"],
            ),
            CustomHookDefinition(
                name="javascript - hook",
                description="JavaScript hook",
                command=["eslint"],
                file_patterns=["*.js"],
            ),
            CustomHookDefinition(
                name="general - hook",
                description="General hook",
                command=["echo", "general"],
                requires_files=False,
            ),
        ]

        plugin = CustomHookPlugin(metadata, hook_defs)
        hook_registry.register_hook_plugin(plugin)

        py_files = [Path("test.py")]
        js_files = [Path("app.js")]

        py_hooks = hook_registry.get_hooks_for_files(py_files)
        js_hooks = hook_registry.get_hooks_for_files(js_files)

        assert "python - hook" in py_hooks
        assert "general - hook" in py_hooks
        assert "javascript - hook" not in py_hooks

        assert "javascript - hook" in js_hooks
        assert "general - hook" in js_hooks
        assert "python - hook" not in js_hooks

    def test_initialize_all_plugins(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
        mock_console: Console,
    ) -> None:
        hook_registry.register_hook_plugin(test_hook_plugin)

        with patch.object(test_hook_plugin, "initialize") as mock_init:
            hook_registry.initialize_all_plugins(mock_console, Path("/ test"))
            mock_init.assert_called_once_with(mock_console, Path("/ test"))


class TestGlobalHookRegistry:
    def test_get_hook_plugin_registry(self) -> None:
        registry1 = get_hook_plugin_registry()
        registry2 = get_hook_plugin_registry()

        assert registry1 is registry2


class TestPluginLoader:
    @pytest.fixture
    def loader(self) -> PluginLoader:
        registry = PluginRegistry()
        return PluginLoader(registry)

    def test_loader_initialization(self, loader: PluginLoader) -> None:
        assert loader.registry is not None
        assert loader.logger is not None

    def test_load_plugin_from_file_not_found(self, loader: PluginLoader) -> None:
        with pytest.raises(PluginLoadError, match="Plugin file not found"):
            loader.load_plugin_from_file(Path("/ non / existent / plugin.py"))

    def test_load_plugin_from_file_wrong_extension(self, loader: PluginLoader) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with pytest.raises(PluginLoadError, match="Plugin file must be .py"):
                loader.load_plugin_from_file(tmp_path)
        finally:
            tmp_path.unlink()

    def test_load_plugin_from_file_valid_plugin(self, loader: PluginLoader) -> None:
        plugin_code = """
from crackerjack.plugins.base import PluginBase, PluginMetadata, PluginType

class TestFilePlugin(PluginBase):
    def activate(self):
        return True

    def deactivate(self):
        return True

metadata = PluginMetadata(
    name ="file - plugin",
    version ="1.0.0",
    plugin_type = PluginType.HOOK,
    description ="Plugin loaded from file"
)

plugin = TestFilePlugin(metadata)

invalid python syntax here < <<

from crackerjack.plugins.base import PluginBase, PluginMetadata, PluginType

class RegisterPlugin(PluginBase):
    def activate(self):
        return True

    def deactivate(self):
        return True

metadata = PluginMetadata(
    name ="register - plugin",
    version ="1.0.0",
    plugin_type = PluginType.HOOK,
    description ="Plugin for registration test"
)

plugin = RegisterPlugin(metadata)

from crackerjack.plugins.base import PluginBase, PluginMetadata, PluginType

class InstallPlugin(PluginBase):
    def activate(self):
        return True

    def deactivate(self):
        return True

metadata = PluginMetadata(
    name ="install - plugin",
    version ="1.0.0",
    plugin_type = PluginType.HOOK,
    description ="Plugin for installation test"
)

plugin = InstallPlugin(metadata)
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(plugin_code)
            tmp_path = Path(tmp.name)

        try:
            result = plugin_manager.install_plugin_from_file(tmp_path)
            assert result is True
        finally:
            tmp_path.unlink()

    def test_get_available_custom_hooks(self, plugin_manager: PluginManager) -> None:
        with patch.object(
            plugin_manager.hook_registry,
            "get_all_custom_hooks",
        ) as mock_get_hooks:
            mock_get_hooks.return_value = {"hook1": Mock(), "hook2": Mock()}

            hooks = plugin_manager.get_available_custom_hooks()
            assert hooks == ["hook1", "hook2"]

    def test_execute_custom_hook(
        self,
        plugin_manager: PluginManager,
        mock_options: OptionsProtocol,
    ) -> None:
        files = [Path("test.py")]

        with patch.object(
            plugin_manager.hook_registry,
            "execute_custom_hook",
        ) as mock_execute:
            mock_execute.return_value = Mock()

            result = plugin_manager.execute_custom_hook(
                "test - hook",
                files,
                mock_options,
            )

            mock_execute.assert_called_once_with("test - hook", files, mock_options)
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__])
