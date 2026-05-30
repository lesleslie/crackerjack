"""Tests for AdapterRegistry.

Covers: crackerjack/adapters/registry.py
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from crackerjack.adapters.registry import AdapterRegistry, get_adapter_registry


class TestAdapterRegistry:
    """Tests for AdapterRegistry class."""

    def setup_method(self):
        """Reset registry state before each test."""
        AdapterRegistry._adapters.clear()

    def test_register_adds_adapter(self):
        class DummyAdapter:
            pass

        AdapterRegistry.register("TestAdapter", DummyAdapter)
        assert "TestAdapter" in AdapterRegistry._adapters
        assert AdapterRegistry._adapters["TestAdapter"] == DummyAdapter

    def test_register_warns_on_duplicate(self, caplog):
        caplog.set_level(logging.WARNING)

        class DummyAdapter:
            pass

        AdapterRegistry.register("TestAdapter", DummyAdapter)
        AdapterRegistry.register("TestAdapter", DummyAdapter)
        assert any("already registered" in r.message for r in caplog.records)

    def test_register_does_not_overwrite_duplicate(self):

        class DummyAdapter:
            pass

        AdapterRegistry.register("TestAdapter", DummyAdapter)
        original = AdapterRegistry._adapters["TestAdapter"]
        AdapterRegistry.register("TestAdapter", DummyAdapter)
        assert AdapterRegistry._adapters["TestAdapter"] is original

    def test_create_returns_instance(self):
        # Register a simple class that can be instantiated
        class TestAdapter:
            def __init__(self, settings=None):
                self.settings = settings

        AdapterRegistry.register("TestAdapter", TestAdapter)
        adapter = AdapterRegistry.create("TestAdapter")
        assert isinstance(adapter, TestAdapter)

    def test_create_with_settings(self):
        class TestAdapter:
            def __init__(self, settings=None):
                self.settings = settings

        AdapterRegistry.register("TestAdapter", TestAdapter)
        settings = MagicMock()
        adapter = AdapterRegistry.create("TestAdapter", settings=settings)
        assert adapter.settings == settings

    def test_create_unknown_adapter_raises(self):
        with pytest.raises(ValueError, match="Unknown adapter"):
            AdapterRegistry.create("NonExistent")

    def test_create_error_includes_available_adapters(self):
        class TestAdapter:
            pass

        AdapterRegistry.register("KnownAdapter", TestAdapter)
        with pytest.raises(ValueError) as exc_info:
            AdapterRegistry.create("Unknown")
        assert "KnownAdapter" in str(exc_info.value)

    def test_is_registered_true(self):
        class DummyAdapter:
            pass

        AdapterRegistry.register("TestAdapter", DummyAdapter)
        assert AdapterRegistry.is_registered("TestAdapter") is True

    def test_is_registered_false(self):
        assert AdapterRegistry.is_registered("NonExistent") is False

    def test_list_adapters_returns_sorted(self):
        class DummyAdapter:
            pass

        AdapterRegistry.register("Zebra", DummyAdapter)
        AdapterRegistry.register("Alpha", DummyAdapter)
        AdapterRegistry.register("Middle", DummyAdapter)
        adapters = AdapterRegistry.list_adapters()
        assert adapters == ["Alpha", "Middle", "Zebra"]

    def test_list_adapters_empty(self):
        adapters = AdapterRegistry.list_adapters()
        assert adapters == []

    def test_get_adapter_info_existing(self):
        class TestAdapter:
            pass

        AdapterRegistry.register("TestAdapter", TestAdapter)
        info = AdapterRegistry.get_adapter_info("TestAdapter")
        assert info is not None
        assert info["name"] == "TestAdapter"
        assert info["class"] == "TestAdapter"

    def test_get_adapter_info_nonexistent(self):
        info = AdapterRegistry.get_adapter_info("NonExistent")
        assert info is None


class TestGetAdapterRegistry:
    """Tests for get_adapter_registry function."""

    def test_returns_adapter_registry_instance(self):
        registry = get_adapter_registry()
        assert isinstance(registry, AdapterRegistry)

    def test_returns_new_instance_each_time(self):
        # Note: get_adapter_registry returns a new instance each call
        registry1 = get_adapter_registry()
        registry2 = get_adapter_registry()
        # These are different objects
        assert registry1 is not registry2
