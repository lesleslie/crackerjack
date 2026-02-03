"""Health check models and protocols for Crackerjack components.

This module provides standardized health check interfaces and result models
for all system components: adapters, managers, and services.
"""

from __future__ import annotations

import logging
import typing as t
from dataclasses import dataclass, field
from datetime import UTC, datetime

if t.TYPE_CHECKING:
    from collections.abc import Mapping


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthCheckResult:
    """Result of a health check for a single component.

    Attributes:
        status: Health status - "healthy", "degraded", or "unhealthy"
        message: Human-readable status message
        details: Additional diagnostic information
        timestamp: When the health check was performed
        component_name: Name of the component checked
        check_duration_ms: How long the check took (optional)
    """

    status: t.Literal["healthy", "degraded", "unhealthy"]
    message: str
    details: dict[str, t.Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    component_name: str = ""
    check_duration_ms: float | None = None

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "component_name": self.component_name,
            "check_duration_ms": self.check_duration_ms,
        }

    @classmethod
    def healthy(
        cls,
        message: str = "Component is healthy",
        component_name: str = "",
        details: dict[str, t.Any] | None = None,
        check_duration_ms: float | None = None,
    ) -> HealthCheckResult:
        """Create a healthy result."""
        return cls(
            status="healthy",
            message=message,
            component_name=component_name,
            details=details or {},
            check_duration_ms=check_duration_ms,
        )

    @classmethod
    def degraded(
        cls,
        message: str,
        component_name: str = "",
        details: dict[str, t.Any] | None = None,
        check_duration_ms: float | None = None,
    ) -> HealthCheckResult:
        """Create a degraded result."""
        return cls(
            status="degraded",
            message=message,
            component_name=component_name,
            details=details or {},
            check_duration_ms=check_duration_ms,
        )

    @classmethod
    def unhealthy(
        cls,
        message: str,
        component_name: str = "",
        details: dict[str, t.Any] | None = None,
        check_duration_ms: float | None = None,
    ) -> HealthCheckResult:
        """Create an unhealthy result."""
        return cls(
            status="unhealthy",
            message=message,
            component_name=component_name,
            details=details or {},
            check_duration_ms=check_duration_ms,
        )

    @property
    def exit_code(self) -> int:
        """Get the appropriate exit code for this health status."""
        return {"healthy": 0, "degraded": 1, "unhealthy": 2}[self.status]


@t.runtime_checkable
class HealthCheckProtocol(t.Protocol):
    """Protocol for components that can perform health checks.

    Any component (adapter, manager, service) that wants to report its health
    should implement this protocol.
    """

    def health_check(self) -> HealthCheckResult:
        """Perform a health check and return the result.

        Returns:
            HealthCheckResult: The health status of the component

        Example:
            >>> def health_check(self) -> HealthCheckResult:
            ...     try:
            ...         # Check component health
            ...         if self.is_healthy():
            ...             return HealthCheckResult.healthy(
            ...                 message="Component is operational",
            ...                 component_name=self.__class__.__name__
            ...             )
            ...         else:
            ...             return HealthCheckResult.unhealthy(
            ...                 message="Component is not operational",
            ...                 component_name=self.__class__.__name__
            ...             )
            ...     except Exception as e:
            ...         return HealthCheckResult.unhealthy(
            ...             message=f"Health check failed: {e}",
            ...             component_name=self.__class__.__name__,
            ...             details={"error": str(e)}
            ...         )
        """
        ...

    def is_healthy(self) -> bool:
        """Quick check if component is healthy (no details).

        This is a simpler version of health_check() for fast checks.
        Returns True if healthy, False otherwise.

        Returns:
            bool: True if healthy, False otherwise
        """
        ...


@dataclass
class ComponentHealth:
    """Aggregated health status for a group of components.

    Attributes:
        category: Component category (adapters, managers, services)
        overall_status: Overall health status across all components
        total: Total number of components checked
        healthy: Number of healthy components
        degraded: Number of degraded components
        unhealthy: Number of unhealthy components
        components: Individual component results
        timestamp: When the health check was performed
    """

    category: str
    overall_status: t.Literal["healthy", "degraded", "unhealthy"]
    total: int
    healthy: int
    degraded: int
    unhealthy: int
    components: dict[str, HealthCheckResult] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category,
            "overall_status": self.overall_status,
            "total": self.total,
            "healthy": self.healthy,
            "degraded": self.degraded,
            "unhealthy": self.unhealthy,
            "components": {
                name: result.to_dict() for name, result in self.components.items()
            },
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_results(
        cls,
        category: str,
        results: Mapping[str, HealthCheckResult],
    ) -> ComponentHealth:
        """Create aggregated health from individual results.

        Args:
            category: Component category name
            results: Mapping of component names to health results

        Returns:
            ComponentHealth: Aggregated health status
        """
        healthy = sum(1 for r in results.values() if r.status == "healthy")
        degraded = sum(1 for r in results.values() if r.status == "degraded")
        unhealthy = sum(1 for r in results.values() if r.status == "unhealthy")
        total = len(results)

        # Determine overall status
        if unhealthy > 0:
            overall_status: t.Literal["healthy", "degraded", "unhealthy"] = "unhealthy"
        elif degraded > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return cls(
            category=category,
            overall_status=overall_status,
            total=total,
            healthy=healthy,
            degraded=degraded,
            unhealthy=unhealthy,
            components=dict(results),
        )

    @property
    def exit_code(self) -> int:
        """Get the appropriate exit code for this overall status."""
        return {"healthy": 0, "degraded": 1, "unhealthy": 2}[self.overall_status]


@dataclass
class SystemHealthReport:
    """Complete system health report across all component categories.

    Attributes:
        overall_status: Overall system health status
        categories: Health status by category
        timestamp: When the report was generated
        summary: Human-readable summary
        metadata: Additional metadata (version, environment, etc.)
    """

    overall_status: t.Literal["healthy", "degraded", "unhealthy"]
    categories: dict[str, ComponentHealth] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    summary: str = ""
    metadata: dict[str, t.Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_status": self.overall_status,
            "categories": {
                name: health.to_dict() for name, health in self.categories.items()
            },
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_category_health(
        cls,
        category_health: Mapping[str, ComponentHealth],
        metadata: dict[str, t.Any] | None = None,
    ) -> SystemHealthReport:
        """Create system health report from category health data.

        Args:
            category_health: Mapping of category names to health data
            metadata: Optional metadata to include

        Returns:
            SystemHealthReport: Complete system health report
        """
        # Determine overall status
        if any(h.overall_status == "unhealthy" for h in category_health.values()):
            overall_status: t.Literal["healthy", "degraded", "unhealthy"] = "unhealthy"
        elif any(h.overall_status == "degraded" for h in category_health.values()):
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        # Generate summary
        total_components = sum(h.total for h in category_health.values())
        total_healthy = sum(h.healthy for h in category_health.values())
        total_degraded = sum(h.degraded for h in category_health.values())
        total_unhealthy = sum(h.unhealthy for h in category_health.values())

        summary_parts = []
        if total_healthy == total_components:
            summary_parts.append(f"All {total_components} components healthy")
        else:
            if total_healthy > 0:
                summary_parts.append(f"{total_healthy} healthy")
            if total_degraded > 0:
                summary_parts.append(f"{total_degraded} degraded")
            if total_unhealthy > 0:
                summary_parts.append(f"{total_unhealthy} unhealthy")

        summary = ", ".join(summary_parts) if summary_parts else "No components checked"

        return cls(
            overall_status=overall_status,
            categories=dict(category_health),
            summary=summary,
            metadata=metadata or {},
        )

    @property
    def exit_code(self) -> int:
        """Get the appropriate exit code for the overall system status."""
        return {"healthy": 0, "degraded": 1, "unhealthy": 2}[self.overall_status]


def health_check_wrapper(
    component_name: str,
    check_func: t.Callable[[], HealthCheckResult],
) -> HealthCheckResult:
    """Wrapper for health check functions with error handling.

    Args:
        component_name: Name of the component being checked
        check_func: Function that performs the health check

    Returns:
        HealthCheckResult: Result of the health check, or unhealthy if exception

    Example:
        >>> def check_my_component() -> HealthCheckResult:
        ...     # Perform health check logic
        ...     return HealthCheckResult.healthy(...)
        >>>
        >>> result = health_check_wrapper("MyComponent", check_my_component)
    """
    import time

    start_time = time.time()
    try:
        result = check_func()
        # Ensure component_name is set
        if not result.component_name:
            return HealthCheckResult(
                status=result.status,
                message=result.message,
                details=result.details,
                timestamp=result.timestamp,
                component_name=component_name,
                check_duration_ms=result.check_duration_ms,
            )
        return result
    except Exception as e:
        logger.exception("Health check failed for %s", component_name)
        return HealthCheckResult.unhealthy(
            message=f"Health check failed with exception: {e!s}",
            component_name=component_name,
            details={
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            check_duration_ms=(time.time() - start_time) * 1000,
        )


__all__ = [
    "ComponentHealth",
    "HealthCheckProtocol",
    "HealthCheckResult",
    "SystemHealthReport",
    "health_check_wrapper",
]
