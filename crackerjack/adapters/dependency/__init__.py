from __future__ import annotations

__all__ = ["OsvScannerAdapter", "PipAuditAdapter"]


try:
    from .pip_audit import OsvScannerAdapter
except ImportError:
    OsvScannerAdapter = None  # type: ignore[assignment, misc, no-redef]


# Backwards-compat alias for callers that still reference the pre-rename
# class name. The implementation is the same; the underlying binary changed
# from pip-audit to osv-scanner, but the class API is identical.
PipAuditAdapter = OsvScannerAdapter  # type: ignore[misc, assignment]
