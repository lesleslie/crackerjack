from __future__ import annotations

__all__ = ["PipAuditAdapter"]


try:
    from .pip_audit import PipAuditAdapter
except ImportError:
    PipAuditAdapter = None  # type: ignore[assignment, misc, no-redef]
