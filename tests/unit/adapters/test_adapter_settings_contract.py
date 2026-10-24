"""Regression tests for the adapter settings contract.

Every tool adapter declares its settings as a *narrowed* type -- e.g.
``BanditAdapter`` declares ``BanditSettings`` and reads adapter-specific
fields such as ``severity_level`` off it. That narrowing is only sound if
the adapter is never handed a foreign settings object.

Two ways that contract was broken:

1. ``DefaultAdapterFactory._create_default_settings`` returned a plain
   ``ToolAdapterSettings`` for Bandit / Semgrep / Refurb, so in AI-agent
   mode those adapters got an object without their own fields and raised
   ``AttributeError: 'ToolAdapterSettings' object has no attribute
   'severity_level'``.

2. ``DefaultAdapterFactory._resolve_settings`` injected the factory-level
   settings into *any* adapter. The MCP server constructs the factory with
   the application settings (``CrackerjackSettings``), which are not
   adapter settings at all, so every adapter raised ``AttributeError`` on
   its first settings access -- and the caller swallowed that into a
   warning, so the adapters silently never worked.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolAdapterSettings
from crackerjack.adapters.factory import DefaultAdapterFactory
from crackerjack.adapters.format.ruff import RuffSettings
from crackerjack.adapters.refactor.refurb import RefurbSettings
from crackerjack.adapters.sast.bandit import BanditSettings
from crackerjack.adapters.sast.semgrep import SemgrepSettings
from crackerjack.adapters.type.pyrefly import PyreflySettings
from crackerjack.adapters.type.ty import TySettings

# The adapter name -> the settings class that adapter declares.
ADAPTER_SETTINGS: dict[str, type[ToolAdapterSettings]] = {
    "Ruff": RuffSettings,
    "Bandit": BanditSettings,
    "Semgrep": SemgrepSettings,
    "Refurb": RefurbSettings,
    "Pyrefly": PyreflySettings,
    "Ty": TySettings,
}


class TestDefaultSettingsAreAdapterSpecific:
    """``_create_default_settings`` must return the adapter's own class."""

    @pytest.mark.parametrize("adapter_name", sorted(ADAPTER_SETTINGS))
    def test_default_settings_match_declared_type(
        self, adapter_name: str
    ) -> None:
        factory = DefaultAdapterFactory()
        settings = factory._create_default_settings(adapter_name)

        assert isinstance(settings, ADAPTER_SETTINGS[adapter_name])

    @pytest.mark.parametrize("adapter_name", sorted(ADAPTER_SETTINGS))
    def test_ai_agent_mode_uses_adapter_specific_settings(
        self, adapter_name: str
    ) -> None:
        """AI-agent mode resolves the same adapter-specific settings."""
        factory = DefaultAdapterFactory()
        env = {k: v for k, v in os.environ.items() if k != "AI_AGENT"}
        with patch.dict(os.environ, {**env, "AI_AGENT": "1"}):
            settings = factory._resolve_settings(adapter_name, None)

        assert isinstance(settings, ADAPTER_SETTINGS[adapter_name])


class TestResolveSettingsDoesNotInjectForeignSettings:
    """Factory-level settings must only be used when they are tool settings."""

    def test_application_settings_are_not_injected(self) -> None:
        """App-level settings are not adapter settings -- do not inject them.

        This mirrors ``crackerjack/server.py``, which builds the factory with
        the application settings.
        """

        class AppSettings:
            """Stand-in for the application-level settings object."""

            enabled: bool = True

        app_settings = AppSettings()
        factory = DefaultAdapterFactory(settings=app_settings)

        for adapter_name in ADAPTER_SETTINGS:
            resolved = factory._resolve_settings(adapter_name, None)
            assert resolved is None, (
                f"{adapter_name} received {type(resolved).__name__} "
                "instead of building its own settings"
            )

    def test_tool_settings_are_injected(self) -> None:
        """A genuine tool settings object is still passed through."""
        ruff_settings = RuffSettings()
        factory = DefaultAdapterFactory(settings=ruff_settings)

        assert factory._resolve_settings("Ruff", None) is ruff_settings

    def test_explicit_settings_win(self) -> None:
        """An explicitly supplied settings object always wins."""
        factory = DefaultAdapterFactory(settings=RuffSettings())
        explicit = BanditSettings()

        assert factory._resolve_settings("Bandit", explicit) is explicit

    @pytest.mark.parametrize("adapter_name", sorted(ADAPTER_SETTINGS))
    def test_created_adapter_never_gets_foreign_settings(
        self, adapter_name: str
    ) -> None:
        """The created adapter's settings are its own class or None."""

        class AppSettings:
            """Stand-in for the application-level settings object."""

        factory = DefaultAdapterFactory(settings=AppSettings())
        adapter = factory.create_adapter(adapter_name)

        assert adapter.settings is None or isinstance(
            adapter.settings, ADAPTER_SETTINGS[adapter_name]
        )


class TestServerStyleFactoryBuildsWorkingAdapters:
    """The ``server.py`` construction pattern yields usable adapters."""

    @pytest.mark.parametrize("adapter_name", sorted(ADAPTER_SETTINGS))
    def test_adapter_builds_its_own_settings(self, adapter_name: str) -> None:
        """With app-level settings, the adapter still builds valid settings."""
        from crackerjack.config.settings import CrackerjackSettings

        factory = DefaultAdapterFactory(CrackerjackSettings(), Path.cwd())
        adapter = factory.create_adapter(adapter_name)

        assert adapter.settings is None

        # The settings the adapter will install must be its own class, so
        # adapter-specific field access cannot fail.
        default = factory._create_default_settings(adapter_name)
        assert isinstance(default, ADAPTER_SETTINGS[adapter_name])
        for field in ("timeout_seconds", "max_workers"):
            assert getattr(default, field) is not None
