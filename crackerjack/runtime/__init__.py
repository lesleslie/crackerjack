"""Runtime health snapshot infrastructure for Oneiric integration.

Provides file-based health snapshots in .oneiric_cache/ for process monitoring
and orchestration integration without requiring live HTTP endpoints.
"""

from .health_snapshot import (
    RuntimeHealthSnapshot,
    write_runtime_health,
    read_runtime_health,
    write_pid_file,
)

__all__ = [
    "RuntimeHealthSnapshot",
    "write_runtime_health",
    "read_runtime_health",
    "write_pid_file",
]
