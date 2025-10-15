"""LSP adapter consolidation for Rust-based analysis tools.

This module consolidates all LSP-related adapter functionality:
- Zuban: Type checking with LSP integration
- Skylos: Dead code detection
- Base protocols and tool result structures
- Manager for coordinating multiple tools
"""

from ._base import BaseRustToolAdapter, Issue, RustToolAdapter, ToolResult
from ._client import ZubanLSPClient
from ._manager import RustToolHookManager
from .skylos import DeadCodeIssue, SkylosAdapter
from .zuban import TypeIssue, ZubanAdapter

__all__ = [
    "RustToolAdapter",
    "BaseRustToolAdapter",
    "ToolResult",
    "Issue",
    "SkylosAdapter",
    "DeadCodeIssue",
    "ZubanAdapter",
    "TypeIssue",
    "RustToolHookManager",
    "ZubanLSPClient",
]
