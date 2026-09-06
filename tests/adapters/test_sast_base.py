"""Tests for ``crackerjack.adapters.sast._base``.

Covers the ``SASTAdapterProtocol`` runtime-checkable protocol and the
``SASTAdapter`` alias.
"""

from __future__ import annotations

from typing import Protocol

from crackerjack.adapters.sast._base import SASTAdapter, SASTAdapterProtocol


def test_sast_adapter_protocol_is_runtime_checkable() -> None:
    """The protocol carries ``@runtime_checkable`` so ``isinstance`` works."""
    assert getattr(SASTAdapterProtocol, "_is_runtime_protocol", False) is True


def test_sast_adapter_is_alias_for_protocol() -> None:
    """The module exports ``SASTAdapter`` as a public alias for the protocol."""
    assert SASTAdapter is SASTAdapterProtocol


def test_sast_adapter_protocol_exposes_expected_members() -> None:
    """The protocol declares the SAST adapter contract surface.

    Note: ``settings`` is only a data-attribute annotation on the protocol
    (not a method or property), so it appears in ``__annotations__`` but not
    in ``dir()`` and is verified separately below.
    """
    expected = {
        "adapter_name",
        "module_id",
        "tool_name",
        "init",
        "build_command",
        "check",
        "parse_output",
        "_get_check_type",
        "get_default_config",
    }
    actual = set(dir(SASTAdapterProtocol))
    missing = expected - actual
    assert not missing, f"protocol missing members: {sorted(missing)}"


def test_sast_adapter_protocol_declares_settings_attribute() -> None:
    """``settings`` is declared as a typed data-attribute on the protocol."""
    annotations = getattr(SASTAdapterProtocol, "__annotations__", {})
    assert "settings" in annotations
    # The annotation should reference the typed ``ToolAdapterSettings | None``
    assert "ToolAdapterSettings" in annotations["settings"]


def test_sast_adapter_protocol_rejects_unrelated_objects() -> None:
    """isinstance(obj, Protocol) is False for objects missing protocol methods."""
    assert not isinstance(object(), SASTAdapterProtocol)
    assert not isinstance("string", SASTAdapterProtocol)
    assert not isinstance(42, SASTAdapterProtocol)


def test_sast_adapter_protocol_subclass_protocol_relationship() -> None:
    """``SASTAdapterProtocol`` is a legitimate ``typing.Protocol`` subclass."""
    assert issubclass(SASTAdapterProtocol, Protocol)
