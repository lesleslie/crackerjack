"""Runtime health snapshot data structures and utilities.

Provides lightweight health snapshots for Oneiric integration, replacing
real-time WebSocket monitoring with file-based state tracking.

Example:
    >>> from pathlib import Path
    >>> import os
    >>> snapshot = RuntimeHealthSnapshot(
    ...     orchestrator_pid=os.getpid(),
    ...     watchers_running=True,
    ...     lifecycle_state={"server_status": "running"},
    ... )
    >>> write_runtime_health(Path(".oneiric_cache/runtime_health.json"), snapshot)
"""

from __future__ import annotations

import json
import typing as t
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RuntimeHealthSnapshot:
    """Runtime health snapshot for Oneiric orchestration.

    Attributes:
        orchestrator_pid: Process ID of the main server process
        watchers_running: Whether background watchers/tasks are active
        lifecycle_state: Flexible dict for runtime state (server_status, timestamps, etc.)

    Example:
        >>> import os
        >>> snapshot = RuntimeHealthSnapshot(
        ...     orchestrator_pid=os.getpid(),
        ...     watchers_running=True,
        ...     lifecycle_state={
        ...         "server_status": "running",
        ...         "start_time": "2025-12-26T10:00:00Z",
        ...     },
        ... )
    """

    orchestrator_pid: int
    watchers_running: bool
    lifecycle_state: dict[str, t.Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert snapshot to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> RuntimeHealthSnapshot:
        """Create snapshot from dictionary loaded from JSON."""
        return cls(
            orchestrator_pid=data["orchestrator_pid"],
            watchers_running=data["watchers_running"],
            lifecycle_state=data.get("lifecycle_state", {}),
        )


def write_runtime_health(path: Path, snapshot: RuntimeHealthSnapshot) -> None:
    """Write runtime health snapshot to JSON file.

    Creates parent directories if they don't exist and writes snapshot
    with pretty-printing for human readability.

    Args:
        path: Path to write snapshot JSON (typically .oneiric_cache/runtime_health.json)
        snapshot: RuntimeHealthSnapshot to persist

    Example:
        >>> from pathlib import Path
        >>> import os
        >>> snapshot = RuntimeHealthSnapshot(
        ...     orchestrator_pid=os.getpid(),
        ...     watchers_running=True,
        ...     lifecycle_state={"server_status": "running"},
        ... )
        >>> write_runtime_health(Path(".oneiric_cache/runtime_health.json"), snapshot)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(snapshot.to_dict(), f, indent=2)


def read_runtime_health(path: Path) -> RuntimeHealthSnapshot | None:
    """Read runtime health snapshot from JSON file.

    Args:
        path: Path to read snapshot JSON from

    Returns:
        RuntimeHealthSnapshot if file exists and is valid, None otherwise

    Example:
        >>> from pathlib import Path
        >>> snapshot = read_runtime_health(Path(".oneiric_cache/runtime_health.json"))
        >>> if snapshot:
        ...     print(f"Server PID: {snapshot.orchestrator_pid}")
    """
    if not path.exists():
        return None

    try:
        with path.open() as f:
            data = json.load(f)
        return RuntimeHealthSnapshot.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def write_pid_file(path: Path, pid: int) -> None:
    """Write process ID to PID file.

    Creates parent directories if they don't exist.

    Args:
        path: Path to write PID file (typically .oneiric_cache/server.pid)
        pid: Process ID to write

    Example:
        >>> from pathlib import Path
        >>> import os
        >>> write_pid_file(Path(".oneiric_cache/server.pid"), os.getpid())
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid))


def read_pid_file(path: Path) -> int | None:
    """Read process ID from PID file.

    Args:
        path: Path to read PID file from

    Returns:
        Process ID if file exists and is valid, None otherwise

    Example:
        >>> from pathlib import Path
        >>> pid = read_pid_file(Path(".oneiric_cache/server.pid"))
        >>> if pid:
        ...     print(f"Server PID: {pid}")
    """
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
