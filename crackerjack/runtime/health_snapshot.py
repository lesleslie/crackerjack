from __future__ import annotations

import json
import typing as t
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RuntimeHealthSnapshot:
    orchestrator_pid: int
    watchers_running: bool
    lifecycle_state: dict[str, t.Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> RuntimeHealthSnapshot:
        return cls(
            orchestrator_pid=data["orchestrator_pid"],
            watchers_running=data["watchers_running"],
            lifecycle_state=data.get("lifecycle_state", {}),
        )


def write_runtime_health(path: Path, snapshot: RuntimeHealthSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(snapshot.to_dict(), f, indent=2)


def read_runtime_health(path: Path) -> RuntimeHealthSnapshot | None:
    if not path.exists():
        return None

    try:
        with path.open() as f:
            data = json.load(f)
        return RuntimeHealthSnapshot.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def write_pid_file(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid))


def read_pid_file(path: Path) -> int | None:
    if not path.exists():
        return None

    try:
        return int(path.read_text().strip())
    except (ValueError, OSError):
        return None


__all__ = [
    "RuntimeHealthSnapshot",
    "write_runtime_health",
    "read_runtime_health",
    "write_pid_file",
    "read_pid_file",
]
