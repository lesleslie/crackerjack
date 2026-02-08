"""Type-safe status enums for crackerjack.

This module provides enum-based status types to replace string comparisons
throughout the codebase, improving type safety and eliminating the
Open/Closed Principle violation where adding new statuses requires
modifying if-chains.

All enums support serialization to/from strings for JSON compatibility.
"""

from enum import Enum


class HealthStatus(str, Enum):
    """Health check status.

    Usage:
        >>> result = HealthCheckResult(status=HealthStatus.HEALTHY)
        >>> if result.status == HealthStatus.HEALTHY:
        ...     print("Component is healthy")
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

    @classmethod
    def from_string(cls, value: str) -> "HealthStatus":
        """Parse string to enum, case-insensitive.

        Args:
            value: String status value

        Returns:
            Corresponding HealthStatus enum

        Raises:
            ValueError: If value is not a valid status
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(s.value for s in cls)
            raise ValueError(
                f"Invalid health status: {value!r}. Valid values: {valid}"
            ) from None

    def __lt__(self, other: "HealthStatus") -> bool:
        """Enable comparison for severity ordering.

        Args:
            other: Other status to compare

        Returns:
            True if self is less severe than other
        """
        order = {HealthStatus.HEALTHY: 0, HealthStatus.DEGRADED: 1, HealthStatus.UNHEALTHY: 2}
        return order[self] < order[other]


class WorkflowPhase(str, Enum):
    """Proactive workflow phase identifiers.

    Usage:
        >>> if phase == WorkflowPhase.CONFIGURATION_SETUP:
        ...     await self._setup_with_architecture(options, plan)
    """

    CONFIGURATION_SETUP = "configuration_setup"
    FAST_HOOKS_WITH_ARCHITECTURE = "fast_hooks_with_architecture"
    ARCHITECTURAL_REFACTORING = "architectural_refactoring"
    COMPREHENSIVE_VALIDATION = "comprehensive_validation"
    PATTERN_LEARNING = "pattern_learning"
    STANDARD_WORKFLOW = "standard_workflow"

    @classmethod
    def from_string(cls, value: str) -> "WorkflowPhase":
        """Parse string to enum.

        Args:
            value: String phase value

        Returns:
            Corresponding WorkflowPhase enum

        Raises:
            ValueError: If value is not a valid phase
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(p.value for p in cls)
            raise ValueError(
                f"Invalid workflow phase: {value!r}. Valid values: {valid}"
            ) from None


class HookStatus(str, Enum):
    """Hook execution status.

    Usage:
        >>> result = HookResult(status=HookStatus.COMPLETED)
        >>> if result.status == HookStatus.FAILED:
        ...     print("Hook failed")
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"

    @classmethod
    def from_string(cls, value: str) -> "HookStatus":
        """Parse string to enum.

        Args:
            value: String status value

        Returns:
            Corresponding HookStatus enum

        Raises:
            ValueError: If value is not a valid status
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(s.value for s in cls)
            raise ValueError(
                f"Invalid hook status: {value!r}. Valid values: {valid}"
            ) from None

    @property
    def is_terminal(self) -> bool:
        """Check if status is terminal (no further transitions possible)."""
        return self in {
            HookStatus.COMPLETED,
            HookStatus.FAILED,
            HookStatus.SKIPPED,
            HookStatus.TIMEOUT,
        }

    @property
    def is_success(self) -> bool:
        """Check if status indicates success."""
        return self == HookStatus.COMPLETED

    @property
    def is_failure(self) -> bool:
        """Check if status indicates failure."""
        return self in {HookStatus.FAILED, HookStatus.TIMEOUT}


class TaskStatus(str, Enum):
    """Task execution status.

    This is the existing TaskStatus from models/task.py, moved here for consistency.

    Usage:
        >>> task = Task(id="1", name="test", status=TaskStatus.IN_PROGRESS)
        >>> if task.status == TaskStatus.COMPLETED:
        ...     print("Task complete")
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def from_string(cls, value: str) -> "TaskStatus":
        """Parse string to enum.

        Args:
            value: String status value

        Returns:
            Corresponding TaskStatus enum

        Raises:
            ValueError: If value is not a valid status
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(s.value for s in cls)
            raise ValueError(
                f"Invalid task status: {value!r}. Valid values: {valid}"
            ) from None

    @property
    def is_terminal(self) -> bool:
        """Check if status is terminal."""
        return self in {TaskStatus.COMPLETED, TaskStatus.FAILED}

    @property
    def is_active(self) -> bool:
        """Check if status is active (not terminal)."""
        return not self.is_terminal


__all__ = [
    "HealthStatus",
    "WorkflowPhase",
    "HookStatus",
    "TaskStatus",
]
