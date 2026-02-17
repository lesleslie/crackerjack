import logging
import typing as t

from crackerjack.adapters._qa_adapter_base import QAAdapterBase

logger = logging.getLogger(__name__)


class AdapterRegistry:
    _adapters: dict[str, type[QAAdapterBase]] = {}

    @classmethod
    def register(cls, name: str, adapter_class: type[QAAdapterBase]) -> None:
        if name in cls._adapters:
            logger.warning(
                f"QAAdapterBase '{name}' already registered, skipping duplicate registration"
            )
            return

        cls._adapters[name] = adapter_class
        logger.debug(f"Registered adapter: {name}")

    @classmethod
    def create(cls, name: str, settings: t.Any | None = None) -> QAAdapterBase:
        if name not in cls._adapters:
            available = ", ".join(sorted(cls._adapters.keys()))
            raise ValueError(f"Unknown adapter: {name}. Available: {available}")

        adapter_class = cls._adapters[name]
        return adapter_class(settings)

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name in cls._adapters

    @classmethod
    def list_adapters(cls) -> list[str]:
        return sorted(cls._adapters.keys())

    @classmethod
    def get_adapter_info(cls, name: str) -> dict[str, t.Any] | None:
        if name not in cls._adapters:
            return None

        adapter_class = cls._adapters[name]
        return {
            "name": name,
            "class": adapter_class.__name__,
            "module": adapter_class.__module__,
        }


def get_adapter_registry() -> AdapterRegistry:
    return AdapterRegistry()


__all__ = [
    "AdapterRegistry",
    "get_adapter_registry",
]
