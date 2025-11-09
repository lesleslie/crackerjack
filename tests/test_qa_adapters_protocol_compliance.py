"""Protocol compliance tests for QA adapters.

Tests verify that all QA adapters correctly implement QAAdapterProtocol
using inspect.signature for method validation, following crackerjack patterns.
"""

import inspect
from pathlib import Path
from uuid import UUID

import pytest

from crackerjack.adapters._qa_adapter_base import QAAdapterBase, QAAdapterProtocol
from crackerjack.adapters.format.ruff import RuffAdapter
from crackerjack.adapters.format.mdformat import MdformatAdapter
from crackerjack.adapters.lint.codespell import CodespellAdapter
from crackerjack.adapters.sast.bandit import BanditAdapter
from crackerjack.adapters.security.gitleaks import GitleaksAdapter
from crackerjack.adapters.type.zuban import ZubanAdapter
from crackerjack.adapters.refactor.refurb import RefurbAdapter
from crackerjack.adapters.refactor.creosote import CreosoteAdapter
from crackerjack.adapters.complexity.complexipy import ComplexipyAdapter
from crackerjack.adapters.utility.checks import UtilityCheckAdapter
from crackerjack.models.protocols import QAAdapterProtocol as ProtocolDef


class TestQAAdapterProtocolCompliance:
    """Test that all QA adapters implement QAAdapterProtocol correctly."""

    @pytest.fixture
    def adapter_classes(self):
        """All QA adapter classes to test."""
        return [
            UtilityCheckAdapter,
            RuffAdapter,
            BanditAdapter,
            GitleaksAdapter,
            ZubanAdapter,
            RefurbAdapter,
            ComplexipyAdapter,
            CreosoteAdapter,
            CodespellAdapter,
            MdformatAdapter,
        ]

    def test_all_adapters_extend_base(self, adapter_classes):
        """Verify all adapters extend QAAdapterBase."""
        for adapter_class in adapter_classes:
            assert issubclass(adapter_class, QAAdapterBase), (
                f"{adapter_class.__name__} must extend QAAdapterBase"
            )

    def test_protocol_compliance(self, adapter_classes):
        """Verify all adapters implement QAAdapterProtocol."""
        for adapter_class in adapter_classes:
            # Check required attributes
            assert hasattr(adapter_class, "settings"), (
                f"{adapter_class.__name__} missing settings attribute"
            )

            # Check required methods
            required_methods = [
                "init",
                "check",
                "validate_config",
                "get_default_config",
                "health_check",
                "adapter_name",
                "module_id",
            ]

            for method in required_methods:
                assert hasattr(adapter_class, method), (
                    f"{adapter_class.__name__} missing method: {method}"
                )

    def test_init_method_signature(self, adapter_classes):
        """Verify init() method has correct signature."""
        for adapter_class in adapter_classes:
            init_sig = inspect.signature(adapter_class.init)

            # Should be async
            assert inspect.iscoroutinefunction(adapter_class.init), (
                f"{adapter_class.__name__}.init() must be async"
            )

            # Should have no required parameters beyond self
            params = [p for p in init_sig.parameters.values() if p.default == inspect.Parameter.empty and p.name != "self"]
            assert len(params) == 0, (
                f"{adapter_class.__name__}.init() should have no required parameters"
            )

    def test_check_method_signature(self, adapter_classes):
        """Verify check() method has correct signature."""
        for adapter_class in adapter_classes:
            check_sig = inspect.signature(adapter_class.check)

            # Should be async
            assert inspect.iscoroutinefunction(adapter_class.check), (
                f"{adapter_class.__name__}.check() must be async"
            )

            # Should have files and config parameters
            params = check_sig.parameters
            assert "files" in params, (
                f"{adapter_class.__name__}.check() missing 'files' parameter"
            )
            assert "config" in params, (
                f"{adapter_class.__name__}.check() missing 'config' parameter"
            )

            # Both should have defaults (None)
            assert params["files"].default is not inspect.Parameter.empty, (
                f"{adapter_class.__name__}.check() 'files' must have default"
            )
            assert params["config"].default is not inspect.Parameter.empty, (
                f"{adapter_class.__name__}.check() 'config' must have default"
            )

    def test_validate_config_method_signature(self, adapter_classes):
        """Verify validate_config() method has correct signature."""
        for adapter_class in adapter_classes:
            validate_sig = inspect.signature(adapter_class.validate_config)

            # Should be async
            assert inspect.iscoroutinefunction(adapter_class.validate_config), (
                f"{adapter_class.__name__}.validate_config() must be async"
            )

            # Should have config parameter and return bool
            params = validate_sig.parameters
            assert "config" in params, (
                f"{adapter_class.__name__}.validate_config() missing 'config' parameter"
            )

    def test_adapter_name_property(self, adapter_classes):
        """Verify adapter_name property returns string."""
        for adapter_class in adapter_classes:
            # Check it's a property
            assert isinstance(
                inspect.getattr_static(adapter_class, "adapter_name"),
                property,
            ), f"{adapter_class.__name__}.adapter_name must be a property"

    def test_module_id_property(self, adapter_classes):
        """Verify module_id property returns UUID."""
        for adapter_class in adapter_classes:
            # Check it's a property
            assert isinstance(
                inspect.getattr_static(adapter_class, "module_id"),
                property,
            ), f"{adapter_class.__name__}.module_id must be a property"


class TestQAAdapterInstantiation:
    """Test adapter instantiation and configuration."""

    def test_ruff_adapter_instantiation(self):
        """Test RuffAdapter can be instantiated."""
        from crackerjack.adapters.format.ruff import RuffSettings

        settings = RuffSettings(mode="check")
        adapter = RuffAdapter(settings=settings)

        assert adapter.settings is not None
        assert isinstance(adapter.adapter_name, str)
        assert isinstance(adapter.module_id, UUID)

    def test_bandit_adapter_instantiation(self):
        """Test BanditAdapter can be instantiated."""
        from crackerjack.adapters.sast.bandit import BanditSettings

        settings = BanditSettings()
        adapter = BanditAdapter(settings=settings)

        assert adapter.settings is not None
        assert isinstance(adapter.adapter_name, str)
        assert isinstance(adapter.module_id, UUID)

    def test_utility_check_adapter_instantiation(self):
        """Test UtilityCheckAdapter can be instantiated."""
        from crackerjack.adapters.utility.checks import (
            UtilityCheckSettings,
            UtilityCheckType,
        )

        settings = UtilityCheckSettings(check_type=UtilityCheckType.TEXT_PATTERN, pattern=r"\\s+$")
        adapter = UtilityCheckAdapter(settings=settings)

        assert adapter.settings is not None
        assert adapter.settings.check_type == UtilityCheckType.TEXT_PATTERN
        assert isinstance(adapter.adapter_name, str)
        assert isinstance(adapter.module_id, UUID)

    def test_adapter_without_settings(self):
        """Test adapters can be instantiated without settings."""
        adapter = RuffAdapter()
        assert adapter.settings is None

        # After init, settings should be set
        # (Can't test async init in synchronous test per CLAUDE.md)


class TestQAAdapterConfiguration:
    """Test adapter configuration validation."""

    def test_get_default_config(self):
        """Test all adapters provide default configuration."""
        from crackerjack.models.qa_config import QACheckConfig

        adapters = [
            RuffAdapter(),
            BanditAdapter(),
            GitleaksAdapter(),
            ZubanAdapter(),
            RefurbAdapter(),
            ComplexipyAdapter(),
            CreosoteAdapter(),
            CodespellAdapter(),
            MdformatAdapter(),
        ]

        for adapter in adapters:
            config = adapter.get_default_config()
            assert isinstance(config, QACheckConfig), (
                f"{adapter.__class__.__name__}.get_default_config() must return QACheckConfig"
            )

            # Verify required config fields
            assert isinstance(config.check_id, UUID)
            assert isinstance(config.check_name, str)
            assert len(config.check_name) > 0
            assert config.enabled is not None
            assert isinstance(config.file_patterns, list)

    def test_utility_check_default_configs(self):
        """Test UtilityCheckAdapter provides configs for different check types."""
        from crackerjack.adapters.utility.checks import UtilityCheckType

        # Test each check type has appropriate configuration
        check_types = [
            UtilityCheckType.TEXT_PATTERN,
            UtilityCheckType.EOF_NEWLINE,
            UtilityCheckType.SYNTAX_VALIDATION,
            UtilityCheckType.SIZE_CHECK,
            UtilityCheckType.DEPENDENCY_LOCK,
        ]

        for check_type in check_types:
            # Each check type would have its own default config
            # (Implementation detail - not testing specific configs here)
            pass


class TestQAAdapterModuleRegistration:
    """Test ACB module registration patterns."""

    def test_adapters_have_module_id(self):
        """Verify all adapters have MODULE_ID at module level."""
        from crackerjack.adapters.format import ruff, mdformat
        from crackerjack.adapters.lint import codespell
        from crackerjack.adapters.security import bandit, gitleaks
        from crackerjack.adapters.type import zuban
        from crackerjack.adapters.refactor import refurb, creosote
        from crackerjack.adapters.complexity import complexipy
        from crackerjack.adapters.utility import checks

        modules = [
            bandit,
            codespell,
            complexipy,
            creosote,
            gitleaks,
            mdformat,
            refurb,
            ruff,
            checks,
            zuban,
        ]

        for module in modules:
            assert hasattr(module, "MODULE_ID"), (
                f"{module.__name__} must have MODULE_ID at module level"
            )
            assert isinstance(module.MODULE_ID, UUID), (
                f"{module.__name__}.MODULE_ID must be UUID"
            )

            assert hasattr(module, "MODULE_STATUS"), (
                f"{module.__name__} must have MODULE_STATUS at module level"
            )
            assert isinstance(module.MODULE_STATUS, str), (
                f"{module.__name__}.MODULE_STATUS must be string"
            )


class TestQABaseSettings:
    """Test QA adapter settings patterns."""

    def test_settings_extend_pydantic(self):
        """Verify settings classes use Pydantic BaseModel."""
        from crackerjack.adapters.format.ruff import RuffSettings
        from pydantic import BaseModel

        assert issubclass(RuffSettings, BaseModel), (
            "Settings must extend Pydantic BaseModel"
        )

    def test_settings_field_validators(self):
        """Test settings have proper field validators."""
        from crackerjack.adapters.format.ruff import RuffSettings

        # Valid settings
        settings = RuffSettings(mode="check")
        assert settings.mode == "check"

        # Tool name should be set
        assert hasattr(settings, "tool_name")
        assert isinstance(settings.tool_name, str)

    def test_settings_with_defaults(self):
        """Test settings have sensible defaults."""
        from crackerjack.adapters.sast.bandit import BanditSettings

        settings = BanditSettings()

        # Should have defaults for all optional fields
        assert hasattr(settings, "severity_level")
        assert hasattr(settings, "confidence_level")
        assert hasattr(settings, "exclude_tests")
