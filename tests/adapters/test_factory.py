"""Tests for DefaultAdapterFactory.

Covers: crackerjack/adapters/factory.py
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.adapters.factory import DefaultAdapterFactory


class TestDefaultAdapterFactory:
    """Tests for DefaultAdapterFactory."""

    def test_tool_to_adapter_name_mapping(self):
        factory = DefaultAdapterFactory()
        assert factory.TOOL_TO_ADAPTER_NAME["ruff"] == "Ruff"
        assert factory.TOOL_TO_ADAPTER_NAME["bandit"] == "Bandit"
        assert factory.TOOL_TO_ADAPTER_NAME["semgrep"] == "Semgrep"
        assert factory.TOOL_TO_ADAPTER_NAME["refurb"] == "Refurb"
        assert factory.TOOL_TO_ADAPTER_NAME["skylos"] == "Skylos"
        assert factory.TOOL_TO_ADAPTER_NAME["zuban"] == "Zuban"
        assert factory.TOOL_TO_ADAPTER_NAME["pyrefly"] == "Pyrefly"
        assert factory.TOOL_TO_ADAPTER_NAME["ty"] == "Ty"

    def test_init_with_defaults(self):
        factory = DefaultAdapterFactory()
        assert factory.settings is None
        assert factory.pkg_path == Path.cwd()

    def test_init_with_settings(self):
        factory = DefaultAdapterFactory(settings={"key": "value"})
        assert factory.settings == {"key": "value"}

    def test_init_with_pkg_path(self):
        custom_path = Path("/custom/path")
        factory = DefaultAdapterFactory(pkg_path=custom_path)
        assert factory.pkg_path == custom_path


class TestIsAIAgentEnabled:
    """Tests for _is_ai_agent_enabled method."""

    def test_ai_agent_disabled_by_default(self):
        env = {k: v for k, v in os.environ.items() if k != "AI_AGENT"}
        with patch.dict(os.environ, env, clear=True):
            factory = DefaultAdapterFactory()
            assert factory._is_ai_agent_enabled() is False

    def test_ai_agent_enabled_when_set(self):
        with patch.dict(os.environ, {"AI_AGENT": "1"}):
            factory = DefaultAdapterFactory()
            assert factory._is_ai_agent_enabled() is True

    def test_ai_agent_disabled_for_other_values(self):
        with patch.dict(os.environ, {"AI_AGENT": "true"}):
            factory = DefaultAdapterFactory()
            assert factory._is_ai_agent_enabled() is False


class TestToolHasAdapter:
    """Tests for tool_has_adapter method."""

    def test_known_tools(self):
        factory = DefaultAdapterFactory()
        assert factory.tool_has_adapter("ruff") is True
        assert factory.tool_has_adapter("bandit") is True
        assert factory.tool_has_adapter("semgrep") is True

    def test_unknown_tools(self):
        factory = DefaultAdapterFactory()
        assert factory.tool_has_adapter("unknown_tool") is False
        assert factory.tool_has_adapter("clang") is False


class TestGetAdapterName:
    """Tests for get_adapter_name method."""

    def test_known_tool_returns_adapter_name(self):
        factory = DefaultAdapterFactory()
        assert factory.get_adapter_name("ruff") == "Ruff"
        assert factory.get_adapter_name("bandit") == "Bandit"

    def test_unknown_tool_returns_none(self):
        factory = DefaultAdapterFactory()
        assert factory.get_adapter_name("unknown") is None


class TestCreateDefaultSettings:
    """Tests for _create_default_settings method."""

    def test_ruff_settings(self):
        factory = DefaultAdapterFactory()
        settings = factory._create_default_settings("Ruff")
        assert settings is not None
        assert settings.tool_name == "ruff"

    def test_bandit_settings(self):
        factory = DefaultAdapterFactory()
        settings = factory._create_default_settings("Bandit")
        assert settings is not None
        assert settings.tool_name == "bandit"

    def test_semgrep_settings(self):
        factory = DefaultAdapterFactory()
        settings = factory._create_default_settings("Semgrep")
        assert settings is not None
        assert settings.tool_name == "semgrep"

    def test_pyrefly_settings(self):
        factory = DefaultAdapterFactory()
        settings = factory._create_default_settings("Pyrefly")
        assert settings is not None

    def test_ty_settings(self):
        factory = DefaultAdapterFactory()
        settings = factory._create_default_settings("Ty")
        assert settings is not None

    def test_unknown_adapter_returns_none(self):
        factory = DefaultAdapterFactory()
        settings = factory._create_default_settings("Unknown")
        assert settings is None


class TestEnableToolNativeFixes:
    """Tests for _enable_tool_native_fixes method."""

    def test_disabled_when_ai_agent_off(self):
        factory = DefaultAdapterFactory()
        settings = MagicMock()
        settings.fix_enabled = False

        result = factory._enable_tool_native_fixes("Ruff", settings)
        assert result.fix_enabled is False

    def test_enables_ruff_fix_when_ai_agent_on(self):
        with patch.dict(os.environ, {"AI_AGENT": "1"}):
            factory = DefaultAdapterFactory()
            settings = MagicMock()
            settings.fix_enabled = False

            result = factory._enable_tool_native_fixes("Ruff", settings)
            assert result.fix_enabled is True

    def test_non_ruff_adapter_unchanged(self):
        with patch.dict(os.environ, {"AI_AGENT": "1"}):
            factory = DefaultAdapterFactory()
            settings = MagicMock()
            settings.fix_enabled = False

            result = factory._enable_tool_native_fixes("Bandit", settings)
            assert result.fix_enabled is False


class TestResolveSettings:
    """Tests for _resolve_settings method."""

    def test_uses_provided_settings(self):
        factory = DefaultAdapterFactory()
        provided = MagicMock()
        result = factory._resolve_settings("Ruff", provided)
        assert result is provided

    def test_uses_factory_settings_when_none_provided(self):
        factory = DefaultAdapterFactory(settings={"key": "value"})
        result = factory._resolve_settings("Ruff", None)
        assert result == {"key": "value"}

    def test_creates_default_when_ai_agent_enabled(self):
        with patch.dict(os.environ, {"AI_AGENT": "1"}):
            factory = DefaultAdapterFactory()
            result = factory._resolve_settings("Ruff", None)
            assert result is not None

    def test_returns_none_when_no_settings_and_ai_agent_off(self):
        factory = DefaultAdapterFactory()
        result = factory._resolve_settings("Ruff", None)
        assert result is None


class TestInstantiateAdapter:
    """Tests for _instantiate_adapter method."""

    def test_instantiates_ruff_adapter(self):
        factory = DefaultAdapterFactory()
        adapter = factory._instantiate_adapter("Ruff", None)
        assert adapter is not None
        assert adapter.__class__.__name__ == "RuffAdapter"

    def test_instantiates_bandit_adapter(self):
        factory = DefaultAdapterFactory()
        adapter = factory._instantiate_adapter("Bandit", None)
        assert adapter is not None
        assert adapter.__class__.__name__ == "BanditAdapter"

    def test_instantiates_semgrep_adapter(self):
        factory = DefaultAdapterFactory()
        adapter = factory._instantiate_adapter("Semgrep", None)
        assert adapter is not None
        assert adapter.__class__.__name__ == "SemgrepAdapter"

    def test_unknown_adapter_returns_none(self):
        factory = DefaultAdapterFactory()
        adapter = factory._instantiate_adapter("UnknownAdapter", None)
        assert adapter is None


class TestCreateAdapter:
    """Tests for create_adapter method."""

    def test_creates_ruff_adapter(self):
        factory = DefaultAdapterFactory()
        adapter = factory.create_adapter("Ruff")
        assert adapter is not None

    def test_creates_fallback_chain_for_ai_adapters(self):
        factory = DefaultAdapterFactory()
        adapter = factory.create_adapter("Claude AI")
        assert adapter is not None

    def test_creates_fallback_chain_for_fallback_chain(self):
        factory = DefaultAdapterFactory()
        adapter = factory.create_adapter("FallbackChain")
        assert adapter is not None

    def test_raises_for_unknown_adapter(self):
        factory = DefaultAdapterFactory()
        with pytest.raises(ValueError, match="Unknown adapter"):
            factory.create_adapter("NonExistentAdapter")

    def test_create_adapter_with_custom_settings(self):
        factory = DefaultAdapterFactory()
        custom_settings = MagicMock()
        custom_settings.tool_name = "ruff"
        adapter = factory.create_adapter("Ruff", settings=custom_settings)
        assert adapter is not None
