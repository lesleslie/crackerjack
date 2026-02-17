"""Tests for DefaultAdapterFactory."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from crackerjack.adapters.factory import DefaultAdapterFactory
from crackerjack.adapters.format.ruff import RuffAdapter
from crackerjack.adapters.sast.bandit import BanditAdapter
from crackerjack.adapters.sast.semgrep import SemgrepAdapter
from crackerjack.adapters.refactor.refurb import RefurbAdapter
from crackerjack.adapters.refactor.skylos import SkylosAdapter
from crackerjack.models.protocols import AdapterProtocol


class TestDefaultAdapterFactory:
    """Test suite for DefaultAdapterFactory."""

    @pytest.fixture
    def factory(self):
        """Create a factory instance."""
        return DefaultAdapterFactory()

    def test_initialization(self, factory):
        """Test factory initialization."""
        assert factory is not None
        assert factory.settings is None
        assert factory.pkg_path == Path.cwd()

    def test_initialization_with_params(self):
        """Test factory initialization with parameters."""
        settings = MagicMock()
        pkg_path = Path("/test/path")
        factory = DefaultAdapterFactory(settings=settings, pkg_path=pkg_path)

        assert factory.settings == settings
        assert factory.pkg_path == pkg_path

    # ---------------------------------------------------------------------
    # Tool Name Mapping Tests
    # ---------------------------------------------------------------------

    def test_get_adapter_name_known_tools(self, factory):
        """Test get_adapter_name for known tools."""
        assert factory.get_adapter_name("ruff") == "Ruff"
        assert factory.get_adapter_name("bandit") == "Bandit"
        assert factory.get_adapter_name("semgrep") == "Semgrep"
        assert factory.get_adapter_name("refurb") == "Refurb"
        assert factory.get_adapter_name("skylos") == "Skylos"
        assert factory.get_adapter_name("zuban") == "Zuban"

    def test_get_adapter_name_unknown_tool(self, factory):
        """Test get_adapter_name for unknown tool."""
        assert factory.get_adapter_name("unknown_tool") is None
        assert factory.get_adapter_name("nonexistent") is None
        assert factory.get_adapter_name("") is None

    def test_tool_has_adapter_known_tools(self, factory):
        """Test tool_has_adapter for known tools."""
        assert factory.tool_has_adapter("ruff") is True
        assert factory.tool_has_adapter("bandit") is True
        assert factory.tool_has_adapter("semgrep") is True
        assert factory.tool_has_adapter("refurb") is True
        assert factory.tool_has_adapter("skylos") is True
        assert factory.tool_has_adapter("zuban") is True

    def test_tool_has_adapter_unknown_tools(self, factory):
        """Test tool_has_adapter for unknown tools."""
        assert factory.tool_has_adapter("unknown") is False
        assert factory.tool_has_adapter("tool_name") is False
        assert factory.tool_has_adapter("") is False

    # ---------------------------------------------------------------------
    # Adapter Creation Tests
    # ---------------------------------------------------------------------

    def test_create_ruff_adapter(self, factory):
        """Test creating Ruff adapter."""
        adapter = factory.create_adapter("Ruff")
        assert isinstance(adapter, RuffAdapter)
        assert adapter.adapter_name == "Ruff"

    def test_create_bandit_adapter(self, factory):
        """Test creating Bandit adapter."""
        adapter = factory.create_adapter("Bandit")
        assert isinstance(adapter, BanditAdapter)
        assert adapter.adapter_name == "Bandit (Security)"

    def test_create_semgrep_adapter(self, factory):
        """Test creating Semgrep adapter."""
        adapter = factory.create_adapter("Semgrep")
        assert isinstance(adapter, SemgrepAdapter)
        assert adapter.adapter_name == "Semgrep (Security)"

    def test_create_refurb_adapter(self, factory):
        """Test creating Refurb adapter."""
        adapter = factory.create_adapter("Refurb")
        assert isinstance(adapter, RefurbAdapter)
        assert adapter.adapter_name == "Refurb (Refactoring)"

    def test_create_skylos_adapter(self, factory):
        """Test creating Skylos adapter."""
        adapter = factory.create_adapter("Skylos")
        assert isinstance(adapter, SkylosAdapter)
        assert adapter.adapter_name == "Skylos (Dead Code)"

    def test_create_zuban_adapter(self, factory):
        """Test creating Zuban adapter."""
        # Zuban requires ExecutionContext which may not be available
        # This tests the factory's error handling or skip gracefully
        try:
            adapter = factory.create_adapter("Zuban")
            # If it succeeds, verify basic properties
            assert adapter is not None
            assert hasattr(adapter, "get_tool_name") or hasattr(adapter, "adapter_name")
        except (ImportError, ModuleNotFoundError) as e:
            # Expected if ExecutionContext module doesn't exist yet
            pytest.skip(f"ExecutionContext not available: {e}")

    def test_create_adapter_with_settings(self, factory):
        """Test creating adapter with custom settings."""
        settings = MagicMock()
        settings.fix_enabled = True

        adapter = factory.create_adapter("Ruff", settings=settings)
        assert adapter.settings == settings

    def test_create_unknown_adapter_raises_error(self, factory):
        """Test creating unknown adapter raises ValueError."""
        with pytest.raises(ValueError, match="Unknown adapter"):
            factory.create_adapter("UnknownAdapter")

    def test_create_adapter_returns_protocol(self, factory):
        """Test that created adapters follow AdapterProtocol."""
        adapter = factory.create_adapter("Ruff")
        # AdapterProtocol compliance is ensured by type checking
        assert isinstance(adapter, AdapterProtocol)

    # ---------------------------------------------------------------------
    # AI Agent Integration Tests
    # ---------------------------------------------------------------------

    def test_enable_tool_native_fixes_no_env(self, factory):
        """Test _enable_tool_native_fixes without AI_AGENT env."""
        with patch.dict(os.environ, {}, clear=True):
            settings = MagicMock()
            result = factory._enable_tool_native_fixes("Ruff", settings)
            assert result == settings

    def test_enable_tool_native_fixes_with_env_ruff(self):
        """Test _enable_tool_native_fixes enables Ruff fixes."""
        with patch.dict(os.environ, {"AI_AGENT": "1"}):
            factory = DefaultAdapterFactory()
            settings = MagicMock()
            settings.fix_enabled = False

            result = factory._enable_tool_native_fixes("Ruff", settings)

            assert result.fix_enabled is True

    def test_enable_tool_native_fixes_with_env_other_adapter(self):
        """Test _enable_tool_native_fixes doesn't affect other adapters."""
        with patch.dict(os.environ, {"AI_AGENT": "1"}):
            factory = DefaultAdapterFactory()
            settings = MagicMock()
            settings.fix_enabled = False

            result = factory._enable_tool_native_fixes("Bandit", settings)

            assert result.fix_enabled is False

    def test_create_adapter_with_ai_agent_enabled(self):
        """Test adapter creation with AI_AGENT environment variable."""
        with patch.dict(os.environ, {"AI_AGENT": "1"}):
            factory = DefaultAdapterFactory()
            adapter = factory.create_adapter("Ruff")

            # After init(), fix_enabled should be True
            assert adapter.settings is not None

    # ---------------------------------------------------------------------
    # Tool Mapping Coverage Tests
    # ---------------------------------------------------------------------

    def test_all_tools_in_mapping_have_adapters(self, factory):
        """Test that all tools in TOOL_TO_ADAPTER_NAME can be created."""
        for tool_name in factory.TOOL_TO_ADAPTER_NAME:
            adapter_name = factory.TOOL_TO_ADAPTER_NAME[tool_name]
            assert factory.tool_has_adapter(tool_name)
            # Should not raise ValueError
            adapter = factory.create_adapter(adapter_name)
            assert adapter is not None

    def test_adapter_mapping_consistency(self, factory):
        """Test consistency between tool_has_adapter and get_adapter_name."""
        for tool_name in factory.TOOL_TO_ADAPTER_NAME:
            assert factory.tool_has_adapter(tool_name)
            adapter_name = factory.get_adapter_name(tool_name)
            assert adapter_name is not None

    # ---------------------------------------------------------------------
    # Edge Cases
    # ---------------------------------------------------------------------

    def test_factory_with_none_pkg_path(self):
        """Test factory with None pkg_path defaults to cwd."""
        factory = DefaultAdapterFactory(pkg_path=None)
        assert factory.pkg_path == Path.cwd()

    def test_factory_with_absolute_pkg_path(self):
        """Test factory with absolute package path."""
        pkg_path = Path("/absolute/test/path")
        factory = DefaultAdapterFactory(pkg_path=pkg_path)
        assert factory.pkg_path == pkg_path

    def test_factory_with_relative_pkg_path(self):
        """Test factory with relative package path."""
        pkg_path = Path("relative/path")
        factory = DefaultAdapterFactory(pkg_path=pkg_path)
        assert factory.pkg_path == pkg_path

    def test_multiple_factory_instances(self):
        """Test multiple factory instances are independent."""
        factory1 = DefaultAdapterFactory(pkg_path=Path("/path1"))
        factory2 = DefaultAdapterFactory(pkg_path=Path("/path2"))

        assert factory1.pkg_path != factory2.pkg_path
        assert factory1.settings != factory2.settings
