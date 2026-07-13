"""Tests for the new CrackerjackSettings.eventbridge field.

Per the deferred-items review (post-Phase 6):
'CrackerjackSettings.eventbridge field missing — operator YAML toggle is
currently inert in Crackerjack. Akosha's AksoshaConfig already has the
field. A follow-on plan should add the EventBridgeSettings Pydantic
model to Crackerjack and migrate CrackerjackSettings to the
OneiricMCPConfig base (separate cross-cutting change).'

The base-class migration is out of scope; this test verifies the
field exists and is bound to a working Pydantic model with sane
defaults (disabled by default for backward compat).
"""
from __future__ import annotations

import importlib

import pytest


def _import_settings_class() -> type:
    """Import ``EventBridgeSettings`` from the settings module.

    Defensive against the eventual ``crackerjack.config.settings``
    module split — tests should follow the class, not the import path.
    """
    settings_module = importlib.import_module("crackerjack.config.settings")
    assert hasattr(settings_module, "EventBridgeSettings"), (
        "crackerjack.config.settings must export EventBridgeSettings "
        "(deferred item #2: CrackerjackSettings.eventbridge field missing)"
    )
    return settings_module.EventBridgeSettings


def _import_crackerjack_settings_class() -> type:
    settings_module = importlib.import_module("crackerjack.config.settings")
    return settings_module.CrackerjackSettings


def test_eventbridge_settings_class_exists() -> None:
    cls = _import_settings_class()
    assert cls.__name__ == "EventBridgeSettings"


def test_eventbridge_settings_defaults_to_disabled() -> None:
    """Master toggle defaults to False -- backward compat with existing installs."""
    cls = _import_settings_class()
    s = cls()
    assert s.enabled is False


def test_eventbridge_settings_endpoint_default_is_empty_string() -> None:
    cls = _import_settings_class()
    s = cls()
    assert s.endpoint == ""


def test_eventbridge_settings_dry_run_defaults_true() -> None:
    """dry_run=True keeps the publisher inert unless operators opt in."""
    cls = _import_settings_class()
    s = cls()
    assert s.dry_run is True


def test_crackerjack_settings_exposes_eventbridge_field() -> None:
    """The deferred item: CrackerjackSettings must have an eventbridge field."""
    cls = _import_crackerjack_settings_class()
    s = cls()
    # The field exists
    assert hasattr(s, "eventbridge"), (
        "CrackerjackSettings must expose an eventbridge field"
    )
    # The field is bound to EventBridgeSettings (not a raw bool)
    assert s.eventbridge.__class__.__name__ == "EventBridgeSettings"


def test_crackerjack_settings_eventbridge_field_is_default_instance() -> None:
    """Default-constructed CrackerjackSettings has disabled eventbridge."""
    cls = _import_crackerjack_settings_class()
    s = cls()
    assert s.eventbridge.enabled is False
    assert s.eventbridge.dry_run is True


def test_eventbridge_settings_can_be_enabled_at_construction() -> None:
    """Constructing CrackerjackSettings(eventbridge=EventBridgeSettings(enabled=True))
    must produce a settings object with eventbridge.enabled == True.

    This is the operator-toggle path: set enabled=true in YAML / at
    construction, and the publisher emits real events.
    """
    cls = _import_crackerjack_settings_class()
    eb_cls = _import_settings_class()
    s = cls(eventbridge=eb_cls(enabled=True, dry_run=False, endpoint="redis://localhost:6379"))
    assert s.eventbridge.enabled is True
    assert s.eventbridge.dry_run is False
    assert s.eventbridge.endpoint == "redis://localhost:6379"
