#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class SkillInvocation:
    skill_name: str
    invoked_at: str
    workflow_path: str | None = None
    completed: bool = False
    duration_seconds: float | None = None
    follow_up_actions: list[str] = field(default_factory=list)
    error_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class SkillMetrics:
    skill_name: str
    total_invocations: int = 0
    completed_invocations: int = 0
    abandoned_invocations: int = 0
    total_duration_seconds: float = 0.0
    workflow_paths: dict[str, int] = field(default_factory=dict)
    common_errors: dict[str, int] = field(default_factory=dict)
    follow_up_actions: dict[str, int] = field(default_factory=dict)
    first_invoked: str | None = None
    last_invoked: str | None = None

    def completion_rate(self) -> float:
        if self.total_invocations == 0:
            return 0.0
        return (self.completed_invocations / self.total_invocations) * 100

    def avg_duration_seconds(self) -> float:
        if self.completed_invocations == 0:
            return 0.0
        return self.total_duration_seconds / self.completed_invocations

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "completion_rate": self.completion_rate(),
            "avg_duration_seconds": self.avg_duration_seconds(),
        }


class SkillMetricsTracker:
    def __init__(self, metrics_file: Path | None = None) -> None:
        if metrics_file is None:
            metrics_file = Path.cwd() / ".session-buddy" / "skill_metrics.json"

        self.metrics_file = metrics_file
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        self._invocations: list[SkillInvocation] = []
        self._skill_metrics: dict[str, SkillMetrics] = {}
        self._load()

    def track_invocation(
        self,
        skill_name: str,
        workflow_path: str | None = None,
    ) -> Callable[[], None]:

        invocation = SkillInvocation(
            skill_name=skill_name,
            invoked_at=datetime.now().isoformat(),
            workflow_path=workflow_path,
        )
        self._invocations.append(invocation)

        def completer(
            *,
            completed: bool = True,
            follow_up_actions: list[str] | None = None,
            error_type: str | None = None,
        ) -> None:
            invocation.completed = completed
            invocation.follow_up_actions = follow_up_actions or []
            invocation.error_type = error_type

            invoked_at = datetime.fromisoformat(invocation.invoked_at)
            invocation.duration_seconds = (datetime.now() - invoked_at).total_seconds()

            self._update_aggregates(invocation)
            self._save()

        return completer

    def get_skill_metrics(self, skill_name: str) -> SkillMetrics | None:
        return self._skill_metrics.get(skill_name)

    def get_all_metrics(self) -> dict[str, SkillMetrics]:
        return self._skill_metrics.copy()

    def get_summary(self) -> dict[str, object]:
        if not self._skill_metrics:
            return {
                "total_skills": 0,
                "total_invocations": 0,
                "overall_completion_rate": 0.0,
                "most_used_skill": None,
                "avg_duration_seconds": 0.0,
            }

        total_invocations = sum(
            m.total_invocations for m in self._skill_metrics.values()
        )
        total_completed = sum(
            m.completed_invocations for m in self._skill_metrics.values()
        )
        most_used = max(
            self._skill_metrics.items(), key=lambda x: x[1].total_invocations
        )

        total_duration = sum(
            m.total_duration_seconds for m in self._skill_metrics.values()
        )
        total_completed_invocations = sum(
            m.completed_invocations for m in self._skill_metrics.values()
        )
        avg_duration = (
            total_duration / total_completed_invocations
            if total_completed_invocations > 0
            else 0.0
        )

        return {
            "total_skills": len(self._skill_metrics),
            "total_invocations": total_invocations,
            "overall_completion_rate": (
                (total_completed / total_invocations * 100)
                if total_invocations > 0
                else 0.0
            ),
            "most_used_skill": most_used[0],
            "most_used_count": most_used[1].total_invocations,
            "avg_duration_seconds": avg_duration,
            "skills_by_usage": sorted(
                [
                    (name, metrics.total_invocations)
                    for name, metrics in self._skill_metrics.items()
                ],
                key=lambda x: x[1],
                reverse=True,
            ),
        }

    def generate_report(self) -> str:
        summary = self.get_summary()

        lines = [
            "=" * 60,
            "Skill Metrics Report",
            "=" * 60,
            "",
            f"Total Skills Tracked: {summary['total_skills']}",
            f"Total Invocations: {summary['total_invocations']}",
            f"Overall Completion Rate: {summary['overall_completion_rate']:.1f}%",
            f"Average Duration: {summary['avg_duration_seconds']:.1f}s",
            "",
            "Most Used Skills:",
        ]

        for skill_name, count in summary.get("skills_by_usage", [])[:5]:
            metrics = self._skill_metrics[skill_name]
            lines.append(
                f"  {skill_name}: {count} invocations "
                f"({metrics.completion_rate():.1f}% complete, "
                f"{metrics.avg_duration_seconds():.1f}s avg)"
            )

        lines.extend(
            [
                "",
                "Workflow Path Preferences:",
            ]
        )

        for skill_name, _ in summary.get("skills_by_usage", [])[:3]:
            metrics = self._skill_metrics[skill_name]
            if metrics.workflow_paths:
                lines.append(f"  {skill_name}:")
                for path, count in sorted(
                    metrics.workflow_paths.items(),
                    key=lambda x: x[1],
                    reverse=True,
                ):
                    lines.append(f"    {path}: {count} uses")

        lines.extend(
            [
                "",
                "Common Follow-up Actions:",
            ]
        )

        all_actions: dict[str, int] = {}
        for metrics in self._skill_metrics.values():
            for action, count in metrics.follow_up_actions.items():
                all_actions[action] = all_actions.get(action, 0) + count

        for action, count in sorted(
            all_actions.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            lines.append(f"  {action}: {count}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def export_metrics(self, output_file: Path) -> None:
        data = {
            "summary": self.get_summary(),
            "skills": {
                name: metrics.to_dict() for name, metrics in self._skill_metrics.items()
            },
            "invocations": [inv.to_dict() for inv in self._invocations],
            "exported_at": datetime.now().isoformat(),
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(data, indent=2))

    def _update_aggregates(self, invocation: SkillInvocation) -> None:
        skill_name = invocation.skill_name

        if skill_name not in self._skill_metrics:
            self._skill_metrics[skill_name] = SkillMetrics(
                skill_name=skill_name,
                first_invoked=invocation.invoked_at,
            )

        metrics = self._skill_metrics[skill_name]
        metrics.total_invocations += 1
        metrics.last_invoked = invocation.invoked_at

        if invocation.completed:
            metrics.completed_invocations += 1
            if invocation.duration_seconds:
                metrics.total_duration_seconds += invocation.duration_seconds
        else:
            metrics.abandoned_invocations += 1

        if invocation.workflow_path:
            metrics.workflow_paths[invocation.workflow_path] = (
                metrics.workflow_paths.get(invocation.workflow_path, 0) + 1
            )

        if invocation.error_type:
            metrics.common_errors[invocation.error_type] = (
                metrics.common_errors.get(invocation.error_type, 0) + 1
            )

        for action in invocation.follow_up_actions:
            metrics.follow_up_actions[action] = (
                metrics.follow_up_actions.get(action, 0) + 1
            )

    def _load(self) -> None:
        if not self.metrics_file.exists():
            return

        try:
            data = json.loads(self.metrics_file.read_text())

            self._invocations = [
                SkillInvocation(**inv) for inv in data.get("invocations", [])
            ]

            for skill_name, skill_data in data.get("skills", {}).items():
                skill_data.pop("completion_rate", None)
                skill_data.pop("avg_duration_seconds", None)

                self._skill_metrics[skill_name] = SkillMetrics(**skill_data)
        except (json.JSONDecodeError, TypeError):
            self._invocations = []
            self._skill_metrics = {}

    def _save(self) -> None:
        data = {
            "invocations": [inv.to_dict() for inv in self._invocations],
            "skills": {
                name: metrics.to_dict() for name, metrics in self._skill_metrics.items()
            },
            "last_updated": datetime.now().isoformat(),
        }

        self.metrics_file.write_text(json.dumps(data, indent=2))


_tracker: SkillMetricsTracker | None = None


def get_tracker() -> SkillMetricsTracker:
    global _tracker
    if _tracker is None:
        _tracker = SkillMetricsTracker()
    return _tracker


def track_skill(
    skill_name: str,
    workflow_path: str | None = None,
) -> Callable[[], None]:
    return get_tracker().track_invocation(skill_name, workflow_path)
