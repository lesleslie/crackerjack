from __future__ import annotations

__all__ = ["OsvScannerAdapter"]


try:
    from .pip_audit import OsvScannerAdapter
except ImportError:
    OsvScannerAdapter = None  # type: ignore[assignment, misc, no-redef]
