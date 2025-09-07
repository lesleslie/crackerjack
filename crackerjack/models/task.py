import time
import typing as t
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel
from rich.console import Console


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    name: str
    status: TaskStatus
    details: str | None = None

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "details": self.details,
        }


@dataclass
class HookResult:
    id: str
    name: str
    status: str
    duration: float
    files_processed: int = 0
    issues_found: list[str] | None = None
    stage: str = "pre-commit"

    def __post_init__(self) -> None:
        if self.issues_found is None:
            self.issues_found = []


@dataclass
class TaskStatusData:
    id: str
    name: str
    status: str
    start_time: float | None = None
    end_time: float | None = None
    duration: float | None = None
    details: str | None = None
    error_message: str | None = None
    files_changed: list[str] | None = None
    hook_results: list[t.Any] | None = None

    def __post_init__(self) -> None:
        if self.files_changed is None:
            self.files_changed = []
        if self.hook_results is None:
            self.hook_results = []
        if self.start_time is not None and self.end_time is not None:
            self.duration = self.end_time - self.start_time


class SessionTracker(BaseModel, arbitrary_types_allowed=True):
    console: Console
    session_id: str
    start_time: float
    progress_file: t.Any = None
    tasks: dict[str, TaskStatusData] = {}
    current_task: str | None = None
    metadata: dict[str, t.Any] = {}

    def __init__(self, **data: t.Any) -> None:
        super().__init__(**data)
        if not self.tasks:
            self.tasks = {}
        if not self.metadata:
            self.metadata = {}

    def start_task(
        self,
        task_id: str,
        task_name: str,
        details: str | None = None,
    ) -> None:
        task = TaskStatusData(
            id=task_id,
            name=task_name,
            status="in_progress",
            start_time=time.time(),
            details=details,
        )
        self.tasks[task_id] = task
        self.current_task = task_id
        self.console.print(f"[yellow]⏳[/ yellow] Started: {task_name}")

    def complete_task(
        self,
        task_id: str,
        details: str | None = None,
        files_changed: list[str] | None = None,
    ) -> None:
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = "completed"
            task.end_time = time.time()
            task.duration = task.end_time - (task.start_time or task.end_time)
            if details:
                task.details = details
            if files_changed:
                task.files_changed = files_changed
                self.console.print(f"[green]✅[/ green] Completed: {task.name}")
            if self.current_task == task_id:
                self.current_task = None

    def fail_task(
        self,
        task_id: str,
        error_message: str,
        details: str | None = None,
    ) -> None:
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = "failed"
            task.end_time = time.time()
            task.duration = task.end_time - (task.start_time or task.end_time)
            task.error_message = error_message
            if details:
                task.details = details
                self.console.print(
                    f"[red]❌[/ red] Failed: {task.name} - {error_message}",
                )
            if self.current_task == task_id:
                self.current_task = None

    def get_summary(self) -> dict[str, t.Any]:
        completed = sum(1 for task in self.tasks.values() if task.status == "completed")
        failed = sum(1 for task in self.tasks.values() if task.status == "failed")
        in_progress = sum(
            1 for task in self.tasks.values() if task.status == "in_progress"
        )

        return {
            "session_id": self.session_id,
            "duration": time.time() - self.start_time,
            "total_tasks": len(self.tasks),
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "current_task": self.current_task,
        }
