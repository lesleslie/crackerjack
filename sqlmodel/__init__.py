from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_MISSING = object()


@dataclass(slots=True)
class FieldInfo:
    default: Any = _MISSING
    default_factory: Callable[[], Any] | None = None


def Field(
    *,
    default: Any = _MISSING,
    default_factory: Callable[[], Any] | None = None,
    **_: Any,
) -> Any:
    return FieldInfo(default=default, default_factory=default_factory)


class SQLModel:
    def __init_subclass__(cls, **_: Any) -> None:
        super().__init_subclass__()

    def __init__(self, **kwargs: Any) -> None:
        annotations = getattr(self, "__annotations__", {})
        for name in annotations:
            if name in kwargs:
                value = kwargs.pop(name)
            else:
                value = self._get_default_value(name)
            setattr(self, name, value)
        for name, value in kwargs.items():
            setattr(self, name, value)

    @classmethod
    def _get_default_value(cls, name: str) -> Any:
        raw = getattr(cls, name, _MISSING)
        if isinstance(raw, FieldInfo):
            if raw.default_factory is not None:
                return raw.default_factory()
            if raw.default is not _MISSING:
                return raw.default
            return None
        if raw is not _MISSING:
            return raw
        return None

    def __repr__(self) -> str:
        fields = ", ".join(
            f"{name}={getattr(self, name)!r}"
            for name in getattr(self, "__annotations__", {})
        )
        return f"{self.__class__.__name__}({fields})"

    __str__ = __repr__
