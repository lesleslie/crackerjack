"""Rust tool adapters for unified integration."""

from acb.adapters import register_adapter

from .rust_tool_adapter import Issue, RustToolAdapter, ToolResult
from .rust_tool_manager import RustToolHookManager
from .skylos_adapter import DeadCodeIssue, SkylosAdapter
from .zuban_adapter import TypeIssue, ZubanAdapter

# Register AI adapter
register_adapter("ai", "crackerjack.adapters.ai.claude", "ClaudeCodeFixer")

__all__ = [
    "RustToolAdapter",
    "ToolResult",
    "Issue",
    "SkylosAdapter",
    "DeadCodeIssue",
    "ZubanAdapter",
    "TypeIssue",
    "RustToolHookManager",
]
