#!/usr/bin/env python3
"""
LSP-aware type checking hook for crackerjack.

This hook communicates with a running Zuban LSP server to perform type checking
instead of spawning a separate zuban process, providing faster and more efficient
type checking during pre-commit hooks.
"""

import sys
from pathlib import Path

from acb.console import Console

from crackerjack.services.lsp_client import LSPClient


def main(console: Console | None = None) -> int:
    """Main entry point for LSP hook."""
    console = console or Console()
    # Get files to check from command line arguments
    files_to_check = sys.argv[1:] if len(sys.argv) > 1 else []

    # If no files specified, check project files
    if not files_to_check:
        files_to_check = _get_project_files()

    if not files_to_check:
        console.print("🔍 No Python files to check")
        return 0

    lsp_client = LSPClient()

    # Check if LSP server is running
    if not lsp_client.is_server_running():
        return _fallback_to_zuban_check(console, files_to_check)

    # Use LSP server for type checking
    return _check_files_with_lsp(console, lsp_client, files_to_check)


def _get_project_files() -> list[str]:
    """Get project files to check."""
    project_path = Path.cwd()
    lsp_client = LSPClient()
    return lsp_client.get_project_files(project_path)


def _fallback_to_zuban_check(console: Console, files_to_check: list[str]) -> int:
    """Fall back to regular zuban execution when LSP server is not running."""
    console.print("⚠️  Zuban LSP server not running, falling back to direct zuban check")
    # Fall back to regular zuban execution
    import subprocess

    try:
        result = subprocess.run(
            ["zuban", "check"] + files_to_check,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(result.stderr, style="red")
        return result.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        console.print(f"❌ Error running zuban: {e}", style="red")
        return 1


def _check_files_with_lsp(
    console: Console, lsp_client: LSPClient, files_to_check: list[str]
) -> int:
    """Check files using LSP server."""
    server_info = lsp_client.get_server_info()
    if server_info:
        console.print(f"🔍 Using Zuban LSP server (PID: {server_info['pid']})")

    # Check files via LSP
    diagnostics = lsp_client.check_files(files_to_check)

    # Display results
    output = lsp_client.format_diagnostics(diagnostics)
    console.print(output)

    # Return appropriate exit code
    has_errors = any(diags for diags in diagnostics.values())
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
