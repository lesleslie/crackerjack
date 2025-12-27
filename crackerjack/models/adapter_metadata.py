"""Adapter metadata and status definitions.

Provides type-safe enums and metadata structures for QA adapters,
replacing ACB's adapter metadata with Crackerjack-specific implementations.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class AdapterStatus(StrEnum):
    """Adapter lifecycle status.

    Indicates the stability and readiness level of an adapter.
    """

    STABLE = "stable"  # Production-ready, well-tested
    BETA = "beta"  # Functional but may have rough edges
    ALPHA = "alpha"  # Early development, experimental
    DEPRECATED = "deprecated"  # Scheduled for removal


@dataclass
class AdapterMetadata:
    """Metadata for QA adapter registration.

    Contains descriptive information about an adapter for discovery,
    documentation, and health monitoring.

    Attributes:
        module_id: Static UUID7 uniquely identifying this adapter
        name: Human-readable adapter name
        category: Adapter category (format, lint, sast, type, security, etc.)
        version: Semantic version string
        status: Lifecycle status (stable, beta, alpha, deprecated)
        description: Brief description of adapter functionality
    """

    module_id: UUID
    name: str
    category: str
    version: str
    status: AdapterStatus
    description: str = ""

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "module_id": str(self.module_id),
            "name": self.name,
            "category": self.category,
            "version": self.version,
            "status": self.status.value,
            "description": self.description,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.name} v{self.version} ({self.status.value})"


__all__ = ["AdapterStatus", "AdapterMetadata"]
