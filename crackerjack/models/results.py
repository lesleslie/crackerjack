import typing as t
from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    operation_id: str
    success: bool
    duration_seconds: float
    output: str = ""
    error: str = ""
    exit_code: int = 0
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])


@dataclass
class ParallelExecutionResult:
    group_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_duration_seconds: float
    results: list[ExecutionResult]

    @property
    def success_rate(self) -> float:
        return (
            self.successful_operations / self.total_operations
            if self.total_operations > 0
            else 0.0
        )

    @property
    def overall_success(self) -> bool:
        return self.failed_operations == 0
