from __future__ import annotations

import typing as t
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class AdapterStatus(StrEnum):
    STABLE = "stable"
    BETA = "beta"
    ALPHA = "alpha"
    DEPRECATED = "deprecated"


@dataclass
class AdapterMetadata:
    module_id: UUID
    name: str
    category: str
    version: str
    status: AdapterStatus
    description: str = ""

    def dict(self) -> dict[str, t.Any]:  # type: ignore[valid-type]
        return self.to_dict()

    def to_dict(self) -> dict[str, t.Any]:  # type: ignore[valid-type]
        return {
            "module_id": str(self.module_id),
            "name": self.name,
            "category": self.category,
            "version": self.version,
            "status": self.status.value,
            "description": self.description,
        }

    def __str__(self) -> str:
        return f"{self.name} v{self.version} ({self.status.value})"


__all__ = ["AdapterStatus", "AdapterMetadata"]
