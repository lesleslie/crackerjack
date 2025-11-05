"""Integration tests for ACB Settings loading and conversion.

These tests validate that CrackerjackSettings loads correctly via ACB DI
and converts properly to OptionsProtocol for use with WorkflowOrchestrator.
"""

from pathlib import Path

import pytest
from rich.console import Console

from acb.depends import depends

from crackerjack.config import CrackerjackSettings
from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.mcp.tools.core_tools import _adapt_settings_to_protocol

# Settings adapter tests target legacy flat schema; skip under nested model
pytestmark = pytest.mark.skip(
    reason="Settings adapter tests are deprecated; current model uses nested settings"
)


class TestACBSettingsLoading:
    def test_acb_settings_loading(self) -> None:
        """Test CrackerjackSettings loads via ACB DI."""
        settings = depends.get_sync(CrackerjackSettings)

        assert settings is not None
        assert isinstance(settings, CrackerjackSettings)
        assert hasattr(settings.hooks, "skip_hooks")
        assert hasattr(settings.testing, "test")
        assert hasattr(settings.execution, "verbose")

    def test_settings_to_protocol_conversion(self) -> None:
        """Test CrackerjackSettings converts to OptionsProtocol."""
        settings = depends.get_sync(CrackerjackSettings)
        options = _adapt_settings_to_protocol(settings)

        # Verify OptionsProtocol interface (adapter properties)
        assert hasattr(options, "skip_hooks")
        assert hasattr(options, "verbose")
        assert hasattr(options, "test")  # Adapter property (maps to run_tests)
        assert hasattr(options, "clean")
        assert hasattr(options, "commit")

    def test_workflow_orchestrator_accepts_settings(self) -> None:
        """Test WorkflowOrchestrator works with CrackerjackSettings."""
        settings = depends.get_sync(CrackerjackSettings)
        options = _adapt_settings_to_protocol(settings)

        orchestrator = WorkflowOrchestrator(pkg_path=Path.cwd())

        # Should accept OptionsProtocol (no type error)
        assert orchestrator is not None

        # Verify adapter property mapping
        assert options.test == settings.run_tests
        assert options.skip_hooks == settings.skip_hooks
        assert options.verbose == settings.verbose

    def test_custom_settings_modification(self) -> None:
        """Test creating custom settings for test scenarios."""
        settings = depends.get_sync(CrackerjackSettings)

        # Create modified copy using Pydantic model_copy()
        custom_settings = settings.model_copy()
        custom_settings.clean = True
        custom_settings.run_tests = True
        custom_settings.verbose = True

        # Convert to OptionsProtocol
        options = _adapt_settings_to_protocol(custom_settings)

        # Verify modifications applied
        assert options.clean is True
        assert options.test is True  # Adapter property
        assert options.verbose is True

    def test_field_rename_mapping(self) -> None:
        """Test critical field renames are correctly mapped."""
        settings = depends.get_sync(CrackerjackSettings)

        # Create settings with renamed fields
        custom_settings = settings.model_copy()
        custom_settings.run_tests = True  # Settings field
        custom_settings.publish_version = "patch"  # Settings field
        custom_settings.bump_version = "minor"  # Settings field

        options = _adapt_settings_to_protocol(custom_settings)

        # Verify adapter exposes old property names
        assert options.test is True  # Adapter property (not run_tests)
        assert options.publish == "patch"  # Adapter property (not publish_version)
        assert options.bump == "minor"  # Adapter property (not bump_version)


class TestAdapterPropertyBehavior:
    def test_adapter_properties_are_read_only(self) -> None:
        """Test that adapter properties are read-only."""
        settings = depends.get(CrackerjackSettings)
        options = _adapt_settings_to_protocol(settings)

        # Attempting to set adapter properties should fail
        with pytest.raises(AttributeError, match="property .* has no setter"):
            options.clean = True  # type: ignore[misc]

        with pytest.raises(AttributeError, match="property .* has no setter"):
            options.test = True  # type: ignore[misc]

    def test_settings_copy_pattern(self) -> None:
        """Test the correct pattern for modifying settings."""
        settings = depends.get(CrackerjackSettings)

        # WRONG: Direct mutation (would fail with adapter)
        # settings.clean = True  # ❌ BaseSettings is immutable

        # CORRECT: Create mutable copy, modify, then adapt
        custom_settings = settings.model_copy()
        custom_settings.clean = True
        custom_settings.run_tests = True

        options = _adapt_settings_to_protocol(custom_settings)

        # Verify changes applied
        assert options.clean is True
        assert options.test is True


class TestBackwardCompatibility:
    def test_flat_access_replaces_nested(self) -> None:
        """Test that flat field access works (no more nesting)."""
        settings = depends.get(CrackerjackSettings)

        # Settings uses flat access (no nesting)
        assert hasattr(settings, "skip_hooks")  # Not settings.hooks.skip_hooks
        assert hasattr(settings, "clean")  # Not settings.cleaning.clean
        assert hasattr(settings, "commit")  # Not settings.git.commit
        assert hasattr(settings, "verbose")  # Not settings.execution.verbose

    def test_adapter_provides_protocol_interface(self) -> None:
        """Test adapter provides OptionsProtocol interface."""
        settings = depends.get(CrackerjackSettings)
        options = _adapt_settings_to_protocol(settings)

        # Adapter exposes all OptionsProtocol properties
        protocol_properties = [
            "skip_hooks",
            "verbose",
            "test",
            "clean",
            "commit",
            "interactive",
            "publish",
            "bump",
        ]

        for prop in protocol_properties:
            assert hasattr(options, prop), f"Adapter missing property: {prop}"
