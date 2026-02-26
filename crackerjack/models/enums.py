from enum import StrEnum


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

    @classmethod
    def from_string(cls, value: str) -> "HealthStatus":
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(s.value for s in cls)
            raise ValueError(
                f"Invalid health status: {value!r}. Valid values: {valid}"
            ) from None

    def __lt__(self, other: "HealthStatus | str") -> bool:
        if isinstance(other, str) and not isinstance(other, HealthStatus):
            return NotImplemented
        order = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
        }
        other_status = other if isinstance(other, HealthStatus) else HealthStatus(other)
        return order[self] < order[other_status]


class WorkflowPhase(StrEnum):
    CONFIGURATION_SETUP = "configuration_setup"
    FAST_HOOKS_WITH_ARCHITECTURE = "fast_hooks_with_architecture"
    ARCHITECTURAL_REFACTORING = "architectural_refactoring"
    COMPREHENSIVE_VALIDATION = "comprehensive_validation"
    PATTERN_LEARNING = "pattern_learning"
    STANDARD_WORKFLOW = "standard_workflow"

    @classmethod
    def from_string(cls, value: str) -> "WorkflowPhase":
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(p.value for p in cls)
            raise ValueError(
                f"Invalid workflow phase: {value!r}. Valid values: {valid}"
            ) from None


class HookStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"

    @classmethod
    def from_string(cls, value: str) -> "HookStatus":
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(s.value for s in cls)
            raise ValueError(
                f"Invalid hook status: {value!r}. Valid values: {valid}"
            ) from None

    @property
    def is_terminal(self) -> bool:
        return self in {
            HookStatus.COMPLETED,
            HookStatus.FAILED,
            HookStatus.SKIPPED,
            HookStatus.TIMEOUT,
        }

    @property
    def is_success(self) -> bool:
        return self == HookStatus.COMPLETED

    @property
    def is_failure(self) -> bool:
        return self in {HookStatus.FAILED, HookStatus.TIMEOUT}


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def from_string(cls, value: str) -> "TaskStatus":
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(s.value for s in cls)
            raise ValueError(
                f"Invalid task status: {value!r}. Valid values: {valid}"
            ) from None

    @property
    def is_terminal(self) -> bool:
        return self in {TaskStatus.COMPLETED, TaskStatus.FAILED}

    @property
    def is_active(self) -> bool:
        return not self.is_terminal


__all__ = [
    "HealthStatus",
    "WorkflowPhase",
    "HookStatus",
    "TaskStatus",
]
