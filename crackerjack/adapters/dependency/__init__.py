"""Dependency security adapters for Software Composition Analysis (SCA).

This module provides adapters for dependency vulnerability scanning tools
that analyze third-party packages for known security vulnerabilities (CVEs).

Available Adapters:
- PipAuditAdapter: Scans Python dependencies for known vulnerabilities

Category: SCA (Software Composition Analysis)
Purpose: Detect vulnerabilities in project dependencies
"""

from __future__ import annotations

__all__ = ["PipAuditAdapter"]

# Import adapters only if their dependencies are available
try:
    from .pip_audit import PipAuditAdapter
except ImportError:
    # pip-audit is an optional dependency (install with: uv sync --extra dependency)
    PipAuditAdapter = None  # type: ignore[assignment,misc]
