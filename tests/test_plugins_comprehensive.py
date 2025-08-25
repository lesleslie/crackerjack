"""Comprehensive test coverage for the plugin system modules.

This test suite provides comprehensive coverage for:
- crackerjack/plugins/base.py - Base plugin classes
- crackerjack/plugins/loader.py - Plugin loading mechanism
- crackerjack/plugins/managers.py - Plugin management
- crackerjack/plugins/hooks.py - Hook integration

Focus on testing plugin discovery, loading, lifecycle management, hook integration,
error handling, configuration validation, and plugin manager functionality.
"""

import json
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
from crackerjack.plugins.loader import PluginDiscovery, PluginLoader, PluginLoadError
from crackerjack.plugins.managers import PluginManager


class ConcreteTestPlugin(PluginBase):
    """Concrete test plugin for testing abstract base class."""

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
    """Test plugin that simulates activation/deactivation failures."""

    def activate(self) -> bool:
        return False

    def deactivate(self) -> bool:
        return False


class ExceptionTestPlugin(PluginBase):
    """Test plugin that raises exceptions during activation/deactivation."""

    def activate(self) -> bool:
        msg = "Activation failed"
        raise RuntimeError(msg)

    def deactivate(self) -> bool:
        msg = "Deactivation failed"
        raise RuntimeError(msg)


@pytest.fixture
def test_metadata() -> PluginMetadata:
    """Create test plugin metadata."""
    return PluginMetadata(
        name="test-plugin",
        version="1.0.0",
        plugin_type=PluginType.HOOK,
        description="Test plugin for unit tests",
        author="Test Author",
        license="MIT",
        requires_python=">=3.11",
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
    """Mock OptionsProtocol for testing."""
    options = Mock(spec=OptionsProtocol)
    options.verbose = False
    options.dry_run = False
    return options


@pytest.fixture
def mock_console() -> Console:
    """Mock Console for testing."""
    return Mock(spec=Console)


class TestPluginMetadata:
    """Test PluginMetadata dataclass."""

    def test_metadata_creation(self, test_metadata: PluginMetadata) -> None:
        """Test metadata creation with all fields."""
        assert test_metadata.name == "test-plugin"
        assert test_metadata.version == "1.0.0"
        assert test_metadata.plugin_type == PluginType.HOOK
        assert test_metadata.description == "Test plugin for unit tests"
        assert test_metadata.author == "Test Author"
        assert test_metadata.license == "MIT"
        assert test_metadata.requires_python == ">=3.11"
        assert test_metadata.dependencies == ["pytest", "mock"]
        assert test_metadata.entry_point == "test_plugin.create_plugin"
        assert "required" in test_metadata.config_schema

    def test_metadata_defaults(self) -> None:
        """Test metadata creation with default values."""
        metadata = PluginMetadata(
            name="simple-plugin",
            version="1.0.0",
            plugin_type=PluginType.FORMATTER,
            description="Simple test plugin",
        )
        assert metadata.author == ""
        assert metadata.license == ""
        assert metadata.requires_python == ">=3.11"
        assert metadata.dependencies == []
        assert metadata.entry_point == ""
        assert metadata.config_schema == {}

    def test_metadata_to_dict(self, test_metadata: PluginMetadata) -> None:
        """Test metadata serialization to dictionary."""
        data = test_metadata.to_dict()

        assert data["name"] == "test-plugin"
        assert data["version"] == "1.0.0"
        assert data["plugin_type"] == "hook"  # Enum value
        assert data["description"] == "Test plugin for unit tests"
        assert data["author"] == "Test Author"
        assert data["license"] == "MIT"
        assert data["requires_python"] == ">=3.11"
        assert data["dependencies"] == ["pytest", "mock"]
        assert data["entry_point"] == "test_plugin.create_plugin"
        assert "required" in data["config_schema"]


class TestPluginType:
    """Test PluginType enum."""

    def test_plugin_types(self) -> None:
        """Test all plugin type values."""
        assert PluginType.HOOK.value == "hook"
        assert PluginType.WORKFLOW.value == "workflow"
        assert PluginType.INTEGRATION.value == "integration"
        assert PluginType.FORMATTER.value == "formatter"
        assert PluginType.ANALYZER.value == "analyzer"
        assert PluginType.PUBLISHER.value == "publisher"

    def test_plugin_type_from_string(self) -> None:
        """Test creating plugin type from string."""
        assert PluginType("hook") == PluginType.HOOK
        assert PluginType("workflow") == PluginType.WORKFLOW
        assert PluginType("integration") == PluginType.INTEGRATION


class TestPluginBase:
    """Test PluginBase abstract class."""

    def test_plugin_base_is_abstract(self, test_metadata: PluginMetadata) -> None:
        """Test that PluginBase cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PluginBase(test_metadata)

    def test_concrete_plugin_properties(self, test_metadata: PluginMetadata) -> None:
        """Test concrete plugin properties."""
        plugin = ConcreteTestPlugin(test_metadata)

        assert plugin.name == "test-plugin"
        assert plugin.version == "1.0.0"
        assert plugin.plugin_type == PluginType.HOOK
        assert plugin.enabled is True
        assert plugin.metadata == test_metadata

    def test_plugin_enable_disable(self, test_metadata: PluginMetadata) -> None:
        """Test plugin enable/disable functionality."""
        plugin = ConcreteTestPlugin(test_metadata)

        assert plugin.enabled is True

        plugin.disable()
        assert plugin.enabled is False

        plugin.enable()
        assert plugin.enabled is True

    def test_plugin_configuration(self, test_metadata: PluginMetadata) -> None:
        """Test plugin configuration functionality."""
        plugin = ConcreteTestPlugin(test_metadata)

        config = {"api_key": "test-key", "timeout": 60}
        plugin.configure(config)

        assert plugin.get_config("api_key") == "test-key"
        assert plugin.get_config("timeout") == 60
        assert plugin.get_config("missing", "default") == "default"

    def test_plugin_config_validation_success(
        self,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test successful config validation."""
        plugin = ConcreteTestPlugin(test_metadata)

        # Valid config with required keys
        config = {"api_key": "test-key", "timeout": 30}
        plugin.configure(config)  # Should not raise

    def test_plugin_config_validation_failure(
        self,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test config validation failure."""
        plugin = ConcreteTestPlugin(test_metadata)

        # Missing required key
        config = {"timeout": 30}
        with pytest.raises(ValueError, match="Required config key 'api_key' missing"):
            plugin.configure(config)

    def test_plugin_config_validation_no_schema(self) -> None:
        """Test config validation with no schema."""
        metadata = PluginMetadata(
            name="no-schema",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Plugin without config schema",
        )
        plugin = ConcreteTestPlugin(metadata)

        # Should not raise even with arbitrary config
        plugin.configure({"anything": "goes"})

    def test_plugin_get_info(self, test_metadata: PluginMetadata) -> None:
        """Test plugin info generation."""
        plugin = ConcreteTestPlugin(test_metadata)
        plugin.configure({"api_key": "test-key"})

        info = plugin.get_info()

        assert "metadata" in info
        assert "enabled" in info
        assert "config" in info
        assert info["enabled"] is True
        assert info["config"]["api_key"] == "test-key"
        assert info["metadata"]["name"] == "test-plugin"


class TestPluginRegistry:
    """Test PluginRegistry functionality."""

    @pytest.fixture
    def registry(self) -> PluginRegistry:
        """Create fresh plugin registry for each test."""
        return PluginRegistry()

    @pytest.fixture
    def test_plugin(self, test_metadata: PluginMetadata) -> ConcreteTestPlugin:
        """Create test plugin instance."""
        return ConcreteTestPlugin(test_metadata)

    def test_registry_initialization(self, registry: PluginRegistry) -> None:
        """Test registry initialization."""
        assert len(registry.list_all()) == 0
        assert len(registry.get_by_type(PluginType.HOOK)) == 0

    def test_plugin_registration(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        """Test plugin registration."""
        result = registry.register(test_plugin)
        assert result is True

        retrieved = registry.get("test-plugin")
        assert retrieved == test_plugin

    def test_duplicate_plugin_registration(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        """Test duplicate plugin registration prevention."""
        registry.register(test_plugin)

        # Try to register again
        result = registry.register(test_plugin)
        assert result is False

    def test_plugin_unregistration(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        """Test plugin unregistration."""
        registry.register(test_plugin)

        result = registry.unregister("test-plugin")
        assert result is True

        assert registry.get("test-plugin") is None

    def test_plugin_unregistration_not_found(self, registry: PluginRegistry) -> None:
        """Test unregistering non-existent plugin."""
        result = registry.unregister("non-existent")
        assert result is False

    def test_get_by_type(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test getting plugins by type."""
        hook_plugin = ConcreteTestPlugin(test_metadata)

        formatter_metadata = PluginMetadata(
            name="formatter-plugin",
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
        """Test getting enabled plugins."""
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
        """Test getting enabled plugins by type."""
        hook_plugin = ConcreteTestPlugin(test_metadata)

        formatter_metadata = PluginMetadata(
            name="formatter-plugin",
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
        """Test activating all plugins."""
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

        assert results["test-plugin"] is True
        assert results["plugin2"] is True
        assert plugin1.activate_called is True
        assert plugin2.activate_called is True

    def test_activate_all_with_disabled(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        """Test activate_all skips disabled plugins."""
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
        """Test activate_all handles failures."""
        failing_plugin = FailingTestPlugin(test_metadata)
        registry.register(failing_plugin)

        results = registry.activate_all()

        assert results["test-plugin"] is False

    def test_activate_all_with_exception(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test activate_all handles exceptions."""
        exception_plugin = ExceptionTestPlugin(test_metadata)
        registry.register(exception_plugin)

        results = registry.activate_all()

        assert results["test-plugin"] is False

    def test_deactivate_all(
        self,
        registry: PluginRegistry,
        test_plugin: ConcreteTestPlugin,
    ) -> None:
        """Test deactivating all plugins."""
        registry.register(test_plugin)

        results = registry.deactivate_all()

        assert results["test-plugin"] is True
        assert test_plugin.deactivate_called is True

    def test_deactivate_all_with_exception(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test deactivate_all handles exceptions."""
        exception_plugin = ExceptionTestPlugin(test_metadata)
        registry.register(exception_plugin)

        results = registry.deactivate_all()

        assert results["test-plugin"] is False

    def test_get_stats(
        self,
        registry: PluginRegistry,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test registry statistics."""
        hook_plugin = ConcreteTestPlugin(test_metadata)

        formatter_metadata = PluginMetadata(
            name="formatter-plugin",
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
    """Test global plugin registry functions."""

    def test_get_plugin_registry(self) -> None:
        """Test global registry access."""
        registry1 = get_plugin_registry()
        registry2 = get_plugin_registry()

        # Should return same instance
        assert registry1 is registry2


class TestCustomHookDefinition:
    """Test CustomHookDefinition functionality."""

    def test_hook_definition_creation(self) -> None:
        """Test hook definition creation."""
        hook_def = CustomHookDefinition(
            name="test-hook",
            description="Test hook for validation",
            command=["echo", "test"],
            file_patterns=["*.py", "*.js"],
            timeout=120,
            stage=HookStage.FAST,
            requires_files=True,
            parallel_safe=False,
        )

        assert hook_def.name == "test-hook"
        assert hook_def.description == "Test hook for validation"
        assert hook_def.command == ["echo", "test"]
        assert hook_def.file_patterns == ["*.py", "*.js"]
        assert hook_def.timeout == 120
        assert hook_def.stage == HookStage.FAST
        assert hook_def.requires_files is True
        assert hook_def.parallel_safe is False

    def test_hook_definition_defaults(self) -> None:
        """Test hook definition with default values."""
        hook_def = CustomHookDefinition(
            name="simple-hook",
            description="Simple test hook",
        )

        assert hook_def.command is None
        assert hook_def.file_patterns == []
        assert hook_def.timeout == 60
        assert hook_def.stage == HookStage.COMPREHENSIVE
        assert hook_def.requires_files is True
        assert hook_def.parallel_safe is True

    def test_to_hook_definition(self) -> None:
        """Test conversion to HookDefinition."""
        hook_def = CustomHookDefinition(
            name="convert-hook",
            description="Hook for conversion test",
            command=["ruff", "check"],
            timeout=90,
            stage=HookStage.FAST,
        )

        hook_definition = hook_def.to_hook_definition()

        assert hook_definition.name == "convert-hook"
        assert hook_definition.command == ["ruff", "check"]
        assert hook_definition.timeout == 90
        assert hook_definition.stage == HookStage.FAST
        assert hook_definition.manual_stage is False  # Because stage is FAST

    def test_to_hook_definition_comprehensive(self) -> None:
        """Test conversion with comprehensive stage."""
        hook_def = CustomHookDefinition(
            name="comprehensive-hook",
            description="Comprehensive hook test",
            stage=HookStage.COMPREHENSIVE,
        )

        hook_definition = hook_def.to_hook_definition()

        assert hook_definition.manual_stage is True  # Because stage is COMPREHENSIVE


class TestCustomHookPlugin:
    """Test CustomHookPlugin functionality."""

    @pytest.fixture
    def hook_metadata(self) -> PluginMetadata:
        """Create hook plugin metadata."""
        return PluginMetadata(
            name="custom-hook-plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Custom hook plugin for testing",
        )

    @pytest.fixture
    def hook_definitions(self) -> list[CustomHookDefinition]:
        """Create test hook definitions."""
        return [
            CustomHookDefinition(
                name="test-hook-1",
                description="First test hook",
                command=["echo", "test1"],
                file_patterns=["*.py"],
            ),
            CustomHookDefinition(
                name="test-hook-2",
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
        """Test custom hook plugin creation."""
        plugin = CustomHookPlugin(hook_metadata, hook_definitions)

        assert plugin.name == "custom-hook-plugin"
        assert plugin.plugin_type == PluginType.HOOK

        retrieved_hooks = plugin.get_hook_definitions()
        assert len(retrieved_hooks) == 2
        assert retrieved_hooks[0].name == "test-hook-1"
        assert retrieved_hooks[1].name == "test-hook-2"

    def test_should_run_hook_with_patterns(
        self,
        hook_metadata: PluginMetadata,
        hook_definitions: list[CustomHookDefinition],
    ) -> None:
        """Test hook execution conditions with file patterns."""
        plugin = CustomHookPlugin(hook_metadata, hook_definitions)

        py_files = [Path("test.py"), Path("module.py")]
        js_files = [Path("app.js"), Path("utils.js")]
        other_files = [Path("readme.txt"), Path("config.yaml")]

        # test-hook-1 should run for Python files
        assert plugin.should_run_hook("test-hook-1", py_files) is True
        assert plugin.should_run_hook("test-hook-1", js_files) is False
        assert plugin.should_run_hook("test-hook-1", other_files) is False

        # test-hook-2 should run for JavaScript files
        assert plugin.should_run_hook("test-hook-2", py_files) is False
        assert plugin.should_run_hook("test-hook-2", js_files) is True
        assert plugin.should_run_hook("test-hook-2", other_files) is False

    def test_should_run_hook_no_patterns(self, hook_metadata: PluginMetadata) -> None:
        """Test hook execution with no file patterns."""
        hook_def = CustomHookDefinition(
            name="no-pattern-hook",
            description="Hook without file patterns",
            command=["echo", "test"],
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])

        files = [Path("any.file")]
        assert plugin.should_run_hook("no-pattern-hook", files) is True

        # Should still require files if requires_files is True
        assert plugin.should_run_hook("no-pattern-hook", []) is False

    def test_should_run_hook_no_files_required(
        self,
        hook_metadata: PluginMetadata,
    ) -> None:
        """Test hook execution when no files are required."""
        hook_def = CustomHookDefinition(
            name="no-files-hook",
            description="Hook that doesn't require files",
            command=["echo", "test"],
            requires_files=False,
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])

        assert plugin.should_run_hook("no-files-hook", []) is True
        assert plugin.should_run_hook("no-files-hook", [Path("file.py")]) is True

    def test_execute_hook_success(
        self,
        hook_metadata: PluginMetadata,
        mock_console: Console,
    ) -> None:
        """Test successful hook execution."""
        hook_def = CustomHookDefinition(
            name="success-hook",
            description="Hook that succeeds",
            command=["echo", "success"],
            timeout=10,
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])
        plugin.initialize(mock_console, Path("/test"))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="", stdout="success")

            result = plugin.execute_hook("success-hook", [Path("test.py")], Mock())

            assert result.status == "passed"
            assert result.name == "success-hook"
            assert result.issues_found == []
            mock_run.assert_called_once()

    def test_execute_hook_failure(
        self,
        hook_metadata: PluginMetadata,
        mock_console: Console,
    ) -> None:
        """Test failed hook execution."""
        hook_def = CustomHookDefinition(
            name="fail-hook",
            description="Hook that fails",
            command=["false"],
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])
        plugin.initialize(mock_console, Path("/test"))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stderr="Error occurred",
                stdout="",
            )

            result = plugin.execute_hook("fail-hook", [], Mock())

            assert result.status == "failed"
            assert result.name == "fail-hook"
            assert result.issues_found == ["Error occurred"]

    def test_execute_hook_timeout(
        self,
        hook_metadata: PluginMetadata,
        mock_console: Console,
    ) -> None:
        """Test hook execution timeout."""
        hook_def = CustomHookDefinition(
            name="timeout-hook",
            description="Hook that times out",
            command=["sleep", "100"],
            timeout=1,
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])
        plugin.initialize(mock_console, Path("/test"))

        with patch("subprocess.run") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired("sleep", 1)

            result = plugin.execute_hook("timeout-hook", [], Mock())

            assert result.status == "timeout"
            assert "timed out" in result.issues_found[0]

    def test_execute_hook_exception(
        self,
        hook_metadata: PluginMetadata,
        mock_console: Console,
    ) -> None:
        """Test hook execution with exception."""
        hook_def = CustomHookDefinition(
            name="exception-hook",
            description="Hook that raises exception",
            command=["invalid-command"],
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])
        plugin.initialize(mock_console, Path("/test"))

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("Command not found")

            result = plugin.execute_hook("exception-hook", [], Mock())

            assert result.status == "error"
            assert "Execution error" in result.issues_found[0]

    def test_execute_hook_not_found(self, hook_metadata: PluginMetadata) -> None:
        """Test executing non-existent hook."""
        plugin = CustomHookPlugin(hook_metadata, [])

        result = plugin.execute_hook("non-existent", [], Mock())

        assert result.status == "error"
        assert "Hook definition not found" in result.issues_found[0]

    def test_execute_hook_no_command(self, hook_metadata: PluginMetadata) -> None:
        """Test executing hook with no command."""
        hook_def = CustomHookDefinition(
            name="no-command-hook",
            description="Hook without command",
        )
        plugin = CustomHookPlugin(hook_metadata, [hook_def])

        result = plugin.execute_hook("no-command-hook", [], Mock())

        assert result.status == "error"
        assert "No command defined" in result.issues_found[0]

    def test_activate_deactivate(self, hook_metadata: PluginMetadata) -> None:
        """Test plugin activation and deactivation."""
        plugin = CustomHookPlugin(hook_metadata, [])

        assert plugin.activate() is True
        assert plugin.deactivate() is True


class TestHookPluginRegistry:
    """Test HookPluginRegistry functionality."""

    @pytest.fixture
    def hook_registry(self) -> HookPluginRegistry:
        """Create fresh hook registry for each test."""
        return HookPluginRegistry()

    @pytest.fixture
    def test_hook_plugin(self) -> CustomHookPlugin:
        """Create test hook plugin."""
        metadata = PluginMetadata(
            name="test-hook-plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Test hook plugin",
        )
        hook_def = CustomHookDefinition(
            name="test-hook",
            description="Test hook",
            command=["echo", "test"],
        )
        return CustomHookPlugin(metadata, [hook_def])

    def test_register_hook_plugin(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        """Test registering hook plugin."""
        result = hook_registry.register_hook_plugin(test_hook_plugin)
        assert result is True

    def test_register_duplicate_hook_plugin(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        """Test registering duplicate hook plugin."""
        hook_registry.register_hook_plugin(test_hook_plugin)

        result = hook_registry.register_hook_plugin(test_hook_plugin)
        assert result is False

    def test_unregister_hook_plugin(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        """Test unregistering hook plugin."""
        hook_registry.register_hook_plugin(test_hook_plugin)

        result = hook_registry.unregister_hook_plugin("test-hook-plugin")
        assert result is True

        result = hook_registry.unregister_hook_plugin("non-existent")
        assert result is False

    def test_get_all_custom_hooks(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        """Test getting all custom hooks."""
        hook_registry.register_hook_plugin(test_hook_plugin)

        hooks = hook_registry.get_all_custom_hooks()

        assert "test-hook" in hooks
        assert hooks["test-hook"].name == "test-hook"

    def test_get_all_custom_hooks_disabled(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
    ) -> None:
        """Test getting custom hooks skips disabled plugins."""
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
        """Test executing custom hook."""
        hook_registry.register_hook_plugin(test_hook_plugin)

        with patch.object(test_hook_plugin, "execute_hook") as mock_execute:
            mock_execute.return_value = HookResult(
                id="test-hook",
                name="test-hook",
                status="passed",
                duration=1.0,
                issues_found=[],
            )

            result = hook_registry.execute_custom_hook(
                "test-hook",
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
        """Test executing non-existent custom hook."""
        result = hook_registry.execute_custom_hook("non-existent", [], mock_options)
        assert result is None

    def test_get_hooks_for_files(self, hook_registry: HookPluginRegistry) -> None:
        """Test getting applicable hooks for files."""
        metadata = PluginMetadata(
            name="multi-hook-plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Plugin with multiple hooks",
        )

        hook_defs = [
            CustomHookDefinition(
                name="python-hook",
                description="Python hook",
                command=["python", "-m", "flake8"],
                file_patterns=["*.py"],
            ),
            CustomHookDefinition(
                name="javascript-hook",
                description="JavaScript hook",
                command=["eslint"],
                file_patterns=["*.js"],
            ),
            CustomHookDefinition(
                name="general-hook",
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

        assert "python-hook" in py_hooks
        assert "general-hook" in py_hooks
        assert "javascript-hook" not in py_hooks

        assert "javascript-hook" in js_hooks
        assert "general-hook" in js_hooks
        assert "python-hook" not in js_hooks

    def test_initialize_all_plugins(
        self,
        hook_registry: HookPluginRegistry,
        test_hook_plugin: CustomHookPlugin,
        mock_console: Console,
    ) -> None:
        """Test initializing all plugins."""
        hook_registry.register_hook_plugin(test_hook_plugin)

        with patch.object(test_hook_plugin, "initialize") as mock_init:
            hook_registry.initialize_all_plugins(mock_console, Path("/test"))
            mock_init.assert_called_once_with(mock_console, Path("/test"))


class TestGlobalHookRegistry:
    """Test global hook registry functions."""

    def test_get_hook_plugin_registry(self) -> None:
        """Test global hook registry access."""
        registry1 = get_hook_plugin_registry()
        registry2 = get_hook_plugin_registry()

        # Should return same instance
        assert registry1 is registry2


class TestPluginLoader:
    """Test PluginLoader functionality."""

    @pytest.fixture
    def loader(self) -> PluginLoader:
        """Create plugin loader for testing."""
        registry = PluginRegistry()
        return PluginLoader(registry)

    def test_loader_initialization(self, loader: PluginLoader) -> None:
        """Test loader initialization."""
        assert loader.registry is not None
        assert loader.logger is not None

    def test_load_plugin_from_file_not_found(self, loader: PluginLoader) -> None:
        """Test loading from non-existent file."""
        with pytest.raises(PluginLoadError, match="Plugin file not found"):
            loader.load_plugin_from_file(Path("/non/existent/plugin.py"))

    def test_load_plugin_from_file_wrong_extension(self, loader: PluginLoader) -> None:
        """Test loading from file with wrong extension."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with pytest.raises(PluginLoadError, match="Plugin file must be .py"):
                loader.load_plugin_from_file(tmp_path)
        finally:
            tmp_path.unlink()

    def test_load_plugin_from_file_valid_plugin(self, loader: PluginLoader) -> None:
        """Test loading valid plugin from file."""
        plugin_code = """
from crackerjack.plugins.base import PluginBase, PluginMetadata, PluginType

class TestFilePlugin(PluginBase):
    def activate(self):
        return True

    def deactivate(self):
        return True

metadata = PluginMetadata(
    name="file-plugin",
    version="1.0.0",
    plugin_type=PluginType.HOOK,
    description="Plugin loaded from file"
)

plugin = TestFilePlugin(metadata)
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(plugin_code)
            tmp_path = Path(tmp.name)

        try:
            plugin = loader.load_plugin_from_file(tmp_path)
            assert plugin.name == "file-plugin"
            assert plugin.version == "1.0.0"
        finally:
            tmp_path.unlink()

    def test_load_plugin_from_file_syntax_error(self, loader: PluginLoader) -> None:
        """Test loading plugin with syntax error."""
        plugin_code = """
invalid python syntax here <<<
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(plugin_code)
            tmp_path = Path(tmp.name)

        try:
            with pytest.raises(
                PluginLoadError,
                match="Failed to execute plugin module",
            ):
                loader.load_plugin_from_file(tmp_path)
        finally:
            tmp_path.unlink()

    def test_load_plugin_from_config_json(self, loader: PluginLoader) -> None:
        """Test loading plugin from JSON config."""
        config = {
            "name": "json-plugin",
            "version": "1.0.0",
            "type": "hook",
            "description": "Plugin from JSON config",
            "hooks": [
                {
                    "name": "json-hook",
                    "description": "Hook from JSON",
                    "command": ["echo", "json"],
                    "stage": "comprehensive",  # Use valid HookStage value
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(config, tmp)
            tmp_path = Path(tmp.name)

        try:
            # Fix the missing import by patching the module import
            with patch("crackerjack.plugins.loader.HookStage", HookStage):
                plugin = loader.load_plugin_from_config(tmp_path)
                assert plugin.name == "json-plugin"
                assert isinstance(plugin, CustomHookPlugin)
        finally:
            tmp_path.unlink()

    def test_load_plugin_from_config_not_found(self, loader: PluginLoader) -> None:
        """Test loading from non-existent config file."""
        with pytest.raises(PluginLoadError, match="Plugin config file not found"):
            loader.load_plugin_from_config(Path("/non/existent/config.json"))

    def test_load_plugin_from_config_invalid_json(self, loader: PluginLoader) -> None:
        """Test loading from invalid JSON config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write("invalid json {{{")
            tmp_path = Path(tmp.name)

        try:
            with pytest.raises(PluginLoadError, match="Failed to parse config file"):
                loader.load_plugin_from_config(tmp_path)
        finally:
            tmp_path.unlink()

    def test_load_plugin_from_config_unsupported_format(
        self,
        loader: PluginLoader,
    ) -> None:
        """Test loading from unsupported config format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as tmp:
            tmp.write("<config></config>")
            tmp_path = Path(tmp.name)

        try:
            with pytest.raises(PluginLoadError, match="Unsupported config format"):
                loader.load_plugin_from_config(tmp_path)
        finally:
            tmp_path.unlink()

    def test_load_and_register_python_file(self, loader: PluginLoader) -> None:
        """Test load and register from Python file."""
        plugin_code = """
from crackerjack.plugins.base import PluginBase, PluginMetadata, PluginType

class RegisterPlugin(PluginBase):
    def activate(self):
        return True

    def deactivate(self):
        return True

metadata = PluginMetadata(
    name="register-plugin",
    version="1.0.0",
    plugin_type=PluginType.HOOK,
    description="Plugin for registration test"
)

plugin = RegisterPlugin(metadata)
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(plugin_code)
            tmp_path = Path(tmp.name)

        try:
            result = loader.load_and_register(tmp_path)
            assert result is True

            # Check if plugin was registered
            registered_plugin = loader.registry.get("register-plugin")
            assert registered_plugin is not None
            assert registered_plugin.name == "register-plugin"
        finally:
            tmp_path.unlink()

    def test_load_and_register_unsupported_file(self, loader: PluginLoader) -> None:
        """Test load and register with unsupported file type."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("not a plugin")
            tmp_path = Path(tmp.name)

        try:
            result = loader.load_and_register(tmp_path)
            assert result is False
        finally:
            tmp_path.unlink()


class TestPluginDiscovery:
    """Test PluginDiscovery functionality."""

    @pytest.fixture
    def discovery(self) -> PluginDiscovery:
        """Create plugin discovery for testing."""
        return PluginDiscovery()

    def test_discovery_initialization(self, discovery: PluginDiscovery) -> None:
        """Test discovery initialization."""
        assert discovery.loader is not None
        assert discovery.logger is not None

    def test_discover_in_directory_not_found(self, discovery: PluginDiscovery) -> None:
        """Test discovery in non-existent directory."""
        result = discovery.discover_in_directory(Path("/non/existent"))
        assert result == []

    def test_discover_in_directory_empty(self, discovery: PluginDiscovery) -> None:
        """Test discovery in empty directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = discovery.discover_in_directory(Path(tmp_dir))
            assert result == []

    def test_discover_in_directory_with_plugins(
        self,
        discovery: PluginDiscovery,
    ) -> None:
        """Test discovery in directory with plugin files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create plugin files (must contain plugin indicators)
            plugin_files = [
                "my_plugin.py",  # Contains "plugin"
                "hook_validator.py",  # Contains "hook"
                "format_checker.json",  # Contains "format"
                "lint_extension.yaml",  # Contains "lint"
            ]

            for filename in plugin_files:
                (tmp_path / filename).write_text("# plugin content")

            # Create non-plugin files
            (tmp_path / "readme.txt").write_text("not a plugin")
            (tmp_path / "__init__.py").write_text("init file")
            (tmp_path / "test_something.py").write_text(
                "test file",
            )  # Starts with "test_"
            (tmp_path / "helper.py").write_text("helper file")  # No plugin indicators

            result = discovery.discover_in_directory(tmp_path)

            # Should find plugin files but not non-plugin files
            discovered_names = [p.name for p in result]
            assert "my_plugin.py" in discovered_names
            assert "hook_validator.py" in discovered_names
            assert "format_checker.json" in discovered_names
            assert "lint_extension.yaml" in discovered_names
            assert "readme.txt" not in discovered_names
            assert "__init__.py" not in discovered_names
            assert "test_something.py" not in discovered_names
            assert "helper.py" not in discovered_names

    def test_discover_in_directory_recursive(self, discovery: PluginDiscovery) -> None:
        """Test recursive discovery."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create nested directory structure
            subdir = tmp_path / "subdirectory"
            subdir.mkdir()

            (tmp_path / "top_plugin.py").write_text("# top level plugin")
            (subdir / "nested_plugin.py").write_text("# nested plugin")

            # Non-recursive should only find top level
            result_non_recursive = discovery.discover_in_directory(
                tmp_path,
                recursive=False,
            )
            names_non_recursive = [p.name for p in result_non_recursive]
            assert "top_plugin.py" in names_non_recursive
            assert "nested_plugin.py" not in names_non_recursive

            # Recursive should find both
            result_recursive = discovery.discover_in_directory(tmp_path, recursive=True)
            names_recursive = [p.name for p in result_recursive]
            assert "top_plugin.py" in names_recursive
            assert "nested_plugin.py" in names_recursive

    def test_discover_in_project(self, discovery: PluginDiscovery) -> None:
        """Test project-level plugin discovery."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir)

            # Create plugin directories
            plugins_dir = project_path / "plugins"
            plugins_dir.mkdir()

            cache_dir = project_path / ".cache" / "crackerjack" / "plugins"
            cache_dir.mkdir(parents=True)

            tools_dir = project_path / "tools" / "crackerjack"
            tools_dir.mkdir(parents=True)

            # Create plugin files in different directories
            (plugins_dir / "project_plugin.py").write_text("# project plugin")
            (cache_dir / "cache_plugin.py").write_text("# cache plugin")
            (tools_dir / "tools_plugin.py").write_text("# tools plugin")

            result = discovery.discover_in_project(project_path)

            names = [p.name for p in result]
            assert "project_plugin.py" in names
            assert "cache_plugin.py" in names
            assert "tools_plugin.py" in names

    def test_looks_like_plugin_file(self, discovery: PluginDiscovery) -> None:
        """Test plugin file detection logic."""
        # Should match plugin files (contain plugin indicators)
        assert discovery._looks_like_plugin_file(Path("my_plugin.py")) is True
        assert discovery._looks_like_plugin_file(Path("hook_validator.py")) is True
        assert (
            discovery._looks_like_plugin_file(Path("crackerjack_extension.json"))
            is True
        )
        assert discovery._looks_like_plugin_file(Path("format_check.yaml")) is True
        assert discovery._looks_like_plugin_file(Path("lint_addon.py")) is True

        # Should not match non-plugin files
        assert (
            discovery._looks_like_plugin_file(Path("test_something.py")) is False
        )  # Starts with "test_"
        assert (
            discovery._looks_like_plugin_file(Path("__init__.py")) is False
        )  # Special file
        assert (
            discovery._looks_like_plugin_file(Path("setup.py")) is False
        )  # Special file
        assert (
            discovery._looks_like_plugin_file(Path("conftest.py")) is False
        )  # Special file
        assert (
            discovery._looks_like_plugin_file(Path(".hidden_file.py")) is False
        )  # Starts with "."
        assert (
            discovery._looks_like_plugin_file(Path("__private__.py")) is False
        )  # Starts with "__"
        assert (
            discovery._looks_like_plugin_file(Path("readme.txt")) is False
        )  # No plugin indicators
        assert (
            discovery._looks_like_plugin_file(Path("helper.py")) is False
        )  # No plugin indicators


class TestPluginManager:
    """Test PluginManager functionality."""

    @pytest.fixture
    def plugin_manager(self, mock_console: Console) -> PluginManager:
        """Create plugin manager for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir)
            registry = PluginRegistry()
            hook_registry = HookPluginRegistry()
            yield PluginManager(mock_console, project_path, registry, hook_registry)

    def test_plugin_manager_initialization(self, plugin_manager: PluginManager) -> None:
        """Test plugin manager initialization."""
        assert plugin_manager.console is not None
        assert plugin_manager.project_path is not None
        assert plugin_manager.registry is not None
        assert plugin_manager.hook_registry is not None
        assert plugin_manager.loader is not None
        assert plugin_manager.discovery is not None
        assert plugin_manager._initialized is False

    def test_initialize_no_plugins(self, plugin_manager: PluginManager) -> None:
        """Test initialization with no plugins found."""
        with patch.object(
            plugin_manager.discovery,
            "auto_discover_and_load",
        ) as mock_discover:
            mock_discover.return_value = {}

            result = plugin_manager.initialize()
            assert result is True
            assert plugin_manager._initialized is True

    def test_initialize_with_plugins(self, plugin_manager: PluginManager) -> None:
        """Test initialization with plugins."""
        with patch.object(
            plugin_manager.discovery,
            "auto_discover_and_load",
        ) as mock_discover:
            mock_discover.return_value = {"plugin1.py": True, "plugin2.py": True}

            with patch.object(plugin_manager.registry, "activate_all") as mock_activate:
                mock_activate.return_value = {"plugin1": True, "plugin2": True}

                result = plugin_manager.initialize()
                assert result is True
                assert plugin_manager._initialized is True

    def test_initialize_already_initialized(
        self,
        plugin_manager: PluginManager,
    ) -> None:
        """Test initialization when already initialized."""
        plugin_manager._initialized = True

        result = plugin_manager.initialize()
        assert result is True

    def test_initialize_error(self, plugin_manager: PluginManager) -> None:
        """Test initialization with error."""
        with patch.object(
            plugin_manager.discovery,
            "auto_discover_and_load",
        ) as mock_discover:
            mock_discover.side_effect = Exception("Discovery failed")

            result = plugin_manager.initialize()
            assert result is False
            assert plugin_manager._initialized is False

    def test_shutdown_not_initialized(self, plugin_manager: PluginManager) -> None:
        """Test shutdown when not initialized."""
        plugin_manager.shutdown()  # Should not raise

    def test_shutdown_initialized(self, plugin_manager: PluginManager) -> None:
        """Test shutdown when initialized."""
        plugin_manager._initialized = True

        with patch.object(plugin_manager.registry, "deactivate_all") as mock_deactivate:
            mock_deactivate.return_value = {"plugin1": True}

            plugin_manager.shutdown()
            assert plugin_manager._initialized is False
            mock_deactivate.assert_called_once()

    def test_list_plugins_all(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test listing all plugins."""
        plugin = ConcreteTestPlugin(test_metadata)
        plugin_manager.registry.register(plugin)

        result = plugin_manager.list_plugins()

        assert result["total"] == 1
        assert result["enabled"] == 1
        assert len(result["plugins"]) == 1
        assert result["plugins"][0]["metadata"]["name"] == "test-plugin"

    def test_list_plugins_by_type(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test listing plugins by type."""
        hook_plugin = ConcreteTestPlugin(test_metadata)

        formatter_metadata = PluginMetadata(
            name="formatter-plugin",
            version="1.0.0",
            plugin_type=PluginType.FORMATTER,
            description="Formatter plugin",
        )
        formatter_plugin = ConcreteTestPlugin(formatter_metadata)

        plugin_manager.registry.register(hook_plugin)
        plugin_manager.registry.register(formatter_plugin)

        hook_result = plugin_manager.list_plugins(PluginType.HOOK)
        formatter_result = plugin_manager.list_plugins(PluginType.FORMATTER)

        assert hook_result["total"] == 1
        assert formatter_result["total"] == 1
        assert hook_result["plugins"][0]["metadata"]["name"] == "test-plugin"
        assert formatter_result["plugins"][0]["metadata"]["name"] == "formatter-plugin"

    def test_enable_plugin_success(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test enabling plugin successfully."""
        plugin = ConcreteTestPlugin(test_metadata)
        plugin.disable()
        plugin_manager.registry.register(plugin)

        result = plugin_manager.enable_plugin("test-plugin")
        assert result is True
        assert plugin.enabled is True
        assert plugin.activate_called is True

    def test_enable_plugin_not_found(self, plugin_manager: PluginManager) -> None:
        """Test enabling non-existent plugin."""
        result = plugin_manager.enable_plugin("non-existent")
        assert result is False

    def test_enable_plugin_already_enabled(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test enabling already enabled plugin."""
        plugin = ConcreteTestPlugin(test_metadata)
        plugin_manager.registry.register(plugin)

        result = plugin_manager.enable_plugin("test-plugin")
        assert result is True

    def test_enable_plugin_activation_failure(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test enabling plugin with activation failure."""
        plugin = FailingTestPlugin(test_metadata)
        plugin.disable()
        plugin_manager.registry.register(plugin)

        result = plugin_manager.enable_plugin("test-plugin")
        assert result is False
        assert plugin.enabled is False

    def test_disable_plugin_success(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test disabling plugin successfully."""
        plugin = ConcreteTestPlugin(test_metadata)
        plugin_manager.registry.register(plugin)

        result = plugin_manager.disable_plugin("test-plugin")
        assert result is True
        assert plugin.enabled is False
        assert plugin.deactivate_called is True

    def test_disable_plugin_not_found(self, plugin_manager: PluginManager) -> None:
        """Test disabling non-existent plugin."""
        result = plugin_manager.disable_plugin("non-existent")
        assert result is False

    def test_disable_plugin_already_disabled(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test disabling already disabled plugin."""
        plugin = ConcreteTestPlugin(test_metadata)
        plugin.disable()
        plugin_manager.registry.register(plugin)

        result = plugin_manager.disable_plugin("test-plugin")
        assert result is True

    def test_reload_plugin(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test reloading plugin."""
        plugin = ConcreteTestPlugin(test_metadata)
        plugin_manager.registry.register(plugin)

        result = plugin_manager.reload_plugin("test-plugin")
        assert result is True

    def test_configure_plugin_success(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test configuring plugin successfully."""
        plugin = ConcreteTestPlugin(test_metadata)
        plugin_manager.registry.register(plugin)

        config = {"api_key": "test-key"}
        result = plugin_manager.configure_plugin("test-plugin", config)
        assert result is True

    def test_configure_plugin_not_found(self, plugin_manager: PluginManager) -> None:
        """Test configuring non-existent plugin."""
        result = plugin_manager.configure_plugin("non-existent", {})
        assert result is False

    def test_configure_plugin_validation_error(
        self,
        plugin_manager: PluginManager,
        test_metadata: PluginMetadata,
    ) -> None:
        """Test configuring plugin with validation error."""
        plugin = ConcreteTestPlugin(test_metadata)
        plugin_manager.registry.register(plugin)

        # Missing required api_key
        config = {"timeout": 30}
        result = plugin_manager.configure_plugin("test-plugin", config)
        assert result is False

    def test_get_plugin_stats(self, plugin_manager: PluginManager) -> None:
        """Test getting plugin statistics."""
        stats = plugin_manager.get_plugin_stats()

        assert "total_plugins" in stats
        assert "enabled_plugins" in stats
        assert "by_type" in stats
        assert "hook_plugins" in stats

    def test_install_plugin_from_file(self, plugin_manager: PluginManager) -> None:
        """Test installing plugin from file."""
        plugin_code = """
from crackerjack.plugins.base import PluginBase, PluginMetadata, PluginType

class InstallPlugin(PluginBase):
    def activate(self):
        return True

    def deactivate(self):
        return True

metadata = PluginMetadata(
    name="install-plugin",
    version="1.0.0",
    plugin_type=PluginType.HOOK,
    description="Plugin for installation test"
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
        """Test getting available custom hooks."""
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
        """Test executing custom hook."""
        files = [Path("test.py")]

        with patch.object(
            plugin_manager.hook_registry,
            "execute_custom_hook",
        ) as mock_execute:
            mock_execute.return_value = Mock()

            result = plugin_manager.execute_custom_hook(
                "test-hook",
                files,
                mock_options,
            )

            mock_execute.assert_called_once_with("test-hook", files, mock_options)
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__])
