from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class SessionMetrics:
    session_id: str
    project_path: Path
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: int | None = None

    git_commit_velocity: float | None = None
    git_branch_count: int | None = None
    git_merge_success_rate: float | None = None
    conventional_commit_compliance: float | None = None
    git_workflow_efficiency_score: float | None = None

    tests_run: int | None = None
    tests_passed: int | None = None
    test_pass_rate: float | None = None
    ai_fixes_applied: int | None = None
    quality_gate_passes: int | None = None

    def __post_init__(self) -> None:

        percentage_fields = {
            "git_merge_success_rate": self.git_merge_success_rate,
            "conventional_commit_compliance": self.conventional_commit_compliance,
            "test_pass_rate": self.test_pass_rate,
        }

        for field_name, value in percentage_fields.items():
            if value is not None:
                if not 0.0 <= value <= 1.0:
                    msg = f"{field_name} must be between 0.0 and 1.0, got {value}"
                    raise ValueError(msg)

        score_fields = {
            "git_workflow_efficiency_score": self.git_workflow_efficiency_score,
        }

        for field_name, value in score_fields.items():
            if value is not None:
                if not 0 <= value <= 100:
                    msg = f"{field_name} must be between 0 and 100, got {value}"
                    raise ValueError(msg)

        non_negative_fields = {
            "duration_seconds": self.duration_seconds,
            "git_branch_count": self.git_branch_count,
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "ai_fixes_applied": self.ai_fixes_applied,
            "quality_gate_passes": self.quality_gate_passes,
        }

        for field_name, value in non_negative_fields.items():
            if value is not None and value < 0:
                msg = f"{field_name} must be non-negative, got {value}"
                raise ValueError(msg)

        if self.git_commit_velocity is not None and self.git_commit_velocity < 0:
            msg = f"git_commit_velocity must be non-negative, got {self.git_commit_velocity}"
            raise ValueError(msg)

        if self.start_time and self.end_time and self.duration_seconds is None:
            self.duration_seconds = int(
                (self.end_time - self.start_time).total_seconds()
            )

        if (
            self.tests_run
            and self.tests_passed is not None
            and self.test_pass_rate is None
        ):
            if self.tests_run > 0:
                self.test_pass_rate = self.tests_passed / self.tests_run
            else:
                self.test_pass_rate = 0.0

    def calculate_duration(self) -> int | None:
        if self.start_time and self.end_time:
            self.duration_seconds = int(
                (self.end_time - self.start_time).total_seconds()
            )
            logger.debug(
                f"Calculated duration for session {self.session_id}: {self.duration_seconds}s"
            )
        else:
            logger.debug(
                f"Cannot calculate duration for session {self.session_id}: "
                f"start_time={self.start_time}, end_time={self.end_time}"
            )
        return self.duration_seconds

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        if isinstance(data.get("project_path"), Path):
            data["project_path"] = str(data["project_path"])

        if data.get("start_time") and isinstance(data["start_time"], datetime):
            data["start_time"] = data["start_time"].isoformat()

        if data.get("end_time") and isinstance(data["end_time"], datetime):
            data["end_time"] = data["end_time"].isoformat()

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMetrics:

        required_fields = ["session_id", "project_path", "start_time"]
        missing_fields = [f for f in required_fields if f not in data]

        if missing_fields:
            msg = f"Missing required fields: {', '.join(missing_fields)}"
            raise ValueError(msg)

        project_path = data["project_path"]
        if isinstance(project_path, str):
            project_path = Path(project_path)

        start_time = data["start_time"]
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)

        end_time = data.get("end_time")
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)

        return cls(
            session_id=str(data["session_id"]),
            project_path=project_path,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=cast(int | None, data.get("duration_seconds")),
            git_commit_velocity=cast(float | None, data.get("git_commit_velocity")),
            git_branch_count=cast(int | None, data.get("git_branch_count")),
            git_merge_success_rate=cast(
                float | None, data.get("git_merge_success_rate")
            ),
            conventional_commit_compliance=cast(
                float | None, data.get("conventional_commit_compliance")
            ),
            git_workflow_efficiency_score=cast(
                float | None, data.get("git_workflow_efficiency_score")
            ),
            tests_run=cast(int | None, data.get("tests_run")),
            tests_passed=cast(int | None, data.get("tests_passed")),
            test_pass_rate=cast(float | None, data.get("test_pass_rate")),
            ai_fixes_applied=cast(int | None, data.get("ai_fixes_applied")),
            quality_gate_passes=cast(int | None, data.get("quality_gate_passes")),
        )

    def get_summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "session_id": self.session_id,
            "duration_seconds": self.duration_seconds,
            "tests_passed": self.tests_passed,
            "tests_run": self.tests_run,
            "test_pass_rate": self.test_pass_rate,
        }

        if any(
            [
                self.git_commit_velocity is not None,
                self.git_branch_count is not None,
                self.git_merge_success_rate is not None,
            ]
        ):
            summary["git_metrics"] = {
                "commit_velocity": self.git_commit_velocity,
                "branch_count": self.git_branch_count,
                "merge_success_rate": self.git_merge_success_rate,
                "conventional_compliance": self.conventional_commit_compliance,
                "efficiency_score": self.git_workflow_efficiency_score,
            }

        if any(
            [
                self.ai_fixes_applied is not None,
                self.quality_gate_passes is not None,
            ]
        ):
            summary["quality_metrics"] = {
                "ai_fixes_applied": self.ai_fixes_applied,
                "quality_gate_passes": self.quality_gate_passes,
            }

        return summary


__all__ = ["SessionMetrics"]
