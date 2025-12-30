import asyncio
import json
import time
import typing as t
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Issue:
    id: str
    type: str
    message: str
    file_path: str
    line_number: int | None = None
    priority: Priority = Priority.MEDIUM
    stage: str = ""
    suggested_fix: str | None = None
    auto_fixable: bool = False

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class StageResult:
    stage: str
    status: StageStatus
    start_time: float
    end_time: float | None = None
    duration: float | None = None
    issues_found: list[Issue] | None = None
    fixes_applied: list[str] | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.issues_found is None:
            self.issues_found = []
        if self.fixes_applied is None:
            self.fixes_applied = []
        if self.end_time and self.start_time:
            self.duration = self.end_time - self.start_time

    def to_dict(self) -> dict[str, t.Any]:
        data = asdict(self)
        data["issues_found"] = [issue.to_dict() for issue in self.issues_found or []]
        return data


@dataclass
class SessionState:
    session_id: str
    start_time: float
    current_stage: str | None = None
    stages: dict[str, StageResult] | None = None
    global_issues: list[Issue] | None = None
    fixes_applied: list[str] | None = None
    metadata: dict[str, t.Any] | None = None

    def __post_init__(self) -> None:
        if self.stages is None:
            self.stages = {}
        if self.global_issues is None:
            self.global_issues = []
        if self.fixes_applied is None:
            self.fixes_applied = []
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, t.Any]:
        data = asdict(self)
        data["stages"] = {k: v.to_dict() for k, v in (self.stages or {}).items()}
        data["global_issues"] = [issue.to_dict() for issue in self.global_issues or []]
        return data


class StateManager:
    def __init__(
        self, state_dir: Path | None = None, batched_saver: t.Any | None = None
    ) -> None:
        self._lock = asyncio.Lock()
        self.state_dir = state_dir or Path.home() / ".cache" / "crackerjack-mcp"
        self.state_dir.mkdir(exist_ok=True)
        self.session_state = SessionState(
            session_id=self._generate_session_id(),
            start_time=time.time(),
        )
        self.checkpoints_dir = self.state_dir / "checkpoints"
        self.checkpoints_dir.mkdir(exist_ok=True)
        self._batched_saver = batched_saver

    def _generate_session_id(self) -> str:
        return str(uuid.uuid4())[:8]

    async def start_stage(self, stage: str) -> None:
        async with self._lock:
            if not self.session_state.stages:
                self.session_state.stages = {}
            self.session_state.current_stage = stage
            self.session_state.stages[stage] = StageResult(
                stage=stage,
                status=StageStatus.RUNNING,
                start_time=time.time(),
            )
            self._save_state()

    async def complete_stage(
        self,
        stage: str,
        issues: list[Issue] | None = None,
        fixes: list[str] | None = None,
    ) -> None:
        async with self._lock:
            stage_result = self._get_stage_result(stage)
            if not stage_result:
                return

            self._update_stage_completion(stage_result)
            self._process_stage_issues(stage_result, issues)
            self._process_stage_fixes(stage_result, fixes)
            self._clear_current_stage(stage)
            self._save_state()

    def _get_stage_result(self, stage: str) -> StageResult | None:
        if not self.session_state.stages or stage not in self.session_state.stages:
            return None
        return self.session_state.stages[stage]

    def _update_stage_completion(self, stage_result: StageResult) -> None:
        stage_result.status = StageStatus.COMPLETED
        stage_result.end_time = time.time()
        stage_result.duration = stage_result.end_time - stage_result.start_time

    def _process_stage_issues(
        self,
        stage_result: StageResult,
        issues: list[Issue] | None,
    ) -> None:
        if not issues:
            return
        stage_result.issues_found = issues
        if not self.session_state.global_issues:
            self.session_state.global_issues = []
        self.session_state.global_issues.extend(issues)

    def _process_stage_fixes(
        self,
        stage_result: StageResult,
        fixes: list[str] | None,
    ) -> None:
        if not fixes:
            return
        stage_result.fixes_applied = fixes
        if not self.session_state.fixes_applied:
            self.session_state.fixes_applied = []
        self.session_state.fixes_applied.extend(fixes)

    def _clear_current_stage(self, stage: str) -> None:
        if self.session_state.current_stage == stage:
            self.session_state.current_stage = None

    async def fail_stage(self, stage: str, error_message: str) -> None:
        async with self._lock:
            if not self.session_state.stages or stage not in self.session_state.stages:
                return
            stage_result = self.session_state.stages[stage]
            stage_result.status = StageStatus.FAILED
            stage_result.end_time = time.time()
            stage_result.duration = stage_result.end_time - stage_result.start_time
            stage_result.error_message = error_message
            if self.session_state.current_stage == stage:
                self.session_state.current_stage = None
            self._save_state()

    async def update_stage_status(self, stage: str, status: str) -> None:
        async with self._lock:
            if not self.session_state.stages:
                self.session_state.stages = {}
            if stage not in self.session_state.stages:
                self.session_state.stages[stage] = StageResult(
                    stage=stage,
                    status=StageStatus(status),
                    start_time=time.time(),
                )
            else:
                self.session_state.stages[stage].status = StageStatus(status)
                if status in ("completed", "failed", "error"):
                    self.session_state.stages[stage].end_time = time.time()
            self._save_state()

    async def add_issue(self, issue: Issue) -> None:
        async with self._lock:
            if not self.session_state.global_issues:
                self.session_state.global_issues = []
            self.session_state.global_issues.append(issue)
            self._save_state()

    def remove_issue(self, issue_id: str) -> bool:
        if not self.session_state.global_issues:
            return False
        initial_count = len(self.session_state.global_issues)
        self.session_state.global_issues = [
            issue for issue in self.session_state.global_issues if issue.id != issue_id
        ]
        removed = len(self.session_state.global_issues) < initial_count
        if removed:
            self._save_state()

        return removed

    def get_issues_by_priority(self, priority: Priority) -> list[Issue]:
        if not self.session_state.global_issues:
            return []

        return [
            issue
            for issue in self.session_state.global_issues
            if issue.priority == priority
        ]

    def get_issues_by_type(self, issue_type: str) -> list[Issue]:
        if not self.session_state.global_issues:
            return []

        return [
            issue
            for issue in self.session_state.global_issues
            if issue.type == issue_type
        ]

    def get_auto_fixable_issues(self) -> list[Issue]:
        if not self.session_state.global_issues:
            return []

        return [
            issue for issue in self.session_state.global_issues if issue.auto_fixable
        ]

    def get_session_summary(self) -> dict[str, t.Any]:
        stages = self.session_state.stages or {}
        issues = self.session_state.global_issues or []
        fixes = self.session_state.fixes_applied or []
        priority_counts = {}
        for priority in Priority:
            priority_counts[priority.value] = len(self.get_issues_by_priority(priority))
        type_counts: dict[str, int] = {}
        for issue in issues:
            type_counts[issue.type] = type_counts.get(issue.type, 0) + 1
        stage_status = {}
        for stage_name, stage_result in stages.items():
            stage_status[stage_name] = stage_result.status.value

        return {
            "session_id": self.session_state.session_id,
            "duration": time.time() - self.session_state.start_time,
            "current_stage": self.session_state.current_stage,
            "stages": stage_status,
            "total_issues": len(issues),
            "issues_by_priority": priority_counts,
            "issues_by_type": type_counts,
            "total_fixes": len(fixes),
            "auto_fixable_issues": len(self.get_auto_fixable_issues()),
        }

    async def save_checkpoint(self, name: str) -> None:
        async with self._lock:
            checkpoint_file = self.checkpoints_dir / f"{name}.json"
            checkpoint_data = {
                "name": name,
                "timestamp": time.time(),
                "session_state": self.session_state.to_dict(),
            }
            with checkpoint_file.open("w") as f:
                json.dump(checkpoint_data, f, indent=2)

    def load_checkpoint(self, name: str) -> bool:
        checkpoint_file = self.checkpoints_dir / f"{name}.json"
        if not checkpoint_file.exists():
            return False
        try:
            with checkpoint_file.open() as f:
                checkpoint_data = json.load(f)
            session_data = checkpoint_data["session_state"]
            self.session_state = SessionState(
                session_id=session_data["session_id"],
                start_time=session_data["start_time"],
                current_stage=session_data.get("current_stage"),
                metadata=session_data.get("metadata", {}),
            )
            stages = {}
            for stage_name, stage_data in session_data.get("stages", {}).items():
                issues = [
                    Issue(**issue_data)
                    for issue_data in stage_data.get("issues_found", [])
                ]
                stages[stage_name] = StageResult(
                    stage=stage_data["stage"],
                    status=StageStatus(stage_data["status"]),
                    start_time=stage_data["start_time"],
                    end_time=stage_data.get("end_time"),
                    duration=stage_data.get("duration"),
                    issues_found=issues,
                    fixes_applied=stage_data.get("fixes_applied", []),
                    error_message=stage_data.get("error_message"),
                )
            self.session_state.stages = stages
            global_issues = [
                Issue(**issue_data)
                for issue_data in session_data.get("global_issues", [])
            ]
            self.session_state.global_issues = global_issues
            self.session_state.fixes_applied = session_data.get("fixes_applied", [])
            self._save_state()
            return True
        except Exception:
            return False

    def list_checkpoints(self) -> list[dict[str, t.Any]]:
        checkpoints: list[dict[str, t.Any]] = []
        for checkpoint_file in self.checkpoints_dir.glob("*.json"):
            try:
                with checkpoint_file.open() as f:
                    data = json.load(f)
                checkpoints.append(
                    {
                        "name": data.get("name", checkpoint_file.stem),
                        "timestamp": data.get("timestamp", 0),
                        "file": str(checkpoint_file),
                    },
                )
            except Exception:
                continue
        import operator

        checkpoints.sort(key=operator.itemgetter("timestamp"), reverse=True)
        return checkpoints

    def start_session(self) -> None:
        self._save_state()

    def complete_session(self) -> None:
        if not self.session_state.metadata:
            self.session_state.metadata = {}
        self.session_state.metadata["status"] = "completed"
        self.session_state.metadata["completed_time"] = time.time()
        self._save_state()

    async def reset_session(self) -> None:
        async with self._lock:
            self.session_state = SessionState(
                session_id=self._generate_session_id(),
                start_time=time.time(),
            )
            self._save_state()

    def _save_state(self) -> None:
        if self._batched_saver:
            save_func = self._save_state_sync

            save_func()
        else:
            self._save_state_sync()

    def _save_state_sync(self) -> None:
        state_file = self.state_dir / "current_session.json"
        try:
            with state_file.open("w") as f:
                json.dump(self.session_state.to_dict(), f, indent=2)
        except (OSError, json.JSONEncodeError):
            pass
        except Exception:
            pass

    def _load_state(self) -> bool:
        state_file = self.state_dir / "current_session.json"
        if not state_file.exists():
            return False
        try:
            with state_file.open() as f:
                session_data = json.load(f)
            checkpoint_data = {"session_state": session_data}
            temp_checkpoint = self.checkpoints_dir / "_temp.json"
            with temp_checkpoint.open("w") as f:
                json.dump(checkpoint_data, f)
            result = self.load_checkpoint("_temp")
            temp_checkpoint.unlink(missing_ok=True)

            return result
        except Exception:
            return False
