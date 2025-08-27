"""
Comprehensive strategic tests for the crackerjack plugin system.

This test suite targets the four main plugin modules with 0% coverage to boost overall coverage
toward the 42% target. Tests cover the entire plugin architecture lifecycle and interactions.

Target Modules:
- crackerjack/plugins/base.py - Plugin base classes and registry (124 statements)
- crackerjack/plugins/hooks.py - Hook plugin system (125 statements)
- crackerjack/plugins/loader.py - Plugin discovery and loading (178 statements)
- crackerjack/plugins/managers.py - Plugin orchestration and management (149 statements)

Combined Impact: 576 statements = potential 3.5% overall coverage boost
"""

import json
import subprocess
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


class TestPluginBase:
    """Test plugin base classes and registry functionality."""

    def test_plugin_metadata_complete_lifecycle(self) -> None:
        """Test complete PluginMetadata lifecycle with all fields."""
        metadata = PluginMetadata(
            name="strategic-plugin",
            version="2.1.0",
            plugin_type=PluginType.FORMATTER,
            description="Strategic test plugin with complete metadata",
            author="Test Suite",
            license="MIT",
            requires_python=">=3.13",
            dependencies=["ruff>=0.5.0", "black>=23.0"],
            entry_point="strategic_plugin:create",
            config_schema={
                "required": ["api_key", "timeout"],
                "properties": {
                    "api_key": {"type": "string"},
                    "timeout": {"type": "integer", "minimum": 1},
                    "enabled_checks": {"type": "array", "items": {"type": "string"}},
                },
            },
        )

        # Test all properties
        assert metadata.name == "strategic-plugin"
        assert metadata.version == "2.1.0"
        assert metadata.plugin_type == PluginType.FORMATTER
        assert metadata.description == "Strategic test plugin with complete metadata"
        assert metadata.author == "Test Suite"
        assert metadata.license == "MIT"
        assert metadata.requires_python == ">=3.13"
        assert "ruff>=0.5.0" in metadata.dependencies
        assert "black>=23.0" in metadata.dependencies
        assert metadata.entry_point == "strategic_plugin:create"
        assert "required" in metadata.config_schema
        assert "api_key" in metadata.config_schema["required"]

        # Test dict conversion with all fields
        metadata_dict = metadata.to_dict()
        assert metadata_dict["name"] == "strategic-plugin"
        assert metadata_dict["plugin_type"] == "formatter"
        assert metadata_dict["author"] == "Test Suite"
        assert metadata_dict["license"] == "MIT"
        assert len(metadata_dict["dependencies"]) == 2
        assert metadata_dict["config_schema"]["required"] == ["api_key", "timeout"]

    def test_plugin_base_configuration_validation(self) -> None:
        """Test plugin configuration validation with schema."""

        class ConfigurablePlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        # Create plugin with config schema
        metadata = PluginMetadata(
            name="config-test",
            version="1.0.0",
            plugin_type=PluginType.ANALYZER,
            description="Plugin with configuration validation",
            config_schema={
                "required": ["database_url", "max_connections"],
                "properties": {
                    "database_url": {"type": "string"},
                    "max_connections": {"type": "integer"},
                    "ssl_verify": {"type": "boolean", "default": True},
                },
            },
        )

        plugin = ConfigurablePlugin(metadata)

        # Test successful configuration
        valid_config = {
            "database_url": "postgresql://localhost/test",
            "max_connections": 10,
            "ssl_verify": False,
        }
        plugin.configure(valid_config)
        assert plugin.get_config("database_url") == "postgresql://localhost/test"
        assert plugin.get_config("max_connections") == 10
        assert plugin.get_config("ssl_verify") is False
        assert plugin.get_config("nonexistent", "default") == "default"

        # Test missing required field
        invalid_config = {"database_url": "postgresql://localhost/test"}
        with pytest.raises(
            ValueError, match="Required config key 'max_connections' missing"
        ):
            plugin.configure(invalid_config)

        # Test plugin without schema (should not raise)
        metadata_no_schema = PluginMetadata(
            name="no-schema",
            version="1.0.0",
            plugin_type=PluginType.WORKFLOW,
            description="Plugin without schema",
        )
        plugin_no_schema = ConfigurablePlugin(metadata_no_schema)
        plugin_no_schema.configure({"any": "config"})  # Should not raise

    def test_plugin_registry_comprehensive_operations(self) -> None:
        """Test comprehensive plugin registry operations."""
        registry = PluginRegistry()

        # Create test plugins of different types
        class TestHookPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        class TestFormatterPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        hook_plugin = TestHookPlugin(
            PluginMetadata(
                name="hook-1",
                version="1.0",
                plugin_type=PluginType.HOOK,
                description="Hook",
            )
        )
        formatter_plugin = TestFormatterPlugin(
            PluginMetadata(
                name="formatter-1",
                version="1.0",
                plugin_type=PluginType.FORMATTER,
                description="Formatter",
            )
        )

        # Test registration
        assert registry.register(hook_plugin) is True
        assert registry.register(formatter_plugin) is True
        assert registry.register(hook_plugin) is False  # Duplicate

        # Test retrieval by type
        hook_plugins = registry.get_by_type(PluginType.HOOK)
        formatter_plugins = registry.get_by_type(PluginType.FORMATTER)
        assert len(hook_plugins) == 1
        assert len(formatter_plugins) == 1
        assert hook_plugins[0].name == "hook-1"

        # Test enabled filtering
        hook_plugin.disable()
        enabled_hooks = registry.get_enabled(PluginType.HOOK)
        enabled_all = registry.get_enabled()
        assert len(enabled_hooks) == 0
        assert len(enabled_all) == 1  # Only formatter enabled

        # Test statistics
        stats = registry.get_stats()
        assert stats["total_plugins"] == 2
        assert stats["enabled_plugins"] == 1
        assert stats["by_type"]["hook"]["total"] == 1
        assert stats["by_type"]["hook"]["enabled"] == 0
        assert stats["by_type"]["hook"]["disabled"] == 1
        assert stats["by_type"]["formatter"]["total"] == 1
        assert stats["by_type"]["formatter"]["enabled"] == 1

        # Test activation/deactivation
        activation_results = registry.activate_all()
        assert len(activation_results) == 1  # Only enabled plugin activated
        assert activation_results["formatter-1"] is True

        deactivation_results = registry.deactivate_all()
        assert len(deactivation_results) == 2  # Both plugins deactivated
        assert deactivation_results["hook-1"] is True
        assert deactivation_results["formatter-1"] is True

        # Test unregistration
        assert registry.unregister("hook-1") is True
        assert registry.unregister("nonexistent") is False
        assert len(registry.list_all()) == 1

    def test_plugin_registry_error_handling(self) -> None:
        """Test plugin registry error handling during activation/deactivation."""
        registry = PluginRegistry()

        class FlakyPlugin(PluginBase):
            def __init__(self, metadata, activate_fails=False, deactivate_fails=False):
                super().__init__(metadata)
                self.activate_fails = activate_fails
                self.deactivate_fails = deactivate_fails

            def activate(self) -> bool:
                if self.activate_fails:
                    raise RuntimeError("Activation failed")
                return True

            def deactivate(self) -> bool:
                if self.deactivate_fails:
                    raise RuntimeError("Deactivation failed")
                return True

        # Test activation with exceptions
        failing_plugin = FlakyPlugin(
            PluginMetadata("fail-activate", "1.0", PluginType.HOOK, "Failing"),
            activate_fails=True,
        )
        registry.register(failing_plugin)

        activation_results = registry.activate_all()
        assert activation_results["fail-activate"] is False

        # Test deactivation with exceptions
        deactivate_fail_plugin = FlakyPlugin(
            PluginMetadata("fail-deactivate", "1.0", PluginType.HOOK, "Failing"),
            deactivate_fails=True,
        )
        registry.register(deactivate_fail_plugin)

        deactivation_results = registry.deactivate_all()
        assert deactivation_results["fail-deactivate"] is False

    def test_global_registry_singleton(self) -> None:
        """Test global plugin registry singleton behavior."""
        registry1 = get_plugin_registry()
        registry2 = get_plugin_registry()
        assert registry1 is registry2

        # Test that changes persist across calls
        class TestPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        plugin = TestPlugin(
            PluginMetadata(
                name="singleton-test",
                version="1.0",
                plugin_type=PluginType.INTEGRATION,
                description="Test",
            )
        )

        registry1.register(plugin)
        assert registry2.get("singleton-test") is plugin


class TestCustomHookSystem:
    """Test custom hook definitions and hook plugins."""

    def test_custom_hook_definition_complete(self) -> None:
        """Test CustomHookDefinition with all parameters."""
        hook_def = CustomHookDefinition(
            name="comprehensive-linter",
            description="Comprehensive code linting with multiple tools",
            command=["uv", "run", "ruff", "check", "--fix"],
            file_patterns=["*.py", "*.pyi", "src/**/*.py"],
            timeout=120,
            stage=HookStage.FAST,
            requires_files=True,
            parallel_safe=False,
        )

        assert hook_def.name == "comprehensive-linter"
        assert hook_def.description == "Comprehensive code linting with multiple tools"
        assert hook_def.command == ["uv", "run", "ruff", "check", "--fix"]
        assert "*.py" in hook_def.file_patterns
        assert "src/**/*.py" in hook_def.file_patterns
        assert hook_def.timeout == 120
        assert hook_def.stage == HookStage.FAST
        assert hook_def.requires_files is True
        assert hook_def.parallel_safe is False

        # Test conversion to HookDefinition
        hook_definition = hook_def.to_hook_definition()
        assert hook_definition.name == "comprehensive-linter"
        assert hook_definition.command == ["uv", "run", "ruff", "check", "--fix"]
        assert hook_definition.timeout == 120
        assert hook_definition.stage == HookStage.FAST
        assert hook_definition.manual_stage is False  # FAST stage

        # Test comprehensive stage
        comprehensive_hook = CustomHookDefinition(
            name="comprehensive-check",
            description="Comprehensive checking",
            stage=HookStage.COMPREHENSIVE,
        )
        comp_def = comprehensive_hook.to_hook_definition()
        assert comp_def.manual_stage is True  # COMPREHENSIVE stage

    def test_custom_hook_plugin_execution(self) -> None:
        """Test CustomHookPlugin execution with various scenarios."""
        # Create hook definitions
        fast_hook = CustomHookDefinition(
            name="quick-format",
            description="Quick formatting",
            command=["echo", "formatting"],
            timeout=10,
            stage=HookStage.FAST,
            requires_files=False,
        )

        file_specific_hook = CustomHookDefinition(
            name="python-check",
            description="Python file checking",
            command=["echo", "checking"],
            file_patterns=["*.py"],
            timeout=30,
            requires_files=True,
        )

        metadata = PluginMetadata(
            name="test-hook-plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Test hook plugin",
        )

        plugin = CustomHookPlugin(metadata, [fast_hook, file_specific_hook])

        # Initialize plugin
        console = Console()
        pkg_path = Path("/test/project")
        plugin.initialize(console, pkg_path)

        assert plugin.console is console
        assert plugin.pkg_path == pkg_path

        # Test hook definitions retrieval
        hook_defs = plugin.get_hook_definitions()
        assert len(hook_defs) == 2
        assert hook_defs[0].name == "quick-format"
        assert hook_defs[1].name == "python-check"

        # Test file filtering
        python_files = [Path("test.py"), Path("main.py")]
        js_files = [Path("script.js"), Path("app.js")]

        # Should run python-check on Python files
        assert plugin.should_run_hook("python-check", python_files) is True
        # Should not run python-check on JS files
        assert plugin.should_run_hook("python-check", js_files) is False
        # Should run quick-format regardless of files (requires_files=False)
        assert plugin.should_run_hook("quick-format", js_files) is True
        assert plugin.should_run_hook("quick-format", []) is True

    @patch("subprocess.run")
    def test_custom_hook_plugin_command_execution(self, mock_run: Mock) -> None:
        """Test actual command execution in CustomHookPlugin."""
        # Mock successful command execution
        mock_run.return_value = Mock(returncode=0, stdout="Success output", stderr="")

        hook_def = CustomHookDefinition(
            name="test-command",
            description="Test command execution",
            command=["echo", "test"],
            requires_files=True,
        )

        metadata = PluginMetadata(
            name="command-plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Command test plugin",
        )

        plugin = CustomHookPlugin(metadata, [hook_def])
        plugin.initialize(Console(), Path("/test"))

        mock_options = Mock(spec=OptionsProtocol)
        files = [Path("test.py")]

        result = plugin.execute_hook("test-command", files, mock_options)

        assert result.status == "passed"
        assert result.name == "test-command"
        assert result.duration >= 0
        assert len(result.issues_found) == 0

        # Verify subprocess was called with files appended
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["echo", "test", "test.py"]

    @patch("subprocess.run")
    def test_custom_hook_plugin_error_scenarios(self, mock_run: Mock) -> None:
        """Test error scenarios in CustomHookPlugin execution."""
        metadata = PluginMetadata(
            name="error-plugin",
            version="1.0.0",
            plugin_type=PluginType.HOOK,
            description="Error test",
        )

        # Test hook not found
        plugin = CustomHookPlugin(metadata, [])
        result = plugin.execute_hook("nonexistent", [], Mock())
        assert result.status == "error"
        assert "Hook definition not found" in result.issues_found[0]

        # Test no command defined
        no_cmd_hook = CustomHookDefinition(name="no-cmd", description="No command")
        plugin = CustomHookPlugin(metadata, [no_cmd_hook])
        result = plugin.execute_hook("no-cmd", [], Mock())
        assert result.status == "error"
        assert "No command defined" in result.issues_found[0]

        # Test command failure
        mock_run.return_value = Mock(returncode=1, stderr="Command failed")
        cmd_hook = CustomHookDefinition(
            name="fail-cmd", description="Failing command", command=["false"]
        )
        plugin = CustomHookPlugin(metadata, [cmd_hook])
        plugin.initialize(Console(), Path("/test"))

        result = plugin.execute_hook("fail-cmd", [], Mock())
        assert result.status == "failed"
        assert "Command failed" in result.issues_found[0]

        # Test timeout
        mock_run.side_effect = subprocess.TimeoutExpired(["timeout-cmd"], 5)
        timeout_hook = CustomHookDefinition(
            name="timeout-cmd",
            description="Timeout command",
            command=["sleep", "10"],
            timeout=5,
        )
        plugin = CustomHookPlugin(metadata, [timeout_hook])
        plugin.initialize(Console(), Path("/test"))

        result = plugin.execute_hook("timeout-cmd", [], Mock())
        assert result.status == "timeout"
        assert "timed out after 5s" in result.issues_found[0]

        # Test general exception
        mock_run.side_effect = RuntimeError("Unexpected error")
        error_hook = CustomHookDefinition(
            name="error-cmd", description="Error command", command=["error"]
        )
        plugin = CustomHookPlugin(metadata, [error_hook])
        plugin.initialize(Console(), Path("/test"))

        result = plugin.execute_hook("error-cmd", [], Mock())
        assert result.status == "error"
        assert "Execution error: Unexpected error" in result.issues_found[0]

    def test_hook_plugin_registry_operations(self) -> None:
        """Test HookPluginRegistry comprehensive operations."""
        registry = HookPluginRegistry()

        # Create test hook plugins
        hook1 = CustomHookDefinition(
            name="hook-1", description="Hook 1", command=["echo", "1"]
        )
        hook2 = CustomHookDefinition(
            name="hook-2",
            description="Hook 2",
            command=["echo", "2"],
            file_patterns=["*.py"],
        )

        metadata1 = PluginMetadata("plugin-1", "1.0", PluginType.HOOK, "Plugin 1")
        metadata2 = PluginMetadata("plugin-2", "1.0", PluginType.HOOK, "Plugin 2")

        plugin1 = CustomHookPlugin(metadata1, [hook1])
        plugin2 = CustomHookPlugin(metadata2, [hook2])

        # Test registration
        assert registry.register_hook_plugin(plugin1) is True
        assert registry.register_hook_plugin(plugin2) is True
        assert registry.register_hook_plugin(plugin1) is False  # Duplicate

        # Test hook retrieval
        all_hooks = registry.get_all_custom_hooks()
        assert len(all_hooks) == 2
        assert "hook-1" in all_hooks
        assert "hook-2" in all_hooks

        # Test disabled plugin filtering
        plugin2.disable()
        enabled_hooks = registry.get_all_custom_hooks()
        assert len(enabled_hooks) == 1
        assert "hook-1" in enabled_hooks
        assert "hook-2" not in enabled_hooks

        # Test initialization
        registry.initialize_all_plugins(Console(), Path("/test"))
        assert plugin1.console is not None
        assert plugin1.pkg_path == Path("/test")

        # Test hook execution
        plugin1.enable()
        with patch.object(plugin1, "execute_hook") as mock_execute:
            mock_execute.return_value = HookResult(
                "hook-1", "hook-1", "passed", 0.1, []
            )
            result = registry.execute_custom_hook("hook-1", [], Mock())
            assert result is not None
            assert result.status == "passed"

        # Test hooks for files
        python_files = [Path("test.py")]
        applicable_hooks = registry.get_hooks_for_files(python_files)
        # Only hook-1 should apply (hook-2 is disabled)
        assert "hook-1" in applicable_hooks

        # Test unregistration
        assert registry.unregister_hook_plugin("plugin-1") is True
        assert registry.unregister_hook_plugin("nonexistent") is False

    def test_hook_registry_singleton(self) -> None:
        """Test global hook plugin registry singleton."""
        registry1 = get_hook_plugin_registry()
        registry2 = get_hook_plugin_registry()
        assert registry1 is registry2


class TestPluginLoader:
    """Test plugin loading and discovery functionality."""

    def test_plugin_load_error_exception(self) -> None:
        """Test PluginLoadError exception."""
        error = PluginLoadError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    @patch("importlib.util.spec_from_file_location")
    @patch("importlib.util.module_from_spec")
    def test_plugin_loader_file_loading_success(
        self, mock_module_from_spec: Mock, mock_spec: Mock
    ) -> None:
        """Test successful plugin loading from file."""
        # Create test plugin file
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp_file:
            plugin_file = Path(tmp_file.name)

        try:
            # Mock module loading
            mock_spec_obj = Mock()
            mock_spec_obj.loader = Mock()
            mock_spec.return_value = mock_spec_obj

            mock_module = Mock()
            mock_module_from_spec.return_value = mock_module

            # Create a test plugin to return
            class TestFilePlugin(PluginBase):
                def activate(self) -> bool:
                    return True

                def deactivate(self) -> bool:
                    return True

            test_plugin = TestFilePlugin(
                PluginMetadata("file-plugin", "1.0", PluginType.HOOK, "File plugin")
            )

            # Mock plugin extraction
            loader = PluginLoader()
            with patch.object(loader, "_extract_plugin_from_module") as mock_extract:
                mock_extract.return_value = test_plugin

                result = loader.load_plugin_from_file(plugin_file)
                assert result is test_plugin
                assert isinstance(result, PluginBase)

        finally:
            plugin_file.unlink(missing_ok=True)

    def test_plugin_loader_file_loading_errors(self) -> None:
        """Test plugin loading error scenarios."""
        loader = PluginLoader()

        # Test non-existent file
        with pytest.raises(PluginLoadError, match="Plugin file not found"):
            loader.load_plugin_from_file(Path("/nonexistent/plugin.py"))

        # Test wrong extension
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with pytest.raises(PluginLoadError, match="Plugin file must be .py"):
                loader.load_plugin_from_file(Path(tmp_file.name))

    @patch("importlib.util.spec_from_file_location")
    def test_plugin_loader_spec_creation_failure(self, mock_spec: Mock) -> None:
        """Test plugin loading when spec creation fails."""
        mock_spec.return_value = None

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp_file:
            plugin_file = Path(tmp_file.name)

        try:
            loader = PluginLoader()
            with pytest.raises(PluginLoadError, match="Could not create module spec"):
                loader.load_plugin_from_file(plugin_file)
        finally:
            plugin_file.unlink(missing_ok=True)

    def test_plugin_loader_config_loading_json(self) -> None:
        """Test plugin loading from JSON configuration."""
        config = {
            "name": "json-plugin",
            "version": "2.0.0",
            "type": "hook",
            "description": "Plugin from JSON",
            "author": "Test Author",
            "license": "Apache-2.0",
            "dependencies": ["requests>=2.0"],
            "hooks": [
                {
                    "name": "json-hook",
                    "description": "Hook from JSON",
                    "command": ["echo", "json"],
                    "file_patterns": ["*.json"],
                    "timeout": 45,
                    "stage": "fast",
                    "requires_files": True,
                    "parallel_safe": False,
                }
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            json.dump(config, tmp_file)
            config_file = Path(tmp_file.name)

        try:
            loader = PluginLoader()
            plugin = loader.load_plugin_from_config(config_file)

            assert isinstance(plugin, CustomHookPlugin)
            assert plugin.name == "json-plugin"
            assert plugin.version == "2.0.0"
            assert plugin.metadata.author == "Test Author"
            assert plugin.metadata.license == "Apache-2.0"
            assert "requests>=2.0" in plugin.metadata.dependencies

            hook_defs = plugin.get_hook_definitions()
            assert len(hook_defs) == 1
            hook = hook_defs[0]
            assert hook.name == "json-hook"
            assert hook.command == ["echo", "json"]
            assert hook.file_patterns == ["*.json"]
            assert hook.timeout == 45
            assert hook.stage == HookStage.FAST
            assert hook.requires_files is True
            assert hook.parallel_safe is False

        finally:
            config_file.unlink(missing_ok=True)

    @patch("yaml.safe_load")
    def test_plugin_loader_config_loading_yaml(self, mock_yaml: Mock) -> None:
        """Test plugin loading from YAML configuration."""
        yaml_config = {
            "name": "yaml-plugin",
            "version": "3.0.0",
            "type": "hook",  # Changed to hook since CustomHookPlugin only supports HOOK type
            "description": "Plugin from YAML",
            "hooks": [
                {
                    "name": "yaml-formatter",
                    "description": "YAML formatter hook",  # Added required description
                    "command": ["yamlfmt"],
                    "stage": "comprehensive",
                }
            ],
        }

        mock_yaml.return_value = yaml_config

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp_file:
            config_file = Path(tmp_file.name)

        try:
            loader = PluginLoader()
            plugin = loader.load_plugin_from_config(config_file)

            assert plugin.name == "yaml-plugin"
            assert plugin.metadata.plugin_type == PluginType.HOOK

            hook_defs = plugin.get_hook_definitions()
            assert len(hook_defs) == 1
            assert hook_defs[0].stage == HookStage.COMPREHENSIVE

        finally:
            config_file.unlink(missing_ok=True)

    def test_plugin_loader_config_errors(self) -> None:
        """Test plugin config loading error scenarios."""
        loader = PluginLoader()

        # Test non-existent config file
        with pytest.raises(PluginLoadError, match="Plugin config file not found"):
            loader.load_plugin_from_config(Path("/nonexistent/config.json"))

        # Test unsupported format
        with tempfile.NamedTemporaryFile(suffix=".xml") as tmp_file:
            config_file = Path(tmp_file.name)
            with pytest.raises(PluginLoadError, match="Unsupported config format"):
                loader.load_plugin_from_config(config_file)

        # Test invalid JSON
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            tmp_file.write("invalid json content")
            config_file = Path(tmp_file.name)

        try:
            with pytest.raises(PluginLoadError, match="Failed to parse config file"):
                loader.load_plugin_from_config(config_file)
        finally:
            config_file.unlink(missing_ok=True)

    def test_plugin_loader_unsupported_plugin_type(self) -> None:
        """Test error when loading unsupported plugin type."""
        config = {
            "name": "unsupported-plugin",
            "type": "unsupported_type",  # This will cause enum error first
            "description": "Unsupported plugin type",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            json.dump(config, tmp_file)
            config_file = Path(tmp_file.name)

        try:
            loader = PluginLoader()
            # This should raise a ValueError from PluginType enum
            with pytest.raises((PluginLoadError, ValueError)):
                loader.load_plugin_from_config(config_file)
        finally:
            config_file.unlink(missing_ok=True)

    def test_plugin_loader_load_and_register(self) -> None:
        """Test load_and_register method with success and failure scenarios."""
        loader = PluginLoader()

        # Test successful loading and registration
        config = {
            "name": "register-test",
            "type": "hook",
            "description": "Registration test plugin",
            "hooks": [{"name": "test-hook", "command": ["echo", "test"]}],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            json.dump(config, tmp_file)
            config_file = Path(tmp_file.name)

        try:
            result = loader.load_and_register(config_file)
            assert result is True

            # Verify plugin was registered
            registered_plugin = loader.registry.get("register-test")
            assert registered_plugin is not None
            assert registered_plugin.name == "register-test"

        finally:
            config_file.unlink(missing_ok=True)

        # Test unsupported file type
        with tempfile.NamedTemporaryFile(suffix=".unknown") as tmp_file:
            result = loader.load_and_register(Path(tmp_file.name))
            assert result is False

        # Test loading failure
        result = loader.load_and_register(Path("/nonexistent/file.py"))
        assert result is False


class TestPluginDiscovery:
    """Test plugin discovery functionality."""

    def test_plugin_discovery_in_directory(self) -> None:
        """Test plugin discovery in specific directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create test plugin files
            plugin_py = tmp_path / "test_plugin.py"
            plugin_py.write_text("# Test plugin")

            plugin_json = tmp_path / "hook_config.json"
            plugin_json.write_text('{"name": "test", "type": "hook"}')

            plugin_yaml = tmp_path / "formatter_plugin.yaml"
            plugin_yaml.write_text("name: formatter")

            # Create files that should be ignored
            init_file = tmp_path / "__init__.py"
            init_file.write_text("")

            test_file = tmp_path / "test_something.py"
            test_file.write_text("")

            hidden_file = tmp_path / ".hidden_plugin.py"
            hidden_file.write_text("")

            discovery = PluginDiscovery()

            # Test non-recursive discovery
            found_files = discovery.discover_in_directory(tmp_path, recursive=False)
            found_names = [f.name for f in found_files]

            assert "test_plugin.py" in found_names
            assert "hook_config.json" in found_names
            assert "formatter_plugin.yaml" in found_names
            assert "__init__.py" not in found_names
            assert "test_something.py" not in found_names
            assert ".hidden_plugin.py" not in found_names

    def test_plugin_discovery_recursive(self) -> None:
        """Test recursive plugin discovery."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create nested structure
            sub_dir = tmp_path / "plugins" / "custom"
            sub_dir.mkdir(parents=True)

            nested_plugin = sub_dir / "nested_plugin.py"
            nested_plugin.write_text("# Nested plugin")

            discovery = PluginDiscovery()

            # Test recursive discovery
            found_files = discovery.discover_in_directory(tmp_path, recursive=True)
            found_paths = [str(f) for f in found_files]

            assert any("nested_plugin.py" in path for path in found_paths)

    def test_plugin_discovery_nonexistent_directory(self) -> None:
        """Test discovery in non-existent directory."""
        discovery = PluginDiscovery()

        found_files = discovery.discover_in_directory(
            Path("/nonexistent"), recursive=False
        )
        assert found_files == []

    def test_plugin_discovery_in_project(self) -> None:
        """Test discovery in project structure."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir)

            # Create expected plugin directories
            plugins_dir = project_path / "plugins"
            plugins_dir.mkdir()

            cache_dir = project_path / ".cache" / "crackerjack" / "plugins"
            cache_dir.mkdir(parents=True)

            tools_dir = project_path / "tools" / "crackerjack"
            tools_dir.mkdir(parents=True)

            # Add plugin files in each directory
            (plugins_dir / "main_plugin.py").write_text("# Main plugin")
            (cache_dir / "cached_plugin.json").write_text('{"name": "cached"}')
            (tools_dir / "tool_plugin.yaml").write_text("name: tool")

            discovery = PluginDiscovery()
            found_files = discovery.discover_in_project(project_path)

            found_names = [f.name for f in found_files]
            assert "main_plugin.py" in found_names
            assert "cached_plugin.json" in found_names
            assert "tool_plugin.yaml" in found_names

    def test_plugin_discovery_auto_discover_and_load(self) -> None:
        """Test auto discovery and loading workflow."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir)
            plugins_dir = project_path / "plugins"
            plugins_dir.mkdir()

            # Create valid plugin config
            plugin_config = {
                "name": "auto-discovered",
                "type": "hook",
                "description": "Auto-discovered plugin",
                "hooks": [{"name": "auto-hook", "command": ["echo", "auto"]}],
            }

            plugin_file = plugins_dir / "auto_plugin.json"
            with plugin_file.open("w") as f:
                json.dump(plugin_config, f)

            # Create mock loader
            mock_loader = Mock()
            mock_loader.load_and_register.return_value = True

            discovery = PluginDiscovery(loader=mock_loader)
            results = discovery.auto_discover_and_load(project_path)

            assert len(results) == 1
            assert str(plugin_file) in results
            assert results[str(plugin_file)] is True
            mock_loader.load_and_register.assert_called_once_with(plugin_file)

    def test_plugin_discovery_looks_like_plugin_file(self) -> None:
        """Test plugin file detection logic."""
        discovery = PluginDiscovery()

        # Files that should be detected as plugins
        plugin_files = [
            Path("my_plugin.py"),
            Path("custom_hook.py"),
            Path("formatter_extension.py"),
            Path("lint_addon.py"),
            Path("crackerjack_tool.py"),
            Path("quality_check.py"),
            Path("code_format.json"),
            Path("hook_plugin.yaml"),
        ]

        for file_path in plugin_files:
            assert discovery._looks_like_plugin_file(file_path), (
                f"{file_path} should be detected as plugin"
            )

        # Files that should NOT be detected as plugins
        non_plugin_files = [
            Path("__init__.py"),
            Path("setup.py"),
            Path("conftest.py"),
            Path("test_something.py"),
            Path("__pycache__/module.py"),
            Path(".hidden_file.py"),
            Path("regular_module.py"),
            Path("utils.py"),
        ]

        for file_path in non_plugin_files:
            assert not discovery._looks_like_plugin_file(file_path), (
                f"{file_path} should NOT be detected as plugin"
            )


class TestPluginManager:
    """Test plugin manager orchestration and lifecycle."""

    @pytest.fixture
    def plugin_manager(self) -> PluginManager:
        """Create plugin manager for testing."""
        console = Console()
        project_path = Path("/test/project")
        return PluginManager(console=console, project_path=project_path)

    def test_plugin_manager_initialization_lifecycle(
        self, plugin_manager: PluginManager
    ) -> None:
        """Test plugin manager complete initialization lifecycle."""
        assert not plugin_manager._initialized

        with patch.object(
            plugin_manager.discovery, "auto_discover_and_load"
        ) as mock_discover:
            with patch.object(plugin_manager.registry, "activate_all") as mock_activate:
                mock_discover.return_value = {
                    "/test/plugin1.py": True,
                    "/test/plugin2.json": True,
                    "/test/plugin3.yaml": False,
                }
                mock_activate.return_value = {"plugin1": True, "plugin2": True}

                result = plugin_manager.initialize()

                assert result is True
                assert plugin_manager._initialized is True
                mock_discover.assert_called_once_with(plugin_manager.project_path)
                mock_activate.assert_called_once()

    def test_plugin_manager_initialization_failure(
        self, plugin_manager: PluginManager
    ) -> None:
        """Test plugin manager initialization failure handling."""
        with patch.object(
            plugin_manager.discovery, "auto_discover_and_load"
        ) as mock_discover:
            mock_discover.side_effect = RuntimeError("Discovery failed")

            result = plugin_manager.initialize()

            assert result is False
            assert not plugin_manager._initialized

    def test_plugin_manager_shutdown(self, plugin_manager: PluginManager) -> None:
        """Test plugin manager shutdown process."""
        # Initialize first
        plugin_manager._initialized = True

        with patch.object(plugin_manager.registry, "deactivate_all") as mock_deactivate:
            mock_deactivate.return_value = {
                "plugin1": True,
                "plugin2": False,
                "plugin3": True,
            }

            plugin_manager.shutdown()

            assert not plugin_manager._initialized
            mock_deactivate.assert_called_once()

    def test_plugin_manager_shutdown_error_handling(
        self, plugin_manager: PluginManager
    ) -> None:
        """Test plugin manager shutdown error handling."""
        plugin_manager._initialized = True

        with patch.object(plugin_manager.registry, "deactivate_all") as mock_deactivate:
            mock_deactivate.side_effect = RuntimeError("Deactivation failed")

            # Should not raise exception
            plugin_manager.shutdown()
            assert not plugin_manager._initialized

    def test_plugin_manager_plugin_control(self, plugin_manager: PluginManager) -> None:
        """Test plugin enable/disable/reload/configure operations."""

        # Create test plugin
        class TestPlugin(PluginBase):
            def __init__(self, metadata):
                super().__init__(metadata)
                self.activate_count = 0
                self.deactivate_count = 0

            def activate(self) -> bool:
                self.activate_count += 1
                return True

            def deactivate(self) -> bool:
                self.deactivate_count += 1
                return True

        metadata = PluginMetadata(
            name="control-test",
            version="1.0",
            plugin_type=PluginType.HOOK,
            description="Control test plugin",
            config_schema={"required": ["setting"]},
        )

        plugin = TestPlugin(metadata)
        plugin_manager.registry.register(plugin)

        # Test enable (already enabled by default)
        result = plugin_manager.enable_plugin("control-test")
        assert result is True

        # Test disable
        result = plugin_manager.disable_plugin("control-test")
        assert result is True
        assert plugin.deactivate_count == 1

        # Test enable after disable
        result = plugin_manager.enable_plugin("control-test")
        assert result is True
        assert plugin.activate_count == 1

        # Test configuration
        config = {"setting": "test_value"}
        result = plugin_manager.configure_plugin("control-test", config)
        assert result is True
        assert plugin.get_config("setting") == "test_value"

        # Test configuration validation error
        invalid_config = {"wrong_key": "value"}
        result = plugin_manager.configure_plugin("control-test", invalid_config)
        assert result is False

        # Test reload
        result = plugin_manager.reload_plugin("control-test")
        assert result is True
        assert plugin.deactivate_count == 2  # One more deactivation
        assert plugin.activate_count == 2  # One more activation

    def test_plugin_manager_plugin_control_errors(
        self, plugin_manager: PluginManager
    ) -> None:
        """Test error scenarios in plugin control operations."""
        # Test operations on non-existent plugin
        assert plugin_manager.enable_plugin("nonexistent") is False
        assert plugin_manager.disable_plugin("nonexistent") is False
        assert plugin_manager.configure_plugin("nonexistent", {}) is False

    def test_plugin_manager_list_plugins(self, plugin_manager: PluginManager) -> None:
        """Test plugin listing functionality."""

        # Create test plugins of different types
        class TestHookPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        class TestFormatterPlugin(PluginBase):
            def activate(self) -> bool:
                return True

            def deactivate(self) -> bool:
                return True

        hook_plugin = TestHookPlugin(
            PluginMetadata("hook-plugin", "1.0", PluginType.HOOK, "Hook plugin")
        )
        formatter_plugin = TestFormatterPlugin(
            PluginMetadata(
                "formatter-plugin", "1.0", PluginType.FORMATTER, "Formatter plugin"
            )
        )

        plugin_manager.registry.register(hook_plugin)
        plugin_manager.registry.register(formatter_plugin)

        # Test list all plugins
        all_plugins = plugin_manager.list_plugins()
        assert all_plugins["total"] == 2
        assert all_plugins["enabled"] == 2
        assert len(all_plugins["plugins"]) == 2

        # Test list plugins by type
        hook_plugins = plugin_manager.list_plugins(PluginType.HOOK)
        assert hook_plugins["total"] == 1
        assert hook_plugins["plugins"][0]["metadata"]["name"] == "hook-plugin"

        formatter_plugins = plugin_manager.list_plugins(PluginType.FORMATTER)
        assert formatter_plugins["total"] == 1
        assert formatter_plugins["plugins"][0]["metadata"]["name"] == "formatter-plugin"

    def test_plugin_manager_stats(self, plugin_manager: PluginManager) -> None:
        """Test plugin manager statistics functionality."""
        # Create hook plugin with custom hooks
        hook_def = CustomHookDefinition(
            name="stat-hook", description="Statistics hook", command=["echo", "stats"]
        )
        hook_metadata = PluginMetadata("stats-plugin", "1.0", PluginType.HOOK, "Stats")
        hook_plugin = CustomHookPlugin(hook_metadata, [hook_def])

        plugin_manager.registry.register(hook_plugin)
        plugin_manager.hook_registry.register_hook_plugin(hook_plugin)

        stats = plugin_manager.get_plugin_stats()

        assert stats["total_plugins"] == 1
        assert stats["hook_plugins"]["active_plugins"] == 1
        assert stats["hook_plugins"]["total_custom_hooks"] == 1
        assert "stat-hook" in stats["hook_plugins"]["hook_names"]

    def test_plugin_manager_install_from_file(
        self, plugin_manager: PluginManager
    ) -> None:
        """Test plugin installation from file."""
        config = {
            "name": "install-test",
            "type": "hook",
            "description": "Installation test plugin",
            "hooks": [{"name": "install-hook", "command": ["echo", "install"]}],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            json.dump(config, tmp_file)
            plugin_file = Path(tmp_file.name)

        try:
            # Initialize plugin manager to test auto-enable
            plugin_manager._initialized = True

            result = plugin_manager.install_plugin_from_file(plugin_file)
            assert result is True

            # Verify plugin was installed and registered
            installed_plugin = plugin_manager.registry.get("install-test")
            assert installed_plugin is not None

        finally:
            plugin_file.unlink(missing_ok=True)

    def test_plugin_manager_custom_hooks(self, plugin_manager: PluginManager) -> None:
        """Test custom hook management."""
        # Create hook plugin
        hook_def1 = CustomHookDefinition(
            name="custom-1", description="Custom hook 1", command=["echo", "1"]
        )
        hook_def2 = CustomHookDefinition(
            name="custom-2", description="Custom hook 2", command=["echo", "2"]
        )

        metadata = PluginMetadata(
            "custom-hooks", "1.0", PluginType.HOOK, "Custom hooks"
        )
        hook_plugin = CustomHookPlugin(metadata, [hook_def1, hook_def2])

        plugin_manager.registry.register(hook_plugin)
        plugin_manager.hook_registry.register_hook_plugin(hook_plugin)

        # Test available custom hooks
        available_hooks = plugin_manager.get_available_custom_hooks()
        assert "custom-1" in available_hooks
        assert "custom-2" in available_hooks

        # Test hook execution
        mock_options = Mock(spec=OptionsProtocol)
        files = [Path("test.py")]

        with patch.object(hook_plugin, "execute_hook") as mock_execute:
            mock_result = HookResult("custom-1", "custom-1", "passed", 0.5, [])
            mock_execute.return_value = mock_result

            result = plugin_manager.execute_custom_hook("custom-1", files, mock_options)
            assert result == mock_result
            mock_execute.assert_called_once_with("custom-1", files, mock_options)


class TestPluginIntegration:
    """Integration tests for the complete plugin system."""

    def test_end_to_end_plugin_workflow(self) -> None:
        """Test complete end-to-end plugin workflow."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir)
            plugins_dir = project_path / "plugins"
            plugins_dir.mkdir()

            # Create plugin configuration
            plugin_config = {
                "name": "e2e-plugin",
                "version": "1.0.0",
                "type": "hook",
                "description": "End-to-end test plugin",
                "author": "Test Suite",
                "license": "MIT",
                "dependencies": ["ruff>=0.1.0"],
                "hooks": [
                    {
                        "name": "e2e-format",
                        "description": "End-to-end formatting",
                        "command": ["echo", "formatting"],
                        "file_patterns": ["*.py"],
                        "timeout": 30,
                        "stage": "fast",
                        "requires_files": True,
                        "parallel_safe": True,
                    },
                    {
                        "name": "e2e-lint",
                        "description": "End-to-end linting",
                        "command": ["echo", "linting"],
                        "stage": "comprehensive",
                        "requires_files": False,
                    },
                ],
            }

            plugin_file = plugins_dir / "e2e_plugin.json"
            with plugin_file.open("w") as f:
                json.dump(plugin_config, f)

            # Initialize plugin manager
            console = Console()
            plugin_manager = PluginManager(console=console, project_path=project_path)

            # Test discovery and initialization
            assert plugin_manager.initialize() is True
            assert plugin_manager._initialized is True

            # Verify plugin was loaded
            loaded_plugin = plugin_manager.registry.get("e2e-plugin")
            assert loaded_plugin is not None
            assert loaded_plugin.name == "e2e-plugin"
            assert loaded_plugin.version == "1.0.0"
            assert loaded_plugin.metadata.author == "Test Suite"

            # Test plugin listing
            all_plugins = plugin_manager.list_plugins()
            assert all_plugins["total"] == 1
            assert all_plugins["enabled"] == 1

            # Test custom hooks
            available_hooks = plugin_manager.get_available_custom_hooks()
            assert "e2e-format" in available_hooks
            assert "e2e-lint" in available_hooks

            # Test hook execution
            mock_options = Mock(spec=OptionsProtocol)
            python_files = [Path("test.py")]

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="success", stderr="")

                result = plugin_manager.execute_custom_hook(
                    "e2e-format", python_files, mock_options
                )
                assert result is not None
                assert result.status == "passed"
                assert result.name == "e2e-format"

            # Test plugin statistics
            stats = plugin_manager.get_plugin_stats()
            assert stats["total_plugins"] == 1
            assert stats["hook_plugins"]["total_custom_hooks"] == 2

            # Test shutdown
            plugin_manager.shutdown()
            assert not plugin_manager._initialized

    def test_plugin_system_error_resilience(self) -> None:
        """Test plugin system resilience to errors."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir)
            plugins_dir = project_path / "plugins"
            plugins_dir.mkdir()

            # Create valid and invalid plugin configs
            valid_config = {
                "name": "valid-plugin",
                "type": "hook",
                "description": "Valid plugin",
                "hooks": [{"name": "valid-hook", "command": ["echo", "valid"]}],
            }

            invalid_config = {
                "name": "invalid-plugin",
                # Missing required 'type' field
                "description": "Invalid plugin",
            }

            valid_file = plugins_dir / "valid_plugin.json"
            with valid_file.open("w") as f:
                json.dump(valid_config, f)

            invalid_file = plugins_dir / "invalid_plugin.json"
            with invalid_file.open("w") as f:
                json.dump(invalid_config, f)

            console = Console()
            plugin_manager = PluginManager(console=console, project_path=project_path)

            # Initialize should succeed despite invalid plugin
            result = plugin_manager.initialize()
            assert result is True

            # Valid plugin should be loaded
            valid_plugin = plugin_manager.registry.get("valid-plugin")
            assert valid_plugin is not None

            # Invalid plugin should not be loaded
            invalid_plugin = plugin_manager.registry.get("invalid-plugin")
            assert invalid_plugin is None

            # System should remain functional
            stats = plugin_manager.get_plugin_stats()
            assert stats["total_plugins"] >= 1  # At least the valid plugin

    def test_plugin_system_concurrent_operations(self) -> None:
        """Test plugin system handling of concurrent-like operations."""
        console = Console()
        project_path = Path("/test")
        plugin_manager = PluginManager(console=console, project_path=project_path)

        # Create multiple plugins
        plugins = []
        for i in range(3):

            class TestPlugin(PluginBase):
                def __init__(self, metadata):
                    super().__init__(metadata)
                    self.activation_count = 0

                def activate(self) -> bool:
                    self.activation_count += 1
                    return True

                def deactivate(self) -> bool:
                    return True

            metadata = PluginMetadata(
                f"concurrent-{i}", "1.0", PluginType.HOOK, f"Concurrent test plugin {i}"
            )
            plugin = TestPlugin(metadata)
            plugins.append(plugin)
            plugin_manager.registry.register(plugin)

        # Test bulk operations
        activation_results = plugin_manager.registry.activate_all()
        assert len(activation_results) == 3
        assert all(result for result in activation_results.values())

        deactivation_results = plugin_manager.registry.deactivate_all()
        assert len(deactivation_results) == 3
        assert all(result for result in deactivation_results.values())

        # Test individual plugin operations don't interfere
        for i, plugin in enumerate(plugins):
            result = plugin_manager.enable_plugin(f"concurrent-{i}")
            assert result is True

        stats = plugin_manager.get_plugin_stats()
        assert stats["total_plugins"] == 3
        assert stats["enabled_plugins"] == 3
