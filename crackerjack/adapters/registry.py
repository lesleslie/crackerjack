"""Adapter Registry for Plugin Architecture.

This module provides a registry pattern implementation that allows QA adapters
to self-register, eliminating the need to modify factory code when adding new adapters.

This implements the Open/Closed Principle: the code is closed for modification
but open for extension via registration.
"""

import logging
import typing as t

from crackerjack.adapters._qa_adapter_base import QAAdapterBase

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry for QA adapters with self-registration capability.

    This implements the Open/Closed Principle by allowing adapters to register
    themselves without requiring modification of core factory code.

    Usage:

        AdapterRegistry.register("ruff", RuffQAAdapterBase)


        adapter = AdapterRegistry.create("ruff", settings)
    """

    _adapters: dict[str, type[QAAdapterBase]] = {}

    @classmethod
    def register(cls, name: str, adapter_class: type[QAAdapterBase]) -> None:
        """Register an adapter class.

        Args:
            name: Unique name for the adapter
            adapter_class: QAAdapterBase class (not instance)

        Raises:
            ValueError: If adapter name already registered

        Example:
            >>> AdapterRegistry.register("ruff", RuffQAAdapterBase)
        """
        if name in cls._adapters:
            logger.warning(
                f"QAAdapterBase '{name}' already registered, skipping duplicate registration"
            )
            return

        cls._adapters[name] = adapter_class
        logger.debug(f"Registered adapter: {name}")

    @classmethod
    def create(cls, name: str, settings: t.Any | None = None) -> QAAdapterBase:
        """Create an adapter instance by name.

        Args:
            name: Registered adapter name
            settings: Optional settings to pass to adapter constructor

        Returns:
            QAAdapterBase instance

        Raises:
            ValueError: If adapter name not registered

        Example:
            >>> adapter = AdapterRegistry.create("ruff", settings)
        """
        if name not in cls._adapters:
            available = ", ".join(sorted(cls._adapters.keys()))
            raise ValueError(f"Unknown adapter: {name}. Available: {available}")

        adapter_class = cls._adapters[name]
        return adapter_class(settings)

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if an adapter is registered.

        Args:
            name: QAAdapterBase name to check

        Returns:
            True if adapter is registered, False otherwise
        """
        return name in cls._adapters

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names.

        Returns:
            Sorted list of adapter names

        Example:
            >>> adapters = AdapterRegistry.list_adapters()
            >>> print(f"Available adapters: {', '.join(adapters)}")
        """
        return sorted(cls._adapters.keys())

    @classmethod
    def get_adapter_info(cls, name: str) -> dict[str, t.Any] | None:
        """Get information about a registered adapter.

        Args:
            name: QAAdapterBase name

        Returns:
            Dictionary with adapter info, or None if not found

        Example:
            >>> info = AdapterRegistry.get_adapter_info("ruff")
            >>> print(f"QAAdapterBase: {info['name']}, Class: {info['class']}")
        """
        if name not in cls._adapters:
            return None

        adapter_class = cls._adapters[name]
        return {
            "name": name,
            "class": adapter_class.__name__,
            "module": adapter_class.__module__,
        }


def get_adapter_registry() -> AdapterRegistry:
    """Get the singleton adapter registry instance.

    Returns:
        AdapterRegistry instance

    Example:
        >>> registry = get_adapter_registry()
        >>> adapter = registry.create("ruff", settings)
    """
    return AdapterRegistry()


__all__ = [
    "AdapterRegistry",
    "get_adapter_registry",
]
