
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

    status: t.Literal["healthy", "degraded", "unhealthy"]
    message: str
    details: dict[str, t.Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    component_name: str = ""
    check_duration_ms: float | None = None

    def to_dict(self) -> dict[str, t.Any]:
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
        return cls(
            status="unhealthy",
            message=message,
            component_name=component_name,
            details=details or {},
            check_duration_ms=check_duration_ms,
        )

    @property
    def exit_code(self) -> int:
        return {"healthy": 0, "degraded": 1, "unhealthy": 2}[self.status]


@t.runtime_checkable
class HealthCheckProtocol(t.Protocol):

    def health_check(self) -> HealthCheckResult:
        ...

    def is_healthy(self) -> bool:
        ...


@dataclass
class ComponentHealth:

    category: str
    overall_status: t.Literal["healthy", "degraded", "unhealthy"]
    total: int
    healthy: int
    degraded: int
    unhealthy: int
    components: dict[str, HealthCheckResult] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, t.Any]:
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
        healthy = sum(1 for r in results.values() if r.status == "healthy")
        degraded = sum(1 for r in results.values() if r.status == "degraded")
        unhealthy = sum(1 for r in results.values() if r.status == "unhealthy")
        total = len(results)


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
        return {"healthy": 0, "degraded": 1, "unhealthy": 2}[self.overall_status]


@dataclass
class SystemHealthReport:

    overall_status: t.Literal["healthy", "degraded", "unhealthy"]
    categories: dict[str, ComponentHealth] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    summary: str = ""
    metadata: dict[str, t.Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, t.Any]:
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

        if any(h.overall_status == "unhealthy" for h in category_health.values()):
            overall_status: t.Literal["healthy", "degraded", "unhealthy"] = "unhealthy"
        elif any(h.overall_status == "degraded" for h in category_health.values()):
            overall_status = "degraded"
        else:
            overall_status = "healthy"


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
        return {"healthy": 0, "degraded": 1, "unhealthy": 2}[self.overall_status]


def health_check_wrapper(
    component_name: str,
    check_func: t.Callable[[], HealthCheckResult | None],
) -> HealthCheckResult:
    import time

    start_time = time.time()
    try:
        result = check_func()


        if result is None:
            return HealthCheckResult.unhealthy(
                message="Health check returned None (not implemented)",
                component_name=component_name,
                details={
                    "error": "health_check method returned None",
                    "suggestion": "Implement health_check() method to return HealthCheckResult",
                },
                check_duration_ms=(time.time() - start_time) * 1000,
            )


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
